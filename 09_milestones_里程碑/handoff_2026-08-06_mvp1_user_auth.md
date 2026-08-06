# 2026-08-06 接手说明：MVP1.1 用户系统完成

## 当前状态

当前项目已经从 Demo User 工作台推进到 MVP1.1：支持真实个人用户注册登录，并且核心业务数据已经绑定当前登录用户。

本轮已完成并验证：

- 用户名 + 密码注册。
- 用户名 + 密码登录。
- HTTP-only Cookie 登录态，有效期 7 天。
- 退出登录。
- `/v1/me` 当前用户接口。
- 未登录可预览工作台 UI。
- 未登录点击资产动作时弹登录/注册弹窗。
- 后端素材、风格、写作、段落重写等业务接口强制登录；未登录返回 401。
- 用户上传的参考文章绑定当前登录用户。
- 用户创建、确认、删除的风格绑定当前登录用户。
- 用户生成、重写的文章绑定当前登录用户。
- Demo User 仍保留为开发/测试辅助，但正常业务接口不再 fallback。
- 账号设置弹窗支持绑定中国大陆手机号。
- 手机验证码为测试模式：后端生成 6 位验证码，当前开发环境返回 `debug_code`，不真实发送短信。
- 手机号唯一。
- 手机号找回密码接口边界已预留，当前返回 501。

## 当前本地访问

- 前端：`http://127.0.0.1:3002`
- 后端：`http://127.0.0.1:8000`
- 后端健康检查：`http://127.0.0.1:8000/healthz`

## 最近一次验证

最近一次完整验证结果：

- `npm run test:api`：28 passed。
- `npm run typecheck:web`：通过。
- `npm run build:web`：通过。
- 后端 `/healthz`：返回 `ok`。
- 前端首页：HTTP 200。
- 注册后 Cookie 登录态访问 `/v1/me`：通过。

说明：`next build --webpack` 仍会出现 Next SWC 原生包加载警告，但构建会 fallback 到 WASM 并成功完成。该警告当前不阻塞开发。

## 关键代码入口

### 后端

- `apps/api/app/core/auth_service.py`
  - 用户名校验、密码校验、密码哈希、登录态签名、Cookie 会话校验、手机号验证码。
- `apps/api/app/main.py`
  - `/v1/auth/register`
  - `/v1/auth/login`
  - `/v1/auth/logout`
  - `/v1/me`
  - `/v1/account/phone/send-code`
  - `/v1/account/phone/bind`
  - `/v1/auth/password-reset/send-code`
  - `/v1/auth/password-reset/confirm`
  - 业务接口已改为依赖当前登录用户。
- `apps/api/app/models.py`
  - `User` 已扩展用户名、密码哈希、手机号字段。
  - 新增 `PhoneVerificationCode`。
- `apps/api/app/database.py`
  - 本地 SQLite 开发库增加缺失 auth 字段的非破坏性补列逻辑。
  - 正式数据库仍应使用 Alembic migration。
- `apps/api/alembic/versions/20260806_0002_user_auth.py`
  - 用户系统字段和手机号验证码表迁移。

### 前端

- `apps/web/components/WritingWorkspace.tsx`
  - 登录/注册弹窗。
  - 账号设置弹窗。
  - 未登录动作拦截。
  - API 请求已带 `credentials: "include"`，确保跨端口开发时 Cookie 生效。
- `apps/web/app/globals.css`
  - 登录/注册弹窗、账号设置弹窗、右上角账号入口样式。

### 测试

- `apps/api/tests/test_auth_workflow.py`
  - 注册登录、退出、用户名/密码校验、未登录 401、用户数据隔离、手机号绑定、找回密码预留接口。
- `apps/api/tests/test_mvp1_workflow.py`
  - 原工作流测试已适配登录态。
- `apps/api/tests/test_api_endpoints.py`
  - legacy prompt-only 行为测试已适配登录态。

## 当前重要产品规则

- 注册开放，不做邀请码。
- 注册只需用户名 + 密码。
- 用户名 6–32 位，只允许英文字母、数字、下划线，不区分大小写唯一。
- 密码 8–64 位，至少包含 1 个字母和 1 个数字。
- 手机号注册后在账号设置中绑定，不作为注册必填。
- 手机号只支持中国大陆手机号。
- 不做真实短信发送。
- 不做游客临时数据，也不做游客数据迁移。
- 不迁移 Demo User 数据。
- 不做组织、余额、历史文章列表、第三方登录、邮箱登录。
- 后续每次产品或交互修改，应先给方案，用户确认后再改代码。

## 不要误做的事情

- 不要让未登录业务接口 fallback 到 Demo User。
- 不要把 `.env.local`、本地数据库、运行日志、`node_modules/`、`eval_sets/`、`测评集/` 提交到仓库。
- 不要在日志、前端页面、测试输出或文档中写入真实 API Key。
- 不要把当前内部评测材料扩展为公网演示、商业宣传或训练材料。
- 不要在本轮用户系统基础上顺手加入组织、余额、历史文章列表等新功能。

## 下一步建议

1. 手工浏览器验证完整用户体验：
   - 未登录打开工作台。
   - 点击上传时弹登录/注册。
   - 注册后再次上传作品。
   - 分析风格、确认保存、生成文章、段落重写。
   - 账号设置中绑定手机号。
   - 退出后确认业务动作再次要求登录。
2. 接入正式 PostgreSQL 后执行 Alembic migration。
3. 完善 Qwen 真实调用的错误展示、超时和重试策略。
4. 做 Markdown/纯文本导出。
5. 设计风格编辑/重命名能力。

## 远程仓库

- GitHub：`https://github.com/siliwen/person_writer`
- 最新用户系统提交：`6161ef5 Add MVP1 user authentication`
