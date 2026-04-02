"""Sidebar panel content builder for the commission candidate detail page.

Two panel types:
- 'validation' for the Personal Info tab (deterministic checks only, no LLM)
- 'summary' for Test / Motivation / Path / Achievements tabs
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import TextAnalysisRun
from invision_api.models.candidate_signals_aggregate import CandidateSignalsAggregate
from invision_api.models.data_check_unit_result import DataCheckUnitResult
from invision_api.repositories import data_check_repository
from invision_api.services.data_check.status_service import TERMINAL_UNIT_STATUSES, compute_run_status
from invision_api.models.enums import DataCheckUnitType


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


def _section_block(title: str, items: list[str]) -> dict[str, Any]:
    return {"title": title, "items": items}


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


def _build_validation_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    """Build sidebar for Personal Info tab — deterministic checks only."""
    runs = data_check_repository.list_runs_for_application(db, application_id)
    unit_map: dict[str, DataCheckUnitResult] = {}
    if runs:
        results = data_check_repository.list_unit_results_for_run(db, runs[0].id)
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

    # Block 4: Attention flags
    warnings: list[str] = []
    for r in unit_map.values():
        if r.warnings:
            warnings.extend(r.warnings)
        if r.manual_review_required and r.status != "completed":
            warnings.append(f"{r.unit_type}: требуется ручная проверка")
    seen: set[str] = set()
    deduped: list[str] = []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            deduped.append(w)
    if deduped:
        sections.append(_section_block("Требует внимания", deduped[:8]))

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
        profile_items.append(str(profile_summary)[:300])
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


def _build_motivation_summary_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    run = _get_analysis_run(db, application_id, "motivation_goals")
    explanations = (run.explanations or {}) if run else {}
    signals = explanations.get("signals", {})
    summary_text = explanations.get("summary", "")

    # Block 1: Brief summary
    summary_items: list[str] = []
    if summary_text:
        summary_items.append(str(summary_text)[:400])
    else:
        summary_items.append("Сводка мотивации ещё не готова")
    sections.append(_section_block("Краткий вывод", summary_items))

    # Block 2: Key signals
    signal_items: list[str] = []
    mot_density = signals.get("motivation_density")
    evidence = signals.get("evidence_density")
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

    # Block 3: Attention
    attention_items: list[str] = []
    flags = (run.flags or {}) if run else {}
    if flags.get("manual_review_required"):
        if word_count and word_count < 70:
            attention_items.append("Очень короткий текст мотивации")
    if mot_density is not None and mot_density < 0.05:
        attention_items.append("Слабая связь с программой")
    if evidence is not None and evidence < 0.03:
        attention_items.append("Отсутствуют конкретные примеры")
    if not attention_items:
        attention_items.append("Замечаний нет")
    sections.append(_section_block("Требует внимания", attention_items))

    # Block 4: Confidence
    conf_items: list[str] = []
    if run and run.status == "completed":
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


def _build_path_summary_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    run = _get_analysis_run(db, application_id, "growth_journey")
    explanations = (run.explanations or {}) if run else {}
    flags = (run.flags or {}) if run else {}
    section_signals = explanations.get("section_signals", {})
    llm_summary = explanations.get("llm_summary")
    raw_pq = explanations.get("per_question", {})
    per_question: list[dict[str, Any]] = list(raw_pq.values()) if isinstance(raw_pq, dict) else (raw_pq if isinstance(raw_pq, list) else [])

    # Block 1: Brief summary
    summary_items: list[str] = []
    if llm_summary:
        summary_items.append(str(llm_summary)[:400])
    else:
        summary_items.append("Сводка пути роста ещё не готова")
    sections.append(_section_block("Краткий вывод", summary_items))

    # Block 2: Key signals
    signal_items: list[str] = []
    growth_score = section_signals.get("growth_score")
    initiative_score = section_signals.get("initiative_score")
    resilience_score = section_signals.get("resilience_score")
    responsibility_score = section_signals.get("responsibility_score")

    def _signal_line(name: str, val: Any) -> str | None:
        if val is None:
            return None
        v = float(val)
        if v >= 0.7:
            return f"{name}: выраженный"
        if v >= 0.3:
            return f"{name}: средний"
        return f"{name}: низкий"

    for name, val in [
        ("Инициатива", initiative_score),
        ("Устойчивость", resilience_score),
        ("Ответственность", responsibility_score),
        ("Рост / рефлексия", growth_score),
    ]:
        line = _signal_line(name, val)
        if line:
            signal_items.append(line)
    if not signal_items:
        signal_items.append("Данные недоступны")
    sections.append(_section_block("Ключевые сигналы", signal_items))

    # Block 3: What shaped the candidate
    shaping_items: list[str] = []
    for pq in per_question[:5]:
        q_key = pq.get("question_key", "")
        snippet = pq.get("snippet", "") or pq.get("summary", "")
        if snippet:
            shaping_items.append(str(snippet)[:150])
    if not shaping_items:
        shaping_items.append("Детали недоступны")
    sections.append(_section_block("Что сформировало кандидата", shaping_items))

    # Block 4: Attention
    attention_items: list[str] = []
    spam_questions = flags.get("spam_questions", [])
    if spam_questions:
        attention_items.append(f"Обнаружены признаки спама в вопросах: {', '.join(spam_questions[:3])}")
    if flags.get("manual_review_required"):
        attention_items.append("Требуется ручная проверка")
    word_counts = [pq.get("word_count", 0) for pq in per_question]
    short_answers = sum(1 for wc in word_counts if wc and wc < 20)
    if short_answers > 0:
        attention_items.append(f"Коротких ответов: {short_answers}")
    if not attention_items:
        attention_items.append("Замечаний нет")
    sections.append(_section_block("Требует внимания", attention_items))

    return {
        "type": "summary",
        "title": "Путь роста",
        "sections": sections,
    }


def _build_achievements_summary_panel(db: Session, application_id: UUID) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    run = _get_analysis_run(db, application_id, "achievements_activities")
    explanations = (run.explanations or {}) if run else {}
    signals = explanations.get("signals", {})
    summary_text = explanations.get("summary", "")
    links = explanations.get("links", [])

    # Block 1: Brief summary
    summary_items: list[str] = []
    if summary_text:
        summary_items.append(str(summary_text)[:400])
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

    runs_list = data_check_repository.list_runs_for_application(db, application_id)
    if runs_list:
        link_results = [
            r for r in data_check_repository.list_unit_results_for_run(db, runs_list[0].id)
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

    # Block 4: Attention
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


_TAB_BUILDERS: dict[str, Any] = {
    "test": _build_test_summary_panel,
    "motivation": _build_motivation_summary_panel,
    "path": _build_path_summary_panel,
    "achievements": _build_achievements_summary_panel,
}


def get_sidebar_panel(db: Session, *, application_id: UUID, tab: str) -> dict[str, Any]:
    """Return sidebar panel content for the given tab.

    ``tab`` is one of: personal, test, motivation, path, achievements.
    """
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
