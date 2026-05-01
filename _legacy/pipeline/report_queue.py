"""
Phase E: Report Queue Management

Manages the daily report generation queue, deciding which projects should get
reports generated and in what order based on triage results and priority rules.
"""

import os
import sys
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import MAX_DAILY_REPORTS
except ImportError:
    # Fallback default if config not available
    MAX_DAILY_REPORTS = 10


@dataclass
class TriageResult:
    """Triage result for a project (from triage.py)"""
    slug: str
    bce_grade: str
    report_decision: str
    forensic_flags: List[str]
    total_score: float
    previous_grade: Optional[str] = None
    last_report_date: Optional[datetime] = None
    refresh_cycle_days: int = 90


class ReportQueue:
    """Manages prioritized report generation queue."""

    # Priority level definitions
    PRIORITY_P0 = 0  # New listings with decisions
    PRIORITY_P1 = 1  # Grade changes
    PRIORITY_P2 = 2  # Forensic alerts
    PRIORITY_P3 = 3  # Stale reports
    PRIORITY_P4 = 4  # Never-reported projects

    def __init__(self):
        """Initialize the report queue manager."""
        pass

    @staticmethod
    def report_types_for_decision(decision: str) -> List[str]:
        """
        Map triage decision to report types to generate.

        Args:
            decision: Triage decision (FULL, STANDARD, MINIMAL, SCAN_ONLY, UNRATABLE)

        Returns:
            List of report type codes: 'econ', 'mat', 'for'
        """
        decision_map = {
            'FULL': ['econ', 'mat', 'for'],       # A/B등급 고투명: 3종 리포트
            'STANDARD': ['econ', 'mat', 'for'],    # C등급+: 3종 리포트
            'MINIMAL': ['econ', 'mat'],             # D등급: ECON + MAT
            'SCAN_ONLY': [],
            'UNRATABLE': [],
        }
        return decision_map.get(decision, [])

    @staticmethod
    def _get_priority_and_reason(
        triage: TriageResult,
        existing_reports: Optional[Dict[str, Dict]] = None,
        new_listing: bool = False
    ) -> tuple:
        """
        Determine priority level and reason for a triage result.

        Args:
            triage: TriageResult object
            existing_reports: Dict mapping slug to report metadata
            new_listing: Whether this is a new listing

        Returns:
            Tuple of (priority_int, reason_str)
        """
        existing_reports = existing_reports or {}

        # P0: New listings with FULL/STANDARD/MINIMAL decision
        if new_listing and triage.report_decision in ['FULL', 'STANDARD', 'MINIMAL']:
            return (
                ReportQueue.PRIORITY_P0,
                f"New listing with {triage.report_decision} decision"
            )

        # P1: Grade changes (upward or downward movement)
        if triage.previous_grade and triage.previous_grade != triage.bce_grade:
            return (
                ReportQueue.PRIORITY_P1,
                f"Grade changed: {triage.previous_grade} → {triage.bce_grade}"
            )

        # P2: Forensic alerts (anomaly detected + sufficient transparency)
        if triage.forensic_flags:
            flags_str = ', '.join(triage.forensic_flags)
            return (
                ReportQueue.PRIORITY_P2,
                f"Forensic alert(s): {flags_str}"
            )

        # P3: Stale reports (existing reports older than refresh cycle)
        if triage.slug in existing_reports:
            report_meta = existing_reports[triage.slug]
            last_report = report_meta.get('last_generated')
            if last_report:
                days_old = (datetime.now() - last_report).days
                if days_old > triage.refresh_cycle_days:
                    return (
                        ReportQueue.PRIORITY_P3,
                        f"Stale report ({days_old} days old, cycle: {triage.refresh_cycle_days})"
                    )

        # P4: Never-reported projects (eligible but no report exists)
        if triage.report_decision in ['FULL', 'STANDARD', 'MINIMAL']:
            if triage.slug not in existing_reports:
                return (
                    ReportQueue.PRIORITY_P4,
                    "Never-reported eligible project"
                )

        # Does not qualify for queue
        return (None, "Does not meet queue criteria")

    def build_queue(
        self,
        triage_results: List[TriageResult],
        existing_reports: Optional[Dict[str, Dict]] = None,
        max_daily: Optional[int] = None
    ) -> List[Dict]:
        """
        Build prioritized report generation queue from triage results.

        Args:
            triage_results: List of TriageResult objects from phase D
            existing_reports: Optional dict mapping slug to report metadata
                             (includes last_generated datetime)
            max_daily: Maximum reports to queue (defaults to MAX_DAILY_REPORTS)

        Returns:
            List of queue items, each containing:
            - slug: project identifier
            - priority: 0-4 priority level
            - priority_reason: explanation of priority
            - report_types: list of report types to generate
            - report_decision: triage decision
            - triage_result: original TriageResult object
        """
        if max_daily is None:
            max_daily = MAX_DAILY_REPORTS

        existing_reports = existing_reports or {}
        queue_items = []

        # Process each triage result
        for triage in triage_results:
            # Determine if this is a new listing
            is_new = triage.slug not in existing_reports

            # Get priority and reason
            priority, reason = self._get_priority_and_reason(
                triage,
                existing_reports,
                new_listing=is_new
            )

            # Skip if doesn't qualify
            if priority is None:
                continue

            # Determine report types
            report_types = self.report_types_for_decision(triage.report_decision)

            # Add 'for' (forensic) report if FULL decision and has forensic flags
            if (triage.report_decision == 'FULL' and
                triage.forensic_flags and
                'for' not in report_types):
                report_types.append('for')

            # Build queue item
            queue_item = {
                'slug': triage.slug,
                'priority': priority,
                'priority_reason': reason,
                'report_types': report_types,
                'report_decision': triage.report_decision,
                'triage_result': triage,
            }

            queue_items.append(queue_item)

        # Sort by priority (lower number = higher priority), then by grade/score
        queue_items.sort(
            key=lambda x: (
                x['priority'],
                -x['triage_result'].total_score,  # Higher score first within priority
                x['slug']  # Alphabetical tiebreaker
            )
        )

        # Truncate to max_daily
        queue_items = queue_items[:max_daily]

        return queue_items

    @staticmethod
    def summarize_queue(queue: List[Dict]) -> Dict:
        """
        Generate summary statistics about the report queue.

        Args:
            queue: List of queue items from build_queue()

        Returns:
            Dict containing:
            - total_items: number of items in queue
            - by_priority: count by priority level (P0, P1, P2, P3, P4)
            - by_decision: count by report decision type
            - by_report_type: count of each report type to be generated
            - total_reports: total number of reports to be generated
        """
        summary = {
            'total_items': len(queue),
            'by_priority': {
                'P0': 0,
                'P1': 0,
                'P2': 0,
                'P3': 0,
                'P4': 0,
            },
            'by_decision': {},
            'by_report_type': {
                'econ': 0,
                'mat': 0,
                'for': 0,
            },
            'total_reports': 0,
        }

        for item in queue:
            # Count by priority
            priority_name = f"P{item['priority']}"
            summary['by_priority'][priority_name] += 1

            # Count by decision
            decision = item['report_decision']
            summary['by_decision'][decision] = summary['by_decision'].get(decision, 0) + 1

            # Count by report type
            for report_type in item['report_types']:
                summary['by_report_type'][report_type] += 1
                summary['total_reports'] += 1

        return summary


