# Pipeline Daily Reporting System

**Issue**: [BCE-1870](/BCE/issues/BCE-1870)
**Owner**: COO  
**Status**: Current slide-pipeline taxonomy normalized

## Overview

파이프라인 운영 현황 일일 보고 시스템은 현재 운영 경로인 `scripts/pipeline/watch_slides.py` 기준으로 ECON/MAT/FOR 슬라이드 발행 상태를 추적하고, 성공/실패/blocked/stale/reconcile 상태를 포함한 일일 보고서를 생성합니다.

## Architecture

### Components

1. **`daily_pipeline_report.py`** — 보고서 생성 스크립트
   - Location: `scripts/pipeline/daily_pipeline_report.py`
   - Function: 파이프라인 실행 이력을 분석하여 마크다운 보고서 생성
   - Output: `doc/board-reports/COO-{YYYYMMDD}_pipeline_operations_daily.md`

2. **GitHub Actions Workflow** — 자동화 실행
   - Location: `.github/workflows/pipeline-daily-report.yml`
   - Schedule: 매일 00:00 UTC (09:00 KST)
   - Function: 보고서 생성 및 리포지토리 커밋

3. **Tracking Data** — 현재 슬라이드 발행 실행 이력
   - Current source of truth: `scripts/pipeline/output/_slide_processed.json`
   - Writer: `scripts/pipeline/watch_slides.py`
   - Source folders: Google Drive `Slide/econ/`, `Slide/mat/`, `Slide/for/`
   - Paperclip telemetry: `scripts/pipeline/watch_slides_telemetry.py`의 success/failure/blocked taxonomy를 재사용
   - Updated: 매 슬라이드 watcher 실행 시

4. **Historical FOR Tracker** — 재현/감사용 legacy 자료
   - Location: `scripts/pipeline/output/_for_processed.json`
   - Former source: `ingest_for.py` / `_legacy/pipeline/watch_for_drafts.py`
   - Usage: historical reproduction only. 현재 운영 상태 판단 기준으로 사용하지 않습니다.

## Report Contents

일일 보고서는 다음 정보를 포함합니다:

### 1. Executive Summary
- 성공 건수
- 실패 건수
- Blocked/manual 건수
- 처리 중 stale 건수
- DB reconcile 건수
- 성공률 (%)

### 2. Report Type Status Matrix
ECON/MAT/FOR별 합계와 상태군을 보여줍니다.

| Status group | Examples | Meaning |
|--------------|----------|---------|
| **success** | `published`, `review_ready`, `unchanged`, `dry_run`, prune success statuses | watcher가 정상적으로 처리했거나 조치 불필요 |
| **failed** | `failed`, legacy terminal failure names | 런타임/발행 실패 |
| **blocked** | `unresolved`, `mismatch`, `language_mismatch`, `blocked_missing_analysis_source`, `prune_skipped_*`, `db_reconcile_skipped` | 자동 발행이 멈췄고 수동 확인 필요 |
| **stale** | stale `processing`, `stale_processing` diagnostics | processing manifest가 stale threshold를 초과 |
| **reconcile** | `db_reconcile_*`, `dry_run_db_reconcile_*` | Drive `Slide/{TYPE}/`와 DB visible rows/timestamps 정합성 결과 |

### 3. Operational Attention Queue
`failed`, `blocked`, `stale`, `reconcile` 상태군의 최근 항목을 최대 30건까지 표시합니다.

### 4. Action Items
상태군에 따른 조치 사항 제안:
- Stale Processing 조사
- Blocked/manual 상태 해소
- DB reconcile 결과 표본 확인
- legacy terminal failure가 남아 있는 경우 재현 범위로 격리

### 5. Technical Details
- 파이프라인 타입
- 트래킹 파일 경로
- 로그 디렉토리
- 보고서 생성 시각

## Usage

### Manual Execution

