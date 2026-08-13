#!/usr/bin/env bash
# =============================================================================
# 墨小小 (moxx) — 生成生产部署包 moxx-deploy.tar.gz
#
# 仅打包「运行所需源码与配置」，依据 scripts/ec2-deploy.sh 的实际依赖：
#   - apps/                (api 后端 + web 前端源码)
#   - package.json         (根 npm workspace 配置, npm install 要用)
#   - package-lock.json
#   - scripts/             (ec2-deploy.sh 等部署脚本)
#   - .env.example         (环境变量模板, 供部署填值)
#   - README.md            (项目说明)
#
# 排除一切过程文件 / 依赖 / 敏感文件：
#   文档文件夹(00~09_*)、测评集/、eval_sets/、references_参考资料/、
#   design-preview/、outputs/、tools/、根目录调试 yaml/json/png、
#   依赖(node_modules / .venv / .next)、密钥(.env.local)、数据库(*.db) 等。
#   （未列入包含清单的根级条目天然不会被打包，下面的 --exclude 仅兜底 apps/ 内部。）
#
# 用法：  bash scripts/make-deploy-package.sh
# 产物：  项目根 moxx-deploy.tar.gz  （配合 scripts/ec2-deploy.sh 上传 ECS 使用）
# =============================================================================
set -euo pipefail

# 切到项目根（脚本位于 scripts/ 下）
cd "$(cd "$(dirname "$0")" && pwd)/.."

OUT="moxx-deploy.tar.gz"

echo "==> 生成部署包：$OUT"
echo "    仅包含：apps/  package.json  package-lock.json  scripts/  .env.example  README.md"
echo "    排除：文档文件夹 / 测评集 / 评测工具 / 依赖(venv,node_modules,.next) / 密钥(.env.local) / 数据库(*.db) 等"

tar -czf "$OUT" \
  --exclude='apps/api/.venv' \
  --exclude='apps/web/.next' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='*.db' \
  --exclude='.env.local' \
  apps \
  package.json \
  package-lock.json \
  scripts \
  .env.example \
  README.md

echo "==> 完成。包大小："
du -h "$OUT"
echo "==> 顶层内容预览："
tar -tzf "$OUT" | sed 's#/.*##' | sort -u
