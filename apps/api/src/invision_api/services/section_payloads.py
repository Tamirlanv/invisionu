"""Pydantic validation for application section JSON payloads."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from invision_api.models.enums import SectionKey


class PersonalSectionPayload(BaseModel):
    preferred_first_name: str = Field(min_length=1, max_length=128)
    preferred_last_name: str = Field(min_length=1, max_length=128)
    date_of_birth: date | None = None
    pronouns: str | None = Field(default=None, max_length=64)


class ContactSectionPayload(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=32)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str = Field(min_length=2, max_length=2)


class EducationItemPayload(BaseModel):
    institution_name: str = Field(min_length=1, max_length=255)
    degree_or_program: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False


class EducationSectionPayload(BaseModel):
    entries: list[EducationItemPayload] = Field(min_length=1, max_length=20)


class InternalTestSectionPayload(BaseModel):
    """Placeholder in section state; real answers live in internal_test_answers."""

    acknowledged_instructions: bool = True


class SocialStatusSectionPayload(BaseModel):
    """Certificate upload tracked via documents; this confirms attestation text."""

    attestation: str = Field(min_length=10, max_length=2000)


def parse_and_validate_section(section_key: SectionKey, payload: dict[str, Any]) -> BaseModel:
    match section_key:
        case SectionKey.personal:
            return PersonalSectionPayload.model_validate(payload)
        case SectionKey.contact:
            return ContactSectionPayload.model_validate(payload)
        case SectionKey.education:
            return EducationSectionPayload.model_validate(payload)
        case SectionKey.internal_test:
            return InternalTestSectionPayload.model_validate(payload)
        case SectionKey.social_status_cert:
            return SocialStatusSectionPayload.model_validate(payload)
    raise ValueError("Unknown section")
