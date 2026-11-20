"""Crea .env a partir de .env.example con secretos aleatorios. No sobrescribe un .env existente.

Uso: python scripts/init_env.py
"""

import re
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
target = root / ".env"
if target.exists():
    print(".env ya existe; no se modifica.")
    raise SystemExit(0)

text = (root / ".env.example").read_text()
text = re.sub(r"(?m)^POSTGRES_PASSWORD=.*$", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}", text)
text = re.sub(r"(?m)^JWT_SECRET=.*$", f"JWT_SECRET={secrets.token_urlsafe(48)}", text)
target.write_text(text)
print(".env creado con secretos aleatorios (está ignorado por Git).")
