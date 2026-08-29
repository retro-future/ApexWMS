"""The reads the platform-identity use cases need, one class each.

Written against ``UserModel`` (MasterDB), not ``User`` (ADR 0007). The
by-email read and the sign-up uniqueness probe are inline in the handlers.
"""

from uuid import UUID

from application.common.specification import Specification
from infrastructure.persistence.master.models import UserModel


class UserForWrite(Specification[UserModel]):
    """Locks the row for a command that loads a user to mutate it."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(UserModel)
        self.user_id = user_id
        self.where(UserModel.id == user_id)
        self.lock()
