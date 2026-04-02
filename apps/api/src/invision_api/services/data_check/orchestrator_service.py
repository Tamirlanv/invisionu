from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import DataCheckUnitStatus, DataCheckUnitType
from invision_api.repositories import data_check_repository
from invision_api.services import job_dispatcher_service
from invision_api.services.data_check.job_registry import FIRST_WAVE_UNITS
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES, UNIT_POLICIES, dependencies_met

logger = logging.getLogger(__name__)

SWEEP_STALE_MINUTES = 10


def enqueue_first_wave_jobs(
    db: Session,
    *,
    application_id: UUID,
    run_id: UUID,
    queue_report: job_dispatcher_service.QueueDispatchReport | None = None,
    strict: bool = False,
) -> job_dispatcher_service.QueueDispatchReport:
    report = queue_report or job_dispatcher_service.QueueDispatchReport()
    for unit_type in FIRST_WAVE_UNITS:
        check = data_check_repository.get_check(db, run_id, unit_type.value)
        if not check:
            continue
        if check.status not in {DataCheckUnitStatus.pending.value, DataCheckUnitStatus.queued.value}:
            continue
        data_check_repository.update_check_status(db, check=check, status=DataCheckUnitStatus.queued.value)
        job_dispatcher_service.enqueue_data_check_unit_job(
            db,
            application_id=application_id,
            run_id=run_id,
            unit_type=unit_type,
            queue_report=report,
            strict=strict,
        )
    return report


def enqueue_ready_followup_jobs(
    db: Session,
    *,
    application_id: UUID,
    run_id: UUID,
    queue_report: job_dispatcher_service.QueueDispatchReport | None = None,
    strict: bool = False,
) -> list[str]:
    report = queue_report
    checks = data_check_repository.list_checks_for_run(db, run_id)
    status_map = {}
    by_unit: dict[DataCheckUnitType, object] = {}
    for check in checks:
        try:
            unit = DataCheckUnitType(check.check_type)
        except ValueError:
            continue
        status_map[unit] = check.status
        by_unit[unit] = check

    enqueued: list[str] = []
    for unit, policy in UNIT_POLICIES.items():
        if not policy.dependencies:
            continue
        check = by_unit.get(unit)
        if not check:
            continue
        if check.status not in {DataCheckUnitStatus.pending.value, DataCheckUnitStatus.queued.value}:
            continue
        if not dependencies_met(unit=unit, statuses=status_map):
            continue
        data_check_repository.update_check_status(db, check=check, status=DataCheckUnitStatus.queued.value)
        job_dispatcher_service.enqueue_data_check_unit_job(
            db,
            application_id=application_id,
            run_id=run_id,
            unit_type=unit,
            queue_report=report,
            strict=strict,
        )
        enqueued.append(unit.value)
    return enqueued


def sweep_stuck_runs(db: Session) -> int:
    """Detect and recover runs that have been stuck (pending/running) for too long.

    For each stuck run:
    1. Checks older than the stale threshold in queued/running are either re-enqueued
       (if under max attempts) or marked failed.
    2. Follow-up jobs whose dependencies are now terminal but were never enqueued get
       re-enqueued.
    3. Run status is recomputed after recovery actions.

    Returns the number of runs that were touched.
    """
    from invision_api.services.data_check.contracts import DataCheckUnitPolicy
    from invision_api.services.data_check.status_service import compute_run_status

    threshold = datetime.now(tz=UTC) - timedelta(minutes=SWEEP_STALE_MINUTES)
    stuck_runs = data_check_repository.list_stuck_runs(db, stale_threshold=threshold)
    if not stuck_runs:
        return 0

    recovered = 0
    for run in stuck_runs:
        stuck_checks = data_check_repository.list_stuck_checks(db, run_id=run.id, stale_threshold=threshold)
        touched = False

        for check in stuck_checks:
            try:
                unit_type = DataCheckUnitType(check.check_type)
            except ValueError:
                continue

            policy: DataCheckUnitPolicy = UNIT_POLICIES.get(unit_type)
            max_attempts = policy.max_attempts if policy else 3
            current_attempts = check.attempts or 0

            if current_attempts >= max_attempts:
                data_check_repository.update_check_status(
                    db,
                    check=check,
                    status=DataCheckUnitStatus.failed.value,
                    last_error=f"exceeded_max_attempts ({max_attempts})",
                )
                logger.warning(
                    "sweep_mark_failed run=%s unit=%s attempts=%d",
                    run.id, check.check_type, current_attempts,
                )
                touched = True
            else:
                data_check_repository.update_check_status(
                    db, check=check, status=DataCheckUnitStatus.queued.value
                )
                try:
                    job_dispatcher_service.enqueue_data_check_unit_job(
                        db,
                        application_id=run.application_id,
                        run_id=run.id,
                        unit_type=unit_type,
                    )
                    logger.info(
                        "sweep_reenqueue run=%s unit=%s attempt=%d",
                        run.id, check.check_type, current_attempts + 1,
                    )
                except Exception:
                    logger.exception("sweep_reenqueue_failed run=%s unit=%s", run.id, check.check_type)
                touched = True

        try:
            enqueue_ready_followup_jobs(db, application_id=run.application_id, run_id=run.id)
        except Exception:
            logger.exception("sweep_followup_failed run=%s", run.id)

        checks_all = data_check_repository.list_checks_for_run(db, run.id)
        status_map = {}
        for c in checks_all:
            try:
                status_map[DataCheckUnitType(c.check_type)] = c.status
            except ValueError:
                continue
        run_computed = compute_run_status(status_map)
        data_check_repository.update_run_status(
            db,
            run=run,
            status=run_computed.status,
            warnings=run_computed.warnings,
            errors=run_computed.errors,
            explainability=run_computed.explainability,
        )

        if touched:
            recovered += 1
            logger.info("sweep_recovered run=%s new_status=%s", run.id, run_computed.status)

        if run_computed.status in TERMINAL_UNIT_STATUSES or run_computed.status in {"ready", "partial", "failed"}:
            from invision_api.services.data_check.job_runner_service import _try_auto_advance

            app = data_check_repository.get_application(db, run.application_id)
            _try_auto_advance(db, run_computed=run_computed, app=app, application_id=run.application_id)

        db.flush()

    return recovered
