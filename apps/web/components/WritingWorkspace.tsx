"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

type Material = {
  id: string;
  title: string;
  genre: string;
  source_filename: string | null;
  char_count: number;
  paragraph_count: number;
};

type StyleJob = {
  id: string;
  status: string;
  material_ids: string[];
  draft_profile: Record<string, unknown>;
};

type StyleProfile = {
  id: string;
  name: string;
  status: string;
  profile: Record<string, unknown>;
};

type StyleDraftView = {
  plainSummary: string;
  dimensions: Array<{
    key: string;
    title: string;
    whatWeFound: string[];
    whyItMatters: string;
    editableSummary: string;
  }>;
  mustDo: string[];
  mustAvoid: string[];
  evidence: string[];
};

type DocumentParagraph = {
  id: string;
  position: number;
  content: string;
  rewrite_count: number;
};


type ModelStatus = {
  mode: string;
  has_api_key: boolean;
  base_url: string;
  model_name: string;
  fallback_behavior: string;
};
type WritingDocument = {
  id: string;
  title: string;
  genre: string;
  content: string;
  paragraphs: DocumentParagraph[];
  updated_at: string;
};

type BusyAction = "upload" | "analysis" | "confirm" | "delete_style" | "writing" | "rewrite" | null;
type StartMode = "create_style" | "use_existing";

const GENRES = ["散文", "故事", "小说", "剧本", "诗歌", "杂文", "随笔"];

function apiBase() {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

async function parseJson<T>(response: Response): Promise<T> {
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail ?? body.message ?? `HTTP ${response.status}`);
  }
  return body as T;
}

