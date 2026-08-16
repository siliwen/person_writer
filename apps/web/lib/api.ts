export function apiBase() {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8010`;
  }
  return "http://127.0.0.1:8010";
}

export async function parseJson<T>(response: Response): Promise<T> {
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail ?? body.message ?? `HTTP ${response.status}`);
  }
  return body as T;
}

export async function fetchQuota(): Promise<import("./types").QuotaView> {
  const response = await fetch(`${apiBase()}/v1/account/quota`, { credentials: "include" });
  return parseJson<import("./types").QuotaView>(response);
}

export async function fetchUsage(page = 1, pageSize = 20): Promise<import("./types").UsagePage> {
  const response = await fetch(`${apiBase()}/v1/account/usage?page=${page}&page_size=${pageSize}`, {
    credentials: "include",
  });
  return parseJson<import("./types").UsagePage>(response);
}

// ---------- 文章鉴评 ----------

/** 取某篇文档最新鉴评报告；未鉴评过返回 null（404 视为无报告，不抛错）。 */
export async function fetchDocumentEvaluation(
  documentId: string
): Promise<import("./types").ArticleEvaluation | null> {
  const response = await fetch(`${apiBase()}/v1/documents/${documentId}/evaluation`, {
    credentials: "include",
  });
  if (response.status === 404) return null;
  return parseJson<import("./types").ArticleEvaluation>(response);
}

/** 手动触发（或重新触发）鉴评。 */
export async function requestDocumentEvaluation(
  documentId: string
): Promise<import("./types").ArticleEvaluation> {
  const response = await fetch(`${apiBase()}/v1/documents/${documentId}/evaluate`, {
    method: "POST",
    credentials: "include",
  });
  return parseJson<import("./types").ArticleEvaluation>(response);
}

// ---------- 管理后台 API（require_admin） ----------

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}/v1/admin${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  return parseJson<T>(response);
}

export function fetchAdminMetrics(): Promise<import("./types").AdminMetrics> {
  return adminFetch<import("./types").AdminMetrics>("/metrics/overview");
}

export function fetchAdminUsers(params: { page?: number; page_size?: number; q?: string; tier?: string } = {}): Promise<{
  total: number;
  page: number;
  page_size: number;
  items: import("./types").AdminUser[];
}> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.q) qs.set("q", params.q);
  if (params.tier) qs.set("tier", params.tier);
  return adminFetch(`/users?${qs.toString()}`);
}

export function adjustAdminUserPoints(userId: string, delta: number, reason: string): Promise<import("./types").AdminUser> {
  return adminFetch<import("./types").AdminUser>(`/users/${userId}/points`, {
    method: "POST",
    body: JSON.stringify({ delta, reason: reason || null }),
  });
}

export function setAdminUserTier(
  userId: string,
  tierCode: string,
  grantMonthlyPoints: boolean,
  reason: string
): Promise<import("./types").AdminUser> {
  return adminFetch<import("./types").AdminUser>(`/users/${userId}/set-tier`, {
    method: "POST",
    body: JSON.stringify({ tier_code: tierCode, grant_monthly_points: grantMonthlyPoints, reason: reason || null }),
  });
}

export function fetchAdminTiers(): Promise<{ items: import("./types").AdminTier[] }> {
  return adminFetch("/tiers");
}
export function createAdminTier(payload: import("./types").AdminTier): Promise<import("./types").AdminTier> {
  return adminFetch("/tiers", { method: "POST", body: JSON.stringify(payload) });
}
export function updateAdminTier(code: string, payload: import("./types").AdminTier): Promise<import("./types").AdminTier> {
  return adminFetch(`/tiers/${code}`, { method: "PATCH", body: JSON.stringify(payload) });
}
export function deleteAdminTier(code: string): Promise<{ status: string }> {
  return adminFetch(`/tiers/${code}`, { method: "DELETE" });
}

export function fetchAdminBrackets(): Promise<{ items: import("./types").AdminBracket[] }> {
  return adminFetch("/article-length-brackets");
}
export function createAdminBracket(payload: import("./types").AdminBracket): Promise<import("./types").AdminBracket> {
  return adminFetch("/article-length-brackets", { method: "POST", body: JSON.stringify(payload) });
}
export function updateAdminBracket(id: string, payload: import("./types").AdminBracket): Promise<import("./types").AdminBracket> {
  return adminFetch(`/article-length-brackets/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}
export function deleteAdminBracket(id: string): Promise<{ status: string }> {
  return adminFetch(`/article-length-brackets/${id}`, { method: "DELETE" });
}

