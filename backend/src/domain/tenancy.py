"""Tenant lifecycle (PRD §3.2, §3.4).

Provisioning is a state machine on the tenant row:

    PENDING → PROVISIONING → ACTIVE | FAILED

A tenant is unusable until ACTIVE. FAILED provisioning is retryable —
every provisioning step is idempotent.

SUSPENDED is not part of that machine: it is an operator decision (unpaid
subscription, abuse) that a SuperAdmin makes on an already-ACTIVE tenant
and can reverse. Its database and data are untouched; only access stops.
"""

from enum import StrEnum


class TenantStatus(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    FAILED = "failed"
    SUSPENDED = "suspended"
