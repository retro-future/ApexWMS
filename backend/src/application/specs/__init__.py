"""Specifications — the reads a use case repeats or that are not trivial to
inline, grouped by aggregate. See ADR 0007 for why these are written
against ORM models.

Not here: a plain load by id (``repo.get(id)``) and a one-off equality
probe (``Specification(Model).where(Model.x == v)`` inline in the handler).
See ``.claude/rules/backend/specifications.md`` rule 6."""

from application.specs.credit_company import (
    CreditCompanyBrowse,
    CreditCompanyForWrite,
)
from application.specs.customer import (
    CustomerBrowse,
    CustomerForWrite,
)
from application.specs.customer_return import (
    RETURN_WITH_LINES,
    CustomerReturnBrowse,
    CustomerReturnById,
    CustomerReturnForWrite,
    CustomerReturnsForInvoice,
)
from application.specs.device_unit import (
    DeviceUnitById,
    DeviceUnitByImei,
    DeviceUnitForWrite,
    DeviceUnitsByIds,
    OnHandDeviceUnits,
)
from application.specs.device_unit_price_change import (
    LatestPriceChangeForUnit,
    PriceChangesForUnit,
)
from application.specs.employee import (
    ActiveOwners,
    EmployeeForWrite,
)
from application.specs.financial_transaction import (
    TransactionsForDocument,
    TransactionsForPair,
)
from application.specs.goods_receipt import (
    GoodsReceiptBrowse,
    GoodsReceiptById,
    GoodsReceiptForWrite,
)
from application.specs.invitation import (
    InvitationForWrite,
)
from application.specs.location import (
    LocationBrowse,
    LocationForWrite,
)
from application.specs.payment import PaymentsForInvoice
from application.specs.product import (
    ProductBarcodeTakenByAnother,
    ProductBrowse,
    ProductByBarcode,
    ProductBySku,
    ProductForWrite,
)
from application.specs.product_price_change import (
    LatestPriceChangeForProduct,
    PriceChangesForProduct,
)
from application.specs.purchase_order import (
    PurchaseOrderBrowse,
    PurchaseOrderById,
    PurchaseOrderForWrite,
)
from application.specs.refresh_token import (
    LiveTokensForUser,
    RefreshTokenForWrite,
)
from application.specs.sales_invoice import (
    SalesInvoiceBrowse,
    SalesInvoiceById,
    SalesInvoiceForWrite,
)
from application.specs.stock_count import (
    StockCountBrowse,
    StockCountById,
    StockCountForWrite,
)
from application.specs.stock_level import StockLevelForPair
from application.specs.stock_movement import (
    MovementsForDocument,
    MovementsForPair,
    MovementsForUnit,
)
from application.specs.supplier import (
    SupplierBrowse,
    SupplierForWrite,
)
from application.specs.supplier_return import (
    SupplierReturnBrowse,
    SupplierReturnById,
    SupplierReturnForWrite,
)
from application.specs.tenant import (
    TenantForWrite,
)
from application.specs.user import (
    UserForWrite,
)
from application.specs.write_off import (
    WriteOffBrowse,
    WriteOffById,
    WriteOffForWrite,
)

__all__ = [
    "ActiveOwners",
    "CreditCompanyBrowse",
    "CreditCompanyForWrite",
    "CustomerBrowse",
    "CustomerForWrite",
    "DeviceUnitByImei",
    "DeviceUnitById",
    "DeviceUnitForWrite",
    "DeviceUnitsByIds",
    "EmployeeForWrite",
    "GoodsReceiptBrowse",
    "GoodsReceiptById",
    "GoodsReceiptForWrite",
    "InvitationForWrite",
    "LatestPriceChangeForProduct",
    "LatestPriceChangeForUnit",
    "MovementsForDocument",
    "MovementsForPair",
    "MovementsForUnit",
    "LiveTokensForUser",
    "LocationBrowse",
    "LocationForWrite",
    "OnHandDeviceUnits",
    "PriceChangesForProduct",
    "PaymentsForInvoice",
    "PriceChangesForUnit",
    "ProductBarcodeTakenByAnother",
    "ProductBrowse",
    "ProductByBarcode",
    "ProductBySku",
    "ProductForWrite",
    "PurchaseOrderBrowse",
    "PurchaseOrderById",
    "PurchaseOrderForWrite",
    "RefreshTokenForWrite",
    "SalesInvoiceBrowse",
    "SalesInvoiceById",
    "SalesInvoiceForWrite",
    "StockCountBrowse",
    "StockCountById",
    "StockCountForWrite",
    "StockLevelForPair",
    "SupplierBrowse",
    "SupplierForWrite",
    "RETURN_WITH_LINES",
    "CustomerReturnBrowse",
    "CustomerReturnById",
    "CustomerReturnForWrite",
    "CustomerReturnsForInvoice",
    "SupplierReturnBrowse",
    "SupplierReturnById",
    "SupplierReturnForWrite",
    "TenantForWrite",
    "UserForWrite",
    "TransactionsForDocument",
    "TransactionsForPair",
    "WriteOffBrowse",
    "WriteOffById",
    "WriteOffForWrite",
]
