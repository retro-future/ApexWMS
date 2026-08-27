"""CQRS response payloads — ``CamelModel`` subclasses carried out of a
handler as a ``Result``/``PagedResult``'s ``TData``. One file per payload,
each next to an optional ``from_<entity>()`` mapping classmethod.

Distinct from ``application/dtos/``, which holds frozen dataclasses that
never cross an HTTP wire (DI-context carriers like ``CurrentUser``). A
``Command``/``Query`` request shape (including a request-only nested item
like ``RepriceDeviceUnitsCommand.UnitPrice``) stays in its own operation's
module in ``application/commands/``/``application/queries/`` — only the
*response* shape moves here, because it is often read by more than the one
handler that first produced it (see ``.claude/rules/backend/cqrs-response-models.md``).
"""

from application.models.accept_invite import AcceptInviteData
from application.models.ageing import AgeingRowData
from application.models.auth_tokens import AuthTokensData
from application.models.count_scan_result import CountScanResultData
from application.models.create_superadmin import CreateSuperAdminData
from application.models.create_tenant import CreateTenantData
from application.models.credit_company import CreditCompanyData
from application.models.currency_subtotal import CurrencySubtotalData
from application.models.customer import CustomerData
from application.models.customer_account import (
    CreditInvoiceDebtData,
    CustomerAccountData,
)
from application.models.debtor import DebtorData
from application.models.device_trace import (
    DeviceTraceData,
    TraceEventData,
    TraceOriginData,
    TraceSaleData,
)
from application.models.device_unit import DeviceUnitData
from application.models.employee import EmployeeListItem
from application.models.financial_ledger import FinancialLedgerRowData
from application.models.goods_receipt import GoodsReceiptData, GoodsReceiptLineData
from application.models.invite_user import InviteResultData
from application.models.invoice_scan_result import InvoiceScanResultData
from application.models.location import LocationData
from application.models.login import LoginData
from application.models.me import MeData
from application.models.movement_log import MovementRowData
from application.models.needs_pricing import NeedsPricingRowData
from application.models.payment import PaymentData
from application.models.price_deviation import PriceDeviationData
from application.models.price_history import PriceChangeData
from application.models.product import ProductData
from application.models.purchase_order import (
    Fulfilment,
    PurchaseOrderData,
    PurchaseOrderLineData,
)
from application.models.received_unit import ReceivedUnitData
from application.models.sales_invoice import SalesInvoiceData, SalesInvoiceLineData
from application.models.sales_summary import (
    LocationSalesData,
    SalesFiguresData,
    SalesSummaryData,
)
from application.models.scan_lookup import ScanKind, ScanLookupData
from application.models.scan_result import ScanResultData
from application.models.stock_count import (
    StockCountData,
    StockCountLineData,
    StockCountUnitData,
)
from application.models.stock_on_hand import StockOnHandData
from application.models.supplier import SupplierData
from application.models.supplier_return import (
    SupplierReturnData,
    SupplierReturnLineData,
)
from application.models.tenant_settings import TenantSettingsData
from application.models.write_off import WriteOffData, WriteOffLineData

__all__ = [
    "AgeingRowData",
    "AcceptInviteData",
    "AuthTokensData",
    "CreateSuperAdminData",
    "CountScanResultData",
    "CreateTenantData",
    "CreditCompanyData",
    "CreditInvoiceDebtData",
    "CurrencySubtotalData",
    "CustomerAccountData",
    "CustomerData",
    "DebtorData",
    "DeviceTraceData",
    "DeviceUnitData",
    "EmployeeListItem",
    "Fulfilment",
    "GoodsReceiptData",
    "GoodsReceiptLineData",
    "InviteResultData",
    "FinancialLedgerRowData",
    "LocationData",
    "LocationSalesData",
    "InvoiceScanResultData",
    "LoginData",
    "MeData",
    "MovementRowData",
    "NeedsPricingRowData",
    "PaymentData",
    "PriceChangeData",
    "PriceDeviationData",
    "ProductData",
    "PurchaseOrderData",
    "PurchaseOrderLineData",
    "ReceivedUnitData",
    "ScanKind",
    "SalesInvoiceData",
    "SalesInvoiceLineData",
    "ScanLookupData",
    "ScanResultData",
    "StockCountData",
    "StockCountLineData",
    "StockCountUnitData",
    "SalesFiguresData",
    "SalesSummaryData",
    "StockOnHandData",
    "SupplierData",
    "TraceEventData",
    "TraceOriginData",
    "TraceSaleData",
    "SupplierReturnData",
    "SupplierReturnLineData",
    "TenantSettingsData",
    "WriteOffData",
    "WriteOffLineData",
]
