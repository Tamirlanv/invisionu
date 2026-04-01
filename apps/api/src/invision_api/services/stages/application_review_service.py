"""Application review: packet aggregation and snapshot."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.application import Application
from invision_api.models.enums import ApplicationStage, SectionKey
from invision_api.repositories import admissions_repository
from invision_api.services import explainability_service
from invision_api.services import personality_profile_service
from invision_api.services.stage_transition_policy import TransitionContext, TransitionName, apply_transition


def _growth_path_committee_view(sections: dict[str, Any], explainability: dict[str, Any]) -> dict[str, Any]:
    """Compact signals + LLM summary for committee; payload.computed preferred, else latest TextAnalysisRun."""
    key = SectionKey.growth_journey.value
    payload = sections.get(key) if isinstance(sections, dict) else None
    out: dict[str, Any] = {}
    if isinstance(payload, dict):
        comp = payload.get("computed")
        if isinstance(comp, dict):
            out["llm_summary"] = comp.get("llm_summary")
            out["section_signals"] = comp.get("section_signals")
            out["computed_at"] = comp.get("computed_at")
    if out.get("llm_summary") is None and out.get("section_signals") is None:
        by_block = explainability.get("by_block") if isinstance(explainability, dict) else None
        run = (by_block or {}).get("growth_journey") if isinstance(by_block, dict) else None
        if isinstance(run, dict):
            expl = run.get("explanations")
            if isinstance(expl, dict):
                out["llm_summary"] = expl.get("llm_summary")
                structured = expl.get("structured_compact")
                if isinstance(structured, dict) and "section_signals" in structured:
                    out["section_signals"] = structured["section_signals"]
    return out


def build_review_packet(db: Session, app: Application) -> dict[str, Any]:
    sections = {s.section_key: s.payload for s in app.section_states}
    exp = explainability_service.build_explainability_snapshot(db, app.id)
    return {
        "application_id": str(app.id),
        "sections": sections,
        "growth_path_committee": _growth_path_committee_view(sections, exp),
        "explainability": {
            **exp,
            "personality_profile": personality_profile_service.build_personality_profile_snapshot(
                db, application_id=app.id, lang="ru"
            ),
        },
    }


def upsert_snapshot_from_packet(
    db: Session,
    application_id: UUID,
    *,
    review_status: str = "in_progress",
) -> Any:
    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        raise ValueError("application not found")
    packet = build_review_packet(db, app)
    exp = packet.get("explainability") or explainability_service.build_explainability_snapshot(db, application_id)
    return admissions_repository.upsert_review_snapshot(
        db,
        application_id,
        review_status=review_status,
        review_packet=packet,
        summary_by_block=(exp.get("by_block") if isinstance(exp, dict) else None),
        explainability_snapshot=exp,
    )


def transition_to_interview(
    db: Session,
    app: Application,
    *,
    actor_user_id: UUID | None,
) -> Application:
    if app.current_stage != ApplicationStage.application_review.value:
        raise ValueError("application must be in application_review stage")
    ctx = TransitionContext(
        application_id=app.id,
        transition=TransitionName.review_complete,
        actor_user_id=actor_user_id,
        actor_type="committee",
    )
    return apply_transition(db, app, ctx)
