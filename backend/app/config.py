from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./srp.db"
    secret_key: str = "change-me-in-production-min-32-chars-long"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"
    debug: bool = True

    # Upload settings
    max_upload_size: int = 20 * 1024 * 1024  # 20 MB
    allowed_extensions: set = {".docx", ".pdf"}
    storage_path: str = "storage/documents"

    # Storage backend
    storage_type: str = "local"  # "local" | "s3"

    # S3 settings (used when storage_type = "s3")
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "srp-documents"
    s3_region: str = "ru-central1"
    s3_use_ssl: bool = True

    # Local storage
    upload_dir: str = "./uploads"

    # GigaChat settings (optional — leave empty for mock mode)
    gigachat_client_id: str = ""
    gigachat_client_secret: str = ""
    gigachat_model: str = "GigaChat-Pro"
    gigachat_auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_api_url: str = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    gigachat_verify_ssl: bool = False
    generation_timeout: int = 120  # seconds
    generation_max_tokens: int = 8000
    generation_temperature: float = 0.3

    # SMTP settings for email sending
    smtp_host: str = "localhost"
    smtp_port: int = 1025  # MailHog default
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_from_email: str = "noreply@srp.dev"

    # Cookie settings for refresh token
    cookie_secure: bool = False  # True in production with HTTPS
    cookie_domain: str | None = None

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True  # можно отключить для dev (fallback на in-memory)

    # Rate limiting
    rate_limit_max_attempts: int = 5    # попыток в window
    rate_limit_window_seconds: int = 60  # окно в секундах
    rate_limit_block_minutes: int = 15   # блокировка после превышения

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
