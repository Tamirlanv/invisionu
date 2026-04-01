from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.commission import CommissionUser
from invision_api.services import audit_log_service


def write_event(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    actor_user_id: UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    role: str | None = None
    if actor_user_id is not None:
        row = db.get(CommissionUser, actor_user_id)
        role = row.role if row else None
    payload_after = dict(after or {})
    if metadata:
        payload_after["metadata"] = metadata
    if role:
        payload_after["actor_commission_role"] = role
    audit_log_service.write_audit(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action=event_type,
        actor_user_id=actor_user_id,
        before_data=before,
        after_data=payload_after or None,
    )

