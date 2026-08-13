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
