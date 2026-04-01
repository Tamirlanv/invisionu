"""Commission domain enums and DTOs.

These types are pure domain contracts: they do not depend on FastAPI/Pydantic/SQLAlchemy.
They are used by application/services and then mapped to Pydantic schemas at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal
from uuid import UUID


class CommissionRole(str, Enum):
    viewer = "viewer"
    reviewer = "reviewer"
    admin = "admin"


class StageStatus(str, Enum):
    new = "new"
    in_review = "in_review"
    needs_attention = "needs_attention"
    approved = "approved"
    rejected = "rejected"


class FinalDecision(str, Enum):
    # Keep naming aligned to requirements; implementation may add aliases later.
    move_forward = "move_forward"
    reject = "reject"
    waitlist = "waitlist"
    invite_interview = "invite_interview"
    enrolled = "enrolled"


class ReviewerRubric(str, Enum):
    motivation = "motivation"
    leadership = "leadership"
    maturity = "maturity"
    resilience = "resilience"
    mission_fit = "mission_fit"


class RubricScore(str, Enum):
    strong = "strong"
    medium = "medium"
    low = "low"


class InternalRecommendation(str, Enum):
    recommend_forward = "recommend_forward"
    needs_discussion = "needs_discussion"
    reject = "reject"


class AIRecommendation(str, Enum):
    recommend = "recommend"
    neutral = "neutral"
    caution = "caution"


@dataclass(frozen=True, kw_only=True)
class AIPlaceholderSummary:
    """Future-ready AI summary contract (human-in-the-loop only)."""

    application_id: UUID
    status: Literal["pending", "ready", "failed", "skipped"]
    summary_text: str | None
    strengths: list[str]
    weak_points: list[str]
    red_flags: list[str]
    leadership_signals: list[str]
    recommendation: AIRecommendation | None
    confidence_score: int | None  # 0..100
    explainability_notes: str | None
    generated_at_iso: str | None
    source_data_version: str | None
    mission_fit_notes: list[str] = field(default_factory=list)
    key_themes: list[str] = field(default_factory=list)
    evidence_highlights: list[str] = field(default_factory=list)
    possible_follow_up_topics: list[str] = field(default_factory=list)
    input_hash: str | None = None
    pipeline_version: str | None = None


@dataclass(frozen=True)
class KanbanCard:
    application_id: UUID
    candidate_full_name: str
    program: str | None
    age: int | None
    city: str | None
    phone: str | None
    submitted_at_iso: str | None
    updated_at_iso: str | None
    stage_column: str  # see mapping.COMMISSION_STAGE_COLUMNS
    stage_status: StageStatus | None
    attention_flag_manual: bool
    final_decision: FinalDecision | None
    visual_status: Literal["neutral", "positive", "negative"]
    visual_reason: str | None
    comment_count: int
    has_ai_summary: bool
    ai_recommendation: AIRecommendation | None


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    entity_type: str
    entity_id: UUID
    actor_user_id: UUID | None
    actor_commission_role: CommissionRole | None
    created_at_iso: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    metadata: dict[str, Any] | None

