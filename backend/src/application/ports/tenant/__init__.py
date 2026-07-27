"""Ports over a tenant's own database: employees, settings, the M2 catalog,
and the unit of work."""

from application.ports.tenant.repositories import (
    CustomerRepository,
    EmployeeRepository,
    LocationRepository,
    ProductRepository,
    SupplierRepository,
    TenantSettingsRepository,
)
from application.ports.tenant.uow import TenantUnitOfWork

__all__ = [
    "CustomerRepository",
    "EmployeeRepository",
    "LocationRepository",
    "ProductRepository",
    "SupplierRepository",
    "TenantSettingsRepository",
    "TenantUnitOfWork",
]
