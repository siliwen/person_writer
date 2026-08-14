#!/usr/bin/env bash
# 生产更新安全序列（由 deploy-console 触发；也可手动执行）。
# 设计要点：
#  - 不删除 /opt/moxx/apps，直接「覆盖解压」——tar 只覆盖包内文件，包外的
#    *.db / .env.local / .venv / .next 天然不动，生产数据零风险。
#  - 任一步失败 -> 自动回滚（恢复 db 备份 + 重解压上一份代码包 + 重启）。
#  - 数据库迁移走版本化运行器（app.core.migrate），只增不改，保数据。
set -euo pipefail

MOXX="${MOXX_ROOT:-/opt/moxx}"
API="$MOXX/apps/api"
WEB="$MOXX/apps/web"
INCOMING="$MOXX/incoming"
TAR="$INCOMING/moxx-deploy.tar.gz"
TAR_PREV="$TAR.prev"
APP_USER="${APP_USER:-moxx}"
DB="$API/personal_writing_agent_mvp1.db"

TS="$(date +%Y%m%d_%H%M%S)"
LOG="${LOG:-/opt/moxx/update-$TS.log}"
DB_BACKUP="/root/moxx-db-backup-$TS.db"
ENV_BACKUP="/root/moxx-env-backup-$TS.local"

# 全部日志同时落盘，便于控制台轮询读取
exec > >(tee -a "$LOG") 2>&1

on_fail() {
  echo "[FAIL] 更新失败，开始回滚（日志：$LOG）"
  if [ -f "$DB_BACKUP" ]; then
    cp "$DB_BACKUP" "$DB"
    echo "[ROLLBACK] 已恢复数据库备份 -> $DB"
  fi
  if [ -f "$TAR_PREV" ]; then
    echo "[ROLLBACK] 恢复上一份代码包..."
    tar -xzf "$TAR_PREV" -C "$MOXX"
    chown -R "$APP_USER:$APP_USER" "$API" "$WEB" "$MOXX/scripts" 2>/dev/null || true
  fi
  systemctl start moxx-api moxx-web 2>/dev/null || true
  echo "[FAIL] 回滚完成。请检查日志并人工确认服务状态。"
}
trap on_fail ERR

echo "===== 开始更新 $TS ====="
echo "[pre] 检查更新包"
[ -f "$TAR" ] || { echo "[pre] 未找到 $TAR，中止"; exit 1; }
# 磁盘空间预警（解压 + 前端构建至少需要 ~500MB 余量）
AVAIL=$(df -m "$MOXX" | awk 'NR==2{print $4}')
if [ "${AVAIL:-0}" -lt 500 ]; then
  echo "[pre] 磁盘可用空间不足 500MB（当前 ${AVAIL}MB），中止"; exit 1
fi

echo "[1/6] 备份数据库与 .env.local"
cp "$DB" "$DB_BACKUP"
[ -f "$API/.env.local" ] && cp "$API/.env.local" "$ENV_BACKUP"
cp "$TAR" "$TAR_PREV"   # 上一份代码包，供回滚

echo "[2/6] 停止服务（释放 SQLite 写锁，避免迁移冲突）"
systemctl stop moxx-api moxx-web || true
sleep 2

echo "[3/6] 覆盖解压（保留 db / .env.local / .venv / .next）"
tar -xzf "$TAR" -C "$MOXX"
chown -R "$APP_USER:$APP_USER" "$API" "$WEB" "$MOXX/scripts" 2>/dev/null || true

echo "[4/6] 执行数据库迁移（版本化、只增不改、保数据）"
export DATABASE_URL="sqlite+pysqlite:///$API/personal_writing_agent_mvp1.db"
cd "$API"
.venv/bin/python -m app.core.migrate

echo "[5/6] 安装依赖并构建前端"
cd "$API" && .venv/bin/pip install -r requirements.txt || true
cd "$WEB" && npm install && NEXT_PUBLIC_API_BASE_URL=/api npm run build

echo "[6/6] 重启服务与健康检查"
systemctl daemon-reload
systemctl start moxx-api moxx-web
sleep 6
if curl -fsS http://127.0.0.1:8010/healthz >/dev/null; then
  echo "[ok] API /healthz 正常"
else
  echo "[FAIL] API 健康检查未通过"; exit 1
fi
if systemctl is-active --quiet moxx-web; then
  echo "[ok] moxx-web 运行中"
else
  echo "[FAIL] moxx-web 未运行"; exit 1
fi

echo "===== 更新成功 $TS ====="
echo "日志：$LOG"
