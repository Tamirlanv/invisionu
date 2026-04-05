"""Extract plain text from uploaded documents (txt, pdf, docx)."""

from __future__ import annotations

import logging
import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.application import Document
from invision_api.models.enums import ExtractionStatus
from invision_api.repositories import admissions_repository
from invision_api.services.storage_read_service import read_document_bytes_with_fallback

EXTRACTOR_VERSION = "1.0.0"
logger = logging.getLogger(__name__)


@dataclass
class ExtractionOutcome:
    text: str | None
    status: str
    error_message: str | None = None


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _extract_docx(data: bytes) -> str:
    from docx import Document as DocxDocument
    from io import BytesIO

    doc = DocxDocument(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text).strip()


def extract_bytes(*, mime_type: str, filename: str, data: bytes) -> ExtractionOutcome:
    mt = (mime_type or "").split(";")[0].strip().lower()
    suffix = Path(filename).suffix.lower()

    try:
        if mt == "text/plain" or suffix == ".txt":
            text = data.decode("utf-8", errors="replace")
            return ExtractionOutcome(text=text, status=ExtractionStatus.completed.value)
        if mt == "application/pdf" or suffix == ".pdf":
            return ExtractionOutcome(text=_extract_pdf(data), status=ExtractionStatus.completed.value)
        if (
            mt == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or suffix == ".docx"
        ):
            return ExtractionOutcome(text=_extract_docx(data), status=ExtractionStatus.completed.value)
    except Exception as e:  # noqa: BLE001
        return ExtractionOutcome(
            text=None,
            status=ExtractionStatus.failed.value,
            error_message=str(e),
        )

    return ExtractionOutcome(
        text=None,
        status=ExtractionStatus.skipped.value,
        error_message=f"Unsupported type for extraction: {mt or suffix}",
    )


def extract_and_persist_for_document(db: Session, document_id: UUID) -> Document:
    """Load document bytes from storage, extract text, persist DocumentExtraction and link on Document."""
    doc = db.get(Document, document_id)
    if not doc:
        raise ValueError("document not found")

    try:
        raw = read_document_bytes_with_fallback(document_id=doc.id, storage_key=doc.storage_key)
    except OSError as exc:
        logger.warning(
            "document_extraction_storage_read_failed document_id=%s storage_key=%s error=%s",
            doc.id,
            doc.storage_key,
            str(exc)[:300],
        )
        ext = admissions_repository.create_document_extraction(
            db,
            document_id,
            sha256_hex=(doc.sha256_hex or ("0" * 64)),
            extracted_text=None,
            extraction_status=ExtractionStatus.failed.value,
            extractor_version=EXTRACTOR_VERSION,
            error_message=f"Storage read failed: {exc}",
        )
        doc.primary_extraction_id = ext.id
        db.flush()
        db.refresh(doc)
        return doc

    sha = hashlib.sha256(raw).hexdigest()
    if not doc.sha256_hex:
        doc.sha256_hex = sha

    outcome = extract_bytes(mime_type=doc.mime_type, filename=doc.original_filename, data=raw)

    ext = admissions_repository.create_document_extraction(
        db,
        document_id,
        sha256_hex=sha,
        extracted_text=outcome.text,
        extraction_status=outcome.status,
        extractor_version=EXTRACTOR_VERSION,
        error_message=outcome.error_message,
    )
    doc.primary_extraction_id = ext.id
    db.flush()
    db.refresh(doc)
    return doc
