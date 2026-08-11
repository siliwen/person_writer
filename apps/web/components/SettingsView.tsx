"use client";

import { useEffect, useState } from "react";
import type { BusyAction, CurrentUser, Material, QuotaView, StyleProfile, UsageRecord } from "@/lib/types";
import { fetchUsage } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useEscapeClose } from "@/lib/useEscapeClose";

type SettingsViewProps = {
  currentUser: CurrentUser | null;
  quota: QuotaView | null;
  materials: Material[];
  styles: StyleProfile[];
  generationCount: number;
  busyAction: BusyAction;
  initialTab?: "profile" | "security" | "usage" | "privacy";
  onSendPhoneCode: (phone: string) => Promise<string>;
  onBindPhone: (phone: string, code: string) => Promise<CurrentUser>;
  onSendEmailCode: (email: string) => Promise<string>;
  onBindEmail: (email: string, code: string) => Promise<CurrentUser>;
  onChangePassword: (oldPassword: string, newPassword: string, confirmPassword: string) => Promise<void>;
  onLogout: () => void;
};

const OP_TYPE_LABELS: Record<string, string> = {
  style_analysis: "风格分析",
  article_generation: "文章生成",
  paragraph_rewrite: "段落重写",
  admin_adjust: "管理员调整",
};

function formatOpType(opType: string): string {
  return OP_TYPE_LABELS[opType] ?? opType;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("zh-CN", { hour12: false });
}

