"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchAdminUsage } from "@/lib/api";
import type { AdminUsageRecord } from "@/lib/types";

const PAGE_SIZE = 20;

const OP_LABELS: Record<string, string> = {
  style_analysis: "风格分析",
  paragraph_rewrite: "段落重写",
  admin_adjust: "管理员调整",
  article_generate: "文章生成",
};

export function AdminUsage() {
  const [page, setPage] = useState(1);
  const [userId, setUserId] = useState("");
  const [items, setItems] = useState<AdminUsageRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    fetchAdminUsage({ page, page_size: PAGE_SIZE, user_id: userId || undefined })
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch((e) => setError(e.message ?? "加载失败"))
      .finally(() => setLoading(false));
  }, [page, userId]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div className="settings-section-title">积分消耗流水（全站）</div>

      <div className="admin-filter-bar">
        <input
          className="form-input"
          placeholder="按用户 ID 过滤（可选）"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
        />
        <button className="btn btn-primary btn-sm" type="button" onClick={() => { setPage(1); load(); }}>
          查询
        </button>
      </div>

      {error ? <p className="inline-error" role="alert">{error}</p> : null}
      {loading ? <p className="inline-status">加载中……</p> : null}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作</th>
              <th>积分</th>
              <th>模型 / 备注</th>
              <th>输入/输出 tokens</th>
              <th>成本(¥)</th>
              <th>用户</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && !loading ? (
              <tr><td colSpan={7} className="admin-table-empty">暂无记录</td></tr>
            ) : (
              items.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.created_at).toLocaleString("zh-CN")}</td>
                  <td>{OP_LABELS[r.op_type] ?? r.op_type}</td>
                  <td className={r.points_consumed >= 0 ? "usage-cost" : "usage-gain"}>
                    {r.points_consumed >= 0 ? `-${r.points_consumed}` : `+${Math.abs(r.points_consumed)}`}
                  </td>
                  <td>{r.model_name ?? "—"}</td>
                  <td>{r.input_tokens}/{r.output_tokens}</td>
                  <td>{r.cost_cny ? (r.cost_cny as number).toFixed(4) : "0"}</td>
                  <td className="admin-monospace">{r.user_id}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="admin-pagination">
        <button className="btn btn-ghost btn-sm" type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
          上一页
        </button>
        <span className="admin-pagination-info">第 {page} / {totalPages} 页 · 共 {total} 条</span>
        <button className="btn btn-ghost btn-sm" type="button" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
          下一页
        </button>
      </div>
    </div>
  );
}
