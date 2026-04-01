"""Collect structured commission AI inputs from Application + projection + optional reviewer context."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from invision_api.commission.ai.pipeline_version import COMMISSION_AI_PIPELINE_VERSION
from invision_api.commission.ai.types import CandidateContext, CommissionAISourceBundle
from invision_api.models.application import Application, InternalTestAnswer
from invision_api.repositories import commission_repository


def _motivation_narrative(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("narrative") or "").strip()


def _growth_path_text(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        return ""
    parts: list[str] = []
    for qid in ("q1", "q2", "q3", "q4", "q5"):
        a = answers.get(qid)
        if isinstance(a, dict):
            parts.append(str(a.get("text") or "").strip())
    return "\n\n".join(p for p in parts if p)


def _essay_text(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    for k in ("narrative", "body", "text", "content", "essay_text"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _portfolio_compact(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    items = payload.get("items")
    if isinstance(items, list):
        out: list[dict[str, str]] = []
        for it in items[:12]:
            if isinstance(it, dict):
                out.append(
                    {
                        "title": str(it.get("title") or "")[:200],
                        "summary": str(it.get("impact_summary") or it.get("description") or it.get("outcome") or "")[:400],
                    }
                )
        return {"item_count": len(items), "items": out}
    notes = payload.get("notes") or payload.get("description")
    if isinstance(notes, str) and notes.strip():
        return {"notes": notes.strip()[:800]}
    return {}


def _structured_test_profile(db: Session, application_id: UUID) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(InternalTestAnswer)
            .where(InternalTestAnswer.application_id == application_id)
            .options(joinedload(InternalTestAnswer.question))
        ).all()
    )
    if not rows:
        return {"present": False}
    finalized = [r for r in rows if r.is_finalized]
    types: dict[str, int] = {}
    text_chars = 0
    for r in finalized:
        q = r.question
        qt = q.question_type if q else "unknown"
        types[qt] = types.get(qt, 0) + 1
        if r.text_answer:
            text_chars += min(len(r.text_answer), 2000)
    return {
        "present": True,
        "answer_rows": len(rows),
        "finalized_count": len(finalized),
        "question_types": types,
        "open_text_char_bucket": min(8000, text_chars),
    }


def _reviewer_context_block(db: Session, application_id: UUID) -> dict[str, Any] | None:
    rubric = commission_repository.list_rubric_scores(db, application_id=application_id)
    recs = commission_repository.list_internal_recommendations(db, application_id=application_id)
    if not rubric and not recs:
        return None
    rubric_compact: list[dict[str, Any]] = []
    for r in rubric[:30]:
        rubric_compact.append({"rubric": r.rubric, "score": r.score})
    rec_compact: list[dict[str, Any]] = []
    for x in recs[:10]:
        rec_compact.append({"recommendation": x.recommendation, "has_comment": bool(x.reason_comment)})
    return {
        "disclaimer": "Reviewer inputs are not ground truth; use only as secondary context.",
        "rubric": rubric_compact,
        "internal_recommendations": rec_compact,
    }


def load_application_for_ai(db: Session, application_id: UUID) -> Application | None:
    return db.scalars(
        select(Application)
        .where(Application.id == application_id)
        .options(selectinload(Application.section_states))
    ).first()


def collect_candidate_ai_source_data(db: Session, application_id: UUID) -> CommissionAISourceBundle:
    app = load_application_for_ai(db, application_id)
    if not app:
        raise ValueError("application not found")
    row = commission_repository.upsert_projection_for_application(db, app)
    sections = {s.section_key: s.payload for s in app.section_states}

    ctx = CandidateContext(
        full_name=(row.candidate_full_name or "").strip() or None,
        program=row.program,
        city=row.city,
        age=row.age,
        submitted_at_iso=row.submitted_at.isoformat() if row.submitted_at else None,
    )

    motivation = sections.get("motivation_letter") if isinstance(sections.get("motivation_letter"), dict) else {}
    growth = sections.get("growth_journey") if isinstance(sections.get("growth_journey"), dict) else {}
    essay = sections.get("essay") if isinstance(sections.get("essay"), dict) else {}
    portfolio = sections.get("portfolio") if isinstance(sections.get("portfolio"), dict) else {}

    bundle = CommissionAISourceBundle(
        application_id=str(app.id),
        candidate=ctx,
        section_payloads={
            "motivation_letter": motivation,
            "growth_journey": growth,
            "essay": essay,
            "portfolio": portfolio,
            "internal_test_section": sections.get("internal_test") if isinstance(sections.get("internal_test"), dict) else {},
            "raw_text_extracts": {
                "motivation": _motivation_narrative(motivation),
                "path": _growth_path_text(growth),
                "essay": _essay_text(essay),
            },
            "portfolio_compact": _portfolio_compact(portfolio),
            "structured_test_profile": _structured_test_profile(db, app.id),
        },
        reviewer_context=_reviewer_context_block(db, app.id),
    )
    return bundle


def hash_parts_from_bundle(bundle: CommissionAISourceBundle) -> dict[str, Any]:
    """Deterministic subset for input_hash."""
    sp = bundle.section_payloads
    extracts = sp.get("raw_text_extracts") or {}
    return {
        "pipeline_version": COMMISSION_AI_PIPELINE_VERSION,
        "motivation": extracts.get("motivation") or "",
        "path": extracts.get("path") or "",
        "essay": extracts.get("essay") or "",
        "portfolio_compact": sp.get("portfolio_compact") or {},
        "structured_test_profile": sp.get("structured_test_profile") or {},
        "candidate": {
            "program": bundle.candidate.program,
            "submitted_at": bundle.candidate.submitted_at_iso,
        },
        "reviewer_context": bundle.reviewer_context,
    }


def source_data_version_string() -> str:
    return f"{COMMISSION_AI_PIPELINE_VERSION}_sd1"
