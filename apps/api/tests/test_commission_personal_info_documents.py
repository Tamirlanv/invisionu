from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from invision_api.commission.application.personal_info_service import get_commission_application_personal_info
from invision_api.models.application import ApplicationSectionState, Document
from invision_api.models.commission import CommissionUser
from invision_api.models.enums import ApplicationState, DocumentType


def test_personal_info_shows_only_referenced_documents(db: Session, factory):
    committee_user = factory.user(db)
    committee_role = factory.committee_role(db)
    factory.assign_role(db, committee_user, committee_role)
    db.add(CommissionUser(user_id=committee_user.id, role="viewer"))

    candidate_user = factory.user(db)
    profile = factory.profile(db, candidate_user, first_name="Алия", last_name="Нурланова")
    app = factory.application(db, profile, state=ApplicationState.submitted.value)
    app.current_stage = "application_review"
    app.locked_after_submit = True
    app.submitted_at = datetime.now(tz=UTC)

    identity_doc_id = uuid4()
    ielts_doc_id = uuid4()
    old_doc_id = uuid4()

    db.add_all(
        [
            Document(
                id=identity_doc_id,
                application_id=app.id,
                document_type=DocumentType.supporting_documents.value,
                storage_key="uploads/identity.pdf",
                original_filename="identity.pdf",
                mime_type="application/pdf",
                byte_size=1300,
            ),
            Document(
                id=ielts_doc_id,
                application_id=app.id,
                document_type=DocumentType.supporting_documents.value,
                storage_key="uploads/ielts.pdf",
                original_filename="ielts.pdf",
                mime_type="application/pdf",
                byte_size=2400,
            ),
            Document(
                id=old_doc_id,
                application_id=app.id,
                document_type=DocumentType.supporting_documents.value,
                storage_key="uploads/old.pdf",
                original_filename="old.pdf",
                mime_type="application/pdf",
                byte_size=1800,
            ),
        ]
    )

    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="personal",
            payload={
                "preferred_first_name": "Алия",
                "preferred_last_name": "Нурланова",
                "identity_document_id": str(identity_doc_id),
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="education",
            payload={
                "english_document_id": str(ielts_doc_id),
                "english_proof_kind": "ielts",
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="contact",
            payload={"phone_e164": "+77000000000", "country": "KZ", "city": "Алматы"},
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )
    db.flush()

    view = get_commission_application_personal_info(db, application_id=app.id, actor=committee_user)
    document_ids = {d["id"] for d in view["personalInfo"]["documents"]}

    assert str(identity_doc_id) in document_ids
    assert str(ielts_doc_id) in document_ids
    assert str(old_doc_id) not in document_ids

