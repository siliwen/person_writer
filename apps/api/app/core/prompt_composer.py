import json
from dataclasses import dataclass
from typing import Any

from app.core.generation_policy import GenerationMode, resolve_generation_policy
from app.core.prompt_template_service import DEFAULT_FREE_WRITE_PROMPT


@dataclass(frozen=True)
class WritingTaskInput:
    genre: str
    task_type: str
    title: str
    brief: str
    target_length: str
    target_reader: str
    must_include: str
    must_avoid: str
    eval_focus: str
    style_intensity: str = "balanced"


@dataclass(frozen=True)
class ComposedPrompt:
    mode: GenerationMode
    rag_enabled: bool
    system_prompt: str
    user_prompt: str
    prompt_version: str
    policy_reason: str


def compose_prompt(
    *,
    task: WritingTaskInput,
    style_profile: dict[str, Any],
    requested_mode: GenerationMode | str | None = None,
    rag_snippets: list[str] | None = None,
    rag_experiment_enabled: bool = True,
) -> ComposedPrompt:
    policy = resolve_generation_policy(
        genre=task.genre,
        requested_mode=requested_mode,
        rag_experiment_enabled=rag_experiment_enabled,
    )
    prompt_version = "style_profile_rag_v2" if policy.rag_enabled else "style_prompt_only_v1"
    intensity = describe_style_intensity(task.style_intensity)
    system_prompt = (
        "你是个人风格写作 Agent。严格完成用户写作任务，不解释过程。"
        "Style Profile 是最高优先级；只能学习抽象风格机制，不得照搬用户素材、RAG 片段或真实作品原句。"
    )
    user_parts = [
        "## 写作任务",
        f"- 任务类型：{task.task_type}",
        f"- 文体：{task.genre}",
        f"- 标题/主题：{task.title}",
        f"- 需求：{task.brief}",
        f"- 目标长度：{task.target_length}",
        f"- 目标读者：{task.target_reader}",
        f"- 必须包含：{task.must_include}",
        f"- 必须避免：{task.must_avoid}",
        f"- 评测重点：{task.eval_focus}",
        f"- 风格贴近程度：{intensity['label']}",
        f"- 贴近程度执行规则：{intensity['instruction']}",
        "",
        "## Style Profile",
        "Style Profile 是最高优先级。请学习语气、节奏、结构、叙述距离、意象密度和收束方式；不要复制来源文本。",
        _no_copy_line(task.style_intensity),
        "```json",
        json.dumps(style_profile, ensure_ascii=False, indent=2),
        "```",
        "",
        f"【本档强度下的 Profile 生效范围】{intensity['scope']}",
    ]
    if policy.rag_enabled and rag_snippets:
        user_parts.extend(
            [
                "",
                "## RAG 实验增强",
                "以下片段只作为低权重风格机制证据，不是内容素材库。",
                "不要复制原句、专名、真实作品名或连续意象组合。",
                "\n\n".join(rag_snippets[:3]),
            ]
        )
    user_parts.extend(
        [
            "",
            "## 输出要求",
            "只输出正文。不要解释 prompt、不要列提纲、不要声明自己在模仿风格。",
        ]
    )

    return ComposedPrompt(
        mode=policy.mode,
        rag_enabled=policy.rag_enabled,
        system_prompt=system_prompt,
        user_prompt="\n".join(user_parts),
        prompt_version=prompt_version,
        policy_reason=policy.reason,
    )


