#!/usr/bin/env bash
# =============================================================================
# 墨小小 (moxx.cn) — 阿里云 ECS 一键部署脚本 (Alibaba Cloud Linux 3 / CentOS 系)
# 用法：
#   export GIT_REPO="https://你的git地址/moxx.git"
#   export DASHSCOPE_API_KEY="sk-..."          # 通义千问 key（或用 OPENAI_API_KEY + BASE_URL）
#   export DEPLOY_DOMAIN="moxx.cn"            # 默认 moxx.cn
#   export CERTBOT_EMAIL="you@example.com"    # 用于 Let's Encrypt 证书
#   export ADMIN_USERNAME="siliwensong"       # 默认超管用户名（留空则用内置默认）
#   export ADMIN_PASSWORD="Siliwen0915sw!@#"  # 默认超管密码（留空则用内置默认）
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
# 默认超管（部署后自动建好，可用环境变量覆盖；强烈建议首次登录后立即改密码）
ADMIN_USERNAME="${ADMIN_USERNAME:-siliwensong}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Siliwen0915sw!@#}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
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
sudo dnf -y install git nginx openssl python3 python3-pip firewalld cronie >/dev/null 2>&1 || \
  sudo yum -y install git nginx openssl python3 python3-pip firewalld cronie

# Node.js 22 (NodeSource)
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]; then
  curl -fsSL https://rpm.nodesource.com/setup_${NODE_MAJOR}.x | sudo bash -
  sudo dnf -y install nodejs
fi
echo "    node: $(node -v)  npm: $(npm -v)"

# certbot (Let's Encrypt)
if ! command -v certbot >/dev/null 2>&1; then
  sudo dnf -y install certbot python3-certbot-nginx 2>/dev/null || \
    sudo python3 -m pip install --user certbot certbot-nginx 2>/dev/null || \
    sudo pip3 install --user certbot certbot-nginx
fi
# 确保证书自动续期（不同发行版 timer 名称不同，逐个尝试）
sudo systemctl enable certbot-renew.timer >/dev/null 2>&1 || \
  sudo systemctl enable certbot-renewal.timer >/dev/null 2>&1 || true

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

# 使用专用系统用户运行服务（非 root，更安全，也避免 SQLite 权限错配导致 readonly）
APP_USER="moxx"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  sudo useradd -r -s /sbin/nologin "${APP_USER}" 2>/dev/null || sudo useradd -m -s /sbin/nologin "${APP_USER}"
fi
APP_DIR="${DEPLOY_DIR}"
cd "${APP_DIR}"

# 把整个项目归属给运行用户，确保进程对目录有写权限
# （SQLite 写入时需在 db 同目录创建 -wal / -shm / journal 临时文件，owner 必须对目录可写）
sudo chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
# 兜底：确保数据库目录可写
sudo chmod 755 "${APP_DIR}/apps/api"

# ----------------------------- 3. 后端环境 ----------------------------------
echo "==> [3/9] 配置后端 Python 虚拟环境"
# 项目需要 Python 3.10+（代码使用 | 联合类型，FastAPI 0.116 亦需较新 Python）。
# Alibaba Cloud Linux 3 / CentOS 8 默认 python3 是 3.6，必须装 3.11/3.12。
PYTHON_CMD=""
for py in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$py" >/dev/null 2>&1; then
        PYTHON_CMD="$py"
        break
    fi
done
if [ -z "$PYTHON_CMD" ]; then
    echo "    未检测到 Python 3.10+，尝试安装 python3.11 / python3.12 ..."
    sudo dnf -y install epel-release >/dev/null 2>&1 || true
    # 阿里云等部分镜像没有 python3.11-venv 包，先只装本体和 pip
    sudo dnf -y install python3.11 python3.11-pip >/dev/null 2>&1 || \
      sudo dnf -y install python3.12 python3.12-pip >/dev/null 2>&1 || \
      sudo yum -y install python3.11 python3.11-pip
    for py in python3.13 python3.12 python3.11 python3.10; do
        if command -v "$py" >/dev/null 2>&1; then
            PYTHON_CMD="$py"
            break
        fi
    done
fi
if [ -z "$PYTHON_CMD" ]; then
    echo "!! 未能安装 Python 3.10+，请手动安装 python3.11 或更高版本后重试。"
    exit 1
fi
echo "    使用 Python：$(${PYTHON_CMD} --version)"

# 旧 venv 若由 python3.6 创建会导致依赖版本不兼容，删掉重建
rm -rf "${APP_DIR}/apps/api/.venv"
if ${PYTHON_CMD} -m venv "${APP_DIR}/apps/api/.venv" >/dev/null 2>&1; then
    echo "    使用 ${PYTHON_CMD} -m venv 创建虚拟环境"
elif ${PYTHON_CMD} -m ensurepip --upgrade >/dev/null 2>&1 && ${PYTHON_CMD} -m venv "${APP_DIR}/apps/api/.venv" >/dev/null 2>&1; then
    echo "    已修复 ensurepip 并创建虚拟环境"
else
    echo "    ${PYTHON_CMD} -m venv 不可用，尝试安装 virtualenv 兜底 ..."
    sudo ${PYTHON_CMD} -m pip install virtualenv >/dev/null 2>&1 || \
      ${PYTHON_CMD} -m pip install --user virtualenv >/dev/null 2>&1
    ${PYTHON_CMD} -m virtualenv "${APP_DIR}/apps/api/.venv"
fi
# shellcheck disable=SC1091
source "${APP_DIR}/apps/api/.venv/bin/activate"
pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/
pip install -r "${APP_DIR}/apps/api/requirements.txt" -i https://mirrors.aliyun.com/pypi/simple/

