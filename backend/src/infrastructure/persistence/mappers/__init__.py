"""One mapper per aggregate root. A child entity is mapped by a private
method of its root's mapper, never by a mapper of its own.

A flat aggregate whose entity fields and ORM columns match by name and need
no conversion has no mapper file: it is registered as
``AutoMapper(Entity, Model)`` directly in ``COMMON_MAPPERS``.

Mappers are not split by database: a mapper holds no session, so nothing
about it is master- or tenant-specific. The two sides differ in which
*session* a repository gets, not in how a row becomes an entity.

``COMMON_MAPPERS`` is what the container builds its ``MapperRegistry``
from — converting an aggregate means writing its mapper (or an
``AutoMapper`` line) and adding one entry here.
"""

from domain.entities import (
    CreditCompany,
    Customer,
    Location,
    RefreshTokenRecord,
    StockLevel,
    Supplier,
    User,
    UserTenantAccess,
)
from infrastructure.persistence.mappers.auto import AutoMapper
from infrastructure.persistence.mappers.customer_return import CustomerReturnMapper
from infrastructure.persistence.mappers.device_unit import DeviceUnitMapper
from infrastructure.persistence.mappers.device_unit_price_change import (
    DeviceUnitPriceChangeMapper,
)
from infrastructure.persistence.mappers.employee import EmployeeMapper
from infrastructure.persistence.mappers.exchange_rate import ExchangeRateMapper
from infrastructure.persistence.mappers.financial_transaction import (
    FinancialTransactionMapper,
)
from infrastructure.persistence.mappers.goods_receipt import GoodsReceiptMapper
from infrastructure.persistence.mappers.invitation import InvitationMapper
from infrastructure.persistence.mappers.payment import PaymentMapper
from infrastructure.persistence.mappers.product import ProductMapper
from infrastructure.persistence.mappers.product_price_change import ProductPriceChangeMapper
from infrastructure.persistence.mappers.purchase_order import PurchaseOrderMapper
from infrastructure.persistence.mappers.registry import (
    MapperRegistry,
    UnmappedModelError,
)
from infrastructure.persistence.mappers.sales_invoice import SalesInvoiceMapper
from infrastructure.persistence.mappers.stock_count import StockCountMapper
from infrastructure.persistence.mappers.stock_movement import StockMovementMapper
from infrastructure.persistence.mappers.supplier_return import SupplierReturnMapper
from infrastructure.persistence.mappers.tenant import TenantMapper
from infrastructure.persistence.mappers.user_app_role import UserAppRoleMapper
from infrastructure.persistence.mappers.write_off import WriteOffMapper
from infrastructure.persistence.master.models import (
    RefreshTokenModel,
    UserModel,
    UserTenantAccessModel,
)
from infrastructure.persistence.tenant.models import (
    CreditCompanyModel,
    CustomerModel,
    LocationModel,
    StockLevelModel,
    SupplierModel,
)

COMMON_MAPPERS = (
    AutoMapper(Supplier, SupplierModel),
    AutoMapper(Location, LocationModel),
    AutoMapper(CreditCompany, CreditCompanyModel),
    AutoMapper(Customer, CustomerModel),
    AutoMapper(StockLevel, StockLevelModel),
    AutoMapper(User, UserModel),
    AutoMapper(UserTenantAccess, UserTenantAccessModel),
    AutoMapper(RefreshTokenRecord, RefreshTokenModel),
    PurchaseOrderMapper(),
    SupplierReturnMapper(),
    CustomerReturnMapper(),
    DeviceUnitMapper(),
    DeviceUnitPriceChangeMapper(),
    ExchangeRateMapper(),
    PaymentMapper(),
    ProductMapper(),
    ProductPriceChangeMapper(),
    EmployeeMapper(),
    FinancialTransactionMapper(),
    TenantMapper(),
    UserAppRoleMapper(),
    InvitationMapper(),
    StockCountMapper(),
    StockMovementMapper(),
    WriteOffMapper(),
    GoodsReceiptMapper(),
    SalesInvoiceMapper(),
)

__all__ = [
    "COMMON_MAPPERS",
    "AutoMapper",
    "CustomerReturnMapper",
    "DeviceUnitMapper",
    "DeviceUnitPriceChangeMapper",
    "EmployeeMapper",
    "FinancialTransactionMapper",
    "GoodsReceiptMapper",
    "InvitationMapper",
    "MapperRegistry",
    "PaymentMapper",
    "ProductMapper",
    "ProductPriceChangeMapper",
    "PurchaseOrderMapper",
    "SalesInvoiceMapper",
    "StockCountMapper",
    "StockMovementMapper",
    "SupplierReturnMapper",
    "TenantMapper",
    "UnmappedModelError",
    "UserAppRoleMapper",
    "WriteOffMapper",
]
