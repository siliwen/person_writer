# 首页自由写作与优化提示词 - 技术方案

> 状态：方案锁定，待开发（2026-08-12）
> 关联产品设计：`02_product_design_产品设计/free_write_home_design.md`

## 一、数据模型：prompt_templates

新增 `PromptTemplate` 模型，用于存储可后台配置的系统提示词（优化提示词等）。

```sql
CREATE TABLE prompt_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX ux_prompt_templates_purpose_active
ON prompt_templates(purpose) WHERE is_active = 1;
```

设计约束：

- `purpose` 是业务唯一标识（如 `optimize_prompt`、`free_write_prompt`）。
- 同一 `purpose` 最多一个 `is_active = 1` 模板（partial unique index 保证）。
- 后台当前只暴露 `optimize_prompt` 这一个用途；`purpose` 字段保留为未来扩展（如 `free_write_prompt` 后台化）留口。
- `Boolean` / `TEXT` / partial unique index 在 SQLite 与 PostgreSQL 下语义一致，迁移 PG 无需 schema 改造。
- migration 用 SQLAlchemy 声明 + Alembic `op.create_table`，不写数据库特定 DDL。

## 二、超管模板 API

仅 `is_admin` 可访问，挂载在现有 AdminPanel 的「提示词模板」Tab。

| 方法 | 端点 | 说明 |
|---|---|---|
| GET | `/v1/admin/prompt-templates` | 列表 |
| GET | `/v1/admin/prompt-templates/{id}` | 详情 |
| POST | `/v1/admin/prompt-templates` | 新建 |
| PATCH | `/v1/admin/prompt-templates/{id}` | 修改 name / system_prompt / is_active |
| DELETE | `/v1/admin/prompt-templates/{id}` | 删除 |
| POST | `/v1/admin/prompt-templates/{id}/set-active` | 设为启用（同时停用同 purpose 其他模板） |

请求示例：

```json
POST /v1/admin/prompt-templates
{
  "name": "优化提示词",
  "purpose": "optimize_prompt",
  "system_prompt": "你是墨小小写作助手的「需求优化器」……"
}
```

响应：

```json
{
  "id": "pt_xxx",
  "name": "优化提示词",
  "purpose": "optimize_prompt",
  "system_prompt": "……",
  "is_active": true,
  "created_at": "2026-08-12T10:00:00"
}
```

后台 UI 约束：

- 只暴露 `optimize_prompt` 模板，不展示 purpose 下拉（固定 `optimize_prompt`）。
- 列表展示：名称、用途、启用状态、system_prompt 预览。
- 新建/编辑表单：名称、system_prompt 大文本框、是否启用开关。
- 保存时校验：同 purpose 只能有一个启用。

## 三、优化接口：POST /v1/optimize-prompt

请求：

```json
{ "prompt": "写点关于秋天的事" }
```

响应：

```json
{ "optimized_prompt": "写一篇关于初秋街景与人事变迁的散文，约1200字……" }
```

实现：

```python
template = get_active_prompt_template(db, "optimize_prompt")
system_prompt = template.system_prompt if template else DEFAULT_OPTIMIZE_PROMPT

optimized = ModelGateway().generate(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.prompt},
    ],
    purpose="optimize_prompt",
    fallback=lambda: request.prompt,   # 模型失败时返回原文
)
# 输入审核不通过 → 400；成功扣 1 积分
```

积分：固定扣 1 积分，`charge(db, user, OPTIMIZE_PROMPT, points=1, ...)`。记录 `model_usage_log`（purpose=optimize_prompt）用于成本核算。

输入审核：端点入口复用现有内容安全审核，不通过返回 400。

## 四、自由生成：POST /v1/writing-tasks 扩展

当前逻辑：`if request.style_profile_id: ... else: raise 400`。改为支持空值：

```python
if request.style_profile_id:
    # 原风格生成路径
elif request.style_profile_id == "":
    # 新增自由写作路径
    target_chars = parse_target_length_chars(request.task.target_length)
    points = validate_and_price(db, user, ARTICLE_GENERATION, target_chars=target_chars)
    created = create_free_writing(db, user_id=user.id, task_input=..., requested_mode=...)
    charge(db, user, ARTICLE_GENERATION, points, ...)
    auto = _run_auto_evaluation(...)   # 此处需跳过无风格文档
    return body
else:
    raise HTTPException(status_code=400, detail="style_profile_id is required")
```

### 4.1 create_free_writing

复制 `create_writing` 骨架，差异：

- `style_profile_id=None`。
- 调用 `compose_free_prompt`（不带 Style Profile）。
- `_fallback_article` 不需要 style_name。
- `document.style_profile_id` 设为 `None`（需确认 `documents.style_profile_id` 是否允许 NULL；如当前非空，改为 nullable 或用系统占位 ID）。

### 4.2 compose_free_prompt

