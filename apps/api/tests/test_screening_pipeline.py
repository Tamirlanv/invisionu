"""Integration tests for initial screening pipeline."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Document, DocumentExtraction
from invision_api.models.enums import ApplicationStage, ApplicationState, ScreeningResult
from invision_api.services.stages.initial_screening_service import (
    run_screening_checks_and_record,
)


def test_screening_passed_when_all_complete(db: Session, factory):
    """Screening passes when all sections are complete."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.initial_screening.value
    factory.fill_required_sections(db, app)
    db.flush()

    result = run_screening_checks_and_record(db, app, actor_user_id=user.id)
    assert result.screening_result == ScreeningResult.passed.value


def test_screening_revision_required_when_incomplete(db: Session, factory):
    """Screening requires revision when sections are missing."""
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.initial_screening.value
    db.flush()

    result = run_screening_checks_and_record(db, app, actor_user_id=user.id)
    assert result.screening_result == ScreeningResult.revision_required.value
    assert result.missing_items is not None
    assert len(result.missing_items.get("missing_sections", [])) > 0


def test_screening_continues_when_extraction_errors(db: Session, factory, monkeypatch: pytest.MonkeyPatch):
    user = factory.user(db)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.current_stage = ApplicationStage.initial_screening.value
    factory.fill_required_sections(db, app)
    db.add(
        Document(
            application_id=app.id,
            uploaded_by_user_id=user.id,
            document_type="transcript",
            storage_key="missing/file.pdf",
            original_filename="file.pdf",
            mime_type="application/pdf",
            byte_size=10,
            verification_status="pending",
            sha256_hex="0" * 64,
        )
    )
    db.flush()

    monkeypatch.setattr(
        "invision_api.services.text_extraction_service.extract_and_persist_for_document",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = run_screening_checks_and_record(db, app, actor_user_id=user.id)
    assert result is not None
    assert result.screening_status == "completed"

    failed_extractions = list(
        db.scalars(
            select(DocumentExtraction).where(DocumentExtraction.error_message.ilike("%Extraction failed%"))
        ).all()
    )
    assert failed_extractions
