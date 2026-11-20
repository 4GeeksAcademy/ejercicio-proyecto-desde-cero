"""add payment refund permission

Revision ID: db812a97f940
Revises: ca558284a0df
Create Date: 2026-11-20 20:15:09.935237
"""
from alembic import op
import sqlalchemy as sa


revision = 'db812a97f940'
down_revision = 'ca558284a0df'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotente: en una BD nueva el permiso ya pudo crearlo la migración de semilla RBAC.
    op.execute("INSERT INTO permissions (id, name) SELECT gen_random_uuid(), 'payment:refund' WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE name = 'payment:refund')")
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r, permissions p
        WHERE r.name IN ('ADMIN', 'OWNER') AND p.name = 'payment:refund'
          AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = r.id AND rp.permission_id = p.id)
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE name = 'payment:refund')")
    op.execute("DELETE FROM permissions WHERE name = 'payment:refund'")
