"""Application settings, loaded from environment / .env.

All variables are prefixed APEXWMS_ (e.g. APEXWMS_CONTROL_DB_URL).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APEXWMS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ApexWMS"
    debug: bool = False

    # Control-plane database (tenants, users, memberships). Tenant
    # databases are created next to it at provisioning time (M1).
    control_db_url: str = "postgresql+asyncpg://apexwms:apexwms@localhost:5432/apexwms_control"

    # JWT (used from M1 on)
    jwt_secret: str = "change-me"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # Tenant engine registry (PRD §3.2)
    max_live_tenant_engines: int = 50
    tenant_pool_size: int = 5
