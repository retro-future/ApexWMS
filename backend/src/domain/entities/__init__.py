"""Entities, split by the database they live in (PRD §3.1).

MasterDB holds the tenant registry and *identity*: who a person is, which
platform roles they hold, which stores they may act in. Each TenantDB
holds that store's business data — its catalog from M2, its ledgers from
M3 — and its ``Employee`` rows: what a person may do *there*.
"""

from domain.entities.customer import Customer
from domain.entities.employee import Employee
from domain.entities.invitation import Invitation, InvitationKind
from domain.entities.location import Location
from domain.entities.product import Product
from domain.entities.refresh_token import RefreshTokenRecord
from domain.entities.supplier import Supplier
from domain.entities.tenant import Tenant
from domain.entities.user import User
from domain.entities.user_app_role import UserAppRole
from domain.entities.user_tenant_access import UserTenantAccess

__all__ = [
    "Customer",
    "Employee",
    "Invitation",
    "InvitationKind",
    "Location",
    "Product",
    "RefreshTokenRecord",
    "Supplier",
    "Tenant",
    "User",
    "UserAppRole",
    "UserTenantAccess",
]
