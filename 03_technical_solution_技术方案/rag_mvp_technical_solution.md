# RAG MVP 技术方案

## 结论

第一个 MVP 必须上 RAG。个人风格写作的核心卖点不是“能写文章”，而是“能按用户本人风格写”。如果没有 RAG 和风格档案，MVP 很容易退化成普通 AI 写作工具。

MVP 采用轻量方案：

- PostgreSQL + pgvector 存储向量片段。
- 模型官方 SDK 直连，通过自研 `ModelGateway` 封装。
- 自研 `StyleRetrieval` 模块完成摄取、切块、向量化、检索和重排。
- 自研显式写作状态机调用 `StyleRetrieval`，不把业务状态交给 LangChain/LlamaIndex。

## 总体链路

```text
用户上传素材
  ↓
MaterialIngestion：解析、清洗、去噪
  ↓
StyleProfileBuilder：抽取结构化风格档案
  ↓
Segmenter：按文体切块
  ↓
EmbeddingAdapter：向量化
  ↓
PostgreSQL + pgvector：存储片段、向量、元数据
  ↓
StyleRetrieval：按任务召回 3-8 个代表片段
  ↓
PromptComposer：拼装系统规则、文体规则、风格档案、召回片段、用户任务
  ↓
WritingOrchestrator：生成大纲、正文、审校、重写
```

## 模块接口

### `StyleRetrieval`

这是 MVP RAG 的核心模块。外部接口保持小，内部隐藏切块、embedding、pgvector 查询、过滤、重排和审计。

```python
class StyleRetrieval:
    def ingest_material(self, user_id: str, style_profile_id: str, source: MaterialSource) -> str:
        ...

    def rebuild_profile_index(self, style_profile_id: str) -> IndexBuildResult:
        ...

    def retrieve_examples(self, style_profile_id: str, writing_spec: WritingSpec) -> list[StyleExample]:
        ...
```

调用方只关心 `retrieve_examples()` 返回哪些风格例子，不关心底层是 pgvector、Qdrant、Milvus 还是 DashVector。将来换向量库时，只替换这个模块内部实现。

### `PromptComposer`

负责把可控上下文拼成模型输入：

```python
class PromptComposer:
    def compose_draft_prompt(
        self,
        writing_spec: WritingSpec,
        style_profile: StyleProfile,
        style_examples: list[StyleExample],
    ) -> PromptBundle:
        ...
```

Prompt 中必须声明：召回片段只用于学习表达节奏和风格，不得复制原句，不得泄露用户素材。

### `ModelGateway`

负责模型供应商隔离：

```python
class ModelGateway:
    def generate(self, purpose: str, prompt: PromptBundle) -> GenerationResult:
        ...

    def embed(self, purpose: str, texts: list[str]) -> list[EmbeddingVector]:
        ...
```

模型 ID、超时、价格、最大 token 和回退顺序必须配置化，不能写死在业务代码里。

## 数据表草案

### `materials`

```sql
create table materials (
  id uuid primary key,
  tenant_id uuid not null,
  user_id uuid not null,
  style_profile_id uuid not null,
  title text,
  genre text not null,
  source_type text not null,
  oss_key text,
  raw_text_hash text not null,
  consent_for_training boolean not null default false,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);
```

### `material_segments`

```sql
create table material_segments (
  id uuid primary key,
  tenant_id uuid not null,
  user_id uuid not null,
  style_profile_id uuid not null,
  material_id uuid not null references materials(id),
  genre text not null,
  segment_index int not null,
  content text not null,
  summary text,
  tags jsonb not null default '{}'::jsonb,
  embedding vector,
  usable_for_retrieval boolean not null default true,
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);
```

### `retrieval_events`

```sql
create table retrieval_events (
  id uuid primary key,
  tenant_id uuid not null,
  user_id uuid not null,
  writing_task_id uuid not null,
  style_profile_id uuid not null,
  query_text text not null,
  selected_segment_ids uuid[] not null,
  retrieval_config jsonb not null,
  created_at timestamptz not null default now()
);
```

## 切块策略

| 文体 | MVP 切块方式 |
|---|---|
| 文章 | 按自然段切；短段合并，长段再切 |
| 散文 | 按自然段和意象段落切，保留标题与情绪标签 |
| 小说 | 按章节、场景、段落保存层级，生成时优先同章节/同人物上下文 |
| 诗歌 | 按整首和小节保存，不把单句切得太碎 |

建议每个 chunk 控制在 `300-800` 中文字。极短片段只适合作为风格标签，不一定进入向量检索。

## 检索策略

MVP 使用“三步检索”：

1. 根据用户任务生成检索 query。
2. pgvector Top K 检索，强制过滤 `tenant_id`、`style_profile_id`、`genre`、`deleted_at is null`。
3. 规则重排，优先同文体、代表作、主题相近、风格标签匹配的片段。

最终进入 Prompt 的片段控制在 `3-8` 段，避免原文过多导致照抄、泄露或 token 成本失控。

## 安全与隔离

- 租户过滤必须在数据库查询层完成。
- 删除素材后，对应片段必须不再召回。
- 模型 Prompt 不得包含其他用户素材。
- 日志只记录片段 ID、hash、token、模型和成本，避免记录完整原稿。
- 用户素材默认不用于训练；训练或微调需要单独授权。

## MVP 验收标准

- `Style Profile + RAG` 输出在盲测中明显优于通用模型直出。
- A 用户不能检索到 B 用户素材。
- 删除素材后，对应向量片段不再进入召回。
- 每次生成可追踪召回片段、Prompt 版本、模型 ID 和成本。
- RAG 召回不会导致大段复制原文。
- 用户能编辑风格档案并看到生成变化。

## 升级条件

只有出现明确痛点时再升级：

- 文本块超过百万级、查询延迟不可接受：评估 Qdrant、Milvus、DashVector。
- 长篇小说上下文切分和复杂格式解析困难：评估 LlamaIndex。
- 多轮工具调用、外部搜索、复杂 Agent 协作成为主需求：评估 LangChain 或其他编排框架。
- RAG + Prompt + 审校仍无法稳定接近个人风格，并且有授权修改数据：评估 LoRA/SFT。

