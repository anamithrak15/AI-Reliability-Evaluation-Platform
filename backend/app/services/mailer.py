import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str


def send(mail: Mail) -> None:
    """Deliver over SMTP. Never raises: it runs after the response, where nobody could handle it."""
    settings = get_settings()
    if not settings.smtp_host:
        if settings.environment.lower() == "production":
            logger.warning("SMTP_HOST is not set; email to an account was not sent")
        else:
            # Development only: the body holds a live link, so it must not reach production logs.
            logger.info("email not sent (no SMTP): to=%s subject=%s\n%s", mail.to, mail.subject, mail.body)
        return
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message.set_content(mail.body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except Exception:
        logger.exception("could not send email")
