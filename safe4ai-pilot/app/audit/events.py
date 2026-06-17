"""Helper for emitting workspace/security audit events.

Centralizes the append-only ``AuditLog`` write for events that aren't chat
queries (workspace lifecycle, membership changes, SAML provisioning, denied
cross-workspace access). Action-type strings are classified by ``kinds.py``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog

# Canonical action_type values (kept here so call sites don't drift on spelling).
WORKSPACE_CREATED = "workspace_created"
WORKSPACE_MEMBERSHIP_GRANTED = "workspace_membership_granted"
WORKSPACE_MEMBERSHIP_REVOKED = "workspace_membership_revoked"
WORKSPACE_ROLE_CHANGED = "workspace_role_changed"
WORKSPACE_ACCESS_DENIED = "workspace_access_denied"
SAML_PROVISIONED = "saml_provisioned"


def record_audit_event(
    db: Session,
    *,
    action_type: str,
    user_id: str | None = None,
    workspace_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    """Append an audit row for a non-chat event."""
    db.add(
        AuditLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            workspace_id=workspace_id,
            action_type=action_type,
            response_metadata=metadata or {},
        )
    )
    if commit:
        db.commit()
