"""Append-only audit trail logger for authentication, assessments, and system actions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from satbhoomi.db.models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    user_id: int | None,
    event: str,
    entity: str,
    entity_id: int,
    at: datetime | None = None,
) -> AuditLog:
    """Record an append-only audit event in the database.

    Privacy and security invariant: Never write raw passwords, tokens, hashes,
    or unregistered usernames (user_id must be None for non-existent users).
    """
    timestamp = at or datetime.now(UTC)
    entry = AuditLog(
        user_id=user_id,
        event=event,
        entity=entity,
        entity_id=entity_id,
        at=timestamp,
    )
    db.add(entry)
    db.flush()
    return entry
