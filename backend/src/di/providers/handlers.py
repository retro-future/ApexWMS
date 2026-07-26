"""Command/query handlers (REQUEST scope), registered via ``provide_all``.

Every constructor parameter here is already a DI-resolvable port or
``NewType`` (see ``application/types.py`` for ``ResolvedTenantId``/TTLs), so
dishka can wire each class by reflecting on its ``__init__`` — no
hand-written factory needed (.claude/rules/backend/providers.md).

``CreateTenantHandler`` and ``CreateSuperAdminHandler`` are deliberately
absent: both are CLI-only, because creating stores and platform operators
has no HTTP surface in the MVP (PRD §3.4, §3.5).
"""

from dishka import Provider, Scope, provide_all

from application.commands.accept_invite import AcceptInviteHandler
from application.commands.change_password import ChangePasswordHandler
from application.commands.change_user_role import ChangeUserRoleHandler
from application.commands.invite_user import InviteUserHandler
from application.commands.login import LoginHandler
from application.commands.refresh_tokens import RefreshTokensHandler
from application.commands.update_tenant_settings import UpdateTenantSettingsHandler
from application.queries.get_me import GetMeHandler
from application.queries.get_tenant_settings import GetTenantSettingsHandler
from application.queries.list_users import ListUsersHandler
from application.services import ClaimsFactory, TokenIssuer


class HandlersProvider(Provider):
    scope = Scope.REQUEST

    handlers = provide_all(
        ClaimsFactory,
        TokenIssuer,
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
    )