export function fetchAdminOperationCosts(): Promise<{ items: import("./types").AdminOperationCost[] }> {
  return adminFetch("/operation-costs");
}
export function createAdminOperationCost(payload: import("./types").AdminOperationCost): Promise<import("./types").AdminOperationCost> {
  return adminFetch("/operation-costs", { method: "POST", body: JSON.stringify(payload) });
}
export function updateAdminOperationCost(id: string, payload: import("./types").AdminOperationCost): Promise<import("./types").AdminOperationCost> {
  return adminFetch(`/operation-costs/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}
export function deleteAdminOperationCost(id: string): Promise<{ status: string }> {
  return adminFetch(`/operation-costs/${id}`, { method: "DELETE" });
}

export function fetchAdminModelPricing(): Promise<{ items: import("./types").AdminModelPricing[] }> {
  return adminFetch("/model-pricing");
}
export function createAdminModelPricing(payload: import("./types").AdminModelPricing): Promise<import("./types").AdminModelPricing> {
  return adminFetch("/model-pricing", { method: "POST", body: JSON.stringify(payload) });
}
export function updateAdminModelPricing(id: string, payload: import("./types").AdminModelPricing): Promise<import("./types").AdminModelPricing> {
  return adminFetch(`/model-pricing/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}
export function deleteAdminModelPricing(id: string): Promise<{ status: string }> {
  return adminFetch(`/model-pricing/${id}`, { method: "DELETE" });
}

export function fetchAdminUsage(params: { page?: number; page_size?: number; user_id?: string; op_type?: string } = {}): Promise<import("./types").AdminUsagePage> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.user_id) qs.set("user_id", params.user_id);
  if (params.op_type) qs.set("op_type", params.op_type);
  return adminFetch<import("./types").AdminUsagePage>(`/usage?${qs.toString()}`);
}

export function fetchAdminAuditLogs(params: { page?: number; page_size?: number; target_type?: string } = {}): Promise<{
  total: number;
  page: number;
  page_size: number;
  items: import("./types").AuditLogEntry[];
}> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.target_type) qs.set("target_type", params.target_type);
  return adminFetch(`/audit-logs?${qs.toString()}`);
}

export function fetchAdminStyles(params: { recommended_only?: boolean } = {}): Promise<{ items: import("./types").AdminStyle[] }> {
  const qs = new URLSearchParams();
  if (params.recommended_only) qs.set("recommended_only", "true");
  return adminFetch(`/style-profiles?${qs.toString()}`);
}

export function setAdminStyleRecommended(styleId: string, isRecommended: boolean): Promise<import("./types").AdminStyle> {
  return adminFetch<import("./types").AdminStyle>(`/style-profiles/${styleId}/recommend`, {
    method: "PATCH",
    body: JSON.stringify({ is_recommended: isRecommended }),
  });
}

