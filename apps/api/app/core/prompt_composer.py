import json
from dataclasses import dataclass
from typing import Any

from app.core.generation_policy import GenerationMode, resolve_generation_policy


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
        "可继承的是抽象风格特征；必须避开原文痕迹。不要照搬原文人物、地名、事件、固定意象组合或标志性表达。",
        "```json",
        json.dumps(style_profile, ensure_ascii=False, indent=2),
        "```",
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
            "instruction": "只参考语气、节奏和观察方式，内容、意象、句式组织都要明显原创。",
        },
        "balanced": {
            "label": "平衡仿写",
            "instruction": "保留可感知的文风特征，但不得复用原文情节、人物、意象组合、标志性短语或段落结构。",
        },
        "close": {
            "label": "高度贴近",
            "instruction": "更贴近原作者的句法、节奏和表达习惯，但仍必须避免让结果像替换内容后的改写稿。",
        },
    }
    return options.get(normalized, options["balanced"])
