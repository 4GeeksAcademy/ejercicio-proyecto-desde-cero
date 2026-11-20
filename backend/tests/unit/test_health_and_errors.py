import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.errors import AppError, BusinessRuleError
from app.core.logging import redact_sensitive
from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()

    @app.get("/_boom")
    async def boom():
        raise RuntimeError("secreto interno")

    @app.get("/_rule")
    async def rule():
        raise BusinessRuleError("Curso lleno", code="COURSE_FULL")

    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t") as c:
        yield c


async def test_health_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert r.headers["x-request-id"]
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_request_id_propagates_when_valid(client):
    r = await client.get("/health", headers={"X-Request-ID": "abc12345-req"})
    assert r.headers["x-request-id"] == "abc12345-req"


async def test_request_id_rejects_garbage(client):
    r = await client.get("/health", headers={"X-Request-ID": "x\ny"})
    assert r.headers["x-request-id"] != "x\ny"


async def test_business_error_format(client):
    r = await client.get("/_rule")
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "COURSE_FULL" and err["request_id"]


async def test_unexpected_error_hides_internals(client):
    r = await client.get("/_boom")
    assert r.status_code == 500
    assert "secreto interno" not in r.text and "Traceback" not in r.text
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"


async def test_404_uses_uniform_format(client):
    r = await client.get("/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_logs_redact_secrets():
    out = redact_sensitive(None, "", {"password": "x", "token": "y", "event": "e", "email": "a@b.c"})
    assert out["password"] == "[REDACTED]" and out["token"] == "[REDACTED]" and out["event"] == "e"
    json.dumps(out)


def test_app_error_defaults():
    assert AppError().status_code == 500
