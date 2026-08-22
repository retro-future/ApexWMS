from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantActivatableRow


class CreditCompanyModel(TenantActivatableRow):
    """A third-party financing partner (PRD §4.2, §4.7).

    Reference data with the same shape as ``suppliers``, and for the same
    reason it carries no money columns: the company pays in full at sale
    time, so nothing is ever owed to or by it.
    """

    __tablename__ = "credit_companies"

    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
