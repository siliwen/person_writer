"use client";

import { useCallback, useEffect, useState } from "react";
import type { AdminStyle } from "@/lib/types";
import { fetchAdminStyles, setAdminStyleRecommended, updateStyleProfile } from "@/lib/api";

type AdminRecommendedProps = {
  onNewStyle: () => void;
};

export function AdminRecommended({ onNewStyle }: AdminRecommendedProps) {
  const [items, setItems] = useState<AdminStyle[]>([]);
  const [onlyRecommended, setOnlyRecommended] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [editingStyle, setEditingStyle] = useState<AdminStyle | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const stylesRes = await fetchAdminStyles({ recommended_only: onlyRecommended });
      setItems(stylesRes.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [onlyRecommended]);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(style: AdminStyle) {
    setBusyId(style.id);
    setError("");
    try {
      await setAdminStyleRecommended(style.id, !style.is_recommended);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  }

  function openEdit(style: AdminStyle) {
    setEditingStyle(style);
    setEditName(style.name);
    setEditDescription(style.description ?? "");
    setEditError("");
  }

  function closeEdit() {
    if (editBusy) return;
    setEditingStyle(null);
  }

  async function saveEdit() {
    if (!editingStyle) return;
    const name = editName.trim();
    if (!name) {
      setEditError("风格名称不能为空");
      return;
    }
    setEditBusy(true);
    setEditError("");
    try {
      await updateStyleProfile(editingStyle.id, {
        name,
        description: editDescription.trim() || null,
      });
      await load();
      setEditingStyle(null);
    } catch (e) {
      setEditError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setEditBusy(false);
    }
  }

  return (
    <div>
      <div className="admin-list-toolbar">
        <div className="admin-filter-group">
          <button
            type="button"
            className={`admin-filter-chip ${!onlyRecommended ? "active" : ""}`}
            onClick={() => setOnlyRecommended(false)}
          >
            全部风格
          </button>
          <button
            type="button"
            className={`admin-filter-chip ${onlyRecommended ? "active" : ""}`}
            onClick={() => setOnlyRecommended(true)}
          >
            仅推荐
          </button>
        </div>
        <div className="admin-toolbar-right">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void load()} disabled={loading}>
            刷新
          </button>
          <button type="button" className="btn btn-primary btn-sm" onClick={onNewStyle}>
            新建推荐风格
          </button>
        </div>
      </div>

      <p className="admin-hint">
        管理员走「新建推荐风格」会进入与普通用户一致的流程：上传参考文章 → 自动提取风格 → 生成风格档案。创建完成后回到此页，将对应风格设为「推荐」即可对所有用户可见。
      </p>

      {error ? <p className="inline-error" role="alert">{error}</p> : null}

      {loading ? (
        <p className="inline-status">加载中……</p>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">还没有风格</div>
          <div className="empty-state-desc">点击右上角「新建推荐风格」开始创建。</div>
        </div>
      ) : (
        <div className="admin-style-list">
          {items.map((style) => (
            <div key={style.id} className={`admin-style-row ${style.is_recommended ? "recommended" : ""}`}>
              <div className="admin-style-main">
                <span className="admin-style-name">{style.name}</span>
                {style.is_recommended ? (
                  <span className="style-card-badge recommended">推荐</span>
                ) : null}
              </div>
              <div className="admin-style-actions">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={busyId === style.id}
                  onClick={() => openEdit(style)}
                >
                  编辑
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${style.is_recommended ? "btn-ghost" : "btn-primary"}`}
                  disabled={busyId === style.id}
                  onClick={() => toggle(style)}
                >
                  {busyId === style.id
                    ? "处理中……"
                    : style.is_recommended
                      ? "取消推荐"
                      : "设为推荐"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editingStyle ? (
        <div className="modal-backdrop" onClick={closeEdit}>
          <div className="modal-dialog admin-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">编辑风格</div>
              <button className="modal-close" type="button" onClick={closeEdit} aria-label="关闭">×</button>
            </div>
            <div className="modal-body">
              {editError ? <p className="inline-error" role="alert">{editError}</p> : null}
              <div className="admin-form-grid">
                <label className="admin-form-field">
                  <span className="admin-form-label">
                    风格名称
                    <span className="admin-required">*</span>
                  </span>
                  <input
                    className="form-input"
                    type="text"
                    value={editName}
                    disabled={editBusy}
                    onChange={(e) => setEditName(e.target.value)}
                  />
                </label>
                <label className="admin-form-field">
                  <span className="admin-form-label">介绍文字</span>
                  <textarea
                    className="form-input"
                    rows={4}
                    value={editDescription}
                    disabled={editBusy}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="会显示在推荐风格卡片底部，最多两行"
                  />
                </label>
              </div>
              <div className="admin-modal-actions">
                <button className="btn btn-ghost btn-sm" type="button" onClick={closeEdit} disabled={editBusy}>
                  取消
                </button>
                <button className="btn btn-primary btn-sm" type="button" onClick={() => void saveEdit()} disabled={editBusy}>
                  {editBusy ? "保存中……" : "保存"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
