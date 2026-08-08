"use client";

import type { WritingDocument, ViewName } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

type ArticlesViewProps = {
  documents: WritingDocument[];
  busyDocumentId: string | null;
  onOpenDocument: (document: WritingDocument) => void;
  onDownloadDocument: (document: WritingDocument) => void;
  onUnsaveDocument: (documentId: string) => Promise<void>;
  onNavigate: (view: ViewName) => void;
};

export function ArticlesView({
  documents,
  busyDocumentId,
  onOpenDocument,
  onDownloadDocument,
  onUnsaveDocument,
  onNavigate,
}: ArticlesViewProps) {
  const { currentUser } = useAuth();

  if (!currentUser) {
    return (
      <div className="empty-state">
        <div className="empty-state-title">请先登录</div>
        <div className="empty-state-desc">登录后可以查看和管理你保存的文章。</div>
      </div>
    );
  }

  return (
    <div>
      <div className="breadcrumb">
        <span className="breadcrumb-item">文章库</span>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-item current">已保存文章</span>
      </div>

      {documents.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-title">还没有保存的文章</div>
          <div className="empty-state-desc">
            在写作页生成文章后，点击「保存文章」即可在这里找到它们。你可以随时打开、下载或继续修改。
          </div>
          <button className="btn btn-primary" type="button" onClick={() => onNavigate("styles")}>
            去写作
          </button>
        </div>
      ) : (
        <div className="articles-grid">
          {documents.map((doc) => (
            <div key={doc.id} className="article-card">
              <div className="article-card-header">
                <div className="article-card-title" title={doc.title}>
                  {doc.title}
                </div>
                <span className="article-card-genre">{doc.genre}</span>
              </div>
              <div className="article-card-meta">
                {doc.paragraphs.length} 段 · 约 {doc.content.length} 字 · 保存于{" "}
                {doc.saved_at ? new Date(doc.saved_at).toLocaleString("zh-CN", { hour12: false }) : "—"}
              </div>
              <p className="article-card-preview">
                {doc.content.slice(0, 120).replace(/\n/g, " ")}
                {doc.content.length > 120 ? "……" : ""}
              </p>
              <div className="article-card-actions">
                <button
                  className="btn btn-ghost btn-sm"
                  type="button"
                  onClick={() => onOpenDocument(doc)}
                >
                  打开
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  type="button"
                  onClick={() => onDownloadDocument(doc)}
                  disabled={busyDocumentId === doc.id}
                >
                  下载
                </button>
                <button
                  className="btn btn-ghost btn-sm btn-danger"
                  type="button"
                  onClick={() => void onUnsaveDocument(doc.id)}
                  disabled={busyDocumentId === doc.id}
                >
                  移除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
