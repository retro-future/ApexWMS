"""TenantDB repositories (M1: settings only)."""

from .base import TenantCrudRepository
from .settings import SETTINGS_ROW_ID, SqlTenantSettingsRepository

__all__ = [
    "SETTINGS_ROW_ID",
    "SqlTenantSettingsRepository",
    "TenantCrudRepository",
]
