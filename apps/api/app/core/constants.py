"""跨模块共享的常量。

集中放置，避免魔法字符串在多处散落、难以统一修改。
"""

# 自由写作（无风格生成）的产物不绑定任何用户风格档案，
# 而是挂在一个系统占位风格档案上：这样 documents.style_profile_id 仍满足
# NOT NULL 约束（避免 SQLite 下对既有表做 DROP NOT NULL 重建），
# 同时鉴评跳过逻辑可据此稳定识别「无风格」文章。
SYSTEM_FREE_WRITE_STYLE_ID = "system_free_write"

# 后台可配置的提示词模板用途标识。
PURPOSE_OPTIMIZE_PROMPT = "optimize_prompt"
PURPOSE_STYLE_ANALYSIS = "style_analysis"
PURPOSE_STYLE_WRITING = "style_writing"
PURPOSE_FREE_WRITING = "free_writing"
PURPOSE_ARTICLE_EVALUATION = "article_evaluation"
PURPOSE_REVISE = "revise"

# 全部可后台配置的提示词用途（用于 seed 与白名单校验）。
ALL_PURPOSES = (
    PURPOSE_OPTIMIZE_PROMPT,
    PURPOSE_STYLE_ANALYSIS,
    PURPOSE_STYLE_WRITING,
    PURPOSE_FREE_WRITING,
    PURPOSE_ARTICLE_EVALUATION,
    PURPOSE_REVISE,
)

# 用途标识 → 中文业务名称 / 说明（供后台展示，避免硬编码在 JSX）。
PURPOSE_LABELS: dict[str, str] = {
    PURPOSE_OPTIMIZE_PROMPT: "优化提示词",
    PURPOSE_STYLE_ANALYSIS: "分析文章风格",
    PURPOSE_STYLE_WRITING: "按风格编写文章",
    PURPOSE_FREE_WRITING: "无风格自由写作",
    PURPOSE_ARTICLE_EVALUATION: "文章鉴评",
    PURPOSE_REVISE: "无风格文章改写",
}
