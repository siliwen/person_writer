# 墨小小 (moxx.cn) ECS 部署手册

适用：阿里云 ECS，Alibaba Cloud Linux 3（CentOS 系），已购并开机，moxx.cn 已解析到 ECS 公网 IP。

## 准备好的东西
1. 代码 git 仓库地址（GitHub / 阿里云 Code / Gitee 均可，私有仓库用带 token 的 URL）
2. 通义千问 API Key（DashScope），或 OpenAI 兼容 key
3. Let's Encrypt 用的邮箱（任意有效邮箱）

## 0. 生成本地部署包（moxx-deploy.tar.gz）

在本地项目根目录执行：

```bash
bash scripts/make-deploy-package.sh
```

脚本**仅打包运行所需**：`apps/`、`package.json`、`package-lock.json`、`scripts/`、`.env.example`、`README.md`；
自动排除一切过程文件（`00~09_` 文档文件夹、测评集、eval_sets、references、design-preview、outputs、tools）、
依赖（`node_modules`/`.venv`/`.next`）、密钥（`.env.local`）与数据库（`*.db`）。
生成 `moxx-deploy.tar.gz` 后，按下方「方式一」上传即可。

> ⚠️ 不要用 `git archive` 或裸 `tar` 直接打包根目录，否则会把 PRD/需求/产品设计等过程文件和非运行依赖一起带进生产包。

## 步骤

> 两种代码来源（二选一）：
> - **方式一（推荐，最简单）**：用 `moxx-deploy.tar.gz` 上传包，不依赖 GitHub；
> - **方式二**：`export GIT_REPO=...` 让脚本自动 clone（需 GitHub 可访问）。
> 下面以**方式一**为主。

