"""The authenticated user's own identity view (GET /auth/me).

Identity comes from MasterDB; the role and permissions come from the token
the request already carried, which the claims factory built from the
store's ``employees`` row.
"""

from application.dtos import CurrentUser, MeView
from application.errors import InvalidTokenError
from application.ports import UserRepository


class GetMe:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, current: CurrentUser) -> MeView:
        user = await self._users.get(current.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()
        return MeView(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            must_change_password=user.must_change_password,
            permissions=current.permissions,
            tenant_id=current.tenant_id,
            tenant_role=current.tenant_role,
            app_roles=current.app_roles,
        )
