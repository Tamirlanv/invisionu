from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import SectionKey
from invision_api.services.data_check.adapters.validation_orchestrator_client import ValidationOrchestratorClient
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section
from invision_api.services.link_validation.service import validate_candidate_link
from invision_api.services.link_validation.types import LinkValidationRequest


def run_link_validation_processing(db: Session, *, application_id: UUID, candidate_id: UUID) -> UnitExecutionResult:
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.achievements_activities,
    )
    links = []
    if validated:
        links = [l.url.strip() for l in (validated.links or []) if l.url and l.url.strip()]

    orchestrator_run_id = None
    orchestrator_warning = None
    client = ValidationOrchestratorClient()
    try:
        created = client.create_run(
            application_id=application_id,
            candidate_id=candidate_id,
            checks=["links"],
        )
        orchestrator_run_id = (created or {}).get("runId")
    except Exception:  # noqa: BLE001
        orchestrator_warning = "External orchestrator unavailable for link validation."

    if not links:
        return UnitExecutionResult(
            status="completed",
            payload={
                "links": [],
                "externalRunId": orchestrator_run_id,
            },
            warnings=[orchestrator_warning] if orchestrator_warning else [],
            explainability=["Ссылки отсутствуют, проверка завершена без результатов."],
        )

    results = []
    bad_links = 0
    for url in links:
        r = validate_candidate_link(db, LinkValidationRequest(url=url, application_id=application_id))
        item = r.model_dump()
        results.append(item)
        if not item.get("isReachable", False):
            bad_links += 1

    manual = bool(orchestrator_warning or bad_links > 0)
    explainability = [f"Проверено ссылок: {len(results)}; недоступных: {bad_links}."]
    if orchestrator_warning:
        explainability.append("Внешний orchestrator недоступен; использована локальная fallback-проверка.")

    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={
            "externalRunId": orchestrator_run_id,
            "links": results,
        },
        warnings=[orchestrator_warning] if orchestrator_warning else [],
        explainability=explainability,
        manual_review_required=manual,
    )
