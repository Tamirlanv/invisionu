from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from invision_api.core.config import get_settings
from invision_api.services.video_processing import summary_openai


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_summarize_transcript_ru_uses_full_text_map_reduce(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls: list[str] = []

    class _FakeCompletions:
        def create(self, *, messages, **_kwargs):  # type: ignore[no-untyped-def]
            user_content = str(messages[-1]["content"])
            calls.append(user_content)
            if "Промежуточные тезисы" in user_content:
                content = (
                    "Кандидат описывает стартовую цель и контекст. "
                    "Он объясняет, какие действия предпринял на практике. "
                    "Отмечает вклад в командную работу и распределение ролей. "
                    "Описывает трудности и способы их преодоления. "
                    "Фиксирует конкретный результат проекта. "
                    "Делает выводы о развитии навыков и подходов. "
                    "Показывает мотивацию продолжать работу и обучение. "
                    "Формулирует следующий шаг и ожидаемый эффект."
                )
            else:
                content = (
                    "Кандидат называет цели и исходные условия. "
                    "Он описывает выполненные действия и решения. "
                    "Приводит результаты и личные выводы. "
                    "Фиксирует, что планирует делать дальше."
                )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    class _FakeOpenAI:
        def __init__(self, **_kwargs):  # type: ignore[no-untyped-def]
            self.chat = SimpleNamespace(completions=_FakeCompletions())

    monkeypatch.setattr(summary_openai, "OpenAI", _FakeOpenAI)

    sentences = [f"Предложение {i} про действия кандидата и результат проекта." for i in range(1, 360)]
    sentences.append("КОНЕЦ_МАРКЕР финального фрагмента транскрипта с выводами кандидата.")
    transcript = " ".join(sentences)

    result = summary_openai.summarize_transcript_ru(transcript)
    out_sentences = [s for s in re.split(r"(?<=[.!?])\s+", result) if s.strip()]
    map_calls = [c for c in calls if "Фрагмент транскрипта" in c]

    assert 7 <= len(out_sentences) <= 8
    assert len(map_calls) >= 2
    assert any("КОНЕЦ_МАРКЕР" in c for c in map_calls)


def test_postprocess_summary_removes_generic_and_duplicates() -> None:
    raw = (
        "Kind: captions Language: ru. "
        "Кандидат рассказывает о себе и своем пути. "
        "Он самостоятельно запустил учебный проект и довел его до результата. "
        "Он самостоятельно запустил учебный проект и довел его до результата. "
        "Описывает, как распределил задачи в команде и улучшил процесс. "
        "Приводит конкретные сложности и шаги по их решению. "
        "Показывает, какие выводы сделал после обратной связи. "
        "Отмечает, какие навыки усилил в ходе работы. "
        "Формулирует следующий этап развития проекта. "
        "Уточняет ожидаемый эффект от дальнейших действий."
    )
    result = summary_openai._postprocess_summary_text(raw)
    out_sentences = [s for s in re.split(r"(?<=[.!?])\s+", result) if s.strip()]

    assert "kind: captions" not in result.lower()
    assert "language: ru" not in result.lower()
    assert "кандидат рассказывает о себе" not in result.lower()
    assert 7 <= len(out_sentences) <= 8


def test_summarize_transcript_returns_empty_for_insufficient_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = summary_openai.summarize_transcript_ru(
        "Короткий комментарий без достаточного количества фактов."
    )
    assert result == ""
