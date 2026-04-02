from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from invision_api.models.enums import DataCheckUnitType


@dataclass(frozen=True)
class DataCheckUnitPolicy:
    unit_type: DataCheckUnitType
    required: bool
    dependencies: tuple[DataCheckUnitType, ...] = ()
    max_attempts: int = 3


@dataclass
class UnitExecutionResult:
    status: str
    payload: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    explainability: list[str] = field(default_factory=list)
    manual_review_required: bool = False


@dataclass(frozen=True)
class DataCheckJobEnvelope:
    application_id: UUID
    run_id: UUID
    unit_type: DataCheckUnitType
    analysis_job_id: UUID | None = None
