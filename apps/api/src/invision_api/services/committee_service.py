"""
Future committee-side orchestration.

Candidate-facing endpoints must not call these helpers without proper authorization.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session


def query_applications_for_review(
    db: Session,
    *,
    stage: str | None = None,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Placeholder query surface for committee dashboards.
    Implemented as a thin filter over `applications` to keep indexes useful later.
    """
    from sqlalchemy import select

    from invision_api.models.application import Application

    stmt = select(Application)
    if stage:
        stmt = stmt.where(Application.current_stage == stage)
    if state:
        stmt = stmt.where(Application.state == state)
    stmt = stmt.order_by(Application.updated_at.desc()).limit(limit).offset(offset)
    rows = db.scalars(stmt).all()
    return [{"id": str(a.id), "state": a.state, "current_stage": a.current_stage} for a in rows]
