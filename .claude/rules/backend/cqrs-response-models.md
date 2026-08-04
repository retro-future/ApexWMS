---
paths:
  - "backend/src/application/commands/**/*.py"
  - "backend/src/application/queries/**/*.py"
  - "backend/src/application/models/**/*.py"
---

# A `TData` response payload lives in `application/models/`, not in the handler's module

A `ResultWithData[TData]`/`PagedResult[TData]` payload class — the shape a
handler hands back out, with its optional `from_<entity>()` mapping
classmethod — is defined in `application/models/`, one file per payload,
never inline in the command/query module that produces it.

## Why this is a separate rule from request shapes

A `Command`/`Query` **request** shape, including a request-only nested item
like `RepriceDeviceUnitsCommand`'s `UnitPrice`, stays in the operation's own
module — it's part of that one message, nothing else will ever construct
one. A **response** payload is different: it's routinely read by more than
the handler that first produced it (`LocationData` is returned by
`GetLocationHandler`, `CreateLocationHandler`, and `ListLocationsHandler`
alike), so leaving it in one of those three modules makes the other two
reach into a file that isn't really "theirs."

## Rules

1. One `CamelModel` response class per file under `application/models/`,
   filename matching the query/command module that originates it
   (`models/customer.py` for the class `get_customer.py`'s handler
   produces).
2. **Every payload class has exactly one classmethod factory, always named
   `from_entity`.** This holds even for a payload with no single natural
   source entity — `LoginData.from_entity(tokens, user, claims)` takes three
   arguments, `TenantSettingsData.from_entity(timezone)` takes a bare `str`,
   but the name is still `from_entity` in both cases. A handler never
   constructs a `TData` via inline keyword arguments
   (`XData(field=..., other=...)`) in its `handle()` — always
   `XData.from_entity(...)`.
3. The one classmethod's *arity* is honest to what the payload actually
   needs — unify the name, not a fake single-argument shape. `DeviceUnitData.from_entity(unit, product, *, show_cost)`
   and `PriceChangeData.from_entity(change)` (a `ProductPriceChange |
   DeviceUnitPriceChange` union) are both correct as they stand; forcing
   every payload's mapper to take exactly one entity would misrepresent
   payloads that are genuinely built from more than one source.
4. Mapping logic stays **on the payload class** — it is still
   `application`'s job (never `domain`'s), it just lives with the class it
   builds rather than the handler that happens to call it.
5. `application/models/__init__.py` re-exports every payload class,
   alphabetized, mirroring `application/dtos/__init__.py`'s format.
6. Not `application/dtos/` — that package is reserved for frozen-dataclass
   DI-context carriers (`CurrentUser`, `IssuedClaims`) that never cross an
   HTTP wire. A wire-format Pydantic response payload is a different kind of
   object with a different job; see `application/dtos/__init__.py`'s
   docstring for the full distinction.

## Example: what this looks like in practice

Before, `application/queries/get_customer.py` defined both the query and
its payload in one file:

```python
class CustomerData(CamelModel):
    id: UUID
    full_name: str
    phone: str | None
    is_active: bool

    @classmethod
    def from_customer(cls, customer: Customer) -> CustomerData: ...


class GetCustomerQuery(Query[ResultWithData[CustomerData]]):
    customer_id: UUID


class GetCustomerHandler(...): ...
```

`CustomerData` moved to `application/models/customer.py`, and its mapper was
renamed to the required `from_entity`:

```python
# application/models/customer.py
class CustomerData(CamelModel):
    id: UUID
    full_name: str
    phone: str | None
    is_active: bool

    @classmethod
    def from_entity(cls, customer: Customer) -> CustomerData: ...
```

```python
# application/queries/get_customer.py
from application.models import CustomerData

class GetCustomerQuery(Query[ResultWithData[CustomerData]]):
    customer_id: UUID

class GetCustomerHandler(...): ...
```

`list_customers.py`, `create_customer.py`, and `update_customer.py` all
import `CustomerData` from `application.models` and call
`CustomerData.from_entity(...)` the same way — none of them reaches into
`get_customer.py` for a class that isn't really about "getting one
customer" anymore, and none of them builds one via raw kwargs instead.

See also `.claude/rules/backend/handler-helpers.md` for the companion rule
about where a handler's *helper logic* belongs.
