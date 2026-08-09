"""Resolving what a line costs the customer — FR-2.14, PRD §4.5b.

```
price_for(unit, product):
    1. unit.asking_price is not None          →  unit.asking_price
    2. unit.condition is NEW
       and product.default_sale_price is not None
                                              →  product.default_sale_price
    3. otherwise                              →  PriceNotSetError
```

**Step 2's ``condition is NEW`` guard is the whole point of the rule, and
it is not optional.** The obvious version — *"unit price, else catalog
price"* — is a silent-corruption trap. A used iPhone 15 Pro worth $500,
received without an asking price, against a catalog row holding the *new*
price of $900, would be quoted at $900 at the counter. There is no error,
no empty field, no visual cue: the invoice has a number on it, the ledger
books $900 of revenue, and the margin report shows $600 of profit that
never existed. **The failure is invisible precisely because a plausible
figure appeared.**

Two consequences fall out for free. A model the store only ever trades
used is just a catalog row with no price — step 2 never fires for any of
its units, so **no "used-only product" flag is needed**. And a specific
*new* unit can still be discounted (an opened box, a display model) by
giving it its own price, because step 1 wins for every condition.

Pure: no database, no repository, no I/O. Both callers — the scan that
adds a line (FR-4.2b) and the confirm that re-resolves it (FR-4.5b1) —
run the identical function, which is what stops a draft and its confirm
from disagreeing about the rule.
"""

from domain.entities import DeviceUnit, Product
from domain.enums import DeviceCondition
from domain.errors import PriceNotSetError
from domain.value_objects import Money


class PriceResolver:
    """Resolves what a line costs the customer, per the rule above.

    Stateless: both methods are pure functions of *unit* and *product*,
    grouped under one name for a consistent call site
    (``PriceResolver.resolve(...)``). Not DI-registered — its one real
    caller, ``DeviceUnitData.from_entity``, is a response-model classmethod
    rather than a constructor-injected collaborator, so there is no seam
    for a container to fill.
    """

    @staticmethod
    def resolve(unit: DeviceUnit | None, product: Product) -> Money:
        """The price *unit* sells at, or ``PriceNotSetError``.

        *unit* is ``None`` for a QUANTITY line: an accessory has no
        per-unit identity to hang a price on (§4.1), so it has no step 1
        and resolves to the catalog price or is refused one step earlier.
        A QUANTITY product with no catalog price is therefore not sellable
        at all — there is nowhere else a price could come from.
        """
        price = PriceResolver.resolve_or_none(unit, product)
        if price is None:
            raise PriceNotSetError(PriceResolver._why_unpriced(unit, product))
        return price

    @staticmethod
    def resolve_or_none(unit: DeviceUnit | None, product: Product) -> Money | None:
        """The same rule, for callers that need to *ask* rather than
        insist — the scan-lookup screen (FR-7.2) and the needs-pricing
        worklist (FR-9.6), which exist to show that a price is missing."""
        if unit is not None and unit.asking_price is not None:
            return unit.asking_price
        if unit is None or unit.condition is DeviceCondition.NEW:
            return product.default_sale_price
        return None

    @staticmethod
    def _why_unpriced(unit: DeviceUnit | None, product: Product) -> str:
        """The message matters: the Seller who hits this cannot fix it —
        pricing is Owner/Manager (§2.1) — so it has to say what is wrong
        and who can act on it (FR-4.2b)."""
        if unit is None:
            return (
                f"{product.sku} has no catalog price, and an accessory has no per-unit "
                "price to fall back on — an Owner or Manager must price it"
            )
        if unit.condition is not DeviceCondition.NEW:
            return (
                f"IMEI {unit.imei} is {unit.condition.value} and has no price of its own. "
                f"A unit that is not new never inherits the catalog price of {product.sku} — "
                "an Owner or Manager must price this handset"
            )
        return (
            f"IMEI {unit.imei} has no price of its own and {product.sku} has no catalog "
            "price — an Owner or Manager must set one"
        )
