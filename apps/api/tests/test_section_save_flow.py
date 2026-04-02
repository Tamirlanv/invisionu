"""Integration tests for section save flow."""

import pytest
from sqlalchemy.orm import Session
from uuid import uuid4

from invision_api.models.application import Document
from invision_api.models.enums import DocumentType
from invision_api.models.enums import ApplicationState, SectionKey
from invision_api.services.application_service import save_section


def test_save_personal_section_updates_profile(db: Session, factory):
    """Saving personal section updates CandidateProfile names."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    identity_doc = Document(
        id=uuid4(),
        application_id=app.id,
        original_filename="id.pdf",
        mime_type="application/pdf",
        byte_size=1024,
        storage_key="uploads/id.pdf",
        document_type=DocumentType.supporting_documents.value,
    )
    db.add(identity_doc)
    db.commit()

    row = save_section(db, user, SectionKey.personal, {
        "preferred_first_name": "Новое",
        "preferred_last_name": "Имя",
        "date_of_birth": "2007-01-01",
        "document_type": "id",
        "citizenship": "KZ",
        "iin": "070101500001",
        "document_number": "123456789",
        "document_issue_date": "2024-01-01",
        "document_issued_by": "МВД РК",
        "father_last": "Имя",
        "father_first": "Отец",
        "father_phone": "+77011234567",
        "mother_last": "Имя",
        "mother_first": "Мать",
        "mother_phone": "+77017654321",
        "consent_privacy": True,
        "consent_age": True,
        "identity_document_id": str(identity_doc.id),
    })
    assert row.is_complete is True
    assert profile.first_name == "Новое"
    assert profile.last_name == "Имя"


def test_save_section_moves_draft_to_in_progress(db: Session, factory):
    """Saving a section when app is draft moves state to in_progress."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile, state="draft")
    db.commit()

    save_section(db, user, SectionKey.personal, {
        "preferred_first_name": "Тест",
        "preferred_last_name": "Кандидат",
    })
    assert app.state == ApplicationState.in_progress.value


def test_save_section_on_locked_app_raises_409(db: Session, factory):
    """Saving a section on a locked app raises 409."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    app.locked_after_submit = True
    db.commit()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        save_section(db, user, SectionKey.personal, {
            "preferred_first_name": "X",
            "preferred_last_name": "Y",
        })
    assert exc_info.value.status_code == 409


def test_save_education_section_syncs_records(db: Session, factory):
    """Saving education section syncs education_records."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.commit()

    save_section(db, user, SectionKey.education, {
        "entries": [
            {"institution_name": "MIT", "is_current": False},
            {"institution_name": "Stanford", "is_current": True},
        ],
        "presentation_video_url": "https://youtube.com/test",
        "english_proof_kind": "ielts_6",
        "certificate_proof_kind": "ent",
    })
    assert len(app.education_records) == 2


def test_save_achievements_section(db: Session, factory):
    """Saving achievements section with activities marks complete."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.commit()

    row = save_section(db, user, SectionKey.achievements_activities, {
        "activities": [{"category": "Спорт", "title": "Чемпионат"}],
    })
    assert row.is_complete is True


def test_save_consent_agreement_section(db: Session, factory):
    """Saving consent agreement with all fields marks complete."""
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)
    db.commit()

    row = save_section(db, user, SectionKey.consent_agreement, {
        "accepted_terms": True,
        "accepted_privacy": True,
        "consent_policy_version": "v1.0",
    })
    assert row.is_complete is True
