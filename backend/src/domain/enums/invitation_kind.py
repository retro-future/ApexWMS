"""Which shape an ``Invitation`` row takes (FR-1.5).

* ``EMPLOYEE`` — ``tenant_id`` and ``tenant_role`` set. Acceptance creates
  a User *and* an Employee in that store's database.
* ``APP_USER`` — both null, ``app_role`` set. Acceptance creates a
  platform operator; no tenant database is touched at all.
"""

from enum import StrEnum


class InvitationKind(StrEnum):
    EMPLOYEE = "employee"
    APP_USER = "app_user"
