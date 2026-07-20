"""The authenticated user's own identity view (GET /auth/me)."""

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
            tenant_id=current.tenant_id,
            role=current.role,
        )
