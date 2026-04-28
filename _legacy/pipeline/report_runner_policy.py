#!/usr/bin/env python3
"""Resolve GitHub Actions runner policy for long-running report jobs."""

from __future__ import annotations

import argparse
import json

DEFAULT_RUNNER_LABELS = ["ubuntu-latest"]
LONG_RUNNER_LABELS = ["self-hosted", "linux", "x64", "bce-long-report"]
DEFAULT_TIMEOUT_MINUTES = 240
LONG_TIMEOUT_MINUTES = 720
LONG_REPORT_TYPES = {"econ", "mat", "all"}


def parse_bool(raw: str | bool | None) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}


def compute_policy(
    *,
    event_name: str,
    report_type: str = "",
    slug: str = "",
    force: str | bool = False,
) -> dict[str, object]:
    normalized_event = (event_name or "").strip()
    normalized_report_type = "all" if normalized_event == "schedule" else (report_type or "for").strip().lower()
    normalized_slug = (slug or "").strip()
    normalized_force = parse_bool(force)

    long_runner_required = False
    route_reason = "scheduled/default-manual path stays on GitHub-hosted runner"

    if normalized_event == "workflow_dispatch" and normalized_force:
        long_runner_required = True
        route_reason = "force rerun uses self-hosted long runner"
    elif (
        normalized_event == "workflow_dispatch"
        and not normalized_slug
        and normalized_report_type in LONG_REPORT_TYPES
    ):
        long_runner_required = True
        route_reason = f"manual {normalized_report_type} full run uses self-hosted long runner"

    return {
        "report_type": normalized_report_type,
        "long_runner_required": str(long_runner_required).lower(),
        "runner_labels": LONG_RUNNER_LABELS if long_runner_required else DEFAULT_RUNNER_LABELS,
        "timeout_minutes": LONG_TIMEOUT_MINUTES if long_runner_required else DEFAULT_TIMEOUT_MINUTES,
        "runner_class": "self-hosted-long" if long_runner_required else "github-hosted-default",
        "route_reason": route_reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--report-type", default="")
    parser.add_argument("--slug", default="")
    parser.add_argument("--force", default="false")
    args = parser.parse_args()

    policy = compute_policy(
        event_name=args.event_name,
        report_type=args.report_type,
        slug=args.slug,
        force=args.force,
    )
    print(json.dumps(policy, separators=(",", ":")))


if __name__ == "__main__":
    main()
