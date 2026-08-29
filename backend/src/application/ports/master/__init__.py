"""Ports over the MasterDB: its unit of work. The aggregates that used to
live here have moved to the generic ``MasterDbRepository`` reached through
a ``Specification`` (ADR 0007)."""

from application.ports.master.uow import MasterUnitOfWork

__all__ = ["MasterUnitOfWork"]