```bash
# Generate report for last 24 hours
python3 scripts/pipeline/daily_pipeline_report.py

# Generate report for last 7 days
python3 scripts/pipeline/daily_pipeline_report.py --days 7

# Dry run (no email)
python3 scripts/pipeline/daily_pipeline_report.py --dry-run

# Save to file only (skip exec-report skill)
python3 scripts/pipeline/daily_pipeline_report.py --output-only
```

### Automated Execution

보고서는 매일 자동으로 생성됩니다:
- **Schedule**: 00:00 UTC (09:00 KST)
- **Method**: GitHub Actions workflow
- **Output**: 
  - Committed to repository: `doc/board-reports/COO-{YYYYMMDD}_pipeline_operations_daily.md`
  - Uploaded as artifact (30-day retention)

### Manual Trigger

GitHub Actions UI에서 수동 실행:
1. Go to **Actions** tab
2. Select **Pipeline Daily Report** workflow
3. Click **Run workflow**

## Email Delivery (Optional)

보고서를 이메일로 발송하려면 `exec-report` 스킬 사용:

```bash
claude code 'Use exec-report skill to send COO-20260419_pipeline_operations_daily.md to philoskor@gmail.com'
```

또는 Paperclip routine으로 자동화 가능.

## Monitoring

### Success Metrics
- 보고서 생성 성공 여부
- 보고서 파일 존재 확인
- GitHub Actions workflow 상태

### Alerts
- Workflow 실패 시 GitHub 알림
- 보고서 파일 생성 실패 시 로그 확인

## Extending the Taxonomy

새 슬라이드 상태를 추가할 때:

1. **Watcher telemetry에 먼저 추가**
   - `scripts/pipeline/watch_slides_telemetry.py`의 success/failure/blocked status set에 상태를 분류
   - Paperclip telemetry와 daily report가 같은 의미로 상태를 읽게 유지

2. **`daily_pipeline_report.py` 검증 추가**
   - 신규 status가 success/failed/blocked/stale/reconcile 중 어디에 속하는지 fixture test 추가
   - DB reconcile 상태는 `db_reconcile_*` 또는 `dry_run_db_reconcile_*` prefix를 유지

3. **운영 문서 갱신**
   - CRO/COO 보고서 포맷에 의미 있는 새 상태군이면 이 문서의 status table과 action item을 갱신

## Troubleshooting

### 보고서가 생성되지 않을 때
1. `scripts/pipeline/output/_slide_processed.json` 파일 존재 확인
2. Python 의존성 설치 확인: `pip install python-dotenv`
3. 로그 확인: GitHub Actions workflow logs

### Tracking data가 없을 때
- `scripts/pipeline/output/_slide_processed.json` 파일 존재 확인
- `scripts/pipeline/watch_slides.py --type all --dry-run`으로 current Slide folder scan 가능 여부 확인
- `_legacy/pipeline/watch_for_drafts.py`, `ingest_for.py`, `_for_processed.json`을 운영 판단 기준으로 사용하지 말 것
- 현재 경로는 `scripts/pipeline/watch_slides.py`와 GDrive `Slide/{TYPE}/` PDF 확인

## Related Issues

- [BCE-1870](/BCE/issues/BCE-1870) — 슬라이드 파이프라인 운영 리포팅 정규화
- [BCE-1869](/BCE/issues/BCE-1869) — watch_slides.py 모듈 경계 1차 분리
- [BCE-461](/BCE/issues/BCE-461) — 파이프라인 운영 현황 일일 보고 시스템 구축
- [BCE-457](/BCE/issues/BCE-457) — 현재 파이프라인의 보고서 생산 QA 전체 점검
- [BCE-112](/BCE/issues/BCE-112) — FOR Draft Watcher (관련 파이프라인)

## Change Log

### 2026-05-12
- Current source of truth changed to `_slide_processed.json`
- ECON/MAT/FOR report type matrix added
- Blocked/stale/reconcile taxonomy aligned with `watch_slides_telemetry.py`
- `_for_processed.json` documented as historical/reproduction-only

### 2026-04-19
- ✅ Initial implementation
- ✅ GitHub Actions automation
- ✅ Report generation script
- ✅ Documentation
