from __future__ import annotations

import logging
import re

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from invision_api.core.config import get_settings

logger = logging.getLogger(__name__)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_GENERIC_PATTERNS = (
    "кандидат рассказывает о себе",
    "в видео затрагиваются важные темы",
    "поднимаются важные вопросы",
    "в целом",
    "в общем",
)
_TECHNICAL_SENTENCE_RE = re.compile(
    r"(?:^|\s)(webvtt|kind\s*[:=]|language\s*[:=]|x-timestamp-map\s*[:=]|region\s*[:=]|style\s*[:=])|-->",
    re.IGNORECASE,
)
_MIN_OUTPUT_SENTENCES = 7
_MAX_OUTPUT_SENTENCES = 8
_CHUNK_TARGET_CHARS = 9000
_CHUNK_MAX_CHARS = 12000
_MAP_MAX_TOKENS = 380
_REDUCE_MAX_TOKENS = 760


class SummaryGenerationError(RuntimeError):
    """Base class for summary generation failures."""


class SummaryConfigError(SummaryGenerationError):
    """Raised when LLM summary client configuration is missing."""


class SummaryProviderError(SummaryGenerationError):
    """Raised when summary provider fails."""


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(normalized) if s.strip()]


def _chunk_sentences(
    sentences: list[str],
    *,
    target_chars: int = _CHUNK_TARGET_CHARS,
    max_chars: int = _CHUNK_MAX_CHARS,
) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        addition = len(sentence) + (1 if current else 0)
        if current and current_len + addition > target_chars:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_len = len(sentence)
            continue
        if not current and len(sentence) > max_chars:
            for start in range(0, len(sentence), max_chars):
                piece = sentence[start : start + max_chars].strip()
                if piece:
                    chunks.append(piece)
            continue
        current.append(sentence)
        current_len += addition
        if current_len >= max_chars:
            chunks.append(" ".join(current).strip())
            current = []
            current_len = 0
    if current:
        chunks.append(" ".join(current).strip())
    return [c for c in chunks if c]


def _normalize_sentence(text: str) -> str:
    s = re.sub(r"\s+", " ", text).strip()
    if not s:
        return ""
    if s[-1] not in ".!?":
        s = f"{s}."
    return s


def _sentence_key(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower(), flags=re.UNICODE)


def _is_generic_sentence(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in _GENERIC_PATTERNS)


def _is_technical_sentence(text: str) -> bool:
    return bool(_TECHNICAL_SENTENCE_RE.search(text))


def _dedupe_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = _sentence_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _postprocess_summary_text(text: str) -> str:
    raw_sentences = _split_sentences(text)
    if not raw_sentences:
        return ""
    normalized = [_normalize_sentence(s) for s in raw_sentences]
    normalized = [s for s in normalized if s]
    normalized = _dedupe_keep_order(normalized)
    filtered = [s for s in normalized if not _is_generic_sentence(s) and not _is_technical_sentence(s)]
    final_sentences = filtered if len(filtered) >= _MIN_OUTPUT_SENTENCES else normalized
    if len(final_sentences) < _MIN_OUTPUT_SENTENCES:
        return ""
    if len(final_sentences) > _MAX_OUTPUT_SENTENCES:
        final_sentences = final_sentences[:_MAX_OUTPUT_SENTENCES]
    return " ".join(final_sentences).strip()


def summarize_transcript_ru(transcript: str) -> str:
    """Summarize the full transcript into a dense RU summary of 7-8 sentences."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise SummaryConfigError("OPENAI_API_KEY не настроен для суммаризации.")
    t = re.sub(r"\s+", " ", transcript).strip()
    if len(t) < 30:
        return ""
    sentences = _split_sentences(t)
    if len(t) < 220:
        return ""

    client = OpenAI(api_key=settings.openai_api_key)
    map_system = (
        "Ты аналитик приёмной комиссии. По фрагменту транскрипта выдели только фактические тезисы: "
        "действия кандидата, опыт, достижения, мотивацию, выводы. "
        "Не добавляй оценок, советов и общих фраз. Пиши по-русски."
    )
    reduce_system = (
        "Собери итоговую выжимку видеопрезентации кандидата на русском языке. "
        "Требование: строго 7 или 8 законченных предложений, без повторов и без воды. "
        "Опирайся только на переданные тезисы и отражай главные факты, действия и выводы кандидата."
    )
    chunks = _chunk_sentences(sentences)
    map_outputs: list[str] = []
    try:
        for idx, chunk in enumerate(chunks, start=1):
            user = (
                f"Фрагмент транскрипта #{idx}:\n{chunk}\n\n"
                "Верни 4-7 коротких фактических тезисов, каждый с новой строки."
            )
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": map_system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                timeout=90.0,
                max_tokens=_MAP_MAX_TOKENS,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                map_outputs.append(text)
        if not map_outputs:
            return ""

        reduce_user = (
            "Промежуточные тезисы по всей транскрипции:\n\n"
            + "\n\n".join(map_outputs)
            + "\n\nСобери итоговую смысловую выжимку."
        )
        reduce_resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": reduce_system},
                {"role": "user", "content": reduce_user},
            ],
            temperature=0.2,
            timeout=90.0,
            max_tokens=_REDUCE_MAX_TOKENS,
        )
        result = _postprocess_summary_text((reduce_resp.choices[0].message.content or "").strip())
        return result
    except (APITimeoutError, APIConnectionError) as exc:
        raise SummaryProviderError(f"Сервис суммаризации недоступен: {exc}") from exc
    except APIStatusError as exc:
        raise SummaryProviderError(f"Сервис суммаризации вернул статус: {exc.status_code}") from exc
    except Exception as exc:
        logger.exception("LLM summary failed")
        raise SummaryProviderError(f"Ошибка суммаризации: {exc}") from exc
