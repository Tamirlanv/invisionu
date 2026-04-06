from invision_api.services.data_check.processors.growth_path_processor import (
    _evaluate_growth_path_quality_gate,
)


def test_quality_gate_mild_single_flag_is_completed_path() -> None:
    out = _evaluate_growth_path_quality_gate(
        {
            "q1": {"spam_check": {"ok": False, "reasons": ["spam_phrase"]}},
            "q2": {"spam_check": {"ok": True, "reasons": []}},
        }
    )
    assert out["manual"] is False
    assert out["manual_reason_code"] is None
    assert "mild_quality_risk" in out["mild_quality_flags"]
    assert "single_spam_phrase" in out["mild_quality_flags"]


def test_quality_gate_severe_multi_question_low_quality() -> None:
    out = _evaluate_growth_path_quality_gate(
        {
            "q1": {"spam_check": {"ok": False, "reasons": ["low_lexical_diversity"]}},
            "q2": {"spam_check": {"ok": False, "reasons": ["high_repetition"]}},
            "q3": {"spam_check": {"ok": False, "reasons": ["low_lexical_diversity"]}},
        }
    )
    assert out["manual"] is True
    assert out["manual_reason_code"] == "severe_multi_question_low_quality"


def test_quality_gate_severe_when_spam_phrase_repeats_across_answers() -> None:
    out = _evaluate_growth_path_quality_gate(
        {
            "q1": {"spam_check": {"ok": False, "reasons": ["spam_phrase"]}},
            "q2": {"spam_check": {"ok": False, "reasons": ["spam_phrase"]}},
        }
    )
    assert out["manual"] is True
    assert out["manual_reason_code"] == "severe_spam_phrase_multi"
