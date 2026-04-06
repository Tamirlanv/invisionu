"""Sidebar panel content builder for the commission candidate detail page.

Two panel types:
- 'validation' for the Personal Info tab (deterministic checks only, no LLM)
- 'summary' for Test / Motivation / Path / Achievements tabs
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import AIReviewMetadata, Application, TextAnalysisRun
from invision_api.models.candidate_signals_aggregate import CandidateSignalsAggregate
from invision_api.models.data_check_unit_result import DataCheckUnitResult
from invision_api.repositories import data_check_repository
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES, UNIT_POLICIES, compute_run_status
from invision_api.models.enums import ApplicationStage, DataCheckUnitType
from invision_api.repositories import ai_interview_repository
from invision_api.services import engagement_scoring_service
from invision_api.commission.application.reviewer_text_sanitizer import (
    dedupe_keep_order as _shared_dedupe_keep_order,
    is_ui_friendly_sentence as _shared_is_ui_friendly_sentence,
    sanitize_reviewer_text as _shared_sanitize_reviewer_text,
    split_sentences as _shared_split_sentences,
    strip_technical_residue as _shared_strip_technical_residue,
    truncate_sentence as _shared_truncate_sentence,
)

logger = logging.getLogger(__name__)

# Подписи для комиссии (без snake_case в UI)
_DATA_CHECK_UNIT_LABEL_RU: dict[str, str] = {
    DataCheckUnitType.test_profile_processing.value: "Профиль теста",
    DataCheckUnitType.motivation_processing.value: "Мотивация",
    DataCheckUnitType.growth_path_processing.value: "Траектория роста",
    DataCheckUnitType.achievements_processing.value: "Достижения",
    DataCheckUnitType.link_validation.value: "Ссылки",
    DataCheckUnitType.video_validation.value: "Видео-презентация",
    DataCheckUnitType.certificate_validation.value: "Документы и сертификаты",
    DataCheckUnitType.signals_aggregation.value: "Сводка сигналов по заявке",
    DataCheckUnitType.candidate_ai_summary.value: "Итоговая сводка по заявке",
}


def _data_check_unit_label_ru(unit_type: str) -> str:
    """Человекочитаемая подпись этапа проверки данных для сайдбара комиссии."""
    return _DATA_CHECK_UNIT_LABEL_RU.get(unit_type, "Проверка данных")


_TAB_TO_PANEL_TYPE: dict[str, str] = {
    "personal": "validation",
    "test": "summary",
    "motivation": "summary",
    "path": "summary",
    "achievements": "summary",
}

_TAB_TO_BLOCK_KEY: dict[str, str] = {
    "test": "test_profile",
    "motivation": "motivation_goals",
    "path": "growth_journey",
    "achievements": "achievements_activities",
}


AttentionNoteCategory = Literal["originality", "consistency", "paste_behavior", "content_quality"]
AttentionSeverity = Literal["low", "medium", "high"]


def _make_attention_note(
    *,
    category: AttentionNoteCategory,
    title: str,
    message: str,
    severity: AttentionSeverity,
    confidence: float | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "category": category,
        "title": title,
        "message": message,
        "severity": severity,
    }
    if confidence is not None:
        out["confidence"] = round(max(0.0, min(1.0, confidence)), 2)
    return out


SidebarItem = str | dict[str, Any]


def _section_block(
    title: str,
    items: list[SidebarItem],
    *,
    attention_notes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"title": title, "items": items}
    if attention_notes:
        out["attentionNotes"] = attention_notes
    return out


def _attention_section(
    title: str,
    notes: list[dict[str, Any]],
    *,
    empty_message: str = "Замечаний нет",
) -> dict[str, Any]:
    if not notes:
        return _section_block(title, [empty_message])
    items = [str(n.get("message", "")).strip() for n in notes if str(n.get("message", "")).strip()]
    if not items:
        items = [empty_message]
    return _section_block(title, items, attention_notes=notes)


def _doc_status_label(status: str | None) -> str:
    if status in {"completed", "passed"}:
        return "Проверено"
    if status in {"manual_review_required"}:
        return "Требует проверки"
    if status in {"failed"}:
        return "Ошибка"
    if status in {"running", "queued", "pending"}:
        return "В обработке"
    return "Не проверено"


_ENT_PASS_MIN = 80.0
_IELTS_PASS_MIN = 6.0


def _parse_numeric_score(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        if isinstance(raw, float) and raw != raw:  # NaN
            return None
        return float(raw)
    if isinstance(raw, str):
        s = raw.strip().replace(",", ".")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _certificate_exam_type_blob(ex: dict[str, Any], dr: dict[str, Any]) -> str:
    """Types from resolved classifier, OCR classifier, and top-level row (for sidebar slot + labels)."""
    parts = [
        str(ex.get("documentType") or ""),
        str(ex.get("ocrDocumentType") or ""),
        str(dr.get("documentType") or ""),
    ]
    return " ".join(parts).lower()


def _slot_from_type_hints(ex: dict[str, Any], dr: dict[str, Any]) -> str | None:
    """Infer english vs certificate from merged type strings (incl. ocrDocumentType when resolved is unknown)."""
    c = _certificate_exam_type_blob(ex, dr)
    if "ielts" in c or "toefl" in c:
        return "english"
    if "nis_12" in c or re.search(r"\bnis\b|ниш|nazarbayev|intellectual schools", c):
        return "certificate"
    if "ent" in c or "ент" in c or "unt" in c:
        return "certificate"
    return None


def _slot_for_certificate_result(
    dr: dict[str, Any],
    *,
    english_document_id: UUID | None,
    certificate_document_id: UUID | None,
    additional_document_id: UUID | None = None,
) -> str | None:
    """Map a certificate_validation result row to 'english' or 'certificate' using document id or type hints."""
    ex = dr.get("examDocument") if isinstance(dr.get("examDocument"), dict) else {}
    doc_id_str = ex.get("documentId")
    doc_uuid: UUID | None = None
    if isinstance(doc_id_str, str) and doc_id_str:
        try:
            doc_uuid = UUID(doc_id_str)
        except ValueError:
            doc_uuid = None

    if doc_uuid is not None:
        if english_document_id and doc_uuid == english_document_id:
            return "english"
        if certificate_document_id and doc_uuid == certificate_document_id:
            return "certificate"
        if additional_document_id and doc_uuid == additional_document_id:
            hinted = _slot_from_type_hints(ex, dr)
            if hinted is not None:
                return hinted

    return _slot_from_type_hints(ex, dr)


def _is_certificate_nis(ex: dict[str, Any], dr: dict[str, Any]) -> bool:
    c = _certificate_exam_type_blob(ex, dr)
    if "nis_12" in c:
        return True
    return bool(re.search(r"\bnis\b|ниш|nazarbayev|intellectual schools", c))


def _is_english_toefl(ex: dict[str, Any], dr: dict[str, Any]) -> bool:
    c = _certificate_exam_type_blob(ex, dr)
    return "toefl" in c


def _build_documents_scores_items(
    cert_unit: DataCheckUnitResult | None,
    *,
    english_document_id: UUID | None,
    certificate_document_id: UUID | None,
    additional_document_id: UUID | None = None,
) -> list[SidebarItem]:
    """ЕНТ / NIS / IELTS / TOEFL lines from certificate_validation first-stage payload (examDocument.detectedScore)."""
    ent_score: float | None = None
    nis_score: float | None = None
    ielts_score: float | None = None
    toefl_score: float | None = None

    if cert_unit and cert_unit.result_payload:
        for dr in cert_unit.result_payload.get("results") or []:
            if not isinstance(dr, dict):
                continue
            slot = _slot_for_certificate_result(
                dr,
                english_document_id=english_document_id,
                certificate_document_id=certificate_document_id,
                additional_document_id=additional_document_id,
            )
            ex = dr.get("examDocument") if isinstance(dr.get("examDocument"), dict) else {}
            score = _parse_numeric_score(ex.get("detectedScore"))
            if score is None:
                continue
            if slot == "certificate":
                if _is_certificate_nis(ex, dr):
                    nis_score = score
                else:
                    ent_score = score
            elif slot == "english":
                if _is_english_toefl(ex, dr):
                    toefl_score = score
                else:
                    ielts_score = score

    def _nis_item(score: float | None) -> dict[str, Any]:
        if score is None:
            return {"text": "NIS: —", "tone": "neutral"}
        display = str(int(score)) if score == int(score) else f"{score:.1f}".rstrip("0").rstrip(".")
        tone = "success" if score >= _ENT_PASS_MIN else "danger"
        return {"text": f"NIS: {display}", "tone": tone}

    def _ent_item(score: float | None) -> dict[str, Any]:
        if score is None:
            return {"text": "ЕНТ: —", "tone": "neutral"}
        display = str(int(score)) if score == int(score) else f"{score:.1f}".rstrip("0").rstrip(".")
        tone = "success" if score >= _ENT_PASS_MIN else "danger"
        return {"text": f"ЕНТ: {display}", "tone": tone}

    def _toefl_item(score: float | None) -> dict[str, Any]:
        if score is None:
            return {"text": "TOEFL: —", "tone": "neutral"}
        display = str(int(score)) if score == int(score) else f"{score:.1f}".rstrip("0").rstrip(".")
        tone = "success" if score >= 60 else "danger"
        return {"text": f"TOEFL: {display}", "tone": tone}

    def _ielts_item(score: float | None) -> dict[str, Any]:
        if score is None:
            return {"text": "IELTS: —", "tone": "neutral"}
        tone = "success" if score >= _IELTS_PASS_MIN else "danger"
        return {"text": f"IELTS: {score:.1f}", "tone": tone}

    cert_line: dict[str, Any]
    if ent_score is not None:
        cert_line = _ent_item(ent_score)
    elif nis_score is not None:
        cert_line = _nis_item(nis_score)
    else:
        cert_line = _ent_item(None)

    eng_line: dict[str, Any]
    if toefl_score is not None:
        eng_line = _toefl_item(toefl_score)
    elif ielts_score is not None:
        eng_line = _ielts_item(ielts_score)
    else:
        eng_line = {"text": "IELTS/TOEFL: —", "tone": "neutral"}

    return [cert_line, eng_line]


def compute_commission_document_borders(
    cert_unit: DataCheckUnitResult | None,
    *,
    english_document_id: UUID | None,
    certificate_document_id: UUID | None,
    additional_document_id: UUID | None,
) -> dict[str, str]:
    """Map document UUID string -> green | red | gray for commission documents list cards."""
    out: dict[str, str] = {}
    if not cert_unit or not cert_unit.result_payload:
        return out
    for dr in cert_unit.result_payload.get("results") or []:
        if not isinstance(dr, dict):
            continue
        ex = dr.get("examDocument") if isinstance(dr.get("examDocument"), dict) else {}
        doc_id_str = ex.get("documentId")
        if not isinstance(doc_id_str, str) or not doc_id_str.strip():
            continue
        score = _parse_numeric_score(ex.get("detectedScore"))
        slot = _slot_for_certificate_result(
            dr,
            english_document_id=english_document_id,
            certificate_document_id=certificate_document_id,
            additional_document_id=additional_document_id,
        )
        if slot is None:
            continue
        if slot == "english":
            if _is_english_toefl(ex, dr):
                if score is None:
                    tone = "green"
                else:
                    tone = "green" if score >= 60.0 else "gray"
            else:
                if score is None:
                    tone = "green"
                else:
                    tone = "green" if score >= _IELTS_PASS_MIN else "red"
        elif slot == "certificate":
            if _is_certificate_nis(ex, dr):
                if score is None:
                    tone = "green"
                else:
                    tone = "green" if score >= _ENT_PASS_MIN else "gray"
            else:
                if score is None:
                    tone = "green"
                else:
                    tone = "green" if score >= _ENT_PASS_MIN else "red"
        else:
            continue
        out[doc_id_str.strip()] = tone
    return out


def _build_validation_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    """Build sidebar for Personal Info tab — deterministic checks only."""
    unit_map: dict[str, DataCheckUnitResult] = {}
    run = data_check_repository.resolve_preferred_run_for_application(db, application_id)
    if run:
        results = data_check_repository.list_unit_results_for_run(db, run.id)
        for r in results:
            unit_map[r.unit_type] = r

    sections: list[dict[str, Any]] = []

    # Block 1: Application readiness
    status_items: list[str] = []
    checks_done = sum(1 for r in unit_map.values() if r.status in TERMINAL_UNIT_STATUSES)
    total = len(unit_map) if unit_map else 0
    if total == 0:
        status_items.append("Обработка еще не запускалась")
    elif checks_done == total:
        status_items.append(f"Все проверки завершены ({checks_done}/{total})")
    else:
        status_items.append(f"Проверки в процессе ({checks_done}/{total})")

    from invision_api.repositories import admissions_repository
    app = admissions_repository.get_application_by_id(db, application_id)
    if app:
        section_states = {ss.section_key: ss for ss in (app.section_states or [])}
        required_sections = ["personal", "contact", "education"]
        filled = sum(1 for s in required_sections if s in section_states and section_states[s].is_complete)
        if filled == len(required_sections):
            status_items.append("Основные данные заполнены")
        else:
            missing = [s for s in required_sections if s not in section_states or not section_states[s].is_complete]
            status_items.append(f"Не заполнены: {', '.join(missing)}")
    sections.append(_section_block("Статус анкеты", status_items))

    # Block 2: Documents
    doc_items: list[str] = []
    cert_unit = unit_map.get(DataCheckUnitType.certificate_validation.value)
    if cert_unit:
        payload = cert_unit.result_payload or {}
        doc_results = payload.get("results", [])
        if doc_results:
            for dr in doc_results:
                ps = dr.get("processingStatus", "pending")
                doc_items.append(f"Документ: {_doc_status_label(ps)}")
        else:
            doc_items.append(f"Документы: {_doc_status_label(cert_unit.status)}")
        if cert_unit.manual_review_required:
            doc_items.append("Требуется ручная проверка документов")
    else:
        doc_items.append("Проверка документов не запускалась")
    sections.append(_section_block("Проверка документов", doc_items))

    # Block 3: Media and links
    media_items: list[str] = []
    video_unit = unit_map.get(DataCheckUnitType.video_validation.value)
    if video_unit:
        vp = video_unit.result_payload or {}
        access = vp.get("accessStatus", "unknown")
        if access == "accessible":
            media_items.append("Видео-презентация: доступна")
        elif video_unit.status == "manual_review_required":
            media_items.append("Видео-презентация: требует ручной проверки")
        elif video_unit.status == "completed":
            media_items.append("Видео-презентация: проверена")
        else:
            media_items.append(f"Видео-презентация: {_doc_status_label(video_unit.status)}")
    else:
        media_items.append("Видео-презентация: не проверена")

    link_unit = unit_map.get(DataCheckUnitType.link_validation.value)
    if link_unit:
        lp = link_unit.result_payload or {}
        links = lp.get("links", [])
        if not links:
            media_items.append("Ссылки: не приложены")
        else:
            reachable = sum(1 for ln in links if ln.get("isReachable"))
            if reachable == len(links):
                media_items.append(f"Ссылки: все доступны ({len(links)})")
            else:
                media_items.append(f"Ссылки: {reachable}/{len(links)} доступны")
        if link_unit.manual_review_required:
            media_items.append("Требуется проверка ссылок")
    else:
        media_items.append("Ссылки: не проверены")
    sections.append(_section_block("Медиа и ссылки", media_items))

    # Block 4: Document scores from first-stage certificate validation (ЕНТ / IELTS)
    edu_payload = _get_section_payloads(db, application_id).get("education") or {}
    eng_doc_id = edu_payload.get("english_document_id")
    cert_doc_id = edu_payload.get("certificate_document_id")
    add_doc_id = edu_payload.get("additional_document_id")

    def _uuid_or_none(val: Any) -> UUID | None:
        if val is None:
            return None
        try:
            return val if isinstance(val, UUID) else UUID(str(val))
        except (ValueError, TypeError):
            return None

    english_uuid = _uuid_or_none(eng_doc_id)
    certificate_uuid = _uuid_or_none(cert_doc_id)
    additional_uuid = _uuid_or_none(add_doc_id)
    sections.append(
        _section_block(
            "Документы",
            _build_documents_scores_items(
                cert_unit,
                english_document_id=english_uuid,
                certificate_document_id=certificate_uuid,
                additional_document_id=additional_uuid,
            ),
        )
    )

    return {
        "type": "validation",
        "title": "Состояние данных",
        "sections": sections,
    }


def _get_analysis_run(db: Session, application_id: UUID, block_key: str) -> TextAnalysisRun | None:
    return db.scalars(
        select(TextAnalysisRun)
        .where(TextAnalysisRun.application_id == application_id, TextAnalysisRun.block_key == block_key)
        .order_by(TextAnalysisRun.created_at.desc())
    ).first()


def _get_analysis_runs(db: Session, application_id: UUID, block_key: str) -> list[TextAnalysisRun]:
    return list(
        db.scalars(
            select(TextAnalysisRun)
            .where(TextAnalysisRun.application_id == application_id, TextAnalysisRun.block_key == block_key)
            .order_by(TextAnalysisRun.created_at.desc())
        ).all()
    )


def _get_section_payloads(db: Session, application_id: UUID) -> dict[str, dict[str, Any]]:
    from invision_api.repositories import admissions_repository

    app = admissions_repository.get_application_by_id(db, application_id)
    if not app:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for ss in app.section_states or []:
        if isinstance(ss.payload, dict):
            out[ss.section_key] = ss.payload
    return out


def _build_test_summary_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    run = _get_analysis_run(db, application_id, "test_profile")
    explanations = (run.explanations or {}) if run else {}
    profile = explanations.get("profile", {})
    flags = (run.flags or {}) if run else {}

    # Block 1: Profile
    profile_items: list[str] = []
    profile_title = profile.get("profileTitle")
    if profile_title:
        profile_items.append(profile_title)
    profile_summary = profile.get("summary")
    if profile_summary:
        profile_items.append(
            _build_compact_summary(
                str(profile_summary),
                fallback="Краткий профиль пока недоступен.",
            )
        )
    if not profile_items:
        profile_items.append("Профиль ещё не определён")
    sections.append(_section_block("Профиль", profile_items))

    # Block 2: Strengths (top 2 traits)
    strength_items: list[str] = []
    ranking = profile.get("ranking", [])
    explain = profile.get("explainability", {})
    top_why = explain.get("topTraitsWhy", [])
    if ranking and len(ranking) >= 2:
        for i, entry in enumerate(ranking[:2]):
            trait = entry.get("trait", "?")
            label = _trait_label(trait)
            why = top_why[i] if i < len(top_why) else ""
            text = f"{label}: {why}" if why else label
            strength_items.append(text)
    if not strength_items:
        strength_items.append("Данные недоступны")
    sections.append(_section_block("Сильные стороны", strength_items))

    # Block 3: Growth zone (weakest trait)
    growth_items: list[str] = []
    weakest = profile.get("weakestTrait")
    less_expr = explain.get("lessExpressed", "")
    if weakest:
        label = _trait_label(weakest)
        text = f"{label}: {less_expr}" if less_expr else f"Менее выраженная шкала: {label}"
        growth_items.append(text)
    if not growth_items:
        growth_items.append("Данные недоступны")
    sections.append(_section_block("Зона роста", growth_items))

    # Block 4: Reliability
    reliability_items: list[str] = []
    meta = profile.get("meta", {})
    answer_count = meta.get("answerCount", 0)
    expected = meta.get("expectedQuestionCount", 40)
    if answer_count >= expected:
        reliability_items.append("Надёжность: высокая")
    elif answer_count >= expected * 0.75:
        reliability_items.append("Надёжность: средняя")
    else:
        reliability_items.append("Надёжность: интерпретировать осторожно")
    pf = profile.get("flags", {})
    if pf.get("shouldReviewForSocialDesirability"):
        reliability_items.append("Возможна социальная желательность ответов")
    if pf.get("consistencyWarning"):
        reliability_items.append("Обнаружена непоследовательность ответов")
    sections.append(_section_block("Надёжность интерпретации", reliability_items))

    return {
        "type": "summary",
        "title": "Тест",
        "sections": sections,
    }


_TRAIT_LABELS = {
    "INI": "Инициативность",
    "RES": "Устойчивость",
    "COL": "Коммуникабельность",
    "ADP": "Адаптивность",
    "REF": "Рефлексивность",
}


def _trait_label(key: str) -> str:
    return _TRAIT_LABELS.get(key, key)


def _first_sentence(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", clean)
    first = parts[0].strip() if parts else clean
    if len(first) > 180:
        first = first[:177].rstrip() + "..."
    return first


def _build_compact_summary(
    raw_text: str,
    *,
    fallback: str,
    max_sentences: int = 3,
    max_sentence_len: int = 220,
) -> str:
    """Build short human-readable summary (1-3 sentences) instead of raw string slicing."""
    source = _shared_strip_technical_residue(str(raw_text or ""))
    source = re.sub(r"\s+", " ", source).strip()
    if not source:
        return fallback

    summary_parts: list[str] = []
    for sentence in _shared_split_sentences(source):
        cleaned = _shared_strip_technical_residue(sentence)
        cleaned = _shared_sanitize_reviewer_text(cleaned)
        if not cleaned or not _shared_is_ui_friendly_sentence(cleaned):
            continue
        trimmed = _shared_truncate_sentence(cleaned, max_sentence_len)
        if trimmed:
            summary_parts.append(trimmed)
        if len(summary_parts) >= max_sentences:
            break

    if not summary_parts:
        cleaned = _shared_sanitize_reviewer_text(source)
        cleaned = _shared_strip_technical_residue(cleaned)
        if cleaned:
            summary_parts.append(_shared_truncate_sentence(cleaned, max_sentence_len))

    summary_parts = _shared_dedupe_keep_order([x for x in summary_parts if x])
    return " ".join(summary_parts) if summary_parts else fallback


def _detect_main_motivation_thesis(summary_text: str, narrative: str) -> str:
    source = (summary_text or "").strip() or (narrative or "").strip()
    if not source:
        return "Главная мотивация не определена"

    lower = source.lower()
    if any(k in lower for k in ("образован", "программа", "университет", "учеб")):
        return "Получить сильное образование и развиваться в выбранной сфере."
    if any(k in lower for k in ("карьер", "профес", "работ")):
        return "Построить профессиональную карьеру в выбранном направлении."
    if any(k in lower for k in ("вклад", "обще", "страна", "сообществ")):
        return "Принести пользу обществу и применить знания на практике."
    if any(k in lower for k in ("проект", "стартап", "бизнес", "инициатив")):
        return "Развивать собственные проекты и лидерские навыки."

    sentence = _first_sentence(source)
    if sentence:
        return sentence
    return "Главная мотивация не определена"


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_motivation_attention_notes(
    *,
    signals: dict[str, Any],
    motivation_payload: dict[str, Any],
    path_signals: dict[str, Any],
    achievements_signals: dict[str, Any],
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []

    mot_density = _to_float(signals.get("motivation_density"))
    evidence = _to_float(signals.get("evidence_density"))
    avg_sentence_len = _to_float(signals.get("avg_sentence_len"))
    word_count = int(signals.get("word_count", 0) or 0)

    # A) Originality (soft heuristics only; never deterministic claim)
    if (
        evidence is not None
        and evidence < 0.05
        and word_count >= 140
        and avg_sentence_len is not None
        and avg_sentence_len >= 18
    ):
        notes.append(
            _make_attention_note(
                category="originality",
                title="Оригинальность",
                message="Текст выглядит слишком шаблонно при низкой конкретике; стоит уточнить личный вклад на интервью.",
                severity="medium",
                confidence=0.71,
            )
        )
    elif evidence is not None and evidence < 0.05 and word_count >= 100:
        notes.append(
            _make_attention_note(
                category="originality",
                title="Оригинальность",
                message="В тексте много общих формулировок и мало фактических деталей; интерпретировать с осторожностью.",
                severity="low",
                confidence=0.64,
            )
        )

    # B) Cross-section consistency
    path_growth = _to_float(path_signals.get("growth"))
    path_concrete = _to_float(path_signals.get("concrete_experience"))
    ach_impact = _to_float(achievements_signals.get("impact_markers")) or 0.0
    ach_links = _to_float(achievements_signals.get("links_count")) or 0.0

    if (
        mot_density is not None
        and mot_density >= 0.35
        and (
            (path_growth is not None and path_growth < 0.3)
            or (path_concrete is not None and path_concrete < 0.3)
        )
    ):
        notes.append(
            _make_attention_note(
                category="consistency",
                title="Согласованность разделов",
                message="Заявленные цели в мотивации пока слабо поддержаны примерами из траектории роста; требует уточнения.",
                severity="medium",
                confidence=0.68,
            )
        )

    if mot_density is not None and mot_density >= 0.35 and ach_impact == 0 and ach_links == 0:
        notes.append(
            _make_attention_note(
                category="consistency",
                title="Согласованность разделов",
                message="Между мотивацией и блоком достижений не прослеживается явная связка подтверждающих результатов.",
                severity="low",
                confidence=0.6,
            )
        )

    # C) Paste behavior
    was_pasted = bool(motivation_payload.get("was_pasted", False))
    paste_count = int(motivation_payload.get("paste_count", 0) or 0)
    if was_pasted and paste_count >= 3:
        notes.append(
            _make_attention_note(
                category="paste_behavior",
                title="Вставки текста",
                message="Зафиксировано несколько вставок крупного текста; полезно проверить глубину самостоятельной проработки ответа.",
                severity="medium",
                confidence=0.74,
            )
        )
    elif was_pasted:
        notes.append(
            _make_attention_note(
                category="paste_behavior",
                title="Вставки текста",
                message="Часть текста была вставлена в поле; учитывать это как дополнительный сигнал при ручной оценке.",
                severity="low",
                confidence=0.58,
            )
        )

    # D) Content quality
    if word_count and word_count < 90:
        notes.append(
            _make_attention_note(
                category="content_quality",
                title="Содержательность",
                message="Текст краткий для уверенной интерпретации мотивации; стоит запросить больше конкретики.",
                severity="medium",
                confidence=0.76,
            )
        )
    elif evidence is not None and evidence < 0.03:
        notes.append(
            _make_attention_note(
                category="content_quality",
                title="Содержательность",
                message="Личный опыт и конкретные примеры раскрыты ограниченно.",
                severity="low",
                confidence=0.67,
            )
        )

    return notes[:6]


def _build_motivation_summary_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    runs = _get_analysis_runs(db, application_id, "motivation_goals")
    run = runs[0] if runs else None
    signals_run = next(
        (
            r
            for r in runs
            if isinstance((r.explanations or {}).get("signals"), dict)
            and bool((r.explanations or {}).get("signals"))
        ),
        None,
    )
    explanations = (signals_run.explanations or {}) if signals_run else ((run.explanations or {}) if run else {})
    signals = explanations.get("signals", {}) if isinstance(explanations.get("signals"), dict) else {}
    summary_text = str(explanations.get("summary") or "")

    section_payloads = _get_section_payloads(db, application_id)
    motivation_payload = section_payloads.get("motivation_goals") or section_payloads.get("motivation_letter") or {}
    if not isinstance(motivation_payload, dict):
        motivation_payload = {}

    if ("was_pasted" not in motivation_payload or "paste_count" not in motivation_payload) and run:
        run_explanations = run.explanations or {}
        if isinstance(run_explanations, dict):
            if "was_pasted" in run_explanations:
                motivation_payload["was_pasted"] = bool(run_explanations.get("was_pasted"))
            if "paste_count" in run_explanations:
                motivation_payload["paste_count"] = int(run_explanations.get("paste_count", 0) or 0)

    narrative = str(motivation_payload.get("narrative") or "").strip()

    # Block 0: Main motivation thesis (required)
    main_thesis = _detect_main_motivation_thesis(str(summary_text or ""), narrative)
    sections.append(_section_block("Главная мотивация", [main_thesis]))

    # Block 1: Brief summary
    summary_items: list[str] = []
    if summary_text:
        summary_items.append(
            _build_compact_summary(
                str(summary_text),
                fallback="Сводка мотивации ещё не готова",
            )
        )
    elif narrative:
        summary_items.append(_detect_main_motivation_thesis("", narrative))
    else:
        summary_items.append("Сводка мотивации ещё не готова")
    sections.append(_section_block("Краткий вывод", summary_items))

    # Block 2: Key signals
    signal_items: list[str] = []
    mot_density = _to_float(signals.get("motivation_density"))
    evidence = _to_float(signals.get("evidence_density"))
    word_count = signals.get("word_count", 0)
    if mot_density is not None:
        if mot_density > 0.15:
            signal_items.append("Высокая мотивационная плотность")
        elif mot_density > 0.05:
            signal_items.append("Средняя мотивационная плотность")
        else:
            signal_items.append("Низкая мотивационная плотность")
    if evidence is not None:
        if evidence > 0.1:
            signal_items.append("Присутствуют конкретные примеры")
        else:
            signal_items.append("Мало конкретных примеров")
    if word_count:
        signal_items.append(f"Объём текста: {word_count} слов")
    if not signal_items:
        signal_items.append("Данные недоступны")
    sections.append(_section_block("Ключевые сигналы", signal_items))

    # Block 3: Attention (structured notes + backward-compatible items)
    path_run = _get_analysis_run(db, application_id, "growth_journey")
    path_signals = ((path_run.explanations or {}).get("section_signals", {})) if path_run else {}
    if not isinstance(path_signals, dict):
        path_signals = {}
    achievements_run = _get_analysis_run(db, application_id, "achievements_activities")
    achievements_signals = ((achievements_run.explanations or {}).get("signals", {})) if achievements_run else {}
    if not isinstance(achievements_signals, dict):
        achievements_signals = {}

    attention_notes = _build_motivation_attention_notes(
        signals=signals,
        motivation_payload=motivation_payload,
        path_signals=path_signals,
        achievements_signals=achievements_signals,
    )
    sections.append(_attention_section("Требует внимания", attention_notes))

    # Block 4: Confidence
    conf_items: list[str] = []
    if signals_run and signals_run.status == "completed":
        conf_items.append("Анализ завершён успешно")
    elif run:
        conf_items.append(f"Статус обработки: {run.status}")
    else:
        conf_items.append("Обработка не запускалась")
    sections.append(_section_block("Надёжность", conf_items))

    return {
        "type": "summary",
        "title": "Мотивация",
        "sections": sections,
    }


_PATH_SIGNAL_LABELS: list[tuple[str, str]] = [
    ("initiative", "Инициатива"),
    ("resilience", "Устойчивость"),
    ("responsibility", "Ответственность"),
    ("growth", "Рост / рефлексия"),
]


def _strip_technical_residue(text: str) -> str:
    return _shared_strip_technical_residue(text)


def _split_sentences(text: str) -> list[str]:
    return _shared_split_sentences(text)


def _truncate_sentence(text: str, limit: int) -> str:
    return _shared_truncate_sentence(text, limit)


def _is_ui_friendly_sentence(text: str) -> bool:
    return _shared_is_ui_friendly_sentence(text)


def _dedupe_keep_order(items: list[str]) -> list[str]:
    return _shared_dedupe_keep_order(items)


def _format_signal_level(name: str, value: Any) -> str | None:
    if value is None:
        return None
    v = float(value)
    if v >= 0.7:
        return f"{name}: выраженный"
    if v >= 0.3:
        return f"{name}: средний"
    return f"{name}: низкий"


def _extract_key_excerpts(
    raw_pq: dict[str, Any] | list[Any],
    section_signals: dict[str, Any] | None = None,
) -> list[str]:
    """Build short, commission-friendly theses from per-question analysis."""
    items: list[dict[str, Any]] = (
        list(raw_pq.values()) if isinstance(raw_pq, dict) else (raw_pq if isinstance(raw_pq, list) else [])
    )
    theses: list[str] = []
    for pq in items[:5]:
        sentences = pq.get("key_sentences") or []
        picked = ""
        for sent in sentences[:2]:
            cleaned = _truncate_sentence(_strip_technical_residue(str(sent)), 110)
            if _is_ui_friendly_sentence(cleaned):
                picked = cleaned
                break
        if picked:
            theses.append(picked)

    theses = _dedupe_keep_order(theses)

    if len(theses) < 2 and section_signals:
        fallback_map: list[tuple[str, str, str]] = [
            (
                "initiative",
                "В траектории роста заметна инициативность и готовность действовать самостоятельно.",
                "Инициативность проявляется точечно и требует дальнейшего развития.",
            ),
            (
                "resilience",
                "Кандидат демонстрирует устойчивость при столкновении с трудностями.",
                "Устойчивость формируется, но пока проявляется не во всех ситуациях.",
            ),
            (
                "responsibility",
                "В ответах прослеживается личная ответственность за общий результат.",
                "Личная ответственность обозначена, но раскрыта не во всех примерах.",
            ),
            (
                "growth",
                "Есть признаки осознанной рефлексии и движения к личному росту.",
                "Рефлексия и рост присутствуют, но пока раскрыты ограниченно.",
            ),
        ]
        for key, strong, developing in fallback_map:
            value = section_signals.get(key)
            if value is None:
                continue
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue
            theses.append(strong if v >= 0.7 else developing)
            if len(theses) >= 4:
                break

    theses = _dedupe_keep_order(theses)
    if not theses:
        return ["Пока недостаточно данных, чтобы выделить факторы, сформировавшие кандидата."]
    return theses[:4]


def _path_paste_signals(growth_payload: dict[str, Any]) -> dict[str, int]:
    answers = growth_payload.get("answers")
    if not isinstance(answers, dict):
        return {
            "pasted_answers_count": 0,
            "total_paste_count": 0,
            "low_edit_after_paste_count": 0,
            "very_short_typing_count": 0,
        }
    pasted_answers_count = 0
    total_paste_count = 0
    low_edit_after_paste_count = 0
    very_short_typing_count = 0
    for answer in answers.values():
        if not isinstance(answer, dict):
            continue
        meta = answer.get("meta")
        if not isinstance(meta, dict):
            continue
        was_pasted = bool(meta.get("was_pasted", False))
        paste_count = int(meta.get("paste_count", 0) or 0)
        edited_after_paste = bool(meta.get("was_edited_after_paste", False))
        typing_duration_ms = int(meta.get("typing_duration_ms", 0) or 0)
        if was_pasted:
            pasted_answers_count += 1
            if not edited_after_paste:
                low_edit_after_paste_count += 1
        if paste_count > 0:
            total_paste_count += paste_count
        if was_pasted and typing_duration_ms > 0 and typing_duration_ms < 20000:
            very_short_typing_count += 1
    return {
        "pasted_answers_count": pasted_answers_count,
        "total_paste_count": total_paste_count,
        "low_edit_after_paste_count": low_edit_after_paste_count,
        "very_short_typing_count": very_short_typing_count,
    }


def _build_path_attention_notes(
    raw_pq: dict[str, Any] | list[Any],
    section_signals: dict[str, Any],
    *,
    growth_payload: dict[str, Any] | None = None,
    motivation_signals: dict[str, Any] | None = None,
    achievements_signals: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    items_list: list[dict[str, Any]] = (
        list(raw_pq.values()) if isinstance(raw_pq, dict) else (raw_pq if isinstance(raw_pq, list) else [])
    )
    notes: list[dict[str, Any]] = []

    # A) Originality-like signals (soft heuristics)
    low_specificity_count = 0
    lexical_low_count = 0
    repetitive_count = 0
    spam_like_count = 0
    for pq in items_list:
        stats = pq.get("stats") or {}
        heur = pq.get("heuristics") or {}
        spam = pq.get("spam_check") or {}
        unique_ratio = _to_float(stats.get("unique_word_ratio"))
        action = _to_float(heur.get("action_score"))
        reflection = _to_float(heur.get("reflection_score"))
        time_score = _to_float(heur.get("time_score"))
        concrete_score = _to_float(heur.get("concrete_score"))
        repetitive = _to_float(heur.get("repetitive_score"))
        if unique_ratio is not None and unique_ratio < 0.4:
            lexical_low_count += 1
        if repetitive is not None and repetitive >= 0.45:
            repetitive_count += 1
        if spam.get("ok") is False:
            spam_like_count += 1
        if (
            action is not None
            and reflection is not None
            and time_score is not None
            and concrete_score is not None
            and action < 0.25
            and reflection < 0.25
            and time_score < 0.25
            and concrete_score < 0.25
        ):
            low_specificity_count += 1

    if low_specificity_count >= 2 or (lexical_low_count >= 2 and repetitive_count >= 2):
        notes.append(
            _make_attention_note(
                category="originality",
                title="Оригинальность",
                message="Часть ответов выглядит шаблонно и слабо персонализировано; рекомендуется уточнить детали на интервью.",
                severity="medium",
                confidence=0.72,
            )
        )
    elif lexical_low_count >= 1 and repetitive_count >= 1:
        notes.append(
            _make_attention_note(
                category="originality",
                title="Оригинальность",
                message="В ответах заметна повторяемость формулировок и ограниченная вариативность лексики.",
                severity="low",
                confidence=0.61,
            )
        )

    # B) Cross-section consistency
    m_signals = motivation_signals or {}
    a_signals = achievements_signals or {}
    mot_density = _to_float(m_signals.get("motivation_density"))
    path_growth = _to_float(section_signals.get("growth"))
    path_concrete = _to_float(section_signals.get("concrete_experience"))
    ach_impact = _to_float(a_signals.get("impact_markers")) or 0.0
    ach_links = _to_float(a_signals.get("links_count")) or 0.0
    if mot_density is not None and mot_density >= 0.35 and path_growth is not None and path_growth < 0.3:
        notes.append(
            _make_attention_note(
                category="consistency",
                title="Согласованность разделов",
                message="Между мотивационными акцентами и описанной траекторией роста видна неполная связка; требует уточнения.",
                severity="medium",
                confidence=0.67,
            )
        )
    if ach_impact >= 2 and (path_concrete is not None and path_concrete < 0.3):
        notes.append(
            _make_attention_note(
                category="consistency",
                title="Согласованность разделов",
                message="В достижениях заявлены сильные результаты, но в «Пути» недостаточно конкретных эпизодов, которые их поддерживают.",
                severity="low",
                confidence=0.63,
            )
        )
    if mot_density is not None and mot_density >= 0.35 and ach_impact == 0 and ach_links == 0:
        notes.append(
            _make_attention_note(
                category="consistency",
                title="Согласованность разделов",
                message="Между разделами «Путь», «Мотивация» и «Достижения» пока не прослеживается явная подтверждающая связка.",
                severity="low",
                confidence=0.58,
            )
        )

    # C) Paste behavior
    paste = _path_paste_signals(growth_payload or {})
    pasted_answers = paste["pasted_answers_count"]
    total_pastes = paste["total_paste_count"]
    low_edit = paste["low_edit_after_paste_count"]
    short_typing = paste["very_short_typing_count"]
    if pasted_answers >= 3 and low_edit >= 2:
        notes.append(
            _make_attention_note(
                category="paste_behavior",
                title="Вставки текста",
                message="Значимая часть ответов была вставлена, а последующее редактирование ограничено; полезна дополнительная проверка аутентичности.",
                severity="medium",
                confidence=0.78,
            )
        )
    elif total_pastes >= 4 or (pasted_answers >= 2 and short_typing >= 1):
        notes.append(
            _make_attention_note(
                category="paste_behavior",
                title="Вставки текста",
                message="Зафиксировано несколько вставок в ответах; учитывать это как дополнительный сигнал при ручной интерпретации.",
                severity="low",
                confidence=0.62,
            )
        )

    # D) Content quality
    word_counts = [(pq.get("stats") or {}).get("word_count", 0) for pq in items_list]
    short_answers = sum(1 for wc in word_counts if wc and wc < 60)
    concrete = _to_float(section_signals.get("concrete_experience"))
    growth = _to_float(section_signals.get("growth"))
    if spam_like_count > 0:
        notes.append(
            _make_attention_note(
                category="content_quality",
                title="Качество содержания",
                message="Часть ответов требует дополнительной проверки на содержательность и самостоятельную проработку.",
                severity="medium",
                confidence=0.74,
            )
        )
    if short_answers > 0:
        notes.append(
            _make_attention_note(
                category="content_quality",
                title="Качество содержания",
                message=f"Есть краткие фрагменты ответа ({short_answers}), из-за чего общий контекст раскрыт не полностью.",
                severity="low",
                confidence=0.64,
            )
        )
    if concrete is not None and concrete < 0.3:
        notes.append(
            _make_attention_note(
                category="content_quality",
                title="Качество содержания",
                message="Мало конкретных примеров и фактических деталей.",
                severity="medium",
                confidence=0.7,
            )
        )
    if growth is not None and growth < 0.3:
        notes.append(
            _make_attention_note(
                category="content_quality",
                title="Качество содержания",
                message="Рефлексия о личном росте раскрыта ограниченно.",
                severity="low",
                confidence=0.66,
            )
        )

    deduped: list[dict[str, Any]] = []
    seen_messages: set[str] = set()
    for n in notes:
        msg = str(n.get("message", "")).strip().lower()
        if not msg or msg in seen_messages:
            continue
        seen_messages.add(msg)
        deduped.append(n)
    return deduped[:6]


def _build_path_attention(
    raw_pq: dict[str, Any] | list[Any],
    section_signals: dict[str, Any],
    *,
    growth_payload: dict[str, Any] | None = None,
    motivation_signals: dict[str, Any] | None = None,
    achievements_signals: dict[str, Any] | None = None,
) -> list[str]:
    notes = _build_path_attention_notes(
        raw_pq,
        section_signals,
        growth_payload=growth_payload,
        motivation_signals=motivation_signals,
        achievements_signals=achievements_signals,
    )
    return [str(n.get("message", "")).strip() for n in notes if str(n.get("message", "")).strip()]


def _sanitize_llm_summary(text: str) -> str:
    """Normalize LLM summary to short Russian, human-facing text."""
    return _shared_sanitize_reviewer_text(text)


def _build_path_fallback_summary(section_signals: dict[str, Any]) -> str:
    highs: list[str] = []
    growth_areas: list[str] = []
    for key, label in _PATH_SIGNAL_LABELS:
        value = section_signals.get(key)
        if value is None:
            continue
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        if v >= 0.7:
            highs.append(label.lower())
        elif v < 0.3:
            growth_areas.append(label.lower())

    base = "В ответах прослеживается последовательная траектория личного развития кандидата."
    if highs and growth_areas:
        return (
            f"{base} Наиболее заметны {', '.join(highs)}. "
            f"Зоной развития остаются {', '.join(growth_areas)}."
        )
    if highs:
        return f"{base} Наиболее заметны {', '.join(highs)}."
    if growth_areas:
        return f"{base} Зоной развития остаются {', '.join(growth_areas)}."
    return f"{base} Ключевые сигналы пока выражены умеренно и требуют дополнительного наблюдения."


def _build_path_summary_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    run = _get_analysis_run(db, application_id, "growth_journey")
    explanations = (run.explanations or {}) if run else {}
    section_signals = explanations.get("section_signals", {})
    llm_summary = explanations.get("llm_summary")
    raw_pq = explanations.get("per_question", {})

    # Block 1: Brief summary (human-facing, no technical residue)
    summary_items: list[str] = []
    if llm_summary:
        clean = _sanitize_llm_summary(str(llm_summary))
        if clean:
            summary_items.append(clean)
    if not summary_items:
        summary_items.append(_build_path_fallback_summary(section_signals))
    sections.append(_section_block("Краткий вывод", summary_items))

    # Block 2: Key signals (correct keys from pipeline)
    signal_items: list[str] = []
    for key, label in _PATH_SIGNAL_LABELS:
        line = _format_signal_level(label, section_signals.get(key))
        if line:
            signal_items.append(line)
    if not signal_items:
        signal_items.append("Сигналы ещё не определены")
    sections.append(_section_block("Ключевые сигналы", signal_items))

    # Block 3: What shaped the candidate (compact theses, no raw fragments)
    excerpts = _extract_key_excerpts(raw_pq, section_signals)
    sections.append(_section_block("Что сформировало кандидата", excerpts))

    # Block 4: Attention (structured + backward-compatible items)
    section_payloads = _get_section_payloads(db, application_id)
    growth_payload = section_payloads.get("growth_journey") if isinstance(section_payloads.get("growth_journey"), dict) else {}

    motivation_run = _get_analysis_run(db, application_id, "motivation_goals")
    motivation_signals = ((motivation_run.explanations or {}).get("signals", {})) if motivation_run else {}
    if not isinstance(motivation_signals, dict):
        motivation_signals = {}

    achievements_run = _get_analysis_run(db, application_id, "achievements_activities")
    achievements_signals = ((achievements_run.explanations or {}).get("signals", {})) if achievements_run else {}
    if not isinstance(achievements_signals, dict):
        achievements_signals = {}

    attention_notes = _build_path_attention_notes(
        raw_pq,
        section_signals,
        growth_payload=growth_payload,
        motivation_signals=motivation_signals,
        achievements_signals=achievements_signals,
    )
    sections.append(_attention_section("Требует внимания", attention_notes))

    return {
        "type": "summary",
        "title": "Путь роста",
        "sections": sections,
    }


_SECTION_LABELS_RU: dict[str, str] = {
    "personal": "личные данные",
    "test": "тест",
    "motivation": "мотивация",
    "path": "путь",
    "achievements": "достижения",
}


def _is_generic_summary_text(text: str) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return True
    technical_markers = (
        "автоматическ",
        "статус готовности",
        "зоны внимания:",
        "ограниченном режиме",
        "degraded",
        "unit outputs",
    )
    return any(marker in low for marker in technical_markers)


def _compute_recommended_scores_snapshot(db: Session, application_id: UUID) -> tuple[float, dict[str, float]]:
    from invision_api.commission.application.section_score_service import compute_recommended_scores

    section_avgs: dict[str, float] = {}
    all_values: list[int] = []
    for section in ("personal", "test", "motivation", "path", "achievements"):
        recommended = compute_recommended_scores(db, application_id, section)
        values = [int(v) for v in recommended.values() if type(v) is int]
        if not values:
            continue
        section_avgs[section] = sum(values) / len(values)
        all_values.extend(values)
    overall_avg = (sum(all_values) / len(all_values)) if all_values else 3.0
    return overall_avg, section_avgs


def _load_candidate_summary_source(db: Session, application_id: UUID) -> dict[str, Any]:
    unit_summary: str | None = None
    canonical_run = data_check_repository.resolve_preferred_run_for_application(db, application_id)
    if canonical_run:
        for row in data_check_repository.list_unit_results_for_run(db, canonical_run.id):
            if row.unit_type != DataCheckUnitType.candidate_ai_summary.value:
                continue
            payload = row.result_payload if isinstance(row.result_payload, dict) else {}
            raw = str(payload.get("summary") or "").strip()
            if raw:
                unit_summary = raw
            break

    latest_ai = db.scalars(
        select(AIReviewMetadata)
        .where(AIReviewMetadata.application_id == application_id)
        .order_by(AIReviewMetadata.created_at.desc())
    ).first()
    flags = latest_ai.flags if (latest_ai and isinstance(latest_ai.flags, dict)) else {}
    strengths = [str(x).strip() for x in (flags.get("strengths") or []) if str(x).strip()]
    weak_points = [str(x).strip() for x in (flags.get("weak_points") or []) if str(x).strip()]
    recommendation = str(flags.get("recommendation") or "").strip().lower() or None
    persisted_summary = str((latest_ai.summary_text if latest_ai else "") or "").strip() or None

    summary_text = unit_summary or persisted_summary
    return {
        "summaryText": summary_text,
        "strengths": strengths,
        "weakPoints": weak_points,
        "recommendation": recommendation,
    }


def _build_final_summary_block(
    db: Session,
    application_id: UUID,
) -> tuple[list[str], float]:
    source = _load_candidate_summary_source(db, application_id)
    avg_score, section_avgs = _compute_recommended_scores_snapshot(db, application_id)

    summary_text = str(source.get("summaryText") or "").strip()
    if _is_generic_summary_text(summary_text):
        summary_text = ""
    summary_line = (
        _build_compact_summary(summary_text, fallback="", max_sentences=3, max_sentence_len=240)
        if summary_text
        else ""
    )
    if not summary_line:
        if avg_score >= 4.0:
            summary_line = "Кандидат показывает сильный и достаточно целостный профиль по основным разделам анкеты."
        elif avg_score >= 3.5:
            summary_line = "Профиль кандидата в целом устойчивый, с рабочим уровнем по ключевым разделам."
        elif avg_score >= 3.0:
            summary_line = "Профиль кандидата смешанный: есть рабочая база, но часть разделов требует дополнительной проверки."
        else:
            summary_line = "Профиль кандидата пока выглядит слабым: в нескольких разделах не хватает доказательности и глубины."

    strengths = [str(x).strip() for x in (source.get("strengths") or []) if str(x).strip()]
    weak_points = [str(x).strip() for x in (source.get("weakPoints") or []) if str(x).strip()]
    strong_sections = [name for name, val in section_avgs.items() if val >= 4.0]
    weak_sections = [name for name, val in section_avgs.items() if val < 3.5]

    if strengths:
        strengths_line = f"Сильные стороны: {', '.join(strengths[:3])}."
    elif strong_sections:
        labels = [_SECTION_LABELS_RU.get(key, key) for key in strong_sections[:3]]
        strengths_line = f"Сильные стороны: более уверенные результаты в разделах «{'», «'.join(labels)}»."
    else:
        strengths_line = "Сильные стороны: базовый уровень по ключевым разделам сохранён."

    if weak_points:
        weak_line = f"Ограничения: {', '.join(weak_points[:3])}."
    elif weak_sections:
        labels = [_SECTION_LABELS_RU.get(key, key) for key in weak_sections[:3]]
        weak_line = f"Ограничения: требуют внимания разделы «{'», «'.join(labels)}»."
    else:
        weak_line = "Ограничения: критичных слабых зон по текущим данным не выявлено."

    rec = str(source.get("recommendation") or "")
    if rec == "recommend" or avg_score >= 4.0:
        profile_line = "Общий характер профиля: сильный, с хорошей готовностью к следующему этапу."
    elif rec == "caution" or avg_score < 3.5:
        profile_line = "Общий характер профиля: неоднородный, часть выводов нуждается в дополнительном подтверждении."
    else:
        profile_line = "Общий характер профиля: рабочий, с потенциалом при адресном уточнении отдельных зон."

    return [summary_line, strengths_line, weak_line, profile_line], avg_score


def _build_recommendation_block(avg_score: float) -> list[str]:
    display = f"{avg_score:.1f}"
    if avg_score < 3.5:
        return [
            f"Средний рекомендованный балл: {display}",
            "Рекомендуется: отправить в архив",
        ]
    return [
        f"Средний рекомендованный балл: {display}",
        "Рекомендуется: отправить на собеседование",
    ]


def _build_achievements_summary_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    run = _get_analysis_run(db, application_id, "achievements_activities")
    explanations = (run.explanations or {}) if run else {}
    signals = explanations.get("signals", {})
    summary_text = explanations.get("summary", "")

    # Block 1: Brief summary
    summary_items: list[str] = []
    if summary_text:
        summary_items.append(
            _build_compact_summary(
                str(summary_text),
                fallback="Сводка достижений ещё не готова",
            )
        )
    else:
        summary_items.append("Сводка достижений ещё не готова")
    sections.append(_section_block("Краткий вывод", summary_items))

    # Block 2: Key signals
    signal_items: list[str] = []
    impact = signals.get("impact_markers", 0)
    has_role = signals.get("has_role", False)
    has_year = signals.get("has_year", False)
    word_count = signals.get("word_count", 0)

    if impact > 0:
        signal_items.append(f"Маркеры значимости: {impact}")
    else:
        signal_items.append("Маркеры значимости не обнаружены")
    if has_role:
        signal_items.append("Личная роль описана")
    else:
        signal_items.append("Личная роль неясна")
    if word_count:
        signal_items.append(f"Объём текста: {word_count} слов")
    if not signal_items:
        signal_items.append("Данные недоступны")
    sections.append(_section_block("Ключевые сигналы", signal_items))

    # Block 3: Confirmability (links + materials)
    confirm_items: list[str] = []
    links_count = signals.get("links_count", 0)
    if links_count:
        confirm_items.append(f"Приложено ссылок: {links_count}")
    else:
        confirm_items.append("Ссылки не приложены")

    canonical_run = data_check_repository.resolve_preferred_run_for_application(db, application_id)
    if canonical_run:
        link_results = [
            r for r in data_check_repository.list_unit_results_for_run(db, canonical_run.id)
            if r.unit_type == DataCheckUnitType.link_validation.value
        ]
        if link_results:
            lr = link_results[0]
            lr_payload = lr.result_payload or {}
            checked_links = lr_payload.get("links", [])
            reachable = sum(1 for ln in checked_links if ln.get("isReachable"))
            total_links = len(checked_links)
            if total_links:
                confirm_items.append(f"Проверенных ссылок: {reachable}/{total_links} доступны")

    if has_year:
        confirm_items.append("Указаны даты/годы")
    if not confirm_items:
        confirm_items.append("Данные недоступны")
    sections.append(_section_block("Подтверждённость", confirm_items))

    # Block 4: Final candidate summary (cross-section)
    final_summary_items, avg_recommended = _build_final_summary_block(db, application_id)
    sections.append(_section_block("Итоговая сводка", final_summary_items))

    # Block 5: Recommendation (transparent rule by average recommended score)
    sections.append(_section_block("Рекомендация", _build_recommendation_block(avg_recommended)))

    # Block 6: Attention
    attention_items: list[str] = []
    flags = (run.flags or {}) if run else {}
    if flags.get("manual_review_required"):
        if word_count and word_count < 30:
            attention_items.append("Очень краткое описание достижений")
        if not has_role and impact == 0:
            attention_items.append("Личная роль и значимость не выражены")
    if links_count == 0:
        attention_items.append("Нет подтверждающих ссылок")
    if not attention_items:
        attention_items.append("Замечаний нет")
    sections.append(_section_block("Требует внимания", attention_items))

    return {
        "type": "summary",
        "title": "Достижения",
        "sections": sections,
    }


_TAB_TO_PRIMARY_UNIT: dict[str, DataCheckUnitType] = {
    "test": DataCheckUnitType.test_profile_processing,
    "motivation": DataCheckUnitType.motivation_processing,
    "path": DataCheckUnitType.growth_path_processing,
    "achievements": DataCheckUnitType.achievements_processing,
}


def _unit_processing_message(ur: DataCheckUnitResult | None) -> str:
    """Short Russian status for commission sidebar during initial_screening (no scoring copy)."""
    if ur is None:
        return "Данные обрабатываются"
    st = (ur.status or "").strip()
    if st == "completed":
        return "Данные обработаны"
    if st in ("pending", "running", "queued") or not st:
        return "Данные обрабатываются"
    if st == "manual_review_required" or ur.manual_review_required:
        return "Требуется ручная проверка"
    return "Не удалось обработать автоматически"


def _build_initial_screening_processing_panel(db: Session, application_id: UUID, tab: str) -> dict[str, Any]:
    """Sidebar for «Проверка данных»: processing status only (no LLM / commission summary)."""
    title = "Статус обработки"
    run = data_check_repository.resolve_preferred_run_for_application(db, application_id)
    if not run:
        return {
            "type": "processing",
            "title": title,
            "sections": [
                _section_block("Проверка данных", ["Ожидание запуска обработки."]),
            ],
        }

    unit_map: dict[str, DataCheckUnitResult] = {}
    for r in data_check_repository.list_unit_results_for_run(db, run.id):
        unit_map[r.unit_type] = r

    checks = data_check_repository.list_checks_for_run(db, run.id)
    status_map: dict[DataCheckUnitType, str] = {}
    for c in checks:
        try:
            status_map[DataCheckUnitType(c.check_type)] = c.status
        except ValueError:
            continue
    overall = compute_run_status(status_map).status if status_map else "pending"
    _overall_ru: dict[str, str] = {
        "pending": "ожидание обработки",
        "running": "идёт обработка",
        "ready": "все блоки успешно обработаны",
        "partial": "есть проблемы или требуется ручная проверка",
        "failed": "есть ошибки обработки",
    }
    overall_ru = _overall_ru.get(overall, "обработка: статус уточняется")

    sections: list[dict[str, Any]] = [
        _section_block("Общий статус", [f"Статус: {overall_ru}"]),
    ]

    if tab == "personal":
        lines = []
        for ut in UNIT_POLICIES:
            label = _data_check_unit_label_ru(ut.value)
            ur = unit_map.get(ut.value)
            lines.append(f"{label}: {_unit_processing_message(ur)}")
        sections.append(_section_block("Разделы заявки", lines))
    else:
        primary = _TAB_TO_PRIMARY_UNIT.get(tab)
        if primary:
            label = _data_check_unit_label_ru(primary.value)
            ur = unit_map.get(primary.value)
            sections.append(_section_block(label, [_unit_processing_message(ur)]))
        else:
            sections.append(_section_block("Раздел", ["Нет данных для этой вкладки."]))

    return {"type": "processing", "title": title, "sections": sections}


_TAB_BUILDERS: dict[str, Any] = {
    "test": _build_test_summary_panel,
    "motivation": _build_motivation_summary_panel,
    "path": _build_path_summary_panel,
    "achievements": _build_achievements_summary_panel,
}


def _build_ai_interview_resolution_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    """Sidebar summary from persisted AI interview resolution JSON (commission read model)."""
    row = ai_interview_repository.get_question_set_for_application(db, application_id)
    title = "AI-собеседование"
    if not row or not row.candidate_completed_at:
        return {
            "type": "summary",
            "title": title,
            "sections": [
                _section_block("Краткий итог", ["Кандидат ещё не завершил AI-собеседование."]),
            ],
        }

    if not isinstance(row.resolution_summary, dict):
        try:
            from invision_api.services.ai_interview.resolution_summary import (
                ensure_resolution_summary_available,
            )

            row = ensure_resolution_summary_available(db, application_id=application_id, row=row) or row
        except Exception:
            logger.exception("ai_interview_sidebar_summary_backfill_failed application_id=%s", application_id)

    err = (row.resolution_summary_error or "").strip()
    data = row.resolution_summary if isinstance(row.resolution_summary, dict) else None

    if err and not data:
        return {
            "type": "summary",
            "title": title,
            "sections": [
                _section_block(
                    "Краткий итог",
                    [
                        "Сводка по AI-собеседованию временно недоступна. Проверьте вопросы и ответы кандидата в основной области страницы.",
                    ],
                ),
            ],
        }

    if not data:
        return {
            "type": "summary",
            "title": title,
            "sections": [_section_block("Краткий итог", ["Сводка формируется. Обновите страницу через несколько секунд."])],
        }

    short = str(data.get("shortSummary") or "").strip()
    if not short:
        short = "Сводка пока недоступна."

    def _lines(key: str) -> list[str]:
        raw = data.get(key)
        if not isinstance(raw, list):
            return []
        out = [str(x).strip() for x in raw if str(x).strip()]
        return out if out else ["—"]

    conf = data.get("confidence")
    conf_label = ""
    if conf == "high":
        conf_label = "уверенность: высокая"
    elif conf == "medium":
        conf_label = "уверенность: средняя"
    elif conf == "low":
        conf_label = "уверенность: низкая"
    if conf_label:
        short = f"{short} ({conf_label})"

    sections = [
        _section_block("Краткий итог", [short]),
        _section_block("Что удалось уточнить", _lines("resolvedPoints")),
        _section_block("Что остаётся под вопросом", _lines("unresolvedPoints")),
        _section_block("Новая информация", _lines("newInformation")),
        _section_block(
            "На что обратить внимание на живом собеседовании",
            _lines("followUpFocus")
            if _lines("followUpFocus") != ["—"]
            else (
                [f"Уточнить: {line}" for line in _lines("unresolvedPoints") if line != "—"][:4]
                or ["—"]
            ),
        ),
    ]
    return {"type": "summary", "title": title, "sections": sections}


def _build_engagement_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    title = "Вовлеченность"
    insight = engagement_scoring_service.build_engagement_insight_for_application(db, application_id=application_id)
    if not insight:
        return {
            "type": "summary",
            "title": title,
            "sections": [
                _section_block("Сигналы", ["Данные по вовлечённости пока недоступны."]),
                _section_block("Интерпретация", ["Недостаточно данных для интерпретации вовлечённости."]),
                _section_block("Итог", ["Итоговый вывод пока недоступен."]),
            ],
        }

    signals = [str(line).strip() for line in (insight.get("signals") or []) if str(line).strip()][:9]
    interpretation = [
        str(line).strip() for line in (insight.get("interpretation") or []) if str(line).strip()
    ][:4]
    final_line = str(insight.get("final") or "").strip()

    if not signals:
        signals = ["Данные по вовлечённости пока недоступны."]
    if not interpretation:
        interpretation = ["Недостаточно данных для интерпретации вовлечённости."]
    if not final_line:
        final_line = "Итоговый вывод пока недоступен."

    return {
        "type": "summary",
        "title": title,
        "sections": [
            _section_block("Сигналы", signals),
            _section_block("Интерпретация", interpretation),
            _section_block("Итог", [final_line]),
        ],
    }


def get_sidebar_panel(db: Session, *, application_id: UUID, tab: str) -> dict[str, Any]:
    """Return sidebar panel content for the given tab.

    ``tab`` is one of: personal, test, motivation, path, achievements, ai_interview, engagement.
    """
    if tab == "engagement":
        return _build_engagement_panel(db, application_id)

    app = db.get(Application, application_id)
    on_initial_screening = bool(app and app.current_stage == ApplicationStage.initial_screening.value)

    # initial_screening must win over tab-specific builders (e.g. ai_interview), otherwise a client
    # that sends tab=ai_interview would receive LLM summary while the application is still on stage 1.
    if on_initial_screening:
        return _build_initial_screening_processing_panel(db, application_id, tab)

    if tab == "ai_interview":
        return _build_ai_interview_resolution_panel(db, application_id)

    panel_type = _TAB_TO_PANEL_TYPE.get(tab, "validation")

    if panel_type == "validation":
        return _build_validation_panel(db, application_id)

    builder = _TAB_BUILDERS.get(tab)
    if builder:
        return builder(db, application_id)

    return {
        "type": "summary",
        "title": tab.capitalize(),
        "sections": [_section_block("Информация", ["Данные для этой вкладки недоступны"])],
    }
