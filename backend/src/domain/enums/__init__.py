"""Every domain-level enum, one class per module.

Value objects with enum-backed behavior (``Currency``, in
``domain/value_objects/``) and the permission catalog
(``domain/permissions/``) are deliberately not here — both are already
properly modularized in their own packages, not loose top-level modules.
"""

from domain.enums.acquisition_source import AcquisitionSource
from domain.enums.app_role import APP_PREFIX, AppRole
from domain.enums.catalog_code_kind import CatalogCodeKind
from domain.enums.count_outcome import CountOutcome
from domain.enums.customer_return_reason import CustomerReturnReason
from domain.enums.device_condition import DeviceCondition
from domain.enums.device_status import DeviceStatus
from domain.enums.document_status import DocumentStatus
from domain.enums.document_type import DocumentType
from domain.enums.invitation_kind import InvitationKind
from domain.enums.label_layout import LabelLayout
from domain.enums.movement_type import MovementType
from domain.enums.payment_method import PaymentMethod
from domain.enums.payment_type import PaymentType
from domain.enums.supplier_return_reason import SupplierReturnReason
from domain.enums.tenant_role import TENANT_PREFIX, TenantRole
from domain.enums.tenant_status import TenantStatus
from domain.enums.tracking_type import TrackingType
from domain.enums.transaction_type import TransactionType
from domain.enums.write_off_reason import WriteOffReason

__all__ = [
    "APP_PREFIX",
    "AcquisitionSource",
    "AppRole",
    "CatalogCodeKind",
    "CountOutcome",
    "CustomerReturnReason",
    "DeviceCondition",
    "DeviceStatus",
    "DocumentStatus",
    "DocumentType",
    "InvitationKind",
    "LabelLayout",
    "MovementType",
    "PaymentMethod",
    "PaymentType",
    "SupplierReturnReason",
    "TENANT_PREFIX",
    "TenantRole",
    "TenantStatus",
    "TrackingType",
    "TransactionType",
    "WriteOffReason",
]
