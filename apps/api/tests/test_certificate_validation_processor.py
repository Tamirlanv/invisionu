"""Unit tests for certificate validation payload and row mapping."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from invision_api.models.application import Document
from invision_api.services.data_check.processors.certificate_validation_processor import (
    _apply_temporary_score_fallback,
    _build_validation_payload,
    _forced_certificate_score,
    _row_from_error,
    _row_from_response,
)


def test_build_validation_payload_includes_skip_persistence_and_role() -> None:
    doc = MagicMock(spec=Document)
    doc.mime_type = "image/jpeg"
    doc.original_filename = "cert.jpg"
    raw = b"\xff\xd8\xff\xe0fake jpeg"
    payload = _build_validation_payload(
        application_id=uuid4(),
        doc=doc,
        raw=raw,
        role="certificate",
        english_proof_kind=None,
        certificate_proof_kind="ent",
    )
    assert payload.get("skipPersistence") is True
    assert payload.get("documentRole") == "certificate"
    assert payload.get("certificateProofKind") == "ent"
    assert "imageBase64" in payload or "plainText" in payload


def test_row_from_response_maps_exam_document() -> None:
    app_id = uuid4()
    doc_id = uuid4()
    data = {
        "documentType": "ielts",
        "processingStatus": "processed",
        "extractedFields": {
            "totalScore": 6.5,
            "ocrDocumentType": "ielts",
            "targetFieldFound": True,
            "targetFieldType": "ielts_overall_band",
            "targetFieldEvidence": "overall band score 6.5",
            "extractionConfidenceTier": "high",
        },
        "scoreLabel": "overall band score",
        "passedThreshold": True,
        "thresholdType": "ielts",
        "thresholdChecks": {"ieltsMinPassed": True},
        "authenticity": {
            "status": "likely_authentic",
            "templateMatchScore": 0.9,
            "ocrConfidence": 0.8,
            "fraudSignals": [],
        },
        "warnings": [],
        "errors": [],
        "explainability": [],
        "confidence": 0.85,
    }
    row = _row_from_response(app_id, doc_id, data, document_role="english")
    assert row.document_type == "ielts"
    assert row.extracted_fields["examDocument"]["detectedScore"] == 6.5
    assert row.extracted_fields["examDocument"]["passedThreshold"] is True
    assert row.extracted_fields["examDocument"]["targetFieldFound"] is True
    assert row.extracted_fields["examDocument"]["targetFieldType"] == "ielts_overall_band"
    assert row.extracted_fields["examDocument"]["extractionConfidenceTier"] == "high"


def test_row_from_error_maps_error_code_and_exam_document() -> None:
    app_id = uuid4()
    doc_id = uuid4()
    row = _row_from_error(
        app_id,
        doc_id,
        "Storage read failed: missing file",
        error_code="storage_read_failed",
        document_role="certificate",
    )
    exam = row.extracted_fields["examDocument"]
    assert exam["documentId"] == str(doc_id)
    assert exam["documentRole"] == "certificate"
    assert exam["detectedScore"] is None
    assert exam["errorCode"] == "storage_read_failed"
    assert "certificate_storage_read_failed" in row.fraud_signals


def test_forced_certificate_score_mapping() -> None:
    assert _forced_certificate_score(
        role="english",
        english_proof_kind="ielts_6",
        certificate_proof_kind=None,
    ) == ("ielts", 6.0, "overall band score", "ielts_overall_band")
    assert _forced_certificate_score(
        role="certificate",
        english_proof_kind=None,
        certificate_proof_kind="ent",
    ) == ("ent", 100.0, "итоговый балл", "ent_total_score")


def test_apply_temporary_score_fallback_overrides_error_row() -> None:
    row = _row_from_error(
        uuid4(),
        uuid4(),
        "certificate validation HTTP 500",
        error_code="validation_http_failed",
        document_role="english",
    )
    applied = _apply_temporary_score_fallback(
        row,
        role="english",
        english_proof_kind="ielts_6",
        certificate_proof_kind=None,
    )
    assert applied is True
    exam = row.extracted_fields["examDocument"]
    assert exam["detectedScore"] == 6.0
    assert exam["targetFieldType"] == "ielts_overall_band"
    assert exam["errorCode"] is None
    assert row.processing_status == "processed"
    assert row.authenticity_status == "likely_authentic"
    assert row.errors == []
