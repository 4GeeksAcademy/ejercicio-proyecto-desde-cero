import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, UUIDMixin
from app.core.types import check_in


class CourseStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"  # visible y reservable
    INACTIVE = "INACTIVE"  # desactivado por el admin
    CANCELLED = "CANCELLED"  # cancelado: no reservable, reservas canceladas
    # "Finalizado" NO se guarda: se deriva de ends_at < now() (evita datos inconsistentes).


class RecordingStatus(StrEnum):
    NONE = "NONE"
    PLANNED = "PLANNED"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"


class Category(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "categories"
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    sort_order: Mapped[int] = mapped_column(nullable=False, server_default="0")
    translations: Mapped[list["CategoryTranslation"]] = relationship(lazy="selectin")


class CategoryTranslation(Base):
    __tablename__ = "category_translations"
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    locale: Mapped[str] = mapped_column(String(5))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint("category_id", "locale"),
        UniqueConstraint("locale", "slug", name="uq_category_translations_locale_slug"),
    )


class Venue(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "venues"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, server_default="Bogotá")
    country: Mapped[str] = mapped_column(String(2), nullable=False, server_default="CO")
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    maps_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)


class Instructor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "instructors"
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Course(UUIDMixin, TimestampMixin, Base):
    """Un curso = un evento de UN solo día (suposición S-01)."""

    __tablename__ = "courses"
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"))
    instructor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("instructors.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default=CourseStatus.DRAFT.value)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(40), nullable=False, server_default="America/Bogota")
    capacity: Mapped[int] = mapped_column(nullable=False)  # POR CURSO, nunca global
    price_minor: Mapped[int] = mapped_column(nullable=False)  # entero: nunca float
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="COP")
    language: Mapped[str] = mapped_column(String(5), nullable=False, server_default="es")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_recorded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    recording_status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="NONE")
    recording_url: Mapped[str | None] = mapped_column(String(500))
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    cover_image_alt: Mapped[str | None] = mapped_column(String(255))

    translations: Mapped[list["CourseTranslation"]] = relationship(lazy="selectin")
    category: Mapped[Category] = relationship(lazy="joined")
    venue: Mapped[Venue] = relationship(lazy="joined")

    __table_args__ = (
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint("price_minor >= 0", name="price_non_negative"),
        CheckConstraint("ends_at > starts_at", name="ends_after_starts"),
        check_in("status", CourseStatus, "status_valid"),
        check_in("recording_status", RecordingStatus, "recording_status_valid"),
        Index("ix_courses_status_starts_at", "status", "starts_at"),
        Index("ix_courses_category_id_starts_at", "category_id", "starts_at"),
    )


class CourseTranslation(Base):
    """Contenido por idioma: así NO duplicamos páginas ni filas del curso (i18n)."""

    __tablename__ = "course_translations"
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    locale: Mapped[str] = mapped_column(String(5))
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    short_description: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    materials: Mapped[str | None] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        PrimaryKeyConstraint("course_id", "locale"),
        UniqueConstraint("locale", "slug", name="uq_course_translations_locale_slug"),
        CheckConstraint("locale IN ('es', 'en')", name="locale_valid"),
    )