def main():
    """Test with mock TriageResult objects."""
    print("=" * 70)
    print("BCE Report Queue - Phase E Test")
    print("=" * 70)

    # Create mock triage results
    now = datetime.now()
    old_date = now - timedelta(days=120)

    triage_results = [
        # P0: New listing with FULL decision
        TriageResult(
            slug='new-project-1',
            bce_grade='B',
            report_decision='FULL',
            forensic_flags=['unusual_volume'],
            total_score=72.5,
            previous_grade=None,
            last_report_date=None,
        ),
        # P1: Grade upgrade
        TriageResult(
            slug='improved-project',
            bce_grade='A',
            report_decision='STANDARD',
            forensic_flags=[],
            total_score=85.0,
            previous_grade='B',
            last_report_date=now,
        ),
        # P2: Forensic alert
        TriageResult(
            slug='alert-project',
            bce_grade='C',
            report_decision='MINIMAL',
            forensic_flags=['suspicious_pattern', 'concentration_risk'],
            total_score=55.0,
            previous_grade='C',
            last_report_date=now,
        ),
        # P3: Stale report
        TriageResult(
            slug='stale-project',
            bce_grade='B',
            report_decision='STANDARD',
            forensic_flags=[],
            total_score=70.0,
            previous_grade='B',
            last_report_date=old_date,
            refresh_cycle_days=90,
        ),
        # P4: Never reported
        TriageResult(
            slug='never-reported',
            bce_grade='B',
            report_decision='STANDARD',
            forensic_flags=[],
            total_score=68.0,
            previous_grade=None,
            last_report_date=None,
        ),
        # Non-qualifying project
        TriageResult(
            slug='unratable-project',
            bce_grade='N/A',
            report_decision='UNRATABLE',
            forensic_flags=[],
            total_score=0.0,
            previous_grade=None,
            last_report_date=None,
        ),
    ]

    # Mock existing reports
    existing_reports = {
        'improved-project': {'last_generated': now},
        'alert-project': {'last_generated': now},
        'stale-project': {'last_generated': old_date},
        'unratable-project': {'last_generated': now},
    }

    # Build queue
    queue = ReportQueue()
    built_queue = queue.build_queue(
        triage_results=triage_results,
        existing_reports=existing_reports,
        max_daily=5
    )

    # Display results
    print(f"\nBuilt queue with {len(built_queue)} items:\n")
    for i, item in enumerate(built_queue, 1):
        print(f"{i}. {item['slug']}")
        print(f"   Priority: P{item['priority']} ({item['priority_reason']})")
        print(f"   Decision: {item['report_decision']}")
        print(f"   Report Types: {', '.join(item['report_types'])}")
        print(f"   Score: {item['triage_result'].total_score}")
        print()

    # Show summary
    summary = queue.summarize_queue(built_queue)
    print("=" * 70)
    print("Queue Summary")
    print("=" * 70)
    print(f"Total items in queue: {summary['total_items']}")
    print(f"Total reports to generate: {summary['total_reports']}\n")

    print("By Priority:")
    for priority, count in summary['by_priority'].items():
        if count > 0:
            print(f"  {priority}: {count}")

    print("\nBy Decision:")
    for decision, count in sorted(summary['by_decision'].items()):
        print(f"  {decision}: {count}")

    print("\nReport Types to Generate:")
    for report_type, count in sorted(summary['by_report_type'].items()):
        if count > 0:
            print(f"  {report_type}: {count}")

    print("\n" + "=" * 70)
    print("Test completed successfully!")
    print("=" * 70)


if __name__ == '__main__':
    main()
