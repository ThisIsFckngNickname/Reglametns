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
    allowed_extensions: set = {".docx", ".pdf", ".xlsx"}
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

    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embedding_model: str = "nomic-embed-text"

    # Generation settings
    generation_timeout: int = 120  # seconds
    generation_max_tokens: int = 48000
    generation_temperature: float = 0.3
    generation_max_prompt_tokens: int = 28000

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
    redis_enabled: bool = True

    # Rate limiting
    rate_limit_max_attempts: int = 5
    rate_limit_window_seconds: int = 60
    rate_limit_block_minutes: int = 15

    # RAG settings
    chroma_persist_directory: str = "./chroma_db"
    rag_max_chunks: int = 8         # Сколько чанков добавлять в промпт
    rag_chunk_size: int = 600       # Размер чанка в токенах (~600 слов для русского)
    rag_chunk_overlap: int = 120    # Перекрытие между чанками
    rag_min_chunk_length: int = 50  # Минимальная длина чанка для индексации

    # Web search settings
    web_search_enabled: bool = True
    web_search_provider: str = "duckduckgo"  # "duckduckgo" | "tavily" | "serpapi"
    tavily_api_key: str = ""
    serpapi_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
