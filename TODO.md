# 项目 TODO 与进度

> 项目：个人风格写作 Agent SaaS  
> 更新日期：2026-08-06  
> 状态约定：`[ ]` 未开始，`[-]` 进行中，`[x]` 已完成，`[!]` 需要决策或存在阻塞。

## 当前目标

MVP1 先不做真实注册、组织和余额，使用固定 Demo User 打通个人风格写作闭环：

Demo User → 二选一开始：上传多篇相似作品并自动分析风格后确认保存，或直接选择已有风格 → 选择风格和贴近程度生成文章 → 在正文中按自然段原地重写。

## 阶段 0：评测与产品决策

- [x] 建立 `eval_sets/mvp_style_eval_v1/` 评测 harness。
- [x] 完成 `baseline_direct`、`style_prompt_only`、`style_profile_rag` 第一轮盲评。
- [x] 完成 `style_profile_rag_v2` 第二轮复评。
- [x] 确定 MVP 默认路径：`style_prompt_only + 可编辑 Style Profile`。
- [x] 确定 RAG 不作为 MVP1 默认路径，只作为文章/散文后续实验能力。

## 阶段 1：MVP1 基础工程

- [x] 初始化前端 Next.js 工作台。
- [x] 初始化后端 FastAPI、PromptComposer 和生成策略。
- [x] 引入 SQLAlchemy/Alembic 数据模型与迁移骨架。
- [x] 建立 MVP1 核心表：User、Material、MaterialParagraph、StyleAnalysisJob、StyleProfile、Document、DocumentParagraph、WritingTask、ModelUsageLog。
- [x] 固定 Demo User；MVP1 不做真实个人注册登录。
- [x] 组织注册接口仅预留，返回 not implemented。
- [ ] 接入正式 PostgreSQL 实例并执行 Alembic migration。
- [ ] 接入 OSS 私有文件存储。

## 阶段 2：作品与风格资产

- [x] 支持批量上传 `.txt/.md/.docx`。
- [x] 实现作品自然段解析和保存。
- [x] 支持多篇作品组成一次 Style Analysis Job。
- [x] 输出待用户确认的 Style Profile 草案。
- [x] 支持用户编辑、命名并确认 Style Profile。
- [x] 已确认风格进入个人 Style Library。
- [x] 增强风格分析为 Style Profile v2：先做客观统计，再用千问六维提示词生成结构化风格档案，模型异常时回退到本地 v2 草案。
- [ ] 继续评测 Style Profile v2 对生成文章风格相似度的提升，并据此调优分析 Prompt。

## 阶段 3：风格写作与段落重写

- [x] 写作时从个人 Style Library 选择 active Style Profile。
- [x] 未确认风格不能用于正式写作。
- [x] 支持 7 类文体入口：散文、故事、小说、剧本、诗歌、杂文、随笔。
- [x] 默认使用 `style_prompt_only` 生成路径。
- [x] 写作任务支持风格贴近程度：轻度参考、平衡仿写、高度贴近；默认平衡仿写并要求避免照搬原文痕迹。
- [x] 生成结果按自然段保存为 Writing Document。
- [x] 支持点击自然段打开弹窗，只重写指定自然段。
- [x] 支持删除已保存风格；MVP1 使用软删除，已生成文章不受影响。
- [x] 记录模型、token、用途和估算成本；MVP1 不做余额扣费。
- [ ] 接入真实 Qwen 生成链路的错误展示、超时和重试策略。

## 阶段 4：前端工作台

- [x] 页面改为 MVP1 信息架构：工作台、作品上传、风格分析、风格确认、风格库、新建写作、段落重写。
- [x] 页面动线改为纵向单线流程：上传并分析风格 → 确认风格 → 生成与修改文章。
- [x] 页面动线修正为“创建新风格 / 使用已有风格”二选一入口，写作区只依赖已选择风格。
- [x] 上传作品后自动触发风格分析；主页面不再展示作品库或作品勾选列表。
- [x] 生成文章和段落修改合并到同一区域；自然段保持连续阅读形态，hover 高亮后点击弹窗填写修改意见并重写。
- [x] 显示“当前为 Demo 用户模式”。
- [x] 组织和余额在 MVP1 中不进入主流程。
- [x] 增加更完整的加载态和错误态设计：上传、风格分析、风格确认、文章生成、段落重写均有动作级 loading 和局部错误提示。
- [ ] 增加文档导出入口；MVP1 先支持 Markdown/纯文本。

