"use client";

import type { CurrentUser, Material, StyleProfile, WritingDocument, ViewName } from "@/lib/types";

type DashboardViewProps = {
  currentUser: CurrentUser | null;
  materials: Material[];
  styles: StyleProfile[];
  savedDocuments: WritingDocument[];
  generationCount: number;
  onNavigate: (view: ViewName) => void;
  onOpenDocument: (doc: WritingDocument) => void;
};

function formatDate(value: string | null | undefined): string {
  if (!value) return "未知时间";
  return value.slice(0, 10);
}

export function DashboardView({
  currentUser,
  materials,
  styles,
  savedDocuments,
  generationCount,
  onNavigate,
  onOpenDocument,
}: DashboardViewProps) {
  const displayName = currentUser?.display_name || currentUser?.username || "写作者";
  const isLoggedIn = !!currentUser;

  const recentDocs = savedDocuments.slice(0, 4);
  const recentStyles = styles.slice(0, 4);

  if (!isLoggedIn) {
    return (
      <div className="dashboard">
        <header className="dashboard-header">
          <h1 className="dashboard-title">墨写 · 个人风格写作工作台</h1>
          <p className="dashboard-subtitle">登录后即可查看你的写作概览、风格档案与已生成文章。</p>
        </header>
        <div className="empty-state">
          <div className="empty-state-title">还没有登录</div>
          <div className="empty-state-desc">登录后开始使用：上传作品、创建风格、按你的文风生成文章。</div>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1 className="dashboard-title">欢迎回来，{displayName}</h1>
        <p className="dashboard-subtitle">这是你的个人写作工作台概览。</p>
      </header>

      <section className="metric-grid">
        <div className="metric-card">
          <div className="metric-label">参考作品</div>
          <div className="metric-value">
            {materials.length}
            <span className="metric-unit">篇</span>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">风格档案</div>
          <div className="metric-value">
            {styles.length}
            <span className="metric-unit">个</span>
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">已生成文章</div>
          <div className="metric-value">
            {generationCount}
            <span className="metric-unit">篇</span>
          </div>
        </div>
      </section>

      <section className="quick-grid">
        <button className="quick-card" type="button" onClick={() => onNavigate("styles")}>
          <div className="quick-card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 5v14M5 12h14" />
            </svg>
          </div>
          <div className="quick-card-title">上传作品 · 创建风格</div>
          <div className="quick-card-desc">上传多篇风格相近的作品，系统自动分析并生成属于你的风格档案。</div>
        </button>
        <button className="quick-card" type="button" onClick={() => onNavigate("articles")}>
          <div className="quick-card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
          </div>
          <div className="quick-card-title">查看文章库</div>
          <div className="quick-card-desc">浏览你已保存的文章，可以继续修改、下载或重新生成。</div>
        </button>
      </section>

      <div className="dashboard-cols">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">我的风格</h2>
            <button className="dashboard-link" type="button" onClick={() => onNavigate("styles")}>
              查看全部
            </button>
          </div>
          {recentStyles.length === 0 ? (
            <div className="empty-state-compact">还没有风格档案，去「风格库」上传作品创建第一个。</div>
          ) : (
            <div className="chip-list">
              {recentStyles.map((s) => (
                <button
                  key={s.id}
                  className="style-chip"
                  type="button"
                  onClick={() => onNavigate("styles")}
                >
                  <span className="style-chip-name">{s.name}</span>
                  {s.is_default ? <span className="badge badge-accent">默认</span> : null}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="card-title">最近文章</h2>
            <button className="dashboard-link" type="button" onClick={() => onNavigate("articles")}>
              查看全部
            </button>
          </div>
          {recentDocs.length === 0 ? (
            <div className="empty-state-compact">还没有保存的文章，去写作页生成你的第一篇。</div>
          ) : (
            <div className="article-list">
              {recentDocs.map((doc) => (
                <button
                  key={doc.id}
                  className="article-item clickable"
                  type="button"
                  onClick={() => onOpenDocument(doc)}
                >
                  <div>
                    <div className="article-item-title">{doc.title}</div>
                    <div className="article-item-meta">
                      {doc.genre} · {formatDate(doc.updated_at)}
                    </div>
                  </div>
                  <span className="badge badge-neutral">{doc.paragraphs.length} 段</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
