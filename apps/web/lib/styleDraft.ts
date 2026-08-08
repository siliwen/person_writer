import type { StyleDraftView } from "./types";

export function summarizeStyleDraft(profile: Record<string, unknown> | undefined): StyleDraftView | null {
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
