"""Tenant settings schemas (timezone in M1, letterhead at M7)."""

from pydantic import BaseModel


class TenantSettingsResponse(BaseModel):
    timezone: str


class TenantSettingsUpdateRequest(BaseModel):
    timezone: str
