from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from invision_api.commission.application.ai_pipeline_service import run_commission_ai_pipeline
from invision_api.commission.application.service import rebuild_projection
from invision_api.db.session import SessionLocal
from invision_api.models.application import AIReviewMetadata, Application
from invision_api.models.certificate_validation import CertificateValidationResultRow
from invision_api.models.enums import DataCheckRunStatus, DataCheckUnitStatus, DataCheckUnitType
from invision_api.models.video_validation import VideoValidationResultRow
from invision_api.repositories import admissions_repository, ai_interview_repository, data_check_repository
from invision_api.services.ai_interview.resolution_summary import ensure_resolution_summary_available
from invision_api.services.ai_interview.service import ensure_ai_interview_draft_best_effort
from invision_api.services.data_check.job_registry import REGISTRY
from invision_api.services.data_check.status_service import compute_run_status
from invision_api.services.stages.application_review_service import upsert_snapshot_from_packet

logger = logging.getLogger(__name__)

BackfillMode = Literal["analysis_only", "full"]
BackfillStatus = Literal["processed", "skipped", "failed", "dry_run"]
MISSING_FIELDS: set[str] = {
    "review_snapshot",
    "commission_ai_summary",
    "ai_interview_draft",
    "ai_interview_resolution",
    "video_summary",
    "certificate_result",
}

FULL_UNIT_ORDER: tuple[DataCheckUnitType, ...] = (
    DataCheckUnitType.test_profile_processing,
    DataCheckUnitType.motivation_processing,
    DataCheckUnitType.growth_path_processing,
    DataCheckUnitType.achievements_processing,
    DataCheckUnitType.link_validation,
    DataCheckUnitType.video_validation,
    DataCheckUnitType.certificate_validation,
    DataCheckUnitType.signals_aggregation,
    DataCheckUnitType.candidate_ai_summary,
)


@dataclass(frozen=True)
class BackfillOptions:
    mode: BackfillMode = "analysis_only"
    dry_run: bool = False
    application_ids: tuple[UUID, ...] = ()
    stages: tuple[str, ...] = ()
    submitted_from: date | None = None
    submitted_to: date | None = None
    only_missing: tuple[str, ...] = ()
    include_archived: bool = False
    force: bool = False
    backfill_version: str | None = None
    auto_advance_ready: bool = False
    limit: int | None = None
    offset: int = 0
    batch_size: int = 100


@dataclass(frozen=True)
class BackfillApplicationResult:
    application_id: UUID
    status: BackfillStatus
    mode: BackfillMode
    actions: tuple[str, ...] = ()
    reason: str | None = None
    error: str | None = None


@dataclass
class BackfillReport:
    mode: BackfillMode
    dry_run: bool
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    dry_run_count: int = 0
    total_targets: int = 0
    results: list[BackfillApplicationResult] = field(default_factory=list)

    def add(self, result: BackfillApplicationResult) -> None:
        self.results.append(result)
        if result.status == "processed":
            self.processed += 1
        elif result.status == "skipped":
            self.skipped += 1
        elif result.status == "dry_run":
            self.dry_run_count += 1
        else:
            self.failed += 1


def _validate_options(options: BackfillOptions) -> None:
    if options.mode not in {"analysis_only", "full"}:
        raise ValueError("mode must be analysis_only|full")
    if options.offset < 0:
        raise ValueError("offset must be >= 0")
    if options.limit is not None and options.limit <= 0:
        raise ValueError("limit must be > 0")
    if options.batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    if options.mode == "full" and not options.backfill_version:
        raise ValueError("backfill_version is required for full mode")
    unknown = [x for x in options.only_missing if x not in MISSING_FIELDS]
    if unknown:
        raise ValueError(f"unknown only-missing filters: {', '.join(sorted(set(unknown)))}")


def _build_targets_stmt(options: BackfillOptions) -> Select[tuple[UUID]]:
    stmt: Select[tuple[UUID]] = select(Application.id)
    if options.application_ids:
        stmt = stmt.where(Application.id.in_(options.application_ids))
    if not options.include_archived:
        stmt = stmt.where(Application.is_archived.is_(False))

    # Default policy for one-shot prod backfill: only submitted applications.
    stmt = stmt.where(Application.submitted_at.is_not(None))

    if options.stages:
        stmt = stmt.where(Application.current_stage.in_(options.stages))
    if options.submitted_from:
        start_dt = datetime.combine(options.submitted_from, time.min, tzinfo=UTC)
        stmt = stmt.where(Application.submitted_at >= start_dt)
    if options.submitted_to:
        end_dt_exclusive = datetime.combine(options.submitted_to, time.min, tzinfo=UTC) + timedelta(days=1)
        stmt = stmt.where(Application.submitted_at < end_dt_exclusive)

    stmt = stmt.order_by(desc(Application.submitted_at), desc(Application.created_at)).offset(options.offset)
    if options.limit is not None:
        stmt = stmt.limit(options.limit)
    return stmt


