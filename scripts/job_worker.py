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
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api", "src"))

from invision_api.core.redis_client import get_redis_client
from invision_api.db.session import SessionLocal
from invision_api.services.data_check.orchestrator_service import sweep_stuck_runs
from invision_api.services.job_dispatcher_service import QUEUE_NAME
from invision_api.workers.job_worker import process_payload

HEARTBEAT_KEY = "invision:worker:heartbeat"
HEARTBEAT_TTL = 90  # seconds — submit pipeline readiness check expects this key alive

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_last_heartbeat: float = 0.0


def _write_heartbeat(r) -> None:
    global _last_heartbeat
    now = time.monotonic()
    if now - _last_heartbeat >= 30:
        try:
            r.setex(HEARTBEAT_KEY, HEARTBEAT_TTL, "1")
            _last_heartbeat = now
        except Exception:
            logger.warning("heartbeat_write_failed", exc_info=True)


def _run_sweep() -> None:
    """Run the stuck-run recovery sweep during idle windows."""
    try:
        db = SessionLocal()
        try:
            recovered = sweep_stuck_runs(db)
            if recovered:
                db.commit()
                logger.info("sweep_done recovered=%d", recovered)
        except Exception:
            db.rollback()
            logger.exception("sweep_error")
        finally:
            db.close()
    except Exception:
        logger.exception("sweep_session_error")


def main() -> None:
    r = get_redis_client()
    logger.info("Worker starting — listening on queue '%s'", QUEUE_NAME)

    # Write initial heartbeat so the submit endpoint knows we're alive
    _write_heartbeat(r)

    while True:
        _write_heartbeat(r)

        try:
            item = r.brpop(QUEUE_NAME, timeout=30)
        except Exception:
            logger.exception("brpop_error — will retry in 5s")
            time.sleep(5)
            continue

        if not item:
            _run_sweep()
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
            logger.info("job_done job_type=%s application_id=%s", job_type, app_id)
        except Exception:
            logger.exception(
                "job_failed job_type=%s application_id=%s", job_type, app_id
            )
            # Continue processing next jobs — do not crash the worker


if __name__ == "__main__":
    main()
