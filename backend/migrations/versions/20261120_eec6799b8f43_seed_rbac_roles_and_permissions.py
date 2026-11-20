"""seed rbac roles and permissions

Revision ID: eec6799b8f43
Revises: 116765fb8ef6
Create Date: 2026-11-20 20:01:37.357167
"""

import sqlalchemy as sa
from alembic import op

revision = "eec6799b8f43"
down_revision = "116765fb8ef6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.rbac_seed import ALL_PERMISSIONS, ROLES

    conn = op.get_bind()
    for p in ALL_PERMISSIONS:
        conn.execute(sa.text("INSERT INTO permissions (id, name) VALUES (gen_random_uuid(), :n)"), {"n": p})
    for role, (desc, perms) in ROLES.items():
        conn.execute(
            sa.text("INSERT INTO roles (id, name, description) VALUES (gen_random_uuid(), :n, :d)"),
            {"n": role, "d": desc},
        )
        for p in perms:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = :r AND p.name = :p"
                ),
                {"r": role, "p": p},
            )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions")
    op.execute("DELETE FROM roles")
    op.execute("DELETE FROM permissions")
