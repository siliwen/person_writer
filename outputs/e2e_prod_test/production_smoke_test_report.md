# 墨小小生产环境功能测试报告

**测试时间：** 2026-08-14 18:00 左右（北京时间）  
**测试目标：** http://121.40.90.16:8080/  
**测试账号：** `moxx_e2e_test` / `MoxxTest123`（本次注册的一次性测试账号，未触碰真实用户数据）  
**测试方式：** 浏览器自动化端到端操作

---

## 一、执行摘要

| 类别 | 结果 |
|------|------|
| 注册/登录/登出 | 通过 |
| 风格库 / 新建风格 | 通过 |
| 写作生成 / 文章鉴评 | 通过 |
| 消息中心 | 通过 |
| 设置 / 主题切换 / 用量 | 通过 |
| 提示词优化 | 通过 |
| 文章保存到文章库 | **不通过（需修复）** |
| 后台管理 | 未测试（需管理员权限） |
| 段落重写 / 下载 | 未测试（免费版不支持） |

**结论：** 核心链路（注册→建风格→写作→鉴评→消息→设置）已跑通；但「保存文章」功能存在明显 bug，文章生成后点击保存不会进入文章库，需优先修复。

---

## 二、详细测试结果

### 2.1 认证与首页 ✅
- 注册新账号 `moxx_e2e_test` 成功，自动登录进入工作台。
- 登出后重新登录成功。
- 工作台显示「我的风格」「最近文章」「积分」「消息」等入口。
- 截图：`01_dashboard_loggedin.png`

### 2.2 风格库 / 新建风格 ✅
- 进入风格库，显示「我的风格 · 0 个」和「推荐风格」。
- 推荐风格当前为占位状态：「推荐风格正在准备中，上线后可直接引用进行写作」。
- 点击「+ 创建你的第一个风格」打开弹窗，上传 `sample_prose.txt`。
- 选择体裁「散文」，点击「开始分析 · 消耗2积分」。
- 分析完成后展示六维风格诊断（词汇和句子、修辞和表达、叙事和结构、情绪和基调、题材和人物、时代和语体）。
- 点击「确认并保存到风格库」成功，风格库变为「我的风格 · 1 个」。
- 截图：`02_style_library.png`、`03_style_analysis_progress.png`、`05_style_analysis_result.png`、`07_style_library_with_style.png`

### 2.3 写作生成 / 文章鉴评 ✅
- 从风格卡片点击「开始写作 →」进入写作页。
- 系统预填：风格「我的散文风格」、文体「散文」、标题「附近生活」、字数「1200字」等。
- 点击「按选定风格生成文章 · 消耗5积分」，约 1 分钟后生成三段落散文《附近生活》。
- 右侧自动展开「文章鉴评」面板，显示总分 6.2 / C 级，以及文体契合度、风格契合度、内容质量、指令遵循、语言规范等维度评分与修改建议。
- 积分从 10 扣至 3（风格分析 -2、文章生成 -5）。
- 截图：`08_writing_from_style.png`、`11_article_generated.png`、`12_evaluation_panel.png`

### 2.4 消息中心 ✅
- 生成完成后顶部消息铃铛显示 3 条未读。
- 打开消息中心看到：
  1. 文章鉴评已生成（《附近生活》C 级 6.2 分）
  2. 积分即将用尽（剩余 3 积分）
  3. 风格生成完成（我的散文风格已生成）
- 截图：`14_message_center.png`

### 2.5 设置 / 主题切换 / 用量与额度 ✅
- 设置页四个标签：个人资料、安全设置、用量与额度、数据与隐私均可切换。
- 三主题切换正常：纸墨（默认）、墨韵紫、瑞士现代。
- 用量与额度页显示：免费版、剩余 3 积分/本月 10、单篇最大 2000 字、额度重置日、积分消耗历史。
- 数据与隐私页显示：素材默认私有、数据隔离、删除风格不影响历史文章均已启用。
- 截图：`16_settings.png`、`17_settings_theme_violet.png`、`18_settings_theme_swiss.png`、`19_settings_usage.png`、`20_settings_security.png`、`28_settings_privacy.png`

### 2.6 提示词优化 ✅
- 在首页输入「写一篇关于老茶馆的故事」，点击「优化提示词 · 1积分」。
- 约 5 秒后文本框被替换为一段结构化、详细的提示词，按钮变为「重新优化 · 1积分」。
- 用量历史中新增 `optimize_prompt -1 分` 记录。
- 截图：`25_prompt_optimize.png`、`27_usage_after_optimize.png`

---

## 三、问题与风险

### ❌ 问题 1：保存文章后未进入文章库（高优先级）

