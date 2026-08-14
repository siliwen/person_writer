export type Material = {
  id: string;
  title: string;
  genre: string;
  source_filename: string | null;
  char_count: number;
  paragraph_count: number;
};

export type StyleJob = {
  id: string;
  status: string;
  material_ids: string[];
  draft_profile: Record<string, unknown>;
};

export type StyleProfile = {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  status: string;
  profile: Record<string, unknown>;
  is_default: boolean;
  is_recommended?: boolean;
};

export type CurrentUser = {
  user_id: string;
  username: string;
  display_name: string;
  mode: string;
  phone_number: string | null;
  phone_verified: boolean;
  email: string | null;
  email_verified: boolean;
  tier_code: string | null;
  points_balance: number;
  is_admin: boolean;
};

export type StyleDraftView = {
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

export type DocumentParagraph = {
  id: string;
  position: number;
  content: string;
  rewrite_count: number;
};

export type ModelStatus = {
  mode: string;
  has_api_key: boolean;
  base_url: string;
  model_name: string;
  fallback_behavior: string;
};

export type WritingDocument = {
  id: string;
  title: string;
  genre: string;
  style_profile_id: string;
  content: string;
  paragraphs: DocumentParagraph[];
  is_saved?: boolean;
  saved_at?: string | null;
  updated_at: string;
};

export type BusyAction = "upload" | "analysis" | "confirm" | "delete_style" | "edit_style" | "set_default" | "writing" | "rewrite" | "auth" | null;
export type StartMode = "create_style" | "use_existing";
export type ViewName = "dashboard" | "styles" | "writing" | "reading" | "free-writing" | "articles" | "settings" | "admin";
export type AuthMode = "login" | "register";

/** 自由写作（无风格）文档挂载的系统占位风格 id，与后端 constants.SYSTEM_FREE_WRITE_STYLE_ID 保持一致。 */
export const SYSTEM_FREE_WRITE_STYLE_ID = "system_free_write";

/** 会员等级配置（来自后端 membership_tiers 表，代码只读取不写死）。 */
export type MembershipTierInfo = {
  code: string;
  name: string;
  monthly_points: number;
  price_monthly: number;
  style_limit: number;
  material_limit: number;
  can_download: boolean;
  can_rewrite: boolean;
  max_article_length: number;
};

/** 文章长度档位（来自后端 article_length_brackets 表）。 */
export type ArticleLengthBracket = {
  label: string;
  min_length: number;
  max_length: number | null;
  points: number;
};

/** /v1/account/quota 返回结构。 */
export type QuotaView = {
  tier: MembershipTierInfo;
  points_balance: number;
  quota_period_end: string | null;
  operation_points: { style_analysis: number; paragraph_rewrite: number };
  article_length_brackets: ArticleLengthBracket[];
};

/** 单条积分消耗流水（来自 usage_records 表）。 */
export type UsageRecord = {
  id: string;
  op_type: string;
  points_consumed: number;
  document_id: string | null;
  model_name: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_cny: number;
  created_at: string;
};

export type UsagePage = {
  total: number;
  page: number;
  page_size: number;
  items: UsageRecord[];
};

/** 管理后台：消耗流水（比用户侧多返回 user_id）。 */
export type AdminUsageRecord = UsageRecord & { user_id: string };

export type AdminUsagePage = {
  total: number;
  page: number;
  page_size: number;
  items: AdminUsageRecord[];
};

/** 管理后台：用户摘要（来自 /v1/admin/users）。 */
export type AdminUser = {
  user_id: string;
  username: string;
  display_name: string;
  tier_code: string | null;
  points_balance: number;
  quota_period_end: string | null;
  is_admin: boolean;
  created_at: string;
};

/** 管理后台：风格档案（含推荐标记），用于「推荐风格」管理页。 */
export type AdminStyle = {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  status: string;
  is_recommended: boolean;
  created_at: string;
};

/** 管理后台：会员等级配置（来自 membership_tiers）。 */
export type AdminTier = {
  code: string;
  name: string;
  monthly_points: number;
  price_monthly: number;
  style_limit: number;
  material_limit: number;
  can_download: boolean;
  can_rewrite: boolean;
  max_article_length: number;
  sort_order: number;
  is_active: boolean;
};

/** 管理后台：文章长度档位。 */
export type AdminBracket = {
  id: string;
  label: string;
  min_length: number;
  max_length: number | null;
  sort_order: number;
  is_active: boolean;
};

/** 管理后台：固定操作积分。 */
export type AdminOperationCost = {
  id: string;
  op_type: string;
  points: number;
  description: string | null;
  is_active: boolean;
};

/** 管理后台：模型单价。 */
export type AdminModelPricing = {
  id: string;
  model: string;
  input_price_per_m: number;
  output_price_per_m: number;
  currency: string;
  is_active: boolean;
  note: string | null;
};

/** 管理后台：仪表盘聚合指标。 */
export type AdminMetrics = {
  total_users: number;
  new_users_today: number;
  active_today: number;
  total_documents: number;
  points_consumed_month: number;
  cost_month_cny: number;
  mrr_estimate_cny: number;
  tier_distribution: Array<{ code: string; name: string; count: number }>;
};

/** 管理后台：操作审计日志。 */
export type AuditLogEntry = {
  id: string;
  actor_id: string;
  actor_name: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string | null;
  created_at: string;
};

/** 消息中心：用户侧收件箱单条（含已读态）。 */
export type MessageInboxItem = {
  id: string;
  sender_id: string;
  title: string;
  body: string;
  category: string; // system / announcement / direct
  target_type: string; // all / tier / specific
  pinned: boolean;
  important: boolean;
  is_automated: boolean;
  sent_at: string | null;
  created_at: string;
  is_read: boolean;
  read_at: string | null;
};

export type MessageInboxPage = {
  total: number;
  page: number;
  page_size: number;
  items: MessageInboxItem[];
};

/** 消息中心：管理员侧消息（已发列表）。 */
export type AdminMessage = {
  id: string;
  sender_id: string;
  title: string;
  body: string;
  category: string;
  target_type: string;
  target_tiers: string[];
  target_user_ids: string[];
  channels: string[];
  status: string; // draft / sent / scheduled / recalled
  pinned: boolean;
  important: boolean;
  is_automated: boolean;
  scheduled_at: string | null;
  sent_at: string | null;
  recipient_count: number;
  created_at: string;
  updated_at: string;
  read_count?: number;
};

export type AdminMessagePage = {
  total: number;
  page: number;
  page_size: number;
  items: AdminMessage[];
};

/** 消息中心：消息模板。 */
export type MessageTemplate = {
  id: string;
  name: string;
  title: string;
  body: string;
  category: string;
  channel: string;
  created_at: string;
  updated_at: string;
};

/** 文章鉴评：单个评分维度。 */
export type EvaluationDimension = {
  key: string;
  label: string;
  weight: number;
  score: number;
  comment: string;
  quotes?: string[];
};

/** 文章鉴评：一条具体修改建议。 */
export type EvaluationSuggestion = {
  location?: string;
  issue?: string;
  why?: string;
  fix?: string;
};

/** 文章鉴评：风格偏离项（对照用户风格档案六维）。 */
export type EvaluationStyleDeviation = {
  dimension?: string;
  expected?: string;
  observed?: string;
  advice?: string;
};

/** 文章鉴评：完整报告体。 */
export type EvaluationReport = {
  genre: string;
  overall: { score: number; grade: string; summary: string };
  dimensions: EvaluationDimension[];
  suggestions: EvaluationSuggestion[];
  style_deviations: EvaluationStyleDeviation[];
  ai_tell_flags: string[];
  features: Record<string, unknown>;
  disclaimer: string;
  engine: string;
};

/** 文章鉴评：接口返回体。 */
export type ArticleEvaluation = {
  id: string;
  document_id: string;
  writing_task_id: string | null;
  genre: string;
  overall_score: number;
  grade: string;
  trigger: string;
  report: EvaluationReport;
  model_name: string | null;
  created_at: string;
};

export const GENRES = ["散文", "故事", "小说", "剧本", "诗歌", "杂文", "随笔"];

/** 首版鉴评仅支持散文，其余文体量规仍在打磨。 */
export const EVALUATION_GENRES = ["散文"];
