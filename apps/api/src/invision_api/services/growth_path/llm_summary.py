"""LLM summary for growth path — compact structured input only."""

from __future__ import annotations

from typing import Any

from invision_api.core.config import get_settings
from invision_api.services.ai_provider import get_ai_provider


def summarize_growth_path_compact(compact: dict[str, Any]) -> str:
    """
    Returns empty string if API key missing or call fails.
    Does not receive raw paste metadata — only compact preprocess output.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        return ""
    try:
        provider = get_ai_provider()
        return provider.summarize_candidate_materials(
            prompt_version="growth_path_v1",
            context={"growth_path": compact},
        )
    except Exception:
        return ""
