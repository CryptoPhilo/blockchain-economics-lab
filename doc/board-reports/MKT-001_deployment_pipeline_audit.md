---
report_id: MKT-001
date: 2026-04-10
type: board_report
author: CMO
classification: INTERNAL - CONFIDENTIAL
title: "3종 보고서 다국어 웹 배포 파이프라인 종합 점검"
---

# CMO Board Report MKT-001
## 3종 보고서 × 7개 언어 — 웹사이트 배포 파이프라인 종합 점검

> **Report ID**: MKT-001 | **Date**: 2026-04-10 | **Author**: CMO Division
> **Classification**: INTERNAL — CONFIDENTIAL

---

## 1. Executive Summary

3종 보고서(ECON/MAT/FOR)를 7개 언어(EN/KO/FR/ES/DE/JA/ZH)로 웹사이트(bcelab.xyz)에 노출시키는 전체 배포 체인을 점검했습니다.

### 한 줄 결론

> **생산 파이프라인(Stage 0→2)은 75% 완성이나, 웹 배포 파이프라인(Stage 3→고객 화면)은 20% 수준으로 심각한 갭 존재.**

### 핵심 수치

| 지표 | 현재값 | 목표값 | 갭 |
|------|--------|--------|-----|
| 생산된 보고서 (DB 등록) | 5건 (EN only) | — | — |
| 번역 완료 보고서 | 0건 | 5 × 6 = 30건 | **30건** |
| products 테이블 등록 | **0건** | 5건+ | **5건** |
| 프로젝트 열람 페이지 | **미구현** | `/projects` | **CRITICAL** |
| 보고서 다운로드 API | **미구현** | `/api/reports/[id]` | **CRITICAL** |
| Dashboard 보기/다운로드 | **버튼만 존재** | 실제 동작 | **HIGH** |
| Edge Functions | **0개** | 필요 시 | LOW |

---

## 2. 현재 인프라 현황

### 2.1 기술 스택

| 계층 | 기술 | 상태 |
|------|------|------|
| 프론트엔드 | Next.js 16.2.2 (App Router) | ✅ 배포 중 |
| 호스팅 | Vercel (ICN1 리전) | ✅ 활성 |
| 데이터베이스 | Supabase Postgres 17 (ap-northeast-2) | ✅ ACTIVE_HEALTHY |
| 인증 | Supabase Auth | ✅ 구성 완료 |
| 결제 (법정화폐) | Stripe (테스트 키) | ⚠️ 테스트 모드 |
| 결제 (암호화폐) | ethers.js + CoinGecko | ✅ 주소 설정 완료 |
| i18n | next-intl (7개 언어) | ✅ UI 번역 완료 |
| 파일 저장소 | Google Drive API | ✅ 연동 구현 |
| CI/CD | GitHub Actions (4 workflows) | ✅ 구성 완료 |
| 도메인 | bcelab.xyz | ✅ 설정 완료 |

### 2.2 Supabase 데이터 현황

| 테이블 | 레코드 수 | 비고 |
|--------|-----------|------|
| tracked_projects | **3** | Heyelsaai, Tokenx, Uniswap |
| project_reports | **5** | 전부 EN only, GDrive URL 보유 |
| report_versions | **2** | Heyelsaai ECON v1→v2 이력 |
| categories | **5** | 온체인/토큰/DeFi/매크로/특별 |
| products | **0** | ⛔ 비어 있음 — 판매 불가 |
| orders | **0** | — |
| profiles | **0** | — |
| user_library | **0** | — |

### 2.3 등록된 보고서 상세

| 프로젝트 | 보고서 유형 | 버전 | 상태 | 언어 | GDrive |
|----------|------------|------|------|------|--------|
| Heyelsaai | ECON | v2 | published | EN | ✅ |
| Heyelsaai | MAT | v1 | published | EN | ✅ |
| Heyelsaai | FOR | v1 | published | EN | ✅ |
| Tokenx | FOR | v1 | published | EN | ✅ |
| Uniswap | MAT | v1 | published | EN | ✅ |

