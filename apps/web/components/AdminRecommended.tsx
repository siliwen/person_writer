"use client";

import { useCallback, useEffect, useState } from "react";
import type { AdminStyle } from "@/lib/types";
import { fetchAdminStyles, setAdminStyleRecommended } from "@/lib/api";

type AdminRecommendedProps = {
  onNewStyle: () => void;
};

export function AdminRecommended({ onNewStyle }: AdminRecommendedProps) {
  const [items, setItems] = useState<AdminStyle[]>([]);
  const [onlyRecommended, setOnlyRecommended] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

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
          ))}
        </div>
      )}
    </div>
  );
}
