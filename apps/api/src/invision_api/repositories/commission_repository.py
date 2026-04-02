from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, String, func, or_, select
from sqlalchemy.orm import Session

from invision_api.models.application import (
    AdmissionDecision,
    AIReviewMetadata,
    Application,
)
from invision_api.models.commission import (
    ApplicationComment,
    ApplicationCommissionProjection,
    ApplicationStageState,
    ApplicationStageStatusHistory,
    ApplicationTag,
    ApplicationTagLink,
    CommissionUser,
    ExportJob,
    InternalRecommendationRow,
    ReviewRubricScore,
)
from invision_api.models.user import User
from invision_api.models.candidate_validation_orchestration import CandidateValidationCheck, CandidateValidationRun


def get_commission_user(db: Session, user_id: UUID) -> CommissionUser | None:
    return db.get(CommissionUser, user_id)


def upsert_projection_for_application(db: Session, app: Application) -> ApplicationCommissionProjection:
    row = db.get(ApplicationCommissionProjection, app.id)
    profile = app.candidate_profile
    full_name = ""
    if profile:
        full_name = f"{profile.first_name} {profile.last_name}".strip()
    if not row:
        row = ApplicationCommissionProjection(
            application_id=app.id,
            candidate_full_name=full_name,
            current_stage=app.current_stage,
            submitted_at=app.submitted_at,
        )
        db.add(row)
    else:
        row.candidate_full_name = full_name
        row.current_stage = app.current_stage
        row.submitted_at = app.submitted_at
        row.updated_at = datetime.now(tz=UTC)

    contact_payload: dict = {}
    personal_payload: dict = {}
    education_payload: dict = {}
    for ss in (app.section_states or []):
        if ss.section_key == "contact" and isinstance(ss.payload, dict):
            contact_payload = ss.payload
        elif ss.section_key == "personal" and isinstance(ss.payload, dict):
            personal_payload = ss.payload
        elif ss.section_key == "education" and isinstance(ss.payload, dict):
            education_payload = ss.payload

    row.city = contact_payload.get("city") or personal_payload.get("city") or None
    row.phone = contact_payload.get("phone_e164") or None
    raw_program = personal_payload.get("education_program") or None
    _PROGRAM_LABELS = {"foundation": "Foundation", "bachelor": "Бакалавриат"}
    row.program = _PROGRAM_LABELS.get(raw_program, raw_program) if raw_program else None

    dob_raw = personal_payload.get("date_of_birth")
    if dob_raw:
        try:
            from datetime import date as _date

            if isinstance(dob_raw, str) and len(dob_raw) >= 10:
                dob = _date.fromisoformat(dob_raw[:10])
                today = datetime.now(tz=UTC).date()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                row.age = age
            else:
                row.age = None
        except (ValueError, TypeError):
            row.age = None
    else:
        row.age = None

    # Pull final decision if exists.
    decision = db.scalars(select(AdmissionDecision).where(AdmissionDecision.application_id == app.id)).first()
    row.final_decision = decision.final_decision_status if decision else None
    # AI placeholder signal.
    ai = db.scalars(
        select(AIReviewMetadata).where(AIReviewMetadata.application_id == app.id).order_by(AIReviewMetadata.created_at.desc())
    ).first()
    row.has_ai_summary = bool(ai and ai.summary_text)
    rec: str | None = None
    if ai and isinstance(ai.flags, dict):
        raw = ai.flags.get("recommendation")
        if raw in ("recommend", "neutral", "caution"):
            rec = raw
    row.ai_recommendation = rec
    # Stage status / manual attention.
    st = db.scalars(
        select(ApplicationStageState)
        .where(ApplicationStageState.application_id == app.id, ApplicationStageState.stage == app.current_stage)
        .limit(1)
    ).first()
    if st:
        row.current_stage_status = st.status
        row.attention_flag_manual = st.attention_flag_manual
    else:
        row.current_stage_status = None
        row.attention_flag_manual = False
    return row


