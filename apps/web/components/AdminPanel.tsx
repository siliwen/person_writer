"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { AdminDashboard } from "./AdminDashboard";
import { AdminUsers } from "./AdminUsers";
import { AdminConfig } from "./AdminConfig";
import { AdminUsage } from "./AdminUsage";
import { AdminAudit } from "./AdminAudit";
import { AdminRecommended } from "./AdminRecommended";
import { AdminMessages } from "./AdminMessages";

type AdminTab = "dashboard" | "users" | "config" | "usage" | "audit" | "recommend" | "messages";

const adminTabs: Array<{ key: AdminTab; label: string }> = [
  { key: "dashboard", label: "概览" },
  { key: "users", label: "用户与账号" },
  { key: "config", label: "会员与配置" },
  { key: "usage", label: "积分消耗" },
  { key: "audit", label: "操作审计" },
  { key: "recommend", label: "推荐风格" },
  { key: "messages", label: "消息中心" },
];

type AdminPanelProps = {
  onNewStyle?: () => void;
};

export function AdminPanel({ onNewStyle }: AdminPanelProps) {
  const { currentUser } = useAuth();
  const [tab, setTab] = useState<AdminTab>("dashboard");

  if (!currentUser?.is_admin) {
    return (
      <div className="admin-guard">
        <div className="empty-state">
          <div className="empty-state-title">无访问权限</div>
          <div className="empty-state-desc">后台管理仅限管理员账号访问。</div>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-shell">
      <div className="admin-subnav">
        {adminTabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`admin-subnav-item ${tab === t.key ? "active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="admin-content">
        {tab === "dashboard" ? <AdminDashboard /> : null}
        {tab === "users" ? <AdminUsers /> : null}
        {tab === "config" ? <AdminConfig /> : null}
        {tab === "usage" ? <AdminUsage /> : null}
        {tab === "audit" ? <AdminAudit /> : null}
        {tab === "recommend" ? <AdminRecommended onNewStyle={onNewStyle ?? (() => {})} /> : null}
        {tab === "messages" ? <AdminMessages /> : null}
      </div>
    </div>
  );
}
