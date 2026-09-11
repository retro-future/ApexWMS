"""Entities, split by the database they live in (PRD §3.1).

MasterDB holds the tenant registry and *identity*: who a person is, which
platform roles they hold, which stores they may act in. Each TenantDB
holds that store's business data — its catalog from M2, its ledgers from
M3 — and its ``Employee`` rows: what a person may do *there*.
"""

from domain.entities.credit_company import CreditCompany
from domain.entities.customer import Customer
from domain.entities.customer_return import CustomerReturn, CustomerReturnLine
from domain.entities.device_unit import DeviceUnit
from domain.entities.device_unit_price_change import DeviceUnitPriceChange
from domain.entities.document import Document
from domain.entities.employee import Employee
from domain.entities.exchange_rate import ExchangeRate
from domain.entities.financial_transaction import FinancialTransaction
from domain.entities.goods_receipt import GoodsReceipt, GoodsReceiptLine, ReceivedUnit
from domain.entities.invitation import Invitation, InvitationKind
from domain.entities.location import Location
from domain.entities.payment import Payment
from domain.entities.product import Product
from domain.entities.product_price_change import ProductPriceChange
from domain.entities.purchase_order import PurchaseOrder, PurchaseOrderLine
from domain.entities.refresh_token import RefreshTokenRecord
from domain.entities.removal_line import RemovalLine
from domain.entities.sales_invoice import SalesInvoice, SalesInvoiceLine
from domain.entities.stock_count import StockCount, StockCountLine, StockCountUnit
from domain.entities.stock_level import StockLevel
from domain.entities.stock_movement import StockMovement
from domain.entities.supplier import Supplier
from domain.entities.supplier_return import SupplierReturn, SupplierReturnLine
from domain.entities.tenant import Tenant
from domain.entities.user import User
from domain.entities.user_app_role import UserAppRole
from domain.entities.user_tenant_access import UserTenantAccess
from domain.entities.write_off import WriteOff, WriteOffLine

__all__ = [
    "CreditCompany",
    "Customer",
    "CustomerReturn",
    "CustomerReturnLine",
    "DeviceUnit",
    "DeviceUnitPriceChange",
    "Document",
    "Employee",
    "ExchangeRate",
    "FinancialTransaction",
    "GoodsReceipt",
    "GoodsReceiptLine",
    "Invitation",
    "InvitationKind",
    "Location",
    "Payment",
    "Product",
    "ProductPriceChange",
    "PurchaseOrder",
    "PurchaseOrderLine",
    "ReceivedUnit",
    "RefreshTokenRecord",
    "RemovalLine",
    "SalesInvoice",
    "SalesInvoiceLine",
    "StockCount",
    "StockCountLine",
    "StockCountUnit",
    "StockLevel",
    "StockMovement",
    "Supplier",
    "SupplierReturn",
    "SupplierReturnLine",
    "Tenant",
    "User",
    "UserAppRole",
    "UserTenantAccess",
    "WriteOff",
    "WriteOffLine",
]
