from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, Notification
from invision_api.models.enums import ApplicationState, DocumentType, SectionKey
from invision_api.models.user import User
from invision_api.repositories import document_repository
from invision_api.repositories.application_repository import get_application_for_candidate, get_candidate_profile_by_user
from invision_api.services import application_service


STAGE_DESCRIPTIONS: dict[str, str] = {
    "application": "Заполните и отправьте материалы заявления.",
    "initial_screening": "Проверяем соответствие требованиям и полноту данных.",
    "application_review": "Оцениваются учебные достижения и сопроводительные материалы.",
    "interview": "При необходимости вас пригласят на собеседование.",
    "committee_review": "Приёмная комиссия рассматривает заявление. Итоговые решения принимают люди.",
    "decision": "Вы получите решение по зачислению.",
}


def build_dashboard(db: Session, user: User) -> dict[str, Any]:
    profile = get_candidate_profile_by_user(db, user.id)
    if not profile:
        return {"error": "no_profile"}

    app = get_application_for_candidate(db, profile.id)
    if not app:
        return {"error": "no_application"}

    pct, missing = application_service.completion_percentage(db, app)
    docs = document_repository.list_documents_for_application(db, app.id)
    doc_summary: dict[str, int] = {dt.value: 0 for dt in DocumentType}
    for d in docs:
        doc_summary[d.document_type] = doc_summary.get(d.document_type, 0) + 1

    missing_items: list[str] = []
    for m in missing:
        missing_items.append(f"section:{m.value}")
    if SectionKey.social_status_cert in missing and not document_repository.has_document_type(
        db, app.id, DocumentType.certificate_of_social_status.value
    ):
        missing_items.append("document:certificate_of_social_status")

    recent = _recent_updates(db, user.id, app.id)

    return {
        "candidate_name": f"{profile.first_name} {profile.last_name}".strip(),
        "application_id": str(app.id),
        "application_state": app.state,
        "current_stage": app.current_stage,
        "completion_percentage": pct,
        "stage_timeline": _timeline_summary(app),
        "document_summary": doc_summary,
        "missing_items": missing_items,
        "recent_updates": recent,
    }


def _timeline_summary(app: Application) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for h in sorted(app.stage_history, key=lambda x: x.entered_at):
        out.append(
            {
                "from_stage": h.from_stage,
                "to_stage": h.to_stage,
                "entered_at": h.entered_at.isoformat(),
                "candidate_visible_note": h.candidate_visible_note,
            }
        )
    return out


def _recent_updates(db: Session, user_id: UUID, application_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    app = db.get(Application, application_id)
    if app:
        for h in sorted(app.stage_history, key=lambda x: x.entered_at, reverse=True)[:limit]:
            if h.candidate_visible_note:
                notes.append(
                    {
                        "kind": "stage_history",
                        "at": h.entered_at.isoformat(),
                        "message": h.candidate_visible_note,
                    }
                )

    notifs = list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).all()
    )
    for n in notifs:
        notes.append(
            {
                "kind": "notification",
                "at": n.created_at.isoformat(),
                "message": n.template_key,
                "status": n.status,
            }
        )
    notes.sort(key=lambda x: x["at"], reverse=True)
    return notes[:limit]


def build_status(db: Session, user: User) -> dict[str, Any]:
    profile = get_candidate_profile_by_user(db, user.id)
    if not profile:
        raise ValueError("no profile")
    app = get_application_for_candidate(db, profile.id)
    if not app:
        raise ValueError("no application")

    history = []
    for h in sorted(app.stage_history, key=lambda x: x.entered_at):
        history.append(
            {
                "from_stage": h.from_stage,
                "to_stage": h.to_stage,
                "entered_at": h.entered_at.isoformat(),
                "exited_at": h.exited_at.isoformat() if h.exited_at else None,
                "candidate_visible_note": h.candidate_visible_note,
            }
        )

    return {
        "current_stage": app.current_stage,
        "submission_state": {
            "state": app.state,
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
            "locked": app.locked_after_submit,
        },
        "stage_history": history,
        "stage_descriptions": STAGE_DESCRIPTIONS,
    }