**공통 문제**: 모든 보고서의 `translation_status`가 7개 언어 전부 `"pending"`, `file_urls_by_lang`는 `{}`, `gdrive_urls_by_lang`에는 EN만 존재.

---

## 3. 배포 파이프라인 전체 흐름도 및 갭 분석

```
[Stage 0]       [Stage 1]       [Stage 1.5]      [Stage 2]        [Stage 3]        [Web Layer]
Data Collect → EN .md Master → Translation → PDF/Slide Gen → GDrive Upload → 웹사이트 노출
   ✅              ✅            ⚠️ 75%          ✅ 3종 OK       ✅ GDrive OK     ⛔ 20%
                                (stub만 테스트)   (EN 검증 완료)   (EN만 등록)
```

### 단계별 상세 점검

#### ✅ Stage 0: Data Collection — PASS
CoinGecko + on-chain API → Supabase `data.*` 테이블 저장. `collection_runs` 테이블로 수집 이력 추적.

#### ✅ Stage 1: .md Master Text — PASS
gen_text_econ/mat/for.py → EN .md (YAML frontmatter + 10장 구조). BTC ECON A+ 레퍼런스 49KB 생산 검증 완료.

#### ⚠️ Stage 1.5: Translation — 75% (코드 완성, 실전 미검증)
translate_md.py 727 LOC 구현 완료. stub 백엔드로 7개 언어 테스트 PASS. **Claude API 연동 미완** (API 키 미설정).

#### ✅ Stage 2: PDF/Slide Generation — PASS
3종 × 7개 언어 슬라이드 PDF 생성 검증 완료 (BTC ECON 기준). Plotly 차트, Playwright 렌더링 정상.

#### ✅ Stage 3: GDrive Upload + DB Registration — PASS (EN only)
gdrive_storage.py → GDrive 업로드 → Supabase project_reports.gdrive_url 등록. 5건 EN 보고서 등록 확인. **번역본 업로드 프로세스 미구현.**

#### ⛔ Web Layer: 웹사이트 노출 — **CRITICAL GAP (20%)**
이하 섹션 4에서 상세 분석.

---

## 4. 웹 배포 레이어 갭 분석 (CRITICAL)

### 4.1 기존 구현 현황 (What Works)

| 기능 | 경로 | 상태 |
|------|------|------|
| 홈페이지 | `/[locale]` | ✅ Hero + Featured 4개 + 카테고리 |
| 상품 목록 | `/[locale]/products` | ✅ 필터(카테고리/타입) + 검색 |
| 상품 상세 | `/[locale]/products/[slug]` | ✅ 설명 + 체크아웃 버튼 |
| 인증 | `/[locale]/auth` | ✅ 이메일/비밀번호 |
| 대시보드 | `/[locale]/dashboard` | ⚠️ UI만 (기능 미연결) |
| UI 다국어 | 7개 언어 메시지 | ✅ next-intl |
| Stripe 결제 | `/api/checkout` | ✅ webhook 포함 |
| 암호화폐 결제 | `/api/crypto` | ✅ BTC/ETH/USDT/USDC |

### 4.2 누락된 CRITICAL 기능

#### GAP-1: 프로젝트 브라우징 페이지 미구현 ⛔

**현재**: 고객이 "Uniswap", "Heyelsaai" 등 프로젝트별로 보고서를 탐색할 방법이 **전혀 없음**.

**필요한 것**:
- `/[locale]/projects` — tracked_projects 목록 (이름, 심볼, 카테고리, 성숙도 점수)
- `/[locale]/projects/[slug]` — 프로젝트 상세 + 해당 프로젝트의 ECON/MAT/FOR 보고서 탭
- 각 보고서에 언어별 가용 상태 배지 표시 ("EN ✓ KO ✓ JA ⏳")

