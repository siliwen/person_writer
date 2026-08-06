import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = PROJECT_ROOT / "eval_sets" / "mvp_style_eval_v1"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env.local"
DEFAULT_REQUESTS_PATH = EVAL_ROOT / "prompt_packets" / "generation_requests.jsonl"
DEFAULT_MANIFEST_PATH = EVAL_ROOT / "material_manifest.csv"
DEFAULT_GENERATION_MANIFEST_PATH = EVAL_ROOT / "generation_manifest.csv"
DEFAULT_RETRIEVAL_EVENTS_PATH = EVAL_ROOT / "retrieval_events.jsonl"

GENERATION_MANIFEST_FIELDS = [
    "generation_id",
    "task_id",
    "writer_id",
    "variant",
    "prompt_version",
    "style_profile_id",
    "model_provider",
    "model_name",
    "temperature",
    "top_p",
    "input_token_count",
    "output_token_count",
    "output_path",
    "generated_at",
    "operator",
    "notes",
]


def load_env(path: Path) -> dict[str, str]:
    env = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def require_config(env: dict[str, str]) -> dict[str, str]:
    api_key = env.get("DASHSCOPE_API_KEY") or env.get("OPENAI_API_KEY")
    if not api_key or "填入" in api_key or "xxxxxxxx" in api_key:
        raise SystemExit(
            "Missing API key. Fill DASHSCOPE_API_KEY in .env.local before running generation."
        )
    base_url = env.get("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
    return {
        "model_provider": env.get("MODEL_PROVIDER", "alibaba_bailian"),
        "base_url": base_url,
        "api_key": api_key,
        "model_name": env.get("MODEL_NAME", "qwen-plus"),
        "temperature": env.get("TEMPERATURE", "0.7"),
        "top_p": env.get("TOP_P", "0.9"),
        "timeout": env.get("REQUEST_TIMEOUT_SECONDS", "120"),
        "sleep": env.get("REQUEST_SLEEP_SECONDS", "0.5"),
    }


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    tree = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in tree.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def chunk_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [item.strip() for item in text.splitlines() if item.strip()]
    chunks = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars])
            continue
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 1 <= max_chars:
            current += "\n" + paragraph
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def tokenize(text: str) -> set[str]:
    latin = re.findall(r"[A-Za-z0-9_]+", text.lower())
    chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    grams = []
    for item in chinese:
        grams.extend(item[index : index + 2] for index in range(max(0, len(item) - 1)))
    return set(latin + grams)


def retrieve_chunks(request: dict, manifest_by_id: dict[str, dict[str, str]]) -> tuple[list[dict], list[str]]:
    policy = request["retrieval_policy"]
    if not policy["enabled"]:
        return [], []
    query_text = request.get("retrieval_query") or policy.get("query") or request["user_prompt"]
    query_tokens = tokenize(query_text)
    max_chunks = int(policy.get("max_chunks", 6))
    max_chars = int(policy.get("max_chars_per_chunk", 500))
    scored = []
    for material_id in policy["allowed_material_ids"]:
        row = manifest_by_id[material_id]
        text = extract_docx_text(PROJECT_ROOT / row["source_path"])
        for index, chunk in enumerate(chunk_text(text, max_chars), start=1):
            overlap = len(query_tokens & tokenize(chunk))
            # Keep a little deterministic variety even when lexical overlap is sparse.
            score = overlap + min(len(chunk), max_chars) / (max_chars * 100)
            scored.append((score, material_id, f"{material_id}_chunk_{index:04d}", chunk))
    picked = sorted(scored, key=lambda item: item[0], reverse=True)[:max_chunks]
    results = [
        {
            "material_id": material_id,
            "chunk_id": chunk_id,
            "score": round(score, 6),
            "char_start": 0,
            "char_end": len(chunk),
        }
        for score, material_id, chunk_id, chunk in picked
    ]
    snippets = [
        f"[{chunk_id} | {material_id}]\n{chunk}"
        for score, material_id, chunk_id, chunk in picked
    ]
    return results, snippets


def load_style_profile(path_value: str) -> tuple[str, str]:
    if not path_value:
        return "", ""
    path = PROJECT_ROOT / path_value
    data = json.load(path.open(encoding="utf-8"))
    return data["style_profile_id"], json.dumps(data, ensure_ascii=False, indent=2)