export function SettingsView({
  currentUser,
  quota,
  materials,
  styles,
  generationCount,
  busyAction,
  initialTab = "profile",
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
  const [activeTab, setActiveTab] = useState<"profile" | "security" | "usage" | "privacy">(initialTab);

  // 密码修改成功弹窗：ESC 关闭
  useEscapeClose(() => setShowPasswordSuccessModal(false), showPasswordSuccessModal);
  const [usageRecords, setUsageRecords] = useState<UsageRecord[]>([]);
  const [usageLoading, setUsageLoading] = useState(false);

  const busy = busyAction !== null;

  /* 界面主题（纸墨 / 墨韵紫 / 瑞士现代），保存在本机 localStorage */
  const THEME_KEY = "moxx-theme";
  type ThemeName = "ink" | "violet" | "swiss";
  const [theme, setTheme] = useState<ThemeName>("ink");
  useEffect(() => {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === "ink" || saved === "violet" || saved === "swiss") setTheme(saved);
    } catch {}
  }, []);
  function applyTheme(next: ThemeName) {
    setTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
      document.documentElement.setAttribute("data-theme", next);
    } catch {}
  }

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (activeTab === "usage") {
      void loadUsage();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  async function loadUsage() {
    setUsageLoading(true);
    try {
      const page = await fetchUsage(1, 50);
      setUsageRecords(page.items);
    } catch {
      setUsageRecords([]);
    } finally {
      setUsageLoading(false);
    }
  }

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
            <div className="settings-section-title">界面主题</div>
            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => applyTheme("ink")}
                style={{
                  flex: "1 1 200px",
                  textAlign: "left",
                  padding: "14px",
                  borderRadius: "var(--radius-md)",
                  border: theme === "ink" ? "2px solid var(--accent)" : "1px solid var(--border-default)",
                  background: theme === "ink" ? "var(--accent-light-bg)" : "var(--bg-surface)",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <span
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: "#FDFBF7",
                      border: "1px solid var(--border-strong)",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#1A1A1A",
                      fontWeight: 600,
                      fontSize: 13,
                    }}
                  >
                    墨
                  </span>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>纸墨</span>
                  {theme === "ink" ? (
                    <span className="badge badge-success" style={{ marginLeft: "auto" }}>
                      当前
                    </span>
                  ) : null}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  纸色背景 · 墨黑强调 · 衬线字体（默认）
                </div>
              </button>
              <button
                type="button"
                onClick={() => applyTheme("violet")}
                style={{
                  flex: "1 1 200px",
                  textAlign: "left",
                  padding: "14px",
                  borderRadius: "var(--radius-md)",
                  border: theme === "violet" ? "2px solid var(--accent)" : "1px solid var(--border-default)",
                  background: theme === "violet" ? "var(--accent-light-bg)" : "var(--bg-surface)",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <span
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: "#534ab7",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#ffffff",
                      fontWeight: 600,
                      fontSize: 13,
                    }}
                  >
                    墨
                  </span>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>墨韵紫</span>
                  {theme === "violet" ? (
                    <span className="badge badge-success" style={{ marginLeft: "auto" }}>
                      当前
                    </span>
                  ) : null}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  经典紫调界面 · 无衬线字体
                </div>
              </button>
              <button
                type="button"
                onClick={() => applyTheme("swiss")}
                style={{
                  flex: "1 1 200px",
                  textAlign: "left",
                  padding: "14px",
                  borderRadius: "var(--radius-md)",
                  border: theme === "swiss" ? "2px solid var(--accent)" : "1px solid var(--border-default)",
                  background: theme === "swiss" ? "var(--accent-light-bg)" : "var(--bg-surface)",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                  <span
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "2px",
                      background: "#E5231B",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#FFFFFF",
                      fontWeight: 600,
                      fontSize: 13,
                    }}
                  >
                    瑞
                  </span>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>瑞士现代</span>
                  {theme === "swiss" ? (
                    <span className="badge badge-success" style={{ marginLeft: "auto" }}>
                      当前
                    </span>
                  ) : null}
                </div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  中性灰底 · 正红强调 · 零圆角黑描边
                </div>
              </button>
            </div>
            <p className="form-hint" style={{ marginTop: 12 }}>
              主题设置保存在本机浏览器，切换后立即生效。
            </p>
          </div>

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
        <div style={{ display: "grid", gap: "20px" }}>
          <div className="card">
            <div className="settings-section-title">
              会员与额度
              {quota ? (
                <span style={{ fontSize: "13px", color: "var(--text-tertiary)", fontWeight: 400 }}>
                  · {quota.tier.name}
                  {currentUser?.is_admin ? "（管理员）" : ""}
                </span>
              ) : null}
            </div>

            {quota ? (
              <>
                <div className="quota-summary">
                  <div className="quota-summary-main">
                    <div className="quota-summary-value">{quota.points_balance}</div>
                    <div className="quota-summary-label">剩余积分 / 本月 {quota.tier.monthly_points}</div>
                  </div>
                  <div className="quota-summary-side">
                    <div>单篇最大长度：{quota.tier.max_article_length > 0 ? `${quota.tier.max_article_length} 字` : "不限"}</div>
                    <div>额度重置日：{formatDateTime(quota.quota_period_end)}</div>
                    <div>下载：{quota.tier.can_download ? "支持" : "不支持"} · 重写：{quota.tier.can_rewrite ? "支持" : "不支持"}</div>
                  </div>
                </div>
              </>
            ) : (
              <p className="inline-status">额度信息加载中……</p>
            )}
          </div>

          <div className="card">
            <div className="settings-section-title">积分消耗历史</div>
            {usageLoading ? (
              <p className="inline-status">加载中……</p>
            ) : usageRecords.length === 0 ? (
              <p className="inline-status">还没有积分消耗记录。</p>
            ) : (
              <div className="usage-history">
                <div className="usage-history-row usage-history-head">
                  <span>操作</span>
                  <span>消耗</span>
                  <span>时间</span>
                </div>
                {usageRecords.map((r) => (
                  <div className="usage-history-row" key={r.id}>
                    <span>{formatOpType(r.op_type)}</span>
                    <span className={r.points_consumed >= 0 ? "usage-cost" : "usage-gain"}>
                      {r.points_consumed >= 0 ? `-${r.points_consumed}` : `+${Math.abs(r.points_consumed)}`} 分
                    </span>
                    <span>{formatDateTime(r.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
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
