# 个人风格写作 Agent SaaS 项目

更新时间：2026-08-04

本项目用于沉淀“面向公网收费的个人风格写作 Agent”产品与技术方案。目标是不使用 Dify 作为生产核心，而是自研 SaaS 应用层，接入云端大模型 API，为用户提供文章、小说、散文、诗歌等文体的个人风格生成、改写、审校与版本管理能力。

## 当前决策基线

- 产品定位：个人风格写作 SaaS，不只是聊天机器人。
- 首发市场假设：中国大陆用户为主，后续保留海外模型和海外部署扩展。
- 技术路线：自研 Web 应用 + 阿里云百炼/Qwen 模型 API + RDS PostgreSQL/pgvector + OSS + FC 起步。
- 关键能力：风格素材上传、结构化风格档案、多租户 RAG、显式写作状态机、版本保存、额度计费、内容安全、合规审计。
- 不采用：Dify 作为正式生产核心、首版私有 GPU 推理、首版微调/LoRA。

## 目录说明

| 目录 | 内容 |
|---|---|
| `00_overview_总览` | 项目章程、范围、核心决策 |
| `01_requirements_需求` | 产品需求、用户角色、MVP 范围 |
| `02_product_design_产品设计` | 前端信息架构和核心交互 |
| `03_technical_solution_技术方案` | 云架构、模块接口、部署选型 |
| `04_prompt_workflow_写作流程` | Agent 状态机、Prompt 分层、生成链路 |
| `05_data_and_style_数据与风格` | 数据模型、风格档案、RAG 与隐私隔离 |
| `06_testing_测试方案` | 效果评测、工程测试、上线门槛 |
| `07_ops_compliance_运维合规` | 公网安全、合规清单、内容治理 |
| `08_business_商业化` | 套餐、额度、支付、成本与毛利 |
| `09_milestones_里程碑` | 12 周落地计划 |
| `references_参考资料` | 参考链接与已有研究索引 |
| `tools` | MVP 前置工具；当前包含网页作品正文采集与 Word 导出工具 |

## 推荐阅读顺序

1. `00_overview_总览/project_charter.md`
2. `00_overview_总览/pre_start_clarification_checklist.md`
3. `CONTEXT.md`
4. `01_requirements_需求/product_requirements.md`
5. `03_technical_solution_技术方案/architecture.md`
6. `03_technical_solution_技术方案/rag_mvp_technical_solution.md`
7. `04_prompt_workflow_写作流程/writing_agent_workflow.md`
8. `06_testing_测试方案/evaluation_plan.md`
9. `06_testing_测试方案/mvp_eval_set_design.md`
10. `07_ops_compliance_运维合规/data_acquisition_policy.md`
11. `07_ops_compliance_运维合规/sample_acquisition_crawler_workflow.md`

## 已实现的前置工具

- 网页作品采集器：`tools/web_article_collector`
- 用途：输入公开网页网址，提取正文并预览，下载为 `.docx`，用于整理内部初试测评素材。
- 限制：不支持付费平台、会员内容，也不会绕过登录、验证码或反爬限制。
- 产物：点击“保存 Word”后，服务端直接把 `.docx` 保存到 `测评集/网页作品`，不调用浏览器下载。
- 启动：在工具目录运行 `start.ps1`，然后打开 `http://127.0.0.1:8765`。
## MVP 工程骨架

当前已开始搭建首版平台骨架：

- 前端：`apps/web`，Next.js + TipTap
- 后端：`apps/api`，FastAPI
- 默认生成路径：`style_prompt_only + 可编辑 Style Profile`
- RAG：只预留为文章/散文实验增强，诗歌/小说默认关闭

运行说明见：

- `03_technical_solution_技术方案/mvp_platform_scaffold.md`
