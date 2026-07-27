from datetime import datetime
from uuid import UUID

from sqlalchemy import update

from domain.entities import RefreshTokenRecord
from infrastructure.persistence.master.models import RefreshTokenModel

from .base import MasterCrudRepository


class SqlRefreshTokenRepository(
    MasterCrudRepository[RefreshTokenRecord, UUID, RefreshTokenModel]
):
    model = RefreshTokenModel

    def _key(self, entity: RefreshTokenRecord) -> UUID:
        return entity.id

    def _to_entity(self, row: RefreshTokenModel) -> RefreshTokenRecord:
        return RefreshTokenRecord(
            id=row.id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            replaced_by=row.replaced_by,
        )

    def _to_model(self, entity: RefreshTokenRecord) -> RefreshTokenModel:
        return RefreshTokenModel(
            id=entity.id,
            user_id=entity.user_id,
            token_hash=entity.token_hash,
            expires_at=entity.expires_at,
            revoked_at=entity.revoked_at,
            replaced_by=entity.replaced_by,
        )

    def _apply(self, row: RefreshTokenModel, entity: RefreshTokenRecord) -> None:
        row.revoked_at = entity.revoked_at
        row.replaced_by = entity.replaced_by

    async def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
