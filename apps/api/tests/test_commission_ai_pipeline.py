"""Unit tests for commission explainable hybrid AI pipeline (no live OpenAI)."""

from __future__ import annotations

import json

from invision_api.commission.ai.confidence.hybrid import algorithmic_confidence_base, final_confidence
from invision_api.commission.ai.input_hash import compute_input_hash
from invision_api.commission.ai.payload import build_compact_ai_payload
from invision_api.commission.ai.signals.aggregate import aggregate_candidate_signals
from invision_api.commission.ai.text.features import build_text_block_features
from invision_api.commission.ai.text.normalize import normalize_commission_text
from invision_api.commission.ai.types import AggregateCandidateSignals, CandidateContext, CommissionAISourceBundle
from invision_api.commission.ai.validator import validate_llm_output_lenient


def test_normalize_commission_text_strips_control_chars() -> None:
    assert "hello" in normalize_commission_text("  hello\n\nworld  ")
    assert normalize_commission_text("") == ""


def test_aggregate_and_confidence_monotonic() -> None:
    long_text = "word " * 120
    blocks = {
        "motivation": build_text_block_features(block_key="motivation", raw_text=long_text),
        "path": build_text_block_features(block_key="path", raw_text=long_text),
        "essay": build_text_block_features(block_key="essay", raw_text=long_text),
    }
    agg = aggregate_candidate_signals(blocks)
    c0, notes = algorithmic_confidence_base(blocks=blocks, aggregate=agg)
    assert 0 <= c0 <= 100
    assert isinstance(notes, list)
    fc, d = final_confidence(c0=c0, llm_delta=5, completeness_fallback=0.5)
    assert fc == min(100, c0 + 5)
    assert d == 5


def test_compact_payload_shape() -> None:
    bundle = CommissionAISourceBundle(
        application_id="00000000-0000-0000-0000-000000000001",
        candidate=CandidateContext(
            full_name="Test User",
            program="X",
            city="Y",
            age=17,
            submitted_at_iso="2026-01-01T00:00:00+00:00",
        ),
        section_payloads={
            "raw_text_extracts": {"motivation": "m", "path": "p", "essay": "e"},
            "structured_test_profile": {"present": False},
            "portfolio_compact": {},
        },
        reviewer_context=None,
    )
    blocks = {
        "motivation": build_text_block_features(block_key="motivation", raw_text="m"),
        "path": build_text_block_features(block_key="path", raw_text="p"),
        "essay": build_text_block_features(block_key="essay", raw_text="e"),
    }
    agg = aggregate_candidate_signals(blocks)
    payload = build_compact_ai_payload(
        bundle=bundle,
        blocks=blocks,
        aggregate_signals=agg,
        algorithmic_explainability_hints=["hint"],
        algorithmic_confidence_base=50,
    )
    assert payload["candidateContext"]["program"] == "X"
    assert "aggregateSignals" in payload
    assert payload["motivation"]["block_key"] == "motivation"


def test_validator_fallback_on_garbage() -> None:
    out = validate_llm_output_lenient("not json {{{")
    assert out.recommendation == "neutral"
    assert "сводка" in out.summary_text.lower() or "Сводка" in out.summary_text


def test_validator_accepts_good_dict() -> None:
    raw = {
        "summary_text": "Кратко: сильные стороны заметны.",
        "strengths": ["a"],
        "weak_points": [],
        "leadership_signals": [],
        "mission_fit_notes": [],
        "red_flags": [],
        "key_themes": ["t"],
        "evidence_highlights": [],
        "explainability_notes": [],
        "possible_follow_up_topics": [],
        "recommendation": "neutral",
        "confidence_adjustment": 0,
    }
    out = validate_llm_output_lenient(raw)
    assert out.summary_text.startswith("Кратко")


def test_input_hash_stable() -> None:
    h1 = compute_input_hash(parts={"a": 1, "b": "x"}, source_data_version="v1")
    h2 = compute_input_hash(parts={"b": "x", "a": 1}, source_data_version="v1")
    assert h1 == h2
    h3 = compute_input_hash(parts={"a": 1, "b": "y"}, source_data_version="v1")
    assert h1 != h3


def test_aggregate_serializable_reasons() -> None:
    from invision_api.commission.ai.signals.aggregate import aggregate_to_serializable

    agg = AggregateCandidateSignals(
        section_coverage={"motivation": True},
        flags={"sparse_texts": False},
        reasons=("r1", "r2"),
        numeric_rollup={"initiative": 0.1},
    )
    d = aggregate_to_serializable(agg)
    assert json.loads(json.dumps(d))["reasons"] == ["r1", "r2"]
