"""Every domain-level enum, one class per module.

Value objects with enum-backed behavior (``Currency``, in
``domain/value_objects/``) and the permission catalog
(``domain/permissions/``) are deliberately not here — both are already
properly modularized in their own packages, not loose top-level modules.
"""

from domain.enums.app_role import APP_PREFIX, AppRole
from domain.enums.invitation_kind import InvitationKind
from domain.enums.tenant_role import TENANT_PREFIX, TenantRole
from domain.enums.tenant_status import TenantStatus
from domain.enums.tracking_type import TrackingType

__all__ = [
    "APP_PREFIX",
    "AppRole",
    "InvitationKind",
    "TENANT_PREFIX",
    "TenantRole",
    "TenantStatus",
    "TrackingType",
]
