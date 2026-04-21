# Pipeline Daily Reporting System

**Issue**: [BCE-461](/BCE/issues/BCE-461)  
**Owner**: COO  
**Status**: Production Ready ✅

## Overview

파이프라인 운영 현황 일일 보고 시스템은 FOR (Forensic) 파이프라인의 실행 현황을 자동으로 추적하고, 실패 케이스에 대한 상세 분석을 포함한 일일 보고서를 생성합니다.

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

3. **Tracking Data** — 파이프라인 실행 이력
   - Location: `scripts/pipeline/output/_for_processed.json`
   - Managed by: `ingest_for.py` and read by `watch_for_drafts.py`
   - Updated: 매 파이프라인 실행 시

## Report Contents

일일 보고서는 다음 정보를 포함합니다:

### 1. Executive Summary
- 성공 건수
- 실패 건수
- 처리 중 (Stale) 건수
- 성공률 (%)

### 2. Failures by Category
실패 케이스를 다음 카테고리로 분류:

| Category | Description |
|----------|-------------|
| **Processing Timeout** | 30분 타임아웃 초과 |
| **GDrive Download Error** | Google Drive 다운로드 실패 |
| **Supabase Publishing Error** | 데이터베이스 발행 실패 |
| **QA Critical Failure** | 치명적 품질 검증 실패 |
| **QA Major Failure** | 주요 품질 검증 실패 |
| **Translation Error** | 번역 프로세스 실패 |
| **PDF Generation Error** | PDF 생성 실패 |
| **GDrive Upload Error** | Google Drive 업로드 실패 |
| **Stuck in Processing** | 처리가 30분 이상 멈춤 (Stale) |

각 실패 케이스는 다음 정보를 포함:
- 파일명 및 slug
- 재시도 횟수
- 실패 시각
- 오류 메시지

### 3. Recent Successes
- **First-Pass Success**: 재시도 없이 성공한 케이스
- **Retried and Succeeded**: 재시도 후 성공한 케이스

### 4. Action Items
실패 유형에 따른 조치 사항 제안:
- Stale Processing 조사
- QA 실패 검토
- 타임아웃 이슈 분석
- 데이터베이스 오류 해결

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

## Extending to Other Pipelines

ECON, MAT 파이프라인으로 확장하려면:

1. **공통 draft ingress 상태 수집 전략 확장**
   - FOR는 `scripts/pipeline/output/_for_processed.json` shared tracker 사용
   - ECON/MAT는 `gdrive_drafts.py` 기반 `drafts/{TYPE}` 공통 ingress 경로를 사용하므로, 일일 리포트는 타입별 processed tracker semantics만 추가로 수집하면 됨

2. **`daily_pipeline_report.py` 수정**
   - `load_processed_data()` 함수에서 FOR local tracker + ECON/MAT source tracker 로드
   - 파이프라인별 카테고리 추가

3. **보고서 템플릿 확장**
   - 파이프라인별 섹션 추가
   - 통합 Executive Summary

## Troubleshooting

### 보고서가 생성되지 않을 때
1. `scripts/pipeline/output/_for_processed.json` 파일 존재 확인
2. Python 의존성 설치 확인: `pip install python-dotenv`
3. 로그 확인: GitHub Actions workflow logs

### Tracking data가 없을 때
- FOR pipeline이 아직 실행되지 않았을 수 있음
- `watch_for_drafts.py` 또는 `ingest_for.py` 실행 확인
- GDrive `drafts/FOR/` 폴더에 파일 존재 확인

## Related Issues

- [BCE-461](/BCE/issues/BCE-461) — 파이프라인 운영 현황 일일 보고 시스템 구축
- [BCE-457](/BCE/issues/BCE-457) — 현재 파이프라인의 보고서 생산 QA 전체 점검
- [BCE-112](/BCE/issues/BCE-112) — FOR Draft Watcher (관련 파이프라인)

## Change Log

### 2026-04-19
- ✅ Initial implementation
- ✅ GitHub Actions automation
- ✅ Report generation script
- ✅ Documentation
