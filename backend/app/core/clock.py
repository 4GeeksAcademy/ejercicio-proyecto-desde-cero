"""Reloj inyectable: los tests pueden 'viajar en el tiempo' para probar las reglas de 24 h."""

from datetime import UTC, datetime

_override: datetime | None = None


def now() -> datetime:
    return _override or datetime.now(UTC)


def freeze(moment: datetime | None) -> None:
    global _override
    _override = moment
