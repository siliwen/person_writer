# 技术架构方案

## 推荐首发架构

```text
浏览器 / 移动 Web
  ↓ HTTPS
CDN + WAF
  ↓
Next.js 前端
  ↓
FastAPI 后端
  ├─ Auth / Tenant
  ├─ Billing Ledger
  ├─ Style Profile
  ├─ Writing Orchestrator
  ├─ Model Gateway
  ├─ Safety Gateway
  └─ Export Service
  ↓
RDS PostgreSQL + pgvector
  ↓
OSS 私有存储
  ↓
阿里云百炼/Qwen + Embedding
```

## MVP RAG 基线

第一个 MVP 必须包含 RAG，但采用轻量可控实现：PostgreSQL + pgvector、模型官方 SDK 直连、自研 `StyleRetrieval` 和显式写作状态机。Milvus/Qdrant、LangChain/LlamaIndex、LoRA/SFT 都作为后续升级选项，不进入 MVP 默认依赖。

详细方案见 `D:\AI_talk\personal_writing_agent_saas\03_technical_solution_技术方案\rag_mvp_technical_solution.md`。

## 技术选型

| 层 | 推荐 | 理由 |
|---|---|---|
| 前端 | Next.js + TipTap | Web 首发快，编辑器生态成熟 |
| 后端 | Python FastAPI | 调模型、文档解析、异步任务生态直接 |
| 写作编排 | 显式状态机 | 长文生成可恢复、可审计、可计费 |
| 数据库 | RDS PostgreSQL + pgvector | 交易数据和早期向量检索一体化 |
| 对象存储 | OSS 私有 Bucket | 原稿、附件、导出文件不公开暴露 |
| 队列 | Redis 队列或阿里云消息队列 | 长任务异步化，避免请求超时 |
| 模型 | 阿里云百炼/Qwen 主供应商 | 国内链路和合规落地更顺 |
| 内容安全 | 阿里云内容安全 + 业务规则 | 输入输出都需要治理 |
| 部署 | 函数计算 FC 起步 | MVP 少运维；稳定后再评估 ACK/ECS |

## 关键模块

### `WritingOrchestrator`

外部接口应保持小而稳定：

```text
create_task(user_id, task_spec) -> writing_task_id
run_next_step(writing_task_id) -> step_result
request_revision(writing_task_id, revision_spec) -> version_id
```

内部负责需求解析、检索、生成、大纲、分段、审校、重写、失败恢复和状态流转。调用方不应该知道每一步使用了几个模型或几次重试。

### `StyleProfile`

负责把原始素材变成可使用的个人风格资产：

```text
ingest_material(user_id, file_or_text) -> material_id
build_profile(user_id, material_ids, genre) -> style_profile_id
retrieve_examples(style_profile_id, writing_spec) -> style_examples
```

它必须内置租户隔离，不允许调用方自己拼过滤条件。

### `ModelGateway`

统一模型供应商接口：

```text
generate(model_purpose, messages, constraints) -> generation_result
embed(texts, embedding_purpose) -> vectors
rerank(query, candidates) -> ranked_candidates
```

模型 ID、价格、超时、最大 token、回退顺序存数据库或配置中心，不写死在业务代码里。

### `BillingLedger`

所有收费动作通过账本，不允许业务模块直接改余额：

```text
estimate(task_spec) -> quote
reserve(user_id, quote) -> reservation_id
settle(reservation_id, actual_usage) -> ledger_entry_id
release(reservation_id, reason) -> ledger_entry_id
```

这样能处理超时、失败、重试、审核拦截和退款。

### `SafetyGateway`

统一做内容安全：

```text
moderate_input(user_id, content) -> safety_result
moderate_output(user_id, content) -> safety_result
```

命中策略不只有“拒绝”，还包括降级、人工复核、隐藏分享、禁止导出和申诉。

## 部署阶段

| 阶段 | 方案 |
|---|---|
| MVP | FC 跑 API，RDS/OSS/Redis 托管服务，百炼 API |
| 付费公测 | 增加 WAF、审计日志、监控告警、成本看板 |
| 稳定增长 | 按账单决定迁移 ACK Serverless 或 ECS |
| 高并发长文 | 独立 worker 池、消息队列、分章节调度、缓存和限流 |

## 不建议首版使用 Dify 的原因

Dify 适合快速验证流程，但正式收费产品的核心状态包括账号、套餐、额度、支付、租户隔离、素材隐私、写作版本、审计、退款和跨模型回退。这些属于业务主系统，不应藏在低代码工作流里。可以把 Dify 保留为内部原型工具，但生产链路应由自有后端控制。
