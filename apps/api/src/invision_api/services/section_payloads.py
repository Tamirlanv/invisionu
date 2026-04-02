"""Pydantic validation for application section JSON payloads."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from invision_api.models.enums import SectionKey
from invision_api.services.growth_path.config import GROWTH_CHAR_LIMITS, GROWTH_QUESTION_ORDER
from invision_api.services.growth_path.normalize import normalize_growth_text

_DD_MM_YYYY = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")


def parse_optional_date(v: Any) -> date | None:
    """Accept ISO date/datetime strings or DD.MM.YYYY as sent by the web form layer."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        m = _DD_MM_YYYY.match(s)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(year, month, day)
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        if len(s) >= 10 and s[4] == "-":
            return date.fromisoformat(s[:10])
        return date.fromisoformat(s)
    raise ValueError(f"invalid date value: {v!r}")


class PersonalSectionPayload(BaseModel):
    preferred_first_name: str = Field(min_length=1, max_length=128)
    preferred_last_name: str = Field(min_length=1, max_length=128)
    middle_name: str | None = Field(default=None, max_length=128)
    date_of_birth: date | None = None
    document_type: str | None = Field(default=None, max_length=32)
    citizenship: str | None = Field(default=None, max_length=128)
    iin: str | None = Field(default=None, max_length=32)
    document_number: str | None = Field(default=None, max_length=64)
    document_issue_date: date | None = None
    document_issued_by: str | None = Field(default=None, max_length=255)
    father_last: str | None = Field(default=None, max_length=128)
    father_first: str | None = Field(default=None, max_length=128)
    father_middle: str | None = Field(default=None, max_length=128)
    father_phone: str | None = Field(default=None, max_length=32)
    mother_last: str | None = Field(default=None, max_length=128)
    mother_first: str | None = Field(default=None, max_length=128)
    mother_middle: str | None = Field(default=None, max_length=128)
    mother_phone: str | None = Field(default=None, max_length=32)
    guardian_last: str | None = Field(default=None, max_length=128)
    guardian_first: str | None = Field(default=None, max_length=128)
    guardian_middle: str | None = Field(default=None, max_length=128)
    guardian_phone: str | None = Field(default=None, max_length=32)
    consent_privacy: bool = False
    consent_age: bool = False
    pronouns: str | None = Field(default=None, max_length=64)
    gender: str | None = Field(default=None, max_length=64)
    nationality: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    short_self_introduction: str | None = Field(default=None, max_length=2000)
    identity_document_id: UUID | None = None

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_date_of_birth(cls, v: Any) -> date | None:
        return parse_optional_date(v)

    @field_validator("document_issue_date", mode="before")
    @classmethod
    def parse_document_issue_date(cls, v: Any) -> date | None:
        return parse_optional_date(v)


