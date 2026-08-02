"""The permission catalog (PRD §2.1): a flat, closed set of strings that the
two role systems (``AppRole`` / ``TenantRole``) assign subsets of.

A tenant role can only ever reference this catalog, never an app-role name,
and vice versa — which is what keeps "custom permissions per tenant" from
colliding with platform roles. Authorization compares permissions, not
roles, because PRD §2.1's matrix is not hierarchical: a Storekeeper receives
goods but cannot sell, a Seller sells but cannot receive. Neither outranks
the other.
"""

from enum import StrEnum, unique


@unique
class Permission(StrEnum):
    """Values are the wire-format strings compared by authorization checks
    and serialized verbatim in ``GET /auth/me``'s response — do not rename
    a value once shipped, only add new members."""

    # --- platform level (held via AppRole, MasterDB) ------------------
    TENANT_VIEW = "Permission.Tenant.View"
    TENANT_MANAGE = "Permission.Tenant.Manage"
    APP_ROLES_MANAGE = "Permission.AppRoles.Manage"

    # --- store level (held via TenantRole, TenantDB) -------------------
    USERS_VIEW = "Permission.Users.View"
    USERS_MANAGE = "Permission.Users.Manage"
    TENANT_SETTINGS_VIEW = "Permission.TenantSettings.View"
    TENANT_SETTINGS_MANAGE = "Permission.TenantSettings.Manage"
    LOCATION_VIEW = "Permission.Location.View"
    LOCATION_MANAGE = "Permission.Location.Manage"
    CATALOG_VIEW = "Permission.Catalog.View"
    CATALOG_MANAGE = "Permission.Catalog.Manage"
    # Acquisition cost and margin. Response-shaping, not just UI (FR-1.7).
    COST_VIEW = "Permission.Cost.View"
    PURCHASE_ORDER_VIEW = "Permission.PurchaseOrder.View"
    PURCHASE_ORDER_MANAGE = "Permission.PurchaseOrder.Manage"
    RECEIVING_VIEW = "Permission.Receiving.View"
    RECEIVING_MANAGE = "Permission.Receiving.Manage"
    SALES_VIEW = "Permission.Sales.View"
    SALES_MANAGE = "Permission.Sales.Manage"
    # Two distinct acts, deliberately not one permission (§2.1): *setting* a
    # price is stating what the store asks for a model or a handset
    # (FR-2.15, FR-2.19); *overriding* one is a negotiation on a single
    # invoice line (FR-4.5). Today both are Owner/Manager, but they are not
    # the same decision and a future role could hold one without the other.
    PRICING_SET = "Permission.Pricing.Set"
    PRICING_OVERRIDE = "Permission.Pricing.Override"
    CREDIT_SALE_CREATE = "Permission.CreditSale.Create"
    CREDIT_COMPANY_VIEW = "Permission.CreditCompany.View"
    CREDIT_COMPANY_MANAGE = "Permission.CreditCompany.Manage"
    PAYMENT_RECORD = "Permission.Payment.Record"
    PAYMENT_REVERSE = "Permission.Payment.Reverse"
    CUSTOMER_VIEW = "Permission.Customer.View"
    CUSTOMER_MANAGE = "Permission.Customer.Manage"
    CUSTOMER_ACCOUNT_VIEW = "Permission.CustomerAccount.View"
    # The full debtor list across all customers is a business-health
    # figure, not a serving-this-customer one (PRD §2.1 note 1).
    CUSTOMER_ACCOUNT_VIEW_ALL = "Permission.CustomerAccount.ViewAll"
    SUPPLIER_RETURN_VIEW = "Permission.SupplierReturn.View"
    SUPPLIER_RETURN_MANAGE = "Permission.SupplierReturn.Manage"
    STOCK_COUNT_RUN = "Permission.StockCount.Run"
    STOCK_COUNT_CONFIRM = "Permission.StockCount.Confirm"
    WRITE_OFF_MANAGE = "Permission.WriteOff.Manage"
    DOCUMENT_VIEW = "Permission.Document.View"
    DOCUMENT_CANCEL = "Permission.Document.Cancel"
    SCAN_LOOKUP = "Permission.Scan.Lookup"
    REPORTING_VIEW = "Permission.Reporting.View"
    FINANCIAL_LEDGER_VIEW = "Permission.FinancialLedger.View"

    @classmethod
    def all(cls) -> frozenset[Permission]:
        return frozenset(cls)
