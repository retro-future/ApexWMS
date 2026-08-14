# Feature map

Every feature area below is CQRS: one file per operation under
`backend/src/application/commands/` or `queries/`, one response payload per
file under `application/models/` (`.claude/rules/backend/cqrs-response-models.md`),
and a `Handler` DI-registered in `di/providers/handlers.py`. Paths are
relative to `backend/src/application/` unless noted.

## Auth & identity

Login, session refresh, invitations, and the platform side of who a user
is. Deep dive: [multi-tenancy.md](../docs/architecture/multi-tenancy.md).

- Commands: `commands/login.py`, `refresh_tokens.py`, `change_password.py`,
  `invite_user.py`, `accept_invite.py`, `change_user_role.py`
- Queries: `queries/get_me.py`, `list_users.py`
- Models: `models/login.py`, `auth_tokens.py`, `invite_user.py`,
  `accept_invite.py`, `me.py`, `employee.py`
- Services: `services/claims.py` (`ClaimsFactory`), `token_issuer.py`
- Security infra: `infrastructure/security/current_user_accessor.py`,
  `infrastructure/current_tenant_accessor.py` (see
  [tenant-resolution.md](../docs/architecture/tenant-resolution.md))

## Platform & tenancy

SuperAdmin provisioning and per-store settings. Deep dive:
[multi-tenancy.md](../docs/architecture/multi-tenancy.md).

- Commands: `commands/create_tenant.py`, `create_superadmin.py`,
  `update_tenant_settings.py`
- Queries: `queries/get_tenant_settings.py`
- Models: `models/create_tenant.py`, `create_superadmin.py`,
  `tenant_settings.py`
- Services: `services/slugs.py`, `timezones.py`
- CLI entry points: `infrastructure/cli.py` (`apexwms create-tenant`,
  `create-superadmin`)

## Catalog (M2)

Products, locations, suppliers, customers — the `TenantCrudRepository`
aggregates. Deep dive:
[ledgers.md#repository-bases](../docs/architecture/ledgers.md).

- Commands: `commands/create_product.py`, `update_product.py`,
  `create_location.py`, `update_location.py`, `create_supplier.py`,
  `update_supplier.py`, `create_customer.py`, `update_customer.py`
- Queries: `queries/get_product.py`, `list_products.py`, `get_location.py`,
  `list_locations.py`, `get_supplier.py`, `list_suppliers.py`,
  `get_customer.py`, `list_customers.py`
- Models: `models/product.py`, `location.py`, `supplier.py`, `customer.py`

## Ledgers & device unit pricing (M3)

Stock/financial ledgers and everything that reprices a unit or product.
Deep dive: [ledgers.md](../docs/architecture/ledgers.md),
[value-objects.md](../docs/architecture/value-objects.md).

- Commands: `commands/reprice_device_unit.py`, `reprice_device_units.py`,
  `change_device_unit_condition.py`
- Queries: `queries/get_device_unit.py`,
  `get_device_unit_price_history.py`, `get_product_price_history.py`
- Models: `models/device_unit.py`, `price_history.py`,
  `currency_subtotal.py`
- Services: `services/ledger.py` (`LedgerPoster`), `verification.py`
  (`apexwms verify-projections`/`verify-financials`),
  `device_unit_repricer.py`, `product_repricer.py`, `device_unit_loader.py`,
  `sale_price.py`
- Domain: `domain/services/pricing.py` (`PriceResolver`),
  `projection.py` (`UnitProjector`), `domain/value_objects/cost_pool.py`

## Purchase orders & goods receipts (M4)

Inbound documents: PO to goods receipt to IMEI scan-in to confirm. Deep
dive: [documents.md](../docs/architecture/documents.md).

- Commands: `commands/create_purchase_order.py`,
  `confirm_purchase_order.py`, `cancel_purchase_order.py`,
  `create_goods_receipt.py`, `confirm_goods_receipt.py`,
  `cancel_goods_receipt.py`, `scan_receipt_unit.py`,
  `unscan_receipt_unit.py`, `price_receipt_unit.py`
- Queries: `queries/get_purchase_order.py`, `list_purchase_orders.py`,
  `get_goods_receipt.py`, `list_goods_receipts.py`
- Models: `models/purchase_order.py`, `goods_receipt.py`, `received_unit.py`,
  `scan_result.py`
- Services: `services/document_numbering.py` (`DocumentNumberer`),
  `document_lines.py`, `document_loader.py`, `receipt_posting.py`
  (`ReceiptPoster`)
- Domain: `domain/entities/document.py` (`Document` base lifecycle),
  `purchase_order.py`, `goods_receipt.py`

## Cross-cutting ports (used by every feature area)

`application/ports/`: `clock.py`, `provisioning.py`, `repository.py`
(`AppendOnlyRepository`), `security.py`, `tenancy.py`, `uow.py`, plus
`master/` and `tenant/` for the two database-specific repository port
groups.
