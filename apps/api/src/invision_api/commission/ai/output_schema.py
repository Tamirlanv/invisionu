"""Pydantic models for LLM output validation (commission AI summary)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CandidateAISummaryLLMOut(BaseModel):
    """Structured summary from the model; validated before persistence."""

    summary_text: str = Field(..., min_length=1, max_length=8000)
    strengths: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)
    leadership_signals: list[str] = Field(default_factory=list)
    mission_fit_notes: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    key_themes: list[str] = Field(default_factory=list)
    evidence_highlights: list[str] = Field(default_factory=list)
    explainability_notes: list[str] = Field(default_factory=list)
    possible_follow_up_topics: list[str] = Field(default_factory=list)
    recommendation: Literal["recommend", "neutral", "caution"]
    confidence_adjustment: int = Field(
        default=0,
        ge=-15,
        le=15,
        description="Delta applied to algorithmic base confidence (bounded).",
    )

    @field_validator(
        "strengths",
        "weak_points",
        "leadership_signals",
        "mission_fit_notes",
        "red_flags",
        "key_themes",
        "evidence_highlights",
        "explainability_notes",
        "possible_follow_up_topics",
        mode="before",
    )
    @classmethod
    def _strip_list(cls, v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        out: list[str] = []
        for x in v:
            s = str(x).strip()
            if s and s not in out:
                out.append(s)
        return out[:50]
