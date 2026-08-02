"""Every domain-level enum, one class per module.

Value objects with enum-backed behavior (``Currency``, in
``domain/value_objects/``) and the permission catalog
(``domain/permissions/``) are deliberately not here — both are already
properly modularized in their own packages, not loose top-level modules.
"""

from domain.enums.app_role import APP_PREFIX, AppRole
from domain.enums.device_condition import DeviceCondition
from domain.enums.device_status import DeviceStatus
from domain.enums.document_type import DocumentType
from domain.enums.invitation_kind import InvitationKind
from domain.enums.movement_type import MovementType
from domain.enums.tenant_role import TENANT_PREFIX, TenantRole
from domain.enums.tenant_status import TenantStatus
from domain.enums.tracking_type import TrackingType
from domain.enums.transaction_type import TransactionType

__all__ = [
    "APP_PREFIX",
    "AppRole",
    "DeviceCondition",
    "DeviceStatus",
    "DocumentType",
    "InvitationKind",
    "MovementType",
    "TENANT_PREFIX",
    "TenantRole",
    "TenantStatus",
    "TrackingType",
    "TransactionType",
]
