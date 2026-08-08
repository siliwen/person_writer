"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import type { BusyAction, StyleJob, StyleDraftView } from "@/lib/types";
import { GENRES } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";
import { StyleProfileEditor } from "./StyleProfileEditor";

type NewStyleModalProps = {
  styleJob: StyleJob | null;
  styleDraftView: StyleDraftView | null;
  styleName: string;
  profileJson: string;
  confirmedStyleId: string;
  uploadGenre: string;
  busyAction: BusyAction;
  uploadError: string;
  analysisError: string;
  confirmError: string;
  onUploadGenreChange: (genre: string) => void;
  onStyleNameChange: (name: string) => void;
  onProfileJsonChange: (json: string) => void;
  onUpload: (files: FileList) => void;
  onConfirm: () => void;
  onClose: () => void;
};

export function NewStyleModal(props: NewStyleModalProps) {
  const {
    styleJob,
    styleDraftView,
    styleName,
    profileJson,
    confirmedStyleId,
    uploadGenre,
    busyAction,
    uploadError,
    analysisError,
    confirmError,
    onUploadGenreChange,
    onStyleNameChange,
    onProfileJsonChange,
    onUpload,
    onConfirm,
    onClose,
  } = props;

  const { requireAuth } = useAuth();

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<FileList | null>(null);
  const [selectedFileNames, setSelectedFileNames] = useState<string[]>([]);
  const [expandedDims, setExpandedDims] = useState<Set<string>>(new Set());
  const [dragOver, setDragOver] = useState(false);

  const busy = busyAction !== null;
  const isUploading = busyAction === "upload";
  const isAnalyzing = busyAction === "analysis";
  const isConfirming = busyAction === "confirm";

  // Determine which step we're on
  const step = styleDraftView ? (confirmedStyleId ? 3 : 2) : 1;

  const allExpanded = styleDraftView
    ? styleDraftView.dimensions.length > 0 &&
      styleDraftView.dimensions.every((d) => expandedDims.has(d.key))
    : false;

  useEffect(() => {
    if (styleDraftView) {
      setExpandedDims(new Set());
    }
  }, [styleDraftView]);

  function toggleDim(key: string) {
    setExpandedDims((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleAll() {
    if (!styleDraftView) return;
    if (allExpanded) setExpandedDims(new Set());
    else setExpandedDims(new Set(styleDraftView.dimensions.map((d) => d.key)));
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const fileList = e.target.files;
    setSelectedFiles(fileList);
    setSelectedFileNames(fileList ? Array.from(fileList).map((f) => f.name) : []);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const fileList = e.dataTransfer.files;
    if (fileList && fileList.length > 0) {
      setSelectedFiles(fileList);
      setSelectedFileNames(Array.from(fileList).map((f) => f.name));
    }
  }

  function handleUploadClick() {
    if (!requireAuth()) return;
    if (!selectedFiles || selectedFiles.length === 0) return;
    onUpload(selectedFiles);
  }

  function handleConfirmClick() {
    onConfirm();
  }

  function handleClose() {
    if (busy) return;
    onClose();
  }

  return (
    <div className="modal-overlay">
      <div className="modal-dialog new-style-modal">
        {/* Modal header */}
        <div className="modal-header">
          <h2 className="modal-title">新建风格</h2>
          <button
            className="modal-close-btn"
            type="button"
            onClick={handleClose}
            disabled={busy}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>

        {/* Step indicator */}
        <div className="modal-steps">
          <div className={`modal-step ${step >= 1 ? "active" : ""} ${step > 1 ? "done" : ""}`}>
            <span className="modal-step-num">{step > 1 ? "✓" : "1"}</span>
            <span className="modal-step-label">上传作品</span>
          </div>
          <div className="modal-step-line" />
          <div className={`modal-step ${step >= 2 ? "active" : ""} ${step > 2 ? "done" : ""}`}>
            <span className="modal-step-num">{step > 2 ? "✓" : "2"}</span>
            <span className="modal-step-label">风格分析</span>
          </div>
          <div className="modal-step-line" />
          <div className={`modal-step ${step >= 3 ? "active" : ""}`}>
            <span className="modal-step-num">3</span>
            <span className="modal-step-label">确认保存</span>
          </div>
        </div>

        {/* Modal body */}
        <div className="modal-body">
          {/* Step 1: Upload */}
          {step === 1 && (
            <div className="modal-step-content">
              <div
                className={`upload-dropzone ${dragOver ? "drag-over" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="upload-dropzone-icon">📄</div>
                <div className="upload-dropzone-text">
                  {selectedFileNames.length > 0
                    ? `已选择 ${selectedFileNames.length} 个文件`
                    : "点击或拖拽文件到此处上传"}
                </div>
                <div className="upload-dropzone-hint">支持 .txt / .md / .docx，可多选</div>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".txt,.md,.docx"
                  onChange={handleFileChange}
                  style={{ display: "none" }}
                />
              </div>

              {selectedFileNames.length > 0 && (
                <div className="upload-file-tags">
                  {selectedFileNames.map((name) => (
                    <span key={name} className="file-tag">{name}</span>
                  ))}
                </div>
              )}

              <div className="form-field" style={{ marginTop: "16px" }}>
                <label className="form-label">作品文体</label>
                <select
                  className="form-select"
                  value={uploadGenre}
                  onChange={(e) => onUploadGenreChange(e.target.value)}
                >
                  {GENRES.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>

              <p className="form-hint" style={{ marginTop: "12px" }}>
                系统会自动完成上传、解析和风格分析。建议选择 2-5 篇风格相近的作品以获得更准确的分析结果。
              </p>

              {uploadError ? <p className="inline-error" role="alert">{uploadError}</p> : null}
              {analysisError ? <p className="inline-error" role="alert">{analysisError}</p> : null}

              <button
                className="btn btn-primary"
                type="button"
                disabled={busy || !selectedFiles || selectedFiles.length === 0}
                onClick={handleUploadClick}
                style={{ marginTop: "16px", width: "100%" }}
              >
                {isUploading ? "正在上传解析……" : isAnalyzing ? "正在分析风格……" : "开始分析"}
              </button>
            </div>
          )}

          {/* Step 2: Diagnosis report */}
          {step === 2 && (
            <div className="modal-step-content">
              {/* Loading state */}
              {(isUploading || isAnalyzing) && !styleDraftView ? (
                <div className="diag-loading">
                  <div className="diag-loading-spinner" />
                  <p className="diag-loading-text">
                    {isUploading ? "正在上传和解析作品……" : "正在分析写作风格……"}
                  </p>
                  <p className="diag-loading-hint">分析过程约需 10-30 秒，请耐心等待</p>
                </div>
              ) : null}

              {styleDraftView ? (
                <>
                  {/* Overall summary */}
                  <div className="diag-overall">
                    <div className="diag-overall-label">风格总览</div>
                    <p className="diag-overall-text">{styleDraftView.plainSummary}</p>
                  </div>

                  {/* Expand all toggle */}
                  <div className="diag-list-header">
                    <span className="diag-list-title">六维风格诊断</span>
                    {styleDraftView.dimensions.length > 0 ? (
                      <button
                        className="btn btn-ghost btn-sm"
                        type="button"
                        onClick={toggleAll}
                      >
                        {allExpanded ? "收起全部" : "展开全部"}
                      </button>
                    ) : null}
                  </div>

                  {/* Expandable dimension cards */}
                  <div className="diag-list">
                    {styleDraftView.dimensions.map((dim, idx) => {
                      const isExpanded = expandedDims.has(dim.key);
                      const summary = dim.whatWeFound[0] || dim.whyItMatters || "暂无诊断信息";
                      return (
                        <div className={`diag-card ${isExpanded ? "expanded" : ""}`} key={dim.key}>
                          <div
                            className="diag-card-header"
                            onClick={() => toggleDim(dim.key)}
                            role="button"
                            tabIndex={0}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                toggleDim(dim.key);
                              }
                            }}
                          >
                            <span className="diag-card-num">{idx + 1}</span>
                            <span className="diag-card-title">{dim.title}</span>
                            <span className={`diag-card-toggle ${isExpanded ? "expanded" : ""}`}>
                              {isExpanded ? "收起" : "展开详情"}
                            </span>
                          </div>

                          {!isExpanded && (
                            <div className="diag-card-summary">{summary}</div>
                          )}

                          {isExpanded && (
                            <div className="diag-card-body">
                              <div className="diag-section">
                                <div className="diag-section-label">诊断发现</div>
                                {dim.whatWeFound.length > 0 ? (
                                  dim.whatWeFound.map((item, i) => (
                                    <p className="diag-finding" key={i}>
                                      <span className="diag-finding-dot" />
                                      {item}
                                    </p>
                                  ))
                                ) : (
                                  <p className="diag-text">暂无诊断发现。</p>
                                )}
                              </div>

                              {dim.whyItMatters ? (
                                <div className="diag-section">
                                  <div className="diag-section-label">为什么重要</div>
                                  <p className="diag-text">{dim.whyItMatters}</p>
                                </div>
                              ) : null}

                              {dim.editableSummary ? (
                                <div className="diag-section">
                                  <div className="diag-section-label">补充说明</div>
                                  <p className="diag-text">{dim.editableSummary}</p>
                                </div>
                              ) : null}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Writing rules */}
                  {(styleDraftView.mustDo.length > 0 || styleDraftView.mustAvoid.length > 0) ? (
                    <div className="diag-rules">
                      {styleDraftView.mustDo.length > 0 ? (
                        <div className="diag-rule-block">
                          <div className="diag-rule-title must-do">写作时必须做到</div>
                          {styleDraftView.mustDo.map((item, i) => (
                            <p className="diag-rule-item" key={i}>
                              <span className="diag-rule-dot must-do" />
                              {item}
                            </p>
                          ))}
                        </div>
                      ) : null}
                      {styleDraftView.mustAvoid.length > 0 ? (
                        <div className="diag-rule-block">
                          <div className="diag-rule-title must-avoid">必须避免</div>
                          {styleDraftView.mustAvoid.map((item, i) => (
                            <p className="diag-rule-item" key={i}>
                              <span className="diag-rule-dot must-avoid" />
                              {item}
                            </p>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {/* Evidence */}
                  {styleDraftView.evidence.length > 0 ? (
                    <details className="diag-evidence">
                      <summary>判断依据（{styleDraftView.evidence.length} 条）</summary>
                      <div className="diag-evidence-list">
                        {styleDraftView.evidence.map((item, i) => (
                          <p className="diag-evidence-item" key={i}>{item}</p>
                        ))}
                      </div>
                    </details>
                  ) : null}

                  {/* Style name + confirm */}
                  <StyleProfileEditor
                    name={styleName}
                    profileJson={profileJson}
                    disabled={Boolean(confirmedStyleId)}
                    busy={busy}
                    error={confirmError}
                    saveLabel={isConfirming ? "正在保存……" : "确认并保存到风格库"}
                    onNameChange={onStyleNameChange}
                    onProfileJsonChange={onProfileJsonChange}
                    onSave={handleConfirmClick}
                  />
                </>
              ) : null}
            </div>
          )}

          {/* Step 3: Success */}
          {step === 3 && (
            <div className="modal-step-content modal-success">
              <div className="modal-success-icon">✓</div>
              <h3 className="modal-success-title">风格已保存</h3>
              <p className="modal-success-desc">
                风格"{styleName}"已成功保存到你的风格库，现在可以用它来写作了。
              </p>
              <button
                className="btn btn-primary"
                type="button"
                onClick={onClose}
                style={{ width: "100%" }}
              >
                完成
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
