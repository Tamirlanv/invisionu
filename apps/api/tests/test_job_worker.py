"""Regression tests for the Redis job worker payload handler."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from invision_api.models.enums import DataCheckUnitType, JobStatus, JobType
from invision_api.services import text_extraction_service
from invision_api.workers import job_worker


def test_process_payload_data_check_unit_resolves_admissions_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inner import in another branch must not shadow module-level admissions_repository (UnboundLocalError)."""
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()

    monkeypatch.setattr(job_worker, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(
        job_worker.admissions_repository,
        "get_application_by_id",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(job_worker.job_runner_service, "run_unit", lambda *_a, **_k: None)

    payload = {
        "job_type": JobType.data_check_unit.value,
        "application_id": str(uuid4()),
        "analysis_job_id": str(uuid4()),
        "run_id": str(uuid4()),
        "unit_type": DataCheckUnitType.test_profile_processing.value,
    }

    job_worker.process_payload(payload)

    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_process_payload_run_block_analysis_marks_analysis_job_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()

    job_id = uuid4()
    app_id = uuid4()
    job_row = MagicMock()
    updated = {"n": 0}

    def _get_analysis_job(_db, jid):
        assert jid == job_id
        return job_row

    def _update_analysis_job(_db, job, *, status=None, attempts=None, last_error=None):
        updated["n"] += 1
        assert status == JobStatus.completed.value

    monkeypatch.setattr(job_worker, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(job_worker.admissions_repository, "get_analysis_job", _get_analysis_job)
    monkeypatch.setattr(job_worker.admissions_repository, "update_analysis_job", _update_analysis_job)

    payload = {
        "job_type": JobType.run_block_analysis.value,
        "application_id": str(app_id),
        "analysis_job_id": str(job_id),
        "block_key": "motivation_goals",
    }

    job_worker.process_payload(payload)

    assert updated["n"] == 1
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_process_payload_extract_text_marks_failed_for_stale_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()

    job_id = uuid4()
    app_id = uuid4()
    doc_id = uuid4()

    analysis_job = MagicMock()
    analysis_job.status = JobStatus.queued.value
    analysis_job.attempts = 0

    updates: list[dict[str, object]] = []

    def _get_analysis_job(_db, _jid):
        return analysis_job

    def _update_analysis_job(_db, _job, *, status=None, attempts=None, last_error=None):
        updates.append({"status": status, "attempts": attempts, "last_error": last_error})

    monkeypatch.setattr(job_worker, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(job_worker.admissions_repository, "get_analysis_job", _get_analysis_job)
    monkeypatch.setattr(job_worker.admissions_repository, "update_analysis_job", _update_analysis_job)
    monkeypatch.setattr(job_worker.admissions_repository, "get_application_by_id", lambda *_a, **_k: object())
    monkeypatch.setattr(
        job_worker.text_extraction_service,
        "extract_and_persist_for_document",
        lambda *_a, **_k: (_ for _ in ()).throw(text_extraction_service.DocumentNotFoundError("document not found")),
    )

    payload = {
        "job_type": JobType.extract_text.value,
        "application_id": str(app_id),
        "analysis_job_id": str(job_id),
        "document_id": str(doc_id),
    }

    job_worker.process_payload(payload)

    assert any((u.get("status") == JobStatus.failed.value and str(u.get("last_error", "")).startswith("stale_document_not_found:")) for u in updates)
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_process_payload_extract_text_skips_terminal_analysis_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()

    job_id = uuid4()
    app_id = uuid4()
    doc_id = uuid4()

    analysis_job = MagicMock()
    analysis_job.status = JobStatus.completed.value
    analysis_job.attempts = 1

    monkeypatch.setattr(job_worker, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(job_worker.admissions_repository, "get_analysis_job", lambda *_a, **_k: analysis_job)
    monkeypatch.setattr(
        job_worker.text_extraction_service,
        "extract_and_persist_for_document",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not run for terminal analysis job")),
    )

    payload = {
        "job_type": JobType.extract_text.value,
        "application_id": str(app_id),
        "analysis_job_id": str(job_id),
        "document_id": str(doc_id),
    }

    job_worker.process_payload(payload)
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()


def test_process_payload_extract_text_marks_failed_for_stale_application_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()

    job_id = uuid4()
    app_id = uuid4()
    doc_id = uuid4()

    analysis_job = MagicMock()
    analysis_job.status = JobStatus.queued.value
    analysis_job.attempts = 0

    updates: list[dict[str, object]] = []

    monkeypatch.setattr(job_worker, "SessionLocal", lambda: mock_db)
    monkeypatch.setattr(job_worker.admissions_repository, "get_analysis_job", lambda *_a, **_k: analysis_job)
    monkeypatch.setattr(
        job_worker.admissions_repository,
        "update_analysis_job",
        lambda _db, _job, *, status=None, attempts=None, last_error=None: updates.append(
            {"status": status, "attempts": attempts, "last_error": last_error}
        ),
    )
    monkeypatch.setattr(job_worker.admissions_repository, "get_application_by_id", lambda *_a, **_k: None)
    monkeypatch.setattr(
        job_worker.text_extraction_service,
        "extract_and_persist_for_document",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not run when application context is stale")),
    )

    payload = {
        "job_type": JobType.extract_text.value,
        "application_id": str(app_id),
        "analysis_job_id": str(job_id),
        "document_id": str(doc_id),
    }

    job_worker.process_payload(payload)

    assert any((u.get("status") == JobStatus.failed.value and str(u.get("last_error", "")).startswith("stale_application_context:")) for u in updates)
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()
