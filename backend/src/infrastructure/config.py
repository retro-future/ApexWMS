"""Application settings, loaded from environment / .env.

All variables are prefixed APEXWMS_ (e.g. APEXWMS_MASTER_DB_URL).
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

    # Master database (the tenant registry). Tenant databases — which hold
    # each tenant's users and business data — are created next to it at
    # provisioning time (M1).
    master_db_url: str = "postgresql+asyncpg://apexwms:apexwms@localhost:5432/apexwms_master"

    # JWT
    jwt_secret: str = "change-me"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # Invitations (FR-1.5)
    invite_ttl_hours: int = 72

    # Tenant databases are created next to the master at provisioning
    # time (PRD §3.4), named <prefix><tenant_uuid_hex>.
    tenant_db_name_prefix: str = "apexwms_tenant_"

    # Tenant engine registry (PRD §3.2)
    max_live_tenant_engines: int = 50
    tenant_pool_size: int = 5
