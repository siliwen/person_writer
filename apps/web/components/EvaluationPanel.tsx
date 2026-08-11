"use client";

import { useMemo, useState } from "react";
import type { ArticleEvaluation, EvaluationSuggestion } from "@/lib/types";

type EvaluationPanelProps = {
  evaluation: ArticleEvaluation | null;
  loading: boolean;
  error: string;
  /** 当前文体是否支持鉴评（首版仅散文）。 */
  supported: boolean;
  genre: string;
  onEvaluate: () => void;
  /** 「按建议重写」：把某条建议作为改写指令喂回段落重写流程；不传则不展示该按钮。 */
  onApplySuggestion?: (instruction: string) => void;
  canRewrite?: boolean;
};

const gradeTone: Record<string, string> = {
  S: "eval-grade-s",
  A: "eval-grade-a",
  B: "eval-grade-b",
  C: "eval-grade-c",
  D: "eval-grade-d",
};

function scoreTone(score: number): string {
  if (score >= 8.5) return "eval-bar-good";
  if (score >= 7) return "eval-bar-ok";
  if (score >= 6) return "eval-bar-warn";
  return "eval-bar-bad";
}

function suggestionToInstruction(item: EvaluationSuggestion): string {
  const parts: string[] = [];
  if (item.issue) parts.push(`问题：${item.issue}`);
  if (item.fix) parts.push(`修改要求：${item.fix}`);
  if (item.why) parts.push(`原因：${item.why}`);
  return parts.join("；") || "按鉴评建议改写本段。";
}

export function EvaluationPanel({
  evaluation,
  loading,
  error,
  supported,
  genre,
  onEvaluate,
  onApplySuggestion,
  canRewrite = false,
}: EvaluationPanelProps) {
  const [expanded, setExpanded] = useState(true);

  const report = evaluation?.report ?? null;
  const features = useMemo(
    () => (report?.features ?? {}) as Record<string, number | string | string[]>,
    [report]
  );

  if (!supported) {
    return (
      <div className="eval-panel">
        <div className="eval-header">
          <h3 className="eval-title">文章鉴评</h3>
          <span className="badge badge-neutral">暂不支持{genre}</span>
        </div>
        <p className="eval-empty">
          首版鉴评只覆盖散文——散文的量规（形散神聚、细节可感、结尾留白）已经打磨到可用。
          {genre}的评分标准还在做，硬套散文量规只会给出误导性的分数。
        </p>
      </div>
    );
  }

  return (
    <div className="eval-panel">
      <div className="eval-header">
        <h3 className="eval-title">文章鉴评</h3>
        <div className="eval-header-actions">
          {evaluation ? (
            <button
              type="button"
              className="eval-toggle"
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "收起" : "展开"}
            </button>
          ) : null}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onEvaluate}
            disabled={loading}
          >
            {loading ? "鉴评中……" : evaluation ? "重新鉴评" : "开始鉴评"}
          </button>
        </div>
      </div>

      {error ? <p className="inline-error" role="alert">{error}</p> : null}

      {!evaluation && !loading && !error ? (
        <p className="eval-empty">
          还没有鉴评报告。点击「开始鉴评」，系统会按散文量规和你的风格档案逐维打分并给出修改建议。
        </p>
      ) : null}

      {evaluation && report ? (
        <>
          <div className="eval-overall">
            <div className={`eval-grade ${gradeTone[evaluation.grade] ?? "eval-grade-c"}`}>
              <span className="eval-grade-letter">{evaluation.grade}</span>
              <span className="eval-grade-score">{evaluation.overall_score.toFixed(1)}</span>
            </div>
            <p className="eval-summary">{report.overall.summary}</p>
          </div>

          {expanded ? (
            <>
              <div className="eval-section">
                <div className="eval-section-title">分项评分</div>
                <div className="eval-dims">
                  {report.dimensions.map((dim) => (
                    <div key={dim.key} className="eval-dim">
                      <div className="eval-dim-head">
                        <span className="eval-dim-label">{dim.label}</span>
                        <span className="eval-dim-weight">权重 {Math.round(dim.weight * 100)}%</span>
                        <span className="eval-dim-score">{dim.score.toFixed(1)}</span>
                      </div>
                      <div className="eval-bar-track">
                        <div
                          className={`eval-bar-fill ${scoreTone(dim.score)}`}
                          style={{ width: `${Math.max(0, Math.min(100, dim.score * 10))}%` }}
                        />
                      </div>
                      <p className="eval-dim-comment">{dim.comment}</p>
                      {dim.quotes && dim.quotes.length > 0 ? (
                        <ul className="eval-quotes">
                          {dim.quotes.map((q, i) => (
                            <li key={i}>「{q}」</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>

              {report.suggestions.length > 0 ? (
                <div className="eval-section">
                  <div className="eval-section-title">
                    修改建议 <span className="eval-count">{report.suggestions.length}</span>
                  </div>
                  <ul className="eval-suggestions">
                    {report.suggestions.map((item, index) => (
                      <li key={index} className="eval-suggestion">
                        <div className="eval-suggestion-head">
                          <span className="eval-suggestion-loc">{item.location || "全文"}</span>
                          <span className="eval-suggestion-issue">{item.issue}</span>
                        </div>
                        {item.why ? <p className="eval-suggestion-why">{item.why}</p> : null}
                        {item.fix ? <p className="eval-suggestion-fix">改法：{item.fix}</p> : null}
                        {onApplySuggestion && canRewrite ? (
                          <button
                            type="button"
                            className="eval-apply"
                            onClick={() => onApplySuggestion(suggestionToInstruction(item))}
                          >
                            用这条建议改写
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {report.style_deviations.length > 0 ? (
                <div className="eval-section">
                  <div className="eval-section-title">风格偏离</div>
                  <ul className="eval-deviations">
                    {report.style_deviations.map((item, index) => (
                      <li key={index}>
                        <span className="eval-dev-dim">{item.dimension}</span>
                        <span className="eval-dev-body">
                          档案要求「{item.expected}」，实际「{item.observed}」
                          {item.advice ? `。建议：${item.advice}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {report.ai_tell_flags.length > 0 ? (
                <div className="eval-section">
                  <div className="eval-section-title">AI 写作痕迹</div>
                  <div className="eval-flags">
                    {report.ai_tell_flags.map((flag, index) => (
                      <span key={index} className="eval-flag">{flag}</span>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="eval-section">
                <div className="eval-section-title">客观统计</div>
                <div className="eval-stats">
                  <span>字数 {String(features.char_count ?? "-")}</span>
                  <span>段落 {String(features.paragraph_count ?? "-")}</span>
                  <span>句数 {String(features.sentence_count ?? "-")}</span>
                  <span>平均句长 {Number(features.avg_sentence_length ?? 0).toFixed(1)}</span>
                  <span>词汇丰富度 {Number(features.ttr ?? 0).toFixed(2)}</span>
                </div>
              </div>
            </>
          ) : null}

          <p className="eval-disclaimer">{report.disclaimer}</p>
        </>
      ) : null}
    </div>
  );
}
