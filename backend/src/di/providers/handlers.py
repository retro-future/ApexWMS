"""Command/query handlers (REQUEST scope), registered via ``provide_all``.

Every constructor parameter here is already a DI-resolvable port or
``NewType`` (see ``application/types.py`` for ``ResolvedTenantId``/TTLs), so
dishka can wire each class by reflecting on its ``__init__`` — no
hand-written factory needed (.claude/rules/backend/providers.md).

The collaborator services some of these handlers depend on
(``ClaimsFactory``, ``SalePriceParser``, ...) are registered by
``ApplicationServicesProvider`` (``di/providers/services.py``), not here.

``CreateTenantHandler`` and ``CreateSuperAdminHandler`` are deliberately
absent: both are CLI-only, because creating stores and platform operators
has no HTTP surface in the MVP (PRD §3.4, §3.5).
"""

from dishka import Provider, Scope, provide_all

from application.commands.accept_invite import AcceptInviteHandler
from application.commands.cancel_goods_receipt import CancelGoodsReceiptHandler
from application.commands.cancel_purchase_order import CancelPurchaseOrderHandler
from application.commands.cancel_sales_invoice import CancelSalesInvoiceHandler
from application.commands.cancel_stock_count import CancelStockCountHandler
from application.commands.cancel_supplier_return import CancelSupplierReturnHandler
from application.commands.cancel_write_off import CancelWriteOffHandler
from application.commands.change_device_unit_condition import (
    ChangeDeviceUnitConditionHandler,
)
from application.commands.change_password import ChangePasswordHandler
from application.commands.change_user_role import ChangeUserRoleHandler
from application.commands.close_stock_count import CloseStockCountHandler
from application.commands.confirm_goods_receipt import ConfirmGoodsReceiptHandler
from application.commands.confirm_purchase_order import ConfirmPurchaseOrderHandler
from application.commands.confirm_sales_invoice import ConfirmSalesInvoiceHandler
from application.commands.confirm_stock_count import ConfirmStockCountHandler
from application.commands.confirm_supplier_return import ConfirmSupplierReturnHandler
from application.commands.confirm_write_off import ConfirmWriteOffHandler
from application.commands.count_stock_count_line import CountStockCountLineHandler
from application.commands.create_credit_company import CreateCreditCompanyHandler
from application.commands.create_customer import CreateCustomerHandler
from application.commands.create_goods_receipt import CreateGoodsReceiptHandler
from application.commands.create_location import CreateLocationHandler
from application.commands.create_product import CreateProductHandler
from application.commands.create_purchase_order import CreatePurchaseOrderHandler
from application.commands.create_sales_invoice import CreateSalesInvoiceHandler
from application.commands.create_supplier import CreateSupplierHandler
from application.commands.create_supplier_return import CreateSupplierReturnHandler
from application.commands.create_write_off import CreateWriteOffHandler
from application.commands.invite_user import InviteUserHandler
from application.commands.login import LoginHandler
from application.commands.open_stock_count import OpenStockCountHandler
from application.commands.override_invoice_line_price import (
    OverrideInvoiceLinePriceHandler,
)
from application.commands.price_purchase_order_line import (
    PricePurchaseOrderLineHandler,
)
from application.commands.price_receipt_unit import PriceReceiptUnitHandler
from application.commands.record_payment import RecordPaymentHandler
from application.commands.refresh_tokens import RefreshTokensHandler
from application.commands.reprice_device_unit import RepriceDeviceUnitHandler
from application.commands.reprice_device_units import RepriceDeviceUnitsHandler
from application.commands.reverse_payment import ReversePaymentHandler
from application.commands.scan_invoice_line import ScanInvoiceLineHandler
from application.commands.scan_receipt_unit import ScanReceiptUnitHandler
from application.commands.scan_stock_count_unit import ScanStockCountUnitHandler
from application.commands.scan_supplier_return_line import ScanSupplierReturnLineHandler
from application.commands.scan_write_off_line import ScanWriteOffLineHandler
from application.commands.unscan_invoice_line import UnscanInvoiceLineHandler
from application.commands.unscan_receipt_unit import UnscanReceiptUnitHandler
from application.commands.unscan_stock_count_unit import UnscanStockCountUnitHandler
from application.commands.unscan_supplier_return_line import (
    UnscanSupplierReturnLineHandler,
)
from application.commands.unscan_write_off_line import UnscanWriteOffLineHandler
from application.commands.update_credit_company import UpdateCreditCompanyHandler
from application.commands.update_customer import UpdateCustomerHandler
from application.commands.update_location import UpdateLocationHandler
from application.commands.update_product import UpdateProductHandler
from application.commands.update_supplier import UpdateSupplierHandler
from application.commands.update_tenant_settings import UpdateTenantSettingsHandler
from application.queries.get_credit_company import GetCreditCompanyHandler
from application.queries.get_customer import GetCustomerHandler
from application.queries.get_customer_account import GetCustomerAccountHandler
from application.queries.get_device_unit import GetDeviceUnitHandler
from application.queries.get_device_unit_price_history import (
    GetDeviceUnitPriceHistoryHandler,
)
from application.queries.get_goods_receipt import GetGoodsReceiptHandler
from application.queries.get_location import GetLocationHandler
from application.queries.get_me import GetMeHandler
from application.queries.get_product import GetProductHandler
from application.queries.get_product_price_history import GetProductPriceHistoryHandler
from application.queries.get_purchase_order import GetPurchaseOrderHandler
from application.queries.get_sales_invoice import GetSalesInvoiceHandler
from application.queries.get_sales_invoice_pdf import GetSalesInvoicePdfHandler
from application.queries.get_stock_count import GetStockCountHandler
from application.queries.get_supplier import GetSupplierHandler
from application.queries.get_supplier_return import GetSupplierReturnHandler
from application.queries.get_tenant_settings import GetTenantSettingsHandler
from application.queries.get_write_off import GetWriteOffHandler
from application.queries.list_credit_companies import ListCreditCompaniesHandler
from application.queries.list_customers import ListCustomersHandler
from application.queries.list_debtors import ListDebtorsHandler
from application.queries.list_goods_receipts import ListGoodsReceiptsHandler
from application.queries.list_locations import ListLocationsHandler
from application.queries.list_price_deviations import ListPriceDeviationsHandler
from application.queries.list_products import ListProductsHandler
from application.queries.list_purchase_orders import ListPurchaseOrdersHandler
from application.queries.list_sales_invoices import ListSalesInvoicesHandler
from application.queries.list_stock_counts import ListStockCountsHandler
from application.queries.list_supplier_returns import ListSupplierReturnsHandler
from application.queries.list_suppliers import ListSuppliersHandler
from application.queries.list_users import ListUsersHandler
from application.queries.list_write_offs import ListWriteOffsHandler
from application.queries.scan_lookup import ScanLookupHandler


