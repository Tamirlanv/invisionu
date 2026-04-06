from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import AnalysisRunStatus, SectionKey
from invision_api.repositories import admissions_repository
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section
from invision_api.services.growth_path.llm_summary import summarize_growth_path_compact
from invision_api.services.growth_path.pipeline import analyze_growth_answers


def _evaluate_growth_path_quality_gate(
    per_question: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    per_question = per_question or {}
    spam_questions: list[str] = []
    reason_counts: Counter[str] = Counter()

    for qid, block in per_question.items():
        spam = (block or {}).get("spam_check") or {}
        if spam.get("ok") is False:
            spam_questions.append(str(qid))
            reasons = spam.get("reasons")
            if isinstance(reasons, list):
                for reason in reasons:
                    if reason:
                        reason_counts[str(reason)] += 1

    flagged_questions = len(spam_questions)
    spam_phrase_count = reason_counts.get("spam_phrase", 0)
    low_lexical_count = reason_counts.get("low_lexical_diversity", 0)
    high_repetition_count = reason_counts.get("high_repetition", 0)

    manual_reason_code: str | None = None
    if spam_phrase_count >= 2:
        manual_reason_code = "severe_spam_phrase_multi"
    elif spam_phrase_count >= 1 and flagged_questions >= 2:
        manual_reason_code = "severe_spam_phrase_plus_multi"
    elif flagged_questions >= 3:
        manual_reason_code = "severe_multi_question_low_quality"
    elif low_lexical_count >= 2 and high_repetition_count >= 2:
        manual_reason_code = "severe_repetition_low_diversity"

    manual = manual_reason_code is not None
    mild_quality_flags: list[str] = []
    if not manual and flagged_questions > 0:
        mild_quality_flags.append("mild_quality_risk")
    if not manual and spam_phrase_count == 1:
        mild_quality_flags.append("single_spam_phrase")
    if not manual and low_lexical_count >= 1 and high_repetition_count >= 1:
        mild_quality_flags.append("lexical_repetition_risk")

    return {
        "manual": manual,
        "manual_reason_code": manual_reason_code,
        "spam_questions": spam_questions,
        "spam_reason_counts": dict(reason_counts),
        "mild_quality_flags": mild_quality_flags,
        "flagged_questions_count": flagged_questions,
    }


def run_growth_path_processing(db: Session, *, application_id: UUID) -> UnitExecutionResult:
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.growth_journey,
    )
    if not validated:
        return UnitExecutionResult(
            status="failed",
            errors=["Growth path section is missing or invalid."],
            explainability=["Не удалось валидировать раздел пути роста."],
        )

    analysis = analyze_growth_answers(validated)
    compact_llm = {
        "version": 1,
        "computed_at": analysis["computed_at"],
        "section_signals": analysis["section_signals"],
        "questions": analysis["compact_questions"],
    }
    llm_summary = summarize_growth_path_compact(compact_llm)
    quality_gate = _evaluate_growth_path_quality_gate(analysis.get("per_question"))

    payload = {
        "computed_at": analysis["computed_at"],
        "section_signals": analysis["section_signals"],
        "per_question": analysis["per_question"],
        "llm_summary": llm_summary,
        "quality_gate": quality_gate,
    }
    spam_flags = quality_gate["spam_questions"]
    manual = bool(quality_gate["manual"])
    manual_reason_code = quality_gate.get("manual_reason_code")
    mild_quality_flags = quality_gate.get("mild_quality_flags") or []

    admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key="growth_journey",
        source_kind="post_submit",
        source_document_id=validated.growth_document_id,
        model=None,
        status=AnalysisRunStatus.completed.value,
        dimensions={"section_signals": analysis["section_signals"]},
        explanations=payload,
        flags={
            "manual_review_required": manual,
            "spam_questions": spam_flags,
            "manual_reason_code": manual_reason_code,
            "spam_reason_counts": quality_gate.get("spam_reason_counts", {}),
            "mild_quality_flags": mild_quality_flags,
        },
    )

    explainability = ["Раздел пути роста обработан через существующий growth_path pipeline."]
    if spam_flags and manual:
        explainability.append(
            f"Требуется ручная проверка: найдены выраженные признаки низкого качества в вопросах {', '.join(spam_flags)}."
        )
        if manual_reason_code:
            explainability.append(f"Код причины ручной проверки: {manual_reason_code}.")
    elif spam_flags:
        explainability.append(
            f"Обнаружены мягкие сигналы качества в вопросах {', '.join(spam_flags)}; автоматическая обработка сохранена."
        )

    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload=payload,
        explainability=explainability,
        manual_review_required=manual,
    )
