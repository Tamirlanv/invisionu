from __future__ import annotations

from invision_api.models.enums import DataCheckUnitStatus, DataCheckUnitType
from invision_api.services.data_check.status_service import compute_run_status


def test_data_check_partial_when_optional_unit_fails() -> None:
    statuses = {
        DataCheckUnitType.test_profile_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.motivation_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.growth_path_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.achievements_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.link_validation: DataCheckUnitStatus.failed.value,
        DataCheckUnitType.video_validation: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.certificate_validation: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.signals_aggregation: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.candidate_ai_summary: DataCheckUnitStatus.completed.value,
    }
    out = compute_run_status(statuses)
    assert out.status == "partial"
    assert out.manual_review_required is True
    assert any("Optional unit failed" in item for item in out.warnings)
