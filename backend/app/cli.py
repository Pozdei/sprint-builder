"""CLI-команды.

Запуск (из папки backend):
    python -m app.cli create-admin

Команда create-admin запрашивает email и пароль, создаёт пользователя
с ролью admin. Полезно, когда нужно завести админа без правки SQL.
"""

import argparse
import getpass
import sys

from app.core.security import hash_password
from app.db import users_repository
from app.db.session import SessionLocal


def cmd_create_admin(args: argparse.Namespace) -> int:
    email = args.email or input("Email админа: ").strip()
    if not email:
        print("Email не может быть пустым")
        return 1

    password = args.password
    if not password:
        password = getpass.getpass("Пароль: ")
        confirm = getpass.getpass("Повтори пароль: ")
        if password != confirm:
            print("Пароли не совпадают")
            return 1
    if not password:
        print("Пароль не может быть пустым")
        return 1

    display_name = args.name or "Администратор"

    db = SessionLocal()
    try:
        existing = users_repository.get_user_by_email(db, email)
        if existing:
            print(f"Пользователь {email} уже существует "
                  f"(id={existing.id}, role={existing.role})")
            return 1

        user = users_repository.create_user(
            db,
            email=email,
            password_hash=hash_password(password),
            role="admin",
            display_name=display_name,
        )
        print(f"Создан администратор id={user.id}, email={user.email}")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint Builder CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_admin = sub.add_parser("create-admin", help="Создать администратора")
    p_admin.add_argument("--email", help="Email")
    p_admin.add_argument("--password",
                          help="Пароль (опаснее — будет в истории shell)")
    p_admin.add_argument("--name", help="Отображаемое имя", default="")

    args = parser.parse_args()

    if args.command == "create-admin":
        return cmd_create_admin(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
