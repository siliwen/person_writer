# 千问更新版 MVP 方案对齐结论

来源文件：`C:\Users\songw\Downloads\作家协会个人风格写作Agent项目方案（更新版）.docx`

评审日期：2026-08-04

## 结论

更新版已经和本项目当前 MVP 技术路线基本达成一致：

- MVP 必须上 RAG，用于验证“个人风格”是否成立。
- MVP 阶段采用 PostgreSQL + pgvector，不上 Milvus/Qdrant。
- RAG 编排先用模型官方 SDK + 自研轻量流程，不上 LangChain/LlamaIndex。
- MVP 阶段暂不微调，使用强 Prompt、结构化风格档案、RAG 召回和基础模型完成验证。
- 重点投入素材清洗、风格档案、Prompt 拼装和作家反馈，而不是重型框架。

## 仍需修正的表述

### 1. “上传素材仅用于训练个人专属模型”

这个表述对 MVP 不准确。MVP 阶段不训练模型，用户素材应表述为：

> 用户上传素材默认仅用于当前用户的风格档案、RAG 检索和生成参考；不得用于公共模型训练。若未来用于微调、LoRA 或专属模型训练，必须取得用户单独、明确授权。

### 2. “1-2 位作家内测”

如果这是作协定制 PoC，可以用 1-2 位作家启动。但如果目标是公网收费 SaaS，评测样本太少。建议拆成：

- PoC：1-2 位风格鲜明作家跑通闭环。
- MVP 效果评测：30-50 个任务覆盖文章、小说、散文、诗歌。
- 小规模公测：30-100 位种子用户。

### 3. “生产阶段默认 LangChain/LlamaIndex + Milvus/Qdrant”

不应写成必然升级路线。更准确的说法是：

- 长文摄取、复杂格式解析和上下文索引成为痛点时，评估 LlamaIndex。
- 多轮工具编排和复杂 Agent 交互成为痛点时，评估 LangChain 或其他编排框架。
- 向量片段超过百万级、QPS 明显增长、pgvector 查询成为瓶颈时，评估 Qdrant/Milvus/DashVector。

## 双方一致版 MVP 基线

| 领域 | 一致结论 |
|---|---|
| RAG | MVP 必须上 |
| 向量存储 | PostgreSQL + pgvector |
| 模型调用 | 百炼/Qwen 或其他官方 SDK 直连，通过自研 ModelGateway 封装 |
| 编排方式 | 自研显式写作状态机，不依赖 Dify/LangChain 隐藏状态 |
| 风格实现 | 结构化 Style Profile + 多租户 RAG + 用户反馈 |
| 微调 | MVP 暂不做 |
| 升级条件 | 有真实痛点和规模指标后再上重型框架或独立向量库 |

## 纳入正式方案

本结论已沉淀到：

- `D:\AI_talk\personal_writing_agent_saas\03_technical_solution_技术方案\rag_mvp_technical_solution.md`
- `D:\AI_talk\personal_writing_agent_saas\03_technical_solution_技术方案\architecture.md`
- `D:\AI_talk\personal_writing_agent_saas\README.md`

