"use client";

import { useEffect, useMemo, useState } from "react";
import {
  createAdminMessage,
  createAdminTemplate,
  deleteAdminTemplate,
  fetchAdminMessages,
  fetchAdminTemplates,
  fetchAdminTiers,
  fetchAdminUsers,
  fetchRecipientPreview,
  recallAdminMessage,
  updateAdminTemplate,
} from "@/lib/api";
import { useEscapeClose } from "@/lib/useEscapeClose";
import type { AdminMessage, AdminTier, AdminUser, MessageTemplate } from "@/lib/types";

type ScopeType = "all" | "tier" | "specific";

export function AdminMessages() {
  const [messages, setMessages] = useState<AdminMessage[]>([]);
  const [tiers, setTiers] = useState<AdminTier[]>([]);
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 撰写表单
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState("announcement");
  const [scope, setScope] = useState<ScopeType>("all");
  const [selectedTiers, setSelectedTiers] = useState<string[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<Array<{ id: string; username: string }>>([]);
  const [userQuery, setUserQuery] = useState("");
  const [userResults, setUserResults] = useState<AdminUser[]>([]);
  const [pinned, setPinned] = useState(false);
  const [important, setImportant] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  const [previewCount, setPreviewCount] = useState<number | null>(null);

  // 发送确认弹窗
  const [confirmOpen, setConfirmOpen] = useState(false);

  // 发送确认弹窗：ESC 关闭
  useEscapeClose(() => setConfirmOpen(false), confirmOpen);

  // 模板编辑
  const [tplOpen, setTplOpen] = useState(false);
  const [tplName, setTplName] = useState("");
  const [tplTitle, setTplTitle] = useState("");
  const [tplBody, setTplBody] = useState("");

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [msgRes, tierRes, tplRes] = await Promise.all([
        fetchAdminMessages({ page: 1, page_size: 50 }),
        fetchAdminTiers(),
        fetchAdminTemplates(),
      ]);
      setMessages(msgRes.items);
      setTiers(tierRes.items ?? tierRes);
      setTemplates(tplRes.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  // 指定用户搜索
  useEffect(() => {
    if (scope !== "specific" || !userQuery.trim()) {
      setUserResults([]);
      return;
    }
    let active = true;
    fetchAdminUsers({ q: userQuery.trim(), page_size: 10 })
      .then((res) => {
        if (active) setUserResults(res.items.filter((u) => !selectedUsers.some((s) => s.id === u.user_id)));
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [userQuery, scope, selectedUsers]);

  function scopeLabel(m: AdminMessage): string {
    if (m.target_type === "all") return "全员";
    if (m.target_type === "tier") return `等级：${(m.target_tiers ?? []).join("、") || "—"}`;
    if (m.target_type === "specific") return `指定 ${(m.target_user_ids ?? []).length} 人`;
    return m.target_type;
  }

  async function handlePreview() {
    try {
      const res = await fetchRecipientPreview({
        target_type: scope,
        target_tiers: scope === "tier" ? selectedTiers : [],
        target_user_ids: scope === "specific" ? selectedUsers.map((u) => u.id) : [],
      });
      setPreviewCount(res.recipient_count);
    } catch (e) {
      setError(e instanceof Error ? e.message : "预估失败");
    }
  }

  const canSend = useMemo(
    () => title.trim().length > 0 && body.trim().length > 0,
    [title, body]
  );

  function validateScope(): string | null {
    if (scope === "tier" && selectedTiers.length === 0) return "请至少选择一个会员等级";
    if (scope === "specific" && selectedUsers.length === 0) return "请至少指定一个用户";
    return null;
  }

  async function doSend() {
    const scopeErr = validateScope();
    if (scopeErr) {
      setError(scopeErr);
      return;
    }
    if (!canSend) {
      setError("标题与正文均不能为空");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await createAdminMessage({
        title: title.trim(),
        body: body.trim(),
        category,
        target_type: scope,
        target_tiers: scope === "tier" ? selectedTiers : [],
        target_user_ids: scope === "specific" ? selectedUsers.map((u) => u.id) : [],
        channels: ["in_app"],
        pinned,
        important,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      });
      setConfirmOpen(false);
      setPreviewCount(null);
      setTitle("");
      setBody("");
      setPinned(false);
      setImportant(false);
      setScheduledAt("");
      setSelectedTiers([]);
      setSelectedUsers([]);
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "发送失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRecall(id: string) {
    if (!confirm("确认撤回该消息？撤回后用户侧将不再展示。")) return;
    setBusy(true);
    try {
      await recallAdminMessage(id);
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "撤回失败");
    } finally {
      setBusy(false);
    }
  }

  function applyTemplate(tpl: MessageTemplate) {
    setTitle(tpl.title);
    setBody(tpl.body);
    setCategory(tpl.category);
  }

  async function handleSaveTemplate() {
    if (!tplName.trim() || !tplTitle.trim() || !tplBody.trim()) {
      setError("模板名称、标题、正文均不能为空");
      return;
    }
    try {
      await createAdminTemplate({ name: tplName.trim(), title: tplTitle.trim(), body: tplBody.trim(), category });
      setTplOpen(false);
      setTplName("");
      setTplTitle("");
      setTplBody("");
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存模板失败");
    }
  }

  async function handleDeleteTemplate(id: string) {
    if (!confirm("确认删除该模板？")) return;
    try {
      await deleteAdminTemplate(id);
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除模板失败");
    }
  }

  return (
    <div className="admin-messages">
      {/* 撰写表单 */}
      <div className="admin-card">
        <div className="admin-card-title">撰写并发送</div>
        {error ? <div className="admin-error">{error}</div> : null}
        <div className="admin-form-grid">
          <label className="admin-field">
            <span>标题</span>
            <input
              className="admin-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="请输入消息标题"
            />
          </label>
          <label className="admin-field">
            <span>分类</span>
            <select className="admin-input" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="announcement">公告</option>
              <option value="system">系统通知</option>
              <option value="direct">私信</option>
            </select>
          </label>
        </div>

        <label className="admin-field">
          <span>正文</span>
          <textarea
            className="admin-textarea"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="支持换行，纯文本"
            rows={4}
          />
        </label>

        <div className="admin-field">
          <span>接收范围</span>
          <div className="admin-segmented">
            {(["all", "tier", "specific"] as ScopeType[]).map((s) => (
              <button
                key={s}
                type="button"
                className={`admin-seg ${scope === s ? "active" : ""}`}
                onClick={() => setScope(s)}
              >
                {s === "all" ? "全员" : s === "tier" ? "按等级" : "指定用户"}
              </button>
            ))}
          </div>
        </div>

        {scope === "tier" ? (
          <div className="admin-field">
            <span>选择等级（可多选）</span>
            <div className="admin-chip-row">
              {tiers.map((t) => (
                <label key={t.code} className="admin-check">
                  <input
                    type="checkbox"
                    checked={selectedTiers.includes(t.code)}
                    onChange={(e) =>
                      setSelectedTiers((prev) =>
                        e.target.checked ? [...prev, t.code] : prev.filter((c) => c !== t.code)
                      )
                    }
                  />
                  {t.name}
                </label>
              ))}
            </div>
          </div>
        ) : null}

        {scope === "specific" ? (
          <div className="admin-field">
            <span>指定用户</span>
            <input
              className="admin-input"
              value={userQuery}
              onChange={(e) => setUserQuery(e.target.value)}
              placeholder="搜索用户名"
            />
            {userResults.length > 0 ? (
              <div className="admin-user-results">
                {userResults.map((u) => (
                  <button
                    key={u.user_id}
                    type="button"
                    className="admin-user-result"
                    onClick={() => {
                      setSelectedUsers((prev) => [...prev, { id: u.user_id, username: u.username }]);
                      setUserQuery("");
                      setUserResults([]);
                    }}
                  >
                    {u.username}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="admin-chip-row">
              {selectedUsers.map((u) => (
                <span key={u.id} className="admin-chip">
                  {u.username}
                  <button
                    type="button"
                    className="admin-chip-x"
                    onClick={() => setSelectedUsers((prev) => prev.filter((s) => s.id !== u.id))}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="admin-form-grid">
          <label className="admin-check">
            <input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} />
            置顶
          </label>
          <label className="admin-check">
            <input type="checkbox" checked={important} onChange={(e) => setImportant(e.target.checked)} />
            重要
          </label>
          <label className="admin-field">
            <span>定时发送（可选）</span>
            <input
              className="admin-input"
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
            />
          </label>
        </div>

        <div className="admin-form-actions">
          <button type="button" className="btn btn-ghost" onClick={handlePreview} disabled={!canSend}>
            预估送达人数
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              const scopeErr = validateScope();
              if (scopeErr) {
                setError(scopeErr);
                return;
              }
              if (!canSend) {
                setError("标题与正文均不能为空");
                return;
              }
              handlePreview().then(() => setConfirmOpen(true));
            }}
            disabled={!canSend || busy}
          >
            发送
          </button>
        </div>
      </div>

      {/* 已发列表 */}
      <div className="admin-card">
        <div className="admin-card-title">
          已发消息
          <button type="button" className="btn btn-link" onClick={() => setTplOpen((o) => !o)}>
            {tplOpen ? "收起模板" : "消息模板"}
          </button>
        </div>
        {tplOpen ? (
          <div className="admin-tpl-box">
            <div className="admin-tpl-list">
              {templates.length === 0 ? <div className="admin-hint">暂无模板</div> : null}
              {templates.map((t) => (
                <div key={t.id} className="admin-tpl-item">
                  <button type="button" className="admin-tpl-apply" onClick={() => applyTemplate(t)}>
                    应用：{t.name}
                  </button>
                  <button type="button" className="admin-tpl-del" onClick={() => handleDeleteTemplate(t.id)}>
                    删除
                  </button>
                </div>
              ))}
            </div>
            <div className="admin-tpl-create">
              <input className="admin-input" placeholder="模板名称" value={tplName} onChange={(e) => setTplName(e.target.value)} />
              <input className="admin-input" placeholder="标题" value={tplTitle} onChange={(e) => setTplTitle(e.target.value)} />
              <textarea className="admin-textarea" placeholder="正文" value={tplBody} onChange={(e) => setTplBody(e.target.value)} rows={2} />
              <button type="button" className="btn btn-primary btn-sm" onClick={handleSaveTemplate}>
                保存模板
              </button>
            </div>
          </div>
        ) : null}
        {loading ? <div className="admin-hint">加载中…</div> : null}
        {!loading && messages.length === 0 ? <div className="admin-hint">还没有发送过消息</div> : null}
        <div className="admin-msg-list">
          {messages.map((m) => (
            <div key={m.id} className={`admin-msg-row ${m.important ? "important" : ""}`}>
              <div className="admin-msg-main">
                <div className="admin-msg-title">
                  {m.pinned ? <span className="style-card-badge recommended">置顶</span> : null}
                  {m.important ? <span className="style-card-badge important">重要</span> : null}
                  {m.is_automated ? <span className="style-card-badge">系统</span> : null}
                  {m.title}
                </div>
                <div className="admin-msg-meta">
                  {scopeLabel(m)} · 送达 {m.recipient_count}
                  {typeof m.read_count === "number" ? ` · 已读 ${m.read_count}` : ""}
                  {m.status === "recalled" ? " · 已撤回" : ""}
                  {m.sent_at ? ` · ${new Date(m.sent_at).toLocaleString("zh-CN")}` : ""}
                </div>
              </div>
              {m.status !== "recalled" ? (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => handleRecall(m.id)} disabled={busy}>
                  撤回
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      {/* 发送确认弹窗 */}
      {confirmOpen ? (
        <div className="modal-backdrop" onClick={() => setConfirmOpen(false)}>
          <div className="modal-card admin-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">确认发送</div>
            <div className="modal-body">
              标题：<b>{title}</b>
              <br />
              接收范围：
              <b>
                {scope === "all" ? "全员" : scope === "tier" ? `等级 ${(selectedTiers).join("、")}` : `指定 ${selectedUsers.length} 人`}
              </b>
              <br />
              预计送达：<b>{previewCount ?? "—"}</b> 人
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setConfirmOpen(false)}>
                取消
              </button>
              <button type="button" className="btn btn-primary" onClick={doSend} disabled={busy}>
                确认发送
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
