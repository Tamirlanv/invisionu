from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.certificate_validation import CertificateValidationResultRow
from invision_api.models.enums import SectionKey
from invision_api.services.data_check.adapters.validation_orchestrator_client import ValidationOrchestratorClient
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section


def run_certificate_validation_processing(db: Session, *, application_id: UUID, candidate_id: UUID) -> UnitExecutionResult:
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.education,
    )
    doc_ids: list[UUID] = []
    if validated:
        for maybe_doc in (
            validated.english_document_id,
            validated.certificate_document_id,
            validated.additional_document_id,
        ):
            if maybe_doc:
                doc_ids.append(maybe_doc)

    orchestrator_run_id = None
    orchestrator_warning = None
    client = ValidationOrchestratorClient()
    try:
        created = client.create_run(
            application_id=application_id,
            candidate_id=candidate_id,
            checks=["certificates"],
        )
        orchestrator_run_id = (created or {}).get("runId")
    except Exception:  # noqa: BLE001
        orchestrator_warning = "External orchestrator unavailable for certificate validation."

    if not doc_ids:
        return UnitExecutionResult(
            status="manual_review_required",
            payload={"externalRunId": orchestrator_run_id, "documentIds": []},
            warnings=[orchestrator_warning] if orchestrator_warning else [],
            explainability=["Сертификаты/документы не приложены, нужна ручная проверка."],
            manual_review_required=True,
        )

    rows = []
    for doc_id in doc_ids:
        row = CertificateValidationResultRow(
            application_id=application_id,
            document_type="education_certificate",
            processing_status="pending_external",
            extracted_fields={"documentId": str(doc_id)},
            threshold_checks=None,
            authenticity_status="manual_review_required" if orchestrator_warning else "pending",
            template_match_score=None,
            ocr_confidence=None,
            fraud_signals=[],
            warnings=[orchestrator_warning] if orchestrator_warning else [],
            errors=[],
            explainability=[
                "Создана запись проверки сертификата.",
                "Подробная OCR/аутентичность ожидается от внешнего orchestrator.",
            ],
            confidence=0.0,
            summary_text="External certificate validation pending.",
        )
        db.add(row)
        rows.append(row)
    db.flush()

    manual = bool(orchestrator_warning)
    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={
            "externalRunId": orchestrator_run_id,
            "results": [{"resultId": str(r.id), "processingStatus": r.processing_status} for r in rows],
        },
        warnings=[orchestrator_warning] if orchestrator_warning else [],
        explainability=["Запущена проверка сертификатов через внешний orchestrator."],
        manual_review_required=manual,
    )
