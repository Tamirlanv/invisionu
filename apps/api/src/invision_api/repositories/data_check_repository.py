from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy import and_

from invision_api.models.application import (
    AIReviewMetadata,
    Application,
    ApplicationSectionState,
    Document,
    InternalTestAnswer,
    TextAnalysisRun,
)
from invision_api.models.application_raw_submission_snapshot import ApplicationRawSubmissionSnapshot
from invision_api.models.candidate_signals_aggregate import CandidateSignalsAggregate
from invision_api.models.candidate_validation_orchestration import CandidateValidationCheck, CandidateValidationRun
from invision_api.models.data_check_unit_result import DataCheckUnitResult


def get_application(db: Session, application_id: UUID) -> Application | None:
    return db.get(Application, application_id)


def list_section_states(db: Session, application_id: UUID) -> list[ApplicationSectionState]:
    return list(
        db.scalars(select(ApplicationSectionState).where(ApplicationSectionState.application_id == application_id)).all()
    )


def list_internal_test_answers(db: Session, application_id: UUID) -> list[InternalTestAnswer]:
    return list(db.scalars(select(InternalTestAnswer).where(InternalTestAnswer.application_id == application_id)).all())


def list_documents(db: Session, application_id: UUID) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.application_id == application_id)).all())


def list_text_analysis_runs(db: Session, application_id: UUID) -> list[TextAnalysisRun]:
    return list(db.scalars(select(TextAnalysisRun).where(TextAnalysisRun.application_id == application_id)).all())


def upsert_submission_snapshot(
    db: Session,
    *,
    application_id: UUID,
    candidate_id: UUID,
    snapshot_kind: str,
    payload: dict,
    submitted_at: datetime | None,
) -> ApplicationRawSubmissionSnapshot:
    row = db.scalars(
        select(ApplicationRawSubmissionSnapshot).where(
            ApplicationRawSubmissionSnapshot.application_id == application_id,
            ApplicationRawSubmissionSnapshot.snapshot_kind == snapshot_kind,
        )
    ).first()
    if not row:
        row = ApplicationRawSubmissionSnapshot(
            application_id=application_id,
            candidate_id=candidate_id,
            snapshot_kind=snapshot_kind,
            payload=payload,
            submitted_at=submitted_at or datetime.now(tz=UTC),
        )
        db.add(row)
        db.flush()
        return row
    row.candidate_id = candidate_id
    row.payload = payload
    row.submitted_at = submitted_at or row.submitted_at
    db.flush()
    return row


def create_run(
    db: Session,
    *,
    candidate_id: UUID,
    application_id: UUID,
    status: str,
    explainability: list[str] | None = None,
) -> CandidateValidationRun:
    row = CandidateValidationRun(
        candidate_id=candidate_id,
        application_id=application_id,
        overall_status=status,
        warnings=[],
        errors=[],
        explainability=explainability or [],
    )
    db.add(row)
    db.flush()
    return row


def list_runs_for_application(db: Session, application_id: UUID) -> list[CandidateValidationRun]:
    return list(
        db.scalars(
            select(CandidateValidationRun)
            .where(CandidateValidationRun.application_id == application_id)
            .order_by(CandidateValidationRun.created_at.desc())
        ).all()
    )


def get_run(db: Session, run_id: UUID) -> CandidateValidationRun | None:
    return db.get(CandidateValidationRun, run_id)


def create_check(
    db: Session,
    *,
    run_id: UUID,
    check_type: str,
    status: str,
    result_payload: dict | None = None,
) -> CandidateValidationCheck:
    row = CandidateValidationCheck(
        run_id=run_id,
        check_type=check_type,
        status=status,
        result_payload=result_payload,
        attempts=0,
    )
    db.add(row)
    db.flush()
    return row


def list_checks_for_run(db: Session, run_id: UUID) -> list[CandidateValidationCheck]:
    return list(db.scalars(select(CandidateValidationCheck).where(CandidateValidationCheck.run_id == run_id)).all())


def get_check(db: Session, run_id: UUID, check_type: str) -> CandidateValidationCheck | None:
    return db.scalars(
        select(CandidateValidationCheck).where(
            CandidateValidationCheck.run_id == run_id,
            CandidateValidationCheck.check_type == check_type,
        )
    ).first()


def update_check_status(
    db: Session,
    *,
    check: CandidateValidationCheck,
    status: str,
    attempts: int | None = None,
    result_payload: dict | None = None,
    last_error: str | None = None,
) -> CandidateValidationCheck:
    now = datetime.now(tz=UTC)
    check.status = status
    if status == "running":
        check.started_at = check.started_at or now
    if status in {"completed", "failed", "manual_review_required"}:
        check.finished_at = now
    if attempts is not None:
        check.attempts = attempts
    if result_payload is not None:
        check.result_payload = result_payload
    if last_error is not None:
        check.last_error = last_error
    db.flush()
    return check


def update_run_status(
    db: Session,
    *,
    run: CandidateValidationRun,
    status: str,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    explainability: list[str] | None = None,
) -> CandidateValidationRun:
    run.overall_status = status
    if warnings is not None:
        run.warnings = warnings
    if errors is not None:
        run.errors = errors
    if explainability is not None:
        run.explainability = explainability
    db.flush()
    return run


