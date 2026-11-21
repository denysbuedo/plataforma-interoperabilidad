import smtplib
import ssl
from email.message import EmailMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mes_common.settings import Settings


class MailConfigurationError(RuntimeError):
    """Raised when the SMTP transport is not configured securely."""


def send_email(
    *,
    settings: "Settings",
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str | None,
) -> None:
    """Submit one message to the institutional SMTP relay using verified STARTTLS."""
    required = {
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USER": settings.smtp_user,
        "SMTP_PASSWORD": settings.smtp_password,
        "EMAIL_FROM": settings.email_from,
        "SMTP_TLS_SERVER_NAME": settings.smtp_tls_server_name,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise MailConfigurationError("SMTP configuration is incomplete")
    if not settings.smtp_starttls or not settings.smtp_tls_reject_unauthorized:
        raise MailConfigurationError("SMTP STARTTLS and certificate validation are required")

    smtp_host = settings.smtp_host
    smtp_user = settings.smtp_user
    smtp_password = settings.smtp_password
    email_from = settings.email_from
    tls_server_name = settings.smtp_tls_server_name
    assert smtp_host is not None
    assert smtp_user is not None
    assert smtp_password is not None
    assert email_from is not None
    assert tls_server_name is not None

    message = EmailMessage()
    message["From"] = email_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(timeout=settings.smtp_timeout_seconds) as client:
        client.connect(smtp_host, settings.smtp_port)
        client.ehlo()
        if not client.has_extn("starttls"):
            raise MailConfigurationError("SMTP relay does not advertise STARTTLS")
        code, response = client.docmd("STARTTLS")
        if code != 220:
            raise smtplib.SMTPResponseException(code, response)
        if client.sock is None:
            raise smtplib.SMTPServerDisconnected("SMTP socket closed before STARTTLS")
        client.sock = context.wrap_socket(
            client.sock,
            server_hostname=tls_server_name,
        )
        client.file = None
        client.ehlo()
        client.login(smtp_user, smtp_password.get_secret_value())
        client.send_message(message)
