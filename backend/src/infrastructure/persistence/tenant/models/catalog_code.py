from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class CatalogCodeSequenceModel(TenantBase):
    """The counter behind a generated SKU (``PH-000001``) or in-store barcode.

    One row per ``CatalogCodeKind``, handed out under a row lock. Unlike
    ``document_sequences`` it has no year: a catalog code is stable for the
    life of the product, so its sequence never restarts.
    """

    __tablename__ = "catalog_code_sequences"

    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer)
