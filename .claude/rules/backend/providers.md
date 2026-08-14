---
paths:
  - "backend/src/di/providers/**/*.py"
---

# Dishka providers must stay dumb

A `Provider` subclass in `di/providers/` exists to *construct and wire*
objects for the container. It is composition-root code, not business logic —
`di/` is "the only package allowed to import from every other layer"
(`docs/architecture/clean-architecture.md`), which makes it tempting to also
let it *do* things from every other layer. Don't.

## Rules

1. **A `@provide` method only constructs or delegates.** Fetch its
   dependencies from the container (constructor injection), pass them to a
   real class, return the result. It must not itself decode a token, query a
   database, evaluate a business rule, or otherwise reimplement what a
   service/use case would do.
2. **At most trivial, non-branching-on-business-rules logic is allowed** —
   e.g. `UUID(tenant.tenant_id)`, or a one-line unit conversion like
   `timedelta(days=settings.refresh_token_ttl_days)`. If you're reaching for
   an `if` that encodes a business rule (is this tenant active? does this
   user have access?), that `if` belongs in a service, not the provider.
3. **No private/static/classmethod helpers on a `Provider` subclass.** If a
   `@provide` method needs a multi-step helper, that's a sign the logic
   belongs in its own class in the appropriate layer (`application/` or
   `infrastructure/`), constructed via DI and injected as a dependency —
   never a `_helper` bolted onto the provider itself.
4. **Never raise `ApplicationError` (or any domain/application exception)
   from a provider.** `application/errors.py`'s `ApplicationError` subclasses
   (`AuthenticationError`, `AuthorizationError`, `TenantNotActiveError`,
   `MissingTenantError`, `TenantNotFoundError`, ...) represent business/use-case
   failures. Each one must be raised from the service, use case, or
   domain-adjacent helper that actually evaluates the rule being violated —
   never from a `di/providers/*` `@provide` method, and never from DI wiring
   code in general. A provider's job is to answer "how do I build a `T`",
   resolved once per scope by the container; putting a `raise` inside that
   resolution step conflates *object construction* with *business
   validation*, the same conflation rule 1 forbids for plain logic, just via
   control flow instead of a branch. It also makes the rule impossible to
   unit-test without standing up the container, whereas a plain service class
   (like `CurrentTenantAccessor` or `CurrentUserAccessor`) can be constructed
   and tested directly with fakes.

   Where these exceptions actually live instead:
   - **Identity**: `CurrentUserAccessor.get_current_user()`
     (`infrastructure/security/current_user_accessor.py`) raises
     `AuthenticationError` for a missing/absent bearer token.
   - **Tenant resolution**: `CurrentTenantAccessor`
     (`infrastructure/current_tenant_accessor.py`) raises
     `MissingTenantError`/`TenantNotFoundError`/`AuthorizationError`/
     `TenantNotActiveError` — see `docs/architecture/tenant-resolution.md`.
   - **Reaching a tenant DB mid-request**: `SqlTenantScope._resolve`
     (`infrastructure/tenant_scope.py`) raises `TenantNotActiveError` for a
     suspended/missing store, independently of the edge-resolution path above.
   - **Handler-level rules** (e.g. `LastOwnerError`, `AlreadyMemberError`,
     `InvitationError`, `SlugAlreadyTakenError`): raised from the
     `IRequestHandler` in `application/commands/`/`application/queries/` that
     owns the rule, inside its `__call__`.

   The provider that ultimately depends on one of these services (directly or
   transitively) does not catch, wrap, or re-raise anything — the exception
   propagates up through the container resolution and is mapped to an HTTP
   status by the presentation layer, same as any exception raised inside a
   handler's `__call__`.
5. **One provider module per concern**, not one giant provider. When a
   concern needs a dedicated resolution step (e.g. "which tenant is this
   request for"), give it its own service class and inject that service,
   rather than inlining the resolution across several `@provide` methods.

## Example: what this looks like in practice

`di/providers/tenant_db.py` used to have a `@staticmethod _resolve` that
queried MasterDB and raised `MissingTenantError`/`TenantNotFoundError`/
`AuthorizationError`/`TenantNotActiveError` — a direct violation of rules 1,
3, and 4. It now looks like this:

```python
class TenantDbProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def accessor(
        self, request: Request, session: MasterSession,
        settings: Settings, claims: RequestBearerClaims,
    ) -> CurrentTenantAccessor:
        return CurrentTenantAccessor(request, session, settings, claims)

    @provide(scope=Scope.REQUEST)
    async def tenant(self, accessor: CurrentTenantAccessor) -> TenantContext:
        return await accessor.get_current_tenant()
```

All the resolution logic and every raise lives in
`infrastructure/current_tenant_accessor.py`'s `CurrentTenantAccessor` — see
`docs/architecture/tenant-resolution.md` and rule 4 above. `di/providers/auth.py`'s
`AuthProvider` follows the identical shape via `CurrentUserAccessor`
(`infrastructure/security/current_user_accessor.py`).

## CQRS handlers: prefer `provide_all` over hand-written factories

When a `@provide` factory method exists *only* to forward constructor
arguments (no derived values, no conditionals), it's pure boilerplate —
replace it with dishka's `provide_all`, which resolves the class's `__init__`
by reflecting on its type hints:

```python
class HandlersProvider(Provider):
    scope = Scope.REQUEST
    handlers = provide_all(
        ClaimsFactory, TokenIssuer, LoginHandler, RefreshTokensHandler,
        ChangePasswordHandler, InviteUserHandler, AcceptInviteHandler,
        GetMeHandler, ListUsersHandler, ChangeUserRoleHandler,
        GetTenantSettingsHandler, UpdateTenantSettingsHandler,
    )
```

This only works if every constructor parameter's type is itself
DI-resolvable and unambiguous — a bare `timedelta` or `UUID` parameter that a
human factory used to fill in from `Settings` must become a distinct
`NewType` (see `application/types.py`) so the container can tell it apart
from any other `timedelta`/`UUID` in the graph. Add the derived value's
provider (a trivial one-line conversion, rule 2) to `di/providers/config.py`
rather than hand-writing a factory for the handler that consumes it.
