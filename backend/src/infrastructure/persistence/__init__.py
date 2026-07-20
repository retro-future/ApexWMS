"""Persistence: SQLAlchemy models, repositories, and Alembic migrations.

Split by database (PRD §3.1): ``master/`` for the MasterDB schema,
``tenant/`` for the per-tenant schema. ORM models never escape the
repositories — repository signatures speak domain types only.
"""
