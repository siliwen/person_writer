"use client";

import { useMemo, useRef, useState } from "react";
import type { ArticleEvaluation, BusyAction, QuotaView, StyleProfile, WritingDocument } from "@/lib/types";
import { EVALUATION_GENRES, GENRES } from "@/lib/types";
import { estimateArticlePoints, parseTargetLengthChars } from "@/lib/quota";
import { useAuth } from "@/lib/auth-context";
import { fetchOptimizePrompt } from "@/lib/api";
import { DocumentReader } from "./DocumentReader";
import { EvaluationPanel } from "./EvaluationPanel";

type WritingViewProps = {
  styles: StyleProfile[];
  selectedStyleId: string;
  quota: QuotaView | null;
  freeWriteMode?: boolean;
  onSelectStyle: (id: string) => void;
  document: WritingDocument | null;
  generationCount: number;
  busyAction: BusyAction;
  writingError: string;
  onGenerate: (params: WritingParams) => void;
  onRewrite: (paragraphId: string, instruction: string) => Promise<string>;
  onOverwriteParagraph: (paragraphId: string, newContent: string) => Promise<void>;
  onSaveDocument: () => Promise<void>;
  onDownloadDocument: () => Promise<void>;
  evaluation: ArticleEvaluation | null;
  evaluationLoading: boolean;
  evaluationError: string;
  onEvaluate: () => void;
};

export type WritingParams = {
  styleProfileId: string;
  genre: string;
  title: string;
  brief: string;
  targetLength: string;
  styleIntensity: string;
  mustInclude: string;
  mustAvoid: string;
};

const styleIntensityOptions = [
  { value: "light", label: "轻度参考：只参考语气和节奏，表达更原创" },
  { value: "balanced", label: "平衡仿写：保留文风特征，避免像改写稿" },
  { value: "close", label: "高度贴近：更接近句法节奏，仅用于内部测试" },
];

