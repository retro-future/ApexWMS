"""Sole mapper for the SalesInvoice aggregate: lines included.

A line's three money columns are bare minor amounts denominated by the
product (§4.5 rule 3), read through a viewonly ``product`` relationship the
spec eager-loads. Lines are scanned and unscanned while the invoice is a
draft, and confirm writes every line's ``resolved``/``charged`` snapshot at
once (FR-4.5b1), so ``to_model``'s update path is a full id-keyed sync that
also copies the mutable price fields.
"""

from decimal import Decimal

from domain.entities import SalesInvoice, SalesInvoiceLine
from domain.enums import DocumentStatus, PaymentType, TrackingType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    SalesInvoiceLineModel,
    SalesInvoiceModel,
)


class SalesInvoiceMapper:
    model: type[SalesInvoiceModel] = SalesInvoiceModel

    def to_entity(self, model: SalesInvoiceModel) -> SalesInvoice:
        return SalesInvoice(
            id=model.id,
            number=model.number,
            status=DocumentStatus(model.status),
            location_id=model.location_id,
            customer_id=model.customer_id,
            note=model.note,
            payment_type=PaymentType(model.payment_type),
            credit_company_id=model.credit_company_id,
            contract_ref=model.contract_ref,
            debt=self._debt(model.debt_minor),
            sale_rate_id=model.sale_rate_id,
            created_by=model.created_by,
            created_at=model.created_at,
            confirmed_by=model.confirmed_by,
            confirmed_at=model.confirmed_at,
            cancelled_by=model.cancelled_by,
            cancelled_at=model.cancelled_at,
            cancellation_reason=model.cancellation_reason,
            lines=[self._line_to_entity(line) for line in model.lines],
        )

    def _line_to_entity(self, model: SalesInvoiceLineModel) -> SalesInvoiceLine:
        currency = Currency(model.product.currency)
        return SalesInvoiceLine(
            id=model.id,
            sales_invoice_id=model.sales_invoice_id,
            product_id=model.product_id,
            device_unit_id=model.device_unit_id,
            quantity=model.quantity,
            currency=currency,
            tracking_type=TrackingType(model.product.tracking_type),
            override_price=self._money(model.override_price_minor, currency),
            price_approved_by=model.price_approved_by,
            price_note=model.price_note,
            resolved_price=self._money(model.resolved_price_minor, currency),
            charged_price=self._money(model.charged_price_minor, currency),
        )

    def to_model(
        self, entity: SalesInvoice, model: SalesInvoiceModel | None = None
    ) -> SalesInvoiceModel:
        fresh = model is None
        model = model or SalesInvoiceModel(id=entity.id)
        # The number, the author and the location cannot change once an
        # invoice is open, so they are set only on the fresh path.
        model.status = entity.status.value
        model.customer_id = entity.customer_id
        model.note = entity.note
        model.payment_type = entity.payment_type.value
        model.credit_company_id = entity.credit_company_id
        model.contract_ref = entity.contract_ref
        model.debt_minor = self._minor(entity.debt)
        model.sale_rate_id = entity.sale_rate_id
        model.confirmed_by = entity.confirmed_by
        model.confirmed_at = entity.confirmed_at
        model.cancelled_by = entity.cancelled_by
        model.cancelled_at = entity.cancelled_at
        model.cancellation_reason = entity.cancellation_reason
        if fresh:
            model.number = entity.number
            model.location_id = entity.location_id
            model.created_by = entity.created_by
            model.created_at = entity.created_at
        self._sync_lines(entity, model)
        return model

    @staticmethod
    def _line_to_model(entity: SalesInvoiceLine) -> SalesInvoiceLineModel:
        return SalesInvoiceLineModel(
            id=entity.id,
            product_id=entity.product_id,
            device_unit_id=entity.device_unit_id,
            quantity=entity.quantity,
            override_price_minor=SalesInvoiceMapper._minor(entity.override_price),
            price_approved_by=entity.price_approved_by,
            price_note=entity.price_note,
            resolved_price_minor=SalesInvoiceMapper._minor(entity.resolved_price),
            charged_price_minor=SalesInvoiceMapper._minor(entity.charged_price),
        )

    def _sync_lines(self, entity: SalesInvoice, model: SalesInvoiceModel) -> None:
        want = {line.id: line for line in entity.lines}
        for row in list(model.lines):
            line = want.get(row.id)
            if line is None:
                model.lines.remove(row)  # cascade delete-orphan issues the DELETE
            else:
                # The product and the handset are left alone: a line naming
                # the wrong phone is removed and re-scanned.
                row.quantity = line.quantity
                row.override_price_minor = self._minor(line.override_price)
                row.price_approved_by = line.price_approved_by
                row.price_note = line.price_note
                row.resolved_price_minor = self._minor(line.resolved_price)
                row.charged_price_minor = self._minor(line.charged_price)
        have = {row.id for row in model.lines}
        for line in entity.lines:
            if line.id not in have:
                model.lines.append(self._line_to_model(line))

    @staticmethod
    def _minor(amount: Money | None) -> int | None:
        return None if amount is None else amount.amount_minor

    @staticmethod
    def _money(minor: int | None, currency: Currency) -> Money | None:
        return None if minor is None else Money(minor, currency)

    @staticmethod
    def _debt(minor: int | Decimal | None) -> Money | None:
        return None if minor is None else Money(int(minor), Currency.UZS)
