"""Regression tests for motivation sidebar attention notes."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from invision_api.commission.application.sidebar_service import _build_motivation_summary_panel
from invision_api.models.application import ApplicationSectionState, TextAnalysisRun

_TECHNICAL_PATTERNS = [
    re.compile(r"\bq\d+\b", re.IGNORECASE),
    re.compile(r"data unavailable", re.IGNORECASE),
    re.compile(r"details unavailable", re.IGNORECASE),
    re.compile(r"\bspam_questions\b", re.IGNORECASE),
    re.compile(r"\bspam_check\b", re.IGNORECASE),
    re.compile(r"\bheuristics\b", re.IGNORECASE),
    re.compile(r"\bpayload\b", re.IGNORECASE),
]


def _assert_human_readable(text: str) -> None:
    assert text.strip(), "Expected non-empty human-readable message"
    for pat in _TECHNICAL_PATTERNS:
        assert not pat.search(text), f"Technical marker leaked: {pat.pattern!r} in {text!r}"


def _add_run(
    db: Session,
    *,
    app_id,
    block_key: str,
    explanations: dict,
    flags: dict | None = None,
) -> None:
    db.add(
        TextAnalysisRun(
            id=uuid4(),
            application_id=app_id,
            block_key=block_key,
            source_kind="pipeline",
            status="completed",
            explanations=explanations,
            flags=flags or {},
        )
    )


def test_motivation_attention_notes_include_originality_consistency_and_paste(db: Session, factory) -> None:
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)

    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="motivation_goals",
            payload={
                "narrative": "Я хочу учиться и развиваться, чтобы приносить пользу обществу." * 10,
                "was_pasted": True,
                "paste_count": 4,
                "consent_privacy": True,
                "consent_parent": True,
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )

    _add_run(
        db,
        app_id=app.id,
        block_key="motivation_goals",
        explanations={
            "summary": "Кандидат выражает сильную мотивацию, но мало конкретных примеров.",
            "signals": {
                "motivation_density": 0.45,
                "evidence_density": 0.02,
                "avg_sentence_len": 21.0,
                "word_count": 180,
            },
        },
    )
    _add_run(
        db,
        app_id=app.id,
        block_key="growth_journey",
        explanations={"section_signals": {"growth": 0.2, "concrete_experience": 0.2}},
    )
    _add_run(
        db,
        app_id=app.id,
        block_key="achievements_activities",
        explanations={"signals": {"impact_markers": 0, "links_count": 0}},
    )
    db.flush()

    panel = _build_motivation_summary_panel(db, app.id)
    attention = next(s for s in panel["sections"] if s["title"] == "Требует внимания")
    notes = attention.get("attentionNotes") or []

    assert notes, "Expected structured attentionNotes for motivation panel"
    categories = {n.get("category") for n in notes}
    assert "originality" in categories
    assert "consistency" in categories
    assert "paste_behavior" in categories
    assert all(n.get("severity") in {"low", "medium", "high"} for n in notes)
    for n in notes:
        _assert_human_readable(str(n.get("message", "")))
    for item in attention["items"]:
        _assert_human_readable(item)


def test_motivation_attention_notes_fallback_to_no_remarks(db: Session, factory) -> None:
    user = factory.user(db)
    role = factory.candidate_role(db)
    factory.assign_role(db, user, role)
    profile = factory.profile(db, user)
    app = factory.application(db, profile)

    db.add(
        ApplicationSectionState(
            application_id=app.id,
            section_key="motivation_goals",
            payload={
                "narrative": "У меня есть долгосрочная цель обучения и конкретные шаги для её реализации." * 8,
                "was_pasted": False,
                "paste_count": 0,
                "consent_privacy": True,
                "consent_parent": True,
            },
            is_complete=True,
            schema_version=1,
            last_saved_at=datetime.now(tz=UTC),
        )
    )

    _add_run(
        db,
        app_id=app.id,
        block_key="motivation_goals",
        explanations={
            "summary": "Мотивация изложена последовательно и с конкретными ориентирами.",
            "signals": {
                "motivation_density": 0.2,
                "evidence_density": 0.2,
                "avg_sentence_len": 12.0,
                "word_count": 190,
            },
        },
    )
    _add_run(
        db,
        app_id=app.id,
        block_key="growth_journey",
        explanations={"section_signals": {"growth": 0.8, "concrete_experience": 0.8}},
    )
    _add_run(
        db,
        app_id=app.id,
        block_key="achievements_activities",
        explanations={"signals": {"impact_markers": 2, "links_count": 1}},
    )
    db.flush()

    panel = _build_motivation_summary_panel(db, app.id)
    attention = next(s for s in panel["sections"] if s["title"] == "Требует внимания")
    assert attention.get("attentionNotes") in (None, [])
    assert attention["items"] == ["Замечаний нет"]
