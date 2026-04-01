from invision_api.services.growth_path.normalize import normalize_growth_text
from invision_api.services.growth_path.spam_rules import check_answer_spam


def test_normalize_growth_text_collapses_whitespace() -> None:
    assert normalize_growth_text("  a \n\n  b  ") == "a b"


def test_check_answer_spam_flags_spam_phrase() -> None:
    t = "x" * 200 + " lorem ipsum " + "y" * 200
    r = check_answer_spam(t)
    assert r.ok is False
    assert "spam_phrase" in r.reasons


def test_check_answer_spam_ok_for_plain_unique_text() -> None:
    words = " ".join(f"слово{i}" for i in range(80))
    t = normalize_growth_text(words)
    assert len(t) >= 200
    r = check_answer_spam(t)
    assert r.ok is True
