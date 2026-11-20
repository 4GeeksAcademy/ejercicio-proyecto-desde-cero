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
    ok = Settings(app_env="production", jwt_secret="x" * 40, payment_webhook_secret="y" * 40, payment_provider="wompi")
    assert ok.is_production
