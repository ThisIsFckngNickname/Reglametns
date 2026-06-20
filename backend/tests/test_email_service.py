"""
Tests for email service: ConsoleEmailService, SmtpEmailService, and factory.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import (
    ConsoleEmailService,
    EmailService,
    SmtpEmailService,
    get_email_service,
)


class TestConsoleEmailService:
    """Tests for ConsoleEmailService."""

    def test_is_abstract_subclass(self):
        """Should implement EmailService ABC."""
        service = ConsoleEmailService()
        assert isinstance(service, EmailService)

    @pytest.mark.asyncio
    async def test_send_code_does_not_raise(self, caplog):
        """Should log the message and print it without raising."""
        import logging

        caplog.set_level(logging.INFO)

        service = ConsoleEmailService()
        # Should not raise any exception
        await service.send_code("test@example.com", "123456", "registration")

        # Check that it was logged
        assert any(
            "[EMAIL] To: test@example.com | Code: 123456 | Purpose: registration" in record.message
            for record in caplog.records
        )


class TestSmtpEmailService:
    """Tests for SmtpEmailService."""

    @pytest.fixture
    def smtp_settings(self, monkeypatch):
        """Configure SMTP settings for testing."""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "secret")
        monkeypatch.setenv("SMTP_USE_TLS", "true")
        monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@srp.dev")

    def test_init_reads_settings(self, smtp_settings):
        """Should read SMTP settings from config."""
        # Reimport config to pick up monkeypatched env vars
        from app.config import settings as s

        # Force reload of settings
        import app.config
        app.config.settings = app.config.Settings()

        service = SmtpEmailService()
        assert service.smtp_host == "smtp.example.com"
        assert service.smtp_port == 587
        assert service.smtp_user == "user@example.com"
        assert service.smtp_password == "secret"
        assert service.smtp_use_tls is True
        assert service.from_email == "noreply@srp.dev"

    @pytest.mark.asyncio
    async def test_send_code_calls_smtplib(self, smtp_settings, monkeypatch):
        """Should send email via SMTP."""
        from unittest.mock import MagicMock

        # Reimport config
        import app.config
        app.config.settings = app.config.Settings()
        from app.config import settings as s

        # Mock smtplib.SMTP with proper context manager support
        mock_smtp = MagicMock()
        mock_smtp.__enter__.return_value = mock_smtp

        monkeypatch.setattr(
            "app.services.email_service.SMTP",
            lambda host, port: mock_smtp,
        )

        service = SmtpEmailService()
        await service.send_code("recipient@example.com", "654321", "login")

        # Verify SMTP was called with correct host and port
        assert mock_smtp.send_message.called
        msg = mock_smtp.send_message.call_args[0][0]
        assert msg["To"] == "recipient@example.com"
        assert msg["From"] == "noreply@srp.dev"
        assert "654321" in msg.get_payload()

    @pytest.mark.asyncio
    async def test_send_code_no_auth_if_no_user(self, monkeypatch):
        """Should skip login if smtp_user is empty."""
        monkeypatch.setenv("SMTP_HOST", "mailhog")
        monkeypatch.setenv("SMTP_PORT", "1025")
        monkeypatch.setenv("SMTP_USER", "")
        monkeypatch.setenv("SMTP_PASSWORD", "")
        monkeypatch.setenv("SMTP_USE_TLS", "false")
        monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@srp.dev")

        import app.config
        app.config.settings = app.config.Settings()

        mock_smtp = MagicMock()
        mock_smtp.__enter__.return_value = mock_smtp
        monkeypatch.setattr(
            "app.services.email_service.SMTP",
            lambda host, port: mock_smtp,
        )

        service = SmtpEmailService()
        await service.send_code("test@example.com", "111111", "registration")

        # login should NOT have been called because smtp_user is empty
        mock_smtp.login.assert_not_called()


class TestGetEmailService:
    """Tests for get_email_service factory."""

    def test_returns_console_when_smtp_not_configured(self, monkeypatch):
        """Should return ConsoleEmailService when SMTP host is localhost."""
        monkeypatch.setenv("SMTP_HOST", "localhost")
        monkeypatch.setenv("SMTP_PORT", "1025")

        import app.config
        app.config.settings = app.config.Settings()

        service = get_email_service()
        assert isinstance(service, ConsoleEmailService)

    def test_returns_console_when_smtp_host_empty(self, monkeypatch):
        """Should return ConsoleEmailService when SMTP host is empty."""
        monkeypatch.setenv("SMTP_HOST", "")
        monkeypatch.setenv("SMTP_PORT", "1025")

        import app.config
        app.config.settings = app.config.Settings()

        service = get_email_service()
        assert isinstance(service, ConsoleEmailService)

    def test_returns_smtp_when_configured(self, monkeypatch):
        """Should return SmtpEmailService when SMTP host is set to a real host."""
        monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
        monkeypatch.setenv("SMTP_PORT", "587")
        monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@srp.dev")

        import app.config
        app.config.settings = app.config.Settings()

        service = get_email_service()
        assert isinstance(service, SmtpEmailService)
