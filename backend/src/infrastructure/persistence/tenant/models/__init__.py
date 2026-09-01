"""Per-tenant schema.

Who works at this store (``employees``), what provisioning seeds
(PRD §3.4: the default location and the tenant's settings), the M2
catalog, M3's two append-only ledgers with the projections they feed,
M4's inbound documents with M5's outbound invoice, M5b's credit
companies and payments, and M6's returns, counts and write-offs.

No table here carries a ``tenant_id``: isolation is physical (PRD §3.1).
"""

from .base import TenantBase
from .catalog_code import CatalogCodeSequenceModel
from .credit_company import CreditCompanyModel
from .customer import CustomerModel
from .device_unit import DeviceUnitModel
from .device_unit_price_change import DeviceUnitPriceChangeModel
from .employee import EmployeeModel
from .financial_transaction import FinancialTransactionModel
from .goods_receipt import (
    DocumentSequenceModel,
    GoodsReceiptLineModel,
    GoodsReceiptModel,
    ReceivedUnitModel,
)
from .location import LocationModel
from .payment import PaymentModel
from .product import ProductModel
from .product_price_change import ProductPriceChangeModel
from .purchase_order import PurchaseOrderLineModel, PurchaseOrderModel
from .sales_invoice import SalesInvoiceLineModel, SalesInvoiceModel
from .settings import TenantSettingsModel
from .stock_count import StockCountLineModel, StockCountModel, StockCountUnitModel
from .stock_level import StockLevelModel
from .stock_movement import StockMovementModel
from .supplier import SupplierModel
from .supplier_return import SupplierReturnLineModel, SupplierReturnModel
from .write_off import WriteOffLineModel, WriteOffModel

__all__ = [
    "CatalogCodeSequenceModel",
    "CreditCompanyModel",
    "CustomerModel",
    "DeviceUnitModel",
    "DeviceUnitPriceChangeModel",
    "DocumentSequenceModel",
    "EmployeeModel",
    "FinancialTransactionModel",
    "GoodsReceiptLineModel",
    "GoodsReceiptModel",
    "LocationModel",
    "PaymentModel",
    "ProductModel",
    "ProductPriceChangeModel",
    "PurchaseOrderLineModel",
    "PurchaseOrderModel",
    "ReceivedUnitModel",
    "SalesInvoiceLineModel",
    "SalesInvoiceModel",
    "StockCountLineModel",
    "StockCountModel",
    "StockCountUnitModel",
    "StockLevelModel",
    "StockMovementModel",
    "SupplierModel",
    "SupplierReturnLineModel",
    "SupplierReturnModel",
    "TenantBase",
    "TenantSettingsModel",
    "WriteOffLineModel",
    "WriteOffModel",
]
