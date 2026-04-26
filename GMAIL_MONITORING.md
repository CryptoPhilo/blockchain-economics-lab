# Gmail Inbox Monitoring System

## Overview

This implementation polls Gmail directly through the Gmail REST API on a 30-minute cadence (UTC), inspects inbox threads from the last 30 minutes, creates Paperclip issues for new actionable work-instruction emails, assigns them by category, and labels the processed Gmail thread to keep reruns safe.

The current production runner intentionally uses the Gmail REST API instead of Gmail MCP. The parent issue description in [BCE-548](/BCE/issues/BCE-548) still references Gmail MCP verbs, but the checked-in automation runs through GitHub Actions and the `./run_gmail_inbox_monitor.sh` entrypoint with Gmail OAuth secrets, so this repository treats the REST implementation as the canonical execution path until an MCP-backed runtime is introduced.

## Canonical Execution Paths

### `./run_gmail_inbox_monitor.sh`
- Canonical local, CI, and workflow entrypoint
- Executes `scripts/gmail_monitor.py`

### `scripts/gmail_inbox_monitor.sh`
- Deprecated compatibility shim
- Forwards to `./run_gmail_inbox_monitor.sh`
- Kept only to avoid breaking older operator habits or stale automation
- New automation and runbooks should call `./run_gmail_inbox_monitor.sh` directly

### Legacy Paperclip routine path
- Legacy / transition path only
- The older Paperclip routine executions are kept only as historical overlap while duplicate-run cleanup is in progress
- This path should be considered disabled for new traffic so the 30-minute cadence remains single-sourced through GitHub Actions

### `.github/workflows/gmail-inbox-monitor.yml`
- GitHub Actions schedule: fixed 30-minute intervals (`*/30 * * * *`, i.e., every 30 minutes in UTC)
- `workflow_dispatch` support for manual reruns
- Runs `./run_gmail_inbox_monitor.sh --preflight` before the live monitor step so scheduled execution uses the same readiness gate as operator runs
- Uses repository secrets for Paperclip and Gmail OAuth credentials
- Uses a 30-minute Gmail search window on each 30-minute execution to avoid gaps when a scheduled run is delayed
- Uses the same default processed label as the script: `Paperclip/Processed`

### `scripts/gmail_monitor.py`
- Direct Gmail REST API runner using OAuth refresh-token auth
- Filters inbox mail to the most recent 30 minutes by default
- Deduplicates on Gmail thread id using:
  - `scripts/processed_gmail_threads.json`
  - existing Paperclip issues whose description already contains the thread id
- Applies the configured Gmail processed label after a successful create or dedup match

## Routing Rules

Detected issue categories map to these assignees:

- `technical` → CTO
- `marketing` → CMO
- `operations` / logistics → COO
- `revenue` / sales → CRO
- `research` → CRO
- `other` → CEO

The runner resolves the real agent IDs at runtime from the Paperclip API, so the code does not hard-code those IDs.

## Priority Rules

- `critical`: contains urgency terms like `즉시`, `긴급`, `ASAP`, `urgent`, `바로`
- `high`: contains terms like `오늘`, `빠르게`, `중요`, `우선`, `금일`
- `medium`: default

## Action Filter

The runner treats a mail as actionable when subject or body contains at least one of:

- `할 것`
- `지시`
- `요청`
- `보고`
- `확인`
- `만들`
- `생성`
- `검토`
- `분석`
- `작성`

It skips obvious non-work mail such as test or forwarded subjects.

## Required Secrets

GitHub Actions and manual runs need:

- `PAPERCLIP_API_URL`
- `PAPERCLIP_API_KEY`
- `PAPERCLIP_COMPANY_ID`
- `PAPERCLIP_AGENT_ID`
- `GMAIL_CLIENT_ID`
- `GMAIL_CLIENT_SECRET`
- `GMAIL_REFRESH_TOKEN`

Live execution still depends on secret provisioning tracked in [BCE-522](/BCE/issues/BCE-522). Without those secrets, preflight can explain the gap but the monitor cannot complete a real run. That secret dependency applies to both GitHub Actions and any manual `./run_gmail_inbox_monitor.sh` invocation.

Optional overrides:

- `GMAIL_MONITOR_USER` default: `philoskor@gmail.com`
- `GMAIL_PROCESSED_LABEL` default: `Paperclip/Processed`
- `GMAIL_SINCE_HOURS` default: `0.5` (30 minute search window on a 30 minute workflow cadence)
- `PAPERCLIP_GOAL_ID` default: Board Operations goal
- `PAPERCLIP_PROJECT_ID` default: Board Operations project

## 운영 시크릿 프로비저닝 체크리스트

이 항목은 배포 운영 환경에서 `gmail_inbox_monitor`를 즉시 실행 가능한 상태로 만들기 위한 체크리스트입니다.

