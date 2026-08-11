"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchAdminAuditLogs } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types";

const PAGE_SIZE = 20;

/** 操作类型 → 中文展示（与后端 log_admin_action 的 action 取值一致）。 */
const ACTION_LABELS: Record<string, string> = {
  adjust_points: "调整积分",
  set_tier: "调整等级",
  create: "新建",
  update: "修改",
  delete: "删除",
};

/** 危险/敏感操作，表格中高亮。 */
const DANGER_ACTIONS = new Set(["delete", "adjust_points", "set_tier"]);

/** 目标类型 → 中文展示 + 筛选下拉选项（与后端 target_type 取值一致）。 */
const TARGET_TYPES: { value: string; label: string }[] = [
  { value: "", label: "全部对象" },
  { value: "user", label: "用户" },
  { value: "tier", label: "会员等级" },
  { value: "bracket", label: "长度档位" },
  { value: "opcost", label: "操作积分" },
  { value: "price", label: "模型单价" },
];

const TARGET_LABELS: Record<string, string> = {
  user: "用户",
  tier: "会员等级",
  bracket: "长度档位",
  opcost: "操作积分",
  price: "模型单价",
};

/** 把 before/after 的 JSON 压成一行短文本，超长截断，完整内容放 title。 */
function summarize(payload: Record<string, unknown> | null): { short: string; full: string } {
  if (!payload || Object.keys(payload).length === 0) return { short: "—", full: "" };
  const full = Object.entries(payload)
    .map(([k, v]) => `${k}=${v === null || v === undefined ? "null" : String(v)}`)
    .join(", ");
  return { short: full.length > 48 ? `${full.slice(0, 48)}…` : full, full };
}

export function AdminAudit() {
  const [page, setPage] = useState(1);
  const [targetType, setTargetType] = useState("");
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    fetchAdminAuditLogs({ page, page_size: PAGE_SIZE, target_type: targetType || undefined })
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e) => setError(e.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [page, targetType]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="settings-section-title">操作审计日志</div>
      <p className="form-hint">
        记录所有管理端敏感操作（调整积分、变更等级、配置增删改）。日志只追加，不可修改或删除。
      </p>

      <div className="admin-filter-bar">
        <select
          className="form-input"
          value={targetType}
          onChange={(e) => {
            setTargetType(e.target.value);
            setPage(1);
          }}
        >
          {TARGET_TYPES.map((t) => (
            <option key={t.value || "all"} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        <button className="btn btn-ghost btn-sm" type="button" onClick={load}>
          刷新
        </button>
      </div>

      {error ? (
        <p className="inline-error" role="alert">
          {error}
        </p>
      ) : null}
      {loading ? <p className="inline-status">加载中……</p> : null}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作人</th>
              <th>操作</th>
              <th>对象</th>
              <th>变更前</th>
              <th>变更后</th>
              <th>原因</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading ? (
              <tr>
                <td colSpan={7} className="admin-table-empty">
                  暂无审计记录
                </td>
              </tr>
            ) : (
              items.map((log) => {
                const before = summarize(log.before);
                const after = summarize(log.after);
                return (
                  <tr key={log.id}>
                    <td>{new Date(log.created_at).toLocaleString("zh-CN")}</td>
                    <td>
                      {log.actor_name ?? "—"}
                      <div className="admin-monospace admin-subtle">{log.actor_id}</div>
                    </td>
                    <td className={DANGER_ACTIONS.has(log.action) ? "admin-action-danger" : undefined}>
                      {ACTION_LABELS[log.action] ?? log.action}
                    </td>
                    <td>
                      {TARGET_LABELS[log.target_type] ?? log.target_type}
                      {log.target_id ? (
                        <div className="admin-monospace admin-subtle">{log.target_id}</div>
                      ) : null}
                    </td>
                    <td className="admin-monospace" title={before.full}>
                      {before.short}
                    </td>
                    <td className="admin-monospace" title={after.full}>
                      {after.short}
                    </td>
                    <td>{log.reason ?? "—"}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="admin-pagination">
        <button
          className="btn btn-ghost btn-sm"
          type="button"
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          上一页
        </button>
        <span className="admin-pagination-info">
          第 {page} / {totalPages} 页 · 共 {total} 条
        </span>
        <button
          className="btn btn-ghost btn-sm"
          type="button"
          disabled={page >= totalPages}
          onClick={() => setPage((p) => p + 1)}
        >
          下一页
        </button>
      </div>
    </div>
  );
}
