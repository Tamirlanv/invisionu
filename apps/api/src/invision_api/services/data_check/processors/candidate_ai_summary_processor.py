from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.core.config import get_settings
from invision_api.models.application import AIReviewMetadata
from invision_api.repositories import data_check_repository
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.llm.llm_summary_client import LLMSummaryClient


def _fallback_summary(*, aggregate_payload: dict[str, Any], attention_flags: list[str]) -> str:
    readiness = aggregate_payload.get("readiness") or "unknown"
    flags = ", ".join(attention_flags[:6]) if attention_flags else "нет"
    return (
        f"Автоматический сводный профиль готов. Статус готовности: {readiness}. "
        f"Флаги внимания: {flags}. Рекомендуется итоговый human review перед решением."
    )


def run_candidate_ai_summary_processing(db: Session, *, application_id: UUID, run_id: UUID) -> UnitExecutionResult:
    aggregate = data_check_repository.get_candidate_signals_aggregate(db, application_id)
    if not aggregate:
        return UnitExecutionResult(
            status="failed",
            errors=["Signals aggregate is missing."],
            explainability=["Невозможно собрать AI summary без агрегированных сигналов."],
        )

    unit_results = data_check_repository.list_unit_results_for_run(db, run_id)
    compact_units = {
        row.unit_type: {
            "status": row.status,
            "payload": row.result_payload,
            "manual_review_required": row.manual_review_required,
        }
        for row in unit_results
    }
    llm_payload = {
        "application_id": str(application_id),
        "run_id": str(run_id),
        "aggregate": {
            "leadership": aggregate.leadership_signals,
            "initiative": aggregate.initiative_signals,
            "resilience": aggregate.resilience_signals,
            "responsibility": aggregate.responsibility_signals,
            "growth": aggregate.growth_signals,
            "mission_fit": aggregate.mission_fit_signals,
            "strong_motivation": aggregate.strong_motivation_signals,
            "communication": aggregate.communication_signals,
            "attention_flags": aggregate.attention_flags,
            "authenticity_concern_signals": aggregate.authenticity_concern_signals,
            "review_readiness_status": aggregate.review_readiness_status,
        },
        "unit_outputs": compact_units,
    }

    llm = LLMSummaryClient()
    llm_out = None
    if llm.enabled:
        try:
            llm_out = llm.summarize(payload=llm_payload)
        except Exception:  # noqa: BLE001
            llm_out = None

    summary_text = None
    key_points: list[str] = []
    provider_name = "internal_fallback"
    if llm_out:
        summary_text = str(llm_out.get("summary") or "").strip() or None
        raw_points = llm_out.get("key_points")
        if isinstance(raw_points, list):
            key_points = [str(p) for p in raw_points if str(p).strip()]
        provider_name = str(llm_out.get("provider") or "internal_llm")

    if not summary_text:
        summary_text = _fallback_summary(
            aggregate_payload={"readiness": aggregate.review_readiness_status},
            attention_flags=aggregate.attention_flags or [],
        )

    settings = get_settings()
    meta = AIReviewMetadata(
        application_id=application_id,
        model=settings.openai_model if llm_out else "internal_fallback",
        prompt_version="data_check_v1",
        summary_text=summary_text,
        flags={
            "provider": provider_name,
            "decision_authority": "human_only",
            "key_points": key_points,
            "data_check_run_id": str(run_id),
        },
        explainability_snapshot={
            "source": "data_check_candidate_ai_summary",
            "notes": ["Summary is generated from structured data-check signals only."],
        },
        authenticity_risk_score=None,
        decision_authority="human_only",
    )
    db.add(meta)
    db.flush()

    manual = bool(aggregate.manual_review_required)
    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={
            "aiReviewId": str(meta.id),
            "summary": summary_text,
            "provider": provider_name,
        },
        explainability=["Итоговый AI summary построен только на структурированных сигналах."],
        manual_review_required=manual,
    )