def get_unit_result(db: Session, run_id: UUID, unit_type: str) -> DataCheckUnitResult | None:
    return db.scalars(
        select(DataCheckUnitResult).where(
            DataCheckUnitResult.run_id == run_id,
            DataCheckUnitResult.unit_type == unit_type,
        )
    ).first()


def upsert_unit_result(
    db: Session,
    *,
    run_id: UUID,
    application_id: UUID,
    unit_type: str,
    status: str,
    result_payload: dict | None,
    warnings: list[str],
    errors: list[str],
    explainability: list[str],
    manual_review_required: bool,
    attempts: int,
    started_at: datetime | None,
    finished_at: datetime | None,
) -> DataCheckUnitResult:
    row = get_unit_result(db, run_id, unit_type)
    if not row:
        row = DataCheckUnitResult(
            run_id=run_id,
            application_id=application_id,
            unit_type=unit_type,
            status=status,
            result_payload=result_payload,
            warnings=warnings,
            errors=errors,
            explainability=explainability,
            manual_review_required=manual_review_required,
            attempts=attempts,
            started_at=started_at,
            finished_at=finished_at,
        )
        db.add(row)
        db.flush()
        return row
    row.status = status
    row.result_payload = result_payload
    row.warnings = warnings
    row.errors = errors
    row.explainability = explainability
    row.manual_review_required = manual_review_required
    row.attempts = attempts
    row.started_at = started_at
    row.finished_at = finished_at
    db.flush()
    return row


def list_unit_results_for_run(db: Session, run_id: UUID) -> list[DataCheckUnitResult]:
    return list(db.scalars(select(DataCheckUnitResult).where(DataCheckUnitResult.run_id == run_id)).all())


def upsert_candidate_signals_aggregate(
    db: Session,
    *,
    run_id: UUID,
    application_id: UUID,
    leadership_signals: dict | None,
    initiative_signals: dict | None,
    resilience_signals: dict | None,
    responsibility_signals: dict | None,
    growth_signals: dict | None,
    mission_fit_signals: dict | None,
    strong_motivation_signals: dict | None,
    communication_signals: dict | None,
    attention_flags: list[str],
    authenticity_concern_signals: list[str],
    review_readiness_status: str,
    manual_review_required: bool,
    explainability: list[str],
) -> CandidateSignalsAggregate:
    row = db.scalars(
        select(CandidateSignalsAggregate).where(
            CandidateSignalsAggregate.application_id == application_id,
        )
    ).first()
    if not row:
        row = CandidateSignalsAggregate(
            run_id=run_id,
            application_id=application_id,
            leadership_signals=leadership_signals,
            initiative_signals=initiative_signals,
            resilience_signals=resilience_signals,
            responsibility_signals=responsibility_signals,
            growth_signals=growth_signals,
            mission_fit_signals=mission_fit_signals,
            strong_motivation_signals=strong_motivation_signals,
            communication_signals=communication_signals,
            attention_flags=attention_flags,
            authenticity_concern_signals=authenticity_concern_signals,
            review_readiness_status=review_readiness_status,
            manual_review_required=manual_review_required,
            explainability=explainability,
        )
        db.add(row)
        db.flush()
        return row
    row.run_id = run_id
    row.leadership_signals = leadership_signals
    row.initiative_signals = initiative_signals
    row.resilience_signals = resilience_signals
    row.responsibility_signals = responsibility_signals
    row.growth_signals = growth_signals
    row.mission_fit_signals = mission_fit_signals
    row.strong_motivation_signals = strong_motivation_signals
    row.communication_signals = communication_signals
    row.attention_flags = attention_flags
    row.authenticity_concern_signals = authenticity_concern_signals
    row.review_readiness_status = review_readiness_status
    row.manual_review_required = manual_review_required
    row.explainability = explainability
    db.flush()
    return row


def get_candidate_signals_aggregate(db: Session, application_id: UUID) -> CandidateSignalsAggregate | None:
    return db.scalars(
        select(CandidateSignalsAggregate).where(CandidateSignalsAggregate.application_id == application_id)
    ).first()


def latest_ai_review(db: Session, application_id: UUID) -> AIReviewMetadata | None:
    return db.scalars(
        select(AIReviewMetadata)
        .where(AIReviewMetadata.application_id == application_id)
        .order_by(AIReviewMetadata.created_at.desc())
    ).first()


def list_stuck_runs(db: Session, *, stale_threshold: datetime) -> list[CandidateValidationRun]:
    """Return runs still in pending/running whose last update is older than *stale_threshold*."""
    return list(
        db.scalars(
            select(CandidateValidationRun).where(
                CandidateValidationRun.overall_status.in_(["pending", "running"]),
                CandidateValidationRun.updated_at < stale_threshold,
            )
        ).all()
    )


def list_stuck_checks(
    db: Session,
    *,
    run_id: UUID,
    stale_threshold: datetime,
) -> list[CandidateValidationCheck]:
    """Return checks within a run that are queued/running and older than *stale_threshold*."""
    return list(
        db.scalars(
            select(CandidateValidationCheck).where(
                and_(
                    CandidateValidationCheck.run_id == run_id,
                    CandidateValidationCheck.status.in_(["queued", "running"]),
                    CandidateValidationCheck.updated_at < stale_threshold,
                )
            )
        ).all()
    )
