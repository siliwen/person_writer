"use client";

import { useMemo, useRef, useState } from "react";
import type { BusyAction, StyleProfile, WritingDocument } from "@/lib/types";
import { GENRES } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";
import { DocumentReader } from "./DocumentReader";

type WritingViewProps = {
  styles: StyleProfile[];
  selectedStyleId: string;
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
}: WritingViewProps) {
  const { requireAuth } = useAuth();
  const [writingGenre, setWritingGenre] = useState("散文");
  const [title, setTitle] = useState("附近生活");
  const [brief, setBrief] = useState("写一篇关于街角小店和旧物的文章。");
  const [targetLength, setTargetLength] = useState("1200字");
  const [styleIntensity, setStyleIntensity] = useState("balanced");
  const [mustInclude, setMustInclude] = useState("具体场景、自然段、克制表达");
  const [mustAvoid, setMustAvoid] = useState("AI 套话、空泛抒情、宏大口号");

  const writingRef = useRef<HTMLDivElement | null>(null);
  const busy = busyAction !== null;
  const isWriting = busyAction === "writing";

  const selectedStyle = useMemo(
    () => styles.find((s) => s.id === selectedStyleId),
    [styles, selectedStyleId]
  );

  function handleGenerate() {
    if (!requireAuth()) return;
    if (!selectedStyleId) return;
    onGenerate({
      styleProfileId: selectedStyleId,
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
            ) : (
              <span className="badge badge-neutral">未选择风格</span>
            )}
          </div>

          {styles.length === 0 ? (
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
                <option value="">请选择已确认风格</option>
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
            <div className="form-field full">
              <label className="form-label">风格贴近程度</label>
              <select className="form-select" value={styleIntensity} onChange={(e) => setStyleIntensity(e.target.value)}>
                {styleIntensityOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
              <span className="form-hint">默认建议使用"平衡仿写"。如果觉得太像原文，可以改成"轻度参考"。</span>
            </div>
            <div className="form-field full">
              <label className="form-label">标题 / 主题</label>
              <input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="form-field full">
              <label className="form-label">写作要求</label>
              <textarea className="form-textarea" value={brief} onChange={(e) => setBrief(e.target.value)} />
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
            disabled={busy || !selectedStyleId}
            onClick={handleGenerate}
          >
            {isWriting ? "正在生成文章……" : "按选定风格生成文章"}
          </button>
          {writingError ? <p className="inline-error" role="alert">{writingError}</p> : null}
        </div>
      </div>

      {/* Right panel: document reader */}
      <div className="writing-right-panel">
        {doc ? (
          <DocumentReader
            document={doc}
            generationCount={generationCount}
            busyAction={busyAction}
            onRewrite={onRewrite}
            onOverwriteParagraph={onOverwriteParagraph}
            onSaveDocument={onSaveDocument}
            onDownloadDocument={onDownloadDocument}
            showSaveButton
          />
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
