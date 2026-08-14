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
#   - README.md
#   - deploy-manifest.json (自动生成：构建 commit / 时间 / 是否需数据库迁移)
#
# 排除一切过程文件 / 依赖 / 敏感文件：
#   文档文件夹(00~09_*)、测评集/、eval_sets/、references_参考资料/、
#   design-preview/、outputs/、tools/、deploy-console/(临时更新控制台, 不进包)、
#   根目录调试 yaml/json/png、依赖(node_modules / .venv / .next)、
#   密钥(.env.local)、数据库(*.db) 等。
#   （未列入包含清单的根级条目天然不会被打包，下面的 --exclude 仅兜底 apps/ 内部。）
#
# 用法：  bash scripts/make-deploy-package.sh
# 产物：  项目根 moxx-deploy.tar.gz  （配合 scripts/ec2-deploy.sh 上传 ECS 使用）
# =============================================================================
set -euo pipefail

# 切到项目根（脚本位于 scripts/ 下）
cd "$(cd "$(dirname "$0")" && pwd)/.."

OUT="moxx-deploy.tar.gz"

# ---- 生成 deploy-manifest.json（供更新控制台比对版本 / 判断是否需要迁移）----
BUILD_COMMIT="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
MIG_COUNT="$(find apps/api/app/migrations -name '*.py' ! -name '__init__.py' 2>/dev/null | wc -l | tr -d ' ')"
if [ "$MIG_COUNT" -gt 0 ]; then REQUIRES_MIGRATION=true; else REQUIRES_MIGRATION=false; fi
cat > deploy-manifest.json <<EOF
{
  "build_commit": "$BUILD_COMMIT",
  "build_time": "$BUILD_TIME",
  "requires_db_migration": $REQUIRES_MIGRATION,
  "generator": "make-deploy-package.sh"
}
EOF
echo "==> 生成 deploy-manifest.json: commit=$BUILD_COMMIT  requires_db_migration=$REQUIRES_MIGRATION"

echo "==> 生成部署包：$OUT"
echo "    仅包含：apps/  package.json  package-lock.json  scripts/  .env.example  README.md  deploy-manifest.json"
echo "    排除：文档文件夹 / 测评集 / 评测工具 / deploy-console / 依赖(venv,node_modules,.next) / 密钥(.env.local) / 数据库(*.db) 等"

tar -czf "$OUT" \
  --exclude='apps/api/.venv' \
  --exclude='apps/web/.next' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='*.db' \
  --exclude='.env.local' \
  --exclude='deploy-console' \
  apps \
  package.json \
  package-lock.json \
  scripts \
  .env.example \
  README.md \
  deploy-manifest.json

# 清理临时 manifest（已嵌入包内，避免留在仓库根造成未跟踪文件）
rm -f deploy-manifest.json

echo "==> 完成。包大小："
du -h "$OUT"
echo "==> 顶层内容预览："
tar -tzf "$OUT" | sed 's#/.*##' | sort -u
