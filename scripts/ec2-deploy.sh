#!/usr/bin/env bash
# =============================================================================
# 墨小小 (moxx.cn) — 阿里云 ECS 一键部署脚本 (Alibaba Cloud Linux 3 / CentOS 系)
# 用法：
#   export GIT_REPO="https://你的git地址/moxx.git"
#   export DASHSCOPE_API_KEY="sk-..."          # 通义千问 key（或用 OPENAI_API_KEY + BASE_URL）
#   export DEPLOY_DOMAIN="moxx.cn"            # 默认 moxx.cn
#   export CERTBOT_EMAIL="you@example.com"    # 用于 Let's Encrypt 证书
#   bash ec2-deploy.sh
# 说明：脚本会自动安装依赖、拉代码、构建、配置 systemd + Nginx + HTTPS。
#       如为私有仓库，请把 GIT_REPO 写成带 token 的地址，或提前配好 SSH key。
# =============================================================================
set -euo pipefail

# ----------------------------- 可配置变量 -----------------------------------
# GIT_REPO 可选：填了就 clone；不填则假定代码已上传到 DEPLOY_DIR（如用 git archive 包）
GIT_REPO="${GIT_REPO:-}"
DEPLOY_DOMAIN="${DEPLOY_DOMAIN:-moxx.cn}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-admin@${DEPLOY_DOMAIN}}"
DASHSCOPE_API_KEY="${DASHSCOPE_API_KEY:-}"
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
BASE_URL="${BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
MODEL_NAME="${MODEL_NAME:-qwen-plus}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/moxx}"
NODE_MAJOR=22

echo "==> 部署参数：DOMAIN=${DEPLOY_DOMAIN}  DIR=${DEPLOY_DIR}"

# ----------------------------- 1. 系统依赖 ----------------------------------
echo "==> [1/9] 安装系统依赖 (git/nginx/node/python/certbot)"
sudo dnf -y update >/dev/null 2>&1 || true
sudo dnf -y install git nginx python3 python3-pip firewalld cronie >/dev/null 2>&1 || \
  sudo yum -y install git nginx python3 python3-pip firewalld cronie

# Node.js 22 (NodeSource)
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]; then
  curl -fsSL https://rpm.nodesource.com/setup_${NODE_MAJOR}.x | sudo bash -
  sudo dnf -y install nodejs
fi
echo "    node: $(node -v)  npm: $(npm -v)"

# certbot (Let's Encrypt)
if ! command -v certbot >/dev/null 2>&1; then
  sudo dnf -y install certbot python3-certbot-nginx 2>/dev/null || \
    sudo pip3 install --break-system-packages certbot certbot-nginx
fi

# ----------------------------- 2. 准备代码 ----------------------------------
# 两种方式：① 填了 GIT_REPO 则 clone；② 不填则假定代码已上传到 DEPLOY_DIR
echo "==> [2/9] 准备代码 (DEPLOY_DIR=${DEPLOY_DIR})"
sudo mkdir -p "${DEPLOY_DIR}"
if [ -n "${GIT_REPO}" ]; then
  if [ -d "${DEPLOY_DIR}/.git" ]; then
    sudo -u "$(logname 2>/dev/null || echo root)" git -C "${DEPLOY_DIR}" pull --ff-only || true
  else
    sudo chown -R "$(logname 2>/dev/null || echo root):" "${DEPLOY_DIR}"
    git clone "${GIT_REPO}" "${DEPLOY_DIR}"
  fi
else
  if [ ! -d "${DEPLOY_DIR}/apps/web" ]; then
    echo "!! 未设置 GIT_REPO，且 ${DEPLOY_DIR}/apps/web 不存在。"
    echo "   请先上传代码包： sudo tar -xzf moxx-deploy.tar.gz -C ${DEPLOY_DIR}"
    exit 1
  fi
  echo "   使用已上传到 ${DEPLOY_DIR} 的代码"
fi

# 切换到部署用户（非 root 运行服务更安全）
APP_USER="$(logname 2>/dev/null || echo root)"
APP_DIR="${DEPLOY_DIR}"
cd "${APP_DIR}"

# ----------------------------- 3. 后端环境 ----------------------------------
echo "==> [3/9] 配置后端 Python 虚拟环境"
python3 -m venv "${APP_DIR}/apps/api/.venv"
# shellcheck disable=SC1091
source "${APP_DIR}/apps/api/.venv/bin/activate"
pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/
pip install -r "${APP_DIR}/apps/api/requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/

