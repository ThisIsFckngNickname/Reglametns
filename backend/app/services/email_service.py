import asyncio
import logging
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from smtplib import SMTP

logger = logging.getLogger(__name__)


class EmailService(ABC):
    """Abstract email service interface."""

    @abstractmethod
    async def send_code(self, email: str, code: str, purpose: str) -> None:
        """Send a verification code to the given email."""
        ...


class ConsoleEmailService(EmailService):
    """Console-based email service that logs codes to stdout and logger."""

    async def send_code(self, email: str, code: str, purpose: str) -> None:
        message = f"[EMAIL] To: {email} | Code: {code} | Purpose: {purpose}"
        logger.info(message)
        print(message)


class SmtpEmailService(EmailService):
    """Real SMTP-based email service."""

    def __init__(self) -> None:
        from app.config import settings

        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.smtp_user
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.from_email = settings.smtp_from_email

    async def send_code(self, email: str, code: str, purpose: str) -> None:
        """Send verification code via SMTP."""
        purpose_label = {"registration": "Registration", "login": "Login"}.get(purpose, purpose)
        msg = MIMEText(
            f"Your verification code: {code}\n\n"
            f"It expires in 15 minutes.\n\n"
            f"Purpose: {purpose_label}"
        )
        msg["Subject"] = f"SRP — {purpose_label} Verification Code"
        msg["From"] = self.from_email
        msg["To"] = email

        def _send() -> None:
            with SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                if self.smtp_user:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

        await asyncio.to_thread(_send)
        logger.info("SMTP email sent to %s (purpose=%s)", email, purpose)


def get_email_service() -> EmailService:
    """Factory: returns real SMTP service if configured, otherwise console."""
    from app.config import settings

    if settings.smtp_host and settings.smtp_host not in ("localhost", "127.0.0.1"):
        return SmtpEmailService()
    return ConsoleEmailService()
