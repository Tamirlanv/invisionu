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


def test_check_answer_spam_does_not_flag_neutral_phrase_ya_ponyal() -> None:
    t = normalize_growth_text(
        "Я понял, что важно доводить начатое до конца, и стал лучше планировать шаги по проекту."
    )
    r = check_answer_spam(t)
    assert r.ok is True


def test_check_answer_spam_uses_phrase_boundaries() -> None:
    t = normalize_growth_text("слово asdfgh пример нормального текста без мусора")
    r = check_answer_spam(t)
    assert r.ok is True
