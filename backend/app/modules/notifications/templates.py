"""Plantillas de notificación por idioma. Los textos NUNCA incluyen datos sensibles (ni enlaces con tokens de pago)."""

from typing import Any

TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "booking_created": {
        "es": (
            "Reserva creada: {course}",
            "Reservaste {course}. Tienes hasta {deadline} para completar el pago o la reserva caducará.",
        ),
        "en": (
            "Booking created: {course}",
            "You booked {course}. Please complete payment by {deadline} or the booking will expire.",
        ),
    },
    "payment_completed": {
        "es": (
            "Pago recibido: {course}",
            "Recibimos tu pago. Estamos revisando tu participación y te confirmaremos pronto.",
        ),
        "en": (
            "Payment received: {course}",
            "We received your payment. We are reviewing your spot and will confirm shortly.",
        ),
    },
    "payment_completed_confirmed": {
        "es": (
            "¡Plaza confirmada!: {course}",
            "Tu plaza en {course} está confirmada. Te esperamos el {when} en {address}.",
        ),
        "en": ("Spot confirmed!: {course}", "Your spot in {course} is confirmed. See you on {when} at {address}."),
    },
    "booking_approved": {
        "es": (
            "¡Plaza confirmada!: {course}",
            "Tu participación en {course} fue aceptada. Te esperamos el {when} en {address}.",
        ),
        "en": (
            "Spot confirmed!: {course}",
            "Your participation in {course} was accepted. See you on {when} at {address}.",
        ),
    },
    "booking_rejected": {
        "es": (
            "Reserva no aceptada: {course}",
            "Lamentamos informarte que no pudimos aceptar tu participación en {course}. Te contactaremos sobre el reembolso.",
        ),
        "en": (
            "Booking not accepted: {course}",
            "We are sorry, we could not accept your participation in {course}. We will contact you about the refund.",
        ),
    },
    "booking_cancelled": {
        "es": ("Reserva cancelada: {course}", "Tu reserva de {course} fue cancelada."),
        "en": ("Booking cancelled: {course}", "Your booking for {course} was cancelled."),
    },
    "booking_expired": {
        "es": (
            "Reserva caducada: {course}",
            "No recibimos el pago a tiempo, así que tu reserva de {course} caducó y liberamos la plaza.",
        ),
        "en": (
            "Booking expired: {course}",
            "We did not receive payment in time, so your booking for {course} expired and the spot was released.",
        ),
    },
    "course_cancelled": {
        "es": (
            "Curso cancelado: {course}",
            "Tuvimos que cancelar {course}. Te contactaremos sobre el reembolso si ya habías pagado.",
        ),
        "en": (
            "Course cancelled: {course}",
            "We had to cancel {course}. We will contact you about the refund if you had already paid.",
        ),
    },
    "payment_failed": {
        "es": (
            "Pago fallido: {course}",
            "No pudimos procesar tu pago. Puedes intentarlo de nuevo mientras tu reserva siga vigente.",
        ),
        "en": (
            "Payment failed: {course}",
            "We could not process your payment. You can try again while your booking is still valid.",
        ),
    },
    "payment_refunded": {
        "es": ("Reembolso realizado: {course}", "Procesamos el reembolso de tu pago de {course}."),
        "en": ("Refund processed: {course}", "We processed the refund for your {course} payment."),
    },
    "booking_reminder": {
        "es": ("Recordatorio: {course} es pronto", "Te recordamos que {course} es el {when} en {address}."),
        "en": ("Reminder: {course} is coming up", "A reminder that {course} takes place on {when} at {address}."),
    },
    "admin_pending_approval": {
        "es": ("Participante por aprobar", "Hay un pago recibido esperando tu aprobación en {course}."),
        "en": ("Participant awaiting approval", "A paid booking is waiting for your approval in {course}."),
    },
    "admin_refund_needed": {
        "es": ("Reembolso pendiente", "Un pago necesita ser reembolsado (reserva en estado {status})."),
        "en": ("Refund needed", "A payment needs to be refunded (booking status {status})."),
    },
}


def render(kind: str, locale: str, data: dict[str, Any]) -> tuple[str, str]:
    by_locale = TEMPLATES[kind]
    title, body = by_locale.get(locale) or by_locale["es"]
    safe = {k: str(v) for k, v in data.items()}
    return title.format_map(_Default(safe)), body.format_map(_Default(safe))


class _Default(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""