**现象：**
- 写作页生成文章后，点击「保存文章」按钮，按钮状态无变化（未出现「已保存」标识）。
- 切换到「文章库」页面，显示「还没有保存的文章」。
- 直接调用后端接口 `GET /api/v1/documents/saved` 返回：
  ```json
  {"user_id":"user_aa8684a76090","documents":[]}
  ```

**影响：** 用户生成的文章无法保存到个人库，文章库/最近文章/下载功能均受影响。

**建议：**
1. 前端：检查 `DocumentReader.handleSave` 是否正确调用 `POST /v1/documents/{id}/save`，并在失败时给出明确提示。
2. 后端：检查 `save_document_endpoint` 是否正确设置 `is_saved=true` 与 `saved_at`。
3. 建议补充 E2E 测试：生成散文 → 保存 → 断言 `/v1/documents/saved` 非空。

### ⚠️ 问题 2：积分余额显示与消耗历史存在 1 分偏差（中优先级，待确认）

**现象：**
- 用量与额度页显示「剩余积分 3 / 本月 10」。
- 积分消耗历史可见：风格分析 -2、文章生成 -5、提示词优化 -1，合计 -8。
- 10 - 8 = 2，但余额显示 3。

**可能原因：**
- `optimize_prompt` 操作实际扣费配置为 0，但历史记录写成了 -1；或
- 顶部/用量余额未在操作后刷新，读取的是旧缓存。

**建议：** 核对 `operation_costs` 表中 `optimize_prompt` 的 points 与 `usage_records` 记录逻辑是否一致。

### ⚠️ 问题 3：部分功能受会员等级限制（产品设计内，非 bug）
- 免费版不支持「段落重写」与「下载文章」，按钮显示「升级后可重写」/ 下载按钮禁用。
- 免费版积分不足时「生成文章」按钮自动禁用。
- 如需验证付费功能，需要开通测试会员或调整测试账号 tier。

### ⚠️ 问题 4：后台管理未覆盖
- 测试账号 `moxx_e2e_test` 不是管理员，侧边栏不显示「后台管理」。
- 直接访问 `/admin` 返回 Next.js 404（因为 admin 是客户端视图而非独立路由）。
- 如需测试后台 5 个 tab，需要将一个账号提权为管理员后再测。

---

## 四、测试截图清单

所有截图保存在 `outputs/e2e_prod_test/`：

| 编号 | 文件名 | 说明 |
|------|--------|------|
| 01 | `01_dashboard_loggedin.png` | 已登录工作台 |
| 02 | `02_style_library.png` | 风格库初始状态 |
| 03 | `02b_style_library_full.png` | 风格库全页（含推荐风格占位） |
| 04 | `03_style_analysis_progress.png` | 风格分析中 |
| 05 | `04_style_analysis_clicked2.png` | 再次点击开始分析后 |
| 06 | `05_style_analysis_result.png` | 风格分析结果（六维诊断） |
| 07 | `06_style_saved.png` / `06b_style_save_bottom.png` | 保存风格 |
| 08 | `07_style_library_with_style.png` | 风格库已有 1 个风格 |
| 09 | `08_writing_from_style.png` | 写作参数页 |
| 10 | `09_writing_generating.png` / `10_writing_clicked_bottom.png` | 文章生成中 |
| 11 | `11_article_generated.png` | 文章已生成 |
| 12 | `12_evaluation_panel.png` | 文章鉴评面板 |
| 13 | `13_article_saved.png` | 点击保存文章后（未出现已保存标识） |
| 14 | `14_message_center.png` | 消息中心 3 条系统消息 |
| 15 | `15_article_library.png` | 文章库为空 |
| 16 | `16_settings.png` | 设置页 |
| 17 | `17_settings_theme_violet.png` | 墨韵紫主题 |
| 18 | `18_settings_theme_swiss.png` | 瑞士现代主题 |
| 19 | `19_settings_usage.png` / `27_usage_after_optimize.png` | 用量与额度 |
| 20 | `20_settings_security.png` | 安全设置 |
| 21 | `21_admin_direct.png` | 直接访问 /admin 404 |
| 22 | `22_user_menu.png` / `23_user_menu_open.png` | 用户菜单 |
| 23 | `24_logged_out.png` | 登出后状态 |
| 24 | `25_prompt_optimize.png` | 提示词优化结果 |
| 25 | `28_settings_privacy.png` | 数据与隐私 |

---

## 五、建议后续动作

1. **修复「保存文章」bug** 后重新跑一遍 生成→保存→文章库 的端到端验证。
2. **核对积分扣费一致性**（optimize_prompt 的 operation_costs vs usage_records）。
3. **后台管理测试**：将 `moxx_e2e_test` 或另一个测试账号提权为管理员（`scripts/make_admin.py`），再测后台 5 个 tab。
4. 测试完成后可删除本次注册的一次性账号 `moxx_e2e_test` 及其关联数据。