def _latest_ai_summary_exists(db: Session, application_id: UUID) -> bool:
    row = db.scalars(
        select(AIReviewMetadata)
        .where(AIReviewMetadata.application_id == application_id)
        .order_by(AIReviewMetadata.created_at.desc())
    ).first()
    return bool(row and (row.summary_text or "").strip())


def _latest_video_summary_exists(db: Session, application_id: UUID) -> bool:
    row = db.scalars(
        select(VideoValidationResultRow)
        .where(VideoValidationResultRow.application_id == application_id)
        .order_by(VideoValidationResultRow.created_at.desc())
    ).first()
    return bool(row and (row.summary_text or "").strip())


def _certificate_result_exists(db: Session, application_id: UUID) -> bool:
    row = db.scalars(
        select(CertificateValidationResultRow.id)
        .where(CertificateValidationResultRow.application_id == application_id)
        .limit(1)
    ).first()
    return row is not None


def _resolve_missing_keys_for_application(db: Session, application_id: UUID) -> set[str]:
    missing: set[str] = set()

    review_snapshot = admissions_repository.get_review_snapshot(db, application_id)
    if review_snapshot is None or not isinstance(review_snapshot.summary_by_block, dict):
        missing.add("review_snapshot")

    if not _latest_ai_summary_exists(db, application_id):
        missing.add("commission_ai_summary")

    qs = ai_interview_repository.get_question_set_for_application(db, application_id)
    if qs is None:
        missing.add("ai_interview_draft")
    if qs is not None and qs.candidate_completed_at and not isinstance(qs.resolution_summary, dict):
        missing.add("ai_interview_resolution")

    if not _latest_video_summary_exists(db, application_id):
        missing.add("video_summary")

    if not _certificate_result_exists(db, application_id):
        missing.add("certificate_result")

    return missing


def collect_target_application_ids(db: Session, options: BackfillOptions) -> list[UUID]:
    _validate_options(options)
    ids = list(db.scalars(_build_targets_stmt(options)).all())
    if not options.only_missing:
        return ids

    required = set(options.only_missing)
    filtered: list[UUID] = []
    for application_id in ids:
        missing_keys = _resolve_missing_keys_for_application(db, application_id)
        if missing_keys.intersection(required):
            filtered.append(application_id)
    return filtered


def _analysis_actions_for_stage(app: Application) -> list[str]:
    actions = [
        "refresh_review_snapshot",
        "refresh_commission_ai_summary",
        "refresh_commission_projection",
    ]
    if app.current_stage == "application_review":
        actions.append("ensure_ai_interview_draft")
    return actions


def _full_backfill_marker(version: str) -> str:
    return f"backfill_version={version}"


def _already_backfilled_for_version(db: Session, *, application_id: UUID, backfill_version: str) -> bool:
    marker = _full_backfill_marker(backfill_version)
    runs = data_check_repository.list_runs_for_application(db, application_id)
    for run in runs:
        explainability = run.explainability if isinstance(run.explainability, list) else []
        if marker in explainability:
            return True
    return False


def _create_backfill_run(db: Session, *, app: Application, backfill_version: str) -> UUID:
    run = data_check_repository.create_run(
        db,
        candidate_id=app.candidate_profile_id,
        application_id=app.id,
        status=DataCheckRunStatus.pending.value,
        explainability=[
            "Backfill full reprocessing run.",
            _full_backfill_marker(backfill_version),
            "backfill_mode=full",
        ],
    )

    for unit in FULL_UNIT_ORDER:
        data_check_repository.create_check(
            db,
            run_id=run.id,
            check_type=unit.value,
            status=DataCheckUnitStatus.pending.value,
            result_payload=None,
        )
        data_check_repository.upsert_unit_result(
            db,
            run_id=run.id,
            application_id=app.id,
            unit_type=unit.value,
            status=DataCheckUnitStatus.pending.value,
            result_payload=None,
            warnings=[],
            errors=[],
            explainability=[],
            manual_review_required=False,
            attempts=0,
            started_at=None,
            finished_at=None,
        )

    return run.id


def _persist_backfill_unit_failure(
    db: Session,
    *,
    run_id: UUID,
    application_id: UUID,
    unit: DataCheckUnitType,
    check: Any,
    error_text: str,
) -> None:
    data_check_repository.update_check_status(
        db,
        check=check,
        status=DataCheckUnitStatus.failed.value,
        last_error=error_text[:500],
    )
    data_check_repository.upsert_unit_result(
        db,
        run_id=run_id,
        application_id=application_id,
        unit_type=unit.value,
        status=DataCheckUnitStatus.failed.value,
        result_payload=None,
        warnings=[],
        errors=[error_text[:500]],
        explainability=["Backfill unit execution failed."],
        manual_review_required=True,
        attempts=check.attempts or 0,
        started_at=check.started_at,
        finished_at=check.finished_at,
    )


