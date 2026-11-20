"""Importa TODOS los modelos para que Alembic y SQLAlchemy los conozcan."""

from app.modules.analytics.models import AnalyticsEvent, DailyCourseMetrics
from app.modules.audit.models import AuditLog
from app.modules.auth.models import (
    PasswordResetToken,
    Permission,
    Profile,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserConsent,
    UserRole,
)
from app.modules.bookings.models import Booking, BookingStatusHistory, IdempotencyKey
from app.modules.core_events.models import DomainEvent
from app.modules.courses.models import (
    Category,
    CategoryTranslation,
    Course,
    CourseTranslation,
    Instructor,
    Venue,
)
from app.modules.notifications.models import Notification, NotificationPreference
from app.modules.payments.models import AppSetting, Commission, Payment, PaymentEvent

__all__ = [
    "AnalyticsEvent",
    "DailyCourseMetrics",
    "AppSetting",
    "AuditLog",
    "Booking",
    "BookingStatusHistory",
    "Category",
    "CategoryTranslation",
    "Commission",
    "Course",
    "CourseTranslation",
    "DomainEvent",
    "IdempotencyKey",
    "Instructor",
    "Notification",
    "NotificationPreference",
    "PasswordResetToken",
    "Payment",
    "PaymentEvent",
    "Permission",
    "Profile",
    "RefreshToken",
    "Role",
    "RolePermission",
    "User",
    "UserConsent",
    "UserRole",
    "Venue",
]
