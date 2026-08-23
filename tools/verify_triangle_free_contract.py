#!/usr/bin/env python3
"""Command-line gate for AdaptiveCAD curve manufacturing jobs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adaptivecad.manufacturing.contract import (
    load_job,
    save_report,
    verification_suite,
)


DEFAULT_SCALES = (0.001, 0.01, 1.0, 100.0, 1000.0)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reject triangle/facet geometry, validate analytic curve continuity, "
            "and prove scale-invariant topology for manufacturing IR jobs."
        )
    )
    parser.add_argument("jobs", nargs="+", type=Path, help="curve job JSON files")
    parser.add_argument(
        "--scales",
        nargs="+",
        type=float,
        default=DEFAULT_SCALES,
        help="positive geometric scale factors",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("triangle_free_contract_report.json"),
        help="verification report path",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    named_jobs = [(path.name, load_job(path)) for path in args.jobs]
    report = verification_suite(named_jobs, factors=args.scales)
    save_report(report, args.output)
    summary = {
        "passed": report["passed"],
        "contract_version": report["contract_version"],
        "report": str(args.output),
        "jobs": [
            {
                "name": audit["name"],
                "process": audit["process"],
                "passed": audit["passed"],
                "layers": audit["statistics"]["layer_count"],
                "paths": audit["statistics"]["path_count"],
                "segments": audit["statistics"]["segment_count"],
            }
            for audit in report["job_audits"]
        ],
        "scale_factors": report["scale_factors"],
        "shared_source_passed": report["shared_source"]["passed"],
    }
    print(json.dumps(summary, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
