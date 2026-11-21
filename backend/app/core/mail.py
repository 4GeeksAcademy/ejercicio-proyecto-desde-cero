"""Puerto de email. Hoy: SMTP (Mailpit en desarrollo) o memoria (tests). Producción: [PENDIENTE P-10]."""

import asyncio
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol

import structlog

from app.core.config import get_settings

log = structlog.get_logger()


@dataclass
class Mail:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    async def send(self, mail: Mail) -> None: ...


@dataclass
class InMemoryMailer:
    sent: list[Mail] = field(default_factory=list)

    async def send(self, mail: Mail) -> None:
        self.sent.append(mail)


class NullMailer:
    """Sin servidor de correo configurado (SMTP_HOST vacío): no se envía nada; los avisos siguen en la web."""

    async def send(self, mail: Mail) -> None:
        log.info("email_skipped", event_name="email_skipped", subject=mail.subject)


class SmtpMailer:
    async def send(self, mail: Mail) -> None:
        s = get_settings()
        msg = EmailMessage()
        msg["From"] = s.mail_from
        msg["To"] = mail.to
        msg["Subject"] = mail.subject
        msg.set_content(mail.body)

        def _send() -> None:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
                smtp.send_message(msg)

        await asyncio.to_thread(_send)
        # Nunca registramos el cuerpo (puede contener enlaces con tokens).
        log.info("email_sent", event_name="email_sent", subject=mail.subject)


_mailer: Mailer | None = None


def get_mailer() -> Mailer:
    global _mailer
    if _mailer is None:
        s = get_settings()
        if s.app_env == "testing":
            _mailer = InMemoryMailer()
        else:
            _mailer = SmtpMailer() if s.smtp_host else NullMailer()
    return _mailer


def set_mailer(m: Mailer | None) -> None:
    global _mailer
    _mailer = m
