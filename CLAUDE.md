# BCE Lab - Project Guide

## Project Overview

**BCE Lab** (Blockchain Economics Research) is a comprehensive research platform for analyzing blockchain economic metrics, trends, and strategic insights.

- **Tech Stack**: Next.js 16, Supabase, Python pipeline
- **Frontend**: React/TypeScript with Next.js API routes
- **Backend**: Supabase (PostgreSQL) + Python orchestrator for report generation
- **Reporting**: Multi-format (ECON, MAT, FOR) with PDF generation and distribution

## 한국어 우선 정책

사내 모든 에이전트 간 소통, 보드 보고서, 이슈 코멘트, 상태 업데이트는 **한국어**로 작성한다.

| 항목 | 언어 | 비고 |
|------|------|------|
| Paperclip 이슈 코멘트 | 한국어 | 모든 에이전트 |
| 보드 보고서 (exec-report) | 한국어 | CEO-###, RES-### 등 |
| 에이전트 간 위임/지시 | 한국어 | 하위 에이전트 포함 |
| git commit message | 영어 | 기술 관례 |
| 코드 변수명/주석 | 영어 | 코드 가독성 |
| API 문서 | 영어 | 외부 호환 |

## Key Directories

- `src/` - Frontend application (Next.js pages, components, API routes)
- `scripts/pipeline/` - Python report generation pipeline
- `supabase/` - Database migrations and configuration
- `data/` - Project JSON definitions and metadata
- `doc/` - Strategy documents and research guides
- `public/` - Static assets

## Report Types

Three main report formats with type codes:

- **ECON** (RPT-ECON) - Economic analysis reports
- **MAT** (RPT-MAT) - Market analysis reports
- **FOR** (RPT-FOR) - Forecast reports

### ECON Prompt Version

**Current Version**: v4.2 (Production) ✅

- **Prompt File**: `econ_v4.2_production_prompt.md`
- **Status**: Production Ready (2026-04-18)
- **Validation**: 3/3 pilot tests passed (Cosmos, Bitcoin, Ethereum)
- **Key Features**:
  - URL-only input (PROJECT_NAME auto-extraction)
  - Mandatory Section 7 참고문헌 (48+ URLs required)
  - Inline citation format: `[1]`, `[2]` (superscripts prohibited)
  - Project-type guides (Layer 1/2, DeFi, dApp)
  - URL validation (404 check)

**Evaluation Reports**:
- [CRO-002: Cosmos v4.1](/doc/board-reports/CRO-002_econ_v4.1_prompt_evaluation.md)
- [CRO-003: Aave v4.1](/doc/board-reports/CRO-003_econ_v4.1_aave_evaluation.md)
- [CRO-004: Bitcoin & Ethereum v4.1.1](/doc/board-reports/CRO-004_econ_v4.1.1_bitcoin_ethereum_evaluation.md)

**Legacy Prompts**: Moved to `_legacy/prompts/` (v3.1, v4.0, v4.1, v4.1.1)

## 5-Stage Pipeline

Report generation follows a strict 5-stage process:

1. **Stage 0: Data Collection** - Fetch data from Etherscan, blockchain sources
2. **Stage 1: Text Generation** - Generate report content using Anthropic API
3. **Stage 1.5: Translation** - Translate to 7 languages (en, ko, fr, es, de, ja, zh)
4. **Stage 2: PDF Generation** - Create PDF documents
5. **Stage 3: Upload** - Upload to Google Drive and send via email (Resend)

## Key Skills

- `exec-report` - **경영진/보드 보고서 통합 프로세스** (.md 작성 → Google Drive 업로드 → 이메일 발송)
- `report-pipeline` - Main orchestrator for report generation (다국어 PDF)
- `slide-econ`, `slide-mat`, `slide-for` - Slide deck generation for each report type
- `auto-analysis` - Automated analysis workflow
- `deploy` - **프론트엔드 배포** (lint/typecheck 검증 → git push → Vercel 자동 빌드 → 라이브 검증)
- `gdrive-upload` - Google Drive integration (exec-report가 내부적으로 호출)
- `resend-email` - Email delivery service (exec-report가 내부적으로 호출)

### 경영진 보고 규칙 (필독)

