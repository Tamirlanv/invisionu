from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import AnalysisRunStatus, SectionKey
from invision_api.repositories import admissions_repository
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section
from invision_api.services.growth_path.llm_summary import summarize_growth_path_compact
from invision_api.services.growth_path.pipeline import analyze_growth_answers


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
    payload = {
        "computed_at": analysis["computed_at"],
        "section_signals": analysis["section_signals"],
        "per_question": analysis["per_question"],
        "llm_summary": llm_summary,
    }
    spam_flags = []
    for qid, block in (analysis.get("per_question") or {}).items():
        spam = (block or {}).get("spam_check") or {}
        if spam.get("ok") is False:
            spam_flags.append(qid)
    manual = bool(spam_flags)

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
        flags={"manual_review_required": manual, "spam_questions": spam_flags},
    )

    explainability = ["Раздел пути роста обработан через существующий growth_path pipeline."]
    if spam_flags:
        explainability.append(f"Обнаружены вопросы с признаками спама: {', '.join(spam_flags)}.")
    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload=payload,
        explainability=explainability,
        manual_review_required=manual,
    )
