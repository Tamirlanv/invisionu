from __future__ import annotations

import base64
import os
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from invision_api.models.application import Document
from invision_api.models.certificate_validation import CertificateValidationResultRow
from invision_api.models.enums import SectionKey
from invision_api.services.data_check.contracts import UnitExecutionResult
from invision_api.services.data_check.utils import get_validated_section
from invision_api.services.storage_read_service import read_document_bytes_with_fallback
from invision_api.services.text_extraction_service import extract_bytes

CERTIFICATE_VALIDATION_URL = os.getenv(
    "CERTIFICATE_VALIDATION_URL", "http://localhost:4400/certificate-validation/validate"
)
CERTIFICATE_VALIDATION_TIMEOUT = float(os.getenv("CERTIFICATE_VALIDATION_TIMEOUT", "120"))


def _role_for_document(
    doc_id: UUID,
    *,
    english_document_id: UUID | None,
    certificate_document_id: UUID | None,
    additional_document_id: UUID | None,
) -> str | None:
    if english_document_id and doc_id == english_document_id:
        return "english"
    if certificate_document_id and doc_id == certificate_document_id:
        return "certificate"
    if additional_document_id and doc_id == additional_document_id:
        return "additional"
    return None


def _build_validation_payload(
    *,
    application_id: UUID,
    doc: Document,
    raw: bytes,
    role: str | None,
    english_proof_kind: str | None,
    certificate_proof_kind: str | None,
) -> dict:
    outcome = extract_bytes(mime_type=doc.mime_type or "", filename=doc.original_filename or "file", data=raw)
    payload: dict = {"applicationId": str(application_id), "skipPersistence": True}
    if outcome.text and outcome.status == "completed":
        payload["plainText"] = outcome.text
    else:
        payload["imageBase64"] = base64.standard_b64encode(raw).decode("ascii")
        payload["mimeType"] = doc.mime_type or "application/octet-stream"

    if role == "english":
        payload["documentRole"] = "english"
        payload["englishProofKind"] = english_proof_kind
    elif role == "certificate":
        payload["documentRole"] = "certificate"
        payload["certificateProofKind"] = certificate_proof_kind
    elif role == "additional":
        payload["documentRole"] = "additional"

    return payload


def _row_from_response(
    application_id: UUID, doc_id: UUID, data: dict, *, document_role: str | None
) -> CertificateValidationResultRow:
    extracted = data.get("extractedFields") or {}
    auth = data.get("authenticity") or {}
    exam = {
        "documentId": str(doc_id),
        "documentRole": document_role,
        "documentType": data.get("documentType"),
        "detectedScore": extracted.get("totalScore"),
        "scoreLabel": data.get("scoreLabel") or extracted.get("scoreLabel"),
        "passedThreshold": data.get("passedThreshold"),
        "thresholdType": data.get("thresholdType"),
        "ocrDocumentType": extracted.get("ocrDocumentType"),
        "declarationMismatch": extracted.get("declarationMismatch"),
        "extractionMethod": extracted.get("extractionMethod"),
        "targetFieldFound": extracted.get("targetFieldFound"),
        "targetFieldType": extracted.get("targetFieldType"),
        "targetFieldEvidence": extracted.get("targetFieldEvidence"),
        "scorePlausible": extracted.get("scorePlausible"),
        "scoreRejectionReason": extracted.get("scoreRejectionReason"),
    }
    merged_extracted = {**extracted, "examDocument": exam}

    return CertificateValidationResultRow(
        application_id=application_id,
        document_type=str(data.get("documentType") or "unknown")[:32],
        processing_status=str(data.get("processingStatus") or "processing_failed")[:32],
        extracted_fields=merged_extracted,
        threshold_checks=data.get("thresholdChecks"),
        authenticity_status=str(auth.get("status") or "manual_review_required")[:32],
        template_match_score=auth.get("templateMatchScore"),
        ocr_confidence=auth.get("ocrConfidence"),
        fraud_signals=list(auth.get("fraudSignals") or []),
        warnings=list(data.get("warnings") or []),
        errors=list(data.get("errors") or []),
        explainability=list(data.get("explainability") or []),
        confidence=float(data.get("confidence") or 0.0),
        summary_text=data.get("summaryText"),
    )


