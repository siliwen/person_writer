# MVP 评测集设计

## 目标

评测集的目标不是证明模型“文笔好”，而是验证 MVP 的核心商业假设：

> `Style Profile + RAG` 是否能比普通大模型直出更接近用户本人风格，并且生成结果可用、可控、可审计。

## 评测规模

MVP 开工前先准备 `30-50` 个任务。建议首版用 `40` 个任务，结构清晰，人工评估压力可控。

| 文体 | 任务数 | 目的 |
|---|---:|---|
| 文章 | 10 | 验证观点表达、结构、标题、开头结尾 |
| 散文 | 10 | 验证情绪线、意象、节奏和叙述距离 |
| 诗歌 | 8 | 验证断句、意象、节奏和非模板化表达 |
| 小说章节 | 12 | 验证人物语气、场景描写、冲突推进和续写一致性 |

## 参与样本

建议第一轮至少准备 `5-8` 个 Writer 样本。每个 Writer 不需要覆盖所有文体，但每个文体至少要有 2 个 Writer。

每个 Writer 准备：

- 3-5 篇代表作，用于启动风格诊断。
- 总字数建议 8000 字以上。
- 标记文体、主题、创作时期、代表性强弱。
- 标记不希望模仿的旧作或失败样本。
- 明确素材仅用于本次 MVP 风格档案和 RAG 评测，不参与训练。

如果真实作家素材暂时不足，可以先用内部自有文章、团队成员原创文本或已获授权样本。不要用未授权名家作品做“个人风格”训练或展示。

不建议通过爬虫默认抓取现代作者作品作为评测样本。爬虫只能用于授权清晰、开放许可或公共领域数据源，并且必须记录来源、许可、采集时间和使用范围。具体规则见 `D:\AI_talk\personal_writing_agent_saas\07_ops_compliance_运维合规\data_acquisition_policy.md`。

如果通过爬虫采集样本，评测集只接收 `material_manifest.csv` 中 `allowed_for_eval=true` 的材料；RAG 只接收 `allowed_for_rag=true` 的材料。采集流程见 `D:\AI_talk\personal_writing_agent_saas\07_ops_compliance_运维合规\sample_acquisition_crawler_workflow.md`。

## 每个任务的结构

每个评测任务必须是一条结构化记录，而不是一句随意 Prompt。

建议字段：

```csv
task_id,writer_id,genre,style_profile_id,task_type,title,brief,target_length,target_reader,must_include,must_avoid,reference_material_ids,eval_focus,difficulty
```

字段说明：

| 字段 | 说明 |
|---|---|
| `task_id` | 任务编号，例如 `ART-001` |
| `writer_id` | 被评测的 Writer |
| `genre` | 文章、散文、诗歌、小说章节 |
| `task_type` | 新写、续写、改写、润色 |
| `brief` | 用户真实需求 |
| `target_length` | 目标字数或行数 |
| `target_reader` | 目标读者 |
| `must_include` | 必须包含的信息 |
| `must_avoid` | 必须避免的表达、主题或事实 |
| `reference_material_ids` | 可用于建档/RAG 的素材 |
| `eval_focus` | 本任务重点看什么 |
| `difficulty` | 1-5 |

## 任务示例

| task_id | 文体 | 任务 |
|---|---|---|
| ART-001 | 文章 | 用该 Writer 的风格写一篇 1200 字观点文，主题是“县城青年为什么重新重视附近生活” |
| ART-002 | 文章 | 将一段普通通知改写成该 Writer 的自媒体文章开头，要求不夸张、不标题党 |
| ESS-001 | 散文 | 写一篇 900 字散文，主题是“傍晚经过一条旧街”，要求克制、有画面感 |
| ESS-002 | 散文 | 输入“秋天”做意象发散，并生成一段该 Writer 风格的开篇 |
| POE-001 | 诗歌 | 写一首 16-24 行现代诗，主题是“旧照片”，避免空泛抒情 |
| POE-002 | 诗歌 | 将一段散文化文字改写成该 Writer 风格的短诗 |
| NOV-001 | 小说 | 根据人物卡续写 1200 字章节，重点验证人物语气和冲突推进 |
| NOV-002 | 小说 | 将一段普通对话改写成两个角色性格明显不同的对话 |

## 对照组设计

每个任务至少生成 3 个版本：

1. `baseline_direct`：通用模型直接根据任务生成。
2. `style_prompt_only`：只使用结构化 Style Profile，不使用 RAG 片段。
3. `style_profile_rag`：使用 Style Profile + RAG 召回片段。

如果预算允许，再加入：

- `provider_qwen`
- `provider_doubao`
- `provider_hunyuan`

评审时隐藏版本来源，避免人工偏见。

## 评分维度

采用 1-5 分制，每项都要有短评。

| 维度 | 评分问题 |
|---|---|
| 风格相似度 | 是否接近该 Writer 的语气、句式、节奏和表达习惯 |
| 任务完成度 | 是否满足主题、字数、结构、必须包含和必须避免 |
| 文体质量 | 是否符合文章/散文/诗歌/小说章节的文体要求 |
| 可修改成本 | 用户要改多少才能拿去用 |
| RAG 使用质量 | 是否合理吸收素材风格，而不是照抄 |
| AI 味控制 | 是否出现套话、空泛抒情、模板化转折 |
| 安全与版权 | 是否泄露原文、复制过多、涉及侵权或隐私 |

建议增加一个总评：

```text
是否可作为 MVP 可用输出：可用 / 修改后可用 / 不可用
```

## 通过门槛

进入正式 MVP 开发前，至少达到：

- `style_profile_rag` 在风格相似度上明显优于 `baseline_direct`。
- `style_profile_rag` 不出现大段照抄原文。
- 至少 60% 任务达到“修改后可用”或以上。
- 租户和素材隔离规则在测试中可验证。

进入小规模公测前，建议达到：

- 至少 70% 任务达到“修改后可用”或以上。
- 文章、散文、诗歌、小说四类都没有明显短板。
- 单任务平均成本可被虚拟额度规则覆盖。

## 文件组织建议

建议建立：

```text
eval_sets/
  mvp_style_eval_v1/
    writers/
      writer_001/
        materials/
        writer_profile.md
      writer_002/
        materials/
        writer_profile.md
    tasks.csv
    outputs/
      baseline_direct/
      style_prompt_only/
      style_profile_rag/
    scores.xlsx
    review_notes.md
```

素材目录不要放未授权作品。真实用户素材进入正式系统后，应按系统权限和隐私规则保存，不建议长期裸放在项目目录。
