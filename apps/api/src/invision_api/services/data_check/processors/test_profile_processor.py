from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import AnalysisRunStatus
from invision_api.repositories import admissions_repository
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.personality_profile_service import build_personality_profile_snapshot


def run_test_profile_processing(db: Session, *, application_id: UUID) -> UnitExecutionResult:
    profile = build_personality_profile_snapshot(
        db,
        application_id=application_id,
        lang="ru",
        include_non_finalized=True,
    )
    answer_count = int(((profile.get("meta") or {}).get("answerCount")) or 0)
    manual = answer_count < 30
    notes = [
        "Профиль рассчитан из сохраненных ответов внутреннего теста.",
        "Это поведенческий профиль для поддержки комиссии, не решение о зачислении.",
    ]
    if manual:
        notes.append("Ответов меньше 30, требуется ручная проверка интерпретации профиля.")

    admissions_repository.create_text_analysis_run(
        db,
        application_id,
        block_key="test_profile",
        source_kind="post_submit",
        source_document_id=None,
        model=None,
        status=AnalysisRunStatus.completed.value,
        dimensions={"profileType": profile.get("profileType"), "dominantTrait": profile.get("dominantTrait")},
        explanations={"profile": profile},
        flags={"manual_review_required": manual},
    )

    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={
            "profileType": profile.get("profileType"),
            "dominantTrait": profile.get("dominantTrait"),
            "secondaryTrait": profile.get("secondaryTrait"),
            "weakestTrait": profile.get("weakestTrait"),
            "profile": profile,
        },
        explainability=notes,
        manual_review_required=manual,
    )
