"""Mapping helpers from existing admissions domain to commission concepts.

The codebase already has:
- Application stages/states + linear stage transitions
- AdmissionDecision (final decision)
- CommitteeReview / AIReviewMetadata (early placeholders)
- TextAnalysisRun and ApplicationReviewSnapshot (explainability packet)

This module provides stable derived fields used by commission UI without
introducing new DB schema yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from invision_api.models.enums import ApplicationStage, ApplicationState


# Commission-facing linear stage columns (requested product naming).
# Map onto existing pipeline stages where possible.
COMMISSION_STAGE_COLUMNS: tuple[str, ...] = (
    "data_check",
    "application_review",
    "interview",
    "committee_decision",
    "result",
)


def application_to_commission_column(current_stage: str) -> str:
    """Map internal stage enum to commission kanban column id."""
    # Existing internal stages:
    # application -> initial_screening -> application_review -> interview -> committee_review -> decision
    if current_stage == ApplicationStage.initial_screening.value:
        return "data_check"
    if current_stage == ApplicationStage.application_review.value:
        return "application_review"
    if current_stage == ApplicationStage.interview.value:
        return "interview"
    if current_stage in (ApplicationStage.committee_review.value, ApplicationStage.decision.value):
        return "committee_decision"
    # Pre-submit drafts should not appear on commission board.
    return "result"


@dataclass(frozen=True)
class VisualStatus:
    """Derived visual status for candidate card outline."""

    kind: str  # neutral|positive|negative
    reason: str | None = None


def derive_visual_status(
    *,
    stage_status: str | None,
    final_decision_status: str | None,
) -> VisualStatus:
    """
    Green outline = positive, red = negative, else neutral.
    MVP rules:
    - Final decision wins.
    - Otherwise stage status drives the outline.
    """
    if final_decision_status:
        if final_decision_status in ("enrolled", "move_forward", "invite_interview"):
            return VisualStatus(kind="positive", reason="final_decision")
        if final_decision_status in ("reject",):
            return VisualStatus(kind="negative", reason="final_decision")
        if final_decision_status in ("waitlist",):
            return VisualStatus(kind="neutral", reason="final_decision")

    if stage_status:
        if stage_status == "approved":
            return VisualStatus(kind="positive", reason="stage_status")
        if stage_status == "rejected":
            return VisualStatus(kind="negative", reason="stage_status")
    return VisualStatus(kind="neutral", reason=None)


def should_appear_on_commission_board(app_state: str, locked_after_submit: bool) -> bool:
    """Only submitted (created) applications are visible to commission."""
    if app_state != ApplicationState.submitted.value:
        # Later pipeline states are also visible to commission (under_screening etc.).
        # We treat any locked application as submitted/created for commission purposes.
        return bool(locked_after_submit)
    return True


def ai_recommendation_ready(ai_row: dict[str, Any] | None) -> bool:
    """Placeholder: AI ready when record exists and has summary text."""
    if not ai_row or not isinstance(ai_row, dict):
        return False
    return bool(ai_row.get("summary_text") or ai_row.get("summaryText"))