新增函数，参数 `style_profile` 可选。当为空时，不拼接 `## Style Profile`，改为拼接 `## 通用写作要求`：

```text
## 通用写作要求
- 严格按指定文体写作，不要混用其他文体特征。
- 避免 AI 常见套话、空泛抒情和宏大口号。
- 使用自然段组织内容，保持可编辑性。
- 只输出正文，不要解释 prompt、不要列提纲。
```

### 4.3 自动鉴评跳过

自动鉴评逻辑中判断：若 `document.style_profile_id` 为空，直接返回 `None`（自由写作暂不鉴评）。手动鉴评接口对无风格文档返回 422，提示「自由写作文章暂不支持鉴评」。

## 五、默认兜底 Prompt（代码内保留）

防止后台误删或没配置时服务不可用：

```python
DEFAULT_OPTIMIZE_PROMPT = """你是墨小小写作助手的「需求优化器」。用户会给你一句简短的写作想法，你需要把它扩展成一段清晰、完整、可直接用于文章生成的写作需求描述。

要求：
1. 保留用户原始意图和主题，不要跑题或篡改核心意思。
2. 补全写作要素：明确文体、建议字数、内容基调、必须包含的元素、必须避免的元素。
3. 若用户已写明文体或字数，沿用其设定；未写明则根据主题合理推测（默认散文、约1200字）。
4. 输出为中文，一段连贯的自然语言，不使用 Markdown 标题、列表符号或编号。
5. 不要解释你的工作过程，不要替用户写文章正文，只优化"要写什么"的需求。"""

DEFAULT_FREE_WRITE_PROMPT = """你是通用写作助手。请严格按用户要求的文体、主题和长度写作。
- 避免 AI 常见套话、空泛抒情和宏大口号。
- 使用自然段组织内容，保持可编辑性。
- 只输出正文，不要解释 prompt、不要列提纲。"""
```

注意：自由写作通用要求当前不在后台管理，直接用 `DEFAULT_FREE_WRITE_PROMPT`；如未来要后台化，只需放开后台 UI 并读取 `free_write_prompt` 模板。

## 六、前端改动清单

| 文件 | 改动 |
|---|---|
| `apps/web/components/DashboardView.tsx` | 顶部新增 `FreeWriteBox`（textarea + 优化按钮 + 文体/字数/风格选择 + 生成按钮 + 文体 chip）；默认视图 dashboard |
| `apps/web/components/WritingWorkspace.tsx` | `currentView` 初值改 `"dashboard"`；新增自由写作生成逻辑（styleProfileId 为空）与优化按钮事件；生成后跳转 writing 视图 |
| `apps/web/components/WritingView.tsx` | 支持无风格状态；风格选择器显示「自由写作」选项 |
| `apps/web/components/AdminPanel.tsx` | 新增「提示词模板」Tab（仅 optimize_prompt） |
| `apps/web/lib/api.ts` | 新增 `fetchOptimizePrompt`、模板管理 API |
| `apps/web/app/globals.css` | 新增 free-write-box、优化按钮、优化高亮、回填边框样式 |

前端 state（FreeWriteBox）：

```ts
const [promptText, setPromptText] = useState("");
const [optimizing, setOptimizing] = useState(false);
const [optimized, setOptimized] = useState(false);
const [optimizeError, setOptimizeError] = useState("");
```

`handleOptimize`：校验非空 → 调 `fetchOptimizePrompt` → 回填 `promptText` → 标记 `optimized`；失败保留原文并提示。

## 七、开发顺序

1. `PromptTemplate` 模型 + migration（SQLite 兼容写法）。
2. 后端模板管理服务（`prompt_template_service`）+ 超管模板 API。
3. 超管后台 UI「提示词模板」Tab。
4. 后端 `POST /v1/optimize-prompt`（读取后台模板/默认兜底，扣 1 积分）。
5. 后端 `create_free_writing` + `compose_free_prompt` + writing-tasks 空 style_profile_id + 鉴评跳过。
6. 前端 `FreeWriteBox` + 优化按钮交互 + 占位符轮播。
7. 前端自由写作生成跳转 writing 视图（无风格状态）。
8. 浏览器 E2E 验证 + 后台模板切换测试（切换模板后优化结果随之变化）。

## 八、跨库兼容性说明

`prompt_templates` 表迁移 PostgreSQL 时：

- `Boolean`：SQLAlchemy ORM 层透明映射（SQLite 0/1 ↔ PG boolean）。
- partial unique index（`WHERE is_active=1`）：SQLite 与 PG 语法一致，Alembic migration 可直接复用。
- 无外键依赖，数据迁移（pgloader/导出导入）无需 schema 改造。
- 唯一约束：migration 不在 DDL 中写数据库特定语法。

结论：保留该表，迁移零成本；且已满足「超管后台改优化提示词无需改代码」的目标。
