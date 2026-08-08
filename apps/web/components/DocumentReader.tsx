"use client";

import { useMemo, useState } from "react";
import type { BusyAction, DocumentParagraph, WritingDocument } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";
import { RewriteDialog } from "./RewriteDialog";

type DocumentReaderProps = {
  document: WritingDocument;
  generationCount: number;
  busyAction: BusyAction;
  onRewrite: (paragraphId: string, instruction: string) => Promise<string>;
  onOverwriteParagraph: (paragraphId: string, newContent: string) => Promise<void>;
  onSaveDocument?: () => Promise<void>;
  onDownloadDocument: () => Promise<void>;
  showSaveButton?: boolean;
  showBackButton?: boolean;
  onBack?: () => void;
};

export function DocumentReader({
  document: doc,
  generationCount,
  busyAction,
  onRewrite,
  onOverwriteParagraph,
  onSaveDocument,
  onDownloadDocument,
  showSaveButton = true,
  showBackButton = false,
  onBack,
}: DocumentReaderProps) {
  const { requireAuth } = useAuth();
  const [rewriteParagraph, setRewriteParagraph] = useState<DocumentParagraph | null>(null);
  const [rewriteError, setRewriteError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [actionMessage, setActionMessage] = useState("");

  const isRewriting = busyAction === "rewrite";

  const documentUpdatedAt = useMemo(() => {
    if (!doc?.updated_at) return "";
    return new Date(doc.updated_at).toLocaleString("zh-CN", { hour12: false });
  }, [doc?.updated_at]);

  async function handleRewrite(instruction: string): Promise<string> {
    if (!rewriteParagraph) throw new Error("未选择段落");
    setRewriteError("");
    try {
      const result = await onRewrite(rewriteParagraph.id, instruction);
      return result;
    } catch (err) {
      setRewriteError(err instanceof Error ? err.message : String(err));
      throw err;
    }
  }

  async function handleOverwrite(newContent: string): Promise<void> {
    if (!rewriteParagraph) return;
    setRewriteError("");
    try {
      await onOverwriteParagraph(rewriteParagraph.id, newContent);
      setRewriteParagraph(null);
    } catch (err) {
      setRewriteError(err instanceof Error ? err.message : String(err));
      throw err;
    }
  }

  async function handleSave() {
    if (!requireAuth()) return;
    if (!onSaveDocument) return;
    setIsSaving(true);
    setActionMessage("");
    try {
      await onSaveDocument();
      setActionMessage("文章已保存到个人文章库");
    } catch (err) {
      setActionMessage(err instanceof Error ? `保存失败：${err.message}` : "保存失败");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDownload() {
    if (!requireAuth()) return;
    setIsDownloading(true);
    setActionMessage("");
    try {
      await onDownloadDocument();
      setActionMessage("文章已开始下载");
    } catch (err) {
      setActionMessage(err instanceof Error ? `下载失败：${err.message}` : "下载失败");
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <div className="document-reader">
      {showBackButton ? (
        <div className="reader-back-bar">
          <button className="btn btn-ghost btn-sm" type="button" onClick={onBack}>
            ← 返回文章库
          </button>
        </div>
      ) : null}

      <div className="document-display">
        <div className="document-header">
          <div>
            <div className="document-header-title">{doc.title}</div>
            <div className="document-header-meta">
              {doc.genre} · 第 {generationCount} 版 · {doc.paragraphs.length} 段 · 约 {doc.content.length} 字 · {documentUpdatedAt}
              {doc.is_saved ? <span className="document-saved-badge">已保存</span> : null}
            </div>
          </div>
          <div className="document-actions">
            {showSaveButton ? (
              <button
                className="btn btn-ghost btn-sm"
                type="button"
                onClick={handleSave}
                disabled={isSaving || isDownloading || doc.is_saved}
                title={doc.is_saved ? "文章已在个人库中" : "保存到个人文章库"}
              >
                {isSaving ? "保存中…" : doc.is_saved ? "已保存" : "保存文章"}
              </button>
            ) : null}
            <button
              className="btn btn-primary btn-sm"
              type="button"
              onClick={handleDownload}
              disabled={isSaving || isDownloading}
            >
              {isDownloading ? "下载中…" : "下载文章"}
            </button>
          </div>
        </div>
        {actionMessage ? <p className="document-action-message">{actionMessage}</p> : null}
        {doc.paragraphs.map((paragraph) => (
          <div
            key={paragraph.id}
            className={`paragraph-block ${rewriteParagraph?.id === paragraph.id ? "active" : ""}`}
            onClick={() => setRewriteParagraph(paragraph)}
          >
            <button
              className="paragraph-edit-btn"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setRewriteParagraph(paragraph);
              }}
            >
              修改这一段
            </button>
            <p>{paragraph.content}</p>
            <span className="paragraph-meta">第 {paragraph.position} 段 · 重写 {paragraph.rewrite_count} 次</span>
          </div>
        ))}
      </div>

      {rewriteError ? <p className="inline-error" role="alert">{rewriteError}</p> : null}

      {rewriteParagraph ? (
        <RewriteDialog
          paragraph={rewriteParagraph}
          busy={isRewriting}
          onClose={() => {
            if (!isRewriting) {
              setRewriteParagraph(null);
              setRewriteError("");
            }
          }}
          onRewrite={handleRewrite}
          onOverwrite={handleOverwrite}
        />
      ) : null}
    </div>
  );
}
