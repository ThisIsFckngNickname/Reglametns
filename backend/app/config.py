"""
Конфигурация приложения.
Загрузка из .env через Pydantic BaseSettings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из .env."""

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b-it-qat"

    # YandexGPT
    yandexgpt_api_key: str = ""
    yandexgpt_folder_id: str = ""

    # Таймауты
    provider_timeout: int = 900

    # База данных
    database_url: str = "sqlite:///./data/srp.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Единственный экземпляр настроек для всего приложения
settings = Settings()
