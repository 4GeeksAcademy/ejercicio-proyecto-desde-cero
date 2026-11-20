"""Rate limiting en memoria (ventana deslizante).

Suficiente para UNA instancia. Con varias instancias hará falta un almacén compartido (Redis): ADR futuro.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request

from app.core.errors import AppError


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Demasiados intentos. Inténtalo de nuevo más tarde."


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit, self.window, self.clock = limit, window_seconds, clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = self.clock()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise RateLimitedError()
        q.append(now)

    def reset(self) -> None:
        self._hits.clear()


def rate_limit(name: str, limit: int, window_seconds: int) -> Callable[[Request], None]:
    limiter = SlidingWindowLimiter(limit, window_seconds)
    _registry.append(limiter)

    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        limiter.check(f"{name}:{ip}")

    return dependency


_registry: list[SlidingWindowLimiter] = []


def reset_all_limiters() -> None:
    for lim in _registry:
        lim.reset()
