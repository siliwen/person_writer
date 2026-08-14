from __future__ import annotations

import os
import shutil
import tempfile
import textwrap

from sqlalchemy import create_engine, text

from app.core import migrate


def _file_engine():
    # 文件型 sqlite：跨连接天然共享同一库，避免内存库 StaticPool 的连接隔离问题
    d = tempfile.mkdtemp(prefix="migtest_")
    db_path = os.path.join(d, "test.db")
    eng = create_engine(f"sqlite:///{db_path}")
    eng._migtest_dir = d  # type: ignore[attr-defined]
    return eng


def _make_migrations(*bodies: str):
    # 迁移模块写在临时目录，不污染 app/migrations/，也不触发仓库删除拦截
    d = tempfile.mkdtemp(prefix="mig_")
    items = []
    for i, body in enumerate(bodies, start=1):
        name = f"900{i}_m"
        path = os.path.join(d, name + ".py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        items.append((name, path))
    return d, items


def _cleanup(*dirs) -> None:
    for d in dirs:
        try:
            shutil.rmtree(d)
        except OSError:
            pass


def test_add_column_idempotent():
    eng = _file_engine()
    with eng.begin() as c:
        c.execute(text("CREATE TABLE t1 (id INTEGER PRIMARY KEY, a TEXT)"))
        c.execute(text("INSERT INTO t1 (id, a) VALUES (1, 'x')"))

    d, items = _make_migrations(
        textwrap.dedent(
            """
            from app.core.migrate import add_column_if_missing
            def upgrade(conn):
                add_column_if_missing(conn, "t1", "b", "TEXT")
            """
        )
    )
    try:
        applied = migrate.run_migrations(eng, migrations=items)
        assert items[0][0] in applied, "首次应执行迁移"
        applied2 = migrate.run_migrations(eng, migrations=items)
        assert applied2 == [], "二次执行应幂等、不重复应用"
        with eng.connect() as c:
            cols = {r[1] for r in c.execute(text("PRAGMA table_info(t1)")).fetchall()}
            assert "b" in cols, "列应已新增"
            val = c.execute(text("SELECT a, b FROM t1")).fetchone()
            assert val[0] == "x", "旧数据应保留"
            assert val[1] is None, "新增列对既有行应为 NULL"
    finally:
        _cleanup(d, eng._migtest_dir)


def test_rebuild_preserves_rows():
    eng = _file_engine()
    with eng.begin() as c:
        c.execute(text("CREATE TABLE t2 (id INTEGER PRIMARY KEY, old_name TEXT)"))
        c.execute(text("INSERT INTO t2 (id, old_name) VALUES (1, 'alice'), (2, 'bob')"))

    d, items = _make_migrations(
        textwrap.dedent(
            """
            from app.core.migrate import rebuild_table
            def upgrade(conn):
                rebuild_table(conn, "t2",
                    new_ddl="id INTEGER PRIMARY KEY, name TEXT",
                    select_cols="id, old_name",
                    insert_cols="id, name")
            """
        )
    )
    try:
        migrate.run_migrations(eng, migrations=items)
        with eng.connect() as c:
            rows = c.execute(text("SELECT id, name FROM t2 ORDER BY id")).fetchall()
            assert [(r[0], r[1]) for r in rows] == [(1, "alice"), (2, "bob")], "重建表应完整保留行"
    finally:
        _cleanup(d, eng._migtest_dir)


def test_skip_already_applied():
    eng = _file_engine()
    with eng.begin() as c:
        c.execute(text("CREATE TABLE t3 (id INTEGER PRIMARY KEY)"))

    d, items = _make_migrations("def upgrade(conn):\n    pass\n")
    try:
        a1 = migrate.run_migrations(eng, migrations=items)
        assert items[0][0] in a1
        a2 = migrate.run_migrations(eng, migrations=items)
        assert a2 == [], "已应用版本应跳过"
    finally:
        _cleanup(d, eng._migtest_dir)


def test_no_migrations_is_noop():
    eng = _file_engine()
    applied = migrate.run_migrations(eng, migrations=[])
    assert applied == []
    with eng.connect() as c:
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()}
        assert "schema_migrations" in tables
    _cleanup(eng._migtest_dir)
