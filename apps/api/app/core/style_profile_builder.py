from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from app import models
from app.core.model_gateway import ModelGateway


def build_style_profile_v2(materials: list[models.Material]) -> dict[str, Any]:
    fallback_profile = build_fallback_style_profile_v2(materials)
    messages = compose_style_analysis_messages(materials=materials, fallback_profile=fallback_profile)
    try:
        model_result = ModelGateway().generate(
            messages=messages,
            purpose="style_analysis",
            fallback=json.dumps(fallback_profile, ensure_ascii=False),
        )
        profile = parse_style_profile_json(model_result.content)
    except Exception:
        profile = fallback_profile
    return normalize_style_profile(profile=profile, materials=materials, fallback_profile=fallback_profile)


def build_fallback_style_profile_v2(materials: list[models.Material]) -> dict[str, Any]:
    paragraph_count = sum(item.paragraph_count for item in materials)
    char_count = sum(item.char_count for item in materials)
    genres = sorted({item.genre for item in materials})
    titles = [item.title for item in materials]
    avg_paragraph_chars = round(char_count / max(1, paragraph_count), 1)
    paragraphs = [p.content for material in materials for p in sorted(material.paragraphs, key=lambda item: item.position)]
    full_text = "\n".join(paragraphs)
    sentence_lengths = sentence_lengths_for(full_text)
    avg_sentence_chars = round(sum(sentence_lengths) / max(1, len(sentence_lengths)), 1)
    punctuation_stats = punctuation_stats_for(full_text)
    frequent_terms = frequent_terms_for(full_text)
    source_language = detect_source_language(full_text)
    profile = {
        "status": "draft_pending_confirmation",
        "profile_version": "style_profile_v2",
        "source_language": source_language,
        "summary": f"基于 {len(materials)} 篇作品、{paragraph_count} 个自然段形成的风格草案，平均段落约 {avg_paragraph_chars} 字。",
        "style_summary": {
            "one_sentence": "从具体场景、物件或动作进入，保持克制观察，并用自然段推进。",
            "stable_features": ["具体场景开篇", "自然段承载完整观察", "少做宏大总结"],
            "unstable_features": [],
            "confidence": 0.62 if char_count < 8000 else 0.78,
        },
        "source_titles": titles,
        "source_material_ids": [item.id for item in materials],
        "applicable_genres": genres or ["散文"],
        "source_stats": {
            "material_count": len(materials),
            "paragraph_count": paragraph_count,
            "char_count": char_count,
            "avg_paragraph_chars": avg_paragraph_chars,
            "sentence_count": len(sentence_lengths),
            "avg_sentence_chars": avg_sentence_chars,
            "sentence_length_distribution": sentence_length_distribution(sentence_lengths),
            "punctuation_stats": punctuation_stats,
            "frequent_terms": frequent_terms,
        },
        "lexical_style": {
            "noun_preference": ["优先保留文本中反复出现的具象名词", *frequent_terms[:8]],
            "verb_preference": ["使用低强度动作动词，避免替作者夸张行动"],
            "adjective_preference": ["形容词密度保持低到中等，不连续堆叠修饰"],
            "abstract_vs_concrete": "以具体物件、地点、动作承载情绪，少直接使用抽象判断。",
            "common_word_register": "现代汉语书面表达，贴近日常口语但不过度网络化。",
            "avoid_words": ["宏大叙事", "心灵鸡汤", "AI 套话", "过度华丽形容词"],
        },
        "syntax_style": {
            "sentence_length_pattern": sentence_pattern_note(avg_sentence_chars),
            "paragraph_length_pattern": f"平均自然段约 {avg_paragraph_chars} 字，生成时应保留自然段呼吸感。",
            "punctuation_habits": [f"{mark}：{count}" for mark, count in punctuation_stats.items()][:8],
            "common_sentence_patterns": ["以陈述句推进观察", "长短句交替", "少用口号式排比"],
            "forbidden_sentence_patterns": ["连续排比", "标题党式设问", "大段解释性总结"],
        },
        "rhetoric_style": {
            "imagery_sources": ["日常器物", "街巷空间", "身体动作", "光线和声音"],
            "metaphor_pattern": "比喻应从生活物件或现场感受中产生，不使用陌生炫技型喻体。",
            "sensory_focus": {
                "visual": "高：优先写物件、光线、位置和动作。",
                "auditory": "中：可使用雨声、脚步、门响等低强度声音。",
                "smell": "低到中：只在场景需要时加入气味。",
                "touch": "低到中：用于旧物质感。",
                "taste": "低：非必要不主动加入。",
            },
            "humor_or_irony": "默认不使用夸张讽刺；如出现幽默，应以克制白描或轻微自嘲呈现。",
        },
        "narrative_style": {
            "point_of_view": "贴近个人经验或近距离观察，不采用全知宏大视角。",
            "opening_patterns": ["从具体物件、动作、声音或地点进入"],
            "development_patterns": ["围绕细节推进", "在观察中带出记忆或判断", "不急于解释主题"],
            "dialogue_style": "对话少量使用；如使用，应短句、留白、贴近日常口语。",
            "ending_patterns": ["用场景、动作或物件收束", "少做直白人生总结"],
        },
        "emotional_tone": {
            "emotion_intensity": "low_to_medium",
            "restraint_level": "high",
            "core_motifs": ["时间痕迹", "日常生活", "旧物", "附近经验"],
            "philosophical_underlay": "通过具体生活细节呈现时间、记忆和个体经验，不直接宣讲价值观。",
        },
        "topic_boundary": {
            "common_scenes": ["街角", "家门口", "小店", "旧屋", "雨后或傍晚场景"],
            "common_character_types": ["普通生活中的人", "家人", "店主", "路过者"],
            "suitable_topics": ["散文", "随笔", "生活观察", "记忆片段", *genres],
            "unsuitable_topics": ["强营销文案", "宏大口号", "高度网络热梗文本"],
        },
        "language_period_style": {
            "modernity": "现代汉语书面语",
            "classical_or_colloquial_features": ["可有轻微口语感", "不主动加入文言腔"],
            "dialect_or_regional_features": [],
        },
        "generation_rules": {
            "must_do": ["从具体物件、动作或地点进入", "保留自然段", "用细节推进而不是先讲道理"],
            "must_avoid": ["空泛抒情", "AI 套话", "未经要求的宏大口号", "复制原文句子或连续意象组合"],
            "opening_rule": "开篇优先落在一个具体场景、物件、动作、声音或地点。",
            "paragraph_rule": f"自然段长度参考原文，平均约 {avg_paragraph_chars} 字；不要改成项目符号或小标题堆叠。",
            "sentence_rule": "根据原文句长分布生成，保持长短句交替和可读停顿。",
            "ending_rule": "结尾用场景、动作或物件收束，少做直白总结。",
            "copying_risk_rules": ["不得复制来源文本原句", "不得连续复用原文专名、真实作品名或独特意象组合"],
        },
        "evidence_map": evidence_map_for(materials),
        "split_recommendation": {
            "should_split": len(genres) > 1,
            "reason": "上传材料包含多个文体，建议用户确认它们是否确实属于同一种风格。" if len(genres) > 1 else "",
            "suggested_profiles": genres if len(genres) > 1 else [],
        },
    }
    profile["display_report"] = build_display_report(profile)
    return profile