# 写 .env.local（在仓库根目录，model_gateway 读取此处）
echo "==> [3/9] 写入 .env.local"
cat > "${APP_DIR}/.env.local" <<EOF
# 墨小小后端运行环境配置（由 deploy 脚本生成）
DATABASE_URL=sqlite+pysqlite:///${APP_DIR}/apps/api/personal_writing_agent_mvp1.db
AUTH_SECRET=$(openssl rand -hex 32)
MODEL_GATEWAY_MODE=auto
DASHSCOPE_API_KEY=${DASHSCOPE_API_KEY}
OPENAI_API_KEY=${OPENAI_API_KEY}
BASE_URL=${BASE_URL}
MODEL_NAME=${MODEL_NAME}
REQUEST_TIMEOUT_SECONDS=120
EOF
echo "    .env.local 已生成"

# ----------------------------- 4. 前端构建 ----------------------------------
echo "==> [4/9] 安装并构建前端 (npm)"
cd "${APP_DIR}/apps/web"
npm config set registry https://registry.npmmirror.com
npm install
NEXT_PUBLIC_API_BASE_URL=/api npm run build
cd "${APP_DIR}"

# ----------------------------- 5. systemd: 后端 -----------------------------
echo "==> [5/9] 注册后端 systemd 服务 (uvicorn :8010)"
cat > /tmp/moxx-api.service <<EOF
[Unit]
Description=Moxx Writing Agent API
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}/apps/api
Environment=PYTHONUNBUFFERED=1
ExecStart=${APP_DIR}/apps/api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo mv /tmp/moxx-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now moxx-api

# ----------------------------- 6. systemd: 前端 -----------------------------
echo "==> [6/9] 注册前端 systemd 服务 (next start :3000)"
cat > /tmp/moxx-web.service <<EOF
[Unit]
Description=Moxx Writing Agent Web
After=network.target moxx-api.service

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}/apps/web
Environment=NEXT_PUBLIC_API_BASE_URL=/api
ExecStart=${APP_DIR}/apps/web/node_modules/.bin/next start -p 3000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo mv /tmp/moxx-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now moxx-web

# ----------------------------- 7. Nginx ------------------------------------
echo "==> [7/9] 写入 Nginx 配置并申请 HTTPS 证书"
sudo tee /etc/nginx/conf.d/moxx.conf >/dev/null <<EOF
server {
    listen 80;
    server_name ${DEPLOY_DOMAIN} www.${DEPLOY_DOMAIN};
    # certbot 会自动接管 80 端口做校验，这里仅做跳转
    location /.well-known/acme-challenge/ { root /var/www/letsencrypt; }
    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name ${DEPLOY_DOMAIN} www.${DEPLOY_DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DEPLOY_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DEPLOY_DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 20m;

    # 前端静态资源
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8010/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
sudo nginx -t
sudo systemctl enable --now nginx

# 申请证书（certbot）
if [ ! -f "/etc/letsencrypt/live/${DEPLOY_DOMAIN}/fullchain.pem" ]; then
  sudo certbot --nginx -d "${DEPLOY_DOMAIN}" -d "www.${DEPLOY_DOMAIN}" \
    --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" --redirect
fi

# ----------------------------- 8. 防火墙 -----------------------------------
echo "==> [8/9] 开放 80/443 (firewalld)"
sudo systemctl enable --now firewalld || true
sudo firewall-cmd --permanent --add-service=http || true
sudo firewall-cmd --permanent --add-service=https || true
sudo firewall-cmd --reload || true

# ----------------------------- 9. 验证 -------------------------------------
echo "==> [9/9] 服务状态"
sleep 3
sudo systemctl status moxx-api --no-pager | head -5 || true
sudo systemctl status moxx-web --no-pager | head -5 || true
sudo systemctl status nginx --no-pager | head -5 || true
echo
echo "==> 部署完成！请访问： https://${DEPLOY_DOMAIN}"
echo "    如首页正常但 API 报错，检查：journalctl -u moxx-api -n 50"
echo "    首次使用：注册账号后，用 make_admin.py 提权后台："
echo "      cd ${APP_DIR}/apps/api && .venv/bin/python scripts/make_admin.py <你的用户名>"
