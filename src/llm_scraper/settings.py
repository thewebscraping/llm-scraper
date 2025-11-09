from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Manages application settings and secrets using Pydantic.
    It automatically loads variables from a .env file.
    """

    # --- Vector Store Provider Configuration ---
    EMBEDDING_PROVIDER: Literal["openai", "gemini"] = "openai"
    VECTOR_DB_PROVIDER: Literal["astradb"] = "astradb"

    # --- OpenAI Configuration ---
    OPENAI_API_KEY: str
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # --- Google Gemini Configuration ---
    GEMINI_API_KEY: str | None = None  # Optional, for when Gemini is implemented

    # --- AstraDB Configuration ---
    ASTRA_DB_API_ENDPOINT: str
    ASTRA_DB_APPLICATION_TOKEN: str
    ASTRA_DB_COLLECTION_NAME: str = "llm_scraper_rag"

    # --- Celery/Redis Configuration ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# Create a single, reusable instance of the settings
settings = Settings()
