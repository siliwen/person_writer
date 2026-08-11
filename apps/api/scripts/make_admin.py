"""把指定用户设为 / 取消管理员。

用法（在 apps/api 目录下执行）：
    ./.venv/Scripts/python.exe scripts/make_admin.py <username>          # 设为管理员
    ./.venv/Scripts/python.exe scripts/make_admin.py <username> --revoke # 取消管理员
    ./.venv/Scripts/python.exe scripts/make_admin.py --list              # 列出所有管理员
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="管理员权限管理")
    parser.add_argument("username", nargs="?", help="目标用户名")
    parser.add_argument("--revoke", action="store_true", help="取消管理员权限")
    parser.add_argument("--list", action="store_true", help="列出所有管理员")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.list:
            admins = db.scalars(select(models.User).where(models.User.is_admin.is_(True))).all()
            if not admins:
                print("当前没有管理员账号。")
            for u in admins:
                print(f"{u.id}\t{u.username}\t{u.display_name}")
            return 0

        if not args.username:
            parser.error("需要提供用户名，或使用 --list")

        user = db.scalar(select(models.User).where(models.User.username == args.username))
        if not user:
            print(f"未找到用户：{args.username}", file=sys.stderr)
            return 1

        user.is_admin = not args.revoke
        db.commit()
        action = "已取消管理员权限" if args.revoke else "已设为管理员"
        print(f"{action}：{user.username}（{user.id}）")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
