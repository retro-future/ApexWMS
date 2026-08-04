"""CQRS commands — one ``Command``, one ``IRequestHandler``, one write operation."""

from application.commands.accept_invite import AcceptInviteCommand, AcceptInviteHandler
from application.commands.change_password import (
    ChangePasswordCommand,
    ChangePasswordHandler,
)
from application.commands.change_user_role import (
    ChangeUserRoleCommand,
    ChangeUserRoleHandler,
)
from application.commands.create_superadmin import (
    CreateSuperAdminCommand,
    CreateSuperAdminHandler,
)
from application.commands.create_tenant import CreateTenantCommand, CreateTenantHandler
from application.commands.invite_user import InviteEmployeeCommand, InviteUserHandler
from application.commands.login import LoginCommand, LoginHandler
from application.commands.refresh_tokens import RefreshTokensCommand, RefreshTokensHandler
from application.commands.update_tenant_settings import (
    UpdateTenantSettingsCommand,
    UpdateTenantSettingsHandler,
)

__all__ = [
    "AcceptInviteCommand",
    "AcceptInviteHandler",
    "ChangePasswordCommand",
    "ChangePasswordHandler",
    "ChangeUserRoleCommand",
    "ChangeUserRoleHandler",
    "CreateSuperAdminCommand",
    "CreateSuperAdminHandler",
    "CreateTenantCommand",
    "CreateTenantHandler",
    "InviteEmployeeCommand",
    "InviteUserHandler",
    "LoginCommand",
    "LoginHandler",
    "RefreshTokensCommand",
    "RefreshTokensHandler",
    "UpdateTenantSettingsCommand",
    "UpdateTenantSettingsHandler",
]