**영향**: 핵심 상품을 고객에게 보여줄 수 없음 → **매출 불가능**

#### GAP-2: products 테이블 비어 있음 ⛔

**현재**: `products` 테이블 0건. `project_reports`에 5건 있지만 `product_id`가 NULL.

**결과**: `/[locale]/products` 페이지에 아무것도 표시되지 않음. 고객이 구매할 상품이 없음.

**필요한 것**: `project_reports` → `products` 자동 등록 파이프라인, 또는 보고서를 직접 판매하는 새 경로.

#### GAP-3: 보고서 열람/다운로드 API 미구현 ⛔

**현재**: Dashboard에 "보기", "다운로드" 버튼이 있지만 `onClick` 핸들러 없음. `/api/reports/[id]` 엔드포인트 미존재.

**필요한 것**:
- `GET /api/reports/[id]?lang={locale}` — 권한 확인 후 GDrive URL redirect 또는 파일 프록시
- `user_library` 테이블 기반 접근 제어
- 현재 locale에 맞는 언어 파일 자동 선택 (fallback to EN)

#### GAP-4: 다국어 보고서 파일 라우팅 미구현 ⛔

**현재**: `project_reports.file_urls_by_lang`는 `{}`, `gdrive_urls_by_lang`에는 EN만 존재.

**필요한 것**:
- Stage 3에서 번역본도 GDrive 업로드 + DB 등록
- 프론트엔드에서 locale 기반 자동 파일 선택
- "이 보고서는 EN, KO에서 이용 가능합니다" 표시

#### GAP-5: 보고서 유형(ECON/MAT/FOR) 필터 미노출 ⚠️

**현재**: 상품 필터에 `category`(온체인/토큰 등)와 `type`(single/subscription/bundle)만 있음. **보고서 유형(ECON/MAT/FOR) 구분 없음.**

**결과**: 10개 ECON + 10개 MAT 보고서가 섞여서 표시됨. 고객이 원하는 유형을 찾을 수 없음.

### 4.3 갭 심각도 매트릭스

| GAP | 심각도 | 매출 영향 | 구현 난이도 | 예상 기간 |
|-----|--------|-----------|------------|-----------|
| GAP-1 | ⛔ CRITICAL | 매출 불가 | MEDIUM | 3-5일 |
| GAP-2 | ⛔ CRITICAL | 매출 불가 | LOW | 1일 |
| GAP-3 | ⛔ CRITICAL | 구매 후 이용 불가 | MEDIUM | 2-3일 |
| GAP-4 | ⛔ CRITICAL | 다국어 서비스 불가 | MEDIUM | 2-3일 |
| GAP-5 | ⚠️ HIGH | UX 저하 | LOW | 1일 |

---

## 5. 고객 여정 분석 (As-Is vs To-Be)

### 5.1 As-Is: 현재 고객 여정 (BROKEN)

```
고객 방문 → /en (홈페이지, Featured 0개) → /en/products (상품 0건) → ❌ 이탈
```

현재 고객이 보고서를 발견하고 구매하여 열람하는 경로가 **완전히 끊겨 있음**.

### 5.2 To-Be: 목표 고객 여정

```
고객 방문 → /en (홈페이지, Featured 프로젝트 + 최신 보고서)
    ↓
/en/projects (프로젝트 목록: Uniswap, Heyelsaai...)
    ↓
/en/projects/uniswap (MAT 보고서 v1 — EN ✓ KO ✓)
    ↓
체크아웃 (Stripe or Crypto) → 결제 완료
    ↓
/en/dashboard (내 보고서 → 보기/다운로드 → 언어 선택)
    ↓
PDF 열람 / 다운로드 (locale 기반 자동 선택)
```

---

## 6. 다국어 배포 파이프라인 상세 분석

### 6.1 UI 레이어: ✅ 완성

