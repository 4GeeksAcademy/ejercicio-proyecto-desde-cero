"""Definición ÚNICA de roles y permisos (la usan la migración y los tests)."""

CLIENT_PERMS = [
    "profile:manage_own",
    "booking:create",
    "booking:read_own",
    "booking:cancel_own",
    "payment:read_own",
    "notification:read_own",
]
ADMIN_PERMS = CLIENT_PERMS + [
    "course:write",
    "booking:read_all",
    "booking:approve",
    "booking:cancel_any",
    "payment:read_all",
    "user:read_all",
    "metrics:read_business",
]
OWNER_PERMS = ADMIN_PERMS + [
    "admin:manage",
    "commission:read",
    "audit:read",
    "settings:write",
    "ops:read",
]

ROLES: dict[str, tuple[str, list[str]]] = {
    "CLIENT": ("Cliente / alumno", CLIENT_PERMS),
    "ADMIN": ("Administrador", ADMIN_PERMS),
    "OWNER": ("Propietario / superadmin", OWNER_PERMS),
    # INSTRUCTOR: se añadirá en el futuro sin tocar el modelo.
}
ALL_PERMISSIONS = sorted(set(OWNER_PERMS))