def _run_full_data_check_recompute(
    db: Session,
    *,
    app: Application,
    backfill_version: str,
) -> tuple[UUID, list[str]]:
    run_id = _create_backfill_run(db, app=app, backfill_version=backfill_version)
    executed_units: list[str] = []

    for unit in FULL_UNIT_ORDER:
        check = data_check_repository.get_check(db, run_id, unit.value)
        if not check:
            continue

        now = datetime.now(tz=UTC)
        attempts = (check.attempts or 0) + 1
        data_check_repository.update_check_status(
            db,
            check=check,
            status=DataCheckUnitStatus.running.value,
            attempts=attempts,
        )
        data_check_repository.upsert_unit_result(
            db,
            run_id=run_id,
            application_id=app.id,
            unit_type=unit.value,
            status=DataCheckUnitStatus.running.value,
            result_payload=check.result_payload,
            warnings=[],
            errors=[],
            explainability=["Backfill unit is running."],
            manual_review_required=False,
            attempts=attempts,
            started_at=check.started_at or now,
            finished_at=None,
        )

        processor = REGISTRY[unit]
        try:
            result = processor(db, app.id, app.candidate_profile_id, run_id)
            final_status = result.status
            if final_status not in {
                DataCheckUnitStatus.completed.value,
                DataCheckUnitStatus.failed.value,
                DataCheckUnitStatus.manual_review_required.value,
            }:
                final_status = DataCheckUnitStatus.failed.value
                result.errors.append(f"Unsupported unit status from processor: {result.status}")

            data_check_repository.update_check_status(
                db,
                check=check,
                status=final_status,
                result_payload=result.payload,
                last_error=("; ".join(result.errors)[:500] if result.errors else None),
            )
            data_check_repository.upsert_unit_result(
                db,
                run_id=run_id,
                application_id=app.id,
                unit_type=unit.value,
                status=final_status,
                result_payload=result.payload,
                warnings=result.warnings,
                errors=result.errors,
                explainability=result.explainability,
                manual_review_required=result.manual_review_required,
                attempts=check.attempts or attempts,
                started_at=check.started_at,
                finished_at=check.finished_at,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "backfill_unit_failed application=%s run=%s unit=%s",
                app.id,
                run_id,
                unit.value,
            )
            _persist_backfill_unit_failure(
                db,
                run_id=run_id,
                application_id=app.id,
                unit=unit,
                check=check,
                error_text=f"backfill_unit_exception:{str(exc)}",
            )

        executed_units.append(unit.value)

    checks = data_check_repository.list_checks_for_run(db, run_id)
    status_map: dict[DataCheckUnitType, str] = {}
    for row in checks:
        try:
            status_map[DataCheckUnitType(row.check_type)] = row.status
        except ValueError:
            continue
    computed = compute_run_status(status_map)
    data_check_repository.update_run_status(
        db,
        run=data_check_repository.get_run(db, run_id),
        status=computed.status,
        warnings=computed.warnings,
        errors=computed.errors,
        explainability=[
            *computed.explainability,
            _full_backfill_marker(backfill_version),
            "backfill_mode=full",
        ],
    )

    return run_id, executed_units


def _run_analysis_only_actions(
    db: Session,
    *,
    app: Application,
    force: bool,
) -> list[str]:
    actions: list[str] = []

    upsert_snapshot_from_packet(db, app.id, review_status="in_progress")
    actions.append("refresh_review_snapshot")

    run_commission_ai_pipeline(
        db,
        application_id=app.id,
        actor_user_id=None,
        force=force,
    )
    actions.append("refresh_commission_ai_summary")

    if app.current_stage == "application_review":
        ensure_ai_interview_draft_best_effort(
            db,
            app.id,
            actor_user_id=None,
            trigger="backfill_script",
        )
        actions.append("ensure_ai_interview_draft")

    qs = ai_interview_repository.get_question_set_for_application(db, app.id)
    if qs and qs.candidate_completed_at is not None:
        ensure_resolution_summary_available(db, application_id=app.id, row=qs)
        actions.append("ensure_ai_interview_resolution")

    rebuild_projection(db, app.id)
    actions.append("refresh_commission_projection")

    return actions


