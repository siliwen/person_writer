# 版本化数据库迁移包。
# 每个迁移文件命名：NNNN_描述.py，导出 upgrade(conn)（conn 为 SQLAlchemy Connection）。
# 铁律：只增不改；必须改列/改名时用 app.core.migrate.rebuild_table 全量拷行，绝不丢失生产数据。
