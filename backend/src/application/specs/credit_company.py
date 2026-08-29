"""The reads the credit-company use cases need, one class each.

Written against ``CreditCompanyModel``, not ``CreditCompany`` (ADR 0007).
The browse spec carries its filters as plain attributes so the in-memory
fake can read them without an ORM. The name-uniqueness probe is inline in
the create/update handlers, not a class here.
"""

from uuid import UUID

from sqlalchemy import or_

from application.common.specification import Specification
from infrastructure.persistence.tenant.models import CreditCompanyModel


class CreditCompanyForWrite(Specification[CreditCompanyModel]):
    """Locks the row so two concurrent renames cannot both pass the probe."""

    def __init__(self, credit_company_id: UUID) -> None:
        super().__init__(CreditCompanyModel)
        self.credit_company_id = credit_company_id
        self.where(CreditCompanyModel.id == credit_company_id)
        self.lock()


class CreditCompanyBrowse(Specification[CreditCompanyModel]):
    """The list: case-insensitive match over name, contact and phone,
    optional active filter, oldest first."""

    def __init__(self, search: str | None = None, is_active: bool | None = None) -> None:
        super().__init__(CreditCompanyModel)
        self.search = search
        self.is_active = is_active
        if search:
            term = f"%{search.strip()}%"
            self.where(
                or_(
                    CreditCompanyModel.name.ilike(term),
                    CreditCompanyModel.contact_name.ilike(term),
                    CreditCompanyModel.phone.ilike(term),
                )
            )
        if is_active is not None:
            self.where(CreditCompanyModel.is_active.is_(is_active))
        self.order(CreditCompanyModel.created_at, CreditCompanyModel.id)