class ContactSectionPayload(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=32)
    alternate_phone_e164: str | None = Field(default=None, max_length=32)
    address_line1: str = Field(min_length=1, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str = Field(min_length=2, max_length=2)
    street: str | None = Field(default=None, max_length=255)
    house: str | None = Field(default=None, max_length=64)
    apartment: str | None = Field(default=None, max_length=32)
    instagram: str | None = Field(default=None, max_length=128)
    telegram: str | None = Field(default=None, max_length=128)
    whatsapp: str | None = Field(default=None, max_length=32)
    preferred_communication_channel: str | None = Field(default=None, max_length=64)
    guardian_name: str | None = Field(default=None, max_length=255)
    guardian_phone_e164: str | None = Field(default=None, max_length=32)
    guardian_email: str | None = Field(default=None, max_length=255)
    emergency_contact_name: str | None = Field(default=None, max_length=255)
    emergency_contact_phone_e164: str | None = Field(default=None, max_length=32)
    consent_privacy: bool = False
    consent_parent: bool = False


class EducationItemPayload(BaseModel):
    institution_name: str = Field(min_length=1, max_length=255)
    degree_or_program: str | None = Field(default=None, max_length=255)
    field_of_study: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    gpa_or_equivalent: str | None = Field(default=None, max_length=32)
    honors_or_awards: str | None = Field(default=None, max_length=500)
    coursework_highlights: str | None = Field(default=None, max_length=2000)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_education_item_dates(cls, v: Any) -> date | None:
        return parse_optional_date(v)


class EducationSectionPayload(BaseModel):
    entries: list[EducationItemPayload] = Field(default_factory=list, max_length=20)
    presentation_video_url: str | None = Field(default=None, max_length=2048)
    english_proof_kind: str | None = Field(default=None, max_length=32)
    certificate_proof_kind: str | None = Field(default=None, max_length=32)
    english_document_id: UUID | None = None
    certificate_document_id: UUID | None = None
    additional_document_id: UUID | None = None


class AchievementLinkItem(BaseModel):
    link_type: str = Field(max_length=32)
    label: str = Field(max_length=64)
    url: str = Field(default="", max_length=4096)


class AchievementsActivitiesSectionPayload(BaseModel):
    achievements_text: str = Field(min_length=1, max_length=500)
    role: str = Field(default="", max_length=50)
    year: str = Field(default="", max_length=4)
    links: list[AchievementLinkItem] = Field(default_factory=list, max_length=8)
    consent_privacy: bool = False
    consent_parent: bool = False


class LeadershipEvidenceItem(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    scope: str | None = Field(default=None, max_length=500)
    outcome: str | None = Field(default=None, max_length=2000)
    supporting_document_ids: list[UUID] = Field(default_factory=list, max_length=10)


class LeadershipEvidenceSectionPayload(BaseModel):
    items: list[LeadershipEvidenceItem] = Field(min_length=1, max_length=20)


class MotivationGoalsSectionPayload(BaseModel):
    narrative: str = Field(min_length=350, max_length=1000)
    was_pasted: bool = False
    paste_count: int = Field(default=0, ge=0)
    last_pasted_at: datetime | None = None
    motivation_document_id: UUID | None = None

    @field_validator("last_pasted_at", mode="before")
    @classmethod
    def parse_last_pasted_at(cls, v: Any) -> datetime | None:
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class GrowthAnswerMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")

    was_pasted: bool = False
    paste_count: int = Field(default=0, ge=0)
    last_pasted_at: datetime | None = None
    typing_count: int = Field(default=0, ge=0)
    typing_duration_ms: int = Field(default=0, ge=0)
    was_edited_after_paste: bool = False
    delete_count: int = Field(default=0, ge=0)
    revision_count: int = Field(default=0, ge=0)

    @field_validator("last_pasted_at", mode="before")
    @classmethod
    def parse_last_pasted_at_growth(cls, v: Any) -> datetime | None:
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class GrowthAnswerPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(default="", max_length=700)
    meta: GrowthAnswerMeta | None = None


class GrowthJourneySectionPayload(BaseModel):
    """Пять ответов о траектории роста; согласия как на других вкладках."""

    model_config = ConfigDict(extra="ignore")

    answers: dict[str, GrowthAnswerPayload]
    consent_privacy: bool = False
    consent_parent: bool = False
    growth_document_id: UUID | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_and_normalize_answers(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "answers" not in out and out.get("narrative") is not None:
            n = str(out.get("narrative") or "")
            out["answers"] = {
                "q1": {"text": n},
                "q2": {"text": "." * GROWTH_CHAR_LIMITS["q2"][0]},
                "q3": {"text": "." * GROWTH_CHAR_LIMITS["q3"][0]},
                "q4": {"text": "." * GROWTH_CHAR_LIMITS["q4"][0]},
                "q5": {"text": "." * GROWTH_CHAR_LIMITS["q5"][0]},
            }
        ans = out.get("answers")
        if isinstance(ans, dict):
            for qid in GROWTH_QUESTION_ORDER:
                if qid not in ans:
                    lo, _ = GROWTH_CHAR_LIMITS[qid]
                    ans[qid] = {"text": "." * lo}
            for k, v in list(ans.items()):
                if isinstance(v, dict) and "text" in v:
                    nv = dict(v)
                    nv["text"] = normalize_growth_text(str(nv.get("text") or ""))
                    ans[k] = nv
            out["answers"] = ans
        return out

    @model_validator(mode="after")
    def _check_question_ranges(self) -> GrowthJourneySectionPayload:
        for qid in GROWTH_QUESTION_ORDER:
            if qid not in self.answers:
                raise ValueError(f"missing answer {qid}")
            t = self.answers[qid].text
            lo, hi = GROWTH_CHAR_LIMITS[qid]
            if len(t) < lo or len(t) > hi:
                raise ValueError(f"invalid length for {qid}")
        return self


def growth_journey_section_complete(v: GrowthJourneySectionPayload) -> bool:
    if not v.consent_privacy or not v.consent_parent:
        return False
    for qid in GROWTH_QUESTION_ORDER:
        t = v.answers[qid].text
        lo, hi = GROWTH_CHAR_LIMITS[qid]
        if len(t) < lo or len(t) > hi:
            return False
    return True


class InternalTestSectionPayload(BaseModel):
    """Placeholder in section state; real answers live in internal_test_answers."""

    acknowledged_instructions: bool = True
    consent_privacy: bool = False
    consent_parent: bool = False


class SocialStatusSectionPayload(BaseModel):
    """Certificate upload tracked via documents; this confirms attestation text."""

    attestation: str = Field(min_length=10, max_length=2000)


class DocumentsManifestSectionPayload(BaseModel):
    """Acknowledgment that required documents are uploaded or will be."""

    acknowledged_required_documents: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class ConsentAgreementSectionPayload(BaseModel):
    accepted_terms: bool = False
    accepted_privacy: bool = False
    consent_policy_version: str = Field(min_length=1, max_length=64)
    accepted_at: datetime | None = None

    @field_validator("accepted_at", mode="before")
    @classmethod
    def parse_accepted_at(cls, v: Any) -> datetime | None:
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


def parse_and_validate_section(section_key: SectionKey, payload: dict[str, Any]) -> BaseModel:
    match section_key:
        case SectionKey.personal:
            return PersonalSectionPayload.model_validate(payload)
        case SectionKey.contact:
            return ContactSectionPayload.model_validate(payload)
        case SectionKey.education:
            return EducationSectionPayload.model_validate(payload)
        case SectionKey.achievements_activities:
            return AchievementsActivitiesSectionPayload.model_validate(payload)
        case SectionKey.leadership_evidence:
            return LeadershipEvidenceSectionPayload.model_validate(payload)
        case SectionKey.motivation_goals:
            return MotivationGoalsSectionPayload.model_validate(payload)
        case SectionKey.growth_journey:
            return GrowthJourneySectionPayload.model_validate(payload)
        case SectionKey.internal_test:
            return InternalTestSectionPayload.model_validate(payload)
        case SectionKey.social_status_cert:
            return SocialStatusSectionPayload.model_validate(payload)
        case SectionKey.documents_manifest:
            return DocumentsManifestSectionPayload.model_validate(payload)
        case SectionKey.consent_agreement:
            return ConsentAgreementSectionPayload.model_validate(payload)
    raise ValueError("Unknown section")