1. GitHub Actions 시크릿 설정
   - 대상 저장소: Paperclip 모니터링 워크플로가 있는 저장소
   - 설정 위치: Repository Settings → Secrets and variables → Actions
   - 등록 시크릿
     - `PAPERCLIP_API_URL`
     - `PAPERCLIP_API_KEY`
     - `PAPERCLIP_COMPANY_ID`
     - `PAPERCLIP_AGENT_ID`
     - `GMAIL_CLIENT_ID`
     - `GMAIL_CLIENT_SECRET`
     - `GMAIL_REFRESH_TOKEN`
   - 권장 값
     - `GMAIL_MONITOR_USER=me`
     - `GMAIL_PROCESSED_LABEL=Paperclip/Processed`
     - `GMAIL_SINCE_HOURS=0.5`
     - `PAPERCLIP_GOAL_ID=176cc80b-f108-4098-ad4c-bac14515d346`
     - `PAPERCLIP_PROJECT_ID=c99a905c-51d4-41a7-9635-b14c5537d9ab`

2. 수동/로컬 실행 환경 점검
   - `PAPERCLIP_API_KEY`는 GitHub Actions 토큰 대신 임시 운영 토큰 사용 금지
   - 실행 명령
     - `export`로 필수 시크릿을 입력한 뒤 `./run_gmail_inbox_monitor.sh --preflight --since-hours "${GMAIL_SINCE_HOURS:-0.5}"`
     - 필요하면 이어서 `./run_gmail_inbox_monitor.sh --dry-run --since-hours "${GMAIL_SINCE_HOURS:-0.5}"`
   - 체크 포인트
     - preflight가 `Missing required environment variable: ... Run ./run_gmail_inbox_monitor.sh --preflight ... BCE-522 ...` 형태의 조치 경로를 포함해 실패 원인을 직접 설명
     - OAuth token 획득, assignee routing 해석, Gmail 검색 접근이 성공
     - 쓰기 동작은 `--dry-run`에서만 별도로 시뮬레이트

3. 운영 실행 검증
   - GitHub Actions에서 수동 실행 1회 (`workflow_dispatch`)
   - 완료 로그에서 `"Starting Gmail inbox monitor"` / `"Gmail inbox monitor completed"` 출력 확인
   - 실행 대상 스레드에 대해서는 `Paperclip/Processed` 라벨 또는 검색 범위 제외가 정상 동작해야 함
   - Paperclip routine 기반 legacy 실행 경로는 중복 생성 방지를 위해 비활성화 상태로 유지

## Runtime Artifacts

- Log file: `scripts/gmail_monitor.log`
- Local dedup state: `scripts/processed_gmail_threads.json`
- Canonical workflow definition: `.github/workflows/gmail-inbox-monitor.yml`

## Manual Verification

Dry run:

```bash
./run_gmail_inbox_monitor.sh --dry-run --since-hours "${GMAIL_SINCE_HOURS:-0.5}"
```

Preflight:

```bash
./run_gmail_inbox_monitor.sh --preflight --since-hours "${GMAIL_SINCE_HOURS:-0.5}"
```

Real run:

```bash
./run_gmail_inbox_monitor.sh --since-hours "${GMAIL_SINCE_HOURS:-0.5}"
```

Deprecated path still works, but should not be used for new automation:

```bash
./scripts/gmail_inbox_monitor.sh --preflight
```

Legacy Paperclip routine path:

- keep only as a transition artifact while duplicate-run cleanup is completed
- do not re-enable for new scheduled traffic unless the single canonical path is being replaced intentionally

Expected result:

- new actionable thread creates one Paperclip issue
- issue description includes sender, received timestamp, summary, and explicit `Gmail Thread ID: ...` marker
- assignee and priority reflect detected category and urgency
- Gmail thread receives the configured processed label (`Paperclip/Processed` by default)
- reruns do not create duplicates

## Testing

Core logic checks:

```bash
npm run test:gmail-monitor
```

This command runs:

- Python syntax validation for `scripts/gmail_monitor.py`
- unit tests in `scripts/test_gmail_monitor.py`

## Deduplication Strategy

The monitor is safe to rerun because it uses both local and remote deduplication:

1. Local file lock + atomic JSON update in `scripts/processed_gmail_threads.json`
2. Existing Paperclip issue search using `GET /api/companies/{companyId}/issues?q={thread_id}` and project-filtered `Gmail Thread ID: ...` marker match
3. Gmail processed label to keep already-handled threads out of the normal search path

## Workspace Hygiene

- Runtime artifacts are local-only and should not be included in the base-branch change set:
  - `scripts/gmail_monitor.log`
  - `scripts/processed_gmail_threads.json`
  - `scripts/*.lock`
  - `__pycache__/`
  - `.pytest_cache/`
