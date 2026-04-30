#!/usr/bin/env python3
"""
Daily Pipeline Operations Report Generator — BCE-461

파이프라인 운영 현황 일일 보고서를 생성하여 경영진에게 제공한다.

보고 항목:
- 원문 제공되었으나 파이프라인 실패한 프로젝트 목록
- 실패 원인 (QA 실패, 번역 실패, PDF 생성 실패, 업로드 실패, DB 발행 실패 등)
- 재시도 횟수 및 성공 여부
- 현재 처리 중인 프로젝트 (stale 감지)
- 최근 24시간 처리 통계

Usage:
    python daily_pipeline_report.py                    # 보고서 생성 및 이메일 발송
    python daily_pipeline_report.py --dry-run          # 보고서 생성만 (발송 안 함)
    python daily_pipeline_report.py --days 7           # 최근 7일 데이터 포함
    python daily_pipeline_report.py --output-only      # 파일 생성만 (exec-report 스킬 사용 안 함)
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════

# Pipeline tracking file
PIPELINE_DIR = Path(__file__).resolve().parent
PROCESSED_FILE = PIPELINE_DIR / 'output' / '_for_processed.json'

# Per-run ingest summaries (BCE-812: translation metrics)
INGEST_SUMMARY_DIR = PIPELINE_DIR / 'output'

# Report output
REPORT_DIR = PIPELINE_DIR.parent.parent / 'doc' / 'board-reports'
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Log directory
LOG_DIR = PIPELINE_DIR.parent.parent / 'logs' / 'for_pipeline'

# Failure categories
FAILURE_CATEGORIES = {
    'failed_timeout': 'Processing Timeout',
    'download_error': 'GDrive Download Error',
    'upload_done_db_error': 'Supabase Publishing Error',
    'processing_error': 'Pipeline Runtime Error',
    'content_failed_terminal': 'Terminal Content Failure',
    'qa_failed_critical': 'QA Critical Failure',
    'qa_failed_major': 'QA Major Failure',
    'translation_error': 'Translation Error',
    'pdf_generation_error': 'PDF Generation Error',
    'gdrive_upload_error': 'GDrive Upload Error',
    'processing': 'Stuck in Processing (Stale)',
}

STALE_THRESHOLD_MINUTES = 30


# ═══════════════════════════════════════════
# Data Loading
# ═══════════════════════════════════════════

def load_processed_data() -> Dict:
    """Load FOR pipeline processed tracker."""
    if not PROCESSED_FILE.exists():
        return {}

    try:
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load {PROCESSED_FILE}: {e}")
        return {}


def is_stale_processing(entry: Dict) -> bool:
    """Check if a 'processing' entry is stale (stuck)."""
    started = entry.get('started_at')
    if not started:
        return True

    try:
        started_dt = datetime.fromisoformat(started.replace('Z', '+00:00'))
        elapsed = (datetime.now(timezone.utc) - started_dt).total_seconds() / 60
        return elapsed > STALE_THRESHOLD_MINUTES
    except Exception:
        return True


def categorize_failures(processed_data: Dict, days: int = 1) -> Tuple[Dict, List, List, List]:
    """
    Categorize pipeline failures from processed tracker.

    Returns:
        (failures_by_category, active_failures, stale_processing, recent_successes)
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

    failures_by_category = defaultdict(list)
    active_failures = []
    stale_processing = []
    recent_successes = []

    for file_id, entry in processed_data.items():
        status = entry.get('status', '')
        updated_at = entry.get('updated_at') or entry.get('started_at')

        # Parse timestamp
        try:
            if updated_at:
                updated_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            else:
                # No timestamp, treat as recent
                updated_dt = datetime.now(timezone.utc)
        except Exception:
            updated_dt = datetime.now(timezone.utc)

        # Skip old entries (beyond cutoff)
        if updated_dt < cutoff_time:
            continue

        # Categorize by status
        if status == 'done':
            recent_successes.append({
                'file_id': file_id,
                'name': entry.get('name', 'Unknown'),
                'slug': entry.get('slug', 'unknown'),
                'completed_at': entry.get('updated_at'),
                'retry_count': entry.get('retry_count', 0),
            })

        elif status in FAILURE_CATEGORIES:
            failure_entry = {
                'file_id': file_id,
                'name': entry.get('name', 'Unknown'),
                'slug': entry.get('slug', 'unknown'),
                'status': status,
                'category': FAILURE_CATEGORIES[status],
                'retry_count': entry.get('retry_count', 0),
                'error': entry.get('error', 'No error details'),
                'failed_at': entry.get('updated_at'),
                'started_at': entry.get('started_at'),
            }

            failures_by_category[status].append(failure_entry)
            active_failures.append(failure_entry)

        elif status == 'processing':
            # Check if stale
            if is_stale_processing(entry):
                stale_entry = {
                    'file_id': file_id,
                    'name': entry.get('name', 'Unknown'),
                    'slug': entry.get('slug', 'unknown'),
                    'started_at': entry.get('started_at'),
                    'elapsed_minutes': _calculate_elapsed_minutes(entry.get('started_at')),
                }
                stale_processing.append(stale_entry)
                failures_by_category['processing'].append(stale_entry)

    return dict(failures_by_category), active_failures, stale_processing, recent_successes