### A. 上传文件到 ECS
在 Workbench 文件管理器里，把以下文件上传到 ECS（如 `/root/`）：
- `moxx-deploy.tar.gz` （代码包，已排除 node_modules/.venv/.next/*.db/.env.local）
- `ec2-deploy.sh` （一键部署脚本）
- （`env.local.example` 仅供参考，脚本会自动生成真实配置）

> 也可用 scp 从本地推：
> `scp moxx-deploy.tar.gz ec2-deploy.sh root@<ECS公网IP>:/root/`

### B. 在 ECS 上解压代码 + 执行部署
```bash
# 1) 解压代码到 /opt/moxx（脚本会从这个目录构建）
sudo mkdir -p /opt/moxx
sudo tar -xzf /root/moxx-deploy.tar.gz -C /opt/moxx

# 2) 给脚本加执行权限
chmod +x /root/ec2-deploy.sh

# 3) 设置环境变量（key 直接在这里填，不进聊天记录）
export DASHSCOPE_API_KEY="sk-你的通义key"
export DEPLOY_DOMAIN="moxx.cn"
export CERTBOT_EMAIL="you@example.com"
# 注意：方式一不要设置 GIT_REPO，脚本会检测到代码已存在而跳过 clone

# 4) 运行（约 3–8 分钟，取决于机器性能）
sudo bash /root/ec2-deploy.sh
```
脚本会自动完成：装依赖 → 建虚拟环境装包 → 构建前端 → 注册 systemd 服务 → 配 Nginx + HTTPS → 开防火墙。

### C. 验证
- 浏览器打开 `https://moxx.cn`，应看到纸墨主题首页
- 部署脚本在首次启动时会**自动创建默认超管账号**（用户名/密码见脚本末尾输出），直接用该账号登录后台即可
- 如需更换超管账号，重跑前在环境变量设 `ADMIN_USERNAME` / `ADMIN_PASSWORD`；已有超管不会被覆盖
- 旧方式（手动提权）仍可用，仅当未配置 ADMIN_* 时备用：
  ```bash
  cd /opt/moxx/apps/api
  .venv/bin/python scripts/make_admin.py <你的用户名>
  ```

## 日常运维
| 操作 | 命令 |
|---|---|
| 看后端日志 | `journalctl -u moxx-api -n 100 -f` |
| 看前端日志 | `journalctl -u moxx-web -n 100 -f` |
| 重启服务 | `sudo systemctl restart moxx-api moxx-web` |
| 更新代码 | 见下方「更新迭代（非首次部署）」小节，按 `/opt/moxx` 是否为 git 仓库选择 tar 覆盖或 git pull |
| 证书续期（自动） | certbot 已加入 cron，一般无需手动；手动：`sudo certbot renew` |

## 更新迭代（非首次部署，已有生产环境）

生产环境已通过 tar 包解压在 `/opt/moxx`（**非 git clone，目录内无 `.git`**）。更新只需替换代码 + 重建 + 重启，**不要重跑整个 `ec2-deploy.sh`**（证书/Nginx/systemd 已就绪，重跑属多余）。

> ⚠️ **数据库位置与保护**：`ec2-deploy.sh` 把 `DATABASE_URL` 写死为 `/opt/moxx/apps/api/personal_writing_agent_mvp1.db`（**在 `apps/api/` 内**）。**更新千万不要 `rm -rf /opt/moxx/apps`**，否则会删除生产数据库！正确做法是直接用 `tar -xzf` 覆盖解压——tar 只覆盖包内文件，不会删除包外的 `*.db` / `.env.local` / `.venv` / `.next`。

### 方式 A：tar 覆盖（默认，适用于 tar 解压的 /opt/moxx）
```bash
# 0) 先备份数据库（安全网）
sudo cp /opt/moxx/apps/api/personal_writing_agent_mvp1.db /root/moxx-db-backup-$(date +%F).db

# 1) 上传新包（本地 moxx-deploy.tar.gz 已含最新代码，无需先推远程）
scp moxx-deploy.tar.gz root@<ECS公网IP>:/root/

# 2) 覆盖解压（只覆盖源码/配置，不动 db/.env.local/.venv/.next）
sudo tar -xzf /root/moxx-deploy.tar.gz -C /opt/moxx

# 3) 修正属主（tar 以 root 解压，应用以 APP_USER 运行；<APP_USER> 见 ec2-deploy.sh）
sudo chown -R <APP_USER>:<APP_USER> /opt/moxx/apps /opt/moxx/scripts

# 4) 后端（仅源码改动时重启即可；requirements.txt 有变更才需 pip install）
cd /opt/moxx/apps/api && .venv/bin/pip install -r requirements.txt && sudo systemctl restart moxx-api

# 5) 前端（有改动时重装 + 构建 + 重启）
cd /opt/moxx/apps/web && npm install && NEXT_PUBLIC_API_BASE_URL=/api npm run build && sudo systemctl restart moxx-web
```

### 方式 B：git pull（仅当 /opt/moxx 当初是 git clone 或已 git init）
```bash
cd /opt/moxx && git pull && cd apps/web && npm install && NEXT_PUBLIC_API_BASE_URL=/api npm run build && sudo systemctl restart moxx-web
# 后端依赖有变更时：cd /opt/moxx/apps/api && .venv/bin/pip install -r requirements.txt && sudo systemctl restart moxx-api
```

> 说明：本项目 ECS 初次部署采用方式一（tar 解压），故默认走**方式 A**。把代码推到 GitHub 远程仅用于备份/团队协作，不是 ECS 更新的前置条件。

### 临时网页更新控制台（deploy-console，一次性工具）

如果你想要「放 tar 到目录 + 点按钮就更新」的网页界面，可以用仓库里的 `deploy-console/`——它是一个**独立进程、独立端口**的临时工具，**不依赖 moxx-api / moxx-web**，所以更新脚本把这两个服务停掉重建时，控制台自身不受影响，页面始终能看进度。

> ⚠️ **特性与边界**：无鉴权、无审计（只给本人临时用）；**用完请删除 `/root/deploy-console` 目录并结束进程**（它不会被打进 `moxx-deploy.tar.gz`，不会污染生产环境）。

**部署与使用**：
```bash
# 1) 把整个 deploy-console/ 传到 ECS（它不在部署包内，需单独传）
scp -r deploy-console root@<ECS公网IP>:/root/

# 2) 在 ECS 上后台启动控制台（MOXX_ROOT 指生产根目录，PORT 自定义）
cd /root/deploy-console
MOXX_ROOT=/opt/moxx PORT=9000 python3 server.py >/dev/null 2>&1 &

# 3) 安全组临时开放 9000 端口，浏览器打开 http://<ECS公网IP>:9000
# 4) 把新 moxx-deploy.tar.gz 放到 ECS 的 /opt/moxx/incoming/（scp 即可）
# 5) 页面点「检查更新包」→ 看到版本差 → 点「执行更新」，日志实时滚动
# 6) 更新完成后：kill 掉控制台进程、删除 /root/deploy-console、关闭 9000 端口
```

**它做了什么**：`执行更新` 会后台跑 `update-from-tar.sh`，顺序为
备份数据库+`.env.local` → 停 moxx-api/moxx-web → 覆盖解压（保留 `*.db`/`.env.local`/`.venv`/`.next`）→ 执行版本化数据库迁移（保数据）→ 装依赖+构建前端 → 重启+健康检查；**任一步失败自动回滚**（恢复 db 备份 + 重解压上一份代码包）。

**版本与迁移判断**：tar 内含 `deploy-manifest.json`（构建 commit / 时间 / `requires_db_migration`），控制台据此显示「当前 → 待更新」版本差并提示是否需要迁移。未来的表结构变更请在 `apps/api/app/migrations/` 下新增 `NNNN_描述.py`（导出 `upgrade(conn)`，铁律只增不改；改列用 `rebuild_table` 全量拷行），`run_migrations` 会自动按序补齐且幂等。

## 常见问题
- **首页能开但写文章 500**：多半是 `DASHSCOPE_API_KEY` 没生效或模型名不对，查 `journalctl -u moxx-api`。
- **端口被旧进程占**：`sudo lsof -i:8010` / `:3000` 找 PID 杀掉再 restart。
- **证书申请失败**：确认域名 A 记录已生效、80 端口对外可访问（安全组放行 80/443/22）。
- **私有仓库 clone 失败**：把 `GIT_REPO` 换成 `https://<user>:<token>@github.com/...` 或预先配好 SSH key。
