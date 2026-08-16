"""文章鉴评服务（Article Evaluation）。

判定逻辑 = 确定性特征抽取（Python，零成本、可复现） + LLM-as-Judge（结构化 JSON）。

- 确定性层：句长分布、TTR、标点密度、重复 n-gram、AI 味正则、字数偏差、必含词命中。
  这些客观信号既用于打底评分，也强制回填进最终报告，保证 LLM 失灵时报告仍然可用。
- 主观层：把「文体量规 + 用户风格档案六维 + 原始写作要求 + 正文」喂给模型，
  要求输出各维度分数、点评、引用原文、可执行改写建议。

首版仅覆盖散文（SUPPORTED_GENRES），其余文体接口直接拒绝，避免用不成熟的量规误导用户。
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.core.constants import PURPOSE_ARTICLE_EVALUATION
from app.core.model_gateway import ModelGateway
from app.core.prompt_template_service import (
    DEFAULT_ARTICLE_EVALUATION_PROMPT,
    get_active_prompt_template,
)


# ---------------------------------------------------------------------------
# 维度与权重（总和必须为 1.0）
# ---------------------------------------------------------------------------

DIMENSIONS: list[tuple[str, str, float]] = [
    ("genre_fit", "文体契合度", 0.25),
    ("style_fit", "风格契合度", 0.25),
    ("content_quality", "内容质量", 0.20),
    ("instruction_fit", "指令遵循", 0.15),
    ("language_norm", "语言规范", 0.15),
]

DIMENSION_LABELS = {key: label for key, label, _w in DIMENSIONS}
DIMENSION_WEIGHTS = {key: weight for key, _l, weight in DIMENSIONS}

SUPPORTED_GENRES = {"散文"}

DISCLAIMER = "AI 鉴评，仅供参考。文学优劣带有主观性，本报告用于提示明显问题与改进方向，不作为终审结论。"


# 散文量规——写进 prompt，也是启发式打分的依据说明
RUBRIC_PROSE = {
    "genre": "散文",
    "core": [
        "形散神聚：材料可以跳跃，但要有一条贯穿的情绪或认知主线，结尾能收得住。",
        "真情实感：从具体的人、物、场景生发感受，不靠空泛抒情和口号式升华。",
        "细节可感：有具体可触的细节（物件、动作、光线、声音、气味），而非概念堆砌。",
        "语言有味：句子有节奏变化，长短相间；克制修辞，不堆砌形容词。",
        "有余味：结尾留白或轻收，不做总结陈词式的强行拔高。",
    ],
    "anti_patterns": [
        "通篇概念与感慨，缺少具体场景与细节。",
        "结尾用'让我们……''总而言之……'式口号收束。",
        "排比与金句密集，情绪浓度超过内容承载。",
        "段落之间没有内在推进，像并列的读后感。",
    ],
}

STYLE_DIMENSION_KEYS = [
    "词汇和句子",
    "修辞和表达",
    "叙事和结构",
    "情绪和基调",
    "题材和人物",
    "时代和语体",
]


# ---------------------------------------------------------------------------
# 确定性特征抽取
# ---------------------------------------------------------------------------

_SENTENCE_END = "。！？!?…"
_PUNCTUATION = "，。！？；：、“”‘’（）《》—…,.!?;:\"'()"

AI_TELL_PATTERNS: list[tuple[str, str]] = [
    (r"不仅[^。！？\n]{0,20}(更|而且|还)", "『不仅…更…』式套路句"),
    (r"在这个[^。！？\n]{0,12}的?时代", "『在这个…的时代』开场套路"),
    (r"(让我们|我们每个人都|愿我们)", "口号式呼告"),
    (r"(总而言之|综上所述|由此可见)", "总结陈词式收束"),
    (r"(诗和远方|心灵的洗礼|灵魂的|治愈了我|人生的意义)", "空泛金句"),
    (r"([^，。\n]{1,6})，\1[^，。\n]{0,6}，\1", "三段式排比堆砌"),
    (r"(？)", "__never__"),  # 占位，永不命中（保持索引稳定，便于后续增删）
]

# 排比检测：同一动词/短语重复三次以上（如「拥抱X，拥抱Y，拥抱Z」）
_TRIPLE_PARALLEL = re.compile(r"([\u4e00-\u9fa5]{2,4})[^，。\n]{0,8}，\1[^，。\n]{0,8}，\1")


def parse_target_chars(target_length: str | None) -> int:
    if not target_length:
        return 0
    digits = "".join(ch for ch in str(target_length) if ch.isdigit())
    return int(digits) if digits else 0


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    buffer = ""
    for ch in text:
        if ch == "\n":
            if buffer.strip():
                sentences.append(buffer.strip())
            buffer = ""
            continue
        buffer += ch
        if ch in _SENTENCE_END:
            if buffer.strip():
                sentences.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        sentences.append(buffer.strip())
    return sentences


def _repeated_ngram_ratio(text: str, n: int = 5) -> float:
    core = re.sub(r"\s+", "", text)
    if len(core) <= n:
        return 0.0
    grams = [core[i : i + n] for i in range(len(core) - n + 1)]
    total = len(grams)
    seen: dict[str, int] = {}
    for gram in grams:
        seen[gram] = seen.get(gram, 0) + 1
    repeated = sum(count for count in seen.values() if count > 1)
    return round(repeated / total, 4)


def detect_ai_tells(text: str) -> list[str]:
    flags: list[str] = []
    for pattern, label in AI_TELL_PATTERNS:
        if label == "__never__":
            continue
        if re.search(pattern, text):
            if label not in flags:
                flags.append(label)
    if _TRIPLE_PARALLEL.search(text) and "三段式排比堆砌" not in flags:
        flags.append("三段式排比堆砌")
    dash_count = text.count("——")
    core_len = max(1, len(re.sub(r"\s+", "", text)))
    if dash_count >= 2 and dash_count / core_len > 0.002:
        flags.append("破折号密度过高")
    return flags


def extract_features(
    text: str,
    *,
    target_length: str | None = None,
    must_include: str = "",
) -> dict[str, Any]:
    """抽取可复现的客观写作特征。不调用模型，零成本。"""
    normalized = (text or "").strip()
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n|\n", normalized) if item.strip()]
    core = re.sub(r"\s+", "", normalized)
    char_count = len(core)
    sentences = split_sentences(normalized)
    lengths = [len(re.sub(r"\s+", "", item)) for item in sentences if item.strip()]
    avg_sentence_length = round(sum(lengths) / len(lengths), 2) if lengths else 0.0
    max_sentence_length = max(lengths) if lengths else 0
    min_sentence_length = min(lengths) if lengths else 0
    variance = (
        round(sum((item - avg_sentence_length) ** 2 for item in lengths) / len(lengths), 2) if lengths else 0.0
    )
    distinct = len(set(core))
    ttr = round(distinct / char_count, 4) if char_count else 0.0
    punctuation_count = sum(1 for ch in normalized if ch in _PUNCTUATION)
    punctuation_density = round(punctuation_count / char_count, 4) if char_count else 0.0
    dialogue_count = normalized.count("“") + normalized.count('"') // 2

    target_chars = parse_target_chars(target_length)
    if target_chars > 0:
        deviation = round((char_count - target_chars) / target_chars, 4)
    else:
        deviation = 0.0

    include_terms = [
        item.strip()
        for item in re.split(r"[,，、;；]", must_include or "")
        if item.strip()
    ]
    missing_terms = [term for term in include_terms if term not in normalized]

    return {
        "char_count": char_count,
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "avg_sentence_length": avg_sentence_length,
        "max_sentence_length": max_sentence_length,
        "min_sentence_length": min_sentence_length,
        "sentence_length_variance": variance,
        "ttr": ttr,
        "punctuation_density": punctuation_density,
        "dialogue_marks": dialogue_count,
        "repeated_ngram_ratio": _repeated_ngram_ratio(normalized),
        "target_chars": target_chars,
        "length_deviation_ratio": deviation,
        "required_terms": include_terms,
        "missing_required_terms": missing_terms,
        "ai_tell_flags": detect_ai_tells(normalized),
    }


# ---------------------------------------------------------------------------
# 评分工具
# ---------------------------------------------------------------------------

def clamp_score(value: Any, *, default: float = 6.0) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return default
    return round(max(0.0, min(10.0, score)), 2)


def weighted_score(dimensions: list[dict[str, Any]]) -> float:
    total = 0.0
    weight_sum = 0.0
    for dim in dimensions:
        key = dim.get("key")
        weight = DIMENSION_WEIGHTS.get(key)
        if weight is None:
            continue
        total += clamp_score(dim.get("score")) * weight
        weight_sum += weight
    if weight_sum <= 0:
        return 0.0
    return round(total / weight_sum, 2)


def grade_for(score: float) -> str:
    if score >= 9.0:
        return "S"
    if score >= 8.0:
        return "A"
    if score >= 7.0:
        return "B"
    if score >= 6.0:
        return "C"
    return "D"


def is_supported_genre(genre: str | None) -> bool:
    return (genre or "").strip() in SUPPORTED_GENRES


# ---------------------------------------------------------------------------
# 启发式报告（LLM 不可用 / 解析失败时的兜底，同时作为 mock 模式的 fallback）
# ---------------------------------------------------------------------------

def _heuristic_scores(features: dict[str, Any]) -> dict[str, tuple[float, str]]:
    flags = features["ai_tell_flags"]
    deviation = abs(features["length_deviation_ratio"])
    avg_len = features["avg_sentence_length"]
    paragraphs = features["paragraph_count"]
    ttr = features["ttr"]
    repeat = features["repeated_ngram_ratio"]

    # 语言规范
    language = 8.5 - min(3.0, 0.6 * len(flags))
    if avg_len > 60 or (0 < avg_len < 8):
        language -= 1.0
    if repeat > 0.05:
        language -= 1.0
    language_comment = (
        "语言基本干净，句长与标点使用合理。"
        if not flags and repeat <= 0.05
        else "检测到 AI 写作痕迹或重复表达：" + "、".join(flags or ["局部措辞重复"]) + "，建议逐处替换为具体描写。"
    )

    # 指令遵循
    if features["target_chars"] <= 0:
        instruction = 7.5
        instruction_comment = "未提供明确目标字数，按内容完整度给中性分。"
    elif deviation <= 0.15:
        instruction = 9.0
        instruction_comment = f"篇幅贴合目标（实际 {features['char_count']} 字，目标 {features['target_chars']} 字）。"
    elif deviation <= 0.3:
        instruction = 7.5
        instruction_comment = f"篇幅略有偏差（实际 {features['char_count']} 字，目标 {features['target_chars']} 字）。"
    elif deviation <= 0.5:
        instruction = 6.0
        instruction_comment = f"篇幅偏差明显（实际 {features['char_count']} 字，目标 {features['target_chars']} 字），需要扩写或压缩。"
    else:
        instruction = 4.5
        instruction_comment = f"篇幅严重偏离目标（实际 {features['char_count']} 字，目标 {features['target_chars']} 字）。"
    if features["missing_required_terms"]:
        instruction -= 1.5
        instruction_comment += " 必含要素未出现：" + "、".join(features["missing_required_terms"]) + "。"

    # 内容质量
    content = 7.5
    if ttr < 0.25:
        content -= 1.0
    if repeat > 0.05:
        content -= 1.0
    if paragraphs < 3:
        content -= 1.0
    content_comment = (
        "内容组织完整，用词丰富度正常。"
        if content >= 7.0
        else "用词重复度偏高或结构过于单薄，建议补入具体场景与细节。"
    )

    # 文体契合（散文）
    genre_score = 8.0
    if paragraphs < 3:
        genre_score -= 1.5
    if avg_len and not (12 <= avg_len <= 50):
        genre_score -= 1.0
    if any(flag in {"口号式呼告", "总结陈词式收束", "空泛金句"} for flag in flags):
        genre_score -= 1.5
    genre_comment = (
        "散文的段落推进与句式节奏基本成立。"
        if genre_score >= 7.0
        else "更像议论或读后感：缺少可感细节，或结尾用口号强行拔高，偏离散文『形散神聚、以小见大』的要求。"
    )

    # 风格契合
    style_score = 7.5
    if flags:
        style_score -= 0.5 * min(2, len(flags))
    style_comment = "整体语气与档案基调无明显冲突；细粒度比对见风格偏离列表。"

    return {
        "genre_fit": (clamp_score(genre_score), genre_comment),
        "style_fit": (clamp_score(style_score), style_comment),
        "content_quality": (clamp_score(content), content_comment),
        "instruction_fit": (clamp_score(instruction), instruction_comment),
        "language_norm": (clamp_score(language), language_comment),
    }


def build_heuristic_report(features: dict[str, Any], *, genre: str = "散文") -> dict[str, Any]:
    scores = _heuristic_scores(features)
    dimensions = [
        {
            "key": key,
            "label": label,
            "weight": weight,
            "score": scores[key][0],
            "comment": scores[key][1],
            "quotes": [],
        }
        for key, label, weight in DIMENSIONS
    ]
    overall = weighted_score(dimensions)

    suggestions: list[dict[str, str]] = []
    for flag in features["ai_tell_flags"]:
        suggestions.append(
            {
                "location": "全文",
                "issue": f"存在{flag}",
                "why": "散文量规要求从具体细节生发感受，套路句会稀释真实感。",
                "fix": "删掉该处概括性表达，换成一个可触摸的细节（物件、动作、声音、光线）。",
            }
        )
    if features["missing_required_terms"]:
        suggestions.append(
            {
                "location": "全文",
                "issue": "必含要素缺失：" + "、".join(features["missing_required_terms"]),
                "why": "写作要求中明确列出的要素必须出现。",
                "fix": "在合适段落自然嵌入这些要素，不要生硬罗列。",
            }
        )
    if abs(features["length_deviation_ratio"]) > 0.3 and features["target_chars"] > 0:
        direction = "扩写" if features["length_deviation_ratio"] < 0 else "压缩"
        suggestions.append(
            {
                "location": "全篇",
                "issue": f"篇幅与目标相差 {abs(features['length_deviation_ratio']) * 100:.0f}%",
                "why": "篇幅偏离会影响节奏与信息密度。",
                "fix": f"按目标 {features['target_chars']} 字{direction}，优先{direction}场景描写而非议论。",
            }
        )
    if features["paragraph_count"] < 3:
        suggestions.append(
            {
                "location": "结构",
                "issue": "段落过少，推进层次不足",
                "why": "散文需要在段落间完成由物及情、由景入理的推进。",
                "fix": "拆出至少 3-5 个自然段，让场景、细节、感受各有落点。",
            }
        )

    return {
        "genre": genre,
        "overall": {
            "score": overall,
            "grade": grade_for(overall),
            "summary": _heuristic_summary(features, overall),
        },
        "dimensions": dimensions,
        "suggestions": suggestions,
        "style_deviations": [],
        "ai_tell_flags": features["ai_tell_flags"],
        "features": features,
        "disclaimer": DISCLAIMER,
        "engine": "heuristic",
    }


def _heuristic_summary(features: dict[str, Any], overall: float) -> str:
    parts = [f"综合 {overall} 分（{grade_for(overall)}）。"]
    if features["ai_tell_flags"]:
        parts.append("主要扣分项是 AI 写作痕迹：" + "、".join(features["ai_tell_flags"]) + "。")
    if abs(features["length_deviation_ratio"]) > 0.3 and features["target_chars"] > 0:
        parts.append("篇幅与目标字数偏差较大。")
    if not features["ai_tell_flags"] and abs(features["length_deviation_ratio"]) <= 0.3:
        parts.append("客观指标未发现明显问题，重点关注细节密度与结尾收束。")
    return "".join(parts)


# ---------------------------------------------------------------------------
# LLM Judge
# ---------------------------------------------------------------------------

def _build_judge_messages(
    *,
    text: str,
    genre: str,
    style_profile: dict[str, Any] | None,
    requirements: dict[str, Any],
    features: dict[str, Any],
    system_prompt: str | None = None,
) -> list[dict[str, str]]:
    dimension_spec = "\n".join(
        f"- {key}（{label}，权重 {weight}）" for key, label, weight in DIMENSIONS
    )
    system_prompt = system_prompt or DEFAULT_ARTICLE_EVALUATION_PROMPT
    user_prompt = "\n".join(
        [
            f"## 评审文体：{genre}",
            "",
            "## 文体量规（判定依据）",
            "核心要求：",
            *[f"- {item}" for item in RUBRIC_PROSE["core"]],
            "典型反模式（命中即扣分）：",
            *[f"- {item}" for item in RUBRIC_PROSE["anti_patterns"]],
            "",
            "## 用户风格档案（style_fit 的标准答案，逐维比对）",
            "```json",
            json.dumps(style_profile or {}, ensure_ascii=False, indent=2)[:4000],
            "```",
            "",
            "## 原始写作要求（instruction_fit 的判定依据）",
            "```json",
            json.dumps(requirements or {}, ensure_ascii=False),
            "```",
            "",
            "## 客观特征（已由程序统计，请直接采信，不要重新计算）",
            "```json",
            json.dumps(features, ensure_ascii=False),
            "```",
            "",
            "## 待评审正文",
            "```",
            text[:8000],
            "```",
            "",
            "## 评分维度（每维 0-10 分，允许一位小数）",
            dimension_spec,
            "",
            "## 输出格式（严格 JSON，字段不可缺）",
            json.dumps(
                {
                    "overall": {"summary": "两到三句总评，点明最大问题"},
                    "dimensions": [
                        {
                            "key": "genre_fit",
                            "score": 7.5,
                            "comment": "该维度的具体判断，必须说明依据",
                            "quotes": ["支撑判断的原文片段"],
                        }
                    ],
                    "suggestions": [
                        {
                            "location": "第几段或原文定位",
                            "issue": "具体问题",
                            "why": "违背了哪条量规或哪条风格特征",
                            "fix": "可直接照做的改写建议，尽量给出改写后的示例句",
                        }
                    ],
                    "style_deviations": [
                        {
                            "dimension": "词汇和句子",
                            "expected": "风格档案里的特征",
                            "observed": "正文实际表现",
                            "advice": "如何靠拢",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            "",
            "要求：dimensions 必须覆盖全部 5 个 key；suggestions 至少 2 条且必须具体可执行；"
            "style_deviations 逐条对应风格档案维度，无偏离时给空数组；不要输出 Markdown 代码块以外的文字。",
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def parse_report_json(content: str) -> dict[str, Any] | None:
    if not content:
        return None
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def normalize_report(
    raw: dict[str, Any] | None,
    *,
    heuristic: dict[str, Any],
    features: dict[str, Any],
    genre: str,
) -> dict[str, Any]:
    """把模型输出规整成契约结构；缺失部分用启发式结果回填，客观特征强制以程序统计为准。"""
    if not raw:
        return heuristic

    heuristic_dims = {item["key"]: item for item in heuristic["dimensions"]}
    raw_dims_source = raw.get("dimensions")
    raw_dims: dict[str, dict[str, Any]] = {}
    if isinstance(raw_dims_source, list):
        for item in raw_dims_source:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if key not in DIMENSION_WEIGHTS:
                # 允许模型用中文标签回传
                key = next((k for k, label in DIMENSION_LABELS.items() if label == item.get("label")), None)
            if key:
                raw_dims[key] = item

    dimensions: list[dict[str, Any]] = []
    for key, label, weight in DIMENSIONS:
        fallback = heuristic_dims[key]
        item = raw_dims.get(key, {})
        quotes = item.get("quotes")
        dimensions.append(
            {
                "key": key,
                "label": label,
                "weight": weight,
                "score": clamp_score(item.get("score"), default=fallback["score"]),
                "comment": str(item.get("comment") or fallback["comment"]).strip(),
                "quotes": [str(q) for q in quotes][:3] if isinstance(quotes, list) else [],
            }
        )

    def _clean_list(value: Any, required_keys: set[str]) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        cleaned: list[dict[str, str]] = []
        for item in value:
            if isinstance(item, dict) and required_keys & set(item):
                cleaned.append({str(k): str(v) for k, v in item.items() if v is not None})
        return cleaned[:12]

    suggestions = _clean_list(raw.get("suggestions"), {"issue", "fix"}) or heuristic["suggestions"]
    deviations = _clean_list(raw.get("style_deviations"), {"dimension", "expected", "observed"})

    overall_score = weighted_score(dimensions)
    raw_overall = raw.get("overall") if isinstance(raw.get("overall"), dict) else {}
    summary = str(raw_overall.get("summary") or heuristic["overall"]["summary"]).strip()

    return {
        "genre": genre,
        "overall": {"score": overall_score, "grade": grade_for(overall_score), "summary": summary},
        "dimensions": dimensions,
        "suggestions": suggestions,
        "style_deviations": deviations,
        "ai_tell_flags": features["ai_tell_flags"],
        "features": features,
        "disclaimer": DISCLAIMER,
        "engine": raw.get("engine") or "llm",
    }


# ---------------------------------------------------------------------------
# 对外主流程
# ---------------------------------------------------------------------------

def evaluate_document(
    db: Session,
    *,
    user_id: str,
    document: models.Document,
    style: models.StyleProfile | None,
    writing_task: models.WritingTask | None = None,
    trigger: str = "auto",
) -> models.ArticleEvaluation:
    """对一篇文档执行鉴评并落库。调用方需保证 genre 已通过 is_supported_genre 校验。"""
    requirements: dict[str, Any] = {}
    if writing_task is not None and isinstance(getattr(writing_task, "requirements", None), dict):
        requirements = dict(writing_task.requirements or {})
    if writing_task is not None:
        requirements.setdefault("title", writing_task.title)
        requirements.setdefault("brief", writing_task.brief)

    features = extract_features(
        document.content,
        target_length=str(requirements.get("target_length") or ""),
        must_include=str(requirements.get("must_include") or ""),
    )
    heuristic = build_heuristic_report(features, genre=document.genre)

    eval_tpl = get_active_prompt_template(db, PURPOSE_ARTICLE_EVALUATION)
    model_result = ModelGateway().generate(
        messages=_build_judge_messages(
            text=document.content,
            genre=document.genre,
            style_profile=style.profile if style else {},
            requirements=requirements,
            features=features,
            system_prompt=eval_tpl.system_prompt if eval_tpl else None,
        ),
        purpose="article_evaluate",
        fallback=json.dumps(heuristic, ensure_ascii=False),
    )
    report = normalize_report(
        parse_report_json(model_result.content),
        heuristic=heuristic,
        features=features,
        genre=document.genre,
    )

    previous = db.scalar(
        select(func.count())
        .select_from(models.ArticleEvaluation)
        .where(models.ArticleEvaluation.document_id == document.id)
    )
    evaluation = models.ArticleEvaluation(
        id=models.new_id("eval"),
        user_id=user_id,
        document_id=document.id,
        writing_task_id=writing_task.id if writing_task else None,
        genre=document.genre,
        revision=int(previous or 0) + 1,
        overall_score=report["overall"]["score"],
        grade=report["overall"]["grade"],
        report=report,
        trigger=trigger,
        model_provider=model_result.model_provider,
        model_name=model_result.model_name,
        input_token_count=model_result.input_token_count,
        output_token_count=model_result.output_token_count,
    )
    db.add(evaluation)
    db.add(
        models.ModelUsageLog(
            id=models.new_id("usage"),
            user_id=user_id,
            purpose="article_evaluate",
            model_provider=model_result.model_provider,
            model_name=model_result.model_name,
            input_token_count=model_result.input_token_count,
            output_token_count=model_result.output_token_count,
        )
    )
    db.commit()
    db.refresh(evaluation)
    return evaluation


def latest_evaluation(
    db: Session,
    *,
    user_id: str,
    writing_task_id: str | None = None,
    document_id: str | None = None,
) -> models.ArticleEvaluation | None:
    stmt = select(models.ArticleEvaluation).where(models.ArticleEvaluation.user_id == user_id)
    if writing_task_id:
        stmt = stmt.where(models.ArticleEvaluation.writing_task_id == writing_task_id)
    if document_id:
        stmt = stmt.where(models.ArticleEvaluation.document_id == document_id)
    stmt = stmt.order_by(
        models.ArticleEvaluation.created_at.desc(),
        models.ArticleEvaluation.revision.desc(),
    )
    return db.scalars(stmt).first()


def evaluation_to_dict(evaluation: models.ArticleEvaluation) -> dict[str, Any]:
    return {
        "id": evaluation.id,
        "document_id": evaluation.document_id,
        "writing_task_id": evaluation.writing_task_id,
        "genre": evaluation.genre,
        "revision": evaluation.revision,
        "overall_score": float(evaluation.overall_score),
        "grade": evaluation.grade,
        "trigger": evaluation.trigger,
        "report": evaluation.report,
        "model_name": evaluation.model_name,
        "created_at": evaluation.created_at.isoformat(),
    }


def evaluation_summary(evaluation: models.ArticleEvaluation) -> dict[str, Any]:
    """给生成接口返回的轻量摘要，避免一次塞入完整报告。"""
    report = evaluation.report or {}
    return {
        "id": evaluation.id,
        "overall_score": float(evaluation.overall_score),
        "grade": evaluation.grade,
        "summary": (report.get("overall") or {}).get("summary", ""),
        "suggestion_count": len(report.get("suggestions") or []),
    }
