from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "src/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "local"

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str

    redis_url: str
    sql_echo: bool = False

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL database connection URL."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


_settings_instance: ApplicationSettings | None = None


@lru_cache()
def get_settings() -> ApplicationSettings:
    """Get cached application settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = ApplicationSettings()
    return _settings_instance
