"""A user changes their own password.

Also the exit from the temporary password an Owner is provisioned with:
clearing ``must_change_password`` is the only way that flag goes away.

Credentials are master-side, so this never opens a tenant database — the
password is a property of the person, not of any store they work at.
"""

from pydantic import Field

from application.common.repository import MasterDbRepository
from application.core import Command, IRequestHandler, Result
from application.dtos import CurrentUser
from application.errors import InvalidCredentialsError, NotFoundError
from application.ports import (
    Clock,
    MasterUnitOfWork,
    PasswordHasher,
)
from application.services import TokenIssuer
from application.specs import UserForWrite
from domain.entities import User
from infrastructure.persistence.master.models import UserModel


class ChangePasswordCommand(Command[Result]):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class ChangePasswordHandler(IRequestHandler[Result, ChangePasswordCommand]):
    def __init__(
        self,
        users: MasterDbRepository[User, UserModel],
        issuer: TokenIssuer,
        hasher: PasswordHasher,
        clock: Clock,
        uow: MasterUnitOfWork,
        current_user: CurrentUser,
    ) -> None:
        self._users = users
        self._issuer = issuer
        self._hasher = hasher
        self._clock = clock
        self._uow = uow
        self._user_id = current_user.user_id

    async def handle(self, request: ChangePasswordCommand) -> Result:
        user = await self._users.find_one(UserForWrite(self._user_id))
        if user is None:
            raise NotFoundError("no such user")
        if user.password_hash is None or not self._hasher.verify(
            user.password_hash, request.current_password
        ):
            raise InvalidCredentialsError()

        user.password_hash = self._hasher.hash(request.new_password)
        user.must_change_password = False
        await self._users.update(user)
        # A password change invalidates sessions opened with the old one —
        # including the temporary password an operator may have seen.
        await self._issuer.revoke_all_for_user(self._user_id, self._clock.now())
        await self._uow.commit()
        return Result.succeed()
