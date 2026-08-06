# 个人风格写作 SaaS 术语表

本文件只记录项目业务术语，不记录实现方案。

## Language

**Demo User**:
早期 MVP 中用于打通个人写作闭环的固定演示用户。MVP1.1 已补真实个人用户系统，Demo User 只保留为开发和测试辅助，不作为正常业务接口的未登录 fallback。
_Avoid_: 临时用户、测试账号、匿名用户

**User**:
登录产品并拥有个人作品库、风格库和写作文档的人。MVP1.1 使用用户名密码注册登录，并通过 `user_id` 隔离用户素材、风格和文档。
_Avoid_: Account、Customer

**Organization**:
未来购买或管理一组个人用户的组织，例如作家协会、写作机构、公司或工作室。MVP1 只预留组织入口，不提供组织注册、子账号或共享余额。
_Avoid_: Tenant、Team

**Material**:
用户上传或粘贴的原始作品文本，例如散文、故事、小说、剧本、诗歌、杂文或随笔。Material 是风格分析的输入。
_Avoid_: 素材片段、训练数据

**Material Paragraph**:
从 Material 中解析出的自然段。Material Paragraph 用于统计、预览和风格分析，不等同于 RAG 检索片段。
_Avoid_: Chunk、Segment

**Style Analysis Job**:
用户选择多篇风格相似的 Material 后发起的一次风格分析任务。任务产出待用户确认的 Style Profile 草案。
_Avoid_: 风格生成任务、训练任务

**Style Profile**:
系统从用户作品中抽取并由用户确认的结构化风格档案，包含语气、句式、节奏、意象、结构偏好和禁用表达等。只有已确认的 active Style Profile 才能用于正式写作。
_Avoid_: Prompt、模板、模型

**Style Library**:
某个 User 已确认 Style Profile 的集合。写作时用户从自己的 Style Library 中选择一个风格。
_Avoid_: 风格市场、公共风格库

**Writing Task**:
用户选择文体、Style Profile、主题和要求后发起的一次生成请求。Writing Task 的结果是一个 Writing Document。
_Avoid_: Prompt 请求

**Writing Document**:
系统生成或用户编辑后的作品容器。Writing Document 按自然段保存，支持后续段落级重写。
_Avoid_: 生成结果、文章字符串

**Document Paragraph**:
Writing Document 中可被单独选择和重写的自然段。重写某个 Document Paragraph 时，其他段落应保持不变。
_Avoid_: 块、编辑节点

**Paragraph Rewrite**:
用户对某个 Document Paragraph 提出修改意见后，系统只重写该自然段的动作。
_Avoid_: 全文重写、润色全文

**Model Usage Log**:
一次模型调用的用量记录，包含用途、模型、token 和估算成本。MVP1 只记录用量，不扣余额。
_Avoid_: 账本、扣费记录
