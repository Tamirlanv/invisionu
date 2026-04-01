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
    Document,
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
from invision_api.services.growth_path.pipeline import process_growth_journey_save


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


DOCUMENTS_MANIFEST_REQUIRED_TYPES: list[str] = [
    DocumentType.transcript.value,
    DocumentType.portfolio.value,
    DocumentType.essay.value,
    DocumentType.certificate_of_social_status.value,
]


def _documents_manifest_complete(db: Session, application_id: UUID, validated: section_payloads.DocumentsManifestSectionPayload) -> bool:
    if not validated.acknowledged_required_documents:
        return False
    return document_repository.has_all_document_types(db, application_id, DOCUMENTS_MANIFEST_REQUIRED_TYPES)


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
            if not edu:
                return False
            if len(edu.entries) >= 1:
                return True
            return bool(
                (edu.presentation_video_url or "").strip()
                and edu.english_proof_kind
                and edu.certificate_proof_kind
            )
        case SectionKey.achievements_activities:
            a = validated if isinstance(validated, section_payloads.AchievementsActivitiesSectionPayload) else None
            return bool(a and len(a.achievements_text.strip()) >= 250)
        case SectionKey.leadership_evidence:
            l = validated if isinstance(validated, section_payloads.LeadershipEvidenceSectionPayload) else None
            return bool(l and len(l.items) >= 1)
        case SectionKey.motivation_goals:
            return isinstance(validated, section_payloads.MotivationGoalsSectionPayload)
        case SectionKey.growth_journey:
            g = validated if isinstance(validated, section_payloads.GrowthJourneySectionPayload) else None
            return bool(g and section_payloads.growth_journey_section_complete(g))
        case SectionKey.internal_test:
            return _internal_test_complete(db, app.id)
        case SectionKey.social_status_cert:
            if not isinstance(validated, section_payloads.SocialStatusSectionPayload):
                return False
            return _social_status_complete(db, app.id)
        case SectionKey.documents_manifest:
            return (
                isinstance(validated, section_payloads.DocumentsManifestSectionPayload)
                and _documents_manifest_complete(db, app.id, validated)
            )
        case SectionKey.consent_agreement:
            c = validated if isinstance(validated, section_payloads.ConsentAgreementSectionPayload) else None
            return bool(
                c
                and c.accepted_terms
                and c.accepted_privacy
                and bool(c.consent_policy_version.strip())
            )
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


def _validate_leadership_documents(db: Session, application_id: UUID, payload: section_payloads.LeadershipEvidenceSectionPayload) -> None:
    for item in payload.items:
        for did in item.supporting_document_ids:
            if not document_repository.document_belongs_to_application(db, did, application_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Документ {did} не принадлежит этому заявлению",
                )


def _validate_optional_motivation_growth_doc(
    db: Session,
    application_id: UUID,
    document_id: UUID | None,
    expected_type: str,
) -> None:
    if document_id is None:
        return
    if not document_repository.document_belongs_to_application(db, document_id, application_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректная ссылка на документ")
    row = db.scalars(select(Document).where(Document.id == document_id, Document.application_id == application_id)).first()
    if not row or row.document_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Документ должен иметь тип {expected_type}",
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
        _validate_optional_motivation_growth_doc(
            db, app.id, p.identity_document_id, DocumentType.supporting_documents.value
        )
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
    elif section_key == SectionKey.achievements_activities:
        a = validated if isinstance(validated, section_payloads.AchievementsActivitiesSectionPayload) else None
        if not a:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Достижения»")
        out_payload = a.model_dump(mode="json")
    elif section_key == SectionKey.leadership_evidence:
        l = validated if isinstance(validated, section_payloads.LeadershipEvidenceSectionPayload) else None
        if not l:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Лидерство»")
        _validate_leadership_documents(db, app.id, l)
        out_payload = l.model_dump(mode="json")
    elif section_key == SectionKey.motivation_goals:
        m = validated if isinstance(validated, section_payloads.MotivationGoalsSectionPayload) else None
        if not m:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Мотивация»")
        _validate_optional_motivation_growth_doc(
            db, app.id, m.motivation_document_id, DocumentType.motivation_upload.value
        )
        out_payload = m.model_dump(mode="json")
    elif section_key == SectionKey.growth_journey:
        g = validated if isinstance(validated, section_payloads.GrowthJourneySectionPayload) else None
        if not g:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Путь»")
        _validate_optional_motivation_growth_doc(
            db, app.id, g.growth_document_id, DocumentType.growth_journey_upload.value
        )
        computed = process_growth_journey_save(db, app.id, g)
        out_payload = g.model_dump(mode="json")
        out_payload["computed"] = computed
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
    elif section_key == SectionKey.documents_manifest:
        d = validated if isinstance(validated, section_payloads.DocumentsManifestSectionPayload) else None
        if not d:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Документы»")
        out_payload = d.model_dump(mode="json")
    elif section_key == SectionKey.consent_agreement:
        co = validated if isinstance(validated, section_payloads.ConsentAgreementSectionPayload) else None
        if not co:
            raise HTTPException(status_code=400, detail="Некорректные данные раздела «Согласие»")
        out_payload = co.model_dump(mode="json")
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
    SectionKey.achievements_activities,
    SectionKey.leadership_evidence,
    SectionKey.motivation_goals,
    SectionKey.growth_journey,
    SectionKey.internal_test,
    SectionKey.social_status_cert,
    SectionKey.documents_manifest,
    SectionKey.consent_agreement,
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


def recompute_documents_manifest_section(db: Session, app: Application) -> None:
    row = db.scalars(
        select(ApplicationSectionState).where(
            ApplicationSectionState.application_id == app.id,
            ApplicationSectionState.section_key == SectionKey.documents_manifest.value,
        )
    ).first()
    if not row:
        return
    try:
        validated = section_payloads.DocumentsManifestSectionPayload.model_validate(row.payload)
    except Exception:
        return
    row.is_complete = compute_section_complete(db, app, SectionKey.documents_manifest, validated)
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
    from invision_api.services.stages import initial_screening_service

    initial_screening_service.enqueue_post_submit_jobs(db, app.id)

    from invision_api.repositories import commission_repository

    commission_repository.upsert_projection_for_application(db, app)

    from invision_api.services import audit_log_service

    audit_log_service.write_audit(
        db,
        entity_type="application",
        entity_id=app.id,
        action="application_submitted",
        actor_user_id=user.id,
        before_data={"state": "in_progress", "current_stage": "application"},
        after_data={
            "state": app.state,
            "current_stage": app.current_stage,
            "submitted_at": app.submitted_at.isoformat(),
        },
    )

    db.commit()
    db.refresh(app)

    try:
        from invision_api.services import validation_trigger_service
        validation_trigger_service.trigger_validation_run(
            application_id=app.id,
            candidate_id=profile.id,
        )
    except Exception:
        pass

    return app
