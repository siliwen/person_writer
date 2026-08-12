# 墨小小 (moxx.cn) ECS 部署手册

适用：阿里云 ECS，Alibaba Cloud Linux 3（CentOS 系），已购并开机，moxx.cn 已解析到 ECS 公网 IP。

## 准备好的东西
1. 代码 git 仓库地址（GitHub / 阿里云 Code / Gitee 均可，私有仓库用带 token 的 URL）
2. 通义千问 API Key（DashScope），或 OpenAI 兼容 key
3. Let's Encrypt 用的邮箱（任意有效邮箱）

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
| 更新代码 | `cd /opt/moxx && git pull && cd apps/web && npm install && npm run build && sudo systemctl restart moxx-web` |
| 证书续期（自动） | certbot 已加入 cron，一般无需手动；手动：`sudo certbot renew` |

## 常见问题
- **首页能开但写文章 500**：多半是 `DASHSCOPE_API_KEY` 没生效或模型名不对，查 `journalctl -u moxx-api`。
- **端口被旧进程占**：`sudo lsof -i:8010` / `:3000` 找 PID 杀掉再 restart。
- **证书申请失败**：确认域名 A 记录已生效、80 端口对外可访问（安全组放行 80/443/22）。
- **私有仓库 clone 失败**：把 `GIT_REPO` 换成 `https://<user>:<token>@github.com/...` 或预先配好 SSH key。
