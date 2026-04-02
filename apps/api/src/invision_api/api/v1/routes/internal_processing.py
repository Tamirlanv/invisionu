from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from invision_api.api.deps import require_roles
from invision_api.db.session import get_db
from invision_api.models.enums import RoleName
from invision_api.models.user import User
from invision_api.services.data_check.external_ingestion_service import ingest_external_unit_result

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
    db.commit()
    return {"status": "ok"}
