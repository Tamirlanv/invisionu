"""Validate / repair LLM JSON output."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from invision_api.commission.ai.output_schema import CandidateAISummaryLLMOut


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    return json.loads(text)


def validate_llm_output(data: dict[str, Any] | str) -> CandidateAISummaryLLMOut:
    if isinstance(data, str):
        data = parse_json_object(data)
    return CandidateAISummaryLLMOut.model_validate(data)


def validate_llm_output_lenient(data: Any) -> CandidateAISummaryLLMOut:
    """Accept dict or JSON string; fall back to a minimal safe summary."""
    try:
        if isinstance(data, str):
            data = parse_json_object(data)
        if not isinstance(data, dict):
            raise ValueError("not a dict")
        return CandidateAISummaryLLMOut.model_validate(data)
    except (ValidationError, ValueError, json.JSONDecodeError, TypeError):
        return CandidateAISummaryLLMOut(
            summary_text="Автоматическая сводка недоступна: ответ модели не прошёл валидацию. Опирайтесь на алгоритмические сигналы и исходные материалы.",
            strengths=[],
            weak_points=[],
            leadership_signals=[],
            mission_fit_notes=[],
            red_flags=["Ответ модели не удалось разобрать; пересчитайте позже."],
            key_themes=[],
            evidence_highlights=[],
            explainability_notes=[],
            possible_follow_up_topics=[],
            recommendation="neutral",
            confidence_adjustment=0,
        )