export async function updateStyleProfile(
  styleId: string,
  payload: { name: string; description?: string | null }
): Promise<import("./types").StyleProfile> {
  const response = await fetch(`${apiBase()}/v1/style-profiles/${styleId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJson<import("./types").StyleProfile>(response);
}

// ---------- 消息中心：管理后台 ----------

export function fetchAdminMessages(params: { page?: number; page_size?: number; category?: string; status?: string } = {}): Promise<import("./types").AdminMessagePage> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.category) qs.set("category", params.category);
  if (params.status) qs.set("status", params.status);
  return adminFetch<import("./types").AdminMessagePage>(`/messages?${qs.toString()}`);
}

export function createAdminMessage(payload: {
  title: string;
  body: string;
  category?: string;
  target_type: string;
  target_tiers?: string[];
  target_user_ids?: string[];
  channels?: string[];
  pinned?: boolean;
  important?: boolean;
  scheduled_at?: string | null;
}): Promise<import("./types").AdminMessage> {
  return adminFetch<import("./types").AdminMessage>("/messages", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function recallAdminMessage(messageId: string): Promise<import("./types").AdminMessage> {
  return adminFetch<import("./types").AdminMessage>(`/messages/${messageId}/recall`, { method: "POST" });
}

export function fetchRecipientPreview(params: {
  target_type: string;
  target_tiers?: string[];
  target_user_ids?: string[];
}): Promise<{ recipient_count: number }> {
  const qs = new URLSearchParams();
  qs.set("target_type", params.target_type);
  for (const t of params.target_tiers ?? []) qs.append("target_tiers", t);
  for (const u of params.target_user_ids ?? []) qs.append("target_user_ids", u);
  return adminFetch<{ recipient_count: number }>(`/messages/recipients-preview?${qs.toString()}`);
}

export function fetchAdminTemplates(): Promise<{ total: number; items: import("./types").MessageTemplate[] }> {
  return adminFetch("/message-templates");
}

export function createAdminTemplate(payload: { name: string; title: string; body: string; category?: string; channel?: string }): Promise<import("./types").MessageTemplate> {
  return adminFetch<import("./types").MessageTemplate>("/message-templates", { method: "POST", body: JSON.stringify(payload) });
}

export function updateAdminTemplate(id: string, payload: { name: string; title: string; body: string; category?: string; channel?: string }): Promise<import("./types").MessageTemplate> {
  return adminFetch<import("./types").MessageTemplate>(`/message-templates/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteAdminTemplate(id: string): Promise<{ status: string }> {
  return adminFetch(`/message-templates/${id}`, { method: "DELETE" });
}

// ---------- 消息中心：用户侧 ----------

export async function fetchMyMessages(params: { unread_only?: boolean; page?: number; page_size?: number } = {}): Promise<import("./types").MessageInboxPage> {
  const qs = new URLSearchParams();
  if (params.unread_only) qs.set("unread_only", "true");
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  return parseJson<import("./types").MessageInboxPage>(
    await fetch(`${apiBase()}/v1/messages?${qs.toString()}`, { credentials: "include" })
  );
}

export async function fetchUnreadCount(): Promise<{ unread_count: number }> {
  return parseJson<{ unread_count: number }>(
    await fetch(`${apiBase()}/v1/messages/unread-count`, { credentials: "include" })
  );
}

export async function markMessageRead(messageId: string): Promise<{ status: string; marked: boolean }> {
  return parseJson(
    await fetch(`${apiBase()}/v1/messages/${messageId}/read`, { method: "POST", credentials: "include" })
  );
}

export async function markAllMessagesRead(): Promise<{ status: string; marked: number }> {
  return parseJson(
    await fetch(`${apiBase()}/v1/messages/read-all`, { method: "POST", credentials: "include" })
  );
}

// ---------- 自由写作：优化提示词 ----------

/** 优化提示词：把一句简短想法扩写成完整写作需求，固定扣 1 积分。模型失败后端回退原文。 */
export async function fetchOptimizePrompt(prompt: string): Promise<{ optimized_prompt: string }> {
  const response = await fetch(`${apiBase()}/v1/optimize-prompt`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  return parseJson<{ optimized_prompt: string }>(response);
}

// ---------- 自由写作：继续修改（覆盖当前文档） ----------

/** 自由写作详情页：按用户修改意见重生成文章并覆盖当前文档，返回更新后的文档。 */
export async function reviseDocument(
  documentId: string,
  instruction: string
): Promise<import("./types").WritingDocument> {
  const response = await fetch(`${apiBase()}/v1/documents/${documentId}/revise`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  });
  return parseJson<import("./types").WritingDocument>(response);
}

// ---------- 后台：提示词模板（仅 optimize_prompt 用途） ----------

export type AdminPromptTemplate = {
  id: string;
  name: string;
  purpose: string;
  system_prompt: string;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export function fetchAdminPromptTemplates(): Promise<{ items: AdminPromptTemplate[] }> {
  return adminFetch("/prompt-templates");
}

export function createAdminPromptTemplate(payload: {
  name: string;
  system_prompt: string;
  is_active?: boolean;
}): Promise<AdminPromptTemplate> {
  return adminFetch<AdminPromptTemplate>("/prompt-templates", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      system_prompt: payload.system_prompt,
      is_active: payload.is_active ?? true,
    }),
  });
}

export function updateAdminPromptTemplate(
  id: string,
  payload: { name?: string; system_prompt?: string; is_active?: boolean }
): Promise<AdminPromptTemplate> {
  return adminFetch<AdminPromptTemplate>(`/prompt-templates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteAdminPromptTemplate(id: string): Promise<{ status: string }> {
  return adminFetch(`/prompt-templates/${id}`, { method: "DELETE" });
}

export function setAdminPromptTemplateActive(id: string): Promise<AdminPromptTemplate> {
  return adminFetch<AdminPromptTemplate>(`/prompt-templates/${id}/set-active`, { method: "POST" });
}

export function resetAdminPromptTemplate(id: string): Promise<AdminPromptTemplate> {
  return adminFetch<AdminPromptTemplate>(`/prompt-templates/${id}/reset`, { method: "POST" });
}
