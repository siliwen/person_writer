"use client";

import { useEffect, useState } from "react";
import {
  AdminPromptTemplate,
  fetchAdminPromptTemplates,
  resetAdminPromptTemplate,
  updateAdminPromptTemplate,
} from "@/lib/api";

const PURPOSE_LABELS: Record<string, string> = {
  optimize_prompt: "优化提示词",
  style_analysis: "分析文章风格",
  style_writing: "按风格编写文章",
  free_writing: "无风格自由写作",
  article_evaluation: "文章鉴评",
  revise: "无风格文章改写",
};

function labelOf(purpose: string): string {
  return PURPOSE_LABELS[purpose] ?? purpose;
}

export function AdminPromptTemplates() {
  const [items, setItems] = useState<AdminPromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<AdminPromptTemplate | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminPromptTemplates();
      setItems(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载提示词模板失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function openEdit(t: AdminPromptTemplate) {
    setEditing(t);
    setDraft(t.system_prompt);
  }

  async function doReset(t: AdminPromptTemplate) {
    try {
      const updated = await resetAdminPromptTemplate(t.id);
      setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
      if (editing && editing.id === updated.id) setDraft(updated.system_prompt);
    } catch (e) {
      setError(e instanceof Error ? e.message : "重置失败");
    }
  }

  async function save() {
    if (!editing) return;
    setSaving(true);
    try {
      const updated = await updateAdminPromptTemplate(editing.id, { system_prompt: draft });
      setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
      setEditing(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="empty-state">加载中…</div>;
  }

  return (
    <div className="admin-prompt-templates">
      <header className="admin-section-header">
        <h2 className="admin-section-title">提示词模板</h2>
        <p className="admin-section-desc">
          6 类系统提示词均可在后台直接编辑，保存后立即生效；未配置时自动回退代码内置默认。
        </p>
      </header>

      {error && <div className="admin-error-bar">{error}</div>}

      <div className="prompt-tpl-list">
        {items.map((t) => (
          <div className="prompt-tpl-row" key={t.id}>
            <div className="prompt-tpl-main">
              <div className="prompt-tpl-name">{labelOf(t.purpose)}</div>
              <code className="prompt-tpl-purpose">{t.purpose}</code>
              <div className="prompt-tpl-preview">{t.system_prompt.slice(0, 56)}…</div>
              <div className="prompt-tpl-updated">
                更新于 {t.updated_at ? t.updated_at.slice(0, 10) : "—"}
              </div>
            </div>
            <div className="prompt-tpl-actions">
              <button type="button" className="btn-ghost-danger" onClick={() => doReset(t)}>
                重置默认
              </button>
              <button type="button" className="btn-primary" onClick={() => openEdit(t)}>
                编辑
              </button>
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <div
          className="modal-backdrop"
          onClick={() => {
            if (!saving) setEditing(null);
          }}
        >
          <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="admin-modal-title">编辑「{labelOf(editing.purpose)}」</h3>

            <label className="admin-form-label">用途标识</label>
            <div className="admin-readonly-box">
              <code>{editing.purpose}</code>
            </div>

            <label className="admin-form-label">模板名称（只读）</label>
            <div className="admin-readonly-box">{editing.name}</div>

            <label className="admin-form-label">系统提示词 (system_prompt)</label>
            <textarea
              className="prompt-tpl-textarea"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={10}
            />

            <div className="admin-modal-actions">
              <button
                type="button"
                className="btn-ghost-danger"
                onClick={() => doReset(editing)}
                disabled={saving}
              >
                重置为默认
              </button>
              <span className="admin-modal-spacer" />
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setEditing(null)}
                disabled={saving}
              >
                取消
              </button>
              <button type="button" className="btn-primary" onClick={save} disabled={saving}>
                {saving ? "保存中…" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
