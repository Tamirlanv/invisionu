from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import AnalysisRunStatus, SectionKey
from invision_api.repositories import admissions_repository
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section

_MOTIVATION_TERMS = ("цель", "мисси", "вклад", "помочь", "разв", "обществ")
_EVIDENCE_TERMS = ("пример", "проект", "инициатив", "достиг", "результат")


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[.!?]+", text) if p.strip()]
    return parts


def run_motivation_processing(db: Session, *, application_id: UUID) -> UnitExecutionResult:
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.motivation_goals,
    )
    if not validated:
        return UnitExecutionResult(
            status="failed",
            errors=["Motivation section is missing or invalid."],
            explainability=["Не удалось валидировать раздел мотивации."],
        )

    text = validated.narrative.strip()
    words = [w for w in re.split(r"\s+", text) if w]
    sentences = _sentences(text)
    lower = text.lower()
    motivation_hits = sum(1 for term in _MOTIVATION_TERMS if term in lower)
    evidence_hits = sum(1 for term in _EVIDENCE_TERMS if term in lower)
    avg_sentence_len = (len(words) / len(sentences)) if sentences else 0.0

    summary = " ".join(sentences[:3])[:700]
    signals = {
        "motivation_density": round(min(1.0, motivation_hits / 4), 3),
        "evidence_density": round(min(1.0, evidence_hits / 4), 3),
        "avg_sentence_len": round(avg_sentence_len, 2),
        "word_count": len(words),
        "char_count": len(text),
    }
    manual = len(words) < 70
    explainability = [
        "Сигналы построены алгоритмически по плотности мотивационных/доказательных маркеров.",
        f"Текст содержит {len(words)} слов и {len(sentences)} предложений.",
    ]
    if manual:
        explainability.append("Короткий текст мотивации — нужен ручной просмотр комиссией.")

    admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key="motivation_goals",
        source_kind="post_submit",
        source_document_id=validated.motivation_document_id,
        model=None,
        status=AnalysisRunStatus.completed.value,
        dimensions=signals,
        explanations={"summary": summary, "signals": signals},
        flags={"manual_review_required": manual},
    )

    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={"summary": summary, "signals": signals},
        explainability=explainability,
        manual_review_required=manual,
    )
