from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenRouterConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPENROUTER_", env_file=".env", extra="ignore")

    API_KEY: str
    BASE_URL: str = "https://openrouter.ai/api/v1"
    MODEL: str = "anthropic/claude-sonnet-4.5"
    APP_URL: str = "http://localhost:3000"
    APP_NAME: str = "World Cup AI Scout"


openrouter_settings = OpenRouterConfig()
