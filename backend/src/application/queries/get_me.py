"""The authenticated user's own identity view (GET /auth/me).

Identity comes from MasterDB; the role and permissions come from the token
the request already carried, which the claims factory built from the
store's ``employees`` row.
"""

from uuid import UUID

from application.core import CamelModel, IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.errors import InvalidTokenError
from application.ports import UserRepository
from domain.enums import AppRole, TenantRole


class MeData(CamelModel):
    user_id: UUID
    email: str
    full_name: str
    must_change_password: bool
    tenant_id: UUID | None = None
    role: TenantRole | None = None
    app_roles: list[AppRole] = []
    permissions: list[str] = []


class GetMeQuery(Query[ResultWithData[MeData]]):
    pass


class GetMeHandler(IRequestHandler[ResultWithData[MeData], GetMeQuery]):
    def __init__(self, users: UserRepository, current_user: CurrentUser) -> None:
        self._users = users
        self._current = current_user

    async def handle(self, request: GetMeQuery) -> ResultWithData[MeData]:
        user = await self._users.get(self._current.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()
        return ResultWithData[MeData].succeed_with_data(
            MeData(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                must_change_password=user.must_change_password,
                tenant_id=self._current.tenant_id,
                role=self._current.tenant_role,
                app_roles=list(self._current.app_roles),
                permissions=sorted(self._current.permissions),
            )
        )
