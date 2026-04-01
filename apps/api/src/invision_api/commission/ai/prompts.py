"""Prompts for commission structured summary (JSON-only contract)."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You assist admissions committee reviewers. Output ONLY valid JSON matching the user schema.
Rules:
- Do NOT make a final admission or enrollment decision.
- Do NOT invent biographical facts not supported by the payload.
- Avoid clinical/psychiatric labels and protected-attribute proxies.
- recommendation must be one of: recommend, neutral, caution (assistive tone only).
- confidence_adjustment is an integer in [-15, 15] adjusting the given algorithmicConfidenceBase.
- All list fields: short strings, no duplicates, max 50 items each.
"""


def build_user_message(*, prompt_version: str, compact_payload: dict[str, Any]) -> str:
    schema_hint = {
        "summary_text": "string",
        "strengths": ["string"],
        "weak_points": ["string"],
        "leadership_signals": ["string"],
        "mission_fit_notes": ["string"],
        "red_flags": ["string"],
        "key_themes": ["string"],
        "evidence_highlights": ["string"],
        "explainability_notes": ["string"],
        "possible_follow_up_topics": ["string"],
        "recommendation": "recommend|neutral|caution",
        "confidence_adjustment": "integer -15..15",
    }
    return json.dumps(
        {
            "prompt_version": prompt_version,
            "output_schema": schema_hint,
            "payload": compact_payload,
        },
        ensure_ascii=False,
    )
