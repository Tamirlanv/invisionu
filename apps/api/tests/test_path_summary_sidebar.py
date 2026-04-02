"""Regression tests for the path summary sidebar panel (commission tab=path).

Validates that:
- Signal keys from the pipeline are mapped correctly.
- No internal identifiers (q1/q2/…) leak into the output.
- No technical fallback strings appear ("Data unavailable", "details unavailable", etc.).
- All section content is human-readable Russian text suitable for the commission.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from invision_api.commission.application.sidebar_service import (
    _build_path_summary_panel,
    _extract_key_excerpts,
    _format_signal_level,
    _sanitize_llm_summary,
    _build_path_attention,
)
from invision_api.models.application import TextAnalysisRun

_TECHNICAL_PATTERNS = [
    re.compile(r'\bq\d+\b', re.IGNORECASE),
    re.compile(r'Data unavailable', re.IGNORECASE),
    re.compile(r'Details unavailable', re.IGNORECASE),
    re.compile(r'submission includes responses', re.IGNORECASE),
    re.compile(r'\bpipeline\b', re.IGNORECASE),
    re.compile(r'\bjson\b', re.IGNORECASE),
    re.compile(r'\bpayload\b', re.IGNORECASE),
    re.compile(r'Данные недоступны'),
    re.compile(r'Детали недоступны'),
    re.compile(r'\bspam_questions\b'),
    re.compile(r'\bspam_check\b'),
    re.compile(r'\bheuristics\b'),
    re.compile(r'\baction_score\b'),
    re.compile(r'\breflection_score\b'),
]


def _assert_no_technical_markers(text: str) -> None:
    for pattern in _TECHNICAL_PATTERNS:
        assert not pattern.search(text), (
            f"Technical marker leaked into summary: pattern={pattern.pattern!r} found in {text!r}"
        )


def _seed_analysis_run(
    db: Session,
    application_id,
    *,
    llm_summary: str | None = None,
    section_signals: dict | None = None,
    per_question: dict | None = None,
    flags: dict | None = None,
) -> TextAnalysisRun:
    run = TextAnalysisRun(
        id=uuid4(),
        application_id=application_id,
        block_key="growth_journey",
        source_kind="pipeline",
        status="completed",
        explanations={
            "llm_summary": llm_summary,
            "section_signals": section_signals or {},
            "per_question": per_question or {},
        },
        flags=flags or {},
    )
    db.add(run)
    db.flush()
    return run


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestFormatSignalLevel:
    def test_high_value(self):
        assert _format_signal_level("Инициатива", 0.85) == "Инициатива: выраженный"

    def test_medium_value(self):
        assert _format_signal_level("Устойчивость", 0.5) == "Устойчивость: средний"

    def test_low_value(self):
        assert _format_signal_level("Рост / рефлексия", 0.1) == "Рост / рефлексия: низкий"

    def test_none_returns_none(self):
        assert _format_signal_level("Инициатива", None) is None

    def test_boundary_high(self):
        assert _format_signal_level("X", 0.7) == "X: выраженный"

    def test_boundary_medium(self):
        assert _format_signal_level("X", 0.3) == "X: средний"


class TestSanitizeLlmSummary:
    def test_strips_q_identifiers(self):
        result = _sanitize_llm_summary("Ответ на q1 показывает рост, q2 содержит рефлексию")
        assert "q1" not in result
        assert "q2" not in result

    def test_strips_english_technical_noise(self):
        result = _sanitize_llm_summary("Summary: Data unavailable. Details unavailable.")
        assert "Data unavailable" not in result
        assert "Details unavailable" not in result

    def test_drops_mostly_english_technical_summary(self):
        result = _sanitize_llm_summary(
            "The applicant's growth path submission includes responses to five questions. "
            "Pipeline payload contains action_score and reflection_score."
        )
        assert result == ""

    def test_preserves_normal_russian_text(self):
        text = "Кандидат демонстрирует выраженную инициативу и ответственность"
        assert _sanitize_llm_summary(text) == text

    def test_truncates_to_400(self):
        result = _sanitize_llm_summary("А" * 600)
        assert len(result) <= 400

    def test_keeps_summary_concise(self):
        text = (
            "Кандидат показывает устойчивый рост и умеет брать ответственность. "
            "В его ответах заметна инициативность в сложных ситуациях. "
            "Отдельно видна рефлексия по ошибкам и выводам. "
            "Сформирован интерес к практическому развитию в команде. "
            "Лишнее предложение, которое не должно попасть в итог."
        )
        result = _sanitize_llm_summary(text)
        # 2-4 sentences max for UI-facing summary contract.
        sentence_count = len([s for s in re.split(r"(?<=[.!?…])\s+", result) if s.strip()])
        assert 1 <= sentence_count <= 4


class TestExtractKeyExcerpts:
    def test_extracts_from_key_sentences(self):
        pq = {
            "q1": {"key_sentences": ["Кандидат проявил лидерство в школьном проекте"]},
            "q2": {"key_sentences": ["Преодолел серьёзные трудности с учёбой"]},
        }
        result = _extract_key_excerpts(pq)
        assert len(result) == 2
        assert "лидерство" in result[0]

    def test_skips_short_sentences(self):
        pq = {"q1": {"key_sentences": ["Ок"]}}
        result = _extract_key_excerpts(pq)
        assert len(result) == 1
        assert "недостаточно данных" in result[0].lower()

    def test_empty_per_question(self):
        result = _extract_key_excerpts({})
        assert len(result) == 1
        assert "недостаточно данных" in result[0].lower()

    def test_truncates_long_excerpt(self):
        pq = {"q1": {"key_sentences": ["Б" * 300]}}
        result = _extract_key_excerpts(pq)
        assert len(result) == 1
        assert len(result[0]) <= 113

    def test_limits_theses_to_four(self):
        pq = {
            "q1": {"key_sentences": ["Кандидат брал ответственность за проект в школе."]},
            "q2": {"key_sentences": ["Кандидат преодолевал ограничения и сохранял дисциплину."]},
            "q3": {"key_sentences": ["Кандидат запускал инициативы в школьном сообществе."]},
            "q4": {"key_sentences": ["Кандидат анализировал ошибки и корректировал подходы."]},
            "q5": {"key_sentences": ["Кандидат учился работать в команде и вести диалог."]},
        }
        result = _extract_key_excerpts(pq)
        assert 2 <= len(result) <= 4

    def test_uses_signal_fallback_when_excerpts_weak(self):
        pq = {"q1": {"key_sentences": ["Ок"]}}
        result = _extract_key_excerpts(
            pq,
            {"initiative": 0.9, "resilience": 0.8, "responsibility": 0.2, "growth": 0.7},
        )
        assert 2 <= len(result) <= 4
        assert any("инициатив" in s.lower() for s in result)


class TestBuildPathAttention:
    def test_no_issues_returns_empty(self):
        pq = {"q1": {"stats": {"word_count": 50}, "spam_check": {"ok": True}}}
        signals = {"initiative": 0.8, "growth": 0.6, "concrete_experience": 0.7}
        assert _build_path_attention(pq, signals) == []

    def test_spam_detected_no_q_identifiers(self):
        pq = {
            "q1": {"stats": {"word_count": 50}, "spam_check": {"ok": False}},
            "q2": {"stats": {"word_count": 50}, "spam_check": {"ok": True}},
        }
        result = _build_path_attention(pq, {})
        assert len(result) >= 1
        text = " ".join(result)
        assert "q1" not in text
        assert "q2" not in text
        _assert_no_technical_markers(text)

    def test_short_answers_counted(self):
        pq = {
            "q1": {"stats": {"word_count": 5}, "spam_check": {"ok": True}},
            "q2": {"stats": {"word_count": 10}, "spam_check": {"ok": True}},
            "q3": {"stats": {"word_count": 100}, "spam_check": {"ok": True}},
        }
        result = _build_path_attention(pq, {})
        combined = " ".join(result)
        assert "Коротких ответов: 2" in combined

    def test_low_concrete_experience(self):
        result = _build_path_attention({}, {"concrete_experience": 0.1})
        assert any("конкретных примеров" in r for r in result)

    def test_low_growth(self):
        result = _build_path_attention({}, {"growth": 0.2})
        assert any("рефлексия" in r.lower() for r in result)


# ---------------------------------------------------------------------------
# Integration tests — full panel build via DB
# ---------------------------------------------------------------------------


class TestBuildPathSummaryPanel:
    def test_full_panel_has_correct_structure(self, db: Session, factory):
        user = factory.user(db)
        role = factory.candidate_role(db)
        factory.assign_role(db, user, role)
        profile = factory.profile(db, user)
        app = factory.application(db, profile)

        _seed_analysis_run(
            db,
            app.id,
            llm_summary="Кандидат демонстрирует выраженную инициативу и активный рост.",
            section_signals={
                "initiative": 0.8,
                "resilience": 0.5,
                "responsibility": 0.6,
                "growth": 0.75,
                "concrete_experience": 0.4,
            },
            per_question={
                "q1": {
                    "key_sentences": ["Я организовал благотворительный проект"],
                    "stats": {"word_count": 80},
                    "spam_check": {"ok": True},
                },
                "q2": {
                    "key_sentences": ["Преодолел трудности в переезде"],
                    "stats": {"word_count": 60},
                    "spam_check": {"ok": True},
                },
            },
        )

        result = _build_path_summary_panel(db, app.id)

        assert result["type"] == "summary"
        assert result["title"] == "Путь роста"
        sections = result["sections"]
        titles = [s["title"] for s in sections]
        assert "Краткий вывод" in titles
        assert "Ключевые сигналы" in titles
        assert "Что сформировало кандидата" in titles

        shaping = next(s for s in sections if s["title"] == "Что сформировало кандидата")
        assert 1 <= len(shaping["items"]) <= 4
        assert all(len(item) <= 120 for item in shaping["items"])

        for section in sections:
            for item in section["items"]:
                _assert_no_technical_markers(item)

    def test_signals_read_correct_keys(self, db: Session, factory):
        user = factory.user(db)
        role = factory.candidate_role(db)
        factory.assign_role(db, user, role)
        profile = factory.profile(db, user)
        app = factory.application(db, profile)

        _seed_analysis_run(
            db,
            app.id,
            section_signals={
                "initiative": 0.9,
                "resilience": 0.4,
                "responsibility": 0.2,
                "growth": 0.8,
            },
        )

        result = _build_path_summary_panel(db, app.id)
        signals_section = next(s for s in result["sections"] if s["title"] == "Ключевые сигналы")
        items = signals_section["items"]

        assert any("выраженный" in i for i in items)
        assert any("средний" in i for i in items)
        assert any("низкий" in i for i in items)
        assert "Сигналы ещё не определены" not in items

    def test_missing_signals_shows_fallback(self, db: Session, factory):
        user = factory.user(db)
        role = factory.candidate_role(db)
        factory.assign_role(db, user, role)
        profile = factory.profile(db, user)
        app = factory.application(db, profile)

        _seed_analysis_run(db, app.id, section_signals={})

        result = _build_path_summary_panel(db, app.id)
        signals_section = next(s for s in result["sections"] if s["title"] == "Ключевые сигналы")
        assert "Сигналы ещё не определены" in signals_section["items"]
        assert "Данные недоступны" not in signals_section["items"]

    def test_no_analysis_run_graceful_fallback(self, db: Session, factory):
        user = factory.user(db)
        role = factory.candidate_role(db)
        factory.assign_role(db, user, role)
        profile = factory.profile(db, user)
        app = factory.application(db, profile)

        result = _build_path_summary_panel(db, app.id)

        assert result["type"] == "summary"
        summary_section = next(s for s in result["sections"] if s["title"] == "Краткий вывод")
        assert len(summary_section["items"]) == 1
        assert "траектория" in summary_section["items"][0].lower()

        for section in result["sections"]:
            for item in section["items"]:
                _assert_no_technical_markers(item)

    def test_shaping_block_has_fallback_when_no_excerpts(self, db: Session, factory):
        user = factory.user(db)
        role = factory.candidate_role(db)
        factory.assign_role(db, user, role)
        profile = factory.profile(db, user)
        app = factory.application(db, profile)

        _seed_analysis_run(
            db,
            app.id,
            per_question={"q1": {"stats": {"word_count": 50}}},
        )

        result = _build_path_summary_panel(db, app.id)
        titles = [s["title"] for s in result["sections"]]
        assert "Что сформировало кандидата" in titles
        shaping = next(s for s in result["sections"] if s["title"] == "Что сформировало кандидата")
        assert len(shaping["items"]) >= 1
        for section in result["sections"]:
            for item in section["items"]:
                assert "Детали недоступны" not in item

    def test_spam_flag_no_q_identifiers_in_attention(self, db: Session, factory):
        user = factory.user(db)
        role = factory.candidate_role(db)
        factory.assign_role(db, user, role)
        profile = factory.profile(db, user)
        app = factory.application(db, profile)

        _seed_analysis_run(
            db,
            app.id,
            per_question={
                "q1": {"stats": {"word_count": 50}, "spam_check": {"ok": False}},
                "q2": {"stats": {"word_count": 50}, "spam_check": {"ok": True}},
            },
            flags={"spam_questions": ["q1"], "manual_review_required": True},
        )

        result = _build_path_summary_panel(db, app.id)
        attention_section = next(s for s in result["sections"] if s["title"] == "Требует внимания")
        combined = " ".join(attention_section["items"])
        assert "q1" not in combined
        assert "q2" not in combined
        _assert_no_technical_markers(combined)

    def test_llm_summary_sanitized(self, db: Session, factory):
        user = factory.user(db)
        role = factory.candidate_role(db)
        factory.assign_role(db, user, role)
        profile = factory.profile(db, user)
        app = factory.application(db, profile)

        _seed_analysis_run(
            db,
            app.id,
            llm_summary=(
                "The applicant's growth path submission includes responses to five questions. "
                "Pipeline payload contains action_score and reflection_score."
            ),
            section_signals={"initiative": 0.8, "resilience": 0.6, "responsibility": 0.4, "growth": 0.7},
        )

        result = _build_path_summary_panel(db, app.id)
        summary_section = next(s for s in result["sections"] if s["title"] == "Краткий вывод")
        summary_text = summary_section["items"][0]
        _assert_no_technical_markers(summary_text)
        # summary must be human-facing Russian text, not leaked english boilerplate
        assert re.search(r"[А-Яа-яЁё]", summary_text)
        assert not re.search(r"[A-Za-z]{4,}", summary_text)
