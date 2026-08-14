from __future__ import annotations

import importlib.util
import os
import re
from datetime import datetime, timezone

from sqlalchemy import text

# 版本化迁移包放在 app/migrations/，与 core 解耦，便于按文件名序号排序与按路径加载
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS_DIR = os.path.join(APP_DIR, "migrations")
MIGRATIONS_PACKAGE = "app.migrations"


def _discover_migrations() -> list[tuple[str, str]]:
    """返回 [(模块名, 文件路径), ...]，按文件名前导数字序号升序。

    文件名约定：NNNN_描述.py（NNNN 为 4 位序号，决定是否执行顺序）。
    """
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    items: list[tuple[int, str, str]] = []
    for fn in os.listdir(MIGRATIONS_DIR):
        if fn == "__init__.py" or not fn.endswith(".py"):
            continue
        m = re.match(r"^(\d{4})_[A-Za-z0-9_]+\.py$", fn)
        if m:
            items.append((int(m.group(1)), fn[:-3], os.path.join(MIGRATIONS_DIR, fn)))
    items.sort(key=lambda x: x[0])
    return [(name, path) for _, name, path in items]


def _load_migration(module_name: str, path: str):
    """按文件路径加载迁移模块，绕过「模块名须为合法标识符」的限制。"""
    spec = importlib.util.spec_from_file_location(f"{MIGRATIONS_PACKAGE}._{module_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ensure_schema_versions_table(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
        )


def get_applied_versions(engine) -> set[str]:
    ensure_schema_versions_table(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {row[0] for row in rows}


def run_migrations(engine, migrations: list[tuple[str, str]] | None = None) -> list[str]:
    """执行未应用的版本化迁移。

    每个迁移模块导出 `upgrade(conn)`，conn 为 SQLAlchemy Connection（已在事务内）。
    幂等：已记录到 schema_migrations 的版本号会被跳过。返回本次实际执行的模块名列表。
    """
    ensure_schema_versions_table(engine)
    applied = get_applied_versions(engine)
    items = migrations if migrations is not None else _discover_migrations()
    applied_now: list[str] = []
    for name, path in items:
        if name in applied:
            continue
        mod = _load_migration(name, path)
        with engine.begin() as conn:
            mod.upgrade(conn)
            conn.execute(
                text("INSERT INTO schema_migrations (version, applied_at) VALUES (:v, :t)"),
                {"v": name, "t": datetime.now(timezone.utc).isoformat()},
            )
        applied_now.append(name)
    return applied_now


def column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def add_column_if_missing(conn, table: str, column: str, definition: str) -> bool:
    """仅当列不存在时新增列；返回是否新增。配合幂等迁移使用。

    SQLite 支持 ADD COLUMN，但无法 ALTER 已有列类型/改名，需改列请用 rebuild_table。
    """
    if column_exists(conn, table, column):
        return False
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
    return True


def rebuild_table(conn, table: str, new_ddl: str, select_cols: str, insert_cols: str) -> None:
    """重建表并保留全部行（用于改名/改列类型等 SQLite 无法 ALTER 的场景）。

    new_ddl:        新表列定义，如 "id INTEGER PRIMARY KEY, name TEXT"
    select_cols:    从旧表选取的列，如 "id, old_name"
    insert_cols:    写入新表的列，如 "id, name"
    过程：建临时表 → 全量拷贝行 → 删旧表 → 临时表改名。绝不丢失数据。
    """
    tmp = f"__{table}_mig_tmp"
    conn.execute(text(f"CREATE TABLE {tmp} ({new_ddl})"))
    conn.execute(text(f"INSERT INTO {tmp} ({insert_cols}) SELECT {select_cols} FROM {table}"))
    conn.execute(text(f"DROP TABLE {table}"))
    conn.execute(text(f"ALTER TABLE {tmp} RENAME TO {table}"))


if __name__ == "__main__":
    # 部署更新时：先 init_db 兜底建表/补列（含 seed，幂等），再跑版本化迁移（未来 schema 变更）。
    from app.database import engine, init_db

    init_db()
    applied = run_migrations(engine)
    if applied:
        print(f"[migrate] applied {len(applied)} migration(s): {', '.join(applied)}")
    else:
        print("[migrate] no pending migrations")
