"""Stateless domain-layer collaborators (APP scope).

``UnitProjector`` has no constructor arguments and no per-request state, so
one instance serves the whole process, the same way ``PermissionEvaluator``
(``di/providers/authorization.py``) does for a domain class with
dependencies. ``provide_all`` needs no hand-written ``@provide`` here since
there is nothing to resolve.
"""

from dishka import Provider, Scope, provide_all

from domain.services import UnitProjector


class DomainServicesProvider(Provider):
    scope = Scope.APP

    services = provide_all(UnitProjector)