## 已知决策

- MVP1 不做真实个人注册登录；先用固定 Demo User 打通核心闭环。
- MVP1 不做组织正式注册、组织子账号、组织共享余额。
- MVP1 不做余额、充值、冻结、扣费；只记录 token 与估算成本。
- PostgreSQL 是正式数据层目标；本地无配置时允许 SQLite fallback 方便开发验证。
- 千问/DashScope 是默认模型供应商；当前 ModelGateway 支持 mock fallback，避免无 Key 时无法演示。
- 授权/版权确认流程按用户要求在当前内部 MVP 中跳过。

## 下一步

1. [x] 已启动后端和前端，并通过真实 `.docx` 跑通上传→分析→确认→写作→段落重写。
2. 配置真实 PostgreSQL，执行 Alembic migration。
3. 完善 Qwen 真实调用的错误处理和前端反馈。
4. 补充导出、风格编辑等工作台细节。

## 2026-08-05 验证记录

- [x] 修复通过局域网/Codex 面板访问前端时，上传 API 因 CORS/API host 不一致导致浏览器拦截的问题。
- [x] 补充 `.docx` 上传解析测试和局域网前端 origin CORS 预检测试。
- [x] 真实 HTTP 闭环验证：上传真实 `.docx` → 风格分析 → 确认风格 → 生成文章 → 指定自然段重写。

## 2026-08-05 产品体验修正

- [x] 第 3 步新增“目标字数 / 篇幅”输入，生成时传入模型任务参数。
- [x] 第 3 步旁新增“生成文章预览”，生成成功后用户可立即看到全文、段落数和约字数。
- [x] 第 4 步明确段落级修改方式：选中自然段 → 输入修改意见 → 只重写该段。

## 2026-08-05 生成质量修复

- [x] 修复 mock/fallback 写作生成器输出“写作说明/段落提示”而不是正文文章的问题。
- [x] 新增回归测试：fallback 生成内容不得包含“这是按…生成”“第二个自然段”“必须包含”“避免：”等说明模板词。

## 2026-08-05 Qwen 调用确认

- [x] 确认此前点击“生成文章”实际走的是 `mock-writing`，没有请求千问；原因是 `auto` 模式静默 fallback。
- [x] 修复 `.env.local` 首行 UTF-8 BOM 导致 `MODEL_GATEWAY_MODE=qwen` 未被读取的问题。
- [x] 新增 `/v1/model-status`，前端状态栏显示当前模型模式、模型名和 fallback 行为。
- [x] 当前后端已切换为 Qwen 强制模式：`mode=qwen`，`fallback_behavior=disabled`。
- [!] 非沙箱网络真实请求 DashScope 已到达平台，但返回 `HTTP 401 Unauthorized`；需要更换有效 DashScope API Key 或确认 Key 权限。

## 2026-08-05 Qwen Key 覆盖问题修复

- [x] 确认 `.env.local` 中有效 DashScope Key 与 `ModelGateway` 实际读到的 Key 不一致：外部环境变量覆盖了项目配置。
- [x] 调整 `ModelGateway` 读取优先级：项目 `.env.local` 优先，系统环境变量仅作为 fallback。
- [x] 真实连通测试通过：`provider=alibaba_bailian`，`model=qwen-plus`，返回“连通成功”。
- [x] 测试套件默认 monkeypatch 模型网关，避免单元测试误打真实千问接口。

## 2026-08-05 Style Profile v2 风格提取升级

