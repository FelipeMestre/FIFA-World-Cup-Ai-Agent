"""Configuration for the Transfermarkt CSV source. Per-domain `BaseSettings`
subclass (AGENTS.md convention): `BASE_URL` is always overridable via the
`TRANSFERMARKT_BASE_URL` env var, never hardcoded into the client itself --
the spec's "Transfermarkt Sync Trigger" requirement is explicit that the
source URL comes from configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class TransfermarktConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRANSFERMARKT_", env_file=".env", extra="ignore")

    BASE_URL: str = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data"


transfermarkt_settings = TransfermarktConfig()