def build_messages(request: dict, style_profile_json: str, rag_snippets: list[str]) -> list[dict[str, str]]:
    user_parts = [request["user_prompt"]]
    if style_profile_json:
        user_parts.append("Style Profile JSON：\n```json\n" + style_profile_json + "\n```")
    if rag_snippets:
        if request.get("variant") == "style_profile_rag_v2" or request["retrieval_policy"].get("evidence_mode"):
            usage_instruction = request.get(
                "rag_usage_instruction",
                "Style Profile 是主规范；RAG 片段只作为风格机制证据，不作为内容素材库。不要复制原句、专名、真实作品名或完整意象组合。",
            )
            user_parts.append(
                "RAG 风格机制证据（只作参考，不是素材库）：\n"
                + "\n\n".join(rag_snippets)
                + "\n\n使用规则：\n"
                + usage_instruction
            )
        else:
            user_parts.append(
                "RAG 风格证据片段：\n"
                + "\n\n".join(rag_snippets)
                + "\n\n要求：只学习语气、节奏、结构和意象倾向，不要复制片段原句。"
            )
    return [
        {"role": "system", "content": request["system_prompt"]},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def call_openai_compatible(config: dict[str, str], messages: list[dict[str, str]]) -> dict:
    payload = {
        "model": config["model_name"],
        "messages": messages,
        "temperature": float(config["temperature"]),
        "top_p": float(config["top_p"]),
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        config["base_url"] + "/chat/completions",
        data=data,
        headers={
            "Authorization": "Bearer " + config["api_key"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(config["timeout"])) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def output_content(response: dict) -> str:
    return response["choices"][0]["message"]["content"]


def token_usage(response: dict) -> tuple[str, str]:
    usage = response.get("usage", {})
    return str(usage.get("prompt_tokens", "")), str(usage.get("completion_tokens", ""))


def append_retrieval_event(path: Path, request: dict, results: list[dict]) -> None:
    if not results:
        return
    event = {
        "generation_id": request["generation_id"],
        "task_id": request["task_id"],
        "tenant_id": "internal_eval",
        "writer_id": request["writer_id"],
        "query": request["user_prompt"],
        "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "results": results,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def existing_generation_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {row["generation_id"] for row in read_csv_rows(path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--requests", default=str(DEFAULT_REQUESTS_PATH))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--variant", default="")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    env = load_env(Path(args.env))
    config = None if args.dry_run else require_config(env)
    requests = read_jsonl(Path(args.requests))
    if args.variant:
        requests = [item for item in requests if item["variant"] == args.variant]
    if args.task_id:
        requests = [item for item in requests if item["task_id"] == args.task_id]
    if args.limit:
        requests = requests[: args.limit]

    manifest_by_id = {row["material_id"]: row for row in read_csv_rows(DEFAULT_MANIFEST_PATH)}
    manifest_rows = read_csv_rows(DEFAULT_GENERATION_MANIFEST_PATH)
    completed = set() if args.overwrite else existing_generation_ids(DEFAULT_GENERATION_MANIFEST_PATH)

    print(f"requests selected: {len(requests)}")
    if args.dry_run:
        for request in requests[:5]:
            print(request["generation_id"], request["variant"], request["output_path"])
        return

    for index, request in enumerate(requests, start=1):
        if request["generation_id"] in completed:
            print(f"skip completed {request['generation_id']}")
            continue
        style_profile_id, style_profile_json = load_style_profile(request["style_profile_path"])
        retrieval_results, rag_snippets = retrieve_chunks(request, manifest_by_id)
        messages = build_messages(request, style_profile_json, rag_snippets)
        print(f"[{index}/{len(requests)}] generating {request['generation_id']}")
        response = call_openai_compatible(config, messages)
        content = output_content(response)
        prompt_tokens, completion_tokens = token_usage(response)

        output_path = PROJECT_ROOT / request["output_path"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content.strip() + "\n", encoding="utf-8")
        append_retrieval_event(DEFAULT_RETRIEVAL_EVENTS_PATH, request, retrieval_results)

        manifest_rows.append(
            {
                "generation_id": request["generation_id"],
                "task_id": request["task_id"],
                "writer_id": request["writer_id"],
                "variant": request["variant"],
                "prompt_version": request["prompt_version"],
                "style_profile_id": style_profile_id,
                "model_provider": config["model_provider"],
                "model_name": config["model_name"],
                "temperature": config["temperature"],
                "top_p": config["top_p"],
                "input_token_count": prompt_tokens,
                "output_token_count": completion_tokens,
                "output_path": request["output_path"],
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "operator": "run_generation_plan.py",
                "notes": "",
            }
        )
        write_csv_rows(DEFAULT_GENERATION_MANIFEST_PATH, manifest_rows, GENERATION_MANIFEST_FIELDS)
        time.sleep(float(config["sleep"]))

    print("done")


if __name__ == "__main__":
    main()
