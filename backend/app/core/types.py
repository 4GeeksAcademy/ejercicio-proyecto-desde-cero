from enum import StrEnum

from sqlalchemy import CheckConstraint


def check_in(column: str, enum: type[StrEnum], name: str) -> CheckConstraint:
    """CHECK (columna IN (...valores del enum...)): la BD también protege los estados válidos."""
    values = ", ".join(f"'{m.value}'" for m in enum)
    return CheckConstraint(f"{column} IN ({values})", name=name)
