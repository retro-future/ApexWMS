"""Query services: reads that fold joined rows into a projection.

Session-backed, behind a `Protocol` port in `application/ports/tenant/
queries.py`, injected into handlers. Not a repository, and not the generic
`SqlAlchemyRepository`. See `.claude/rules/backend/query-services.md`.
"""

from infrastructure.persistence.tenant.queries.device_unit import SqlDeviceUnitQueries
from infrastructure.persistence.tenant.queries.financial_transaction import (
    SqlFinancialTransactionQueries,
)
from infrastructure.persistence.tenant.queries.goods_receipt import (
    SqlGoodsReceiptQueries,
)
from infrastructure.persistence.tenant.queries.month_end import SqlMonthEndQueries
from infrastructure.persistence.tenant.queries.sales_invoice import (
    SqlSalesInvoiceQueries,
)
from infrastructure.persistence.tenant.queries.stock_movement import (
    SqlStockMovementQueries,
)
from infrastructure.persistence.tenant.queries.stock_on_hand import (
    SqlStockOnHandQueries,
)

__all__ = [
    "SqlDeviceUnitQueries",
    "SqlFinancialTransactionQueries",
    "SqlGoodsReceiptQueries",
    "SqlMonthEndQueries",
    "SqlSalesInvoiceQueries",
    "SqlStockMovementQueries",
    "SqlStockOnHandQueries",
]
