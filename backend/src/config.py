from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Composition-root settings: things `main.py` needs that don't belong to any
    single bounded context (environment name, CORS). Domain-specific settings
    (JWT, database, redis, openrouter) live in their own `config.py` per AGENTS.md.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "local"
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


app_settings = AppConfig()
