"""Per-tenant schema.

Who works at this store (``employees``), what provisioning seeds
(PRD §3.4: the default location and the tenant's settings), and the M2
catalog: products, locations, suppliers, customers. The ledgers land in M3.

No table here carries a ``tenant_id``: isolation is physical (PRD §3.1).
"""

from .base import TenantBase
from .customer import CustomerModel
from .employee import EmployeeModel
from .location import LocationModel
from .product import ProductModel
from .settings import TenantSettingsModel
from .supplier import SupplierModel

__all__ = [
    "CustomerModel",
    "EmployeeModel",
    "LocationModel",
    "ProductModel",
    "SupplierModel",
    "TenantBase",
    "TenantSettingsModel",
]
