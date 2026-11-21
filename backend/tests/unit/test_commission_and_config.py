import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.payments.commission import compute_commission


def test_twenty_percent_of_100000():
    assert compute_commission(100_000, 2000) == (20_000, 80_000)


@pytest.mark.parametrize(
    ("gross", "bps", "expected"),
    [
        (0, 2000, (0, 0)),
        (1, 2000, (0, 1)),
        (3, 2000, (1, 2)),
        (5, 1000, (1, 4)),
        (100, 0, (0, 100)),
        (100, 10_000, (100, 0)),
    ],
)
def test_rounding_cases(gross, bps, expected):
    assert compute_commission(gross, bps) == expected


@given(gross=st.integers(min_value=0, max_value=10**12), bps=st.integers(min_value=0, max_value=10_000))
def test_commission_plus_net_always_equals_gross(gross, bps):
    c, n = compute_commission(gross, bps)
    assert c + n == gross and c >= 0 and n >= 0 and c <= gross


def test_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        compute_commission(-1, 2000)
    with pytest.raises(ValueError):
        compute_commission(100, 10_001)


def test_money_is_integer_not_float():
    c, n = compute_commission(19_999_99, 2000)
    assert isinstance(c, int) and isinstance(n, int)


def test_production_refuses_default_secrets():
    with pytest.raises(ValidationError):
        Settings(app_env="production")
    with pytest.raises(ValidationError):
        Settings(app_env="staging", jwt_secret="x" * 40, payment_webhook_secret="y" * 40)  # proveedor 'fake'
    ok = Settings(
        app_env="production",
        jwt_secret="x" * 40,
        payment_webhook_secret="y" * 40,
        payment_provider="wompi",
        cookie_secure=True,
    )
    assert ok.is_production
    with pytest.raises(ValidationError):  # cookies sin Secure fuera de desarrollo
        Settings(app_env="production", jwt_secret="x" * 40, payment_webhook_secret="y" * 40, payment_provider="wompi")


def _req(xff: str | None, peer: str = "172.18.0.5"):
    from starlette.requests import Request

    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234), "method": "GET", "path": "/"})


def test_client_ip_ignores_forwarded_header_without_trusted_proxy(monkeypatch):
    from app.core.rate_limit import client_ip

    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "0")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert client_ip(_req("9.9.9.9")) == "172.18.0.5"  # sin proxy de confianza no se cree la cabecera
    get_settings.cache_clear()


def test_client_ip_uses_rightmost_entry_added_by_our_proxy(monkeypatch):
    from app.core.config import get_settings
    from app.core.rate_limit import client_ip

    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    get_settings.cache_clear()
    # el atacante escribe "1.2.3.4" a la izquierda; nuestro proxy añade la IP real a la derecha
    assert client_ip(_req("1.2.3.4, 203.0.113.7")) == "203.0.113.7"
    assert client_ip(_req(None)) == "172.18.0.5"
    get_settings.cache_clear()


def test_database_url_from_render_style_url():
    s = Settings(DATABASE_URL="postgres://user:pa55@dpg-abc.render.internal/tallerya_db")
    assert s.database_url == "postgresql+psycopg://user:pa55@dpg-abc.render.internal/tallerya_db"
    assert Settings(DATABASE_URL="postgresql://u:p@h:5432/d").database_url == "postgresql+psycopg://u:p@h:5432/d"
    assert Settings().database_url.startswith(
        "postgresql+psycopg://tallerya:"
    )  # sin DATABASE_URL: variables POSTGRES_*


def test_fake_payments_allowed_outside_dev_only_in_explicit_demo():
    base = dict(app_env="staging", jwt_secret="x" * 40, payment_webhook_secret="y" * 40, cookie_secure=True)
    with pytest.raises(ValidationError):
        Settings(**base)  # proveedor fake sin permiso explícito
    demo = Settings(**base, allow_fake_payments=True)
    assert demo.dev_endpoints_enabled is True  # la demo puede simular pagos
    real = Settings(**base, payment_provider="wompi")
    assert real.dev_endpoints_enabled is False  # con proveedor real NO hay endpoints /dev
