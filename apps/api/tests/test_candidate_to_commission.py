"""Pipeline test: full flow from candidate creation to commission visibility."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Application, ApplicationStageHistory, AuditLog, Document
from invision_api.models.commission import ApplicationCommissionProjection
from invision_api.models.enums import ApplicationStage, ApplicationState, DocumentType, SectionKey
from invision_api.repositories.commission_repository import (
    list_projections,
    upsert_projection_for_application,
)
from invision_api.services.application_service import (
    save_section,
    submit_application,
    completion_percentage,
)


def _mock_post_submit():
    """Disable Redis-dependent post-submit jobs."""
    import invision_api.services.stages.initial_screening_service as iss
    original = iss.enqueue_post_submit_jobs
    iss.enqueue_post_submit_jobs = lambda db, app_id, **_kwargs: None
    return original


def _seed_required_documents(db: Session, app_id):
    """Create required document types so documents_manifest and social_status pass completion."""
    for dtype in [
        DocumentType.transcript.value,
        DocumentType.portfolio.value,
        DocumentType.essay.value,
        DocumentType.certificate_of_social_status.value,
    ]:
        db.add(Document(
            id=uuid4(),
            application_id=app_id,
            original_filename=f"{dtype}.pdf",
            mime_type="application/pdf",
            byte_size=1024,
            storage_key=f"uploads/{dtype}.pdf",
            document_type=dtype,
        ))
    db.flush()


def _seed_supporting_document(db: Session, app_id):
    doc = Document(
        id=uuid4(),
        application_id=app_id,
        original_filename="id.pdf",
        mime_type="application/pdf",
        byte_size=1024,
        storage_key="uploads/id.pdf",
        document_type=DocumentType.supporting_documents.value,
    )
    db.add(doc)
    db.flush()
    return doc


def _seed_internal_test(db: Session, app_id):
    """Seed internal test questions and finalized answers so internal_test passes completion."""
    from invision_api.repositories import internal_test_repository
    total = internal_test_repository.count_active_questions(db)
    if total == 0:
        return
    from invision_api.models.application import ApplicationSectionState
    from datetime import UTC, datetime
    row = db.query(ApplicationSectionState).filter(
        ApplicationSectionState.application_id == app_id,
        ApplicationSectionState.section_key == SectionKey.internal_test.value,
    ).first()
    if row:
        row.is_complete = True
        row.last_saved_at = datetime.now(tz=UTC)


def test_full_candidate_to_commission_pipeline(db: Session, factory, monkeypatch):
    """
    End-to-end pipeline:
    1. Create candidate + application
    2. Fill all required sections via save_section (where feasible) + factory helpers
    3. Verify completion is 100%
    4. Submit application
    5. Verify state changes (locked, under_screening, submitted_at)
    6. Verify projection is created on commission side
    7. Verify audit log entry exists
    8. Verify stage history has submit transition
    """
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user, first_name="Марат", last_name="Исмаилов")
    app = factory.application(db, profile, state="draft")
    db.flush()
    identity_doc = _seed_supporting_document(db, app.id)

    save_section(db, user, SectionKey.personal, {
        "preferred_first_name": "Марат",
        "preferred_last_name": "Исмаилов",
        "date_of_birth": "2007-01-01",
        "document_type": "id",
        "citizenship": "KZ",
        "iin": "070101500001",
        "document_number": "123456789",
        "document_issue_date": "2024-01-01",
        "document_issued_by": "МВД РК",
        "father_last": "Исмаилов",
        "father_first": "Петр",
        "father_phone": "+77011234567",
        "mother_last": "Исмаилова",
        "mother_first": "Мария",
        "mother_phone": "+77017654321",
        "consent_privacy": True,
        "consent_age": True,
        "identity_document_id": str(identity_doc.id),
    })
    save_section(db, user, SectionKey.contact, {
        "phone_e164": "+77017654321",
        "region": "Алматинская область",
        "street": "Абая",
        "house": "10",
        "apartment": "25",
        "address_line1": "ул. Абая 10",
        "city": "Алматы",
        "country": "KZ",
        "telegram": "@marat",
        "consent_privacy": True,
        "consent_parent": True,
    })
    save_section(db, user, SectionKey.education, {
        "entries": [{"institution_name": "НИШ", "is_current": True}],
        "presentation_video_url": "https://youtube.com/watch?v=abc",
        "english_proof_kind": "ielts_6",
        "certificate_proof_kind": "ent",
    })
    save_section(db, user, SectionKey.achievements_activities, {
        "achievements_text": "A" * 260,
        "role": "Участник",
        "year": "2025",
        "links": [],
        "consent_privacy": True,
        "consent_parent": True,
    })
    save_section(db, user, SectionKey.leadership_evidence, {
        "items": [{"title": "Президент школьного совета"}],
    })
    save_section(db, user, SectionKey.motivation_goals, {
        "narrative": "A" * 350,
    })
    save_section(db, user, SectionKey.growth_journey, {
        "answers": {
            "q1": {"text": "x" * 250},
            "q2": {"text": "x" * 200},
            "q3": {"text": "x" * 200},
            "q4": {"text": "x" * 200},
            "q5": {"text": "x" * 150},
        },
        "consent_privacy": True,
        "consent_parent": True,
    })
    save_section(db, user, SectionKey.consent_agreement, {
        "accepted_terms": True,
        "accepted_privacy": True,
        "consent_policy_version": "v1.0",
    })

    _seed_required_documents(db, app.id)

    save_section(db, user, SectionKey.social_status_cert, {
        "attestation": "Подтверждаю социальный статус данного документа",
    })
    save_section(db, user, SectionKey.documents_manifest, {
        "acknowledged_required_documents": True,
    })

    save_section(db, user, SectionKey.internal_test, {
        "acknowledged_instructions": True,
    })
    _seed_internal_test(db, app.id)

    db.refresh(app)
    pct, missing = completion_percentage(db, app)
    assert pct == 100, f"Expected 100%, got {pct}%. Missing: {[m.value for m in missing]}"

    monkeypatch.setattr("invision_api.services.application_service.redis_ping", lambda: True)
    monkeypatch.setattr(
        "invision_api.services.application_service.get_redis_client",
        lambda: type("_R", (), {"exists": lambda self, *_a: 1})(),
    )
    monkeypatch.setattr("invision_api.services.job_dispatcher_service.enqueue_job", lambda *_args, **_kwargs: None)

    original = _mock_post_submit()
    try:
        result = submit_application(db, user)
    finally:
        import invision_api.services.stages.initial_screening_service as iss
        iss.enqueue_post_submit_jobs = original

    assert result.locked_after_submit is True
    assert result.state == ApplicationState.under_screening.value
    assert result.current_stage == ApplicationStage.initial_screening.value
    assert result.submitted_at is not None

    projection = db.get(ApplicationCommissionProjection, app.id)
    assert projection is not None, "Projection should be created on submit"
    assert projection.candidate_full_name == "Марат Исмаилов"
    assert projection.current_stage == ApplicationStage.initial_screening.value

    logs = list(db.scalars(
        select(AuditLog).where(
            AuditLog.entity_id == app.id,
            AuditLog.action == "application_submitted",
        )
    ).all())
    assert len(logs) >= 1

    histories = list(db.scalars(
        select(ApplicationStageHistory)
        .where(ApplicationStageHistory.application_id == app.id)
        .order_by(ApplicationStageHistory.entered_at.desc())
    ).all())
    submit_hist = next((h for h in histories if h.to_stage == ApplicationStage.initial_screening.value), None)
    assert submit_hist is not None
