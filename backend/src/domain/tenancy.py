"""Tenant lifecycle (PRD §3.2, §3.4).

Provisioning is a state machine on the tenant row:

    PENDING → PROVISIONING → ACTIVE | FAILED

A tenant is unusable until ACTIVE. FAILED provisioning is retryable —
every provisioning step is idempotent.
"""

from enum import StrEnum


class TenantStatus(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
