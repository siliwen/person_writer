"use client";

import { useEffect, useMemo, useState } from "react";
import type { QuotaView, StyleProfile } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";
import { fetchOptimizePrompt } from "@/lib/api";
import { estimateArticlePoints } from "@/lib/quota";

/** 自由写作去掉文体/字数选择后，内部固定传给后端的占位值。 */
const FREE_WRITE_GENRE = "不限";
const FREE_WRITE_TARGET_LENGTH = "按需求";
/** 无字数选择时，按默认 1200 字预估积分。 */
const DEFAULT_ESTIMATE_CHARS = 1200;

const PLACEHOLDERS = [
  "例如：写一篇关于街角旧书店的散文，1200字，温暖克制",
  "例如：以「迟到」为题写一篇叙事散文",
  "例如：写一首关于夏末傍晚的短诗",
  "例如：写一段杂文，聊聊年轻人为什么不爱发朋友圈了",
];

export type FreeWritePayload = {
  genre: string;
  targetLength: string;
  title: string;
  brief: string;
  /** 空字符串 = 自由写作（不绑定风格）；非空 = 指定个人风格。 */
  styleProfileId: string;
};

type FreeWriteBoxProps = {
  quota: QuotaView | null;
  styles: StyleProfile[];
  generating: boolean;
  onFreeWrite: (payload: FreeWritePayload) => void;
};

export function FreeWriteBox({ quota, styles: _styles, generating, onFreeWrite }: FreeWriteBoxProps) {
  const { requireAuth } = useAuth();

  const [promptText, setPromptText] = useState("");
  // 自由写作固定不绑定个人风格，文体/字数由用户在需求中描述，不再提供选择器。
  const genre = FREE_WRITE_GENRE;
  const targetLength = FREE_WRITE_TARGET_LENGTH;
  const styleProfileId = "";
  const [optimizing, setOptimizing] = useState(false);
  const [optimized, setOptimized] = useState(false);
  const [optimizeError, setOptimizeError] = useState("");
  const [genError, setGenError] = useState("");
  const [placeholderIndex, setPlaceholderIndex] = useState(0);

  // 占位符轮播（仅在未输入内容时展示）
  useEffect(() => {
    if (promptText.trim()) return;
    const timer = window.setInterval(() => {
      setPlaceholderIndex((i) => (i + 1) % PLACEHOLDERS.length);
    }, 3500);
    return () => window.clearInterval(timer);
  }, [promptText]);

  const estimate = useMemo(() => {
    if (!quota) return { points: 0, blocked: false, overLength: false, insufficient: false };
    const points = estimateArticlePoints(DEFAULT_ESTIMATE_CHARS, quota.article_length_brackets);
    const overLength = false;
    const insufficient = quota.points_balance < points;
    return { points, blocked: overLength || insufficient, overLength, insufficient };
  }, [quota]);

  const optimizeCost = 1; // 优化提示词固定 1 积分
  const canOptimize = !optimizing && !generating && !!quota && quota.points_balance >= optimizeCost;

  async function handleOptimize() {
    setOptimizeError("");
    if (!requireAuth()) return;
    const source = promptText.trim();
    if (!source) {
      setOptimizeError("请先输入一句话需求，再点优化提示词。");
      return;
    }
    if (quota && quota.points_balance < optimizeCost) {
      setOptimizeError("积分不足，无法优化提示词。");
      return;
    }
    setOptimizing(true);
    try {
      const res = await fetchOptimizePrompt(source);
      setPromptText(res.optimized_prompt);
      setOptimized(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setOptimizeError(`优化失败：${message}`);
    } finally {
      setOptimizing(false);
    }
  }

  function handleGenerate() {
    setGenError("");
    if (!requireAuth()) return;
    const brief = promptText.trim();
    if (!brief) {
      setGenError("请填写写作需求，或先点「优化提示词」扩写。");
      return;
    }
    if (estimate.blocked) {
      setGenError(
        estimate.overLength
          ? `当前等级单篇文章最大长度为 ${quota?.tier.max_article_length} 字，请缩短或升级会员。`
          : `积分不足，本次生成预计需要 ${estimate.points} 积分，当前剩余 ${quota?.points_balance} 积分。`
      );
      return;
    }
    // 标题从需求首行推导，避免重复填写
    const firstLine = brief.split("\n").map((l) => l.trim()).find((l) => l) ?? "自由写作";
    const title = firstLine.length > 30 ? `${firstLine.slice(0, 30)}…` : firstLine;
    onFreeWrite({
      genre,
      targetLength,
      title,
      brief,
      styleProfileId,
    });
  }

  return (
    <section className="free-write-box">
      <div className="free-write-head">
        <h2 className="free-write-title">今天想写什么？</h2>
        <p className="free-write-sub">
          一句话描述想法，可点「优化提示词」扩写成完整需求，或直接生成。自由写作不绑定你的个人风格。
        </p>
      </div>

      <div className="free-write-input-wrap">
        <textarea
          className={`free-write-textarea ${optimized ? "optimize-flash" : ""}`}
          value={promptText}
          onChange={(e) => {
            setPromptText(e.target.value);
            setOptimized(false);
          }}
          placeholder={PLACEHOLDERS[placeholderIndex]}
          rows={4}
        />
        <button
          type="button"
          className="free-write-optimize-float"
          onClick={handleOptimize}
          disabled={!canOptimize}
          title={quota ? `消耗 ${optimizeCost} 积分` : "请先登录"}
        >
          {optimizing ? "优化中…" : optimized ? "重新优化" : "优化提示词"}
          <span className="free-write-cost"> · {optimizeCost}积分</span>
        </button>
      </div>

      <div className="free-write-config-row">
        <div className="free-write-actions">
          <button
            type="button"
            className="btn btn-primary free-write-generate"
            onClick={handleGenerate}
            disabled={generating || estimate.blocked}
          >
            {generating ? "正在生成文章……" : (
              <>
                生成文章
                {quota ? <span className="btn-cost"> · 预计{estimate.points}积分</span> : null}
              </>
            )}
          </button>
        </div>
        {optimizeError ? <span className="inline-error">{optimizeError}</span> : null}
      </div>

      {genError ? <p className="inline-error free-write-gen-error">{genError}</p> : null}
    </section>
  );
}
