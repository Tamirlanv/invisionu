from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.repositories import data_check_repository
from invision_api.services.data_check.contracts import UnitExecutionResult


def _score_from_payload(payload: dict | None, *keys: str) -> float:
    if not isinstance(payload, dict):
        return 0.0
    score = 0.0
    for key in keys:
        val = payload.get(key)
        if isinstance(val, bool):
            score += 1.0 if val else 0.0
        elif isinstance(val, (int, float)):
            score += float(val)
    return score


def run_signals_aggregation(db: Session, *, application_id: UUID, run_id: UUID) -> UnitExecutionResult:
    unit_results = data_check_repository.list_unit_results_for_run(db, run_id)
    by_unit = {r.unit_type: r for r in unit_results}

    test_payload = (by_unit.get("test_profile_processing") or {}).result_payload if by_unit.get("test_profile_processing") else {}
    motivation_payload = (by_unit.get("motivation_processing") or {}).result_payload if by_unit.get("motivation_processing") else {}
    growth_payload = (by_unit.get("growth_path_processing") or {}).result_payload if by_unit.get("growth_path_processing") else {}
    achievements_payload = (by_unit.get("achievements_processing") or {}).result_payload if by_unit.get("achievements_processing") else {}

    dominant = ((test_payload or {}).get("profile") or {}).get("dominantTrait")
    top_traits = ((test_payload or {}).get("profile") or {}).get("ranking") or []
    top_trait_score = float(top_traits[0]["score"]) if top_traits else 0.0

    motivation_signals = ((motivation_payload or {}).get("signals") or {})
    growth_signals = ((growth_payload or {}).get("section_signals") or {})
    achievement_signals = ((achievements_payload or {}).get("signals") or {})

    leadership_score = _score_from_payload(achievement_signals, "impact_markers") + (
        1.5 if dominant in {"INI", "COL"} else 0.0
    )
    initiative_score = _score_from_payload(motivation_signals, "motivation_density") + (
        1.0 if dominant == "INI" else 0.0
    )
    resilience_score = float((growth_signals or {}).get("resilience_score") or 0.0) + (1.0 if dominant == "RES" else 0.0)
    responsibility_score = (1.0 if dominant == "RES" else 0.0) + min(2.0, top_trait_score / 10.0)
    communication_score = _score_from_payload(motivation_signals, "avg_sentence_len", "evidence_density")

    attention_flags: list[str] = []
    authenticity_concerns: list[str] = []
    for row in unit_results:
        if row.manual_review_required:
            attention_flags.append(f"{row.unit_type}:manual_review")
        if row.status == "failed":
            attention_flags.append(f"{row.unit_type}:failed")
        if row.unit_type in {"link_validation", "video_validation", "certificate_validation"} and row.status != "completed":
            authenticity_concerns.append(f"{row.unit_type}_not_completed")

    manual = bool(attention_flags)
    readiness = "partial_processing_ready" if manual else "ready_for_commission"
    explainability = [
        "Сигналы агрегированы из algorithmic unit outputs.",
        f"Dominant trait: {dominant or 'unknown'}.",
    ]

    aggregate = data_check_repository.upsert_candidate_signals_aggregate(
        db,
        run_id=run_id,
        application_id=application_id,
        leadership_signals={"score": round(leadership_score, 3)},
        initiative_signals={"score": round(initiative_score, 3)},
        resilience_signals={"score": round(resilience_score, 3)},
        responsibility_signals={"score": round(responsibility_score, 3)},
        growth_signals={"score": round(float((growth_signals or {}).get("growth_score") or 0.0), 3)},
        mission_fit_signals={"score": round(float(motivation_signals.get("motivation_density") or 0.0), 3)},
        strong_motivation_signals={"score": round(float(motivation_signals.get("evidence_density") or 0.0), 3)},
        communication_signals={"score": round(communication_score, 3)},
        attention_flags=attention_flags,
        authenticity_concern_signals=authenticity_concerns,
        review_readiness_status=readiness,
        manual_review_required=manual,
        explainability=explainability,
    )
    payload = {
        "aggregateId": str(aggregate.id),
        "readiness": readiness,
        "attentionFlags": attention_flags,
        "authenticityConcernSignals": authenticity_concerns,
    }
    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload=payload,
        explainability=explainability,
        manual_review_required=manual,
    )
