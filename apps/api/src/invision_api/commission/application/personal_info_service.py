from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.commission.application import service as commission_service
from invision_api.commission.application.personal_info_mapper import build_personal_info_view
from invision_api.commission.application.personal_info_validators import (
    load_submitted_application_or_404,
    resolve_commission_actions,
)
from invision_api.models.enums import DataCheckUnitType
from invision_api.models.user import User
from invision_api.repositories import commission_repository, data_check_repository, document_repository, internal_test_repository
from invision_api.services.application_service import collect_referenced_document_ids
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES, compute_run_status
from invision_api.services.personality_profile_service import build_personality_profile_snapshot


def _build_processing_status(db: Session, application_id: UUID) -> dict[str, Any] | None:
    runs = data_check_repository.list_runs_for_application(db, application_id)
    if not runs:
        return None
    run = runs[0]
    checks = data_check_repository.list_checks_for_run(db, run.id)
    if not checks:
        return None

    status_map: dict[DataCheckUnitType, str] = {}
    for c in checks:
        try:
            status_map[DataCheckUnitType(c.check_type)] = c.status
        except ValueError:
            continue

    run_computed = compute_run_status(status_map)
    completed = sum(1 for s in status_map.values() if s in TERMINAL_UNIT_STATUSES)

    return {
        "overall": run_computed.status,
        "completedCount": completed,
        "totalCount": len(status_map),
        "units": {unit.value: st for unit, st in status_map.items()},
        "manualReviewRequired": run_computed.manual_review_required,
        "warnings": run_computed.warnings,
        "errors": run_computed.errors,
    }


def get_commission_application_personal_info(db: Session, *, application_id: UUID, actor: User) -> dict[str, Any]:
    app = load_submitted_application_or_404(db, application_id)

    projection = commission_repository.upsert_projection_for_application(db, app)
    sections = {s.section_key: s.payload for s in app.section_states}
    stage_status = projection.current_stage_status or "new"

    referenced_document_ids = collect_referenced_document_ids(app)
    all_documents = document_repository.list_documents_for_application(db, app.id)
    documents = [d for d in all_documents if d.id in referenced_document_ids]

    ai_summary = commission_service.get_ai_summary(db, application_id=application_id)
    personality_profile: dict[str, Any] | None = None
    try:
        personality_profile = build_personality_profile_snapshot(db, application_id=application_id, lang="ru")
    except Exception:
        personality_profile = None

    processing_status = _build_processing_status(db, application_id)

    comments = commission_repository.list_comments_with_author(db, application_id=application_id, limit=50)
    actions = resolve_commission_actions(db, actor, can_advance_stage=app.current_stage == "application_review")

    return build_personal_info_view(
        app=app,
        projection=projection,
        sections=sections,
        stage_status=stage_status,
        ai_summary=ai_summary,
        personality_profile=personality_profile,
        comments=comments,
        documents=documents,
        actions=actions,
        processing_status=processing_status,
    )


def get_commission_application_test_info(db: Session, *, application_id: UUID) -> dict[str, Any]:
    app = load_submitted_application_or_404(db, application_id)

    questions = internal_test_repository.list_active_questions(db)
    answers = internal_test_repository.list_answers_for_application(db, application_id)
    answer_map: dict[str, Any] = {}
    for a in answers:
        answer_map[str(a.question_id)] = a

    personality_profile: dict[str, Any] | None = None
    try:
        personality_profile = build_personality_profile_snapshot(db, application_id=application_id, lang="ru")
    except Exception:
        personality_profile = None

    question_list: list[dict[str, Any]] = []
    for idx, q in enumerate(questions, start=1):
        answer = answer_map.get(str(q.id))
        selected_text: str | None = None
        if answer and answer.selected_options:
            key = str(answer.selected_options[0]).upper()
            opts = q.options or []
            for opt in opts:
                if isinstance(opt, dict) and str(opt.get("key", "")).upper() == key:
                    selected_text = opt.get("text") or opt.get("label") or key
                    break
            if selected_text is None:
                selected_text = key
        elif answer and answer.text_answer:
            selected_text = answer.text_answer
        question_list.append({
            "index": idx,
            "questionId": str(q.id),
            "prompt": q.prompt,
            "selectedAnswer": selected_text,
        })

    ai_about: str | None = None
    ai_weak_points: list[str] = []
    ai_summary_row = commission_service.get_ai_summary(db, application_id=application_id)
    if ai_summary_row:
        ai_about = getattr(ai_summary_row, "summary_text", None)
        ai_weak_points = getattr(ai_summary_row, "weak_points", None) or []

    profile_data: dict[str, Any] | None = None
    if personality_profile:
        profile_data = {
            "profileType": personality_profile.get("profileType"),
            "profileTitle": personality_profile.get("profileTitle"),
            "summary": personality_profile.get("summary"),
            "rawScores": personality_profile.get("rawScores"),
            "ranking": personality_profile.get("ranking"),
            "dominantTrait": personality_profile.get("dominantTrait"),
            "secondaryTrait": personality_profile.get("secondaryTrait"),
            "weakestTrait": personality_profile.get("weakestTrait"),
            "flags": personality_profile.get("flags"),
            "meta": personality_profile.get("meta"),
        }

    return {
        "personalityProfile": profile_data,
        "testLang": "RU",
        "questions": question_list,
        "aiSummary": {
            "aboutCandidate": ai_about,
            "weakPoints": ai_weak_points,
        } if ai_about or ai_weak_points else None,
    }


def create_commission_comment(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID | None,
    text: str,
) -> dict[str, Any]:
    load_submitted_application_or_404(db, application_id)
    return commission_service.add_comment(db, application_id=application_id, actor_user_id=actor_user_id, body=text)


def move_application_to_next_stage(
    db: Session,
    *,
    application_id: UUID,
    actor_user_id: UUID | None,
    reason_comment: str | None,
) -> dict[str, Any]:
    load_submitted_application_or_404(db, application_id)
    return commission_service.advance_stage(
        db,
        application_id=application_id,
        actor_user_id=actor_user_id,
        reason_comment=reason_comment,
    )

