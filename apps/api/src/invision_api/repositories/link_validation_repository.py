from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.link_validation import LinkValidationResultRow
from invision_api.services.link_validation.types import LinkValidationResult


def create_link_validation_result(
    db: Session, application_id: UUID | None, result: LinkValidationResult
) -> LinkValidationResultRow:
    row = LinkValidationResultRow(
        application_id=application_id,
        original_url=result.originalUrl,
        normalized_url=result.normalizedUrl,
        is_valid_format=result.isValidFormat,
        is_reachable=result.isReachable,
        availability_status=result.availabilityStatus,
        provider=result.provider,
        resource_type=result.resourceType,
        status_code=result.statusCode,
        content_type=result.contentType,
        content_length=result.contentLength,
        redirected=result.redirected,
        redirect_count=result.redirectCount,
        response_time_ms=result.responseTimeMs,
        warnings=result.warnings,
        errors=result.errors,
        confidence=result.confidence,
    )
    db.add(row)
    return row
