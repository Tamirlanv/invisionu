from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from invision_api.models.enums import SectionKey
from invision_api.repositories import data_check_repository
from invision_api.services import section_payloads


def get_section_payload(
    db: Session,
    *,
    application_id: UUID,
    section_key: SectionKey,
) -> dict[str, Any] | None:
    sections = data_check_repository.list_section_states(db, application_id)
    for section in sections:
        if section.section_key == section_key.value and isinstance(section.payload, dict):
            return section.payload
    return None


def get_validated_section(
    db: Session,
    *,
    application_id: UUID,
    section_key: SectionKey,
) -> Any | None:
    payload = get_section_payload(db, application_id=application_id, section_key=section_key)
    if not payload:
        return None
    try:
        return section_payloads.parse_and_validate_section(section_key, payload)
    except Exception:  # noqa: BLE001 - non-blocking for partial processing
        return None