# 写 .env.local（在仓库根目录，model_gateway 读取此处）
# 用 Python 写，避免 API key / 密码里的 $ 被 shell 提前解析
echo "==> [3/9] 写入 .env.local"
AUTH_SECRET=$(openssl rand -hex 32)
${PYTHON_CMD} - <<PY
import os
app_dir = os.environ['APP_DIR']
auth_secret = os.environ['AUTH_SECRET']
with open(os.path.join(app_dir, '.env.local'), 'w', encoding='utf-8') as f:
    f.write(f"""# 墨小小后端运行环境配置（由 deploy 脚本生成）
DATABASE_URL=sqlite+pysqlite:///{app_dir}/apps/api/personal_writing_agent_mvp1.db
AUTH_SECRET={auth_secret}
MODEL_GATEWAY_MODE=auto
DASHSCOPE_API_KEY={os.environ.get('DASHSCOPE_API_KEY', '')}
OPENAI_API_KEY={os.environ.get('OPENAI_API_KEY', '')}
BASE_URL={os.environ.get('BASE_URL', '')}
MODEL_NAME={os.environ.get('MODEL_NAME', '')}
REQUEST_TIMEOUT_SECONDS=120
# 默认超管引导（init_db 读取；不设则跳过）
ADMIN_USERNAME={os.environ.get('ADMIN_USERNAME', '')}
ADMIN_PASSWORD={os.environ.get('ADMIN_PASSWORD', '')}
ADMIN_EMAIL={os.environ.get('ADMIN_EMAIL', '')}
""")
PY
echo "    .env.local 已生成"

# 密钥文件仅运行用户可读
sudo chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env.local"
sudo chmod 600 "${APP_DIR}/.env.local"

# ----------------------------- 4. 前端构建 ----------------------------------
# 项目根目录是 npm workspace（workspaces: ["apps/web"]），必须在根目录 install，
# 再用 --workspace 构建，否则在 apps/web 子目录里直接 npm install 会报 ENOWORKSPACES。
echo "==> [4/9] 安装并构建前端 (npm workspace)"
cd "${APP_DIR}"
npm config set registry https://registry.npmmirror.com
npm install
NEXT_PUBLIC_API_BASE_URL=/api npm --workspace apps/web run build

# 所有构建产物（venv / node_modules / .next / 数据库目录）生成后，
# 统一归属给运行用户。SQLite 写入时需在 db 同目录创建临时文件，
# 只有 owner 对目录有写权限才能成功，避免 readonly 错误。
sudo chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
sudo chmod 755 "${APP_DIR}/apps/api"

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
# npm workspaces 会把 bin 提升/链接到根 node_modules/.bin
ExecStart=${APP_DIR}/apps/web/node_modules/.bin/next start -p 3000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo mv /tmp/moxx-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now moxx-web

# ----------------------------- 7. Nginx + HTTPS ------------------------------------
echo "==> [7/9] 配置 Nginx 并申请 HTTPS 证书"

# 先确保 certbot webroot 目录存在
sudo mkdir -p /var/www/letsencrypt

# 移除 Nginx 默认站点，避免 80/443 端口冲突（CentOS/Alibaba Cloud Linux 默认带 default.conf）
if [ -f /etc/nginx/conf.d/default.conf ]; then
  sudo mv /etc/nginx/conf.d/default.conf "/etc/nginx/conf.d/default.conf.bak.$(date +%s)"
  echo "    已备份默认站点 default.conf"
fi

# 阶段 A：先写 HTTP-only 配置，让 certbot 能用 webroot 校验，也让服务先可用
sudo tee /etc/nginx/conf.d/moxx.conf >/dev/null <<EOF
server {
    listen 80;
    server_name ${DEPLOY_DOMAIN} www.${DEPLOY_DOMAIN};
    root /var/www/letsencrypt;

    location /.well-known/acme-challenge/ { }

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

# 阶段 B：申请证书（webroot 模式，不修改 nginx 配置）
if [ ! -f "/etc/letsencrypt/live/${DEPLOY_DOMAIN}/fullchain.pem" ]; then
  echo "    正在申请 Let's Encrypt 证书，请确保 ${DEPLOY_DOMAIN} 已解析到本机 80 端口 ..."
  sudo certbot certonly --webroot -w /var/www/letsencrypt \
    -d "${DEPLOY_DOMAIN}" -d "www.${DEPLOY_DOMAIN}" \
    --non-interactive --agree-tos -m "${CERTBOT_EMAIL}" || true
fi

# 阶段 C：证书到手后，再写入完整的 HTTP→HTTPS 配置
if [ -f "/etc/letsencrypt/live/${DEPLOY_DOMAIN}/fullchain.pem" ]; then
  sudo tee /etc/nginx/conf.d/moxx.conf >/dev/null <<EOF
server {
    listen 80;
    server_name ${DEPLOY_DOMAIN} www.${DEPLOY_DOMAIN};
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
  sudo nginx -t && sudo systemctl reload nginx
  echo "    HTTPS 证书已配置：${DEPLOY_DOMAIN}"
else
  echo "    ⚠️ 证书申请失败，Nginx 仍以 HTTP 模式运行，请检查域名解析和 80 端口连通性。"
  echo "       排查后可重跑本脚本（不会重复建库/建账号）。"
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
echo
echo "==> 默认超管账号（由 init_db 在首次启动时创建）："
echo "    用户名： ${ADMIN_USERNAME}"
echo "    密码：   ${ADMIN_PASSWORD}"
echo "    ⚠️ 请首次登录后台后立即修改密码；如需更换，重跑前在环境变量设 ADMIN_USERNAME/ADMIN_PASSWORD 即可。"
