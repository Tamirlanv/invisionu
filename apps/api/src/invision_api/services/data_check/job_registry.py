from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import DataCheckUnitType
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.processors.achievements_processor import run_achievements_processing
from invision_api.services.data_check.processors.candidate_ai_summary_processor import (
    run_candidate_ai_summary_processing,
)
from invision_api.services.data_check.processors.certificate_validation_processor import (
    run_certificate_validation_processing,
)
from invision_api.services.data_check.processors.growth_path_processor import run_growth_path_processing
from invision_api.services.data_check.processors.link_validation_processor import run_link_validation_processing
from invision_api.services.data_check.processors.motivation_processor import run_motivation_processing
from invision_api.services.data_check.processors.signals_aggregate_processor import run_signals_aggregation
from invision_api.services.data_check.processors.test_profile_processor import run_test_profile_processing
from invision_api.services.data_check.processors.video_validation_processor import run_video_validation_processing

ProcessorFn = Callable[[Session, UUID, UUID, UUID], UnitExecutionResult]


def _test(db: Session, application_id: UUID, _: UUID, __: UUID) -> UnitExecutionResult:
    return run_test_profile_processing(db, application_id=application_id)


def _motivation(db: Session, application_id: UUID, _: UUID, __: UUID) -> UnitExecutionResult:
    return run_motivation_processing(db, application_id=application_id)


def _growth(db: Session, application_id: UUID, _: UUID, __: UUID) -> UnitExecutionResult:
    return run_growth_path_processing(db, application_id=application_id)


def _achievements(db: Session, application_id: UUID, _: UUID, __: UUID) -> UnitExecutionResult:
    return run_achievements_processing(db, application_id=application_id)


def _links(db: Session, application_id: UUID, candidate_id: UUID, __: UUID) -> UnitExecutionResult:
    return run_link_validation_processing(db, application_id=application_id, candidate_id=candidate_id)


def _video(db: Session, application_id: UUID, candidate_id: UUID, __: UUID) -> UnitExecutionResult:
    return run_video_validation_processing(db, application_id=application_id, candidate_id=candidate_id)


def _certs(db: Session, application_id: UUID, candidate_id: UUID, __: UUID) -> UnitExecutionResult:
    return run_certificate_validation_processing(db, application_id=application_id, candidate_id=candidate_id)


def _signals(db: Session, application_id: UUID, _: UUID, run_id: UUID) -> UnitExecutionResult:
    return run_signals_aggregation(db, application_id=application_id, run_id=run_id)


def _ai_summary(db: Session, application_id: UUID, _: UUID, run_id: UUID) -> UnitExecutionResult:
    return run_candidate_ai_summary_processing(db, application_id=application_id, run_id=run_id)


REGISTRY: dict[DataCheckUnitType, ProcessorFn] = {
    DataCheckUnitType.test_profile_processing: _test,
    DataCheckUnitType.motivation_processing: _motivation,
    DataCheckUnitType.growth_path_processing: _growth,
    DataCheckUnitType.achievements_processing: _achievements,
    DataCheckUnitType.link_validation: _links,
    DataCheckUnitType.video_validation: _video,
    DataCheckUnitType.certificate_validation: _certs,
    DataCheckUnitType.signals_aggregation: _signals,
    DataCheckUnitType.candidate_ai_summary: _ai_summary,
}


FIRST_WAVE_UNITS: tuple[DataCheckUnitType, ...] = (
    DataCheckUnitType.test_profile_processing,
    DataCheckUnitType.motivation_processing,
    DataCheckUnitType.growth_path_processing,
    DataCheckUnitType.achievements_processing,
    DataCheckUnitType.link_validation,
    DataCheckUnitType.video_validation,
    DataCheckUnitType.certificate_validation,
)
