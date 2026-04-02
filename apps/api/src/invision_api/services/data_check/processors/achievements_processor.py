from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import AnalysisRunStatus, SectionKey
from invision_api.repositories import admissions_repository
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section

_IMPACT_TERMS = ("результат", "увелич", "сниз", "побед", "лидер", "команд")


def run_achievements_processing(db: Session, *, application_id: UUID) -> UnitExecutionResult:
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.achievements_activities,
    )
    if not validated:
        return UnitExecutionResult(
            status="failed",
            errors=["Achievements section is missing or invalid."],
            explainability=["Не удалось валидировать раздел достижений."],
        )

    text = (validated.achievements_text or "").strip()
    words = [w for w in re.split(r"\s+", text) if w]
    lower = text.lower()
    impact_hits = sum(1 for t in _IMPACT_TERMS if t in lower)
    links = [{"label": l.label, "url": l.url, "linkType": l.link_type} for l in (validated.links or []) if l.url]
    signals = {
        "word_count": len(words),
        "impact_markers": impact_hits,
        "links_count": len(links),
        "has_role": bool(validated.role.strip()),
        "has_year": bool(validated.year.strip()),
    }
    summary = text[:700]
    manual = len(words) < 30 or (not links and impact_hits == 0)

    admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key="achievements_activities",
        source_kind="post_submit",
        source_document_id=None,
        model=None,
        status=AnalysisRunStatus.completed.value,
        dimensions=signals,
        explanations={"summary": summary, "signals": signals, "links": links},
        flags={"manual_review_required": manual},
    )

    explainability = [
        "Сигналы достижений рассчитаны по тексту, маркерам результата и приложенным ссылкам.",
    ]
    if manual:
        explainability.append("Недостаточно подтверждающих сигналов, требуется ручная проверка.")
    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={"summary": summary, "signals": signals, "links": links},
        explainability=explainability,
        manual_review_required=manual,
    )