def describe_style_intensity(value: str) -> dict[str, str]:
    normalized = (value or "balanced").strip().lower()
    options = {
        "light": {
            "label": "轻度参考",
            "instruction": (
                "仅把 Style Profile 当作「语气与节奏的大方向」参考。"
            "【硬性禁止】不得使用档案中的任何具体意象、母题、人物、食物词、标志性短语或句式结构；"
            "尤其禁止复用档案的标志性收束句式『人这一辈子，能有……就好』（连同『……就好』式结尾），"
            "也禁止『趁热吃/趁热喝』类短语——结尾必须由你自己另写，不得套用原文收束。"
                "必须写全新的内容、意象、词汇和句式。整体读起来要像「同主题但明显是另一个人写的」，越原创越好。"
            ),
            "scope": (
                "本次仅以该 Profile 的『语气、节奏、句式结构』为参考；"
                "其 topic_boundary（题材边界）、标志性收束规则与具体意象建议【不生效】，"
                "请勿复用其母题、题材或签名式收束。"
            ),
        },
        "balanced": {
            "label": "平衡仿写",
            "instruction": (
                "保留可感知的文风特征：句法节奏、语气、常用修辞都要像原作者。"
            "但你必须重新设定一个与档案【不同的】温暖日常场景与人物（如档案写母亲冬夜煮食，你就换别的亲属或朋友的另一种温暖小事，或换一种不重样的日常食物），"
            "【硬性要求】严禁使用档案里的具体意象组合（豆腐摊/热食/母亲/趁热吃等），不得逐字复用标志性短语（如「趁热吃」）或具体专名（「母亲」须改泛称），"
                "收束须用你自己的句式，不能套用「人这一辈子，能有……就好」。"
                "句式在你的自主组织与原作风味之间取平衡——读起来能明确认出风格，但不像改写稿。"
            ),
            "scope": (
                "该 Profile 全部特征生效；题材母题仅作『类型』参考，"
                "标志性收束与标志性短语可借鉴风格但须换成你自己的表达，不得逐字照搬。"
            ),
        },
        "close": {
            "label": "高度贴近",
            "instruction": (
                "尽可能逼近 Style Profile 中的量化特征：平均句长、短句比、句式结构都要向档案数值靠拢；"
            "【硬性要求】必须锁定并复用档案的【核心意象组合】（如豆腐摊/热食/母亲/趁热吃），逐字复用其标志性短语与收束方式，"
            "并复用参考中的具体词汇（如「母亲」）。只替换最表层的事件细节，读起来应高度接近原作者真实手笔。"
                "仅确保不是把原文替换内容后的改写稿即可。"
            ),
            "scope": (
                "该 Profile 全部生效，尤其 topic_boundary 与收束方式【必须严格遵循、逐字复用标志性短语】；"
                "平均句长、短句比须向 Profile 中的数值靠拢。"
            ),
        },
    }
    return options.get(normalized, options["balanced"])


def _no_copy_line(style_intensity: str) -> str:
    """系统级「不得照搬」约束按档位放宽：close 允许并强制逐字复用标志性短语与收束。"""
    key = (style_intensity or "balanced").strip().lower()
    if key == "close":
        return (
            "可继承的是抽象风格特征；除本档强制逐字复用的标志性短语与收束方式外，"
            "其余原文痕迹仍须避开，不得照搬其余原文人物、地名、事件或固定意象组合。"
        )
    return "可继承的是抽象风格特征；必须避开原文痕迹。不要照搬原文人物、地名、事件、固定意象组合或标志性表达。"


def compose_free_prompt(
    *,
    task: WritingTaskInput,
) -> ComposedPrompt:
    """自由写作（无风格生成）的提示词拼装。

    不绑定任何用户风格档案：system_prompt 使用通用写作要求（可由后台覆盖的
    DEFAULT_FREE_WRITE_PROMPT 同款语义），user_prompt 仅携带本次写作任务要素。
    """
    policy = resolve_generation_policy(
        genre=task.genre,
        requested_mode=GenerationMode.STYLE_PROMPT_ONLY,
    )
    system_prompt = DEFAULT_FREE_WRITE_PROMPT
    user_parts = [
        "## 写作任务",
        f"- 任务类型：{task.task_type}",
    ]
    if task.genre and task.genre != "不限":
        user_parts.append(f"- 文体：{task.genre}")
    user_parts.extend([
        f"- 标题/主题：{task.title}",
        f"- 需求：{task.brief}",
    ])
    if task.target_length and task.target_length != "按需求":
        user_parts.append(f"- 目标长度：{task.target_length}")
    user_parts.extend([
        f"- 目标读者：{task.target_reader}",
        f"- 必须包含：{task.must_include}",
        f"- 必须避免：{task.must_avoid}",
        f"- 评测重点：{task.eval_focus}",
        "",
        "## 通用写作要求",
    ])
    if task.genre and task.genre != "不限":
        user_parts.append("严格按指定文体写作，不要混用其他文体特征。")
    else:
        user_parts.append("文体由需求自定，保持全文风格统一即可。")
    user_parts.extend([
        "避免 AI 常见套话、空泛抒情和宏大口号。",
        "使用自然段组织内容，保持可编辑性。",
        "只输出正文，不要解释 prompt、不要列提纲。",
        "",
        "## 输出要求",
        "只输出正文。不要解释 prompt、不要列提纲、不要声明自己在模仿风格。",
    ])
    return ComposedPrompt(
        mode=policy.mode,
        rag_enabled=False,
        system_prompt=system_prompt,
        user_prompt="\n".join(user_parts),
        prompt_version="free_write_v1",
        policy_reason="自由写作：不绑定用户风格档案，按通用写作要求生成",
    )
