#!/usr/bin/env python3
"""
Redis list consumer scaffold for future async AI / notification jobs.

BRPOP from a queue and print payloads. Extend with real handlers.

Usage:
  PYTHONPATH=apps/api/src REDIS_URL=redis://localhost:6379/0 python scripts/job_worker.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api", "src"))

from invision_api.core.redis_client import get_redis_client

QUEUE = "invision:jobs:default"


def main() -> None:
    r = get_redis_client()
    print(f"Listening on {QUEUE} …", flush=True)
    while True:
        item = r.brpop(QUEUE, timeout=0)
        if not item:
            continue
        _, raw = item
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            print("bad json", raw)
            continue
        print("job", payload, flush=True)


if __name__ == "__main__":
    main()