export function WritingView({
  styles,
  selectedStyleId,
  quota,
  freeWriteMode = false,
  onSelectStyle,
  document: doc,
  generationCount,
  busyAction,
  writingError,
  onGenerate,
  onRewrite,
  onOverwriteParagraph,
  onSaveDocument,
  onDownloadDocument,
  evaluation,
  evaluationLoading,
  evaluationError,
  onEvaluate,
}: WritingViewProps) {
  const { requireAuth } = useAuth();
  const [writingGenre, setWritingGenre] = useState("散文");
  const [title, setTitle] = useState("附近生活");
  const [brief, setBrief] = useState("写一篇关于街角小店和旧物的文章。");
  const [targetLength, setTargetLength] = useState("1200字");
  const [styleIntensity, setStyleIntensity] = useState("balanced");
  const [mustInclude, setMustInclude] = useState("具体场景、自然段、克制表达");
  const [mustAvoid, setMustAvoid] = useState("AI 套话、空泛抒情、宏大口号");

  // 提示词优化（与首页无风格写作一致）
  const [optimizing, setOptimizing] = useState(false);
  const [optimized, setOptimized] = useState(false);
  const [optimizeError, setOptimizeError] = useState("");
  const optimizeCost = 1;

  const writingRef = useRef<HTMLDivElement | null>(null);
  const busy = busyAction !== null;
  const isWriting = busyAction === "writing";

  const canOptimize = !optimizing && !busy && !!quota && quota.points_balance >= optimizeCost;

  async function handleOptimize() {
    setOptimizeError("");
    if (!requireAuth()) return;
    const source = brief.trim();
    if (!source) {
      setOptimizeError("请先输入写作要求，再点优化提示词。");
      return;
    }
    if (quota && quota.points_balance < optimizeCost) {
      setOptimizeError("积分不足，无法优化提示词。");
      return;
    }
    setOptimizing(true);
    try {
      const res = await fetchOptimizePrompt(source);
      setBrief(res.optimized_prompt);
      setOptimized(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setOptimizeError(`优化失败：${message}`);
    } finally {
      setOptimizing(false);
    }
  }

  const selectedStyle = useMemo(
    () => styles.find((s) => s.id === selectedStyleId),
    [styles, selectedStyleId]
  );

  // 根据当前 targetLength 与等级档位预估本次生成消耗积分
  const estimate = useMemo(() => {
    if (!quota) return null;
    const chars = parseTargetLengthChars(targetLength);
    const tier = quota.tier;
    const points = estimateArticlePoints(chars, quota.article_length_brackets);
    const overLength =
      tier.max_article_length > 0 && chars > tier.max_article_length;
    const insufficient = quota.points_balance < points;
    return { chars, points, overLength, insufficient, blocked: overLength || insufficient };
  }, [quota, targetLength]);

  const canDownload = quota ? quota.tier.can_download : true;
  const canRewrite = quota ? quota.tier.can_rewrite : true;

  function handleGenerate() {
    if (!requireAuth()) return;
    if (!freeWriteMode && !selectedStyleId) return;
    if (estimate?.blocked) return; // 由下方按钮 disabled 与提示兜底，这里再保险一次
    onGenerate({
      styleProfileId: freeWriteMode ? "" : selectedStyleId,
      genre: writingGenre,
      title: title.trim(),
      brief: brief.trim(),
      targetLength: targetLength.trim(),
      styleIntensity,
      mustInclude,
      mustAvoid,
    });
  }

  function handleGenreChange(genre: string) {
    setWritingGenre(genre);
    setTargetLength((current) => {
      if (current === "1200字" || current === "12行") {
        return genre === "诗歌" ? "12行" : "1200字";
      }
      return current;
    });
  }

  return (
    <div ref={writingRef} className="writing-layout">
      {/* Left panel: writing params */}
      <div className="writing-left-panel">
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">写作参数</h2>
            {selectedStyle ? (
              <span className="badge badge-accent">风格：{selectedStyle.name}</span>
            ) : freeWriteMode ? (
              <span className="badge badge-neutral">自由写作（无风格）</span>
            ) : (
              <span className="badge badge-neutral">未选择风格</span>
            )}
          </div>

          {styles.length === 0 && !freeWriteMode ? (
            <div className="empty-state" style={{ marginBottom: "16px" }}>
              <div className="empty-state-title">请先创建或选择一个风格</div>
              <div className="empty-state-desc">在风格库页面上传作品并保存风格后，即可开始写作</div>
            </div>
          ) : (
            <div className="form-field">
              <label className="form-label">选择风格</label>
              <select
                className="form-select"
                value={selectedStyleId}
                onChange={(e) => onSelectStyle(e.target.value)}
              >
                <option value="">{freeWriteMode ? "自由写作" : "请选择已确认风格"}</option>
                {styles.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          )}

          <div className="writing-params">
            <div className="form-field">
              <label className="form-label">写作文体</label>
              <select className="form-select" value={writingGenre} onChange={(e) => handleGenreChange(e.target.value)}>
                {GENRES.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div className="form-field">
              <label className="form-label">目标字数 / 篇幅</label>
              <input
                className="form-input"
                value={targetLength}
                onChange={(e) => setTargetLength(e.target.value)}
                placeholder="例如：800字、1200字、12行"
              />
            </div>
            {freeWriteMode ? null : (
              <div className="form-field full">
                <label className="form-label">风格贴近程度</label>
                <select className="form-select" value={styleIntensity} onChange={(e) => setStyleIntensity(e.target.value)}>
                  {styleIntensityOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                </select>
                <span className="form-hint">默认建议使用"平衡仿写"。如果觉得太像原文，可以改成"轻度参考"。</span>
              </div>
            )}
            <div className="form-field full">
              <label className="form-label">标题 / 主题</label>
              <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="form-field full">
              <label className="form-label">写作要求</label>
              <div className="prompt-optimize-wrap">
                <textarea
                  className={`form-textarea ${optimized ? "optimize-flash" : ""}`}
                  value={brief}
                  onChange={(e) => {
                    setBrief(e.target.value);
                    setOptimized(false);
                  }}
                />
                <button
                  type="button"
                  className="prompt-optimize-float"
                  onClick={handleOptimize}
                  disabled={!canOptimize}
                  title={quota ? `消耗 ${optimizeCost} 积分` : "请先登录"}
                >
                  {optimizing ? "优化中…" : optimized ? "重新优化" : "优化提示词"}
                  <span className="prompt-optimize-cost"> · {optimizeCost}积分</span>
                </button>
              </div>
              {optimizeError ? <p className="inline-error">{optimizeError}</p> : null}
            </div>
            <div className="form-field full">
              <label className="form-label">必须包含</label>
              <input className="form-input" value={mustInclude} onChange={(e) => setMustInclude(e.target.value)} />
            </div>
            <div className="form-field full">
              <label className="form-label">必须避免</label>
              <input className="form-input" value={mustAvoid} onChange={(e) => setMustAvoid(e.target.value)} />
            </div>
          </div>

          <button
            className="btn btn-primary"
            type="button"
            disabled={busy || (!freeWriteMode && !selectedStyleId) || !!estimate?.blocked}
            onClick={handleGenerate}
          >
            {isWriting ? "正在生成文章……" : (
              <>{freeWriteMode ? "自由写作生成文章" : "按选定风格生成文章"}{estimate ? <span className="btn-cost"> · 消耗{estimate.points}积分</span> : null}</>
            )}
          </button>

          {estimate?.blocked ? (
            <p className="inline-error" role="alert">
              {estimate.overLength
                ? `当前等级单篇文章最大长度为 ${quota?.tier.max_article_length} 字，请缩短或升级会员。`
                : `积分不足，本次生成预计需要 ${estimate.points} 积分，当前剩余 ${quota?.points_balance} 积分。可在「设置 → 用量与额度」查看或升级会员。`}
            </p>
          ) : null}
          {writingError ? <p className="inline-error" role="alert">{writingError}</p> : null}
        </div>
      </div>

      {/* Right panel: document reader */}
      <div className="writing-right-panel">
        {doc ? (
          <>
            <DocumentReader
              document={doc}
              generationCount={generationCount}
              busyAction={busyAction}
              canDownload={canDownload}
              canRewrite={canRewrite}
              onRewrite={onRewrite}
              onOverwriteParagraph={onOverwriteParagraph}
              onSaveDocument={onSaveDocument}
              onDownloadDocument={onDownloadDocument}
              showSaveButton
              paragraphRewritePoints={quota ? quota.operation_points.paragraph_rewrite : null}
            />
            <EvaluationPanel
              evaluation={evaluation}
              loading={evaluationLoading}
              error={evaluationError}
              supported={EVALUATION_GENRES.includes(doc.genre) && !freeWriteMode}
              genre={doc.genre}
              onEvaluate={onEvaluate}
            />
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-state-title">还没有生成文章</div>
            <div className="empty-state-desc">
              填写主题、字数和写作要求后，点击"按选定风格生成文章"。生成完成后，点击正文里的自然段可以提交修改意见。
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
