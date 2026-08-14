---
paths:
  - "backend/src/application/commands/**/*.py"
  - "backend/src/presentation/routers/**/*.py"
---

# A URL path segment is never a field on the client-facing body model

A `Command` often needs an id that only exists because the router pulled it
out of the URL (`purchase_order_id` in `PATCH
/purchase-orders/{purchase_order_id}/lines/{line_id}`). That id must reach
the handler on the same `Command` object as the fields the client actually
sent — but it must never appear in the body schema FastAPI generates from
that object, and a client sending one must never be able to make it stick.

## The old way, and why it was wrong

The previous shape put the path id directly on the `Command`, defaulted to
`None` and marked `exclude=True`, then had the router build the real object
with `body.model_copy(update={"purchase_order_id": purchase_order_id})`.

`exclude=True` only affects `model_dump`/serialization. It does nothing to
the request schema FastAPI builds from the same class for the OpenAPI docs,
so `purchase_order_id` still showed up in Swagger as an optional body field
on a route where the id is also, redundantly, a path parameter — one real
value with two conflicting entry points, and a client who filled in the
body one would have it silently overwritten by the router regardless.

## The rule

1. Split the `Command` in two. `XCommandPayload(CamelModel)` holds exactly
   the fields the client sends — this is the class the router's `body:`
   parameter is typed as. `XCommand(XCommandPayload, Command[TResult])`
   adds the path segment(s), as plain required fields (`purchase_order_id:
   UUID`, not `UUID | None = Field(default=None, exclude=True)`) — this is
   the class the handler receives.
2. The router builds `XCommand` explicitly, once, from both sources:
   ```python
   return await handler.handle(
       PricePurchaseOrderLineCommand(
           **body.model_dump(exclude_unset=True),
           purchase_order_id=purchase_order_id,
           line_id=line_id,
       )
   )
   ```
   `exclude_unset=True` is not optional here — a handler that reads
   `request.model_fields_set` for partial-update semantics (`update_product.py`'s
   `"barcode" in sent`) needs that set to reflect what the *client* actually
   sent, not every field the payload happens to have a value for.
3. **A route whose body would be empty once the path id is removed
   (`ConfirmPurchaseOrderCommand`, `ConfirmGoodsReceiptCommand`,
   `UnscanReceiptUnitCommand`) gets no `Payload` class and no `body:`
   parameter at all.** The router builds the `Command` straight from the
   path:
   ```python
   @router.post("/{purchase_order_id}/confirm")
   async def confirm_purchase_order(
       purchase_order_id: UUID,
       current: FromDishka[CurrentUser],
       handler: FromDishka[ConfirmPurchaseOrderHandler],
   ) -> ResultWithData[PurchaseOrderData]:
       require(current, Permission.PURCHASE_ORDER_MANAGE)
       return await handler.handle(
           ConfirmPurchaseOrderCommand(purchase_order_id=purchase_order_id)
       )
   ```
   A route that still asked for a JSON body here, only to ignore its
   contents, would be worse than no `Payload` split at all.
4. Because the router always builds `XCommand` with every field supplied,
   the path field(s) need no default and no `Field(exclude=True)` — a plain
   required `UUID`/`str`. That removes the `assert request.x is not None`
   line every one of these handlers used to open with; `ty check` already
   knows the field can't be `None`.
5. A router check that used to run against `body.model_fields_set`
   (`goods_receipts.py`'s pricing-permission escalation,
   `products.py`'s `"default_sale_price" in body.model_fields_set`) stays
   exactly as it was, just against the now-`Payload`-typed `body` — nothing
   about that check changes, since the fields it inspects were never path
   segments to begin with.

## Where the `Payload` class lives

In the same module as its `Command`, immediately above it — this is a
request shape, not a response payload, so
`.claude/rules/backend/cqrs-response-models.md`'s "one payload class per
file under `application/models/`" does not apply here; nothing outside the
one command/router pair ever constructs a `Payload`.

## Example: full split

```python
class PricePurchaseOrderLineCommandPayload(CamelModel):
    unit_cost: str | int


class PricePurchaseOrderLineCommand(
    PricePurchaseOrderLineCommandPayload, Command[ResultWithData[PurchaseOrderData]]
):
    # URL path segments, filled in by the router — never sent by the client.
    purchase_order_id: UUID
    line_id: UUID
```

The handler's `handle()` still takes `PricePurchaseOrderLineCommand` — it
never sees the `Payload` type, and needs no `assert ... is not None` guard
on the path fields, since the router-constructed object always has them.
