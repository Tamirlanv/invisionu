from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from invision_api.api.deps import require_roles
from invision_api.db.session import get_db
from invision_api.models.enums import RoleName, SectionKey
from invision_api.models.user import User
from invision_api.repositories.application_repository import get_application_for_candidate, get_candidate_profile_by_user
from invision_api.repositories import document_repository
from invision_api.services import application_service, dashboard_service
from invision_api.services.application_service import REQUIRED_SECTIONS

router = APIRouter()


class SectionPatchBody(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


@router.get("/me/dashboard-summary")
def dashboard_summary(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    data = dashboard_service.build_dashboard(db, user)
    if data.get("error"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Панель недоступна")
    return data


@router.get("/me/application/status")
def application_status(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return dashboard_service.build_status(db, user)
    except ValueError:
        raise HTTPException(status_code=404, detail="Не найдено")


@router.get("/me/application")
def get_application(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    profile = get_candidate_profile_by_user(db, user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    app = get_application_for_candidate(db, profile.id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")

    sections = {s.section_key: {"payload": s.payload, "is_complete": s.is_complete} for s in app.section_states}
    pct, missing = application_service.completion_percentage(db, app)
    return {
        "application": {
            "id": str(app.id),
            "state": app.state,
            "current_stage": app.current_stage,
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
            "locked_after_submit": app.locked_after_submit,
        },
        "sections": sections,
        "education_records": [
            {
                "id": str(er.id),
                "institution_name": er.institution_name,
                "degree_or_program": er.degree_or_program,
                "field_of_study": er.field_of_study,
                "start_date": er.start_date.isoformat() if er.start_date else None,
                "end_date": er.end_date.isoformat() if er.end_date else None,
                "is_current": er.is_current,
            }
            for er in app.education_records
        ],
        "completion_percentage": pct,
        "missing_sections": [m.value for m in missing],
    }


@router.get("/me/application/review")
def review_application(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    profile = get_candidate_profile_by_user(db, user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    app = get_application_for_candidate(db, profile.id)
    if not app:
        raise HTTPException(status_code=404, detail="Заявление не найдено")

    pct, missing = application_service.completion_percentage(db, app)
    docs = document_repository.list_documents_for_application(db, app.id)
    return {
        "application_id": str(app.id),
        "state": app.state,
        "current_stage": app.current_stage,
        "locked": app.locked_after_submit,
        "completion_percentage": pct,
        "missing_sections": [m.value for m in missing],
        "sections": {
            s.section_key: {"is_complete": s.is_complete, "payload": s.payload}
            for s in app.section_states
        },
        "documents": [
            {
                "id": str(d.id),
                "document_type": d.document_type,
                "original_filename": d.original_filename,
                "mime_type": d.mime_type,
                "byte_size": d.byte_size,
                "verification_status": d.verification_status,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
        "required_sections": [k.value for k in REQUIRED_SECTIONS],
    }


@router.patch("/me/application/sections/{section_key}")
def patch_section(
    section_key: str,
    body: SectionPatchBody,
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        key = SectionKey(section_key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неизвестный раздел")
    row = application_service.save_section(db, user, key, body.payload)
    return {
        "section_key": row.section_key,
        "is_complete": row.is_complete,
        "payload": row.payload,
        "last_saved_at": row.last_saved_at.isoformat(),
    }


@router.post("/me/application/submit")
def submit(
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    app = application_service.submit_application(db, user)
    return {
        "application_id": str(app.id),
        "state": app.state,
        "current_stage": app.current_stage,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "locked_after_submit": app.locked_after_submit,
    }