def _calculate_elapsed_minutes(started_at: Optional[str]) -> int:
    """Calculate elapsed minutes since start time."""
    if not started_at:
        return 0

    try:
        started_dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        return int((datetime.now(timezone.utc) - started_dt).total_seconds() / 60)
    except Exception:
        return 0


def load_translation_metrics(days: int = 1) -> List[Dict]:
    """Load per-report translation metrics from ingest_*.json summaries (BCE-812).

    Each ingest run writes `output/ingest_{type}_{ts}.json` with `results[*]` containing
    `translated_words`, `translated_words_total`, `google_request_count_total`,
    `google_requests_per_lang`, and `source_word_count`.

    Returns a flat list of per-report metric dicts (one per published/failed slug)
    inside the cutoff window.
    """
    if not INGEST_SUMMARY_DIR.exists():
        return []

    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
    metrics: List[Dict] = []
    seen_keys: set = set()

    for summary_file in sorted(INGEST_SUMMARY_DIR.glob('ingest_*.json')):
        try:
            ts_dt = datetime.fromtimestamp(summary_file.stat().st_mtime, tz=timezone.utc)
            if ts_dt < cutoff_time:
                continue
            with open(summary_file, 'r', encoding='utf-8') as fp:
                payload = json.load(fp)
        except Exception:
            continue

        report_type = payload.get('report_type', 'unknown')
        for entry in payload.get('results', []) or []:
            translated_words = entry.get('translated_words') or {}
            if not translated_words:
                continue
            slug = entry.get('slug') or entry.get('project_slug') or entry.get('name') or 'unknown'
            key = (report_type, slug, payload.get('timestamp') or summary_file.name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            metrics.append({
                'report_type': report_type,
                'slug': slug,
                'status': entry.get('status', 'unknown'),
                'source_word_count': entry.get('source_word_count'),
                'translated_words': translated_words,
                'translated_words_total': entry.get('translated_words_total')
                    or sum(translated_words.values()),
                'google_request_count_total': entry.get('google_request_count_total', 0),
                'google_requests_per_lang': entry.get('google_requests_per_lang') or {},
                'translation_durations': entry.get('translation_durations') or {},
                'translation_backend': entry.get('translation_backend', 'google_cloud'),
                'timestamp': payload.get('timestamp') or ts_dt.isoformat(),
            })

    return metrics


def summarize_translation_metrics(metrics: List[Dict]) -> Dict:
    """Aggregate translation metrics across reports for the dashboard section."""
    if not metrics:
        return {
            'report_count': 0,
            'total_translated_words': 0,
            'total_google_requests': 0,
            'avg_words_per_report': 0,
            'avg_requests_per_report': 0,
            'by_lang': {},
            'by_type': {},
        }

    by_lang_words: Dict[str, int] = defaultdict(int)
    by_lang_requests: Dict[str, int] = defaultdict(int)
    by_type_words: Dict[str, int] = defaultdict(int)
    by_type_count: Dict[str, int] = defaultdict(int)
    total_words = 0
    total_requests = 0

    for m in metrics:
        total_words += m['translated_words_total']
        total_requests += m['google_request_count_total']
        by_type_words[m['report_type']] += m['translated_words_total']
        by_type_count[m['report_type']] += 1
        for lang, words in m['translated_words'].items():
            by_lang_words[lang] += int(words or 0)
        for lang, reqs in m['google_requests_per_lang'].items():
            by_lang_requests[lang] += int(reqs or 0)

    n = len(metrics)
    return {
        'report_count': n,
        'total_translated_words': total_words,
        'total_google_requests': total_requests,
        'avg_words_per_report': total_words // n if n else 0,
        'avg_requests_per_report': total_requests // n if n else 0,
        'by_lang': {
            lang: {
                'words': by_lang_words[lang],
                'requests': by_lang_requests.get(lang, 0),
            }
            for lang in sorted(by_lang_words)
        },
        'by_type': {
            rt: {
                'reports': by_type_count[rt],
                'words': by_type_words[rt],
                'avg_words_per_report': (by_type_words[rt] // by_type_count[rt])
                    if by_type_count[rt] else 0,
            }
            for rt in sorted(by_type_count)
        },
    }


def load_recent_logs(days: int = 1) -> List[Path]:
    """Load recent pipeline log files."""
    if not LOG_DIR.exists():
        return []

    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
    recent_logs = []

    for log_file in LOG_DIR.glob('for_pipeline_run_*.md'):
        try:
            # Extract timestamp from filename: for_pipeline_run_20260418_210450.md
            timestamp_str = log_file.stem.replace('for_pipeline_run_', '')
            log_dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S').replace(tzinfo=timezone.utc)

            if log_dt >= cutoff_time:
                recent_logs.append(log_file)
        except Exception:
            continue

    return sorted(recent_logs)


# ═══════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════

def generate_report(
    failures_by_category: Dict,
    active_failures: List,
    stale_processing: List,
    recent_successes: List,
    days: int = 1,
    translation_metrics: Optional[List[Dict]] = None,
) -> str:
    """Generate markdown report content."""

    report_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    report_period = f"최근 {days}일" if days > 1 else "최근 24시간"

    # Calculate statistics
    total_failures = len(active_failures)
    total_stale = len(stale_processing)
    total_successes = len(recent_successes)
    total_processed = total_failures + total_successes

    success_rate = (total_successes / total_processed * 100) if total_processed > 0 else 0

    # Build report
    report = f"""# Pipeline Operations Daily Report — COO-{datetime.now().strftime('%Y%m%d')}

**보고 일자**: {report_date}
**보고 기간**: {report_period}
**보고 대상**: FOR Pipeline (Forensic Reports)

---

## Executive Summary

**처리 현황** ({report_period}):
- ✅ **성공**: {total_successes}건
- ❌ **실패**: {total_failures}건
- ⏸️ **처리 중 (Stale)**: {total_stale}건
- 📊 **성공률**: {success_rate:.1f}%

"""

    # Translation pipeline metrics (BCE-812)
    if translation_metrics:
        agg = summarize_translation_metrics(translation_metrics)
        report += f"""
## 번역 파이프라인 지표 ({report_period})

**유료 번역 API**: Google Cloud Translation v3 (`projects.locations.translateText`)

| 지표 | 값 |
|------|-----|
| 처리 보고서 수 | {agg['report_count']}건 |
| 유료 API 통과 단어 합계 | **{agg['total_translated_words']:,}** words |
| 보고서 1건당 평균 단어 | {agg['avg_words_per_report']:,} words |
| Google 요청 합계 | {agg['total_google_requests']:,} 회 |
| 보고서 1건당 평균 요청 | {agg['avg_requests_per_report']} 회 |

### 언어별 번역량 (target=언어, source=ko)

| 언어 | 단어 수 | Google 요청 |
|------|---------|------------|
"""
        for lang, stats in agg['by_lang'].items():
            report += f"| {lang} | {stats['words']:,} | {stats['requests']:,} |\n"

        if agg['by_type']:
            report += """
### 보고서 유형별 번역량

| 유형 | 보고서 수 | 단어 합계 | 평균 단어/건 |
|------|----------|-----------|------------|
"""
            for rt, stats in agg['by_type'].items():
                report += (
                    f"| {rt.upper()} | {stats['reports']} | "
                    f"{stats['words']:,} | {stats['avg_words_per_report']:,} |\n"
                )

        report += "\n### 보고서별 상세 (상위 10건)\n\n"
        report += "| 시각 | 유형 | 슬러그 | 상태 | 단어수 | Google 요청 |\n"
        report += "|------|------|--------|------|--------|-------------|\n"
        for m in sorted(translation_metrics, key=lambda x: x['timestamp'], reverse=True)[:10]:
            slug_short = m['slug'][:40] + ('…' if len(m['slug']) > 40 else '')
            ts_short = m['timestamp'][:16].replace('T', ' ')
            report += (
                f"| {ts_short} | {m['report_type']} | `{slug_short}` | "
                f"{m['status']} | {m['translated_words_total']:,} | "
                f"{m['google_request_count_total']} |\n"
            )
        report += "\n"

    # Failures by category
    if total_failures > 0 or total_stale > 0:
        report += f"""
## Failures by Category

"""
        for category_key, category_name in FAILURE_CATEGORIES.items():
            entries = failures_by_category.get(category_key, [])
            if entries:
                report += f"""
### {category_name} ({len(entries)}건)

"""
                for entry in entries:
                    slug = entry.get('slug', 'unknown')
                    name = entry.get('name', 'Unknown')
                    retry_count = entry.get('retry_count', 0)
                    error = entry.get('error', 'No details')

                    if category_key == 'processing':
                        elapsed = entry.get('elapsed_minutes', 0)
                        report += f"- **{name}** (`{slug}`)\n"
                        report += f"  - 경과 시간: {elapsed}분 (threshold: {STALE_THRESHOLD_MINUTES}분)\n"
                        report += f"  - 시작 시각: {entry.get('started_at', 'N/A')}\n"
                    else:
                        report += f"- **{name}** (`{slug}`)\n"
                        report += f"  - 재시도 횟수: {retry_count}\n"
                        report += f"  - 실패 시각: {entry.get('failed_at', 'N/A')}\n"
                        report += f"  - 오류: {error}\n"

                    report += "\n"

    else:
        report += f"""
## No Failures

{report_period} 동안 실패한 케이스가 없습니다. ✅

"""

    # Recent successes summary
    if recent_successes:
        report += f"""
## Recent Successes ({len(recent_successes)}건)

"""
        # Group by retry count
        first_pass = [s for s in recent_successes if s['retry_count'] == 0]
        retried = [s for s in recent_successes if s['retry_count'] > 0]

        if first_pass:
            report += f"""
### First-Pass Success ({len(first_pass)}건)

"""
            for success in first_pass[:10]:  # Show first 10
                report += f"- {success['name']} (`{success['slug']}`)\n"

            if len(first_pass) > 10:
                report += f"\n*...and {len(first_pass) - 10} more*\n"

        if retried:
            report += f"""
### Retried and Succeeded ({len(retried)}건)

"""
            for success in retried:
                report += f"- {success['name']} (`{success['slug']}`) — {success['retry_count']} retries\n"

    # Action items
    if total_failures > 0 or total_stale > 0:
        report += f"""
---

## Action Items

"""
        if total_stale > 0:
            report += f"""
### 1. Investigate Stale Processing ({total_stale}건)

처리가 {STALE_THRESHOLD_MINUTES}분 이상 멈춰 있는 케이스를 조사하고 재시도 또는 취소 결정 필요.

"""

        if failures_by_category.get('qa_failed_critical') or failures_by_category.get('qa_failed_major'):
            qa_count = len(failures_by_category.get('qa_failed_critical', [])) + len(failures_by_category.get('qa_failed_major', []))
            report += f"""
### 2. QA Failures Review ({qa_count}건)

QA 검증 실패 케이스를 검토하여 원문 품질 개선 또는 QA 룰 조정 필요.

"""

        if failures_by_category.get('failed_timeout'):
            timeout_count = len(failures_by_category['failed_timeout'])
            report += f"""
### 3. Timeout Issues ({timeout_count}건)

처리 시간이 30분을 초과한 케이스. 파이프라인 성능 최적화 또는 타임아웃 임계값 조정 검토 필요.

"""

        if failures_by_category.get('upload_done_db_error'):
            db_error_count = len(failures_by_category['upload_done_db_error'])
            report += f"""
### 4. Database Publishing Errors ({db_error_count}건)

PDF 생성 및 GDrive 업로드는 완료되었으나 Supabase 발행 단계에서 실패. DB 연결 및 스키마 검증 필요.

"""

    else:
        report += f"""
---

## Action Items

현재 조치가 필요한 실패 케이스 없음. 모니터링 지속.

"""

    # Metadata
    report += f"""
---

## Technical Details

**Pipeline**: FOR (Forensic Reports)
**Tracking File**: `{PROCESSED_FILE.relative_to(PIPELINE_DIR.parent.parent)}`
**Log Directory**: `{LOG_DIR.relative_to(PIPELINE_DIR.parent.parent)}`
**Report Generated**: {datetime.now(timezone.utc).isoformat()}Z
**Issue**: [BCE-461](/BCE/issues/BCE-461)

"""

    return report


def save_report(content: str, output_path: Optional[Path] = None) -> Path:
    """Save report to file."""
    if output_path is None:
        report_id = f"COO-{datetime.now().strftime('%Y%m%d')}_pipeline_operations_daily"
        output_path = REPORT_DIR / f"{report_id}.md"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ Report saved: {output_path}")
    return output_path


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Generate daily pipeline operations report')
    parser.add_argument('--days', type=int, default=1, help='Days to include in report (default: 1)')
    parser.add_argument('--dry-run', action='store_true', help='Generate report but do not send email')
    parser.add_argument('--output-only', action='store_true', help='Only save to file, skip exec-report skill')
    args = parser.parse_args()

    print("=" * 70)
    print("Pipeline Operations Daily Report Generator — BCE-461")
    print(f"Report Period: Last {args.days} day(s)")
    print("=" * 70)

    # Step 1: Load processed data
    print("\n[1/4] Loading pipeline data...")
    processed_data = load_processed_data()
    print(f"  ✓ Loaded {len(processed_data)} tracked files")

    # Step 2: Categorize failures
    print("\n[2/4] Analyzing failures...")
    failures_by_category, active_failures, stale_processing, recent_successes = categorize_failures(
        processed_data, days=args.days
    )

    print(f"  ✓ Total failures: {len(active_failures)}")
    print(f"  ✓ Stale processing: {len(stale_processing)}")
    print(f"  ✓ Recent successes: {len(recent_successes)}")

    # Step 2.5: Load translation metrics from per-run ingest summaries (BCE-812)
    print("\n[2.5/4] Aggregating translation metrics...")
    translation_metrics = load_translation_metrics(days=args.days)
    if translation_metrics:
        agg = summarize_translation_metrics(translation_metrics)
        print(f"  ✓ Reports with translation data: {agg['report_count']}")
        print(f"  ✓ Total billed words (Google Cloud Translation): {agg['total_translated_words']:,}")
    else:
        print("  ✓ No translation metrics in window")

    # Step 3: Generate report
    print("\n[3/4] Generating report...")
    report_content = generate_report(
        failures_by_category,
        active_failures,
        stale_processing,
        recent_successes,
        days=args.days,
        translation_metrics=translation_metrics,
    )

    # Step 4: Save report
    print("\n[4/4] Saving report...")
    report_path = save_report(report_content)

    # Optional: Use exec-report skill
    if not args.output_only and not args.dry_run:
        print("\n[NEXT] To send this report via exec-report skill, run:")
        print(f"  claude code 'Use exec-report skill to send {report_path.name} to philoskor@gmail.com'")

    print("\n" + "=" * 70)
    print("REPORT GENERATION COMPLETE")
    print(f"  Report: {report_path}")
    print(f"  Total failures: {len(active_failures)}")
    print(f"  Stale processing: {len(stale_processing)}")
    print("=" * 70)

    return 0


if __name__ == '__main__':
    sys.exit(main())
