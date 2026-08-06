# MVP Platform Scaffold

更新日期：2026-08-05

## 当前工程决策

首版 MVP 默认主路径：

`Style Profile + PromptComposer + Writing Task`

RAG 不作为默认生成路径。根据两轮评测结果：

- 文章/散文：RAG 可作为实验增强能力预留。
- 诗歌/小说章节：默认关闭 RAG，避免破坏节奏、留白、叙事推进和风格克制。
- LoRA/微调：不进入首版。

## 目录结构

```text
apps/
  api/                 FastAPI 后端
    app/core/          可测试的领域逻辑
    app/main.py        HTTP API
    tests/             后端行为测试
  web/                 Next.js + TipTap 前端
    app/               App Router 页面
    components/        写作工作台组件
```

## 已实现的第一条 vertical slice

后端：

- `resolve_generation_policy`
- `compose_prompt`
- `InMemoryWritingTaskService`
- `GET /healthz`
- `POST /v1/prompt/compose`
- `POST /v1/writing-tasks`
- `GET /v1/writing-tasks/{task_id}`

前端：

- 写作任务表单
- Style Profile JSON 编辑区
- TipTap 正文编辑器
- 生成模式选择
- RAG 策略展示
- 创建任务按钮，调用后端 `/v1/writing-tasks`

## 运行方式

后端：

```powershell
cd D:\AI_talk\personal_writing_agent_saas
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\apps\api\requirements-dev.txt
$env:PYTHONPATH='D:\AI_talk\personal_writing_agent_saas\apps\api'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir .\apps\api --reload
```

前端：

```powershell
cd D:\AI_talk\personal_writing_agent_saas
npm install
npm run dev:web
```

默认 API 地址：

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## 下一步

1. 把内存任务服务替换为 PostgreSQL 持久化。
2. 增加 `StyleProfile`、`Document`、`DocumentVersion`、`WritingTask` 数据表。
3. 接入 ModelGateway 调 Qwen。
4. 增加任务状态机：pending → composing_prompt → generating → completed / failed。
5. 增加用户空间和 tenant_id 隔离。
