"""Comandos de administración. Ejemplo:

    TALLERYA_PASSWORD='...' uv run python -m app.cli create-user --email dueña@tallerya.co \
        --name "Propietaria" --phone +573001234567 --role OWNER

La contraseña NUNCA se pasa como argumento (quedaría en el historial del shell): variable de entorno o prompt.
"""

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select

from app.core.db import dispose_engine, get_sessionmaker
from app.core.security import hash_password
from app.modules.auth.models import Profile, Role, User


async def create_user(email: str, name: str, phone: str, role_name: str, password: str) -> None:
    async with get_sessionmaker()() as s:
        role = (await s.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
        if role is None:
            raise SystemExit(f"Rol desconocido: {role_name}")
        user = User(email=email.lower(), password_hash=hash_password(password))
        user.profile = Profile(full_name=name, phone=phone, preferred_locale="es")
        user.roles = [role]
        s.add(user)
        await s.commit()
    await dispose_engine()
    print(f"Usuario {email} creado con rol {role_name}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    cu = sub.add_parser("create-user")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--phone", required=True)
    cu.add_argument("--role", choices=["CLIENT", "ADMIN", "OWNER"], default="CLIENT")
    args = parser.parse_args()
    password = os.environ.get("TALLERYA_PASSWORD") or getpass.getpass("Contraseña: ")
    if len(password) < 10:
        sys.exit("La contraseña debe tener al menos 10 caracteres")
    asyncio.run(create_user(args.email, args.name, args.phone, args.role, password))


if __name__ == "__main__":
    main()
