"use client";

import { useEffect, useMemo, useState } from "react";
import type { BusyAction, QuotaView, WritingDocument } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";
import { estimateArticlePoints } from "@/lib/quota";
import { DocumentReader } from "./DocumentReader";

/** 无字数选择时，按默认 1200 字预估积分。 */
const DEFAULT_ESTIMATE_CHARS = 1200;

type FreeWritingDetailViewProps = {
  document: WritingDocument | null;
  generationCount: number;
  busyAction: BusyAction;
  quota: QuotaView | null;
  onRevise: (instruction: string) => Promise<void>;
  onSaveDocument: () => Promise<void>;
  onDownloadDocument: () => Promise<void>;
  onBack: () => void;
};

const PLACEHOLDERS = [
  "例如：把第二段写得更克制一些，少一点抒情",
  "例如：结尾加一段对旧物的感慨，收束全文",
  "例如：整体缩短到 800 字左右，去掉重复的表达",
];

export function FreeWritingDetailView({
  document: doc,
  generationCount,
  busyAction,
  quota,
  onRevise,
  onSaveDocument,
  onDownloadDocument,
  onBack,
}: FreeWritingDetailViewProps) {
  const { requireAuth } = useAuth();
  const [instruction, setInstruction] = useState("");
  const [placeholderIndex, setPlaceholderIndex] = useState(0);
  const [revisionError, setRevisionError] = useState("");

  const busy = busyAction === "writing";

  const estimate = useMemo(() => {
    if (!quota) return { points: 0, blocked: false, insufficient: false };
    const points = estimateArticlePoints(DEFAULT_ESTIMATE_CHARS, quota.article_length_brackets);
    const insufficient = quota.points_balance < points;
    return { points, blocked: insufficient, insufficient };
  }, [quota]);

  // 占位符轮播（仅在未输入内容时展示）
  useEffect(() => {
    if (instruction.trim()) return;
    const timer = window.setInterval(() => {
      setPlaceholderIndex((i) => (i + 1) % PLACEHOLDERS.length);
    }, 3500);
    return () => window.clearInterval(timer);
  }, [instruction]);

  async function handleRevise() {
    setRevisionError("");
    if (!requireAuth()) return;
    const text = instruction.trim();
    if (!text) {
      setRevisionError("请先填写你希望怎么改，再点「生成文章」。");
      return;
    }
    if (!doc) {
      setRevisionError("当前没有可修改的文章。");
      return;
    }
    try {
      await onRevise(text);
      setInstruction("");
    } catch (err) {
      setRevisionError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="free-writing-layout">
      <div className="reader-back-bar">
        <button className="btn btn-ghost btn-sm" type="button" onClick={onBack}>
          ← 返回
        </button>
      </div>

      <div className="free-revise-scroll">
        {busy && !doc ? (
          <div className="empty-state">
            <div className="empty-state-title">正在生成文章……</div>
            <div className="empty-state-desc">请稍候，文章即将生成。</div>
          </div>
        ) : doc ? (
          <DocumentReader
            document={doc}
            generationCount={generationCount}
            busyAction={busyAction}
            canDownload={quota ? quota.tier.can_download : true}
            canRewrite={false}
            readOnly
            onRewrite={async () => ""}
            onOverwriteParagraph={async () => {}}
            onSaveDocument={onSaveDocument}
            onDownloadDocument={onDownloadDocument}
            showSaveButton
          />
        ) : (
          <div className="empty-state">
            <div className="empty-state-title">还没有生成文章</div>
            <div className="empty-state-desc">回到首页输入想法，即可开始自由写作。</div>
          </div>
        )}
      </div>

      <div className="free-revise-bar">
        <textarea
          className="free-revise-input"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder={PLACEHOLDERS[placeholderIndex]}
          rows={2}
          disabled={busy || !doc}
        />
        <div className="free-revise-actions">
          <button
            className="btn btn-primary free-revise-submit"
            type="button"
            onClick={handleRevise}
            disabled={busy || !doc || estimate.blocked}
          >
            {busy ? "正在生成新文章……" : (
              <>
                生成文章
                {quota ? <span className="btn-cost"> · 预计{estimate.points}积分</span> : null}
              </>
            )}
          </button>
        </div>
      </div>

      {revisionError ? (
        <p className="inline-error" role="alert">
          {revisionError}
        </p>
      ) : null}
    </div>
  );
}
