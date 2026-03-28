from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import (
    Application,
    ApplicationSectionState,
    ApplicationStageHistory,
    CandidateProfile,
    EducationRecord,
)
from invision_api.models.enums import (
    ApplicationStage,
    ApplicationState,
    DocumentType,
    SectionKey,
    StageActorType,
)
from invision_api.models.user import User
from invision_api.repositories import document_repository, internal_test_repository
from invision_api.repositories.application_repository import (
    get_application_for_candidate,
    get_candidate_profile_by_user,
)
from invision_api.services import section_payloads


def _dt_from_date(d: date | None) -> datetime | None:
    if d is None:
        return None
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def get_profile_and_application(db: Session, user: User) -> tuple[CandidateProfile, Application]:
    profile = get_candidate_profile_by_user(db, user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль абитуриента не найден")
    app = get_application_for_candidate(db, profile.id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявление не найдено")
    return profile, app


def _ensure_editable(app: Application) -> None:
    if app.locked_after_submit:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="После отправки заявление недоступно для редактирования")


def _internal_test_complete(db: Session, application_id: UUID) -> bool:
    total = internal_test_repository.count_active_questions(db)
    if total == 0:
        return False
    finalized = internal_test_repository.count_finalized_answers_for_application(db, application_id)
    return finalized >= total


def _social_status_complete(db: Session, application_id: UUID) -> bool:
    return document_repository.has_document_type(
        db,
        application_id,
        DocumentType.certificate_of_social_status.value,
    )


def compute_section_complete(
    db: Session,
    app: Application,
    section_key: SectionKey,
    validated: BaseModel,
) -> bool:
    match section_key:
        case SectionKey.personal | SectionKey.contact:
            return True
        case SectionKey.education:
            edu = validated if isinstance(validated, section_payloads.EducationSectionPayload) else None
            return bool(edu and len(edu.entries) >= 1)
        case SectionKey.internal_test:
            return _internal_test_complete(db, app.id)
        case SectionKey.social_status_cert:
            if not isinstance(validated, section_payloads.SocialStatusSectionPayload):
                return False
            return _social_status_complete(db, app.id)
    return False


def upsert_section_state(
    db: Session,
    app: Application,
    section_key: SectionKey,
    payload: dict[str, Any],
    is_complete: bool,
) -> ApplicationSectionState:
    now = datetime.now(tz=UTC)
    row = db.scalars(
        select(ApplicationSectionState).where(
            ApplicationSectionState.application_id == app.id,
            ApplicationSectionState.section_key == section_key.value,
        )
    ).first()
    if row:
        row.payload = payload
        row.is_complete = is_complete
        row.last_saved_at = now
        return row
    row = ApplicationSectionState(
        application_id=app.id,
        section_key=section_key.value,
        payload=payload,
        is_complete=is_complete,
        schema_version=1,
        last_saved_at=now,
    )
    db.add(row)
    return row


def sync_education_records(db: Session, app: Application, validated: section_payloads.EducationSectionPayload) -> None:
    for row in list(app.education_records):
        db.delete(row)
    db.flush()
    for e in validated.entries:
        db.add(
            EducationRecord(
                application_id=app.id,
                institution_name=e.institution_name,
                degree_or_program=e.degree_or_program,
                field_of_study=e.field_of_study,
                start_date=_dt_from_date(e.start_date),
                end_date=_dt_from_date(e.end_date),
                is_current=e.is_current,
            )
        )


def save_section(
    db: Session,
    user: User,
    section_key: SectionKey,
    payload: dict[str, Any],
) -> ApplicationSectionState:
    profile, app = get_profile_and_application(db, user)
    _ensure_editable(app)

    validated = section_payloads.parse_and_validate_section(section_key, payload)

    if section_key == SectionKey.personal:
        p = validated if isinstance(validated, section_payloads.PersonalSectionPayload) else None
        if not p:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Личные данные»")
        profile.first_name = p.preferred_first_name
        profile.last_name = p.preferred_last_name
        out_payload = p.model_dump(mode="json")
    elif section_key == SectionKey.contact:
        c = validated if isinstance(validated, section_payloads.ContactSectionPayload) else None
        if not c:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Контакты»")
        out_payload = c.model_dump(mode="json")
    elif section_key == SectionKey.education:
        e = validated if isinstance(validated, section_payloads.EducationSectionPayload) else None
        if not e:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Образование»")
        sync_education_records(db, app, e)
        out_payload = e.model_dump(mode="json")
    elif section_key == SectionKey.internal_test:
        it = validated if isinstance(validated, section_payloads.InternalTestSectionPayload) else None
        if not it:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Внутренний тест»")
        out_payload = it.model_dump(mode="json")
    elif section_key == SectionKey.social_status_cert:
        s = validated if isinstance(validated, section_payloads.SocialStatusSectionPayload) else None
        if not s:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Социальный статус»")
        out_payload = s.model_dump(mode="json")
    else:
        raise HTTPException(status_code=400, detail="Неизвестный раздел")

    is_complete = compute_section_complete(db, app, section_key, validated)

    row = upsert_section_state(db, app, section_key, out_payload, is_complete)

    if app.state == ApplicationState.draft.value:
        app.state = ApplicationState.in_progress.value

    db.commit()
    db.refresh(row)
    return row


REQUIRED_SECTIONS: list[SectionKey] = [
    SectionKey.personal,
    SectionKey.contact,
    SectionKey.education,
    SectionKey.internal_test,
    SectionKey.social_status_cert,
]


def completion_percentage(db: Session, app: Application) -> tuple[int, list[SectionKey]]:
    missing: list[SectionKey] = []
    for key in REQUIRED_SECTIONS:
        st = next((s for s in app.section_states if s.section_key == key.value), None)
        if not st or not st.is_complete:
            missing.append(key)
    total = len(REQUIRED_SECTIONS)
    done = total - len(missing)
    pct = int(round(100 * done / total)) if total else 0
    return pct, missing


def recompute_social_section(db: Session, app: Application) -> None:
    row = db.scalars(
        select(ApplicationSectionState).where(
            ApplicationSectionState.application_id == app.id,
            ApplicationSectionState.section_key == SectionKey.social_status_cert.value,
        )
    ).first()
    if not row:
        return
    try:
        validated = section_payloads.SocialStatusSectionPayload.model_validate(row.payload)
    except Exception:
        return
    row.is_complete = compute_section_complete(db, app, SectionKey.social_status_cert, validated)
    row.last_saved_at = datetime.now(tz=UTC)


def submit_application(db: Session, user: User) -> Application:
    if not user.email_verified_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Подтвердите email перед отправкой заявления",
        )
    profile = get_candidate_profile_by_user(db, user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль абитуриента не найден")
    app = get_application_for_candidate(db, profile.id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявление не найдено")
    _ensure_editable(app)

    _, missing = completion_percentage(db, app)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Не все разделы заполнены", "missing_sections": [m.value for m in missing]},
        )

    now = datetime.now(tz=UTC)
    last_open = db.scalars(
        select(ApplicationStageHistory)
        .where(ApplicationStageHistory.application_id == app.id, ApplicationStageHistory.exited_at.is_(None))
        .order_by(ApplicationStageHistory.entered_at.desc())
    ).first()
    if last_open:
        last_open.exited_at = now

    app.submitted_at = now
    app.state = ApplicationState.under_screening.value
    app.current_stage = ApplicationStage.initial_screening.value
    app.locked_after_submit = True

    db.add(
        ApplicationStageHistory(
            application_id=app.id,
            from_stage=ApplicationStage.application.value,
            to_stage=ApplicationStage.initial_screening.value,
            entered_at=now,
            actor_type=StageActorType.user.value,
            candidate_visible_note="Заявление отправлено и ожидает первичного рассмотрения.",
        )
    )
    db.commit()
    db.refresh(app)
    return app