**모든 경영진/보드 보고서는 반드시 `exec-report` 스킬을 따른다:**
1. **.md 형식만 사용** (.docx, .pdf로 만들지 않는다)
2. `doc/board-reports/` 에 저장 (Report ID 체계: CEO-###, RES-###, OPS-###, MKT-###, QA-###, SEC-###)
3. Google Drive "C-level management report" 폴더에 업로드
4. **philoskor@gmail.com** 으로 이메일 발송 (Drive 링크 포함)
5. Supabase board_reports 테이블에 메타데이터 기록

## 티켓 생성 규칙 (CEO-006 / QA-006 승인)

**모든 업무는 Supabase `tickets` 테이블에 티켓으로 관리한다.** 프롬프트가 티켓 생성 없이 실행되는 것을 방지하기 위해 다음 규칙을 따른다.

### 프롬프트 유형 판별

| 유형 | 판별 기준 | 티켓 생성 |
|------|-----------|----------|
| **지시** | "~해줘", "~할 것", "~하도록", "~를 수정해", 스크린샷+수정 요청 | ✅ 필수 |
| **검토/확인** | "~인지 확인해", "~를 검토해", "~를 점검해" | ✅ 필수 |
| **질문/대화** | "이게 뭐야?", "왜 그런 거지?", "어떻게 해?" | ❌ 불요 |

### 티켓 생성 타이밍

1. **단건 지시**: 작업 착수 **전** tickets 테이블에 INSERT (status: `in_progress`)
2. **실시간 피드백 루프** (스크린샷 → 수정 → 확인 반복): 루프 **종료 후** 일괄 등록 (status: `done`, origin: `session_retroactive`)
3. **세션 종료 시**: 해당 세션에서 수행된 모든 작업을 복기하여 누락 티켓 소급 등록

### 티켓 코드 체계

담당 부서 prefix를 따른다: `OPS-`, `RES-`, `MKT-`, `QA-`, `SEC-`, `STR-`
보드 리포트 하위 작업: `{report_id}-T{##}` (예: `QA-006-T01`)

### Board 보고 연동

티켓 생성 시 `board_report_id` 필드에 관련 보드 리포트 ID를 기록한다.

## Deprecated (Do Not Use)

- `_legacy_gen_*.py` - Legacy generator scripts (deprecated)
- `slide-report` skill - Use type-specific skills instead
- `bce-multilingual-report` skill - Use `report-pipeline` instead

## Main Command

Generate reports with the orchestrator:

```bash
python scripts/pipeline/orchestrator.py --type econ --project <slug> --version <N> --lang all
```

**Options:**
- `--type` - Report type (econ, mat, for)
- `--project` - Project slug (from data/projects.json)
- `--version` - Report version number
- `--lang` - Language code or 'all' for all 7 supported languages

## Supported Languages

7 languages across all reports: **en, ko, fr, es, de, ja, zh**

## Required Environment Variables

See `.env.example` for all variables. Key categories:

- **Supabase**: Database credentials
- **Email**: Resend API + webhook secret
- **Google Drive**: Service account JSON + folder ID
- **Pipeline**: Anthropic API + Etherscan API
- **Secrets**: Newsletter & cron API secrets (32+ bytes)

## Automated Pipelines

### Pipeline Daily Reporting (BCE-461)

The pipeline operations daily reporting system tracks and reports on pipeline execution status:

- **Script**: `scripts/pipeline/daily_pipeline_report.py`
- **Schedule**: Daily at 00:00 UTC (09:00 KST) via GitHub Actions
- **Output**: `doc/board-reports/COO-{YYYYMMDD}_pipeline_operations_daily.md`
- **Documentation**: `doc/PIPELINE_DAILY_REPORTING.md`

**Reports include**:
- Success/failure counts and success rate
- Failures categorized by type (timeout, QA, translation, PDF, upload, DB)
- Retry history and status
- Stale processing detection
- Actionable recommendations

**Manual execution**:
```bash
python3 scripts/pipeline/daily_pipeline_report.py --days 1
```

### FOR Pipeline Automation (BCE-364)

The FOR pipeline runs automatically via **GitHub Actions** (every 30 minutes):

- **Workflow**: `.github/workflows/for-pipeline-cron.yml`
- **Schedule**: `*/30 * * * *` (every 30 minutes)
- **Manual Trigger**: Available via GitHub Actions UI
- **Logs**: Stored as GitHub Actions artifacts (30-day retention)

**Key Features**:
- Scans `drafts/FOR/` folder in Google Drive
- Downloads new .md reports
- Translates to 7 languages
- Generates PDFs with QA verification
- Uploads to Google Drive
- Publishes to Supabase database

**Setup Guide**: See `doc/FOR_PIPELINE_GITHUB_ACTIONS_SETUP.md`  
**Secrets Checklist**: See `.github/SECRETS_SETUP_CHECKLIST.md`

**Migration Note**: This replaces the previous Paperclip routine scheduling method (BCE-364).

## Getting Started

1. Copy `.env.example` to `.env.local` and fill in credentials
2. Install dependencies: `npm install`
3. Run migrations: `npm run db:migrate`
4. Start dev server: `npm run dev`
5. For pipeline: ensure Python 3.9+, install requirements from `scripts/pipeline/`
