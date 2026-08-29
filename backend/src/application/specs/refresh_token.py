"""Reads for stored refresh tokens (MasterDB, ADR 0007)."""

from uuid import UUID

from application.common.specification import Specification
from infrastructure.persistence.master.models import RefreshTokenModel


class RefreshTokenForWrite(Specification[RefreshTokenModel]):
    def __init__(self, token_id: UUID) -> None:
        super().__init__(RefreshTokenModel)
        self.token_id = token_id
        self.where(RefreshTokenModel.id == token_id)
        self.lock()


class LiveTokensForUser(Specification[RefreshTokenModel]):
    """Every not-yet-revoked token for a user, locked: the caller revokes
    each one (theft response, or a password change)."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(RefreshTokenModel)
        self.user_id = user_id
        self.where(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked_at.is_(None),
        )
        self.lock()
