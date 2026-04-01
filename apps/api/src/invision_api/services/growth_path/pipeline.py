"""Orchestrate preprocessing, spam checks, LLM summary, and TextAnalysisRun."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from invision_api.core.config import get_settings
from invision_api.models.enums import AnalysisRunStatus
from invision_api.repositories import admissions_repository
from invision_api.services.growth_path.config import GROWTH_QUESTION_ORDER
from invision_api.services.growth_path.key_sentences import extract_key_sentences
from invision_api.services.growth_path.llm_summary import summarize_growth_path_compact
from invision_api.services.growth_path.normalize import normalize_growth_text
from invision_api.services.growth_path.signals import aggregate_section_signals, build_per_question_block
from invision_api.services.growth_path.spam_rules import check_answer_spam
from invision_api.services.section_payloads import GrowthJourneySectionPayload


def process_growth_journey_save(
    db: Session,
    application_id: UUID,
    validated: GrowthJourneySectionPayload,
) -> dict[str, Any]:
    """
    Run algorithmic pipeline; may raise HTTP 422 on spam/low-effort.
    Returns `computed` dict to merge into section payload.
    Also persists a TextAnalysisRun row.
    """
    per_question: dict[str, dict[str, Any]] = {}
    compact_questions: dict[str, Any] = {}

    for qid in GROWTH_QUESTION_ORDER:
        raw = validated.answers[qid].text
        text = normalize_growth_text(raw)
        spam = check_answer_spam(text)
        if not spam.ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Текст одного из ответов выглядит слишком общим или нерелевантным. Опишите личный опыт подробнее.",
            )
        block = build_per_question_block(qid=qid, normalized_text=text)
        keys = extract_key_sentences(text, max_sentences=2)
        per_question[qid] = {**block, "key_sentences": keys}
        compact_questions[qid] = {
            "stats": block["stats"],
            "heuristics": block["heuristics"],
            "key_sentences": keys,
        }

    section_signals = aggregate_section_signals(per_question)
    computed_at = datetime.now(tz=UTC).isoformat()

    compact_llm: dict[str, Any] = {
        "version": 1,
        "computed_at": computed_at,
        "section_signals": section_signals,
        "questions": compact_questions,
    }

    summary = summarize_growth_path_compact(compact_llm)

    computed: dict[str, Any] = {
        "computed_at": computed_at,
        "per_question": per_question,
        "section_signals": section_signals,
        "llm_summary": summary or None,
    }

    settings = get_settings()
    model_name = settings.openai_api_key and settings.openai_model or None
    status_val = AnalysisRunStatus.completed.value if summary else AnalysisRunStatus.skipped.value

    admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key="growth_journey",
        source_kind="inline",
        source_document_id=None,
        model=model_name,
        status=status_val,
        dimensions={"section_signals": section_signals},
        explanations={
            "llm_summary": summary,
            "structured_compact": compact_llm,
            "per_question": per_question,
        },
        flags={"has_llm_summary": bool(summary)},
    )

    return computed
