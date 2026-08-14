#!/usr/bin/env python3
"""临时生产更新控制台（独立进程，无鉴权，用完即删）。

仅你本人使用，不做任何鉴权/审计——这是有意为之的临时运维工具，部署完成后请删除本目录并关停进程。

端点：
  GET  /              -> 返回 index.html
  POST /api/check     -> 读取 incoming 目录 tar 内的 deploy-manifest.json，返回版本/checksum/磁盘信息
  POST /api/update    -> 后台执行 update-from-tar.sh（解压日志写入 LOG_PATH），返回是否启动
  GET  /api/status    -> {running, exit_code, log_path}
  GET  /api/log?lines=N -> 返回最近 N 行日志（默认 200）
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tarfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
MOXX_ROOT = os.environ.get("MOXX_ROOT", "/opt/moxx")
PORT = int(os.environ.get("PORT", "9000"))
INCOMING = os.path.join(MOXX_ROOT, "incoming")
TAR = os.path.join(INCOMING, "moxx-deploy.tar.gz")
SCRIPT = os.path.join(HERE, "update-from-tar.sh")
LOG_PATH = os.path.join(MOX_ROOT := MOXX_ROOT, "update-console.log")

proc = None  # 当前运行的更新子进程


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_manifest(tar_path: str):
    try:
        with tarfile.open(tar_path) as tf:
            try:
                member = tf.getmember("deploy-manifest.json")
            except KeyError:
                return None
            data = tf.extractfile(member).read().decode("utf-8")
        return json.loads(data)
    except Exception:
        return None


def _disk_free_mb() -> int:
    try:
        import shutil

        return shutil.disk_usage(MOXX_ROOT).free // (1024 * 1024)
    except Exception:
        return -1


def build_check_payload() -> dict:
    payload = {
        "tar_exists": os.path.exists(TAR),
        "incoming_manifest": None,
        "current_manifest": None,
        "size_bytes": None,
        "sha256": None,
        "disk_free_mb": _disk_free_mb(),
    }
    if os.path.exists(TAR):
        payload["size_bytes"] = os.path.getsize(TAR)
        payload["sha256"] = _sha256(TAR)
        payload["incoming_manifest"] = _read_manifest(TAR)
    cur = os.path.join(MOXX_ROOT, "deploy-manifest.json")
    if os.path.exists(cur):
        try:
            with open(cur, "r", encoding="utf-8") as f:
                payload["current_manifest"] = json.load(f)
        except Exception:
            payload["current_manifest"] = None
    return payload


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, status: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, text: str):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            try:
                with open(os.path.join(HERE, "index.html"), "r", encoding="utf-8") as f:
                    self._send_html(f.read())
            except FileNotFoundError:
                self._send_text("index.html not found", 500)
            return
        if parsed.path == "/api/status":
            running = proc is not None and proc.poll() is None
            self._send_json({
                "running": running,
                "exit_code": proc.poll() if proc else None,
                "log_path": LOG_PATH,
            })
            return
        if parsed.path == "/api/log":
            qs = parse_qs(parsed.query)
            n = int(qs.get("lines", ["200"])[0])
            try:
                with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
                self._send_json({"text": "\n".join(lines[-n:])})
            except FileNotFoundError:
                self._send_json({"text": "(暂无日志)"})
            return
        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/check":
            self._send_json(build_check_payload())
            return
        if parsed.path == "/api/update":
            global proc
            if proc is not None and proc.poll() is None:
                self._send_json({"started": False, "error": "已有更新任务在运行"}, 409)
                return
            if not os.path.exists(TAR):
                self._send_json({"started": False, "error": f"未找到更新包：{TAR}"}, 400)
                return
            # 清空旧日志；脚本内部 tee 会写入 LOG_PATH，子进程 stdout 丢弃避免重复
            open(LOG_PATH, "w").close()
            env = dict(os.environ)
            env["LOG"] = LOG_PATH
            env["MOXX_ROOT"] = MOXX_ROOT
            proc = subprocess.Popen(
                ["bash", SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                env=env,
            )
            self._send_json({"started": True, "pid": proc.pid})
            return
        self._send_json({"error": "not found"}, 404)

    def log_message(self, *args):  # 静默默认访问日志
        return


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"临时更新控制台已启动: http://<ECS_IP>:{PORT}/")
    print(f"  更新包目录: {INCOMING}")
    print(f"  日志文件:   {LOG_PATH}")
    print("  用完请删除 deploy-console 目录并结束本进程。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
