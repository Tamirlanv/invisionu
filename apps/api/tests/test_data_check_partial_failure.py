from __future__ import annotations

from invision_api.models.enums import DataCheckUnitStatus, DataCheckUnitType
from invision_api.services.data_check.status_service import (
    build_commission_human_issues,
    compute_run_status,
    dependencies_met,
)


def test_data_check_failed_when_link_validation_fails() -> None:
    """link_validation is required; failure yields failed run, not partial."""
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
    assert out.status == "failed"
    assert out.manual_review_required is True
    assert any("Required unit failed: link_validation" in e for e in out.errors)


def test_data_check_partial_when_unit_needs_manual_review() -> None:
    """Partial run when a required unit needs manual review (not failure)."""
    statuses = {
        DataCheckUnitType.test_profile_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.motivation_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.growth_path_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.achievements_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.link_validation: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.video_validation: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.certificate_validation: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.signals_aggregation: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.candidate_ai_summary: DataCheckUnitStatus.manual_review_required.value,
    }
    out = compute_run_status(statuses)
    assert out.status == "partial"
    assert out.manual_review_required is True
    assert any("Required unit needs manual review" in w for w in out.warnings)


def test_incomplete_status_map_never_ready() -> None:
    """Missing unit types are treated as pending; run cannot be ready until all units are terminal."""
    statuses = {
        DataCheckUnitType.test_profile_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.motivation_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.growth_path_processing: DataCheckUnitStatus.completed.value,
    }
    out = compute_run_status(statuses)
    assert out.status == "running"


def test_empty_status_map_all_pending() -> None:
    out = compute_run_status({})
    assert out.status == "pending"


def test_signals_aggregation_waits_for_full_first_wave() -> None:
    statuses = {
        DataCheckUnitType.test_profile_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.motivation_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.growth_path_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.achievements_processing: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.link_validation: DataCheckUnitStatus.pending.value,
        DataCheckUnitType.video_validation: DataCheckUnitStatus.completed.value,
        DataCheckUnitType.certificate_validation: DataCheckUnitStatus.completed.value,
    }
    assert dependencies_met(unit=DataCheckUnitType.signals_aggregation, statuses=statuses) is False


def test_commission_human_issues_hide_technical_unit_keys() -> None:
    statuses = {
        DataCheckUnitType.growth_path_processing: DataCheckUnitStatus.manual_review_required.value,
        DataCheckUnitType.video_validation: DataCheckUnitStatus.failed.value,
    }
    warnings, errors = build_commission_human_issues(statuses)
    joined = "; ".join(warnings + errors).lower()
    assert "manual_review_required" not in joined
    assert "growth_path_processing" not in joined
    assert "video_validation" not in joined
    assert "путь" in joined
    assert "видео" in joined


def test_candidate_ai_summary_reason_uses_non_technical_name() -> None:
    statuses = {
        DataCheckUnitType.candidate_ai_summary: DataCheckUnitStatus.manual_review_required.value,
    }
    warnings, errors = build_commission_human_issues(statuses)
    joined = "; ".join(warnings + errors).lower()
    assert "итогов" in joined
    assert "сводк" in joined
    assert "ai-сводк" not in joined