def _maybe_auto_advance_after_full(
    db: Session,
    *,
    app: Application,
    run_id: UUID,
) -> bool:
    """Try stage auto-advance for backfill run when aggregate is ready.

    Backfill defaults to no stage transitions. This helper is called only when
    the explicit ``auto_advance_ready`` option is enabled.
    """
    from invision_api.services.data_check.job_runner_service import _try_auto_advance

    before_stage = app.current_stage
    checks = data_check_repository.list_checks_for_run(db, run_id)
    status_map: dict[DataCheckUnitType, str] = {}
    for c in checks:
        try:
            status_map[DataCheckUnitType(c.check_type)] = c.status
        except ValueError:
            continue
    computed = compute_run_status(status_map)
    _try_auto_advance(db, run_computed=computed, app=app, application_id=app.id)
    db.flush()
    db.refresh(app)
    return app.current_stage != before_stage


def reprocess_application(
    db: Session,
    *,
    application_id: UUID,
    options: BackfillOptions,
) -> BackfillApplicationResult:
    _validate_options(options)

    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        return BackfillApplicationResult(
            application_id=application_id,
            status="failed",
            mode=options.mode,
            reason="application_not_found",
            error="Application not found",
        )

    if options.mode == "analysis_only":
        planned = _analysis_actions_for_stage(app)
        if options.dry_run:
            return BackfillApplicationResult(
                application_id=application_id,
                status="dry_run",
                mode=options.mode,
                actions=tuple(planned),
                reason="dry_run",
            )

        try:
            actions = _run_analysis_only_actions(db, app=app, force=options.force)
            return BackfillApplicationResult(
                application_id=application_id,
                status="processed",
                mode=options.mode,
                actions=tuple(actions),
            )
        except Exception as exc:  # noqa: BLE001
            return BackfillApplicationResult(
                application_id=application_id,
                status="failed",
                mode=options.mode,
                reason="analysis_only_failed",
                error=str(exc),
            )

    # Full mode.
    assert options.backfill_version is not None  # validated above

    if not options.force and _already_backfilled_for_version(
        db,
        application_id=application_id,
        backfill_version=options.backfill_version,
    ):
        return BackfillApplicationResult(
            application_id=application_id,
            status="skipped",
            mode=options.mode,
            reason="already_backfilled_for_version",
            actions=(),
        )

    active_run = data_check_repository.resolve_canonical_run_for_application(
        db,
        application_id,
        active_only=True,
    )
    if active_run and not options.force:
        return BackfillApplicationResult(
            application_id=application_id,
            status="skipped",
            mode=options.mode,
            reason="active_data_check_run_exists",
            actions=(),
        )

    planned = [f"run_units:{','.join(u.value for u in FULL_UNIT_ORDER)}", "analysis_only_post_steps"]
    if options.dry_run:
        return BackfillApplicationResult(
            application_id=application_id,
            status="dry_run",
            mode=options.mode,
            actions=tuple(planned),
            reason="dry_run",
        )

    try:
        run_id, units = _run_full_data_check_recompute(
            db,
            app=app,
            backfill_version=options.backfill_version,
        )
        actions = [f"full_data_check_run:{run_id}", *units]
        if options.auto_advance_ready:
            moved = _maybe_auto_advance_after_full(db, app=app, run_id=run_id)
            actions.append("auto_advance_ready_ok" if moved else "auto_advance_ready_skip")
        actions.extend(_run_analysis_only_actions(db, app=app, force=options.force))
        return BackfillApplicationResult(
            application_id=application_id,
            status="processed",
            mode=options.mode,
            actions=tuple(actions),
        )
    except Exception as exc:  # noqa: BLE001
        return BackfillApplicationResult(
            application_id=application_id,
            status="failed",
            mode=options.mode,
            reason="full_backfill_failed",
            error=str(exc),
        )


def reprocess_applications(
    options: BackfillOptions,
    *,
    session_factory: Any = SessionLocal,
) -> BackfillReport:
    _validate_options(options)

    report = BackfillReport(mode=options.mode, dry_run=options.dry_run)

    discover_db = session_factory()
    try:
        target_ids = collect_target_application_ids(discover_db, options)
    finally:
        discover_db.close()

    report.total_targets = len(target_ids)
    if not target_ids:
        return report

    for idx in range(0, len(target_ids), options.batch_size):
        batch = target_ids[idx : idx + options.batch_size]
        logger.info(
            "backfill_batch_start mode=%s dry_run=%s batch_start=%s batch_size=%s",
            options.mode,
            options.dry_run,
            idx,
            len(batch),
        )
        for application_id in batch:
            db = session_factory()
            try:
                result = reprocess_application(db, application_id=application_id, options=options)
                if options.dry_run:
                    db.rollback()
                elif result.status == "processed":
                    db.commit()
                else:
                    db.rollback()
                report.add(result)
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                report.add(
                    BackfillApplicationResult(
                        application_id=application_id,
                        status="failed",
                        mode=options.mode,
                        reason="unhandled_exception",
                        error=str(exc),
                    )
                )
            finally:
                db.close()

    return report
