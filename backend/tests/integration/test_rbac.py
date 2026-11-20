from sqlalchemy import select

from app.core.security import hash_password
from app.modules.audit.models import AuditLog
from app.modules.auth.models import Profile, Role, User
from tests.integration.conftest import REGISTER, csrf_headers

API = "/api/v1"


async def make_staff(session, email, role_name):
    role = (await session.execute(select(Role).where(Role.name == role_name))).scalar_one()
    u = User(email=email, password_hash=hash_password("clave-de-staff-123"))
    u.profile = Profile(full_name=role_name.title(), phone="+573000000000", preferred_locale="es")
    u.roles = [role]
    session.add(u)
    await session.commit()
    return u


async def login(client, email, password="clave-de-staff-123"):
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


async def test_visitor_gets_401_on_admin(client):
    assert (await client.get(f"{API}/admin/users")).status_code == 401


async def test_client_gets_403_on_admin(client):
    await client.post(f"{API}/auth/register", json=REGISTER)
    r = await client.get(f"{API}/admin/users")
    assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_can_list_users_but_not_manage_admins(client, session):
    await make_staff(session, "admin@tallerya.co", "ADMIN")
    await login(client, "admin@tallerya.co")
    assert (await client.get(f"{API}/admin/users")).status_code == 200
    r = await client.post(f"{API}/admin/admins", json={"email": "x@example.com"}, headers=csrf_headers(client))
    assert r.status_code == 403


async def test_owner_grants_and_revokes_admin_with_audit(client, new_client, session):
    await make_staff(session, "owner@tallerya.co", "OWNER")
    target = await new_client()
    await target.post(f"{API}/auth/register", json=REGISTER)
    await login(client, "owner@tallerya.co")

    r = await client.post(f"{API}/admin/admins", json={"email": "ana@example.com"}, headers=csrf_headers(client))
    assert r.status_code == 201 and "ADMIN" in r.json()["roles"]
    uid = r.json()["id"]
    again = await client.post(f"{API}/admin/admins", json={"email": "ana@example.com"}, headers=csrf_headers(client))
    assert again.status_code == 409

    assert (await client.delete(f"{API}/admin/admins/{uid}", headers=csrf_headers(client))).status_code == 204
    actions = [a.action for a in (await session.execute(select(AuditLog).order_by(AuditLog.id))).scalars()]
    assert actions == ["permission.admin_granted", "permission.admin_revoked"]


async def test_permission_change_takes_effect_immediately(client, new_client, session):
    """Los permisos se leen de la BD en cada petición: quitar el rol corta el acceso sin esperar al token."""
    await make_staff(session, "owner@tallerya.co", "OWNER")
    admin_client = await new_client()
    await admin_client.post(f"{API}/auth/register", json=REGISTER)
    await login(client, "owner@tallerya.co")
    r = await client.post(f"{API}/admin/admins", json={"email": "ana@example.com"}, headers=csrf_headers(client))
    assert (await admin_client.get(f"{API}/admin/users")).status_code == 200
    await client.delete(f"{API}/admin/admins/{r.json()['id']}", headers=csrf_headers(client))
    assert (await admin_client.get(f"{API}/admin/users")).status_code == 403
