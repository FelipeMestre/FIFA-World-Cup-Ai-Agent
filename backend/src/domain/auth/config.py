from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JWT_", env_file=".env", extra="ignore")

    SECRET: str
    ALG: str = "HS256"
    EXP_MINUTES: int = 60


auth_settings = AuthConfig()
