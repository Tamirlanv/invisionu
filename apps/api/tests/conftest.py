"""Shared pytest fixtures: transactional test DB, model factories, and test helpers.

Each test runs inside a DB transaction that is rolled back after the test,
ensuring test isolation without dropping/recreating tables every time.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-0123456789")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake")

_raw_db_url = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+psycopg://invision:invision@localhost:5432/invision"),
)
if _raw_db_url.startswith("postgresql+asyncpg://"):
    _raw_db_url = _raw_db_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
os.environ["DATABASE_URL"] = _raw_db_url

from invision_api.db.base import Base  # noqa: E402
from invision_api.models.application import (  # noqa: E402
    Application,
    ApplicationSectionState,
    ApplicationStageHistory,
    CandidateProfile,
)
from invision_api.models.application_raw_submission_snapshot import ApplicationRawSubmissionSnapshot  # noqa: E402
from invision_api.models.candidate_signals_aggregate import CandidateSignalsAggregate  # noqa: E402
from invision_api.models.commission import ApplicationCommissionProjection  # noqa: E402
from invision_api.models.data_check_unit_result import DataCheckUnitResult  # noqa: E402
from invision_api.models.enums import ApplicationStage, ApplicationState, SectionKey  # noqa: E402
from invision_api.models.user import Role, User, UserRole  # noqa: E402

# Import all models so Base.metadata knows about every table.
import invision_api.models  # noqa: E402, F401

_engine = create_engine(_raw_db_url, echo=False, pool_pre_ping=True)
_SessionFactory = sessionmaker(bind=_engine)


@pytest.fixture(autouse=True)
def db() -> Generator[Session, None, None]:
    """Provide a transactional DB session that rolls back after each test."""
    connection = _engine.connect()
    transaction = connection.begin()
    session = _SessionFactory(bind=connection)

    # Nested transaction so service code calling commit() doesn't end our wrapper.
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


class Factory:
    """Helpers to create test entities quickly."""

    @staticmethod
    def user(db: Session, *, email: str | None = None, verified: bool = True) -> User:
        if email is None:
            email = f"test-{uuid4().hex[:8]}@example.com"
        u = User(
            id=uuid4(),
            email=email,
            hashed_password="$2b$12$fakehashfakehashfakehashfakehashfakehashfakehashfake",
            is_active=True,
            email_verified_at=datetime.now(tz=UTC) if verified else None,
        )
        db.add(u)
        db.flush()
        return u

    @staticmethod
    def candidate_role(db: Session) -> Role:
        role = db.query(Role).filter(Role.name == "candidate").first()
        if role:
            return role
        role = Role(id=uuid4(), name="candidate")
        db.add(role)
        db.flush()
        return role

    @staticmethod
    def committee_role(db: Session) -> Role:
        role = db.query(Role).filter(Role.name == "committee").first()
        if role:
            return role
        role = Role(id=uuid4(), name="committee")
        db.add(role)
        db.flush()
        return role

    @staticmethod
    def assign_role(db: Session, user: User, role: Role) -> None:
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.flush()

    @staticmethod
    def profile(db: Session, user: User, *, first_name: str = "Тест", last_name: str = "Кандидат") -> CandidateProfile:
        p = CandidateProfile(
            id=uuid4(),
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
        )
        db.add(p)
        db.flush()
        return p

    @staticmethod
    def application(db: Session, profile: CandidateProfile, *, state: str = "draft") -> Application:
        app = Application(
            id=uuid4(),
            candidate_profile_id=profile.id,
            state=state,
            current_stage=ApplicationStage.application.value,
            locked_after_submit=False,
        )
        db.add(app)
        db.add(ApplicationStageHistory(
            application_id=app.id,
            from_stage=ApplicationStage.application.value,
            to_stage=ApplicationStage.application.value,
            entered_at=datetime.now(tz=UTC),
            actor_type="system",
        ))
        db.flush()
        return app

    @staticmethod
    def fill_required_sections(db: Session, app: Application) -> None:
        """Mark all required sections as complete with minimal valid payloads."""
        section_data: dict[str, dict[str, Any]] = {
            SectionKey.personal.value: {
                "preferred_first_name": "Тест",
                "preferred_last_name": "Кандидат",
                "date_of_birth": "2007-01-01",
                "document_type": "id",
                "citizenship": "KZ",
                "iin": "070101500001",
                "document_number": "123456789",
                "document_issue_date": "2024-01-01",
                "document_issued_by": "МВД РК",
                "father_last": "Кандидатов",
                "father_first": "Петр",
                "father_phone": "+77011234567",
                "mother_last": "Кандидатова",
                "mother_first": "Мария",
                "mother_phone": "+77017654321",
                "consent_privacy": True,
                "consent_age": True,
                "identity_document_id": str(uuid4()),
            },
            SectionKey.contact.value: {
                "phone_e164": "+77001234567",
                "address_line1": "ул. Тестовая 1",
                "region": "Алматинская область",
                "city": "Алматы",
                "street": "Тестовая",
                "house": "1",
                "apartment": "10",
                "country": "KZ",
                "telegram": "@test",
                "consent_privacy": True,
                "consent_parent": True,
            },
            SectionKey.education.value: {
                "entries": [{"institution_name": "Школа №1", "is_current": False}],
                "presentation_video_url": "https://youtube.com/watch?v=test",
                "english_proof_kind": "ielts_6",
                "certificate_proof_kind": "ent",
            },
            SectionKey.achievements_activities.value: {
                "activities": [{"category": "Олимпиада", "title": "Республиканская олимпиада"}],
            },
            SectionKey.leadership_evidence.value: {
                "items": [{"title": "Капитан команды"}],
            },
            SectionKey.motivation_goals.value: {
                "narrative": "A" * 350,
            },
            SectionKey.growth_journey.value: {
                "answers": {
                    "q1": {"text": "x" * 250},
                    "q2": {"text": "x" * 200},
                    "q3": {"text": "x" * 200},
                    "q4": {"text": "x" * 200},
                    "q5": {"text": "x" * 150},
                },
                "consent_privacy": True,
                "consent_parent": True,
            },
            SectionKey.internal_test.value: {
                "acknowledged_instructions": True,
            },
            SectionKey.social_status_cert.value: {
                "attestation": "Подтверждаю социальный статус данного заявления",
            },
            SectionKey.documents_manifest.value: {
                "acknowledged_required_documents": True,
            },
            SectionKey.consent_agreement.value: {
                "accepted_terms": True,
                "accepted_privacy": True,
                "consent_policy_version": "v1.0",
            },
        }
        for key, payload in section_data.items():
            db.add(ApplicationSectionState(
                application_id=app.id,
                section_key=key,
                payload=payload,
                is_complete=True,
                schema_version=1,
                last_saved_at=datetime.now(tz=UTC),
            ))
        db.flush()


@pytest.fixture
def factory() -> Factory:
    return Factory()


@pytest.fixture(autouse=True)
def ensure_data_check_tables(db: Session) -> None:
    bind = db.get_bind()
    ApplicationRawSubmissionSnapshot.__table__.create(bind=bind, checkfirst=True)
    DataCheckUnitResult.__table__.create(bind=bind, checkfirst=True)
    CandidateSignalsAggregate.__table__.create(bind=bind, checkfirst=True)