def compose_style_analysis_messages(
    *,
    materials: list[models.Material],
    fallback_profile: dict[str, Any],
) -> list[dict[str, str]]:
    stats = fallback_profile["source_stats"]
    paragraphs = []
    for material in materials:
        ordered = sorted(material.paragraphs, key=lambda item: item.position)
        for paragraph in ordered[:8]:
            paragraphs.append(f"【{material.title}｜第 {paragraph.position} 段】{truncate(paragraph.content, 500)}")
    samples = "\n\n".join(paragraphs[:24])
    schema = style_profile_v2_schema_example(stats)
    source_language = str(fallback_profile.get("source_language") or "chinese")
    output_language_rule = (
        "输入作品主要是英文，分析结论可以使用英文。"
        if source_language == "english"
        else "输入作品主要是中文，除 JSON 字段名外，所有分析结论、display_report、规则说明都必须使用中文；不得出现英文术语、英文括注或中英混写。"
    )
    return [
        {
            "role": "system",
            "content": (
                "你是文学风格分析器和 AI 提示词工程师。你的任务是从多篇作品中提取可复用、可执行、可验证的作者 Style Profile。"
                "不要写普通文学评论；不要使用“生动、优美、细腻、深刻”等空泛评价词。"
                f"{output_language_rule}"
                "只输出严格 JSON，不要输出 Markdown，不要解释过程。"
            ),
        },
        {
            "role": "user",
            "content": (
                "## 任务目标\n"
                "请判断这些作品是否属于同一种稳定风格，并提取可直接用于后续仿写的 Style Profile v2。\n\n"
                "## 分析维度要求\n"
                "1. 词汇与句法层：词性偏好、具象/抽象比例、句长分布、标点习惯。\n"
                "2. 修辞与表达层：意象来源、比喻机制、视觉/听觉/嗅觉/触觉/味觉侧重、幽默或讽刺机制。\n"
                "3. 叙事与结构层：叙事视角、开篇方式、发展方式、对话风格、结尾方式。\n"
                "4. 情感与基调层：情绪浓度、克制程度、核心母题、思想底色。\n"
                "5. 题材与素材层：核心场景、人物原型、适合/不适合的写作题材。\n"
                "6. 时代与语体层：语言时代感、书面/口语比例、方言或地域语法。\n\n"
                "## 客观统计\n"
                f"{json.dumps(stats, ensure_ascii=False, indent=2)}\n\n"
                "## 代表段落\n"
                f"{samples}\n\n"
                "## 输出要求\n"
                "- 必须输出严格 JSON，字段结构必须贴近下面的 Schema。\n"
                "- 每个风格判断要尽量变成 generation_rules 中的可执行规则。\n"
                "- evidence_map 只记录段落位置和判断理由，不要复制长原文。\n"
                "- display_report 给普通用户看，必须使用大白话解释，不要使用工程字段名。\n"
                f"- 输出语言要求：{output_language_rule}\n"
                "- 如果多篇作品风格差异明显，split_recommendation.should_split 必须为 true。\n\n"
                "## JSON Schema 示例\n"
                f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


def style_profile_v2_schema_example(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_version": "style_profile_v2",
        "source_language": "chinese|english|mixed",
        "style_summary": {"one_sentence": "string", "stable_features": ["string"], "unstable_features": ["string"], "confidence": 0.0},
        "source_stats": stats,
        "lexical_style": {
            "noun_preference": ["string"],
            "verb_preference": ["string"],
            "adjective_preference": ["string"],
            "abstract_vs_concrete": "string",
            "common_word_register": "string",
            "avoid_words": ["string"],
        },
        "syntax_style": {
            "sentence_length_pattern": "string",
            "paragraph_length_pattern": "string",
            "punctuation_habits": ["string"],
            "common_sentence_patterns": ["string"],
            "forbidden_sentence_patterns": ["string"],
        },
        "rhetoric_style": {
            "imagery_sources": ["string"],
            "metaphor_pattern": "string",
            "sensory_focus": {"visual": "string", "auditory": "string", "smell": "string", "touch": "string", "taste": "string"},
            "humor_or_irony": "string",
        },
        "narrative_style": {
            "point_of_view": "string",
            "opening_patterns": ["string"],
            "development_patterns": ["string"],
            "dialogue_style": "string",
            "ending_patterns": ["string"],
        },
        "emotional_tone": {"emotion_intensity": "string", "restraint_level": "string", "core_motifs": ["string"], "philosophical_underlay": "string"},
        "topic_boundary": {"common_scenes": ["string"], "common_character_types": ["string"], "suitable_topics": ["string"], "unsuitable_topics": ["string"]},
        "language_period_style": {"modernity": "string", "classical_or_colloquial_features": ["string"], "dialect_or_regional_features": ["string"]},
        "generation_rules": {
            "must_do": ["string"],
            "must_avoid": ["string"],
            "opening_rule": "string",
            "paragraph_rule": "string",
            "sentence_rule": "string",
            "ending_rule": "string",
            "copying_risk_rules": ["string"],
        },
        "display_report": {
            "plain_summary": "string",
            "dimensions": [
                {
                    "key": "lexical_syntax",
                    "title": "词汇和句子",
                    "what_we_found": ["string"],
                    "why_it_matters": "string",
                    "editable_summary": "string",
                }
            ],
            "writing_rules_plain": {"must_do": ["string"], "must_avoid": ["string"]},
            "evidence_plain": ["string"],
        },
        "evidence_map": [{"claim": "string", "material_title": "string", "paragraph_index": 1, "evidence_type": "lexical|syntax|imagery|structure|tone|topic"}],
        "split_recommendation": {"should_split": False, "reason": "string", "suggested_profiles": ["string"]},
    }


def parse_style_profile_json(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(stripped[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("style profile must be a JSON object")
    return parsed


def normalize_style_profile(
    *,
    profile: dict[str, Any],
    materials: list[models.Material],
    fallback_profile: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(fallback_profile)
    normalized.update(profile)
    normalized["status"] = "draft_pending_confirmation"
    normalized["profile_version"] = "style_profile_v2"
    normalized["source_titles"] = [item.title for item in materials]
    normalized["source_material_ids"] = [item.id for item in materials]
    normalized["applicable_genres"] = sorted({item.genre for item in materials}) or ["散文"]
    normalized["source_language"] = normalized.get("source_language") or fallback_profile.get("source_language") or "chinese"
    normalized.setdefault("style_summary", fallback_profile["style_summary"])
    normalized.setdefault("generation_rules", fallback_profile["generation_rules"])
    normalized.setdefault("evidence_map", fallback_profile["evidence_map"])
    normalized["display_report"] = normalize_display_report(normalized.get("display_report"), normalized)
    return normalized


def normalize_display_report(value: Any, profile: dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        report = build_display_report(profile)
        report.update(value)
        if not isinstance(report.get("dimensions"), list) or len(report["dimensions"]) != 6:
            report["dimensions"] = build_display_report(profile)["dimensions"]
    else:
        report = build_display_report(profile)
    if profile.get("source_language") != "english":
        return sanitize_report_language(report)
    return report


def build_display_report(profile: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(profile.get("style_summary"))
    lexical = as_dict(profile.get("lexical_style"))
    syntax = as_dict(profile.get("syntax_style"))
    rhetoric = as_dict(profile.get("rhetoric_style"))
    narrative = as_dict(profile.get("narrative_style"))
    tone = as_dict(profile.get("emotional_tone"))
    topic = as_dict(profile.get("topic_boundary"))
    language = as_dict(profile.get("language_period_style"))
    rules = as_dict(profile.get("generation_rules"))
    stats = as_dict(profile.get("source_stats"))
    evidence = as_list(profile.get("evidence_map"))
    avg_paragraph = stats.get("avg_paragraph_chars", "未知")
    avg_sentence = stats.get("avg_sentence_chars", "未知")
    one_sentence = as_text(summary.get("one_sentence")) or "这批作品形成了一个可用于仿写的个人风格草案。"
    return {
        "plain_summary": (
            f"我们理解到：{one_sentence}"
            f"从统计上看，平均自然段约 {avg_paragraph} 字，平均句长约 {avg_sentence} 字。"
            "下面把这种风格拆成六个方面，方便你判断系统是否真正读懂了参考文章。"
        ),
        "dimensions": [
            {
                "key": "lexical_syntax",
                "title": "词汇和句子",
                "what_we_found": [
                    f"常用词更偏向：{join_items(lexical.get('noun_preference'))}。",
                    as_text(syntax.get("sentence_length_pattern")),
                    as_text(syntax.get("paragraph_length_pattern")),
                ],
                "why_it_matters": "这决定了生成文章时用哪些词、句子长短怎么安排、读起来是否像原作者。",
                "editable_summary": "如果你觉得作者其实更口语、更书面、更爱长句或更爱短句，可以直接修改这里。",
            },
            {
                "key": "rhetoric_expression",
                "title": "修辞和表达",
                "what_we_found": [
                    f"意象主要来自：{join_items(rhetoric.get('imagery_sources'))}。",
                    as_text(rhetoric.get("metaphor_pattern")),
                    f"感官侧重：{summarize_sensory_focus(rhetoric.get('sensory_focus'))}",
                ],
                "why_it_matters": "这决定了仿写时是多写自然、旧物、市井、典故，还是多写抽象感受。",
                "editable_summary": "如果系统误判了作者常用意象或比喻来源，可以在这里改。",
            },
            {
                "key": "narrative_structure",
                "title": "叙事和结构",
                "what_we_found": [
                    f"常见开头：{join_items(narrative.get('opening_patterns'))}。",
                    f"中间推进：{join_items(narrative.get('development_patterns'))}。",
                    f"常见结尾：{join_items(narrative.get('ending_patterns'))}。",
                ],
                "why_it_matters": "这决定了文章是先讲观点、先给画面，还是先进入人物和动作。",
                "editable_summary": "如果原作者有固定起手式、转折方式或结尾方式，可以在这里补充。",
            },
            {
                "key": "emotion_tone",
                "title": "情绪和基调",
                "what_we_found": [
                    f"情绪浓度：{as_text(tone.get('emotion_intensity')) or '未判断'}。",
                    f"克制程度：{as_text(tone.get('restraint_level')) or '未判断'}。",
                    f"核心母题：{join_items(tone.get('core_motifs'))}。",
                ],
                "why_it_matters": "这决定了生成内容是热烈直白、冷静克制，还是带幽默、讽刺或伤感。",
                "editable_summary": "如果你觉得作者情绪更强、更冷、更幽默或更尖锐，可以在这里改。",
            },
            {
                "key": "topic_material",
                "title": "题材和人物",
                "what_we_found": [
                    f"常见场景：{join_items(topic.get('common_scenes'))}。",
                    f"常见人物：{join_items(topic.get('common_character_types'))}。",
                    f"适合题材：{join_items(topic.get('suitable_topics'))}。",
                ],
                "why_it_matters": "这决定了系统以后选择什么生活素材和人物类型来承载风格。",
                "editable_summary": "如果作者更常写乡村、城市、家庭、历史或某类人物，可以在这里补充。",
            },
            {
                "key": "period_register",
                "title": "时代和语体",
                "what_we_found": [
                    f"语言时代感：{as_text(language.get('modernity')) or '未判断'}。",
                    f"书面/口语特点：{join_items(language.get('classical_or_colloquial_features'))}。",
                    f"方言或地域特征：{join_items(language.get('dialect_or_regional_features'))}。",
                ],
                "why_it_matters": "这决定了生成文章是现代白话、半文半白、口语化，还是带地域表达。",
                "editable_summary": "如果作者有明显口头语、方言、年代感或文言残留，可以在这里补充。",
            },
        ],
        "writing_rules_plain": {
            "must_do": as_str_list(rules.get("must_do")),
            "must_avoid": as_str_list(rules.get("must_avoid")),
        },
        "evidence_plain": [
            f"{as_text(as_dict(item).get('material_title'))} 第 {as_dict(item).get('paragraph_index')} 段：{as_text(as_dict(item).get('claim'))}"
            for item in evidence[:6]
            if isinstance(item, dict)
        ],
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_str_list(value: Any) -> list[str]:
    return [item for item in as_list(value) if isinstance(item, str)]


def as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def join_items(value: Any) -> str:
    items = as_str_list(value)
    return "、".join(items[:6]) if items else "暂未判断"


def summarize_sensory_focus(value: Any) -> str:
    focus = as_dict(value)
    if not focus:
        return "暂未判断"
    labels = {
        "visual": "视觉",
        "auditory": "听觉",
        "smell": "嗅觉",
        "touch": "触觉",
        "taste": "味觉",
    }
    return "；".join(f"{labels.get(key, key)}：{text}" for key, text in focus.items() if isinstance(text, str)) or "暂未判断"


def sanitize_report_language(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize_report_language(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_report_language(item) for item in value]
    if isinstance(value, str):
        return clean_chinese_display_text(value)
    return value


def clean_chinese_display_text(value: str) -> str:
    cleaned = value
    cleaned = re.sub(r"\bAI\b", "人工智能", cleaned)
    cleaned = re.sub(r"\bJSON\b", "数据", cleaned)
    cleaned = re.sub(r"\bStyle\s*Profile\b", "风格档案", cleaned)
    cleaned = re.sub(r"\([^()\u4e00-\u9fff]*[A-Za-z][^()\u4e00-\u9fff]*\)", "", cleaned)
    cleaned = re.sub(r"\b[A-Za-z][A-Za-z0-9_-]*\b", "", cleaned)
    cleaned = re.sub(r"\s*/\s*", "、", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"：\s*[。；，]", "：暂未判断。", cleaned)
    cleaned = re.sub(r"[（(]\s*[）)]", "", cleaned)
    return cleaned.strip()


def detect_source_language(text: str) -> str:
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_count = len(re.findall(r"[A-Za-z]", text))
    if english_count > chinese_count * 2 and english_count > 80:
        return "english"
    if chinese_count > english_count:
        return "chinese"
    return "mixed"


def sentence_lengths_for(text: str) -> list[int]:
    sentences = [item.strip() for item in re.split(r"[。！？!?；;]+", text) if item.strip()]
    return [len(item) for item in sentences]


def sentence_length_distribution(lengths: list[int]) -> dict[str, int]:
    return {
        "short_<=15": sum(1 for item in lengths if item <= 15),
        "medium_16_35": sum(1 for item in lengths if 16 <= item <= 35),
        "long_>35": sum(1 for item in lengths if item > 35),
    }


def sentence_pattern_note(avg_sentence_chars: float) -> str:
    if avg_sentence_chars <= 18:
        return f"平均句长约 {avg_sentence_chars} 字，短句占比较高，生成时应保留停顿感。"
    if avg_sentence_chars >= 35:
        return f"平均句长约 {avg_sentence_chars} 字，长句展开较多，生成时要控制层层推进的句法。"
    return f"平均句长约 {avg_sentence_chars} 字，长短句混合，生成时避免单一节奏。"


def punctuation_stats_for(text: str) -> dict[str, int]:
    marks = "，。！？；：、“”‘’（）——……,.!?;:"
    counts = Counter(ch for ch in text if ch in marks)
    return dict(counts.most_common(10))


def frequent_terms_for(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    stop_words = {"一个", "一篇", "我们", "他们", "这个", "那个", "没有", "还是", "只是", "时候", "起来"}
    return [word for word, _ in Counter(token for token in tokens if token not in stop_words).most_common(12)]


def evidence_map_for(materials: list[models.Material]) -> list[dict[str, Any]]:
    evidence = []
    for material in materials:
        ordered = sorted(material.paragraphs, key=lambda item: item.position)
        for paragraph in ordered[:2]:
            evidence.append(
                {
                    "claim": "代表段落用于判断开篇方式、句法节奏和意象来源",
                    "material_title": material.title,
                    "paragraph_index": paragraph.position,
                    "evidence_type": "structure",
                }
            )
    return evidence[:8]


def truncate(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else compact[:limit] + "…"
