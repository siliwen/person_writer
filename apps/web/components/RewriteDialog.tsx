"use client";

import { useState } from "react";
import type { DocumentParagraph } from "@/lib/types";

type RewriteDialogProps = {
  paragraph: DocumentParagraph;
  busy: boolean;
  /** 本次 AI 重写将消耗的积分；为 null 时不展示（如配额未加载）。 */
  paragraphRewritePoints?: number | null;
  onClose: () => void;
  onRewrite: (instruction: string) => Promise<string>;
  onOverwrite: (newContent: string) => Promise<void>;
};

export function RewriteDialog({ paragraph, busy, paragraphRewritePoints = null, onClose, onRewrite, onOverwrite }: RewriteDialogProps) {
  const originalContent = paragraph.content;
  const [editText, setEditText] = useState(originalContent);
  const [instruction, setInstruction] = useState("");
  const [error, setError] = useState("");
  const [isAiResult, setIsAiResult] = useState(false);
  const [isOverwriting, setIsOverwriting] = useState(false);

  const hasModified = editText.trim() !== originalContent.trim();
  const canOverwrite = hasModified && !busy && !isOverwriting;
  const canRewrite = !!instruction.trim() && !busy && !isOverwriting;

  async function handleRewrite() {
    const trimmed = instruction.trim();
    if (!trimmed) return;
    setError("");
    try {
      const result = await onRewrite(trimmed);
      setEditText(result);
      setIsAiResult(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  function handleRestore() {
    setEditText(originalContent);
    setIsAiResult(false);
    setError("");
  }

  async function handleOverwrite() {
    if (!hasModified) return;
    setError("");
    setIsOverwriting(true);
    try {
      await onOverwrite(editText.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsOverwriting(false);
    }
  }

  const showRestore = hasModified || isAiResult;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card rewrite-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">修改第 {paragraph.position} 段</h3>
          <button
            className="modal-close"
            type="button"
            disabled={busy || isOverwriting}
            onClick={onClose}
            aria-label="关闭"
          >
            ×
          </button>
        </div>

        <div className="rewrite-edit-section">
          <div className="rewrite-edit-header">
            <label className="form-label">原文（可编辑）</label>
            {showRestore ? (
              <button className="rewrite-restore-btn" type="button" onClick={handleRestore} disabled={busy}>
                恢复原文
              </button>
            ) : null}
          </div>
          <textarea
            className={`rewrite-edit-area ${isAiResult ? "ai-result" : ""}`}
            value={editText}
            onChange={(e) => {
              setEditText(e.target.value);
              setIsAiResult(false);
            }}
            disabled={busy}
            rows={6}
          />
          {isAiResult ? (
            <span className="rewrite-ai-badge">AI 重写结果</span>
          ) : null}
        </div>

        <div className="form-field">
          <label className="form-label">修改意见（AI重写）</label>
          <textarea
            className="form-textarea"
            placeholder="例如：更克制一点，减少解释，保留画面感。"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            disabled={busy}
            rows={2}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleRewrite();
              }
            }}
          />
        </div>
        <p className="form-hint">按 Cmd/Ctrl + Enter 快速重写 · 可多次重写直到满意</p>

        {error ? <p className="inline-error" role="alert">{error}</p> : null}
        {busy ? <p className="inline-status">正在重写，请稍候……</p> : null}

        <div className="modal-actions">
          <button className="btn btn-secondary" type="button" disabled={busy || isOverwriting} onClick={onClose}>
            取消
          </button>
          <button
            className="btn btn-secondary"
            type="button"
            disabled={!canRewrite}
            onClick={handleRewrite}
          >
            {busy ? "正在重写……" : (
              <>AI重写{paragraphRewritePoints != null ? <span className="btn-cost"> · 消耗{paragraphRewritePoints}积分</span> : null}</>
            )}
          </button>
          <button
            className="btn btn-primary"
            type="button"
            disabled={!canOverwrite}
            onClick={handleOverwrite}
          >
            {isOverwriting ? "正在保存……" : "确认覆盖原文"}
          </button>
        </div>
      </div>
    </div>
  );
}