class HandlersProvider(Provider):
    scope = Scope.REQUEST

    handlers = provide_all(
        LoginHandler,
        RefreshTokensHandler,
        ChangePasswordHandler,
        InviteUserHandler,
        AcceptInviteHandler,
        GetMeHandler,
        ListUsersHandler,
        ChangeUserRoleHandler,
        GetTenantSettingsHandler,
        UpdateTenantSettingsHandler,
        # --- M2 catalog ---
        CreateProductHandler,
        UpdateProductHandler,
        GetProductHandler,
        GetProductPriceHistoryHandler,
        ListProductsHandler,
        CreateLocationHandler,
        UpdateLocationHandler,
        GetLocationHandler,
        ListLocationsHandler,
        CreateSupplierHandler,
        UpdateSupplierHandler,
        GetSupplierHandler,
        ListSuppliersHandler,
        CreateCustomerHandler,
        UpdateCustomerHandler,
        GetCustomerHandler,
        ListCustomersHandler,
        # --- M3 stock & unit pricing ---
        GetDeviceUnitHandler,
        GetDeviceUnitPriceHistoryHandler,
        RepriceDeviceUnitHandler,
        RepriceDeviceUnitsHandler,
        ChangeDeviceUnitConditionHandler,
        ScanLookupHandler,
        # --- M4 purchasing & receiving ---
        CreatePurchaseOrderHandler,
        PricePurchaseOrderLineHandler,
        ConfirmPurchaseOrderHandler,
        CancelPurchaseOrderHandler,
        GetPurchaseOrderHandler,
        ListPurchaseOrdersHandler,
        CreateGoodsReceiptHandler,
        ScanReceiptUnitHandler,
        PriceReceiptUnitHandler,
        UnscanReceiptUnitHandler,
        ConfirmGoodsReceiptHandler,
        CancelGoodsReceiptHandler,
        GetGoodsReceiptHandler,
        ListGoodsReceiptsHandler,
        # --- M5 outbound ---
        CreateSalesInvoiceHandler,
        ScanInvoiceLineHandler,
        OverrideInvoiceLinePriceHandler,
        UnscanInvoiceLineHandler,
        ConfirmSalesInvoiceHandler,
        CancelSalesInvoiceHandler,
        GetSalesInvoiceHandler,
        GetSalesInvoicePdfHandler,
        ListSalesInvoicesHandler,
        # --- M5b credit sales & customer debt ---
        CreateCreditCompanyHandler,
        UpdateCreditCompanyHandler,
        GetCreditCompanyHandler,
        ListCreditCompaniesHandler,
        RecordPaymentHandler,
        ReversePaymentHandler,
        GetCustomerAccountHandler,
        # --- M6 supplier returns ---
        CreateSupplierReturnHandler,
        ScanSupplierReturnLineHandler,
        UnscanSupplierReturnLineHandler,
        ConfirmSupplierReturnHandler,
        CancelSupplierReturnHandler,
        GetSupplierReturnHandler,
        ListSupplierReturnsHandler,
        # --- M6 write-offs ---
        CreateWriteOffHandler,
        ScanWriteOffLineHandler,
        UnscanWriteOffLineHandler,
        ConfirmWriteOffHandler,
        CancelWriteOffHandler,
        GetWriteOffHandler,
        ListWriteOffsHandler,
        # --- M6 stock counts ---
        OpenStockCountHandler,
        ScanStockCountUnitHandler,
        UnscanStockCountUnitHandler,
        CountStockCountLineHandler,
        CloseStockCountHandler,
        ConfirmStockCountHandler,
        CancelStockCountHandler,
        GetStockCountHandler,
        ListStockCountsHandler,
        # --- reporting ---
        ListPriceDeviationsHandler,
        ListDebtorsHandler,
    )
