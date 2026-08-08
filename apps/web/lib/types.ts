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
  name: string;
  status: string;
  profile: Record<string, unknown>;
  is_default: boolean;
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
  content: string;
  paragraphs: DocumentParagraph[];
  is_saved?: boolean;
  saved_at?: string | null;
  updated_at: string;
};

export type BusyAction = "upload" | "analysis" | "confirm" | "delete_style" | "edit_style" | "set_default" | "writing" | "rewrite" | "auth" | null;
export type StartMode = "create_style" | "use_existing";
export type ViewName = "dashboard" | "styles" | "writing" | "reading" | "articles" | "settings";
export type AuthMode = "login" | "register";

export const GENRES = ["散文", "故事", "小说", "剧本", "诗歌", "杂文", "随笔"];
