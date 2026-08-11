"use client";

import { useEffect, useState } from "react";
import { fetchAdminMetrics } from "@/lib/api";
import type { AdminMetrics } from "@/lib/types";

function yuan(fen: number): string {
  return `¥${(fen / 100).toFixed(2)}`;
}

export function AdminDashboard() {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetchAdminMetrics()
      .then((m) => {
        if (alive) setMetrics(m);
      })
      .catch((e) => {
        if (alive) setError(e.message ?? "加载失败");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (loading) return <p className="inline-status">加载中……</p>;
  if (error) return <p className="inline-error" role="alert">{error}</p>;
  if (!metrics) return null;

  const cards: Array<{ label: string; value: string; hint?: string }> = [
    { label: "总用户数", value: String(metrics.total_users) },
    { label: "今日新增", value: String(metrics.new_users_today), hint: "按注册时间" },
    { label: "今日活跃", value: String(metrics.active_today), hint: "有积分消耗记录" },
    { label: "累计文章", value: String(metrics.total_documents) },
    { label: "本月积分消耗", value: String(metrics.points_consumed_month), hint: "正数消耗" },
    { label: "本月成本", value: yuan(Math.round(metrics.cost_month_cny * 100)), hint: "内部真实成本" },
    { label: "预估月收入", value: yuan(metrics.mrr_estimate_cny), hint: "非免费版月费之和" },
  ];

  return (
    <div>
      <div className="settings-section-title">运营概览</div>
      <div className="stat-grid">
        {cards.map((c) => (
          <div className="stat-card" key={c.label}>
            <div className="stat-card-value">{c.value}</div>
            <div className="stat-card-label">{c.label}</div>
            {c.hint ? <div className="stat-card-hint">{c.hint}</div> : null}
          </div>
        ))}
      </div>

      <div className="settings-section-title">等级分布</div>
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>等级</th>
              <th>用户数</th>
            </tr>
          </thead>
          <tbody>
            {metrics.tier_distribution.length === 0 ? (
              <tr>
                <td colSpan={2} className="admin-table-empty">暂无数据</td>
              </tr>
            ) : (
              metrics.tier_distribution.map((t) => (
                <tr key={t.code}>
                  <td>{t.name}</td>
                  <td>{t.count}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
