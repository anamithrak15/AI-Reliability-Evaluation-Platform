import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"


@dataclass(frozen=True)
class Mail:
    to: str
    subject: str
    body: str


def can_deliver() -> bool:
    """False in production with no delivery method, where a queued message would silently go nowhere."""
    settings = get_settings()
    configured = bool(settings.brevo_api_key or settings.smtp_host)
    return configured or settings.environment.lower() != "production"


def _send_brevo(mail: Mail) -> None:
    settings = get_settings()
    name, address = parseaddr(settings.smtp_from)
    sender = {"email": address, **({"name": name} if name else {})}
    payload = {"sender": sender, "to": [{"email": mail.to}], "subject": mail.subject, "textContent": mail.body}
    request = urllib.request.Request(
        _BREVO_URL,
        data=json.dumps(payload).encode(),
        headers={"api-key": settings.brevo_api_key, "content-type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15):
        pass


def _send_smtp(mail: Mail) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message.set_content(mail.body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def send(mail: Mail) -> None:
    """Deliver by Brevo's HTTPS API or SMTP. Never raises: it runs after the response, where nobody could handle it."""
    settings = get_settings()
    if not (settings.brevo_api_key or settings.smtp_host):
        if settings.environment.lower() == "production":
            logger.warning("no email delivery is configured; email to an account was not sent")
        else:
            # Development only: the body holds a live link, so it must not reach production logs.
            logger.info("email not sent (not configured): to=%s subject=%s\n%s", mail.to, mail.subject, mail.body)
        return
    try:
        (_send_brevo if settings.brevo_api_key else _send_smtp)(mail)
    except urllib.error.HTTPError as exc:
        # The response body names the cause (e.g. an unverified sender) and never echoes the API key.
        logger.error("could not send email: HTTP %s %s", exc.code, exc.read(300).decode(errors="replace"))
    except Exception as exc:
        logger.error("could not send email: %s: %s", type(exc).__name__, exc)
