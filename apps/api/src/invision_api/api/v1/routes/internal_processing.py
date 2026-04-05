from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from invision_api.api.deps import require_roles
from invision_api.core.config import get_settings
from invision_api.db.session import get_db
from invision_api.models.application import Document
from invision_api.models.enums import RoleName
from invision_api.models.user import User
from invision_api.services.data_check.external_ingestion_service import (
    ExternalIngestionConflictError,
    ExternalIngestionNotFoundError,
    ExternalIngestionValidationError,
    ingest_external_unit_result,
)
from invision_api.services.storage import get_storage

router = APIRouter()
VALIDATION_WEBHOOK_SECRET = os.getenv("VALIDATION_ORCHESTRATOR_SHARED_SECRET")


class ExternalCheckIngestionBody(BaseModel):
    application_id: UUID = Field(alias="applicationId")
    run_id: UUID = Field(alias="runId")
    check_type: str = Field(alias="checkType", min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=32)
    result_payload: dict = Field(default_factory=dict, alias="resultPayload")
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    explainability: list[str] = Field(default_factory=list)


@router.post("/validation-ingestion")
def ingest_validation_result(
    body: ExternalCheckIngestionBody,
    db: Session = Depends(get_db),
    user: User | None = Depends(require_roles(RoleName.admin, RoleName.committee)),
    x_validation_secret: str | None = Header(default=None),
) -> dict[str, str]:
    _ = user
    if VALIDATION_WEBHOOK_SECRET and x_validation_secret != VALIDATION_WEBHOOK_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid validation webhook secret")
    try:
        ingest_external_unit_result(
            db,
            application_id=body.application_id,
            run_id=body.run_id,
            check_type=body.check_type,
            status=body.status,
            result_payload=body.result_payload,
            warnings=body.warnings,
            errors=body.errors,
            explainability=body.explainability,
        )
    except ExternalIngestionValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ExternalIngestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ExternalIngestionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return {"status": "ok"}


@router.get("/storage/documents/{document_id}/file")
def get_storage_document_file(
    document_id: UUID,
    x_storage_proxy_secret: str | None = Header(default=None, alias="X-Storage-Proxy-Secret"),
    db: Session = Depends(get_db),
) -> Response:
    settings = get_settings()
    expected = settings.internal_storage_proxy_secret
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Storage proxy is disabled")
    if x_storage_proxy_secret != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid storage proxy secret")

    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    try:
        data = get_storage().read_bytes(doc.storage_key)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage")

    return Response(content=data, media_type=doc.mime_type or "application/octet-stream")
