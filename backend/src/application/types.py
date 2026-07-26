"""NewType aliases for values resolved at the edge and handed to handlers.

Plain ``UUID``/``timedelta`` parameters are indistinguishable to the DI
container, which is what forces a hand-written factory instead of
``provide_all`` (di/providers/handlers.py). Wrapping each in its own
``NewType`` gives it a distinct identity in the container, matching the
pattern ``infrastructure/types.py`` already uses for engines/sessions —
these live here, not there, because unlike a database session a handler's
own constructor is typed with them directly, and ``application/`` may not
import ``infrastructure/``.
"""

from datetime import timedelta
from typing import NewType
from uuid import UUID

# The tenant resolved at the edge (PRD §3.3), for the few collaborators that
# must stamp it into something — currently ``InviteUserHandler``.
ResolvedTenantId = NewType("ResolvedTenantId", UUID)

RefreshTokenTtl = NewType("RefreshTokenTtl", timedelta)
InviteTtl = NewType("InviteTtl", timedelta)
