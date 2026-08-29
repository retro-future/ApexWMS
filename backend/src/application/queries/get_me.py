"""The authenticated user's own identity view (GET /auth/me).

Identity comes from MasterDB; the role and permissions come from the token
the request already carried, which the claims factory built from the
store's ``employees`` row.
"""

from application.common.repository import MasterDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.errors import InvalidTokenError
from application.models import MeData
from domain.entities import User
from infrastructure.persistence.master.models import UserModel


class GetMeQuery(Query[ResultWithData[MeData]]):
    pass


class GetMeHandler(IRequestHandler[ResultWithData[MeData], GetMeQuery]):
    def __init__(
        self, users: MasterDbRepository[User, UserModel], current_user: CurrentUser
    ) -> None:
        self._users = users
        self._current = current_user

    async def handle(self, request: GetMeQuery) -> ResultWithData[MeData]:
        user = await self._users.get(self._current.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()
        return ResultWithData[MeData].succeed_with_data(MeData.from_entity(user, self._current))
