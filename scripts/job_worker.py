#!/usr/bin/env python3
"""
Redis BRPOP job worker for the admission pipeline.

Listens on the real job queue (invision:admission_jobs) and dispatches
each payload to the application-layer handler (process_payload).

Usage:
  make worker
  # or directly:
  PYTHONPATH=apps/api/src python scripts/job_worker.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api", "src"))

from invision_api.core.config import get_settings
from invision_api.core.redis_client import get_redis_client
from invision_api.db.session import SessionLocal
from invision_api.services.data_check.orchestrator_service import sweep_stuck_runs
from invision_api.services.commission_interview_reminder_service import sweep_commission_interview_reminders
from invision_api.services.interview_preference_window.service import sweep_expired_preference_windows
from invision_api.services.job_dispatcher_service import QUEUE_NAME
from invision_api.services.video_processing.ffmpeg_tools import resolve_media_runtime_binaries
from invision_api.workers.job_worker import process_payload

HEARTBEAT_KEY = "invision:worker:heartbeat"


def _env_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(min_value, int(raw))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


HEARTBEAT_TTL = _env_int("WORKER_HEARTBEAT_TTL_SECONDS", 180)
HEARTBEAT_INTERVAL_SECONDS = _env_int("WORKER_HEARTBEAT_INTERVAL_SECONDS", 20)
DATA_CHECK_SWEEP_INTERVAL_SECONDS = _env_int("DATA_CHECK_SWEEP_INTERVAL_SECONDS", 30)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

def _write_heartbeat(r) -> None:
    try:
        r.setex(HEARTBEAT_KEY, HEARTBEAT_TTL, "1")
    except Exception:
        logger.warning("heartbeat_write_failed", exc_info=True)


def _heartbeat_loop(r, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        _write_heartbeat(r)
        stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)


def _run_sweep() -> None:
    """Run periodic stuck-run recovery sweep."""
    try:
        db = SessionLocal()
        try:
            recovered = sweep_stuck_runs(db)
            db.commit()
            logger.info("sweep_done recovered=%d", recovered)
        except Exception:
            db.rollback()
            logger.exception("sweep_error")
        finally:
            db.close()
    except Exception:
        logger.exception("sweep_session_error")


def _data_check_sweep_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        _run_sweep()
        stop_event.wait(DATA_CHECK_SWEEP_INTERVAL_SECONDS)


def _run_interview_preference_window_sweep() -> None:
    try:
        db = SessionLocal()
        try:
            n = sweep_expired_preference_windows(db)
            if n:
                db.commit()
                logger.info("interview_preference_window_sweep n=%d", n)
        except Exception:
            db.rollback()
            logger.exception("interview_preference_window_sweep_error")
        finally:
            db.close()
    except Exception:
        logger.exception("interview_preference_window_sweep_session_error")


def _run_commission_interview_reminder_sweep() -> None:
    try:
        db = SessionLocal()
        try:
            n = sweep_commission_interview_reminders(db)
            if n:
                logger.info("commission_interview_reminder_sweep n=%d", n)
        except Exception:
            db.rollback()
            logger.exception("commission_interview_reminder_sweep_error")
        finally:
            db.close()
    except Exception:
        logger.exception("commission_interview_reminder_sweep_session_error")


def main() -> None:
    r = get_redis_client()
    stop_event = threading.Event()
    settings = get_settings()
    require_media_bins = _env_bool(
        "WORKER_REQUIRE_MEDIA_BINARIES",
        default=settings.environment in {"staging", "production"},
    )
    try:
        upload_root = settings.upload_root
        logger.info("Worker resolved UPLOAD_ROOT=%s (must match API for file-based units)", upload_root)
        logger.info(
            "Worker storage read mode=%s proxy_base=%s",
            settings.storage_read_mode,
            settings.storage_proxy_base_url or "-",
        )
        asr_base = getattr(settings, "asr_base_url", None)
        asr_model = getattr(settings, "asr_model", None)
        asr_key_set = bool(getattr(settings, "asr_api_key", None) or getattr(settings, "openai_api_key", None))
        logger.info(
            "Worker ASR config base=%s model=%s key_set=%s",
            asr_base or "-",
            asr_model or "-",
            asr_key_set,
        )
    except Exception:
        logger.warning("Worker could not log UPLOAD_ROOT", exc_info=True)
    try:
        media_bins = resolve_media_runtime_binaries(include_ytdlp=True)
        missing = [name for name, path in media_bins.items() if not path]
        if missing:
            msg = f"Worker media runtime missing dependencies: {', '.join(missing)}"
            if require_media_bins:
                logger.error("%s", msg)
                logger.error(
                    "Fail-fast: set WORKER_REQUIRE_MEDIA_BINARIES=0 only for local debugging."
                )
                raise RuntimeError(msg)
            logger.warning("%s", msg)
        else:
            logger.info("Worker media runtime dependencies ready: %s", ", ".join(sorted(media_bins.keys())))
    except Exception:
        logger.warning("Worker could not evaluate media runtime dependencies", exc_info=True)
        if require_media_bins:
            raise
    logger.info("Worker starting — listening on queue '%s'", QUEUE_NAME)

    # Write initial heartbeat so the submit endpoint knows we're alive
    _write_heartbeat(r)
    threading.Thread(
        target=_heartbeat_loop,
        args=(r, stop_event),
        daemon=True,
        name="worker-heartbeat",
    ).start()
    threading.Thread(
        target=_data_check_sweep_loop,
        args=(stop_event,),
        daemon=True,
        name="data-check-sweep",
    ).start()

    while True:
        try:
            item = r.brpop(QUEUE_NAME, timeout=10)
        except Exception:
            logger.exception("brpop_error — will retry in 5s")
            time.sleep(5)
            continue

        if not item:
            _run_interview_preference_window_sweep()
            _run_commission_interview_reminder_sweep()
            continue

        _, raw = item
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("invalid_json raw=%s", raw[:300])
            continue

        job_type = payload.get("job_type", "unknown")
        app_id = payload.get("application_id", "?")

        try:
            process_payload(payload)
            if job_type == "data_check_unit":
                logger.info(
                    "job_done job_type=%s application_id=%s unit_type=%s",
                    job_type,
                    app_id,
                    payload.get("unit_type", "?"),
                )
            else:
                logger.info("job_done job_type=%s application_id=%s", job_type, app_id)
        except Exception:
            logger.exception(
                "job_failed job_type=%s application_id=%s", job_type, app_id
            )
            # Continue processing next jobs — do not crash the worker


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Worker stopped (KeyboardInterrupt)")
        sys.exit(0)
