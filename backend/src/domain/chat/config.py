from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatHistoryConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHAT_HISTORY_", env_file=".env", extra="ignore")

    TOKEN_BUDGET: int = 24_000
    """Max tokens of prior user+assistant text rebuilt from Postgres into the
    prompt when the Redis history cache is empty."""


chat_history_settings = ChatHistoryConfig()
