# Pipeline Ops Dashboard Snapshot Runbook

**Issue**: [BCE-882](/BCE/issues/BCE-882) — 메모리 부족 환경에서 `next dev`/`next start` 없이 운영 대시보드 확인
**Owner**: CTO

## 목적

로컬 메모리 제약 때문에 Next.js dev/prod 서버를 띄울 수 없는 환경에서도 파이프라인 운영 현황을 확인할 수 있는 **정적 HTML 스냅샷**을 제공한다. API 라우트, 로그인 세션, 백엔드 서버가 전혀 필요 없다 — 파일을 더블클릭하면 브라우저가 `file://` 로 직접 연다.

## 산출물

생성기를 1회 실행하면 아래 3개 파일이 `public/snapshots/` 아래 떨어진다:

| 파일 | 설명 |
|---|---|
| `public/snapshots/pipeline-ops-dashboard.ko.html` | 한국어 대시보드 (자체 완결, file:// 열람) |
| `public/snapshots/pipeline-ops-dashboard.en.html` | 영문 대시보드 (자체 완결) |
| `public/snapshots/pipeline-ops-dashboard.snapshot.json` | 원본 JSON (요약 + 최근 실행) |

각 HTML은 외부 CDN/JS 의존성이 없는 단일 파일이다. 다크/라이트 자동 전환 CSS만 포함한다.

## 생성 방법

### 1) 사전 준비 (선택)

실제 Supabase 데이터를 사용하려면 `.env.local`에 다음 두 변수를 둔다:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service-role-key>
```

자격증명이 없으면 `src/lib/fixtures/pipeline-ops-dashboard-snapshot.json` fallback 데이터로 산출물이 만들어진다 (스키마/렌더링 검증용).

### 2) 실행

```bash
node scripts/generate-pipeline-ops-snapshot.mjs            # 최근 7일
node scripts/generate-pipeline-ops-snapshot.mjs --days 14  # 최근 14일
```

콘솔에 `source=supabase` 또는 `source=fixture`가 찍힌다.

### 3) 열람

```bash
open public/snapshots/pipeline-ops-dashboard.ko.html
open public/snapshots/pipeline-ops-dashboard.en.html
```

또는 Finder에서 더블클릭. URL은 `file:///<repo>/public/snapshots/pipeline-ops-dashboard.ko.html` 형태가 된다.

## 데이터 모델

`pipeline_runs` 테이블에서 다음 컬럼만 가져와 직렬화한다 — 추가 join/RLS 불필요:

```
id, report_type, project_slug, version, status,
source_filename, retry_count, started_at, completed_at,
languages_completed, error_detail
```

대시보드는 다음 4개 카드 + 2개 분포 + 1개 테이블을 렌더링한다:

- 요약 카드: 총 실행 / 완료 / 처리 중 / Stale(>30분) / 실패·재시도 / 성공률
- 분포: report_type별 카운트, status별 카운트
- 테이블: 최근 실행 시각·유형·프로젝트·버전·상태·재시도·언어 진행·오류 요약

## 보안 고려

- 정적 산출물은 `pipeline_runs`의 메타데이터(프로젝트 슬러그, 상태, 오류 요약)만 포함한다. 실제 보고서 본문/번역물은 직렬화하지 않는다.
- `error_detail`은 500자로 잘려 저장되며, 비밀키·토큰을 노출하지 않도록 파이프라인 단에서 마스킹된 값을 그대로 사용한다.
- 산출물은 `public/snapshots/` 에 떨어지므로 Vercel 빌드에 포함되어 외부에 노출될 수 있다 — **민감 정보가 들어갈 때는 `.gitignore`에 `public/snapshots/` 추가 또는 별도 디렉토리로 출력 경로를 변경**할 것.

## 갱신 주기

수동 실행이 기본이다. 정기 갱신이 필요하면 GitHub Actions에서 다음과 같이 추가:

```yaml
- name: Generate pipeline ops snapshot
  run: node scripts/generate-pipeline-ops-snapshot.mjs --days 14
  env:
    NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}
    SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
```

## 관련 파일

- `scripts/generate-pipeline-ops-snapshot.mjs` — 생성기
- `src/lib/fixtures/pipeline-ops-dashboard-snapshot.json` — fallback fixture
- `scripts/pipeline/pipeline_state.py` — 데이터 소스 (`pipeline_runs` 테이블 스키마 정의)
- `scripts/pipeline/daily_pipeline_report.py` — 일일 보드 보고서 (보고용, 대시보드와 별개)