def _row_from_error(application_id: UUID, doc_id: UUID, message: str) -> CertificateValidationResultRow:
    return CertificateValidationResultRow(
        application_id=application_id,
        document_type="unknown",
        processing_status="processing_failed",
        extracted_fields={"documentId": str(doc_id), "error": message},
        threshold_checks=None,
        authenticity_status="manual_review_required",
        template_match_score=None,
        ocr_confidence=None,
        fraud_signals=["certificate_validation_http_error"],
        warnings=[],
        errors=[message],
        explainability=["Certificate validation service request failed."],
        confidence=0.0,
        summary_text=None,
    )


def run_certificate_validation_processing(
    db: Session, *, application_id: UUID, candidate_id: UUID
) -> UnitExecutionResult:
    _ = candidate_id
    validated = get_validated_section(
        db,
        application_id=application_id,
        section_key=SectionKey.education,
    )
    doc_ids: list[UUID] = []
    english_proof_kind: str | None = None
    certificate_proof_kind: str | None = None
    if validated:
        english_proof_kind = validated.english_proof_kind
        certificate_proof_kind = validated.certificate_proof_kind
        for maybe_doc in (
            validated.english_document_id,
            validated.certificate_document_id,
            validated.additional_document_id,
        ):
            if maybe_doc:
                doc_ids.append(maybe_doc)

    if not doc_ids:
        return UnitExecutionResult(
            status="manual_review_required",
            payload={"documentIds": [], "results": []},
            warnings=[],
            explainability=["Сертификаты/документы не приложены, нужна ручная проверка."],
            manual_review_required=True,
        )

    rows: list[CertificateValidationResultRow] = []
    warnings: list[str] = []
    explainability: list[str] = []

    for doc_id in doc_ids:
        doc = db.get(Document, doc_id)
        if not doc:
            row = _row_from_error(application_id, doc_id, "Document not found")
            db.add(row)
            rows.append(row)
            continue

        role = _role_for_document(
            doc_id,
            english_document_id=validated.english_document_id if validated else None,
            certificate_document_id=validated.certificate_document_id if validated else None,
            additional_document_id=validated.additional_document_id if validated else None,
        )

        try:
            raw = read_document_bytes_with_fallback(document_id=doc.id, storage_key=doc.storage_key)
        except OSError as e:
            row = _row_from_error(application_id, doc_id, f"Storage read failed: {e}")
            db.add(row)
            rows.append(row)
            continue

        payload = _build_validation_payload(
            application_id=application_id,
            doc=doc,
            raw=raw,
            role=role,
            english_proof_kind=english_proof_kind,
            certificate_proof_kind=certificate_proof_kind,
        )

        try:
            with httpx.Client(timeout=CERTIFICATE_VALIDATION_TIMEOUT) as client:
                resp = client.post(CERTIFICATE_VALIDATION_URL, json=payload)
                if resp.status_code >= 300:
                    row = _row_from_error(
                        application_id,
                        doc_id,
                        f"certificate validation HTTP {resp.status_code}: {resp.text[:500]}",
                    )
                else:
                    data = resp.json()
                    row = _row_from_response(application_id, doc_id, data, document_role=role)
        except httpx.HTTPError as e:
            row = _row_from_error(application_id, doc_id, str(e))
        except Exception as e:  # noqa: BLE001
            row = _row_from_error(application_id, doc_id, str(e))

        db.add(row)
        rows.append(row)

    db.flush()

    manual = False
    for r in rows:
        exam_doc = ((r.extracted_fields or {}).get("examDocument") or {}) if isinstance(r.extracted_fields, dict) else {}
        role = exam_doc.get("documentRole")
        score_expected = role in ("english", "certificate")
        score_missing = exam_doc.get("detectedScore") is None if score_expected else False
        target_missing = exam_doc.get("targetFieldFound") is False if score_expected else False
        if (
            r.authenticity_status != "likely_authentic"
            or r.processing_status in ("ocr_failed", "unsupported", "processing_failed")
            or r.errors
            or score_missing
            or target_missing
        ):
            manual = True
            break

    explainability.append(f"Обработано документов: {len(rows)}.")

    return UnitExecutionResult(
        status="manual_review_required" if manual else "completed",
        payload={
            "results": [
                {
                    "resultId": str(r.id),
                    "documentType": r.document_type,
                    "processingStatus": r.processing_status,
                    "examDocument": (r.extracted_fields or {}).get("examDocument"),
                }
                for r in rows
            ],
        },
        warnings=warnings,
        explainability=explainability,
        manual_review_required=manual,
    )
