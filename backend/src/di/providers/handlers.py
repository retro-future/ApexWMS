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
from application.commands.change_device_unit_condition import (
    ChangeDeviceUnitConditionHandler,
)
from application.commands.change_password import ChangePasswordHandler
from application.commands.change_user_role import ChangeUserRoleHandler
from application.commands.create_customer import CreateCustomerHandler
from application.commands.create_location import CreateLocationHandler
from application.commands.create_product import CreateProductHandler
from application.commands.create_supplier import CreateSupplierHandler
from application.commands.invite_user import InviteUserHandler
from application.commands.login import LoginHandler
from application.commands.refresh_tokens import RefreshTokensHandler
from application.commands.reprice_device_unit import RepriceDeviceUnitHandler
from application.commands.reprice_device_units import RepriceDeviceUnitsHandler
from application.commands.update_customer import UpdateCustomerHandler
from application.commands.update_location import UpdateLocationHandler
from application.commands.update_product import UpdateProductHandler
from application.commands.update_supplier import UpdateSupplierHandler
from application.commands.update_tenant_settings import UpdateTenantSettingsHandler
from application.queries.get_customer import GetCustomerHandler
from application.queries.get_device_unit import GetDeviceUnitHandler
from application.queries.get_device_unit_price_history import (
    GetDeviceUnitPriceHistoryHandler,
)
from application.queries.get_location import GetLocationHandler
from application.queries.get_me import GetMeHandler
from application.queries.get_product import GetProductHandler
from application.queries.get_product_price_history import GetProductPriceHistoryHandler
from application.queries.get_supplier import GetSupplierHandler
from application.queries.get_tenant_settings import GetTenantSettingsHandler
from application.queries.list_customers import ListCustomersHandler
from application.queries.list_locations import ListLocationsHandler
from application.queries.list_products import ListProductsHandler
from application.queries.list_suppliers import ListSuppliersHandler
from application.queries.list_users import ListUsersHandler


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
    )