| 항목 | 구현 | 비고 |
|------|------|------|
| next-intl 설정 | ✅ | 7개 locale |
| 메시지 파일 | ✅ | en/ko/fr/es/de/ja/zh.json |
| Middleware locale 강제 | ✅ | always-prefix 전략 |
| 상품 다국어 필드 | ✅ | title_{lang}, description_{lang} |
| getLocalizedField() 헬퍼 | ✅ | 컴포넌트에서 사용 중 |
| Header 언어 선택기 | ✅ | 7개 언어 드롭다운 |

### 6.2 콘텐츠 레이어: ⛔ 미완성

| 항목 | 구현 | 비고 |
|------|------|------|
| 보고서 EN 생산 | ✅ | 5건 GDrive 등록 |
| 보고서 번역 (KO~ZH) | ⛔ | 0건 — translate_md.py stub만 |
| 번역본 GDrive 업로드 | ⛔ | 미구현 |
| file_urls_by_lang 등록 | ⛔ | 전부 `{}` |
| translation_status 업데이트 | ⛔ | 전부 `"pending"` |
| 프론트 언어별 파일 선택 | ⛔ | 미구현 |

### 6.3 언어별 고객 경험 시뮬레이션

| 언어 | UI | 상품 제목 | 보고서 파일 | 최종 판정 |
|------|-----|----------|------------|-----------|
| EN | ✅ | ✅ (title_en) | ✅ (GDrive EN) | ⚠️ 파일 라우팅만 구현 필요 |
| KO | ✅ | ⚠️ (title_ko NULL) | ⛔ | 콘텐츠 전체 미완 |
| FR | ✅ | ⛔ (NULL) | ⛔ | 콘텐츠 전체 미완 |
| ES | ✅ | ⛔ (NULL) | ⛔ | 콘텐츠 전체 미완 |
| DE | ✅ | ⛔ (NULL) | ⛔ | 콘텐츠 전체 미완 |
| JA | ✅ | ⛔ (NULL) | ⛔ | 콘텐츠 전체 미완 |
| ZH | ✅ | ⛔ (NULL) | ⛔ | 콘텐츠 전체 미완 |

---

## 7. CI/CD 및 배포 자동화 점검

### 7.1 GitHub Actions (4 workflows)