- [x] 新增 `style_profile_builder.py`，风格分析改为“文本统计 + 六维文风诊断 Prompt + 结构化 JSON”。
- [x] 风格分析 Prompt 覆盖：词汇与句法、修辞与表达、叙事与结构、情感与基调、题材与素材、时代与语体。
- [x] Style Profile v2 增加 `source_stats`、`lexical_style`、`syntax_style`、`rhetoric_style`、`narrative_style`、`emotional_tone`、`topic_boundary`、`language_period_style`、`generation_rules`、`evidence_map`、`split_recommendation`。
- [x] 前端风格确认区新增“文风诊断摘要”和关键写作规则展示，完整 JSON 仍可编辑。
- [x] 修正根目录 `npm run test:api` 使用项目 `.venv` 和 pytest，避免错误 Python 解释器缺依赖导致测试失败。
- [x] 新增 `display_report`：把机器结构化风格档案转换成普通用户能判断的大白话六维报告。
- [x] 前端风格确认区改为优先展示六个维度的人话诊断、写作规则和判断依据；完整 Style Profile JSON 默认折叠到高级区。
- [x] 修复旧格式风格草案兼容问题：即使后端返回旧 Style Profile 字段，前端也能生成六维大白话报告，不再只显示空标题。

## 2026-08-06 风格分析展示修正

- [x] 中文素材的风格分析展示内容强制中文化；除英文原文场景外，不向用户展示英文术语、英文括注或中英混写。
- [x] 后端风格分析 Prompt 增加输出语言约束：中文输入时，除 JSON 字段名外，所有分析结论必须使用中文。
- [x] 后端 `display_report` 增加清洗逻辑：中文来源下会过滤模型返回的英文分析词。
- [x] 前端风格分析区从“六维卡片 + 三个规则卡片”的九块布局，改为单份连续报告：维度标题 + 描述内容依次排列。
- [x] “完整 Style Profile JSON”入口文案改为“完整风格档案数据”，避免普通用户看到不必要的英文术语。

## 2026-08-06 按钮状态与重复保存修复

- [x] 修复“确认并保存到风格库”二次点击/重试问题：同一个 Style Analysis Job 重复确认时幂等返回已有 Style Profile。
- [x] 增加同一用户 active 风格名称重复校验；重复时返回中文提示“风格名称已存在，请换一个名称。”。
- [x] 前端统一按钮状态：上传、分析、保存、生成、重写分别显示当前动作 loading 文案。
- [x] 前端增加局部错误提示：每一步的校验和接口错误显示在对应操作区域，不再只依赖顶部状态栏。
- [x] 生成文章失败时不再提前增加版本号；失败后明确提示右侧仍显示上一次文章。
- [x] 段落重写增加空修改意见校验，避免无效请求。

## 2026-08-06 单线流程与风格贴近程度

- [x] 主工作台从左右网格改为纵向单线流程，减少用户左右来回查看。
- [x] 主工作台增加开始方式二选一：上传参考作品创建新风格，或直接使用已有风格写文章。
- [x] “上传并解析”和“生成风格草案”合并为一个动作：上传作品并分析风格。
- [x] 主工作台移除作品库展示；素材管理后续如需要应拆到独立页面。
- [x] 主工作台保留已保存风格选择入口；已有风格可直接进入写作。
- [x] 第 3 步改为“生成与修改文章”，生成结果和段落重写入口放在一起。
- [x] 每个自然段下方原地填写修改意见并重写，重写后全文在同一区域更新。
- [x] 新增 `style_intensity` 写作参数，PromptComposer 将轻度参考、平衡仿写、高度贴近转成模型执行规则。
- [x] Prompt 增加反照搬约束：只学习抽象风格机制，不复用原文人物、地名、事件、固定意象组合或标志性表达。

## 2026-08-06 段落重写交互与风格删除

- [x] 段落重写从“每段下方常驻输入框”改为“正文连续展示 + 段落 hover 高亮 + 弹窗填写修改意见”，降低文章被切碎的阅读感。
- [x] 新增已保存风格删除入口；后端使用软删除，删除后不再出现在风格库，也不能再用于新写作。
- [x] 已生成文章不依赖风格列表展示，删除风格不会影响历史生成结果。
- [x] 新增 API 回归测试覆盖风格软删除、列表隐藏、删除后禁止写作和重复删除幂等。
