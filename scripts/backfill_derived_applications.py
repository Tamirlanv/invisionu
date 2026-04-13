#!/usr/bin/env python3
"""One-shot backfill/reprocessing for derived application data."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, date, datetime
from uuid import UUID

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api", "src"))

from invision_api.services.backfill.application_backfill_service import (
    BackfillOptions,
    reprocess_applications,
)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: {value}") from exc


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid UUID: {value}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One-shot backfill for derived application data")
    parser.add_argument("--mode", choices=["analysis_only", "full"], default="analysis_only")
    parser.add_argument("--dry-run", action="store_true", help="Plan actions without writing to DB")
    parser.add_argument("--application-id", dest="application_ids", action="append", type=_parse_uuid, default=[])
    parser.add_argument("--stage", dest="stages", action="append", default=[])
    parser.add_argument("--submitted-from", type=_parse_date)
    parser.add_argument("--submitted-to", type=_parse_date)
    parser.add_argument(
        "--only-missing",
        default="",
        help=(
            "CSV: review_snapshot,commission_ai_summary,ai_interview_draft,"
            "ai_interview_resolution,video_summary,certificate_result"
        ),
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--include-archived", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--auto-advance-ready",
        action="store_true",
        help="After full recompute, auto-move ready applications from initial_screening to application_review.",
    )
    parser.add_argument("--backfill-version")
    return parser


def _default_backfill_version(mode: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    if mode == "full":
        return None
    ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"analysis-only-{ts}"


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    backfill_version = _default_backfill_version(args.mode, args.backfill_version)
    if args.mode == "full" and not backfill_version:
        parser.error("--backfill-version is required when --mode full")

    only_missing = tuple(x.strip() for x in args.only_missing.split(",") if x.strip())

    options = BackfillOptions(
        mode=args.mode,
        dry_run=bool(args.dry_run),
        application_ids=tuple(args.application_ids),
        stages=tuple(args.stages),
        submitted_from=args.submitted_from,
        submitted_to=args.submitted_to,
        only_missing=only_missing,
        include_archived=bool(args.include_archived),
        force=bool(args.force),
        backfill_version=backfill_version,
        auto_advance_ready=bool(args.auto_advance_ready),
        limit=args.limit,
        offset=args.offset,
        batch_size=args.batch_size,
    )

    report = reprocess_applications(options)

    print("Backfill completed")
    print(f"mode={report.mode} dry_run={report.dry_run} total_targets={report.total_targets}")
    print(
        f"processed={report.processed} skipped={report.skipped} "
        f"dry_run={report.dry_run_count} failed={report.failed}"
    )
    for r in report.results:
        details = []
        if r.reason:
            details.append(f"reason={r.reason}")
        if r.error:
            details.append(f"error={r.error}")
        if r.actions:
            details.append(f"actions={','.join(r.actions)}")
        suffix = f" ({'; '.join(details)})" if details else ""
        print(f"- {r.application_id} [{r.status}]{suffix}")

    return 1 if report.failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