| Workflow | 트리거 | 기능 | 상태 |
|----------|--------|------|------|
| ci.yml | push → main/develop | Lint + TypeCheck + Test + Build | ✅ |
| deploy-production.yml | push → main | Vercel production deploy | ✅ |
| db-migration.yml | push → supabase/migrations/** | Supabase CLI db push | ✅ |
| agent-heartbeat.yml | cron 00:00 UTC (09:00 KST) | 에이전트 일일 점검 | ✅ |

### 7.2 Vercel Cron

| 경로 | 스케줄 | 용도 |
|------|--------|------|
| /api/cron/heartbeat | 매일 00:00 UTC | 시스템 상태 체크 |

### 7.3 자동 배포 파이프라인 갭

| 누락 항목 | 설명 | 우선순위 |
|-----------|------|----------|
| 보고서 생산 → products 자동 등록 | published된 project_report → products INSERT | P0 |
| 번역 완료 → translation_status 업데이트 | Stage 1.5 완료 후 DB 자동 반영 | P0 |
| 번역본 → GDrive 업로드 자동화 | Stage 3에 다국어 분기 추가 | P1 |
| 보고서 published → 프론트 캐시 무효화 | ISR revalidation 또는 on-demand | P2 |

---

## 8. CMO 권고: 4주 실행 로드맵

### Phase 1: 최소 판매 가능 상태 달성 (Week 1) — 🔴 최우선

| 작업 | 담당 | 산출물 |
|------|------|--------|
| project_reports → products 등록 스크립트 | COO/Data Eng | products 테이블 5건+ |
| `/[locale]/projects` 목록 페이지 | COO/Frontend | Next.js 페이지 |
| `/[locale]/projects/[slug]` 상세 + 3종 탭 | COO/Frontend | ECON/MAT/FOR 탭 UI |
| `GET /api/reports/[id]?lang=` 다운로드 API | COO/Backend | 권한 확인 + GDrive redirect |
| Dashboard 보기/다운로드 버튼 연결 | COO/Frontend | onClick → API 호출 |

**Week 1 목표**: EN 보고서 5건을 고객이 발견 → 구매 → 다운로드할 수 있는 최소 경로 확보.

### Phase 2: 다국어 콘텐츠 파이프라인 완성 (Week 2)

| 작업 | 담당 | 산출물 |
|------|------|--------|
| Claude API 번역 백엔드 연동 | CRO/Pipeline | translate_md.py → claude backend |
| 5건 보고서 × 6개 언어 번역 실행 | CRO/Pipeline | 30개 번역 .md |
| 번역본 PDF/Slide 생성 | CRO/Pipeline | 30개 PDF + 30개 Slide |
| 번역본 GDrive 업로드 + DB 등록 | COO/Pipeline | file_urls_by_lang, translation_status |
| products.title_{lang} 다국어 등록 | COO/Data Eng | 7개 언어 상품 메타데이터 |

**Week 2 목표**: 7개 언어 콘텐츠가 실제로 GDrive + DB에 존재.

### Phase 3: 다국어 UX 완성 (Week 3)

| 작업 | 담당 | 산출물 |
|------|------|--------|
| 프로젝트 상세에 언어 가용 배지 | CMO/Frontend | "EN ✓ KO ✓ JA ⏳" |
| 보고서 유형 필터 (ECON/MAT/FOR) | CMO/Frontend | ProductFilter 확장 |
| locale 기반 자동 파일 선택 + EN fallback | COO/Backend | API lang 파라미터 처리 |
| 홈페이지 Featured 보고서 자동 노출 | CMO/Frontend | 최신 published 보고서 |
| 번역 진행률 대시보드 (admin) | COO/Internal | 관리 도구 |

**Week 3 목표**: KO 고객이 KO 보고서를, JA 고객이 JA 보고서를 자연스럽게 받아볼 수 있음.

### Phase 4: QA 및 론칭 (Week 4)

| 작업 | 담당 | 산출물 |
|------|------|--------|
| 7개 언어 E2E 고객 여정 테스트 | QA/CMO | 테스트 보고서 |
| Stripe 라이브 키 전환 | COO | 실제 결제 |
| 암호화폐 결제 E2E 테스트 | COO | BTC/ETH 실거래 |
| PDF 렌더링 언어별 품질 확인 | CRO | CJK 폰트 등 |
| SEO 메타태그 + OG 이미지 | CMO | 소셜 공유 최적화 |
| 론칭 공지 및 마케팅 | CMO | bcelab.xyz 오픈 |

---

## 9. 리스크 및 의존성

| 리스크 | 영향 | 완화 방안 |
|--------|------|-----------|
| Claude API 키 미설정 | 번역 불가 → 다국어 론칭 지연 | **즉시 API 키 발급** (P0) |
| GDrive 공유 권한 | 다운로드 링크 403 에러 | 서비스 계정 공유 설정 확인 |
| Stripe 라이브 키 미전환 | 실제 결제 불가 | Week 4 전환 일정 확정 |
| products 0건 | 상품 페이지 빈 화면 | Week 1 자동 등록 스크립트 |
| project_reports.title_{lang} NULL | 상품 제목 빈칸 | 번역 시 DB 동시 업데이트 |
| Next.js ISR 캐시 | 새 보고서 노출 지연 | on-demand revalidation API |

---

## 10. KPI 및 성공 지표

### STR-001 Q2 2026 목표 대비 현황

| KPI | 목표 | 현재 | 달성률 | 판정 |
|-----|------|------|--------|------|
| 월간 보고서 발행 | 4-6건 | 5건 (EN) | 83% | ⚠️ EN only |
| 가입자 수 | 50명 | 0명 | 0% | ⛔ 판매 경로 미존재 |
| 월 방문자 | 5,000명 | 측정 불가 | 0% | ⛔ Analytics 미설정 |
| 암호화폐 결제 성공률 | >90% | 테스트 미실행 | — | ⚠️ |
| 시스템 가동률 | >99.5% | 추정 99%+ | — | ✅ |

### CMO 추가 KPI 제안

| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| 언어별 보고서 커버리지 | 100% (7/7) | `translation_status` != "pending" |
| 발견→구매 전환율 | >5% | products 조회 → checkout 비율 |
| 보고서 다운로드 수 | >100/월 | user_library.download_count |
| 언어별 사용 비율 | 트래킹 | locale 기반 API 호출 로그 |

---

## 11. Conclusion

현재 배포 파이프라인은 **"보고서는 만들 수 있지만, 고객에게 보여줄 수 없는"** 상태입니다.

생산 인프라(파이프라인, GDrive, DB 스키마)와 결제 인프라(Stripe + Crypto)는 잘 갖춰져 있으나, 이 둘을 잇는 **"발견 → 구매 → 열람"** 의 고객 여정이 구현되지 않았습니다. 구체적으로는 프로젝트 브라우징 페이지 미구현, products 테이블 비어 있음, 다운로드 API 미존재, 다국어 파일 라우팅 미구현의 4가지 CRITICAL 갭이 있습니다.

CMO는 **Week 1에 EN 최소 판매 경로 확보, Week 2에 다국어 콘텐츠 투입, Week 3에 다국어 UX 완성, Week 4에 론칭**의 4주 실행 로드맵을 권고합니다. 특히 Week 1의 프로젝트 페이지 + 다운로드 API가 가장 시급하며, 이것만 완성되면 EN 보고서 5건의 즉시 판매가 가능합니다.

---

### 부록 A: 파일 인벤토리

**웹앱 핵심 파일**:
- `src/app/[locale]/page.tsx` — 홈페이지
- `src/app/[locale]/products/page.tsx` — 상품 목록
- `src/app/[locale]/products/[slug]/page.tsx` — 상품 상세
- `src/app/[locale]/dashboard/page.tsx` — 대시보드
- `src/lib/types.ts` — 전체 타입 정의 (TrackedProject, ProjectReport, 3종 enum)
- `src/middleware.ts` — locale 라우팅
- `src/i18n/config.ts` — 7개 언어 설정

**파이프라인 핵심 파일**:
- `scripts/pipeline/orchestrator.py` — 5단계 파이프라인
- `scripts/pipeline/translate_md.py` — 번역 모듈 (NEW)
- `scripts/pipeline/gdrive_storage.py` — GDrive 업로드
- `scripts/pipeline/gen_slide_html_{econ,mat,for}.py` — 슬라이드 생성
- `scripts/pipeline/gen_text_{econ,mat,for}.py` — .md 텍스트 생성

**인프라 파일**:
- `vercel.json` — Vercel 설정 (ICN1)
- `.github/workflows/` — CI/CD 4 workflows
- `supabase/migrations/` — DB 마이그레이션

### 부록 B: Supabase 스키마 관계도

```
tracked_projects (3)
    ├── project_reports (5) ──→ products (0) ⛔
    │       └── report_versions (2)
    ├── forensic_monitoring_logs (0)
    ├── project_subscription_items (0)
    │       └── project_subscriptions (0)
    └── data.* (price_daily, onchain_daily, whale_transfers...)

products (0)
    ├── order_items → orders → profiles
    ├── bundle_items
    ├── subscriptions
    └── user_library
```

---

*Prepared by CMO Division, Blockchain Economics Lab*
*bcelab.xyz | 2026-04-10*
