---
paths:
  - "backend/src/**/*.py"
---

# Exceptions are raised by the code that owns the rule, never by a provider

`application/errors.py`'s `ApplicationError` subclasses (`AuthenticationError`,
`AuthorizationError`, `TenantNotActiveError`, `MissingTenantError`,
`TenantNotFoundError`, ...) represent business/use-case failures. Each one
must be raised from the service, use case, or domain-adjacent helper that
actually evaluates the rule being violated — never from a `di/providers/*`
`@provide` method, and never from DI wiring code in general.

## Why

A provider's job is to answer "how do I build a `T`", resolved once per
scope by the container. Putting a `raise` inside that resolution step
conflates *object construction* with *business validation* — the same
conflation `providers.md` forbids for plain logic, just via control flow
instead of a branch. It also makes the rule impossible to unit-test without
standing up the container, whereas a plain service class (like
`CurrentTenantAccessor` or `CurrentUserAccessor`) can be constructed and
tested directly with fakes.

## Where exceptions live instead

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
  `InvitationError`, `SlugAlreadyTakenError`): raised from the `IRequestHandler`
  in `application/commands/`/`application/queries/` that owns the rule,
  inside its `__call__` — this guidance does not change how handlers already
  behave, only how the DI edge (providers) is required to behave.

The provider that ultimately depends on one of these services (directly or
transitively) does not catch, wrap, or re-raise anything — the exception
propagates up through the container resolution and is mapped to an HTTP
status by the presentation layer, same as any exception raised inside a
handler's `__call__`.
