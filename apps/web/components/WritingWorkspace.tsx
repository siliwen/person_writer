"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type {
  ArticleEvaluation,
  BusyAction,
  CurrentUser,
  Material,
  ModelStatus,
  QuotaView,
  StyleJob,
  StyleProfile,
  ViewName,
  WritingDocument,
} from "@/lib/types";
import { EVALUATION_GENRES, SYSTEM_FREE_WRITE_STYLE_ID } from "@/lib/types";
import {
  apiBase,
  fetchDocumentEvaluation,
  fetchQuota,
  fetchUnreadCount,
  parseJson,
  requestDocumentEvaluation,
  reviseDocument,
} from "@/lib/api";
import { estimateArticlePoints, parseTargetLengthChars } from "@/lib/quota";
import { summarizeStyleDraft } from "@/lib/styleDraft";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { Sidebar } from "./Sidebar";
import { DashboardView } from "./DashboardView";
import type { FreeWritePayload } from "./FreeWriteBox";
import { FreeWritingDetailView } from "./FreeWritingDetailView";
import { StylesView } from "./StylesView";
import { NewStyleModal } from "./NewStyleModal";
import { EditStyleModal } from "./EditStyleModal";
import { WritingView, type WritingParams } from "./WritingView";
import { DocumentReader } from "./DocumentReader";
import { ArticlesView } from "./ArticlesView";
import { SettingsView } from "./SettingsView";
import { AdminPanel } from "./AdminPanel";
import { SiteFooter } from "./SiteFooter";
import { MessageCenter } from "./MessageCenter";
import { EvaluationPanel } from "./EvaluationPanel";

const viewTitles: Record<ViewName, { title: string; subtitle: string }> = {
  dashboard: { title: "工作台", subtitle: "" },
  styles: { title: "选择风格", subtitle: "选择一个风格开始写作，或创建新的风格档案" },
  writing: { title: "写作", subtitle: "按你的风格生成和修改文章" },
  "free-writing": { title: "自由写作", subtitle: "无风格创作，可继续提出修改要求" },
  reading: { title: "文章详情", subtitle: "查看和修改已保存的文章" },
  articles: { title: "文章库", subtitle: "查看和管理你保存的文章" },
  settings: { title: "设置", subtitle: "管理账号、安全和使用量" },
  admin: { title: "后台管理", subtitle: "会员、等级、积分与系统配置" },
};

export function WritingWorkspace() {
  return (
    <AuthProvider>
      <WorkspaceInner />
    </AuthProvider>
  );
}

