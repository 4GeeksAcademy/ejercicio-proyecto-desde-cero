import pytest
from httpx import ASGITransport, AsyncClient

from app.core import clock
from app.core.mail import InMemoryMailer, set_mailer
from app.core.rate_limit import reset_all_limiters
from app.main import create_app


@pytest.fixture(autouse=True)
def _reset_state():
    reset_all_limiters()
    yield
    set_mailer(None)
    clock.freeze(None)


@pytest.fixture
def mailer() -> InMemoryMailer:
    m = InMemoryMailer()
    set_mailer(m)
    return m


@pytest.fixture
def app():
    a = create_app()
    return a


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as c:
        yield c


def csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("csrf_token") or ""}


REGISTER = {
    "email": "ana@example.com",
    "password": "una-clave-larga-123",
    "full_name": "Ana Pérez",
    "phone": "+573001234567",
    "preferred_locale": "es",
    "accept_terms": True,
}


@pytest.fixture
async def new_client(app):
    """Fábrica de clientes independientes (cada uno con su propia sesión/cookies)."""
    clients: list[AsyncClient] = []

    async def make() -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test")
        clients.append(c)
        return c

    yield make
    for c in clients:
        await c.aclose()


@pytest.fixture
async def auth_client(app):
    """Fábrica: cliente HTTP ya autenticado como `user` (sin pasar por login, que es lento por argon2)."""
    from app.core.security import create_access_token

    clients: list[AsyncClient] = []

    async def make(user) -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test")
        c.cookies.set("access_token", create_access_token(user.id))
        c.cookies.set("csrf_token", "csrf-test-token")
        c.headers["X-CSRF-Token"] = "csrf-test-token"
        clients.append(c)
        return c

    yield make
    for c in clients:
        await c.aclose()
