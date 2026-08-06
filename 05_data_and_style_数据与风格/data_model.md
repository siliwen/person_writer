# 数据模型草案

## 核心实体

| 实体 | 说明 |
|---|---|
| `users` | 用户账号 |
| `tenants` | 租户或工作空间 |
| `memberships` | 用户与租户关系 |
| `materials` | 用户上传的原始素材 |
| `material_segments` | 解析后的段落或片段 |
| `style_profiles` | 结构化风格档案 |
| `style_profile_versions` | 风格档案版本 |
| `writing_tasks` | 写作任务 |
| `writing_task_steps` | 状态机步骤 |
| `documents` | 生成作品 |
| `document_versions` | 作品版本 |
| `model_calls` | 模型调用记录 |
| `billing_accounts` | 用户额度账户 |
| `billing_ledger_entries` | 额度流水 |
| `safety_reviews` | 内容审核记录 |
| `user_feedback` | 用户评分和修改反馈 |

## 素材来源字段

`materials` 必须记录来源和授权状态，不能只保存正文。

建议字段：

- `source_type`：user_upload / organization_authorized / internal_original / open_license / public_domain。
- `source_url`：原始来源链接。
- `source_site`：来源站点。
- `author_name`：作者名。
- `license_name`：许可名称。
- `license_url`：许可说明链接。
- `rights_status`：授权状态。
- `allowed_for_eval`：是否允许评测。
- `allowed_for_rag`：是否允许 RAG 检索。
- `allowed_for_training`：是否允许训练。
- `authorization_document_id`：授权文件或授权记录 ID。

## 多租户隔离

所有与用户内容相关的数据必须包含：

- `tenant_id`
- `user_id`
- `visibility`
- `deleted_at`

向量检索必须在数据库层强制过滤 `tenant_id`，不能把租户过滤交给 Prompt 或前端。

## 风格档案字段

`style_profiles` 建议包含：

- `genre`：文体。
- `summary`：风格摘要。
- `tone`：语气。
- `sentence_rhythm`：句长和节奏。
- `vocabulary_preferences`：词汇偏好。
- `imagery_patterns`：意象偏好。
- `structure_patterns`：结构偏好。
- `narrative_viewpoint`：叙事视角。
- `do_rules`：应保留规则。
- `avoid_rules`：应避免规则。
- `forbidden_phrases`：禁用表达。
- `training_consent`：是否允许用于后续训练。
- `version`：版本号。

## 向量数据

`material_segments` 建议包含：

- 原文段落。
- 段落摘要。
- 文体标签。
- 主题标签。
- 风格标签。
- embedding 向量。
- 来源作品 ID。
- 是否可用于生成召回。
- 是否可用于训练。

## 数据隐私规则

- 用户原稿默认私有。
- 删除素材后，向量、缓存和派生片段也应进入删除流程。
- 日志中不记录完整原文，只记录必要 ID、长度、hash 和调用元数据。
- 未获授权的数据不得进入模型训练集。
- 对外分享链接必须短期有效或可撤销。
