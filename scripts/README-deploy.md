# 墨小小 (moxx.cn) ECS 部署手册

适用：阿里云 ECS，Alibaba Cloud Linux 3（CentOS 系），已购并开机，moxx.cn 已解析到 ECS 公网 IP。

## 准备好的东西
1. 代码 git 仓库地址（GitHub / 阿里云 Code / Gitee 均可，私有仓库用带 token 的 URL）
2. 通义千问 API Key（DashScope），或 OpenAI 兼容 key
3. Let's Encrypt 用的邮箱（任意有效邮箱）

## 步骤

### A. 上传脚本
在 Workbench 终端里，把本目录的两个文件上传到 ECS 任意目录（如 `/root/`）：
- `ec2-deploy.sh`
- （`env.local.example` 仅供参考，脚本会自动生成真实配置）

> 也可用 `scp ec2-deploy.sh root@<ECS公网IP>:/root/` 从本地推。

### B. 在 ECS 上执行一键部署
```bash
# 1) 给脚本加执行权限
chmod +x /root/ec2-deploy.sh

# 2) 设置必要环境变量（私钥不要进 git/聊天记录，建议直接在这里填）
export GIT_REPO="https://你的git地址/moxx.git"
export DASHSCOPE_API_KEY="sk-你的通义key"
export DEPLOY_DOMAIN="moxx.cn"
export CERTBOT_EMAIL="you@example.com"

# 3) 运行（约 3–8 分钟，取决于机器性能）
sudo bash /root/ec2-deploy.sh
```
脚本会自动完成：装依赖 → 拉代码 → 建虚拟环境装包 → 构建前端 → 注册 systemd 服务 → 配 Nginx + HTTPS → 开防火墙。

### C. 验证
- 浏览器打开 `https://moxx.cn`，应看到纸墨主题首页
- 注册一个账号 → 写文章测试后端连通
- 提权后台管理员（在 ECS 上）：
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