export function WritingWorkspace() {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [startMode, setStartMode] = useState<StartMode>("create_style");
  const [startModeTouched, setStartModeTouched] = useState(false);
  const [files, setFiles] = useState<FileList | null>(null);
  const [uploadGenre, setUploadGenre] = useState("散文");
  const [styleJob, setStyleJob] = useState<StyleJob | null>(null);
  const [styleName, setStyleName] = useState("我的散文风格");
  const [profileJson, setProfileJson] = useState("");
  const [styles, setStyles] = useState<StyleProfile[]>([]);
  const [selectedStyleId, setSelectedStyleId] = useState("");
  const [writingGenre, setWritingGenre] = useState("散文");
  const [title, setTitle] = useState("附近生活");
  const [brief, setBrief] = useState("写一篇关于街角小店和旧物的文章。");
  const [targetLength, setTargetLength] = useState("1200字");
  const [styleIntensity, setStyleIntensity] = useState("balanced");
  const [mustInclude, setMustInclude] = useState("具体场景、自然段、克制表达");
  const [mustAvoid, setMustAvoid] = useState("AI 套话、空泛抒情、宏大口号");
  const [document, setDocument] = useState<WritingDocument | null>(null);
  const [generationCount, setGenerationCount] = useState(0);
  const [rewriteDialogParagraphId, setRewriteDialogParagraphId] = useState("");
  const [rewriteInstruction, setRewriteInstruction] = useState("");
  const [deleteStyleError, setDeleteStyleError] = useState("");
  const [status, setStatus] = useState("当前为 Demo 用户模式：MVP1 暂不做真实注册登录。");
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const [uploadError, setUploadError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [confirmError, setConfirmError] = useState("");
  const [writingError, setWritingError] = useState("");
  const [rewriteError, setRewriteError] = useState("");
  const [confirmedStyleId, setConfirmedStyleId] = useState("");
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const writingRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const busy = busyAction !== null;

  const selectedStyle = useMemo(
    () => styles.find((item) => item.id === selectedStyleId),
    [styles, selectedStyleId]
  );
  const styleDraftView = useMemo(() => summarizeStyleDraft(styleJob?.draft_profile), [styleJob]);
  const documentUpdatedAt = useMemo(() => {
    if (!document?.updated_at) {
      return "";
    }
    return new Date(document.updated_at).toLocaleString("zh-CN", { hour12: false });
  }, [document?.updated_at]);
  const rewriteDialogParagraph = useMemo(
    () => document?.paragraphs.find((item) => item.id === rewriteDialogParagraphId) ?? null,
    [document, rewriteDialogParagraphId]
  );

  useEffect(() => {
    void refreshAll();
  }, []);

  async function refreshAll() {
    await Promise.all([loadMaterials(), loadStyles(), loadModelStatus()]);
  }

  async function loadMaterials() {
    const response = await fetch(`${apiBase()}/v1/materials`);
    const body = await parseJson<{ materials: Material[] }>(response);
    setMaterials(body.materials);
  }


  async function loadModelStatus() {
    const response = await fetch(`${apiBase()}/v1/model-status`);
    const body = await parseJson<ModelStatus>(response);
    setModelStatus(body);
  }
  async function loadStyles() {
    const response = await fetch(`${apiBase()}/v1/style-profiles`);
    const body = await parseJson<{ styles: StyleProfile[] }>(response);
    setStyles(body.styles);
    setSelectedStyleId((current) => current || body.styles[0]?.id || "");
    setStartMode((current) => {
      if (startModeTouched) {
        return current;
      }
      return body.styles.length > 0 ? "use_existing" : "create_style";
    });
  }

  async function uploadMaterials() {
    setUploadError("");
    setAnalysisError("");
    setConfirmError("");
    if (!files || files.length === 0) {
      setUploadError("请选择要上传的 .txt/.md/.docx 文件。");
      setStatus("请选择要上传的 .txt/.md/.docx 文件。");
      return;
    }
    if (styleJob && !confirmedStyleId) {
      const shouldOverwrite = window.confirm("当前还有未保存的风格草案。上传新作品会重新分析并覆盖当前草案，是否继续？");
      if (!shouldOverwrite) {
        return;
      }
    }
    let currentPhase: "upload" | "analysis" = "upload";
    setBusyAction("upload");
    setStatus("正在上传并解析作品……");
    try {
      const form = new FormData();
      form.set("genre", uploadGenre);
      Array.from(files).forEach((file) => form.append("files", file));
      const response = await fetch(`${apiBase()}/v1/materials/upload`, {
        method: "POST",
        body: form
      });
      const body = await parseJson<{ materials: Material[] }>(response);
      await loadMaterials();
      setFiles(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      setStatus(`已上传 ${body.materials.length} 篇作品，正在分析风格……`);
      currentPhase = "analysis";
      setBusyAction("analysis");
      const analysisResponse = await fetch(`${apiBase()}/v1/style-analysis-jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ material_ids: body.materials.map((item) => item.id) })
      });
      const job = await parseJson<StyleJob>(analysisResponse);
      setStyleJob(job);
      setConfirmedStyleId("");
      setProfileJson(JSON.stringify(job.draft_profile, null, 2));
      setStatus("风格分析完成，请确认系统理解是否准确。");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (currentPhase === "analysis") {
        setAnalysisError(message);
        setStatus(`风格分析失败：${message}`);
      } else {
        setUploadError(message);
        setStatus(`上传或分析失败：${message}`);
      }
    } finally {
      setBusyAction(null);
    }
  }

  async function confirmStyle() {
    setConfirmError("");
    if (!styleJob) {
      setConfirmError("还没有待确认的风格分析草案。");
      setStatus("还没有待确认的风格分析草案。");
      return;
    }
    const normalizedStyleName = styleName.trim();
    if (!normalizedStyleName) {
      setConfirmError("请填写风格名称。");
      setStatus("请填写风格名称。");
      return;
    }
    if (styles.some((style) => style.name.trim() === normalizedStyleName && style.id !== confirmedStyleId)) {
      setConfirmError("这个风格名称已经存在，请换一个名称。");
      setStatus("这个风格名称已经存在，请换一个名称。");
      return;
    }
    let profile: Record<string, unknown>;
    try {
      profile = JSON.parse(profileJson) as Record<string, unknown>;
    } catch {
      setConfirmError("风格 JSON 格式错误，请修正后再确认。");
      setStatus("风格 JSON 格式错误，请修正后再确认。");
      return;
    }
    setBusyAction("confirm");
    setStatus("正在保存到个人风格库……");
    try {
      const response = await fetch(`${apiBase()}/v1/style-profiles/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: styleJob.id, name: normalizedStyleName, profile })
      });
      const style = await parseJson<StyleProfile>(response);
      await loadStyles();
      setSelectedStyleId(style.id);
      setConfirmedStyleId(style.id);
      setStartMode("use_existing");
      setStartModeTouched(true);
      setStatus(`风格“${style.name}”已保存，可以用于写作。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const friendlyMessage = message.includes("风格名称已存在") ? "这个风格名称已经存在，请换一个名称。" : message;
      setConfirmError(friendlyMessage);
      setStatus(`保存风格失败：${friendlyMessage}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function createWritingTask() {
    setWritingError("");
    if (!selectedStyleId) {
      setWritingError("请先从风格库选择一个 active 风格。");
      setStatus("请先从风格库选择一个 active 风格。");
      return;
    }
    if (!title.trim()) {
      setWritingError("请填写标题或主题。");
      setStatus("请填写标题或主题。");
      return;
    }
    if (!brief.trim()) {
      setWritingError("请填写写作要求。");
      setStatus("请填写写作要求。");
      return;
    }
    if (!targetLength.trim()) {
      setWritingError("请填写目标字数或篇幅。");
      setStatus("请填写目标字数或篇幅。");
      return;
    }
    setBusyAction("writing");
    const nextGenerationCount = generationCount + 1;
    setStatus(`正在按选定风格生成第 ${nextGenerationCount} 版文章……`);
    try {
      const response = await fetch(`${apiBase()}/v1/writing-tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          style_profile_id: selectedStyleId,
          requested_mode: "style_prompt_only",
          task: {
            genre: writingGenre,
            task_type: "新写",
            title: title.trim(),
            brief: brief.trim(),
            target_length: targetLength.trim(),
            target_reader: "普通读者",
            must_include: mustInclude,
            must_avoid: mustAvoid,
            eval_focus: "风格贴近但表达原创、任务完成度、自然段可编辑性",
            style_intensity: styleIntensity
          }
        })
      });
      const body = await parseJson<{ document: WritingDocument }>(response);
      setDocument(body.document);
      setGenerationCount(nextGenerationCount);
      setRewriteDialogParagraphId("");
      setRewriteInstruction("");
      setStatus(`第 ${nextGenerationCount} 版文章已生成。点击正文里的自然段即可提交修改意见。`);
      window.setTimeout(() => writingRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setWritingError(`本次生成失败，右侧仍显示上一次文章。原因：${message}`);
      setStatus(`生成失败：${message}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function deleteSelectedStyle() {
    setDeleteStyleError("");
    if (!selectedStyle) {
      setDeleteStyleError("请先选择要删除的风格。");
      return;
    }
    const shouldDelete = window.confirm(`确认删除风格“${selectedStyle.name}”吗？删除后它不会再出现在风格列表里，已生成文章不受影响。`);
    if (!shouldDelete) {
      return;
    }
    setBusyAction("delete_style");
    setStatus(`正在删除风格“${selectedStyle.name}”……`);
    try {
      const response = await fetch(`${apiBase()}/v1/style-profiles/${selectedStyle.id}`, {
        method: "DELETE"
      });
      await parseJson<{ id: string; status: string }>(response);
      const nextStyles = styles.filter((style) => style.id !== selectedStyle.id);
      setStyles(nextStyles);
      const nextSelectedStyleId = nextStyles[0]?.id ?? "";
      setSelectedStyleId(nextSelectedStyleId);
      if (confirmedStyleId === selectedStyle.id) {
        setConfirmedStyleId("");
      }
      if (!nextSelectedStyleId) {
        setDocument(null);
        setGenerationCount(0);
      }
      setStatus(`风格“${selectedStyle.name}”已删除。`);
      await loadStyles();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setDeleteStyleError(message);
      setStatus(`删除风格失败：${message}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function rewriteParagraph() {
    setRewriteError("");
    if (!document) {
      setRewriteError("请选择要重写的自然段。");
      setStatus("请选择要重写的自然段。");
      return;
    }
    if (!rewriteDialogParagraphId) {
      setRewriteError("请选择要重写的自然段。");
      return;
    }
    const instruction = rewriteInstruction.trim();
    if (!instruction) {
      setRewriteError("请填写对选中自然段的修改意见。");
      setStatus("请填写对选中自然段的修改意见。");
      return;
    }
    setBusyAction("rewrite");
    setStatus("正在重写指定自然段……");
    try {
      const response = await fetch(
        `${apiBase()}/v1/documents/${document.id}/paragraphs/${rewriteDialogParagraphId}/rewrite`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ instruction })
        }
      );
      const updated = await parseJson<WritingDocument>(response);
      setDocument(updated);
      setRewriteDialogParagraphId("");
      setRewriteInstruction("");
      setStatus("指定自然段已重写，其他自然段保持不变。");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setRewriteError(message);
      setStatus(`段落重写失败：${message}`);
    } finally {
      setBusyAction(null);
    }
  }

  function openRewriteDialog(paragraph: DocumentParagraph) {
    setRewriteDialogParagraphId(paragraph.id);
    setRewriteInstruction("");
    setRewriteError("");
  }

  function closeRewriteDialog() {
    if (busyAction === "rewrite") {
      return;
    }
    setRewriteDialogParagraphId("");
    setRewriteInstruction("");
    setRewriteError("");
  }

  return (
    <main className="shell">
      <section className="hero">
        <div>
          <h1>个人风格写作 SaaS · MVP1</h1>
          <p>
            先用固定 Demo 用户打通个人风格写作闭环：作品上传、风格分析、用户确认、风格库、风格写作和自然段重写。
          </p>
        </div>
        <div className="badge">Demo 用户模式 / 组织与余额 MVP2</div>
      </section>

      <section className="status-bar">{busy ? "处理中…… " : ""}{status}<span className="model-chip">模型：{modelStatus ? `${modelStatus.mode} / ${modelStatus.model_name} / ${modelStatus.fallback_behavior}` : "读取中"}</span></section>

      <section className="dashboard">
        <div className="metric">
          <span>作品</span>
          <strong>{materials.length}</strong>
        </div>
        <div className="metric">
          <span>已确认风格</span>
          <strong>{styles.length}</strong>
        </div>
        <div className="metric">
          <span>当前风格</span>
          <strong>{selectedStyle?.name ?? "未选择"}</strong>
        </div>
      </section>

      <section className="workflow-linear">
        <div className="panel start-panel">
          <div className="step-heading">
            <h2>选择开始方式</h2>
            <span>{startMode === "create_style" ? "创建新风格" : "使用已有风格"}</span>
          </div>
          <p className="small">可以上传新的参考文章生成风格，也可以直接使用以前保存过的风格写文章。</p>
          <div className="start-mode-grid">
            <button
              className={`choice-card ${startMode === "create_style" ? "selected" : ""}`}
              type="button"
              onClick={() => {
                setStartMode("create_style");
                setStartModeTouched(true);
                setSelectedStyleId("");
                setWritingError("");
              }}
            >
              <strong>上传参考作品，创建新风格</strong>
              <span>适合第一次使用，或要分析一个新的作者/新风格。</span>
            </button>
            <button
              className={`choice-card ${startMode === "use_existing" ? "selected" : ""}`}
              type="button"
              onClick={() => {
                setStartMode("use_existing");
                setStartModeTouched(true);
                setSelectedStyleId((current) => current || styles[0]?.id || "");
                setWritingError("");
              }}
            >
              <strong>使用已有风格写文章</strong>
              <span>适合已经保存过风格，想直接进入写作。</span>
            </button>
          </div>
        </div>

        {startMode === "create_style" ? (
          <>
        <div className="panel step-panel">
          <div className="step-heading">
            <h2>A1. 上传作品并分析风格</h2>
            <span>{styleJob ? "已生成风格草案" : busyAction === "upload" || busyAction === "analysis" ? "进行中" : "未开始"}</span>
          </div>
          <p className="small">支持一次选择多篇风格相近的 .txt/.md/.docx 作品。</p>
          <div className="field">
            <label>作品文体</label>
            <select value={uploadGenre} onChange={(event) => setUploadGenre(event.target.value)}>
              {GENRES.map((genre) => (
                <option key={genre} value={genre}>{genre}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>文件</label>
            <input
              multiple
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.docx"
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                setFiles(event.target.files);
                setUploadError("");
              }}
            />
          </div>
          <button className="primary" type="button" disabled={busy} onClick={uploadMaterials}>
            {busyAction === "upload"
              ? "正在上传解析……"
              : busyAction === "analysis"
                ? "正在分析风格……"
                : "上传作品并分析风格"}
          </button>
          {uploadError ? <p className="inline-error" role="alert">{uploadError}</p> : null}
          {analysisError ? <p className="inline-error" role="alert">{analysisError}</p> : null}
          <p className="inline-status" aria-live="polite">
            {styleJob ? "风格分析完成。请继续确认风格。" : "选择文件后点击按钮，系统会自动完成上传、解析和风格分析。"}
          </p>
        </div>

        <div className="panel step-panel">
          <div className="step-heading">
            <h2>A2. 确认并保存新风格</h2>
            <span>{confirmedStyleId ? "已保存" : styleJob ? "待确认" : "请先完成 A1"}</span>
          </div>
          {styleDraftView ? (
            <div className="style-summary-card">
              <strong>我们理解到的作者风格</strong>
              <p>{styleDraftView.plainSummary}</p>
              <div className="report-sections">
                {styleDraftView.dimensions.map((dimension) => (
                  <section className="report-section" key={dimension.key}>
                    <h3>{dimension.title}：</h3>
                    {dimension.whatWeFound.map((item) => <p key={item}>{item}</p>)}
                    <small>{dimension.whyItMatters}</small>
                  </section>
                ))}
                <section className="report-section">
                  <h3>写作时必须做到：</h3>
                  {styleDraftView.mustDo.map((item) => <p key={item}>{item}</p>)}
                </section>
                <section className="report-section">
                  <h3>必须避免：</h3>
                  {styleDraftView.mustAvoid.map((item) => <p key={item}>{item}</p>)}
                </section>
                <section className="report-section">
                  <h3>判断依据：</h3>
                  {styleDraftView.evidence.map((item) => <p key={item}>{item}</p>)}
                </section>
              </div>
            </div>
          ) : (
            <div className="empty-preview">
              <strong>还没有风格分析结果</strong>
              <p>上传作品并分析完成后，这里会展示系统提炼出的作者风格。</p>
            </div>
          )}
          <div className="field">
            <label>风格名称</label>
            <input
              value={styleName}
              disabled={Boolean(confirmedStyleId) || !styleJob}
              onChange={(event) => {
                setStyleName(event.target.value);
                setConfirmError("");
              }}
            />
          </div>
          <details className="advanced-json">
            <summary>高级：查看和编辑完整风格档案数据</summary>
            <div className="field">
              <label>风格分析结果（确认前可编辑）</label>
              <textarea
                className="profile-json"
                value={profileJson}
                disabled={Boolean(confirmedStyleId)}
                onChange={(event) => {
                  setProfileJson(event.target.value);
                  setConfirmError("");
                }}
              />
            </div>
          </details>
          <button className="primary" type="button" disabled={busy || !styleJob || Boolean(confirmedStyleId)} onClick={confirmStyle}>
            {confirmedStyleId ? "已保存到风格库" : busyAction === "confirm" ? "正在保存……" : "确认并保存到风格库"}
          </button>
          {confirmError ? <p className="inline-error" role="alert">{confirmError}</p> : null}
          {confirmedStyleId ? <p className="inline-success">当前风格已保存。需要新风格时，请重新上传一组作品分析。</p> : null}
        </div>
          </>
        ) : (
        <div className="panel step-panel">
          <div className="step-heading">
            <h2>选择已有风格</h2>
            <span>{selectedStyleId ? "已选择" : styles.length > 0 ? "待选择" : "暂无风格"}</span>
          </div>
          {styles.length === 0 ? (
            <div className="empty-preview">
              <strong>还没有保存过风格</strong>
              <p>请切换到“上传参考作品，创建新风格”，先上传参考文章并确认保存一个风格。</p>
            </div>
          ) : (
            <>
              <p className="small">选择一个已保存风格后，可以直接在下方写作。</p>
              <div className="field">
                <label>选择已有风格</label>
                <div className="style-select-row">
                  <select value={selectedStyleId} onChange={(event) => setSelectedStyleId(event.target.value)}>
                    <option value="">请选择已确认风格</option>
                    {styles.map((style) => (
                      <option key={style.id} value={style.id}>{style.name}</option>
                    ))}
                  </select>
                  <button className="danger-secondary" type="button" disabled={busy || !selectedStyleId} onClick={deleteSelectedStyle}>
                    {busyAction === "delete_style" ? "正在删除……" : "删除这个风格"}
                  </button>
                </div>
              </div>
              {deleteStyleError ? <p className="inline-error" role="alert">{deleteStyleError}</p> : null}
            </>
          )}
        </div>
        )}

        <div className="panel step-panel" ref={writingRef}>
          <div className="step-heading">
            <h2>写作与修改文章</h2>
            <span>{document ? `第 ${generationCount} 版` : selectedStyleId ? "可生成" : "请先选择风格"}</span>
          </div>
          <p className="small">生成文章和段落修改放在同一区域。文章生成后，把鼠标移到自然段上会高亮，点击“修改这一段”填写修改意见。</p>
          {selectedStyle ? (
            <p className="current-style-note">当前使用风格：{selectedStyle.name}</p>
          ) : (
            <div className="empty-preview">
              <strong>请先选择一个风格</strong>
              <p>可以在上方创建新风格，也可以切换到“使用已有风格写文章”选择风格。</p>
            </div>
          )}
          <div className="field">
            <label>写作文体</label>
            <select
              value={writingGenre}
              onChange={(event) => {
                const nextGenre = event.target.value;
                setWritingGenre(nextGenre);
                setTargetLength((current) => {
                  if (current === "1200字" || current === "12行") {
                    return nextGenre === "诗歌" ? "12行" : "1200字";
                  }
                  return current;
                });
              }}
            >
              {GENRES.map((genre) => (
                <option key={genre} value={genre}>{genre}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>目标字数 / 篇幅</label>
            <input value={targetLength} onChange={(event) => setTargetLength(event.target.value)} placeholder="例如：800字、1200字、12行、3000字" />
            <small>生成时会把这个要求传给模型；诗歌可填“12行”，散文/小说/故事建议填“800字、1200字、3000字”。</small>
          </div>
          <div className="field">
            <label>风格贴近程度</label>
            <select value={styleIntensity} onChange={(event) => setStyleIntensity(event.target.value)}>
              <option value="light">轻度参考：只参考语气和节奏，表达更原创</option>
              <option value="balanced">平衡仿写：保留文风特征，避免像改写稿</option>
              <option value="close">高度贴近：更接近句法节奏，仅用于内部测试</option>
            </select>
            <small>默认建议使用“平衡仿写”。如果觉得太像原文，可以改成“轻度参考”。</small>
          </div>
          <div className="field">
            <label>标题 / 主题</label>
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>
          <div className="field">
            <label>写作要求</label>
            <textarea value={brief} onChange={(event) => setBrief(event.target.value)} />
          </div>
          <div className="field">
            <label>必须包含</label>
            <input value={mustInclude} onChange={(event) => setMustInclude(event.target.value)} />
          </div>
          <div className="field">
            <label>必须避免</label>
            <input value={mustAvoid} onChange={(event) => setMustAvoid(event.target.value)} />
          </div>
          <button className="primary" type="button" disabled={busy || !selectedStyleId} onClick={createWritingTask}>
            {busyAction === "writing" ? "正在生成文章……" : "按选定风格生成文章"}
          </button>
          {writingError ? <p className="inline-error" role="alert">{writingError}</p> : null}
          
          {!document ? (
            <div className="empty-preview">
              <strong>还没有生成文章</strong>
              <p>填写主题、字数和写作要求后，点击“按选定风格生成文章”。生成完成后，全文和段落修改入口会显示在这里。</p>
            </div>
          ) : (
            <article className="document-preview inline-document-editor">
              <div className="document-title">
                <strong>{document.title}</strong>
                <span>{document.genre} · 第 {generationCount} 版 · {document.paragraphs.length} 段 · 约 {document.content.length} 字 · {documentUpdatedAt} · ID {document.id.slice(-6)}</span>
              </div>
              {document.paragraphs.map((paragraph) => (
                <section
                  className={`readable-paragraph ${rewriteDialogParagraphId === paragraph.id ? "active" : ""}`}
                  key={paragraph.id}
                  onClick={() => openRewriteDialog(paragraph)}
                >
                  <button
                    className="paragraph-edit-button"
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      openRewriteDialog(paragraph);
                    }}
                  >
                    修改这一段
                  </button>
                  <p>{paragraph.content}</p>
                  <small>第 {paragraph.position} 段 · 重写 {paragraph.rewrite_count} 次</small>
                </section>
              ))}
            </article>
          )}
          {rewriteDialogParagraph ? (
            <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="rewrite-dialog-title">
              <div className="modal-card">
                <div className="modal-header">
                  <h3 id="rewrite-dialog-title">修改第 {rewriteDialogParagraph.position} 段</h3>
                  <button className="modal-close" type="button" disabled={busyAction === "rewrite"} onClick={closeRewriteDialog}>
                    ×
                  </button>
                </div>
                <div className="rewrite-preview">
                  <p>{rewriteDialogParagraph.content}</p>
                </div>
                <div className="field">
                  <label>修改意见</label>
                  <textarea
                    value={rewriteInstruction}
                    placeholder="例如：更克制一点，减少解释，保留画面感。"
                    onChange={(event) => {
                      setRewriteInstruction(event.target.value);
                      setRewriteError("");
                    }}
                  />
                </div>
                {rewriteError ? <p className="inline-error" role="alert">{rewriteError}</p> : null}
                <div className="modal-actions">
                  <button className="secondary" type="button" disabled={busyAction === "rewrite"} onClick={closeRewriteDialog}>
                    取消
                  </button>
                  <button className="primary" type="button" disabled={busy} onClick={rewriteParagraph}>
                    {busyAction === "rewrite" ? "正在重写……" : "重写这一段"}
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}

function summarizeStyleDraft(profile: Record<string, unknown> | undefined): StyleDraftView | null {
  if (!profile) {
    return null;
  }
  const shouldUseChineseOnly = asString(profile.source_language) !== "english";
  const report = asRecord(profile.display_report);
  const writingRules = asRecord(report.writing_rules_plain);
  let dimensions = asRecordList(report.dimensions).map((item) => ({
    key: asString(item.key) || asString(item.title),
    title: cleanDisplayText(asString(item.title), shouldUseChineseOnly),
    whatWeFound: asStringList(item.what_we_found).map((text) => cleanDisplayText(text, shouldUseChineseOnly)).filter(Boolean),
    whyItMatters: cleanDisplayText(asString(item.why_it_matters), shouldUseChineseOnly),
    editableSummary: cleanDisplayText(asString(item.editable_summary), shouldUseChineseOnly),
  })).filter((item) => item.title);
  if (dimensions.length === 0) {
    dimensions = buildFallbackDimensions(profile);
  }
  dimensions = dimensions.map((item) => ({
    ...item,
    title: cleanDisplayText(item.title, shouldUseChineseOnly),
    whatWeFound: item.whatWeFound.map((text) => cleanDisplayText(text, shouldUseChineseOnly)).filter(Boolean),
    whyItMatters: cleanDisplayText(item.whyItMatters, shouldUseChineseOnly),
    editableSummary: cleanDisplayText(item.editableSummary, shouldUseChineseOnly),
  }));
  const generationRules = asRecord(profile.generation_rules);
  const legacyImagery = asRecord(profile.imagery);
  const legacyPromptRules = asStringList(profile.prompt_rules);
  return {
    plainSummary: cleanDisplayText(asString(report.plain_summary) || asString(profile.summary) || "已生成结构化风格草案。", shouldUseChineseOnly),
    dimensions,
    mustDo: firstNonEmptyStringList(writingRules.must_do, generationRules.must_do, legacyPromptRules).slice(0, 5).map((text) => cleanDisplayText(text, shouldUseChineseOnly)).filter(Boolean),
    mustAvoid: firstNonEmptyStringList(writingRules.must_avoid, generationRules.must_avoid, legacyImagery.avoid).slice(0, 5).map((text) => cleanDisplayText(text, shouldUseChineseOnly)).filter(Boolean),
    evidence: firstNonEmptyStringList(report.evidence_plain, buildFallbackEvidence(profile)).slice(0, 6).map((text) => cleanDisplayText(text, shouldUseChineseOnly)).filter(Boolean),
  };
}

function buildFallbackDimensions(profile: Record<string, unknown>): StyleDraftView["dimensions"] {
  const voice = asRecord(profile.voice);
  const syntax = asRecord(profile.syntax);
  const imagery = asRecord(profile.imagery);
  const structure = asRecord(profile.structure);
  const sourceStats = asRecord(profile.source_stats);
  const lexical = asRecord(profile.lexical_style);
  const syntaxStyle = asRecord(profile.syntax_style);
  const rhetoric = asRecord(profile.rhetoric_style);
  const narrative = asRecord(profile.narrative_style);
  const tone = asRecord(profile.emotional_tone);
  const topic = asRecord(profile.topic_boundary);
  const language = asRecord(profile.language_period_style);
  return [
    {
      key: "lexical_syntax",
      title: "词汇和句子",
      whatWeFound: [
        textOrDefault(joinMaybe(lexical.noun_preference), "系统倾向认为作者更依赖具体名词和现场细节，而不是抽象概念。"),
        asString(syntaxStyle.sentence_length_pattern) || asStringList(syntax.sentence_patterns).join("；") || `平均自然段约 ${asStringOrNumber(syntax.avg_paragraph_chars) || asStringOrNumber(sourceStats.avg_paragraph_chars) || "未知"} 字。`,
        asString(syntaxStyle.paragraph_length_pattern) || "文章保留自然段节奏，不建议改成提纲式表达。",
      ],
      whyItMatters: "这决定了生成文章时用哪些词、句子长短怎么安排、读起来是否像原作者。",
      editableSummary: "如果你觉得作者其实更口语、更书面、更爱长句或更爱短句，可以直接修改完整 JSON。",
    },
    {
      key: "rhetoric_expression",
      title: "修辞和表达",
      whatWeFound: [
        textOrDefault(joinMaybe(rhetoric.imagery_sources), "系统目前主要从参考段落里提取意象，后续写作应学习意象类型，不复制原句。"),
        asString(rhetoric.metaphor_pattern) || "比喻和修辞应贴近原文的生活经验，不主动炫技。",
        textOrDefault(summarizeSensoryFocusFromClient(rhetoric.sensory_focus), "感官侧重暂未细分，建议用户确认视觉、听觉、气味等是否准确。"),
      ],
      whyItMatters: "这决定了仿写时是多写自然、旧物、市井、典故，还是多写抽象感受。",
      editableSummary: "如果系统误判了作者常用意象或比喻来源，可以直接修改完整 JSON。",
    },
    {
      key: "narrative_structure",
      title: "叙事和结构",
      whatWeFound: [
        asString(structure.opening) || joinMaybe(narrative.opening_patterns) || "常从具体物件、动作、声音或地点进入。",
        asString(structure.development) || joinMaybe(narrative.development_patterns) || "中间围绕细节推进，不急于解释主题。",
        asString(structure.ending) || joinMaybe(narrative.ending_patterns) || "结尾用场景、动作或物件收束，少做直白总结。",
      ],
      whyItMatters: "这决定了文章是先讲观点、先给画面，还是先进入人物和动作。",
      editableSummary: "如果原作者有固定起手式、转折方式或结尾方式，可以直接修改完整 JSON。",
    },
    {
      key: "emotion_tone",
      title: "情绪和基调",
      whatWeFound: [
        `整体语气：${joinMaybe(voice.tone) || asString(tone.emotion_intensity) || "克制、具体，保留作者自己的观察角度"}。`,
        `叙述距离：${asString(voice.narrative_distance) || asString(tone.restraint_level) || "贴近个人经验和现场细节"}。`,
        `核心母题：${joinMaybe(tone.core_motifs) || "时间、记忆、日常经验或现场观察"}。`,
      ],
      whyItMatters: "这决定了生成内容是热烈直白、冷静克制，还是带幽默、讽刺或伤感。",
      editableSummary: "如果你觉得作者情绪更强、更冷、更幽默或更尖锐，可以直接修改完整 JSON。",
    },
    {
      key: "topic_material",
      title: "题材和人物",
      whatWeFound: [
        `常见场景：${joinMaybe(topic.common_scenes) || "需要根据更多作品继续确认"}。`,
        `常见人物：${joinMaybe(topic.common_character_types) || "普通生活中的人、家人、路过者或观察对象"}。`,
        `适合题材：${joinMaybe(topic.suitable_topics) || joinMaybe(profile.applicable_genres) || "散文、随笔、生活观察"}。`,
      ],
      whyItMatters: "这决定了系统以后选择什么生活素材和人物类型来承载风格。",
      editableSummary: "如果作者更常写乡村、城市、家庭、历史或某类人物，可以直接修改完整 JSON。",
    },
    {
      key: "period_register",
      title: "时代和语体",
      whatWeFound: [
        `语言时代感：${asString(language.modernity) || "现代汉语书面语"}。`,
        `书面/口语特点：${joinMaybe(language.classical_or_colloquial_features) || "贴近日常表达，但不主动加入网络语"}。`,
        `方言或地域特征：${joinMaybe(language.dialect_or_regional_features) || "暂未发现明显方言特征"}。`,
      ],
      whyItMatters: "这决定了生成文章是现代白话、半文半白、口语化，还是带地域表达。",
      editableSummary: "如果作者有明显口头语、方言、年代感或文言残留，可以直接修改完整 JSON。",
    },
  ].map((item) => ({
    ...item,
    whatWeFound: item.whatWeFound.filter(Boolean),
  }));
}

function buildFallbackEvidence(profile: Record<string, unknown>): string[] {
  const evidence = asRecordList(profile.evidence_map).map((item) => {
    const title = asString(item.material_title) || "参考作品";
    const paragraphIndex = asStringOrNumber(item.paragraph_index) || "?";
    const claim = asString(item.claim) || "用于判断文章风格";
    return `${title} 第 ${paragraphIndex} 段：${claim}`;
  });
  if (evidence.length > 0) {
    return evidence;
  }
  return asStringList(profile.source_titles).map((title) => `${title}：用于提炼这份风格草案`);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function asRecordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object" && !Array.isArray(item)) : [];
}

function firstNonEmptyStringList(...values: unknown[]): string[] {
  for (const value of values) {
    const list = Array.isArray(value) ? asStringList(value) : typeof value === "string" ? [value] : [];
    if (list.length > 0) {
      return list;
    }
  }
  return [];
}

function joinMaybe(value: unknown): string {
  const list = asStringList(value);
  return list.length > 0 ? list.slice(0, 6).join("、") : "";
}

function textOrDefault(value: string, fallback: string): string {
  return value.trim() ? value : fallback;
}

function asStringOrNumber(value: unknown): string {
  return typeof value === "string" || typeof value === "number" ? String(value) : "";
}

function summarizeSensoryFocusFromClient(value: unknown): string {
  const focus = asRecord(value);
  const labels: Record<string, string> = {
    visual: "视觉",
    auditory: "听觉",
    smell: "嗅觉",
    touch: "触觉",
    taste: "味觉",
  };
  return Object.entries(focus)
    .filter(([, item]) => typeof item === "string" && item)
    .map(([key, item]) => `${labels[key] ?? key}：${item}`)
    .join("；");
}

function cleanDisplayText(value: string, shouldUseChineseOnly: boolean): string {
  if (!shouldUseChineseOnly) {
    return value;
  }
  return value
    .replace(/\bAI\b/g, "人工智能")
    .replace(/\bJSON\b/g, "数据")
    .replace(/\bStyle\s*Profile\b/g, "风格档案")
    .replace(/\([^()\u4e00-\u9fff]*[A-Za-z][^()\u4e00-\u9fff]*\)/g, "")
    .replace(/\b[A-Za-z][A-Za-z0-9_-]*\b/g, "")
    .replace(/\s*\/\s*/g, "、")
    .replace(/\s+/g, " ")
    .replace(/：\s*[。；，]/g, "：暂未判断。")
    .replace(/[（(]\s*[）)]/g, "")
    .trim();
}











