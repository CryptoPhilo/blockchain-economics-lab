# Pipeline Ops Dashboard Snapshot Runbook

**Issue**: [BCE-882](/BCE/issues/BCE-882) — 메모리 부족 환경에서 `next dev`/`next start` 없이 운영 대시보드 확인
**관련 이슈**: [BCE-1711](/BCE/issues/BCE-1711) (작동 주기 컨트롤), [BCE-1712](/BCE/issues/BCE-1712) (DB 스키마), [BCE-1713](/BCE/issues/BCE-1713) (워크플로 게이트), [BCE-1714](/BCE/issues/BCE-1714) (컨트롤 패널 UI)
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

## 슬라이드 파이프라인 작동 주기 컨트롤 (BCE-1711)

대시보드 상단의 **"Schedule control"** 패널에서 슬라이드 파이프라인의 cron 작동 주기를 admin이 직접 조절한다. 정적 HTML이지만 임베드된 JS가 Supabase JS SDK로 `pipeline_schedules` 테이블을 직접 read/write 한다 — 별도 백엔드 없음.

### 동작 모델

GitHub Actions cron(`*/5 * * * *`)은 항상 빈번하게 트리거되지만, 첫 step `Schedule gate (BCE-1711)`가 다음 조건을 평가한다:

1. `enabled=false` → 즉시 `exit 0` (정상 종료)
2. `last_run_at IS NULL` 또는 `now() - last_run_at >= interval_minutes` → 정상 실행
3. cooldown 안이면 즉시 `exit 0`
4. `workflow_dispatch`(수동) 트리거는 게이트 우회

처리 종료 시 `last_run_at = now()`, `updated_by='cron'`으로 UPDATE.

### Admin 사용 절차

1. 정적 대시보드를 연다 (`open public/snapshots/pipeline-ops-dashboard.ko.html` 또는 영문 버전)
2. **Schedule control** 패널의 이메일 입력란에 admin 이메일 입력 → **Send magic link**
3. 메일함에서 magic link 클릭 → 동일 HTML로 복귀, 세션 복원
4. 권한 배너가 **Admin** 으로 바뀌면 행이 활성화됨
   - 비-admin 이메일은 **Read-only** 표시 + 컨트롤 비활성
5. `Interval (min)` 변경 또는 `Enabled` 토글 후 **Save**
6. 저장 성공 토스트 확인 → 다음 cron tick(최대 5분 이내)부터 새 cadence 적용

### admin allowlist 관리

`admin_emails` 테이블에 row를 추가/제거한다. 1차 시드:

```sql
SELECT email, note FROM admin_emails;
-- philoskor@gmail.com | BCE Lab founder / C-level (BCE-1712)
```

추가 시 (service_role 또는 직접 SQL):

```sql
INSERT INTO admin_emails (email, note) VALUES ('newadmin@example.com', '담당자 이름 / 역할');
```

### 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| 마이크 링크 전송은 되는데 권한이 **Read-only** | 이메일이 `admin_emails`에 없음 | 위 SQL로 row 추가 |
| 패널에 "Loading…"만 표시 | Supabase URL/ANON_KEY 누락 | `.env.local` 설정 후 생성기 재실행 |
| Save 시 403 | RLS UPDATE 정책 fail (admin allowlist 외) | `admin_emails`에 본인 이메일 있는지 확인, JWT의 email claim과 대소문자 무관하게 일치하는지 확인 |
| cron이 자주/드물게 도는데 interval 변경이 안 보임 | GH Actions schedule cron은 best-effort, 실제 cadence는 `interval_minutes` 또는 GH 스케줄러 latency 중 큰 값 | `gh run list --workflow=slide-pipeline-cron.yml` 로 실제 트리거 확인 |
| 즉시 한 번 돌리고 싶음 | `workflow_dispatch`가 게이트 우회 | Actions UI > "Slide Pipeline - Automated Processing" > Run workflow |

### 검증 (BCE-1711 Stage 4 완료 시)

- ✅ DB 라이브 row 존재: `pipeline_schedules('slide-pipeline', 30, true, ...)`
- ✅ `admin_emails`에 `philoskor@gmail.com` 시드
- ✅ 워크플로 마지막 실행이 `last_run_at`을 갱신함 (e.g. `updated_by='cron'`)
- ✅ 게이트 step이 cron 트리거에서 cooldown 평가 후 `should_run` 출력
- ✅ 정적 HTML(ko/en)에 schedule panel + magic link 폼 + Supabase SDK 임베드

## 관련 파일

- `scripts/generate-pipeline-ops-snapshot.mjs` — 생성기 (Schedule control 패널 포함)
- `src/lib/fixtures/pipeline-ops-dashboard-snapshot.json` — fallback fixture
- `scripts/pipeline/pipeline_state.py` — 데이터 소스 (`pipeline_runs` 테이블 스키마 정의)
- `scripts/pipeline/daily_pipeline_report.py` — 일일 보드 보고서 (보고용, 대시보드와 별개)
- `supabase/migrations/20260430_add_pipeline_schedules.sql` — `pipeline_schedules` + `admin_emails` 스키마/RLS
- `.github/workflows/slide-pipeline-cron.yml` — DB 게이트 + last_run_at 갱신 step
