import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import MasterBase


class InvitationModel(MasterBase):
    """Master-side so acceptance needs no tenant context (PRD §3.1).

    ``tenant_id``/``tenant_role`` are set for an employee invite, ``app_role``
    for a platform-operator invite — never both.
    """

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id"), nullable=True
    )
    tenant_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    app_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
