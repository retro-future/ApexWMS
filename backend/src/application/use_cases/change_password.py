"""A user changes their own password.

Also the exit from the temporary password an Owner is provisioned with:
clearing ``must_change_password`` is the only way that flag goes away.

Credentials are master-side, so this never opens a tenant database — the
password is a property of the person, not of any store they work at.
"""

from uuid import UUID

from application.errors import InvalidCredentialsError, NotFoundError
from application.ports import (
    Clock,
    MasterUnitOfWork,
    PasswordHasher,
    RefreshTokenRepository,
    UserRepository,
)


class ChangePassword:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        hasher: PasswordHasher,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._hasher = hasher
        self._clock = clock
        self._uow = uow

    async def execute(self, user_id: UUID, current_password: str, new_password: str) -> None:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundError("no such user")
        if user.password_hash is None or not self._hasher.verify(
            user.password_hash, current_password
        ):
            raise InvalidCredentialsError()

        user.password_hash = self._hasher.hash(new_password)
        user.must_change_password = False
        await self._users.update(user)
        # A password change invalidates sessions opened with the old one —
        # including the temporary password an operator may have seen.
        await self._refresh_tokens.revoke_all_for_user(user_id, self._clock.now())
        await self._uow.commit()
