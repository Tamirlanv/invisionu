"""Orchestrator: deterministic features → LLM JSON → AIReviewMetadata + projection + audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.commission.application import audit as commission_audit
from invision_api.commission.ai.confidence.hybrid import (
    algorithmic_confidence_base,
    completeness_score,
    final_confidence,
)
from invision_api.commission.ai.input_hash import compute_input_hash
from invision_api.commission.ai.output_schema import CandidateAISummaryLLMOut
from invision_api.commission.ai.payload import build_compact_ai_payload
from invision_api.commission.ai.pipeline_version import COMMISSION_AI_PIPELINE_VERSION, COMMISSION_AI_PROMPT_VERSION
from invision_api.commission.ai.prompts import SYSTEM_PROMPT, build_user_message
from invision_api.commission.ai.signals.aggregate import aggregate_candidate_signals
from invision_api.commission.ai.source_data import (
    collect_candidate_ai_source_data,
    hash_parts_from_bundle,
    source_data_version_string,
)
from invision_api.commission.ai.text.features import build_text_block_features
from invision_api.commission.ai.validator import validate_llm_output_lenient
from invision_api.core.config import get_settings
from invision_api.models.application import AIReviewMetadata, Application
from invision_api.repositories import commission_repository
from invision_api.services.ai_provider import OpenAIProvider, get_ai_provider


@dataclass(frozen=True)
class CommissionAIPipelineResult:
    status: Literal["success", "skipped", "failed"]
    detail: str | None
    input_hash: str | None


def _latest_ai_row(db: Session, application_id: UUID) -> AIReviewMetadata | None:
    return db.scalars(
        select(AIReviewMetadata).where(AIReviewMetadata.application_id == application_id).order_by(AIReviewMetadata.created_at.desc())
    ).first()


def _should_skip(
    *,
    force: bool,
    new_hash: str,
    existing: AIReviewMetadata | None,
) -> bool:
    if force:
        return False
    if not existing or not existing.flags:
        return False
    prev = existing.flags.get("input_hash") if isinstance(existing.flags, dict) else None
    return prev == new_hash


def run_commission_ai_pipeline(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID | None,
    force: bool = False,
    provider: OpenAIProvider | None = None,
) -> CommissionAIPipelineResult:
    settings = get_settings()
    sd_ver = source_data_version_string()
    try:
        bundle = collect_candidate_ai_source_data(db, application_id)
    except ValueError as e:
        commission_audit.write_event(
            db,
            event_type="ai_summary_failed",
            entity_type="application",
            entity_id=application_id,
            actor_user_id=actor_user_id,
            metadata={"reason": str(e)},
        )
        return CommissionAIPipelineResult(status="failed", detail=str(e), input_hash=None)

    parts = hash_parts_from_bundle(bundle)
    input_hash = compute_input_hash(parts=parts, source_data_version=sd_ver)
    existing = _latest_ai_row(db, application_id)
    if _should_skip(force=force, new_hash=input_hash, existing=existing):
        return CommissionAIPipelineResult(status="skipped", detail="input_hash unchanged", input_hash=input_hash)

    sp = bundle.section_payloads
    extracts = sp.get("raw_text_extracts") or {}
    blocks = {
        "motivation": build_text_block_features(block_key="motivation", raw_text=str(extracts.get("motivation") or "")),
        "path": build_text_block_features(block_key="path", raw_text=str(extracts.get("path") or "")),
        "essay": build_text_block_features(block_key="essay", raw_text=str(extracts.get("essay") or "")),
    }
    agg = aggregate_candidate_signals(blocks)
    c0, algo_notes = algorithmic_confidence_base(blocks=blocks, aggregate=agg)
    hints = list(agg.reasons) + algo_notes

    compact = build_compact_ai_payload(
        bundle=bundle,
        blocks=blocks,
        aggregate_signals=agg,
        algorithmic_explainability_hints=hints,
        algorithmic_confidence_base=c0,
    )

    raw_out: dict[str, Any]
    try:
        prov = provider or get_ai_provider()
        raw_out = prov.committee_structured_summary(
            prompt_version=COMMISSION_AI_PROMPT_VERSION,
            compact_payload=compact,
            system_prompt=SYSTEM_PROMPT,
            user_message=build_user_message(prompt_version=COMMISSION_AI_PROMPT_VERSION, compact_payload=compact),
        )
    except Exception as e:  # noqa: BLE001 — provider / network
        commission_audit.write_event(
            db,
            event_type="ai_summary_failed",
            entity_type="application",
            entity_id=application_id,
            actor_user_id=actor_user_id,
            metadata={"error": str(e), "input_hash": input_hash},
        )
        return CommissionAIPipelineResult(status="failed", detail=str(e), input_hash=input_hash)

    out: CandidateAISummaryLLMOut = validate_llm_output_lenient(raw_out)
    comp = completeness_score(blocks)
    final_c, applied_delta = final_confidence(c0=c0, llm_delta=out.confidence_adjustment, completeness_fallback=comp)

    flags: dict[str, Any] = {
        "strengths": out.strengths,
        "weak_points": out.weak_points,
        "red_flags": out.red_flags,
        "leadership_signals": out.leadership_signals,
        "mission_fit_notes": out.mission_fit_notes,
        "key_themes": out.key_themes,
        "evidence_highlights": out.evidence_highlights,
        "possible_follow_up_topics": out.possible_follow_up_topics,
        "recommendation": out.recommendation,
        "confidence_score": final_c,
        "algorithmic_signals": {
            "numeric_rollup": agg.numeric_rollup,
            "flags": agg.flags,
        },
        "input_hash": input_hash,
        "pipeline_version": COMMISSION_AI_PIPELINE_VERSION,
        "provider": "openai",
        "llm_confidence_delta_applied": applied_delta,
        "algorithmic_confidence_base": c0,
    }

    explainability_snapshot = {
        "algorithmic_explainability": {"notes": algo_notes, "reasons": list(agg.reasons)},
        "llm_explainability": {"notes": out.explainability_notes},
        "notes": "\n".join(out.explainability_notes[:20]) if out.explainability_notes else None,
    }

    meta = AIReviewMetadata(
        application_id=application_id,
        model=settings.openai_model,
        prompt_version=COMMISSION_AI_PROMPT_VERSION,
        summary_text=out.summary_text,
        flags=flags,
        explainability_snapshot=explainability_snapshot,
        authenticity_risk_score=None,
        decision_authority="human_only",
    )
    db.add(meta)
    db.flush()

    app = db.get(Application, application_id)
    if app:
        commission_repository.upsert_projection_for_application(db, app)

    commission_audit.write_event(
        db,
        event_type="ai_summary_generated",
        entity_type="application",
        entity_id=application_id,
        actor_user_id=actor_user_id,
        metadata={"input_hash": input_hash, "model": settings.openai_model},
    )
    return CommissionAIPipelineResult(status="success", detail=None, input_hash=input_hash)