def list_projections(
    db: Session,
    *,
    stage: str | None = None,
    stage_status: str | None = None,
    attention_only: bool = False,
    program: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ApplicationCommissionProjection]:
    stmt: Select[tuple[ApplicationCommissionProjection]] = select(ApplicationCommissionProjection)
    if stage:
        stmt = stmt.where(ApplicationCommissionProjection.current_stage == stage)
    if stage_status:
        stmt = stmt.where(ApplicationCommissionProjection.current_stage_status == stage_status)
    if attention_only:
        stmt = stmt.where(
            or_(
                ApplicationCommissionProjection.current_stage_status == "needs_attention",
                ApplicationCommissionProjection.attention_flag_manual.is_(True),
            )
        )
    if program:
        stmt = stmt.where(ApplicationCommissionProjection.program == program)
    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                ApplicationCommissionProjection.candidate_full_name.ilike(q),
                ApplicationCommissionProjection.city.ilike(q),
                ApplicationCommissionProjection.phone.ilike(q),
                ApplicationCommissionProjection.program.ilike(q),
                func.cast(ApplicationCommissionProjection.application_id, String).ilike(q),
            )
        )
    stmt = stmt.order_by(ApplicationCommissionProjection.updated_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


def get_projection(db: Session, application_id: UUID) -> ApplicationCommissionProjection | None:
    return db.get(ApplicationCommissionProjection, application_id)


def set_stage_status(
    db: Session,
    *,
    application_id: UUID,
    stage: str,
    status: str,
    actor_user_id: UUID | None,
    reason_comment: str | None,
) -> ApplicationStageState:
    row = db.scalars(
        select(ApplicationStageState).where(
            ApplicationStageState.application_id == application_id,
            ApplicationStageState.stage == stage,
        )
    ).first()
    prev = row.status if row else None
    if not row:
        row = ApplicationStageState(application_id=application_id, stage=stage, status=status, attention_flag_manual=False)
        db.add(row)
    else:
        row.status = status
        row.revision += 1
    hist = ApplicationStageStatusHistory(
        application_id=application_id,
        stage=stage,
        from_status=prev,
        to_status=status,
        actor_user_id=actor_user_id,
        reason_comment=reason_comment,
    )
    db.add(hist)
    return row


def set_attention_flag(db: Session, *, application_id: UUID, stage: str, value: bool) -> ApplicationStageState:
    row = db.scalars(
        select(ApplicationStageState).where(
            ApplicationStageState.application_id == application_id,
            ApplicationStageState.stage == stage,
        )
    ).first()
    if not row:
        row = ApplicationStageState(
            application_id=application_id,
            stage=stage,
            status="new",
            attention_flag_manual=value,
        )
        db.add(row)
    else:
        row.attention_flag_manual = value
        row.revision += 1
    return row


def create_comment(db: Session, *, application_id: UUID, author_user_id: UUID | None, body: str) -> ApplicationComment:
    row = ApplicationComment(application_id=application_id, author_user_id=author_user_id, body=body)
    db.add(row)
    return row


def list_comments(db: Session, application_id: UUID, limit: int = 100) -> list[ApplicationComment]:
    stmt = (
        select(ApplicationComment)
        .where(ApplicationComment.application_id == application_id)
        .order_by(ApplicationComment.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def list_comments_with_author(db: Session, application_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    stmt = (
        select(ApplicationComment, User.email)
        .outerjoin(User, User.id == ApplicationComment.author_user_id)
        .where(ApplicationComment.application_id == application_id)
        .order_by(ApplicationComment.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "id": row[0].id,
            "text": row[0].body,
            "author_user_id": row[0].author_user_id,
            "author_name": row[1] if isinstance(row[1], str) else None,
            "created_at": row[0].created_at,
        }
        for row in rows
    ]


def upsert_rubric_score(
    db: Session,
    *,
    application_id: UUID,
    reviewer_user_id: UUID,
    rubric: str,
    score: str,
    comment: str | None,
) -> ReviewRubricScore:
    row = db.scalars(
        select(ReviewRubricScore).where(
            ReviewRubricScore.application_id == application_id,
            ReviewRubricScore.reviewer_user_id == reviewer_user_id,
            ReviewRubricScore.rubric == rubric,
        )
    ).first()
    if not row:
        row = ReviewRubricScore(
            application_id=application_id,
            reviewer_user_id=reviewer_user_id,
            rubric=rubric,
            score=score,
            comment=comment,
        )
        db.add(row)
    else:
        row.score = score
        row.comment = comment
        row.revision += 1
    return row


def upsert_internal_recommendation(
    db: Session,
    *,
    application_id: UUID,
    reviewer_user_id: UUID,
    recommendation: str,
    reason_comment: str | None,
) -> InternalRecommendationRow:
    row = db.scalars(
        select(InternalRecommendationRow).where(
            InternalRecommendationRow.application_id == application_id,
            InternalRecommendationRow.reviewer_user_id == reviewer_user_id,
        )
    ).first()
    if not row:
        row = InternalRecommendationRow(
            application_id=application_id,
            reviewer_user_id=reviewer_user_id,
            recommendation=recommendation,
            reason_comment=reason_comment,
        )
        db.add(row)
    else:
        row.recommendation = recommendation
        row.reason_comment = reason_comment
        row.revision += 1
    return row


def list_rubric_scores(db: Session, application_id: UUID) -> list[ReviewRubricScore]:
    stmt = (
        select(ReviewRubricScore)
        .where(ReviewRubricScore.application_id == application_id)
        .order_by(ReviewRubricScore.updated_at.desc(), ReviewRubricScore.rubric.asc())
    )
    return list(db.scalars(stmt).all())


def list_internal_recommendations(db: Session, application_id: UUID) -> list[InternalRecommendationRow]:
    stmt = (
        select(InternalRecommendationRow)
        .where(InternalRecommendationRow.application_id == application_id)
        .order_by(InternalRecommendationRow.updated_at.desc())
    )
    return list(db.scalars(stmt).all())


def create_export_job(
    db: Session,
    *,
    created_by_user_id: UUID | None,
    export_format: str,
    filter_payload: dict[str, Any] | None,
    application_ids: Sequence[str] | None,
) -> ExportJob:
    row = ExportJob(
        created_by_user_id=created_by_user_id,
        format=export_format,
        status="pending",
        filter_payload=filter_payload,
        application_ids=list(application_ids) if application_ids is not None else None,
    )
    db.add(row)
    return row


def get_or_create_application_tag(db: Session, key: str) -> ApplicationTag:
    row = db.scalars(select(ApplicationTag).where(ApplicationTag.key == key)).first()
    if row:
        return row
    row = ApplicationTag(key=key)
    db.add(row)
    db.flush()
    return row


def set_application_tags(db: Session, *, application_id: UUID, tag_keys: Sequence[str]) -> list[str]:
    db.query(ApplicationTagLink).filter(ApplicationTagLink.application_id == application_id).delete()
    cleaned: list[str] = []
    for key in tag_keys:
        k = key.strip()
        if not k:
            continue
        t = get_or_create_application_tag(db, k)
        db.add(ApplicationTagLink(application_id=application_id, tag_id=t.id))
        cleaned.append(k)
    return cleaned


def list_application_tags(db: Session, application_id: UUID) -> list[str]:
    stmt = (
        select(ApplicationTag.key)
        .join(ApplicationTagLink, ApplicationTagLink.tag_id == ApplicationTag.id)
        .where(ApplicationTagLink.application_id == application_id)
        .order_by(ApplicationTag.key.asc())
    )
    return list(db.scalars(stmt).all())


def get_latest_validation_report(db: Session, application_id: UUID) -> dict[str, Any] | None:
    run = db.scalars(
        select(CandidateValidationRun)
        .where(CandidateValidationRun.application_id == application_id)
        .order_by(CandidateValidationRun.updated_at.desc())
        .limit(1)
    ).first()
    if not run:
        return None
    checks = list(
        db.scalars(select(CandidateValidationCheck).where(CandidateValidationCheck.run_id == run.id)).all()
    )
    checks_map: dict[str, Any] = {
        "links": None,
        "videoPresentation": None,
        "certificates": None,
        "test_profile_processing": None,
        "motivation_processing": None,
        "growth_path_processing": None,
        "achievements_processing": None,
        "link_validation": None,
        "video_validation": None,
        "certificate_validation": None,
        "signals_aggregation": None,
        "candidate_ai_summary": None,
    }
    aliases = {
        "links": "link_validation",
        "videoPresentation": "video_validation",
        "certificates": "certificate_validation",
    }
    for c in checks:
        checks_map[c.check_type] = {
            "status": c.status,
            "result": c.result_payload,
            "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
        }
        alias = aliases.get(c.check_type)
        if alias:
            checks_map[alias] = checks_map[c.check_type]
    return {
        "runId": str(run.id),
        "candidateId": str(run.candidate_id),
        "applicationId": str(run.application_id),
        "overallStatus": run.overall_status,
        "checks": checks_map,
        "warnings": run.warnings or [],
        "errors": run.errors or [],
        "explainability": run.explainability or [],
        "updatedAt": run.updated_at.isoformat() if run.updated_at else None,
    }