function WorkspaceInner() {
  const { currentUser, setCurrentUser, requireAuth, openAuth, logout: authLogout } = useAuth();

  const [currentView, setCurrentView] = useState<ViewName>("dashboard");
  const [settingsInitialTab, setSettingsInitialTab] = useState<"profile" | "security" | "usage" | "privacy">("profile");
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [newStyleModalOpen, setNewStyleModalOpen] = useState(false);
  const [messageOpen, setMessageOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const [materials, setMaterials] = useState<Material[]>([]);
  const [styles, setStyles] = useState<StyleProfile[]>([]);
  const [selectedStyleId, setSelectedStyleId] = useState("");
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [quota, setQuota] = useState<QuotaView | null>(null);
  const [document, setDocument] = useState<WritingDocument | null>(null);
  const [generationCount, setGenerationCount] = useState(0);
  const [savedDocuments, setSavedDocuments] = useState<WritingDocument[]>([]);
  const [busyDocumentId, setBusyDocumentId] = useState<string | null>(null);

  // 文章鉴评（首版仅散文）
  const [evaluation, setEvaluation] = useState<ArticleEvaluation | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);
  const [evaluationError, setEvaluationError] = useState("");

  const [styleJob, setStyleJob] = useState<StyleJob | null>(null);
  const [styleName, setStyleName] = useState("我的散文风格");
  const [profileJson, setProfileJson] = useState("");
  const [confirmedStyleId, setConfirmedStyleId] = useState("");
  const [uploadGenre, setUploadGenre] = useState("散文");

  const [status, setStatus] = useState("选择一个风格开始写作，或点击右上角「新建风格」创建新的风格档案。");
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const [uploadError, setUploadError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [confirmError, setConfirmError] = useState("");
  const [writingError, setWritingError] = useState("");
  // 是否处于「自由写作（无风格）」模式：从首页 FreeWriteBox 生成进入写作视图时置 true。
  const [freeWriteMode, setFreeWriteMode] = useState(false);
  const [deleteStyleError, setDeleteStyleError] = useState("");

  // Edit style modal state
  const [editingStyle, setEditingStyle] = useState<StyleProfile | null>(null);
  const [editStyleName, setEditStyleName] = useState("");
  const [editProfileJson, setEditProfileJson] = useState("");
  const [editStyleError, setEditStyleError] = useState("");

  const styleDraftView = useMemo(
    () => summarizeStyleDraft(styleJob?.draft_profile),
    [styleJob]
  );

  // Track previous user ID to detect login/logout transitions
  const prevUserIdRef = useRef<string | null | undefined>(undefined);

  useEffect(() => {
    void refreshAll();
    void loadUnread();
  }, []);

  // React to auth state changes (login / logout)
  useEffect(() => {
    const userId = currentUser?.user_id ?? null;
    if (prevUserIdRef.current === userId) return;
    const prevId = prevUserIdRef.current;
    prevUserIdRef.current = userId;

    if (userId && !prevId) {
      // User logged in (or initial session found) — load user data
      setStatus(`已登录：${currentUser!.username}。可以继续使用工作台。`);
      void Promise.all([loadMaterials(), loadStyles(), loadSavedDocuments(), loadQuota()]);
      void loadUnread();
    } else if (!userId && prevId) {
      setUnreadCount(0);
      // User logged out — clear all user data
      setMaterials([]);
      setStyles([]);
      setSavedDocuments([]);
      setSelectedStyleId("");
      setDocument(null);
      setEvaluation(null);
      setGenerationCount(0);
      setQuota(null);
      setFreeWriteMode(false);
      setCurrentView("dashboard");
      setStatus("已退出登录。未登录可以预览工作台，创建资产需要重新登录。");
    }
  }, [currentUser]);

  async function loadQuota() {
    try {
      const q = await fetchQuota();
      setQuota(q);
    } catch {
      setQuota(null);
    }
  }

  async function loadUnread() {
    try {
      const res = await fetchUnreadCount();
      setUnreadCount(res.unread_count);
    } catch {
      setUnreadCount(0);
    }
  }

  async function refreshAll() {
    // Check if user has an existing session
    try {
      const response = await fetch(`${apiBase()}/v1/me`, { credentials: "include" });
      if (response.status !== 401) {
        const user = await parseJson<CurrentUser>(response);
        setCurrentUser(user);
      }
    } catch {
      // Not logged in
    }
    await Promise.all([loadModelStatus(), loadStyles()]);
  }

  async function loadSavedDocuments() {
    try {
      const response = await fetch(`${apiBase()}/v1/documents/saved`, { credentials: "include" });
      const body = await parseJson<{ documents: WritingDocument[] }>(response);
      setSavedDocuments(body.documents);
    } catch {
      setSavedDocuments([]);
    }
  }

  async function loadMaterials() {
    try {
      const response = await fetch(`${apiBase()}/v1/materials`, { credentials: "include" });
      const body = await parseJson<{ materials: Material[] }>(response);
      setMaterials(body.materials);
    } catch {
      setMaterials([]);
    }
  }

  async function loadModelStatus() {
    try {
      const response = await fetch(`${apiBase()}/v1/model-status`, { credentials: "include" });
      const body = await parseJson<ModelStatus>(response);
      setModelStatus(body);
    } catch {
      setModelStatus(null);
    }
  }

  async function loadStyles() {
    try {
      const response = await fetch(`${apiBase()}/v1/style-profiles`, { credentials: "include" });
      const body = await parseJson<{ styles: StyleProfile[] }>(response);
      setStyles(body.styles);
      setSelectedStyleId((current) => current || body.styles[0]?.id || "");
    } catch {
      setStyles([]);
    }
  }

  function handleOpenNewStyle() {
    setStyleJob(null);
    setConfirmedStyleId("");
    setStyleName("我的散文风格");
    setProfileJson("");
    setUploadError("");
    setAnalysisError("");
    setConfirmError("");
    setNewStyleModalOpen(true);
  }

  function handleOpenSettings(tab: "profile" | "security" | "usage" | "privacy") {
    setSettingsInitialTab(tab);
    setCurrentView("settings");
  }

  function handleOpenMessages() {
    void loadUnread();
    setMessageOpen(true);
  }

  function handleCloseNewStyle() {
    setNewStyleModalOpen(false);
  }

  function handleStartWriting(styleId: string) {
    setSelectedStyleId(styleId);
    setFreeWriteMode(false);
    setCurrentView("writing");
    // 从风格库（我的风格/推荐风格）进入写作页时，清空上次生成的文章，
    // 避免右侧仍显示旧文章内容。
    setDocument(null);
    setEvaluation(null);
    setGenerationCount(0);
    setWritingError("");
    setStatus("已选择风格，可以开始写作。");
  }

  async function handleUpload(files: FileList) {
    setUploadError("");
    setAnalysisError("");
    setConfirmError("");
    if (files.length === 0) {
      setUploadError("请选择要上传的 .txt/.md/.docx 文件。");
      return;
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
        credentials: "include",
        body: form,
      });
      const body = await parseJson<{ materials: Material[] }>(response);
      await loadMaterials();
      setStatus(`已上传 ${body.materials.length} 篇作品，正在分析风格……`);
      currentPhase = "analysis";
      setBusyAction("analysis");
      const analysisResponse = await fetch(`${apiBase()}/v1/style-analysis-jobs`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ material_ids: body.materials.map((item) => item.id) }),
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

  async function handleConfirmStyle() {
    setConfirmError("");
    if (!styleJob) {
      setConfirmError("还没有待确认的风格分析草案。");
      return;
    }
    const normalizedStyleName = styleName.trim();
    if (!normalizedStyleName) {
      setConfirmError("请填写风格名称。");
      return;
    }
    if (styles.some((style) => style.name.trim() === normalizedStyleName && style.id !== confirmedStyleId)) {
      setConfirmError("这个风格名称已经存在，请换一个名称。");
      return;
    }
    let profile: Record<string, unknown>;
    try {
      profile = JSON.parse(profileJson) as Record<string, unknown>;
    } catch {
      setConfirmError("风格数据格式错误，请修正后再确认。");
      return;
    }
    setBusyAction("confirm");
    setStatus("正在保存到个人风格库……");
    try {
      const response = await fetch(`${apiBase()}/v1/style-profiles/confirm`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: styleJob.id, name: normalizedStyleName, profile }),
      });
      const style = await parseJson<StyleProfile>(response);
      await loadStyles();
      setSelectedStyleId(style.id);
      setConfirmedStyleId(style.id);
      setStatus(`风格"${style.name}"已保存，可以用于写作。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const friendlyMessage = message.includes("风格名称已存在") ? "这个风格名称已经存在，请换一个名称。" : message;
      setConfirmError(friendlyMessage);
      setStatus(`保存风格失败：${friendlyMessage}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function handleDeleteStyle(styleId: string) {
    setDeleteStyleError("");
    const styleToDelete = styles.find((s) => s.id === styleId);
    if (!styleToDelete) return;
    const shouldDelete = window.confirm(`确认删除风格"${styleToDelete.name}"吗？删除后它不会再出现在风格列表里，已生成文章不受影响。`);
    if (!shouldDelete) return;
    setBusyAction("delete_style");
    setStatus(`正在删除风格"${styleToDelete.name}"……`);
    try {
      const response = await fetch(`${apiBase()}/v1/style-profiles/${styleToDelete.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      await parseJson<{ id: string; status: string }>(response);
      const nextStyles = styles.filter((s) => s.id !== styleToDelete.id);
      setStyles(nextStyles);
      if (selectedStyleId === styleToDelete.id) {
        setSelectedStyleId(nextStyles[0]?.id ?? "");
      }
      if (confirmedStyleId === styleToDelete.id) {
        setConfirmedStyleId("");
      }
      if (nextStyles.length === 0) {
        setDocument(null);
        setEvaluation(null);
        setGenerationCount(0);
      }
      setStatus(`风格"${styleToDelete.name}"已删除。`);
      await loadStyles();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setDeleteStyleError(message);
      setStatus(`删除风格失败：${message}`);
    } finally {
      setBusyAction(null);
    }
  }

  function handleOpenEditStyle(styleId: string) {
    const style = styles.find((s) => s.id === styleId);
    if (!style) return;
    setEditingStyle(style);
    setEditStyleName(style.name);
    setEditProfileJson(JSON.stringify(style.profile, null, 2));
    setEditStyleError("");
  }

  function handleCloseEditStyle() {
    setEditingStyle(null);
    setEditStyleName("");
    setEditProfileJson("");
    setEditStyleError("");
  }

  async function handleSaveEditStyle() {
    if (!editingStyle) return;
    if (!editStyleName.trim()) {
      setEditStyleError("请填写风格名称。");
      return;
    }
    let parsedProfile: Record<string, unknown> | undefined;
    if (editProfileJson.trim()) {
      try {
        parsedProfile = JSON.parse(editProfileJson) as Record<string, unknown>;
      } catch {
        setEditStyleError("风格档案 JSON 格式不正确，请检查后重试。");
        return;
      }
    }
    setBusyAction("edit_style");
    setEditStyleError("");
    setStatus(`正在保存风格"${editStyleName}"的修改……`);
    try {
      const response = await fetch(`${apiBase()}/v1/style-profiles/${editingStyle.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: editStyleName.trim(),
          profile: parsedProfile,
        }),
      });
      await parseJson<{ id: string }>(response);
      setStatus(`风格"${editStyleName}"已更新。`);
      handleCloseEditStyle();
      await loadStyles();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const friendlyMessage = message.includes("风格名称已存在") ? "这个风格名称已经存在，请换一个名称。" : message;
      setEditStyleError(friendlyMessage);
      setStatus(`更新风格失败：${friendlyMessage}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSetDefaultStyle(styleId: string) {
    const style = styles.find((s) => s.id === styleId);
    if (!style) return;
    setBusyAction("set_default");
    setStatus(`正在将"${style.name}"设为默认风格……`);
    try {
      const response = await fetch(`${apiBase()}/v1/style-profiles/${styleId}/set-default`, {
        method: "POST",
        credentials: "include",
      });
      await parseJson<{ id: string }>(response);
      setStatus(`已将"${style.name}"设为默认风格。`);
      await loadStyles();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`设置默认风格失败：${message}`);
    } finally {
      setBusyAction(null);
    }
  }

  /** 拉取指定文档的最新鉴评报告；非散文直接清空，不打接口。 */
  async function loadEvaluation(doc: WritingDocument | null) {
    setEvaluationError("");
    if (!doc || !EVALUATION_GENRES.includes(doc.genre)) {
      setEvaluation(null);
      return;
    }
    try {
      const report = await fetchDocumentEvaluation(doc.id);
      setEvaluation(report);
    } catch {
      // 报告拉取失败不打断主流程，用户可手动点「开始鉴评」
      setEvaluation(null);
    }
  }

  /** 手动触发或重新触发鉴评。 */
  async function handleEvaluate() {
    if (!requireAuth()) return;
    if (!document) return;
    setEvaluationLoading(true);
    setEvaluationError("");
    try {
      const report = await requestDocumentEvaluation(document.id);
      setEvaluation(report);
      setStatus(`鉴评完成：${report.grade} 级（${report.overall_score.toFixed(1)} 分）。`);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setEvaluationError(`鉴评失败：${message}`);
    } finally {
      setEvaluationLoading(false);
    }
  }

  async function handleGenerate(params: WritingParams) {
    setWritingError("");
    if (!params.title) {
      setWritingError("请填写标题或主题。");
      return;
    }
    if (!params.brief) {
      setWritingError("请填写写作要求。");
      return;
    }
    if (!params.targetLength) {
      setWritingError("请填写目标字数或篇幅。");
      return;
    }
    // 生成前预校验：等级长度上限与积分余额（后端会再次校验，这里提供即时反馈）
    if (quota) {
      const chars = parseTargetLengthChars(params.targetLength);
      const tier = quota.tier;
      if (tier.max_article_length && tier.max_article_length > 0 && chars > tier.max_article_length) {
        setWritingError(`当前等级单篇文章最大长度为 ${tier.max_article_length} 字，请缩短或升级会员。`);
        return;
      }
      const estimated = estimateArticlePoints(chars, quota.article_length_brackets);
      if (quota.points_balance < estimated) {
        setWritingError(
          `积分不足，本次生成预计需要 ${estimated} 积分，当前剩余 ${quota.points_balance} 积分。可在「设置 → 用量与额度」查看或升级会员。`
        );
        return;
      }
    }
    setBusyAction("writing");
    const nextGenerationCount = generationCount + 1;
    setStatus(`正在按选定风格生成第 ${nextGenerationCount} 版文章……`);
    try {
      const response = await fetch(`${apiBase()}/v1/writing-tasks`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          style_profile_id: params.styleProfileId,
          requested_mode: "style_prompt_only",
          task: {
            genre: params.genre,
            task_type: "新写",
            title: params.title,
            brief: params.brief,
            target_length: params.targetLength,
            target_reader: "普通读者",
            must_include: params.mustInclude,
            must_avoid: params.mustAvoid,
            eval_focus: "风格贴近但表达原创、任务完成度、自然段可编辑性",
            style_intensity: params.styleIntensity,
          },
        }),
      });
      const body = await parseJson<{ document: WritingDocument; evaluation?: { grade: string } | null }>(response);
      setDocument(body.document);
      setGenerationCount(nextGenerationCount);
      setStatus(
        body.evaluation
          ? `第 ${nextGenerationCount} 版文章已生成，鉴评 ${body.evaluation.grade} 级。点击正文里的自然段即可提交修改意见。`
          : `第 ${nextGenerationCount} 版文章已生成。点击正文里的自然段即可提交修改意见。`
      );
      void loadQuota();
      void loadUnread();
      // 散文生成后端已自动鉴评，这里直接拉取报告；其他文体不请求。
      void loadEvaluation(body.document);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setWritingError(`本次生成失败。原因：${message}`);
      setStatus(`生成失败：${message}`);
    } finally {
      setBusyAction(null);
    }
  }

  async function handleFreeWrite(payload: FreeWritePayload) {
    setWritingError("");
    if (!payload.brief) {
      setWritingError("请填写写作需求。");
      return;
    }
    // 生成前预校验：等级长度上限与积分余额（后端会再次校验，这里提供即时反馈）
    if (quota) {
      const isFreeWrite = payload.styleProfileId === "";
      const chars = isFreeWrite ? 1200 : parseTargetLengthChars(payload.targetLength);
      const tier = quota.tier;
      if (tier.max_article_length && tier.max_article_length > 0 && chars > tier.max_article_length) {
        setWritingError(`当前等级单篇文章最大长度为 ${tier.max_article_length} 字，请缩短或升级会员。`);
        return;
      }
      const estimated = estimateArticlePoints(chars, quota.article_length_brackets);
      if (quota.points_balance < estimated) {
        setWritingError(
          `积分不足，本次生成预计需要 ${estimated} 积分，当前剩余 ${quota.points_balance} 积分。可在「设置 → 用量与额度」查看或升级会员。`
        );
        return;
      }
    }
    const isFree = payload.styleProfileId === "";
    // 开始新的自由写作时清空上次的文章/鉴评/状态，避免进入详情页仍显示旧文章
    if (isFree) {
      setDocument(null);
      setEvaluation(null);
      setStatus("");
    }
    setBusyAction("writing");
    setFreeWriteMode(isFree);
    setSelectedStyleId(payload.styleProfileId); // 自由写作为空
    // 自由写作进入独立的无风格详情页（无逐段编辑、底部悬浮修改框）；风格写作仍走 writing 视图
    setCurrentView(isFree ? "free-writing" : "writing");
    const nextGenerationCount = generationCount + 1;
    setStatus(`正在${isFree ? "按自由写作" : "按选定风格"}生成第 ${nextGenerationCount} 版文章……`);
    try {
      const response = await fetch(`${apiBase()}/v1/writing-tasks`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          style_profile_id: payload.styleProfileId,
          requested_mode: "style_prompt_only",
          task: {
            genre: payload.genre,
            task_type: "新写",
            title: payload.title,
            brief: payload.brief,
            target_length: payload.targetLength,
            target_reader: "普通读者",
            must_include: "",
            must_avoid: "",
            eval_focus: "任务完成度、自然段可编辑性",
            style_intensity: "balanced",
          },
        }),
      });
      const body = await parseJson<{ document: WritingDocument; evaluation?: { grade: string } | null }>(response);
      setDocument(body.document);
      setGenerationCount(nextGenerationCount);
      setStatus(
        isFree
          ? `第 ${nextGenerationCount} 版文章已生成。请在下方输入修改意见，继续优化文章。`
          : `第 ${nextGenerationCount} 版文章已生成。点击正文里的自然段即可提交修改意见。`
      );
      void loadQuota();
      void loadUnread();
      // 自由写作文章不鉴评，跳过拉取报告
      if (!isFree) void loadEvaluation(body.document);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setWritingError(`本次生成失败。原因：${message}`);
      setStatus(`生成失败：${message}`);
      setFreeWriteMode(false);
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSaveDocument(): Promise<void> {
    if (!document) {
      throw new Error("当前没有可保存的文章");
    }
    const response = await fetch(`${apiBase()}/v1/documents/${document.id}/save`, {
      method: "POST",
      credentials: "include",
    });
    const updated = await parseJson<WritingDocument>(response);
    setDocument(updated);
    await loadSavedDocuments();
  }

  async function handleDownloadDocument(targetDocument?: WritingDocument): Promise<void> {
    const doc = targetDocument || document;
    if (!doc) {
      throw new Error("当前没有可下载的文章");
    }
    setBusyDocumentId(doc.id);
    try {
      const response = await fetch(`${apiBase()}/v1/documents/${doc.id}/download/docx`, {
        credentials: "include",
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? body.message ?? `HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const filename = `${doc.title}.docx`.replace(/\s+/g, "_");
      const url = window.URL.createObjectURL(blob);
      const link = getDownloadAnchor();
      if (!link) return;
      link.href = url;
      link.download = filename;
      link.click();
      window.URL.revokeObjectURL(url);
    } finally {
      setBusyDocumentId(null);
    }
  }

  function getDownloadAnchor(): HTMLAnchorElement | null {
    if (typeof window === "undefined" || !window.document) return null;
    let link = window.document.getElementById("download-docx-anchor") as HTMLAnchorElement | null;
    if (!link) {
      link = window.document.createElement("a");
      link.id = "download-docx-anchor";
      link.style.display = "none";
      window.document.body.appendChild(link);
    }
    return link;
  }

  function handleOpenDocument(targetDocument: WritingDocument) {
    setDocument(targetDocument);
    setGenerationCount(1);
    // 自由写作（无风格）文档也进入独立的无风格详情页（无逐段编辑）
    if (targetDocument.style_profile_id === SYSTEM_FREE_WRITE_STYLE_ID) {
      setFreeWriteMode(true);
      setCurrentView("free-writing");
    } else {
      setCurrentView("reading");
    }
    setStatus(`已打开文章「${targetDocument.title}」。可继续修改或下载。`);
    void loadEvaluation(targetDocument);
  }

  /** 自由写作详情页：按用户修改意见重生成并覆盖当前文档。 */
  async function handleReviseDocument(instruction: string): Promise<void> {
    if (!requireAuth()) return;
    if (!document) {
      throw new Error("当前没有可修改的文章");
    }
    setWritingError("");
    setBusyAction("writing");
    const nextGenerationCount = generationCount + 1;
    setStatus(`正在根据修改意见重新生成第 ${nextGenerationCount} 版文章……`);
    try {
      const updated = await reviseDocument(document.id, instruction);
      setDocument(updated);
      setGenerationCount(nextGenerationCount);
      setStatus(`第 ${nextGenerationCount} 版文章已生成，已覆盖上一版。`);
      void loadQuota();
      void loadUnread();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setWritingError(`修改失败：${message}`);
      setStatus(`修改失败：${message}`);
      throw error;
    } finally {
      setBusyAction(null);
    }
  }

  async function handleUnsaveDocument(documentId: string): Promise<void> {
    setBusyDocumentId(documentId);
    try {
      const response = await fetch(`${apiBase()}/v1/documents/${documentId}/unsave`, {
        method: "POST",
        credentials: "include",
      });
      await parseJson<WritingDocument>(response);
      if (document?.id === documentId) {
        setDocument((current) => (current ? { ...current, is_saved: false, saved_at: null } : current));
      }
      await loadSavedDocuments();
      setStatus("文章已从个人库移除");
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function handleRewrite(paragraphId: string, instruction: string): Promise<string> {
    if (!document) {
      throw new Error("文档不存在");
    }
    setBusyAction("rewrite");
    setStatus("正在重写指定自然段……");
    try {
      const response = await fetch(
        `${apiBase()}/v1/documents/${document.id}/paragraphs/${paragraphId}/rewrite`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ instruction }),
        }
      );
      const body = await parseJson<{ rewritten_content: string }>(response);
      setStatus("AI 重写完成，请在弹窗中查看结果。");
      void loadQuota();
      return body.rewritten_content;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`段落重写失败：${message}`);
      throw error;
    } finally {
      setBusyAction(null);
    }
  }

  async function handleOverwriteParagraph(paragraphId: string, newContent: string): Promise<void> {
    if (!document) {
      throw new Error("文档不存在");
    }
    setBusyAction("rewrite");
    setStatus("正在保存修改……");
    try {
      const response = await fetch(
        `${apiBase()}/v1/documents/${document.id}/paragraphs/${paragraphId}`,
        {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: newContent }),
        }
      );
      const updated = await parseJson<WritingDocument>(response);
      setDocument(updated);
      setStatus("段落已更新。");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(`段落保存失败：${message}`);
      throw error;
    } finally {
      setBusyAction(null);
    }
  }

  async function handleLogout() {
    setBusyAction("confirm");
    try {
      await authLogout();
    } finally {
      setBusyAction(null);
    }
  }

  async function handleSendPhoneCode(phone: string): Promise<string> {
    const response = await fetch(`${apiBase()}/v1/account/phone/send-code`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: phone }),
    });
    const body = await parseJson<{ debug_code: string }>(response);
    return body.debug_code;
  }

  async function handleBindPhone(phone: string, code: string): Promise<CurrentUser> {
    const response = await fetch(`${apiBase()}/v1/account/phone/bind`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: phone, code }),
    });
    const body = await parseJson<{ user: CurrentUser }>(response);
    setCurrentUser(body.user);
    return body.user;
  }

  async function handleSendEmailCode(email: string): Promise<string> {
    const response = await fetch(`${apiBase()}/v1/account/email/send-code`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const body = await parseJson<{ debug_code: string }>(response);
    return body.debug_code;
  }

  async function handleBindEmail(email: string, code: string): Promise<CurrentUser> {
    const response = await fetch(`${apiBase()}/v1/account/email/bind`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code }),
    });
    const body = await parseJson<{ user: CurrentUser }>(response);
    setCurrentUser(body.user);
    return body.user;
  }

  async function handleChangePassword(
    oldPassword: string,
    newPassword: string,
    confirmPassword: string
  ): Promise<void> {
    const response = await fetch(`${apiBase()}/v1/account/password/change`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    });
    await parseJson<{ user: CurrentUser }>(response);
  }

  function handleSelectStyleFromWriting(styleId: string) {
    setSelectedStyleId(styleId);
    if (styleId) setFreeWriteMode(false);
  }

  function handleNavigate(view: ViewName) {
    setCurrentView(view);
    // 离开写作 / 自由写作视图时退出自由写作模式，并清空临时文章状态，避免回到首页后仍显示旧文章
    if (view !== "writing" && view !== "free-writing") {
      if (freeWriteMode) {
        setDocument(null);
        setGenerationCount(0);
        setEvaluation(null);
        setStatus("");
      }
      setFreeWriteMode(false);
    }
  }

  const viewMeta = viewTitles[currentView];

  return (
    <div className="app-shell">
      <Sidebar currentView={currentView} onNavigate={handleNavigate} isAdmin={currentUser?.is_admin} />
      <div className="main-area">
        <div className="topbar">
          <div className="topbar-left">
            <span className="topbar-title">{viewMeta.title}</span>
            {viewMeta.subtitle ? <span className="topbar-subtitle">{viewMeta.subtitle}</span> : null}
          </div>
          <div className="topbar-right">
            {currentUser ? (
              <>
                <button
                  className="topbar-capsule"
                  type="button"
                  onClick={() => handleOpenSettings("usage")}
                  title="查看用量与额度"
                >
                  <span className="topbar-capsule-main">
                    <span className="topbar-capsule-icon">⚡</span>
                    <span
                      className={`topbar-capsule-points ${
                        (quota?.points_balance ?? currentUser.points_balance) <= 0 ? "zero" : ""
                      }`}
                    >
                      {quota?.points_balance ?? currentUser.points_balance}
                    </span>
                    <span className="topbar-capsule-unit">积分</span>
                  </span>
                  <span className="topbar-capsule-divider" />
                  <span className="topbar-capsule-tier">
                    {quota?.tier.name ?? currentUser.tier_code ?? "免费版"}
                  </span>
                </button>
                <button
                  className="topbar-bell"
                  type="button"
                  onClick={handleOpenMessages}
                  aria-label="消息"
                  title="消息中心"
                >
                  <span className="topbar-bell-icon">🔔</span>
                  {unreadCount > 0 ? (
                    <span className="topbar-bell-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
                  ) : null}
                </button>
                <div className="topbar-user-menu">
                  <button
                    className="topbar-user-trigger"
                    type="button"
                    onClick={() => setUserMenuOpen((o) => !o)}
                    title="账户菜单"
                    aria-haspopup="true"
                    aria-expanded={userMenuOpen}
                  >
                    <span className="topbar-avatar">
                      {currentUser.username?.charAt(0)?.toUpperCase() ?? "U"}
                    </span>
                    <span className="topbar-username">{currentUser.username}</span>
                    <span className="topbar-chevron">▼</span>
                  </button>

                  {userMenuOpen ? (
                    <>
                      <div className="topbar-menu-overlay" onClick={() => setUserMenuOpen(false)} />
                      <div className="topbar-dropdown" role="menu">
                        <button
                          type="button"
                          className="topbar-dropdown-item"
                          onClick={() => {
                            setUserMenuOpen(false);
                            handleOpenSettings("profile");
                          }}
                        >
                          个人资料
                        </button>
                        <button
                          type="button"
                          className="topbar-dropdown-item"
                          onClick={() => {
                            setUserMenuOpen(false);
                            handleOpenSettings("usage");
                          }}
                        >
                          用量与额度
                        </button>
                        <button
                          type="button"
                          className="topbar-dropdown-item danger"
                          onClick={() => {
                            const confirmed = window.confirm("确认退出登录？");
                            if (!confirmed) return;
                            setUserMenuOpen(false);
                            handleLogout();
                          }}
                        >
                          退出登录
                        </button>
                      </div>
                    </>
                  ) : null}
                </div>
              </>
            ) : (
              <button
                className="btn btn-primary btn-sm"
                type="button"
                onClick={() => openAuth("login")}
              >
                登录 / 注册
              </button>
            )}
          </div>
        </div>

        <div
          className={`content-area ${currentView === "writing" || currentView === "reading" ? "wide-content" : ""} ${currentView === "free-writing" ? "no-scroll" : ""}`}
        >
          {currentView === "dashboard" ? (
            <DashboardView
              currentUser={currentUser}
              materials={materials}
              styles={styles}
              savedDocuments={savedDocuments}
              generationCount={generationCount}
              quota={quota}
              generating={busyAction === "writing"}
              onNavigate={handleNavigate}
              onOpenDocument={handleOpenDocument}
              onFreeWrite={handleFreeWrite}
            />
          ) : null}

          {currentView === "styles" ? (
            <StylesView
              styles={styles}
              selectedStyleId={selectedStyleId}
              busyAction={busyAction}
              deleteStyleError={deleteStyleError}
              onStartWriting={handleStartWriting}
              onDeleteStyle={handleDeleteStyle}
              onEditStyle={handleOpenEditStyle}
              onSetDefaultStyle={handleSetDefaultStyle}
              onNewStyle={handleOpenNewStyle}
            />
          ) : null}

          {currentView === "writing" ? (
            <WritingView
              styles={styles}
              selectedStyleId={selectedStyleId}
              quota={quota}
              freeWriteMode={freeWriteMode}
              onSelectStyle={handleSelectStyleFromWriting}
              document={document}
              generationCount={generationCount}
              busyAction={busyAction}
              writingError={writingError}
              onGenerate={handleGenerate}
              onRewrite={handleRewrite}
              onOverwriteParagraph={handleOverwriteParagraph}
              onSaveDocument={handleSaveDocument}
              onDownloadDocument={() => handleDownloadDocument()}
              evaluation={evaluation}
              evaluationLoading={evaluationLoading}
              evaluationError={evaluationError}
              onEvaluate={handleEvaluate}
            />
          ) : null}

          {currentView === "free-writing" ? (
            <FreeWritingDetailView
              document={document}
              generationCount={generationCount}
              busyAction={busyAction}
              quota={quota}
              onRevise={handleReviseDocument}
              onSaveDocument={handleSaveDocument}
              onDownloadDocument={() => handleDownloadDocument()}
              onBack={() => handleNavigate("dashboard")}
            />
          ) : null}

          {currentView === "reading" ? (
            document ? (
              <>
                <DocumentReader
                  document={document}
                  generationCount={generationCount}
                  busyAction={busyAction}
                  canDownload={quota ? quota.tier.can_download : true}
                  canRewrite={quota ? quota.tier.can_rewrite : true}
                  onRewrite={handleRewrite}
                  onOverwriteParagraph={handleOverwriteParagraph}
                  onDownloadDocument={() => handleDownloadDocument()}
                  showSaveButton={false}
                  showBackButton
                  onBack={() => setCurrentView("articles")}
                  paragraphRewritePoints={quota ? quota.operation_points.paragraph_rewrite : null}
                />
                <EvaluationPanel
                  evaluation={evaluation}
                  loading={evaluationLoading}
                  error={evaluationError}
                  supported={EVALUATION_GENRES.includes(document.genre)}
                  genre={document.genre}
                  onEvaluate={handleEvaluate}
                />
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-state-title">没有选中的文章</div>
                <div className="empty-state-desc">请从文章库中选择一篇文章打开。</div>
              </div>
            )
          ) : null}

          {currentView === "articles" ? (
            <ArticlesView
              documents={savedDocuments}
              busyDocumentId={busyDocumentId}
              onOpenDocument={handleOpenDocument}
              onDownloadDocument={handleDownloadDocument}
              onUnsaveDocument={handleUnsaveDocument}
              onNavigate={handleNavigate}
            />
          ) : null}

          {currentView === "settings" ? (
            <SettingsView
              currentUser={currentUser}
              quota={quota}
              materials={materials}
              styles={styles}
              generationCount={generationCount}
              busyAction={busyAction}
              initialTab={settingsInitialTab}
              onSendPhoneCode={handleSendPhoneCode}
              onBindPhone={handleBindPhone}
              onSendEmailCode={handleSendEmailCode}
              onBindEmail={handleBindEmail}
              onChangePassword={handleChangePassword}
              onLogout={handleLogout}
            />
          ) : null}

          {currentView === "admin" ? <AdminPanel onNewStyle={handleOpenNewStyle} /> : null}
        </div>

        <SiteFooter />
      </div>

      {newStyleModalOpen ? (
        <NewStyleModal
          styleJob={styleJob}
          styleDraftView={styleDraftView}
          styleName={styleName}
          profileJson={profileJson}
          confirmedStyleId={confirmedStyleId}
          uploadGenre={uploadGenre}
          busyAction={busyAction}
          uploadError={uploadError}
          analysisError={analysisError}
          confirmError={confirmError}
          onUploadGenreChange={setUploadGenre}
          onStyleNameChange={setStyleName}
          onProfileJsonChange={setProfileJson}
          onUpload={handleUpload}
          onConfirm={handleConfirmStyle}
          onClose={handleCloseNewStyle}
          styleAnalysisPoints={quota ? quota.operation_points.style_analysis : null}
        />
      ) : null}

      {editingStyle ? (
        <EditStyleModal
          style={editingStyle}
          styleName={editStyleName}
          profileJson={editProfileJson}
          busyAction={busyAction}
          editError={editStyleError}
          onNameChange={setEditStyleName}
          onProfileJsonChange={setEditProfileJson}
          onSave={handleSaveEditStyle}
          onClose={handleCloseEditStyle}
        />
      ) : null}

      {messageOpen ? (
        <MessageCenter onClose={() => setMessageOpen(false)} onUnreadChange={setUnreadCount} />
      ) : null}
    </div>
  );
}
