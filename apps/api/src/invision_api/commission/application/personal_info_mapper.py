from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from invision_api.commission.domain.mapping import application_to_commission_column
from invision_api.commission.domain.types import AIPlaceholderSummary
from invision_api.models.application import Application, Document
from invision_api.models.commission import ApplicationCommissionProjection


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _iso_date_or_none(value: Any) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if len(text) >= 10:
            return text[:10]
    return None


def _compute_age(value: Any) -> int | None:
    if isinstance(value, date):
        birth_date = value
    elif isinstance(value, str):
        try:
            birth_date = date.fromisoformat(value[:10])
        except ValueError:
            return None
    else:
        return None
    today = datetime.now(tz=UTC).date()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _format_size(value: int | None) -> str | None:
    if value is None:
        return None
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


def _build_full_name(last: str | None, first: str | None, middle: str | None) -> str | None:
    parts = [p for p in [_str_or_none(last), _str_or_none(first), _str_or_none(middle)] if p]
    if not parts:
        return None
    return " ".join(parts)


def _map_guardians(personal: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    candidates = [
        (
            "Мать",
            _build_full_name(personal.get("mother_last"), personal.get("mother_first"), personal.get("mother_middle")),
            _str_or_none(personal.get("mother_phone")),
        ),
        (
            "Отец",
            _build_full_name(personal.get("father_last"), personal.get("father_first"), personal.get("father_middle")),
            _str_or_none(personal.get("father_phone")),
        ),
        (
            "Опекун",
            _build_full_name(personal.get("guardian_last"), personal.get("guardian_first"), personal.get("guardian_middle")),
            _str_or_none(personal.get("guardian_phone")),
        ),
    ]
    for role, full_name, phone in candidates:
        if not full_name and not phone:
            continue
        entries.append(
            {
                "role": role,
                "fullName": full_name or "—",
                "phone": phone,
            }
        )
    return entries


def _map_address(contact: dict[str, Any]) -> dict[str, Any]:
    country = _str_or_none(contact.get("country"))
    region = _str_or_none(contact.get("region"))
    city = _str_or_none(contact.get("city"))
    full_address = _str_or_none(contact.get("address_line1"))
    if full_address is None:
        parts = [
            _str_or_none(contact.get("street")),
            _str_or_none(contact.get("house")),
            _str_or_none(contact.get("apartment")),
            city,
            region,
            country,
        ]
        parts = [p for p in parts if p]
        full_address = ", ".join(parts) if parts else None
    return {
        "country": country,
        "region": region,
        "city": city,
        "fullAddress": full_address,
    }


def _proof_kind_to_type(kind: str | None, fallback: str) -> str:
    if not kind:
        return fallback
    normalized = kind.strip().lower()
    if "ielts" in normalized:
        return "IELTS"
    if "toefl" in normalized:
        return "TOEFL"
    if "ent" in normalized or "ент" in normalized:
        return "ЕНТ"
    return fallback


def _map_documents(
    *,
    documents: list[Document],
    personal: dict[str, Any],
    education: dict[str, Any],
) -> list[dict[str, Any]]:
    docs_by_id = {d.id: d for d in documents}
    output: list[dict[str, Any]] = []
    used: set[UUID] = set()

    def append_doc(doc_id: UUID | None, type_name: str) -> None:
        if doc_id is None or doc_id in used:
            return
        doc = docs_by_id.get(doc_id)
        if not doc:
            return
        used.add(doc_id)
        output.append(
            {
                "id": str(doc.id),
                "type": type_name,
                "fileName": doc.original_filename,
                "fileSize": _format_size(doc.byte_size),
                "fileUrl": None,
                "fileRef": doc.storage_key,
            }
        )

    identity_id = _to_uuid(personal.get("identity_document_id"))
    english_id = _to_uuid(education.get("english_document_id"))
    certificate_id = _to_uuid(education.get("certificate_document_id"))
    additional_id = _to_uuid(education.get("additional_document_id"))

    append_doc(identity_id, "Удостоверение личности/паспорт")
    append_doc(english_id, _proof_kind_to_type(_str_or_none(education.get("english_proof_kind")), "Сертификат по английскому"))
    append_doc(certificate_id, _proof_kind_to_type(_str_or_none(education.get("certificate_proof_kind")), "Сертификат"))
    append_doc(additional_id, "Другое")

    for doc in documents:
        if doc.id in used:
            continue
        append_doc(doc.id, "Другое")
    return output


def _map_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in comments:
        created_at = row.get("created_at")
        created_at_iso = created_at.isoformat() if isinstance(created_at, datetime) else None
        author_name = _str_or_none(row.get("author_name"))
        author_user_id = row.get("author_user_id")
        out.append(
            {
                "id": str(row["id"]),
                "text": str(row.get("text") or ""),
                "authorName": author_name or (str(author_user_id) if author_user_id else "system"),
                "createdAt": created_at_iso,
            }
        )
    return out


def build_personal_info_view(
    *,
    app: Application,
    projection: ApplicationCommissionProjection,
    sections: dict[str, Any],
    stage_status: str,
    ai_summary: AIPlaceholderSummary,
    personality_profile: dict[str, Any] | None,
    comments: list[dict[str, Any]],
    documents: list[Document],
    actions: dict[str, Any],
    processing_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    personal = sections.get("personal") if isinstance(sections.get("personal"), dict) else {}
    contact = sections.get("contact") if isinstance(sections.get("contact"), dict) else {}
    education = sections.get("education") if isinstance(sections.get("education"), dict) else {}

    full_name = projection.candidate_full_name or _build_full_name(
        personal.get("preferred_last_name"),
        personal.get("preferred_first_name"),
        personal.get("middle_name"),
    )
    birth_date = _iso_date_or_none(personal.get("date_of_birth"))
    age = projection.age if isinstance(projection.age, int) else _compute_age(birth_date)
    mapped_stage = application_to_commission_column(app.current_stage)

    ai_profile_title = None
    if personality_profile and isinstance(personality_profile, dict):
        meta = personality_profile.get("meta")
        answer_count = meta.get("answerCount") if isinstance(meta, dict) else None
        if isinstance(answer_count, int) and answer_count > 0:
            ai_profile_title = _str_or_none(personality_profile.get("profileTitle"))

    has_ai_content = bool(ai_summary.summary_text or ai_summary.strengths or ai_summary.weak_points or ai_profile_title)

    candidate_phone = _str_or_none(contact.get("phone_e164")) or projection.phone
    candidate_telegram = _str_or_none(contact.get("telegram"))
    candidate_instagram = _str_or_none(contact.get("instagram"))
    video_url = _str_or_none(education.get("presentation_video_url"))

    return {
        "applicationId": str(app.id),
        "candidateSummary": {
            "fullName": full_name or "Кандидат",
            "program": projection.program,
            "phone": candidate_phone,
            "telegram": candidate_telegram,
            "instagram": candidate_instagram,
            "submittedAt": app.submitted_at.isoformat() if app.submitted_at else None,
            "currentStage": mapped_stage,
            "currentStageStatus": stage_status,
        },
        "aiSummary": (
            {
                "profileTitle": ai_profile_title,
                "summaryText": ai_summary.summary_text,
                "strengths": list(ai_summary.strengths or []),
                "weakPoints": list(ai_summary.weak_points or []),
            }
            if has_ai_content
            else None
        ),
        "stageContext": {
            "currentStage": mapped_stage,
            "currentStageStatus": stage_status,
            "availableActions": ["move_forward"] if actions.get("canMoveForward") else [],
        },
        "personalInfo": {
            "basicInfo": {
                "fullName": full_name or "Кандидат",
                "gender": _str_or_none(personal.get("gender")),
                "birthDate": birth_date,
                "age": age,
            },
            "guardians": _map_guardians(personal),
            "address": _map_address(contact),
            "contacts": {
                "phone": candidate_phone,
                "instagram": candidate_instagram,
                "telegram": candidate_telegram,
                "whatsapp": _str_or_none(contact.get("whatsapp")),
            },
            "documents": _map_documents(documents=documents, personal=personal, education=education),
            "videoPresentation": {"url": video_url} if video_url else None,
        },
        "processingStatus": processing_status,
        "comments": _map_comments(comments),
        "actions": {
            "canComment": bool(actions.get("canComment")),
            "canMoveForward": bool(actions.get("canMoveForward")),
        },
    }

