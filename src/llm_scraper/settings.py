from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Manages application settings and secrets using Pydantic.
    It automatically loads variables from a .env file.
    """

    # OpenAI Configuration
    OPENAI_API_KEY: str = "YOUR_OPENAI_API_KEY_HERE"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # AstraDB Configuration
    ASTRA_DB_API_ENDPOINT: str = "YOUR_ASTRA_DB_API_ENDPOINT_HERE"
    ASTRA_DB_APPLICATION_TOKEN: str = "YOUR_ASTRA_DB_APPLICATION_TOKEN_HERE"
    ASTRA_DB_COLLECTION_NAME: str = "llm_scraper_rag"

    # Celery/Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# Create a single, reusable instance of the settings
settings = Settings()
