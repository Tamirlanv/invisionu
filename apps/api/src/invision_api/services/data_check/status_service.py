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
        required=True,
    ),
    DataCheckUnitType.video_validation: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.video_validation,
        required=True,
    ),
    DataCheckUnitType.certificate_validation: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.certificate_validation,
        required=True,
    ),
    DataCheckUnitType.signals_aggregation: DataCheckUnitPolicy(
        unit_type=DataCheckUnitType.signals_aggregation,
        required=True,
        dependencies=(
            DataCheckUnitType.test_profile_processing,
            DataCheckUnitType.motivation_processing,
            DataCheckUnitType.growth_path_processing,
            DataCheckUnitType.achievements_processing,
            DataCheckUnitType.link_validation,
            DataCheckUnitType.video_validation,
            DataCheckUnitType.certificate_validation,
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

_UNIT_FAILED_REASON_RU: dict[DataCheckUnitType, str] = {
    DataCheckUnitType.test_profile_processing: "Не удалось обработать результаты теста.",
    DataCheckUnitType.motivation_processing: "Не удалось полностью обработать раздел «Мотивация».",
    DataCheckUnitType.growth_path_processing: "Не удалось полностью обработать раздел «Путь».",
    DataCheckUnitType.achievements_processing: "Не удалось полностью обработать раздел «Достижения».",
    DataCheckUnitType.link_validation: "Не удалось корректно проверить ссылки.",
    DataCheckUnitType.video_validation: "Не удалось корректно обработать видео-презентацию.",
    DataCheckUnitType.certificate_validation: "Не удалось автоматически обработать сертификаты.",
    DataCheckUnitType.signals_aggregation: "Не удалось собрать полную сводку сигналов по заявке.",
    DataCheckUnitType.candidate_ai_summary: "Не удалось собрать итоговую сводку.",
}

_UNIT_MANUAL_REASON_RU: dict[DataCheckUnitType, str] = {
    DataCheckUnitType.test_profile_processing: "Требуется ручная проверка результатов теста.",
    DataCheckUnitType.motivation_processing: "Требуется ручная проверка раздела «Мотивация».",
    DataCheckUnitType.growth_path_processing: "Требуется ручная проверка раздела «Путь».",
    DataCheckUnitType.achievements_processing: "Требуется ручная проверка раздела «Достижения».",
    DataCheckUnitType.link_validation: "Требуется ручная проверка ссылок.",
    DataCheckUnitType.video_validation: "Не удалось корректно обработать видео-презентацию.",
    DataCheckUnitType.certificate_validation: "Не удалось автоматически обработать сертификаты.",
    DataCheckUnitType.signals_aggregation: "Часть итоговых сводок требует ручной проверки.",
    DataCheckUnitType.candidate_ai_summary: "Не удалось собрать итоговую сводку.",
}


@dataclass(frozen=True)
class RunStatusComputation:
    status: str
    warnings: list[str]
    errors: list[str]
    explainability: list[str]
    manual_review_required: bool


def build_commission_human_issues(statuses: dict[DataCheckUnitType, str]) -> tuple[list[str], list[str]]:
    """Return human-readable (RU) warnings/errors from canonical unit statuses."""
    warnings: list[str] = []
    errors: list[str] = []
    for unit in UNIT_POLICIES:
        status = statuses.get(unit, DataCheckUnitStatus.pending.value)
        if status == DataCheckUnitStatus.manual_review_required.value:
            warnings.append(_UNIT_MANUAL_REASON_RU.get(unit, "Требуется ручная проверка этого блока."))
        elif status == DataCheckUnitStatus.failed.value:
            errors.append(_UNIT_FAILED_REASON_RU.get(unit, "Не удалось обработать этот блок автоматически."))

    # Keep stable order, remove duplicates.
    return list(dict.fromkeys(warnings)), list(dict.fromkeys(errors))


def dependencies_met(*, unit: DataCheckUnitType, statuses: dict[DataCheckUnitType, str]) -> bool:
    deps = UNIT_POLICIES[unit].dependencies
    if not deps:
        return True
    for dep in deps:
        if statuses.get(dep) not in TERMINAL_UNIT_STATUSES:
            return False
    return True


def compute_run_status(statuses: dict[DataCheckUnitType, str]) -> RunStatusComputation:
    """Aggregate run status from per-unit statuses.

    Every unit type in ``UNIT_POLICIES`` must be accounted for. Missing keys are treated as
    ``pending`` so an incomplete map cannot yield ``ready`` (avoids premature auto-advance).
    Unknown keys in ``statuses`` are ignored.
    """
    canonical: dict[DataCheckUnitType, str] = {}
    for unit in UNIT_POLICIES:
        canonical[unit] = statuses[unit] if unit in statuses else DataCheckUnitStatus.pending.value

    any_started = any(s != DataCheckUnitStatus.pending.value for s in canonical.values())
    any_non_terminal = any(s not in TERMINAL_UNIT_STATUSES for s in canonical.values())
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

    for unit, status in canonical.items():
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
