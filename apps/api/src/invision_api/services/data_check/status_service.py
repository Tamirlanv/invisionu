from __future__ import annotations

from dataclasses import dataclass

from invision_api.models.enums import DataCheckRunStatus, DataCheckUnitStatus, DataCheckUnitType
from invision_api.services.data_check.contracts import DataCheckUnitPolicy


UNIT_POLICIES: dict[DataCheckUnitType, DataCheckUnitPolicy] = {
    DataCheckUnitType.test_profile_processing: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.test_profile_processing,
        required=True,
    ),
    DataCheckUnitType.motivation_processing: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.motivation_processing,
        required=True,
    ),
    DataCheckUnitType.growth_path_processing: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.growth_path_processing,
        required=True,
    ),
    DataCheckUnitType.achievements_processing: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.achievements_processing,
        required=True,
    ),
    DataCheckUnitType.link_validation: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.link_validation,
        required=False,
    ),
    DataCheckUnitType.video_validation: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.video_validation,
        required=False,
    ),
    DataCheckUnitType.certificate_validation: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.certificate_validation,
        required=False,
    ),
    DataCheckUnitType.signals_aggregation: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.signals_aggregation,
        required=True,
        dependencies=(
            DataCheckUnitType.test_profile_processing,
            DataCheckUnitType.motivation_processing,
            DataCheckUnitType.growth_path_processing,
            DataCheckUnitType.achievements_processing,
        ),
    ),
    DataCheckUnitType.candidate_ai_summary: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.candidate_ai_summary,
        required=True,
        dependencies=(DataCheckUnitType.signals_aggregation,),
    ),
}

TERMINAL_UNIT_STATUSES = {
    DataCheckUnitStatus.completed.value,
    DataCheckUnitStatus.failed.value,
    DataCheckUnitStatus.manual_review_required.value,
}


@dataclass(frozen=True)
class RunStatusComputation:
    status: str
    warnings: list[str]
    errors: list[str]
    explainability: list[str]
    manual_review_required: bool


def dependencies_met(*, unit: DataCheckUnitType, statuses: dict[DataCheckUnitType, str]) -> bool:
    deps = UNIT_POLICIES[unit].dependencies
    if not deps:
        return True
    for dep in deps:
        if statuses.get(dep) not in TERMINAL_UNIT_STATUSES:
            return False
    return True


def compute_run_status(statuses: dict[DataCheckUnitType, str]) -> RunStatusComputation:
    if not statuses:
        return RunStatusComputation(
            status=DataCheckRunStatus.pending.value,
            warnings=[],
            errors=[],
            explainability=[],
            manual_review_required=False,
        )

    any_started = any(s != DataCheckUnitStatus.pending.value for s in statuses.values())
    any_non_terminal = any(s not in TERMINAL_UNIT_STATUSES for s in statuses.values())
    if any_non_terminal:
        return RunStatusComputation(
            status=DataCheckRunStatus.running.value if any_started else DataCheckRunStatus.pending.value,
            warnings=[],
            errors=[],
            explainability=["Data-check processing is still running."],
            manual_review_required=False,
        )

    required_failed = []
    required_manual = []
    optional_failed = []
    optional_manual = []

    for unit, status in statuses.items():
        policy = UNIT_POLICIES[unit]
        if policy.required and status == DataCheckUnitStatus.failed.value:
            required_failed.append(unit.value)
        elif policy.required and status == DataCheckUnitStatus.manual_review_required.value:
            required_manual.append(unit.value)
        elif not policy.required and status == DataCheckUnitStatus.failed.value:
            optional_failed.append(unit.value)
        elif not policy.required and status == DataCheckUnitStatus.manual_review_required.value:
            optional_manual.append(unit.value)

    if required_failed:
        return RunStatusComputation(
            status=DataCheckRunStatus.failed.value,
            warnings=[],
            errors=[f"Required unit failed: {name}" for name in required_failed],
            explainability=["One or more required processing units failed."],
            manual_review_required=True,
        )

    partial_reasons = []
    if required_manual:
        partial_reasons.extend(f"Required unit needs manual review: {name}" for name in required_manual)
    if optional_failed:
        partial_reasons.extend(f"Optional unit failed: {name}" for name in optional_failed)
    if optional_manual:
        partial_reasons.extend(f"Optional unit needs manual review: {name}" for name in optional_manual)

    if partial_reasons:
        return RunStatusComputation(
            status=DataCheckRunStatus.partial.value,
            warnings=partial_reasons,
            errors=[],
            explainability=["Data-check is partially ready; manual attention required for some units."],
            manual_review_required=True,
        )

    return RunStatusComputation(
        status=DataCheckRunStatus.ready.value,
        warnings=[],
        errors=[],
        explainability=["All data-check units completed successfully."],
        manual_review_required=False,
    )
