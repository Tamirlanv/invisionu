#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

check_port() {
  local port="$1"
  if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is not listening. Start services with: make backend" >&2
    exit 1
  fi
}

echo "== Checking service ports =="
check_port 8000
check_port 4300
check_port 4400
check_port 4500
echo "Ports OK."

echo "== Resolving application id =="
APP_ID="$(
python3 - <<'PY'
import os
from pathlib import Path
import psycopg

env = Path(".env")
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

url = os.environ.get("DATABASE_URL", "")
url = url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")
if not url:
    print("")
    raise SystemExit(0)

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("select id::text from applications limit 1")
        row = cur.fetchone()
        print(row[0] if row else "")
PY
)"
if [[ -z "$APP_ID" ]]; then
  echo "No application row found in DB; cannot run full smoke." >&2
  exit 1
fi
echo "Using application_id=$APP_ID"

echo "== Smoke: link validation auth guard =="
LINK_CODE="$(curl -s -o /tmp/smoke_link_guard.json -w "%{http_code}" -X POST "http://127.0.0.1:8000/api/v1/links/validate" -H "Content-Type: application/json" -d '{"url":"https://example.com"}')"
if [[ "$LINK_CODE" != "401" ]]; then
  echo "Expected 401 for unauthenticated link endpoint, got $LINK_CODE" >&2
  exit 1
fi
echo "Link endpoint auth guard OK (401 as expected)."

echo "== Smoke: video validation =="
VIDEO_CODE="$(curl -s -o /tmp/smoke_video_service.json -w "%{http_code}" -X POST "http://127.0.0.1:4300/video-validation/validate" -H "Content-Type: application/json" -d '{"videoUrl":"https://example.com/video.mp4","applicationId":"'"$APP_ID"'"}')"
if [[ "$VIDEO_CODE" != "200" ]]; then
  echo "Video validation failed with code $VIDEO_CODE" >&2
  cat /tmp/smoke_video_service.json >&2 || true
  exit 1
fi
echo "Video endpoint OK."

echo "== Smoke: certificate validation =="
CERT_CODE="$(curl -s -o /tmp/smoke_cert_service.json -w "%{http_code}" -X POST "http://127.0.0.1:4400/certificate-validation/validate" -H "Content-Type: application/json" -d '{"imagePath":"/tmp/nonexistent-certificate.png","applicationId":"'"$APP_ID"'"}')"
if [[ "$CERT_CODE" != "200" ]]; then
  echo "Certificate validation failed with code $CERT_CODE" >&2
  cat /tmp/smoke_cert_service.json >&2 || true
  exit 1
fi
echo "Certificate endpoint OK."

echo "== Smoke: orchestrator submit/report =="
ORCH_CODE="$(curl -s -o /tmp/smoke_orch_submit.json -w "%{http_code}" -X POST "http://127.0.0.1:4500/candidate-validation/runs" -H "Content-Type: application/json" -d '{"candidateId":"00000000-0000-0000-0000-000000000001","applicationId":"'"$APP_ID"'","checks":{"videoPresentation":{"videoUrl":"https://example.com/video.mp4"},"certificates":{"imagePath":"/tmp/nonexistent-certificate.png"}}}')"
if [[ "$ORCH_CODE" != "200" ]]; then
  echo "Orchestrator submit failed with code $ORCH_CODE" >&2
  cat /tmp/smoke_orch_submit.json >&2 || true
  exit 1
fi
RUN_ID="$(python3 - <<'PY'
import json
from pathlib import Path
d = json.loads(Path("/tmp/smoke_orch_submit.json").read_text())
print(d.get("runId",""))
PY
)"
if [[ -z "$RUN_ID" ]]; then
  echo "No runId returned by orchestrator" >&2
  exit 1
fi

REPORT_CODE="$(curl -s -o /tmp/smoke_orch_report.json -w "%{http_code}" "http://127.0.0.1:4500/candidate-validation/runs/$RUN_ID")"
if [[ "$REPORT_CODE" != "200" ]]; then
  echo "Orchestrator report failed with code $REPORT_CODE" >&2
  cat /tmp/smoke_orch_report.json >&2 || true
  exit 1
fi

echo "Orchestrator endpoints OK."
echo "Smoke services OK."
