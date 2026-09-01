"""Seed a platform operator (PRD §3.5).

A SuperAdmin is not a separate kind of entity — it is a ``User`` with no
``tenant_id`` and ``app.superadmin`` in ``user_app_roles``. That is the
whole model, ported from the C# reference where the role is assigned
through Identity's ordinary ``user_roles`` join.

Invoked by the CLI only: there is no HTTP surface that creates one, and
having the MasterDB URL is the credential that authorizes it.
"""

from uuid import uuid4

from application.common.repository import MasterDbRepository
from application.common.specification import Specification
from application.core import Command, IRequestHandler, ResultWithData
from application.errors import AlreadyMemberError
from application.models import CreateSuperAdminData
from application.ports import (
    Clock,
    MasterUnitOfWork,
    PasswordHasher,
    TokenService,
)
from domain.entities import User, UserAppRole
from domain.enums import AppRole
from infrastructure.persistence.master.models import UserAppRoleModel, UserModel


class CreateSuperAdminCommand(Command[ResultWithData[CreateSuperAdminData]]):
    email: str
    full_name: str
    role: AppRole = AppRole.SUPERADMIN


class CreateSuperAdminHandler(
    IRequestHandler[ResultWithData[CreateSuperAdminData], CreateSuperAdminCommand]
):
    def __init__(
        self,
        users: MasterDbRepository[User, UserModel],
        app_roles: MasterDbRepository[UserAppRole, UserAppRoleModel],
        hasher: PasswordHasher,
        tokens: TokenService,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> None:
        self._users = users
        self._app_roles = app_roles
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock
        self._uow = uow

    async def handle(
        self, request: CreateSuperAdminCommand
    ) -> ResultWithData[CreateSuperAdminData]:
        email = request.email.strip().lower()
        if await self._users.exists(
            Specification(UserModel).where(UserModel.email == email)
        ):
            raise AlreadyMemberError(email, email=email)

        temporary_password = self._tokens.new_opaque_secret()
        user = User(
            id=uuid4(),
            email=email,
            full_name=request.full_name,
            password_hash=self._hasher.hash(temporary_password),
            # No home store: a platform operator's token carries no tenant claim.
            tenant_id=None,
            is_active=True,
            must_change_password=True,
            created_at=self._clock.now(),
        )
        await self._users.add(user)
        await self._app_roles.add(
            UserAppRole(id=uuid4(), user_id=user.id, role=request.role)
        )
        await self._uow.commit()
        return ResultWithData[CreateSuperAdminData].succeed_with_data(
            CreateSuperAdminData.from_entity(user, temporary_password)
        )
