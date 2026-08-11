"use client";

import { useState } from "react";
import type { AuthMode, CurrentUser } from "@/lib/types";
import { apiBase, parseJson } from "@/lib/api";
import { useEscapeClose } from "@/lib/useEscapeClose";

type AuthModalProps = {
  mode: AuthMode;
  onClose: () => void;
  onSuccess: (user: CurrentUser) => void;
  onModeChange: (mode: AuthMode) => void;
};

export function AuthModal({ mode, onClose, onSuccess, onModeChange }: AuthModalProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // 提交中不允许 ESC 关闭，避免请求半途丢失上下文
  useEscapeClose(onClose, !loading);

  async function handleSubmit() {
    setError("");
    if (!username.trim()) {
      setError("请填写用户名。");
      return;
    }
    if (!password) {
      setError("请填写密码。");
      return;
    }
    if (mode === "register" && password !== confirmPassword) {
      setError("两次输入的密码不一致。");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${apiBase()}/v1/auth/${mode === "login" ? "login" : "register"}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: username.trim(),
          password,
          confirm_password: confirmPassword,
        }),
      });
      const body = await parseJson<{ user: CurrentUser }>(response);
      onSuccess(body.user);
      setPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop auth-modal" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="auth-split" onClick={(e) => e.stopPropagation()}>
        <div className="auth-brand">
          <div className="auth-brand-logo">墨</div>
          <div>
            <h2 className="auth-brand-title">个人风格写作</h2>
            <p className="auth-brand-desc">
              上传你的作品，提取独属于你的写作风格，让 AI 按你的风格生成文章、散文、小说和诗歌。
            </p>
            <p className="auth-brand-feature">风格档案 · 段落级重写 · 多文体支持</p>
          </div>
        </div>
        <div className="auth-form-side">
          <div className="auth-tabs">
            <button
              type="button"
              className={`auth-tab ${mode === "login" ? "active" : ""}`}
              onClick={() => { onModeChange("login"); setError(""); }}
            >
              登录
            </button>
            <button
              type="button"
              className={`auth-tab ${mode === "register" ? "active" : ""}`}
              onClick={() => { onModeChange("register"); setError(""); }}
            >
              注册
            </button>
          </div>
          <p className="form-hint" style={{ marginBottom: "16px" }}>
            用户名 6–32 位，只允许英文字母、数字、下划线。密码 8–64 位，至少包含 1 个字母和 1 个数字。
          </p>
          <div className="form-field">
            <label className="form-label">用户名</label>
            <input
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
            />
          </div>
          <div className="form-field">
            <label className="form-label">密码</label>
            <input
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
            />
          </div>
          {mode === "register" ? (
            <div className="form-field">
              <label className="form-label">确认密码</label>
              <input
                className="form-input"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="请再次输入密码"
              />
            </div>
          ) : null}
          <button
            className="btn btn-primary"
            type="button"
            disabled={loading}
            onClick={handleSubmit}
            style={{ width: "100%", marginTop: "4px" }}
          >
            {loading ? "处理中……" : mode === "login" ? "登录" : "注册并登录"}
          </button>
          <button
            className="btn btn-ghost"
            type="button"
            onClick={() => setError("手机号找回密码入口已预留，完整流程后续接入。")}
            style={{ width: "100%", marginTop: "8px" }}
          >
            忘记密码？
          </button>
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
        </div>
      </div>
    </div>
  );
}
