"use client";

import { useEffect, useState } from "react";
import type { ViewName } from "@/lib/types";

type SidebarProps = {
  currentView: ViewName;
  onNavigate: (view: ViewName) => void;
  isAdmin?: boolean;
};

const STORAGE_KEY = "sidebar-expanded";

const navItems: Array<{ view: ViewName; label: string; icon: React.ReactNode; adminOnly?: boolean }> = [
  {
    view: "dashboard",
    label: "首页",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 12l9-9 9 9" />
        <path d="M5 10v10h14V10" />
      </svg>
    ),
  },
  {
    view: "styles",
    label: "风格库",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 4h16v3H4z" />
        <path d="M6 7v13h12V7" />
        <path d="M10 11h4" />
      </svg>
    ),
  },
  {
    view: "articles",
    label: "文章库",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    ),
  },
  {
    view: "settings",
    label: "设置",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3.5" />
        <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
      </svg>
    ),
  },
  {
    view: "admin",
    label: "后台管理",
    adminOnly: true,
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3l8 4v5c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V7z" />
        <path d="M12 8v4M10 10h4" />
      </svg>
    ),
  },
];

function readInitialExpanded(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function Sidebar({ currentView, onNavigate, isAdmin }: SidebarProps) {
  const [expanded, setExpanded] = useState<boolean>(false);
  const [hydrated, setHydrated] = useState<boolean>(false);

  useEffect(() => {
    setHydrated(true);
    setExpanded(readInitialExpanded());
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, expanded ? "true" : "false");
    } catch {
      /* ignore */
    }
  }, [expanded, hydrated]);

  const visibleItems = isAdmin ? navItems : navItems.filter((i) => !i.adminOnly);

  return (
    <nav className={`sidebar${hydrated && expanded ? " expanded" : ""}`}>
      <div className="sidebar-logo">
        <span className="sidebar-logo-mark">墨</span>
        <span className="sidebar-logo-text">墨小小</span>
      </div>

      <div className="sidebar-nav">
        {visibleItems.map((item) => (
          <button
            key={item.view}
            type="button"
            className={`sidebar-nav-item ${currentView === item.view ? "active" : ""}`}
            onClick={() => onNavigate(item.view)}
            title={item.label}
            aria-label={item.label}
          >
            {item.icon}
            <span className="sidebar-nav-item-content">
              <span className="sidebar-nav-item-label">{item.label}</span>
            </span>
          </button>
        ))}
      </div>

      <button
        type="button"
        className="sidebar-toggle"
        onClick={() => setExpanded((v) => !v)}
        title={expanded ? "收起侧边栏" : "展开侧边栏"}
        aria-label={expanded ? "收起侧边栏" : "展开侧边栏"}
        aria-pressed={expanded}
      >
        {expanded ? (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M13 6l-6 6 6 6" />
            <path d="M19 6l-6 6 6 6" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 6l6 6-6 6" />
            <path d="M5 6l6 6-6 6" />
          </svg>
        )}
      </button>
    </nav>
  );
}
