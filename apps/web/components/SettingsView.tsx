"use client";

import { useState } from "react";
import type { BusyAction, CurrentUser, Material, StyleProfile } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

type SettingsViewProps = {
  currentUser: CurrentUser | null;
  materials: Material[];
  styles: StyleProfile[];
  generationCount: number;
  busyAction: BusyAction;
  onSendPhoneCode: (phone: string) => Promise<string>;
  onBindPhone: (phone: string, code: string) => Promise<CurrentUser>;
  onSendEmailCode: (email: string) => Promise<string>;
  onBindEmail: (email: string, code: string) => Promise<CurrentUser>;
  onChangePassword: (oldPassword: string, newPassword: string, confirmPassword: string) => Promise<void>;
  onLogout: () => void;
};

export function SettingsView({
  currentUser,
  materials,
  styles,
  generationCount,
  busyAction,
  onSendPhoneCode,
  onBindPhone,
  onSendEmailCode,
  onBindEmail,
  onChangePassword,
  onLogout,
}: SettingsViewProps) {
  const { requireAuth, setCurrentUser } = useAuth();
  const [phoneNumber, setPhoneNumber] = useState(currentUser?.phone_number ?? "");
  const [phoneCode, setPhoneCode] = useState("");
  const [phoneDebugCode, setPhoneDebugCode] = useState("");
  const [accountError, setAccountError] = useState("");
  const [accountStatus, setAccountStatus] = useState("");
  const [emailAddress, setEmailAddress] = useState(currentUser?.email ?? "");
  const [emailCode, setEmailCode] = useState("");
  const [emailDebugCode, setEmailDebugCode] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [showPasswordSuccessModal, setShowPasswordSuccessModal] = useState(false);
  const [activeTab, setActiveTab] = useState<"profile" | "security" | "usage" | "privacy">("profile");

  const busy = busyAction !== null;

  async function handleSendCode() {
    if (!requireAuth()) return;
    setAccountError("");
    setAccountStatus("");
    try {
      const debugCode = await onSendPhoneCode(phoneNumber.trim());
      setPhoneDebugCode(debugCode);
      setAccountStatus("测试验证码已生成。当前版本不真实发送短信，请使用下方显示的验证码。");
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleBindPhone() {
    if (!requireAuth()) return;
    setAccountError("");
    setAccountStatus("");
    try {
      const updated = await onBindPhone(phoneNumber.trim(), phoneCode.trim());
      setPhoneDebugCode("");
      setPhoneCode("");
      setAccountStatus("手机号已绑定。");
      setCurrentUser(updated);
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleSendEmailCode() {
    if (!requireAuth()) return;
    setAccountError("");
    setAccountStatus("");
    try {
      const debugCode = await onSendEmailCode(emailAddress.trim());
      setEmailDebugCode(debugCode);
      setAccountStatus("测试验证码已生成。当前版本不真实发送邮件，请使用下方显示的验证码。");
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleBindEmail() {
    if (!requireAuth()) return;
    setAccountError("");
    setAccountStatus("");
    try {
      const updated = await onBindEmail(emailAddress.trim(), emailCode.trim());
      setEmailDebugCode("");
      setEmailCode("");
      setAccountStatus("邮箱已绑定。");
      setCurrentUser(updated);
    } catch (err) {
      setAccountError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleChangePassword() {
    if (!requireAuth()) return;
    setPasswordError("");
    try {
      await onChangePassword(oldPassword, newPassword, confirmPassword);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowPasswordSuccessModal(true);
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : String(err));
    }
  }

  function handleLogout() {
    onLogout();
  }

  if (!currentUser) {
    return (
      <div className="empty-state">
        <div className="empty-state-title">请先登录</div>
        <div className="empty-state-desc">登录后可以查看和管理账号设置</div>
      </div>
    );
  }

  const displayName = currentUser.display_name || currentUser.username;
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <div>
      <div className="breadcrumb">
        <span className="breadcrumb-item">设置</span>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-item current">账号设置</span>
      </div>

      <div className="settings-tabs">
        <button
          className={`settings-tab ${activeTab === "profile" ? "active" : ""}`}
          onClick={() => setActiveTab("profile")}
        >
          个人资料
        </button>
        <button
          className={`settings-tab ${activeTab === "security" ? "active" : ""}`}
          onClick={() => setActiveTab("security")}
        >
          安全设置
        </button>
        <button
          className={`settings-tab ${activeTab === "usage" ? "active" : ""}`}
          onClick={() => setActiveTab("usage")}
        >
          用量与额度
        </button>
        <button
          className={`settings-tab ${activeTab === "privacy" ? "active" : ""}`}
          onClick={() => setActiveTab("privacy")}
        >
          数据与隐私
        </button>
      </div>

      {activeTab === "profile" ? (
        <div style={{ display: "grid", gap: "20px" }}>
          <div className="card">
            <div className="settings-section-title">基本信息</div>
            <div style={{ display: "flex", gap: "20px", alignItems: "flex-start" }}>
              <div className="avatar-circle">{initial}</div>
              <div style={{ flex: 1 }}>
                <div className="form-row">
                  <div className="form-field">
                    <label className="form-label">用户名</label>
                    <input className="form-input" value={currentUser.username} disabled style={{ background: "var(--bg-subtle)" }} />
                  </div>
                  <div className="form-field">
                    <label className="form-label">显示名称</label>
                    <input className="form-input" value={displayName} disabled style={{ background: "var(--bg-subtle)" }} />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-field">
                    <label className="form-label">手机号</label>
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <input
                        className="form-input"
                        value={phoneNumber}
                        placeholder="例如：13800138000"
                        onChange={(e) => setPhoneNumber(e.target.value)}
                        style={{ flex: 1 }}
                      />
                      {currentUser.phone_verified ? (
                        <span className="badge badge-success">已绑定</span>
                      ) : null}
                    </div>
                    <span className="form-hint">当前只支持中国大陆手机号。验证码为测试模式，不真实发送短信。</span>
                  </div>
                  <div className="form-field">
                    <label className="form-label">用户模式</label>
                    <input className="form-input" value={currentUser.mode === "admin" ? "管理员" : "标准用户"} disabled style={{ background: "var(--bg-subtle)" }} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="settings-section-title">手机号绑定</div>
            <div style={{ display: "flex", gap: "12px", alignItems: "flex-end", flexWrap: "wrap" }}>
              <div className="form-field" style={{ flex: 1, minWidth: "200px" }}>
                <label className="form-label">验证码</label>
                <input
                  className="form-input"
                  value={phoneCode}
                  onChange={(e) => setPhoneCode(e.target.value)}
                  placeholder="输入验证码"
                />
              </div>
              <button className="btn btn-secondary" type="button" disabled={busy} onClick={handleSendCode}>
                {busy ? "处理中……" : "发送测试验证码"}
              </button>
              <button className="btn btn-primary" type="button" disabled={busy} onClick={handleBindPhone}>
                绑定手机号
              </button>
            </div>
            {phoneDebugCode ? (
              <p className="inline-status">测试验证码：{phoneDebugCode}</p>
            ) : null}
            {accountStatus ? <p className="inline-status">{accountStatus}</p> : null}
            {accountError ? <p className="inline-error" role="alert">{accountError}</p> : null}
          </div>

          <div className="card">
            <div className="settings-section-title">账号操作</div>
            <button className="btn btn-danger" type="button" disabled={busy} onClick={handleLogout}>
              退出登录
            </button>
          </div>
        </div>
      ) : null}

      {activeTab === "security" ? (
        <div style={{ display: "grid", gap: "20px" }}>
          <div className="card">
            <div className="settings-section-title">修改密码</div>
            <div className="form-field">
              <label className="form-label">当前密码</label>
              <input
                className="form-input"
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
              />
            </div>
            <div className="form-field">
              <label className="form-label">新密码</label>
              <input
                className="form-input"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="8-64 位，至少包含 1 个字母和 1 个数字"
              />
            </div>
            <div className="form-field">
              <label className="form-label">确认新密码</label>
              <input
                className="form-input"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
            <button className="btn btn-primary" type="button" disabled={busy} onClick={handleChangePassword}>
              修改密码
            </button>
            {passwordError ? <p className="inline-error" role="alert">{passwordError}</p> : null}
          </div>

          <div className="card">
            <div className="settings-section-title">绑定邮箱</div>
            {currentUser?.email_verified && currentUser?.email ? (
              <div className="form-field">
                <label className="form-label">邮箱</label>
                <div className="settings-bound-value">
                  <span style={{ wordBreak: "break-all" }}>{currentUser.email}</span>
                  <span className="badge badge-success">已绑定</span>
                </div>
                <span className="form-hint">已绑定邮箱将用于接收重要通知。</span>
              </div>
            ) : (
              <>
                <div className="form-field">
                  <label className="form-label">邮箱</label>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <input
                      className="form-input"
                      value={emailAddress}
                      placeholder="例如：you@example.com"
                      onChange={(e) => setEmailAddress(e.target.value)}
                      style={{ flex: 1 }}
                    />
                  </div>
                  <span className="form-hint">用于接收重要通知。验证码为测试模式，不真实发送邮件。</span>
                </div>
                <div style={{ display: "flex", gap: "12px", alignItems: "flex-end", flexWrap: "wrap" }}>
                  <div className="form-field" style={{ flex: 1, minWidth: "200px" }}>
                    <label className="form-label">验证码</label>
                    <input
                      className="form-input"
                      value={emailCode}
                      onChange={(e) => setEmailCode(e.target.value)}
                      placeholder="输入验证码"
                    />
                  </div>
                  <button className="btn btn-secondary" type="button" disabled={busy} onClick={handleSendEmailCode}>
                    发送测试验证码
                  </button>
                  <button className="btn btn-primary" type="button" disabled={busy} onClick={handleBindEmail}>
                    绑定邮箱
                  </button>
                </div>
                {emailDebugCode ? (
                  <p className="inline-status">测试验证码：{emailDebugCode}</p>
                ) : null}
                {accountStatus ? <p className="inline-status">{accountStatus}</p> : null}
                {accountError ? <p className="inline-error" role="alert">{accountError}</p> : null}
              </>
            )}
          </div>
        </div>
      ) : null}

      {activeTab === "usage" ? (
        <div className="card">
          <div className="settings-section-title">
            本月用量 <span style={{ fontSize: "13px", color: "var(--text-tertiary)", fontWeight: 400 }}>· {currentUser.mode === "admin" ? "管理员" : "免费版"}</span>
          </div>
          <div className="usage-grid">
            <div>
              <div className="usage-item-label">参考作品</div>
              <div className="usage-item-value">{materials.length}<span className="usage-item-unit">篇</span></div>
              <div className="usage-bar">
                <div className="usage-bar-fill" style={{ width: `${Math.min(100, materials.length * 10)}%`, background: "var(--accent)" }} />
              </div>
            </div>
            <div>
              <div className="usage-item-label">风格档案</div>
              <div className="usage-item-value">{styles.length}<span className="usage-item-unit">个</span></div>
              <div className="usage-bar">
                <div className="usage-bar-fill" style={{ width: `${Math.min(100, styles.length * 20)}%`, background: "var(--success)" }} />
              </div>
            </div>
            <div>
              <div className="usage-item-label">生成文章</div>
              <div className="usage-item-value">{generationCount}<span className="usage-item-unit">篇</span></div>
              <div className="usage-bar">
                <div className="usage-bar-fill" style={{ width: `${Math.min(100, generationCount * 5)}%`, background: "var(--warning)" }} />
              </div>
            </div>
          </div>

          <div className="upgrade-banner">
            <div className="upgrade-banner-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: "18px", height: "18px" }}>
                <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 16.8l-6.2 4.5 2.4-7.4L2 9.4h7.6z" />
              </svg>
            </div>
            <div className="upgrade-banner-text">
              <div className="upgrade-banner-title">升级到专业版</div>
              <div className="upgrade-banner-desc">解锁无限文章生成、更多风格档案、优先排队</div>
            </div>
            <button className="btn btn-primary btn-sm" type="button">了解详情</button>
          </div>
        </div>
      ) : null}

      {activeTab === "privacy" ? (
        <div className="card">
          <div className="settings-section-title">数据与隐私</div>
          <div style={{ display: "grid", gap: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: "0.5px solid var(--border-default)" }}>
              <div>
                <div style={{ fontSize: "14px", fontWeight: 500 }}>素材默认私有</div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>你上传的作品仅自己可见，不参与模型训练</div>
              </div>
              <span className="badge badge-success">已启用</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: "0.5px solid var(--border-default)" }}>
              <div>
                <div style={{ fontSize: "14px", fontWeight: 500 }}>数据隔离</div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>你的风格档案和文章数据在数据库层与你绑定，他人无法访问</div>
              </div>
              <span className="badge badge-success">已启用</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0" }}>
              <div>
                <div style={{ fontSize: "14px", fontWeight: 500 }}>删除风格不影响历史文章</div>
                <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>删除风格档案后，已生成的文章仍然保留</div>
              </div>
              <span className="badge badge-success">已启用</span>
            </div>
          </div>
        </div>
      ) : null}

      {showPasswordSuccessModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <div className="modal-success">
              <div className="modal-success-icon">✓</div>
              <div className="modal-success-title">密码已修改成功</div>
              <div className="modal-success-desc">你的登录密码已更新，下次登录请使用新密码。</div>
              <button
                className="btn btn-primary"
                type="button"
                onClick={() => setShowPasswordSuccessModal(false)}
                style={{ minWidth: "120px" }}
              >
                确认
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
