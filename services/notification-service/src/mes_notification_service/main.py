import logging
import smtplib
import ssl
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from mes_common.app import create_service_app
from mes_common.mail import MailConfigurationError, send_email
from mes_common.security import Principal, require_any_role
from mes_common.settings import get_settings
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)
settings = get_settings("notification-service")
NotificationSender = Annotated[
    Principal,
    Depends(require_any_role("notification-sender")),
]

app = create_service_app(
    title="MES Notification Service",
    service_name="notification-service",
)


class EmailNotificationRequest(BaseModel):
    recipient: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    text_body: str = Field(min_length=1, max_length=20_000)
    html_body: str | None = Field(default=None, max_length=50_000)


class EmailNotificationResponse(BaseModel):
    status: str = "accepted_by_relay"


@app.post(
    "/api/v1/notifications/email",
    tags=["notifications"],
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EmailNotificationResponse,
)
async def submit_email_notification(
    request: EmailNotificationRequest,
    _sender: NotificationSender,
) -> EmailNotificationResponse:
    """Submit one plain-text or HTML email through the institutional relay."""
    try:
        await run_in_threadpool(
            send_email,
            settings=settings,
            recipient=str(request.recipient),
            subject=request.subject,
            text_body=request.text_body,
            html_body=request.html_body,
        )
    except MailConfigurationError as exc:
        logger.error("smtp_configuration_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured",
        ) from exc
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        logger.warning("smtp_submission_failed", extra={"error_type": type(exc).__name__})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The email relay could not accept the message",
        ) from exc
    return EmailNotificationResponse()
