import json

from sqlalchemy import select, text

from app.modules.auth.models import PasswordResetToken, RefreshToken, User, UserConsent
from tests.integration.conftest import REGISTER, csrf_headers

API = "/api/v1"


async def register(client, **over):
    return await client.post(f"{API}/auth/register", json={**REGISTER, **over})


async def test_register_creates_client_user_and_logs_in(client, session):
    r = await register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["roles"] == ["CLIENT"] and "booking:create" in body["permissions"]
    assert body["marketing_consent"] is False
    assert "password" not in r.text and "password_hash" not in r.text
    assert {"access_token", "refresh_token", "csrf_token"} <= set(client.cookies.keys())
    me = await client.get(f"{API}/users/me")
    assert me.status_code == 200 and me.json()["email"] == "ana@example.com"


async def test_password_is_stored_as_argon2_hash(client, session):
    await register(client)
    h = (await session.execute(text("SELECT password_hash FROM users"))).scalar_one()
    assert h.startswith("$argon2id$") and "una-clave-larga-123" not in h


async def test_terms_are_mandatory(client):
    r = await register(client, accept_terms=False)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "una-clave-larga-123" not in r.text  # no se refleja el valor enviado


async def test_marketing_never_preselected_and_recorded_when_given(client, session):
    await register(client)
    kinds = [c.consent_type for c in (await session.execute(select(UserConsent))).scalars()]
    assert sorted(kinds) == ["privacy", "terms"]  # sin marketing por defecto


async def test_marketing_consent_recorded_with_history(client, session):
    await register(client, marketing_consent=True)
    assert (await client.get(f"{API}/users/me")).json()["marketing_consent"] is True
    r = await client.put(f"{API}/users/me/consents", json={"marketing": False}, headers=csrf_headers(client))
    assert r.json()["marketing_consent"] is False
    rows = (await session.execute(select(UserConsent).where(UserConsent.consent_type == "marketing"))).scalars().all()
    assert sorted(c.granted for c in rows) == [False, True]  # historial, no sobrescritura


async def test_invalid_phone_and_short_password(client):
    assert (await register(client, phone="3001234567")).status_code == 422
    assert (await register(client, password="corta")).status_code == 422


async def test_duplicate_email_case_insensitive(client, new_client):
    assert (await register(client)).status_code == 201
    other = await new_client()
    r = await register(other, email="ANA@example.com")
    assert r.status_code == 409 and r.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_login_wrong_password_and_unknown_email_look_identical(client, new_client):
    await register(client)
    c2 = await new_client()
    a = await c2.post(f"{API}/auth/login", json={"email": "ana@example.com", "password": "mala-clave-123"})
    b = await c2.post(f"{API}/auth/login", json={"email": "nadie@example.com", "password": "mala-clave-123"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


async def test_account_locks_after_repeated_failures(client, new_client):
    await register(client)
    c2 = await new_client()
    for _ in range(5):
        await c2.post(f"{API}/auth/login", json={"email": "ana@example.com", "password": "mala-clave-123"})
    r = await c2.post(f"{API}/auth/login", json={"email": "ana@example.com", "password": REGISTER["password"]})
    assert r.status_code == 423 and r.json()["error"]["code"] == "ACCOUNT_LOCKED"


async def test_login_rate_limited(new_client):
    c = await new_client()
    codes = [
        (await c.post(f"{API}/auth/login", json={"email": "x@example.com", "password": "mala-clave-123"})).status_code
        for _ in range(12)
    ]
    assert 429 in codes


async def test_me_requires_authentication(client):
    r = await client.get(f"{API}/users/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "NOT_AUTHENTICATED"


async def test_tampered_access_token_rejected(client):
    await register(client)
    client.cookies.set("access_token", "x.y.z")
    assert (await client.get(f"{API}/users/me")).status_code == 401


async def test_csrf_required_for_mutations(client):
    await register(client)
    r = await client.patch(f"{API}/users/me", json={"full_name": "Otro"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_FAILED"
    ok = await client.patch(f"{API}/users/me", json={"full_name": "Otro"}, headers=csrf_headers(client))
    assert ok.status_code == 200 and ok.json()["full_name"] == "Otro"


async def test_refresh_rotates_and_reuse_revokes_family(client, new_client, session):
    await register(client)
    old_refresh = client.cookies.get("refresh_token", path="/api/v1/auth")
    r = await client.post(f"{API}/auth/refresh")
    assert r.status_code == 200
    new_refresh = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert new_refresh != old_refresh

    attacker = await new_client()
    attacker.cookies.set("refresh_token", old_refresh, path="/api/v1/auth")
    assert (await attacker.post(f"{API}/auth/refresh")).status_code == 401  # reutilización detectada

    # la familia entera queda revocada: el refresh legítimo "nuevo" tampoco sirve ya
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401
    live = (await session.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_(None)))).scalars().all()
    assert live == []


async def test_refresh_tokens_stored_hashed(client, session):
    await register(client)
    raw = client.cookies.get("refresh_token", path="/api/v1/auth")
    stored = (await session.execute(select(RefreshToken.token_hash))).scalar_one()
    assert stored != raw and len(stored) == 64


async def test_logout_revokes_session(client):
    await register(client)
    assert (await client.post(f"{API}/auth/logout")).status_code == 204
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401


async def test_password_reset_flow(client, new_client, mailer, session):
    await register(client)
    c2 = await new_client()
    assert (await c2.post(f"{API}/auth/forgot-password", json={"email": "nadie@example.com"})).status_code == 202
    assert mailer.sent == []  # no revela ni envía nada si no existe
    assert (await c2.post(f"{API}/auth/forgot-password", json={"email": "ana@example.com"})).status_code == 202
    assert len(mailer.sent) == 1
    token = mailer.sent[0].body.split("token=")[1].split()[0]
    stored = (await session.execute(select(PasswordResetToken.token_hash))).scalar_one()
    assert token not in stored  # solo se guarda el hash

    r = await c2.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "nueva-clave-segura-1"})
    assert r.status_code == 204
    again = await c2.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "otra-clave-segura-2"})
    assert again.status_code == 401  # un solo uso
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401  # sesiones antiguas cerradas
    ok = await c2.post(f"{API}/auth/login", json={"email": "ana@example.com", "password": "nueva-clave-segura-1"})
    assert ok.status_code == 200


async def test_invalid_reset_token(client):
    r = await client.post(
        f"{API}/auth/reset-password", json={"token": "x" * 40, "new_password": "nueva-clave-segura-1"}
    )
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_RESET_TOKEN"


async def test_secrets_never_appear_in_logs(client, capsys):
    await register(client)
    await client.post(f"{API}/auth/login", json={"email": "ana@example.com", "password": REGISTER["password"]})
    out = capsys.readouterr().out
    assert REGISTER["password"] not in out
    assert client.cookies.get("access_token") not in out
    for line in out.splitlines():
        if line.startswith("{"):
            json.loads(line)  # cada línea es JSON válido


async def test_anonymize_account(client, new_client, session):
    await register(client)
    assert (await client.delete(f"{API}/users/me", headers=csrf_headers(client))).status_code == 204
    u = (await session.execute(select(User))).scalar_one()
    assert u.anonymized_at and u.email.endswith("@anonymized.invalid")
    c2 = await new_client()
    r = await c2.post(f"{API}/auth/login", json={"email": "ana@example.com", "password": REGISTER["password"]})
    assert r.status_code == 401
