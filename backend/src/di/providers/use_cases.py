"""Use cases (REQUEST scope), registered via ``provide_all``.

Every constructor parameter here is already a DI-resolvable port or
``NewType`` (see ``application/types.py`` for ``ResolvedTenantId``/TTLs), so
dishka can wire each class by reflecting on its ``__init__`` — no
hand-written factory needed (.claude/rules/backend/providers.md).

``CreateTenant`` and ``CreateSuperAdmin`` are deliberately absent: both are
CLI-only, because creating stores and platform operators has no HTTP
surface in the MVP (PRD §3.4, §3.5).
"""

from dishka import Provider, Scope, provide_all

from application.use_cases import (
    AcceptInvite,
    ChangePassword,
    ChangeUserRole,
    ClaimsFactory,
    GetMe,
    GetTenantSettings,
    InviteUser,
    ListUsers,
    Login,
    RefreshTokens,
    TokenIssuer,
    UpdateTenantSettings,
)


class UseCasesProvider(Provider):
    scope = Scope.REQUEST

    use_cases = provide_all(
        ClaimsFactory,
        TokenIssuer,
        Login,
        RefreshTokens,
        ChangePassword,
        InviteUser,
        AcceptInvite,
        GetMe,
        ListUsers,
        ChangeUserRole,
        GetTenantSettings,
        UpdateTenantSettings,
    )
