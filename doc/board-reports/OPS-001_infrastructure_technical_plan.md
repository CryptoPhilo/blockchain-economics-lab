---
report_id: OPS-001
date: 2026-04-12
type: board_report
author: COO
classification: INTERNAL - CONFIDENTIAL
title: "신규 BM 대응 — 인프라/기술 대응 계획"
references:
  - CEO-003 (MKT-002 검토 및 전사 지시)
  - MKT-002 (마케팅 계획 재수립)
  - RES-001 (신규 BM 서비스/보고서 기획)
  - STR-002 (보고서 생산 파이프라인)
  - STR-003 (파이프라인 v2)
---

# COO Board Report OPS-001
## 신규 BM 대응 — 인프라/기술 대응 계획

> **Report ID**: OPS-001 | **Date**: 2026-04-12 | **Author**: COO Division
> **Classification**: INTERNAL — CONFIDENTIAL

---

## 1. Executive Summary

CEO-003의 지시에 따라, 거래소 레퍼럴 연동형 BM 전환에 필요한 4가지 핵심 인프라를 설계했습니다. 본 보고서는 각 인프라의 기술 아키텍처, 구현 방안, 일정, 비용을 구체적으로 제시합니다.

### 대응 인프라 전체 맵

```
[CEO-003 지시]                    [COO 인프라 대응]

① 레퍼럴 추적 인프라 설계     →   섹션 2: Referral Tracking System
② 이메일 뉴스레터 발송 인프라  →   섹션 3: Email Newsletter Infrastructure
③ KR IP 레퍼럴 비노출 미들웨어 →   섹션 4: Geo-Compliance Middleware
④ Freemium 접근 제어 시스템   →   섹션 5: Content Access Control
```

**총 예상 월 운영비**: $85-150/월 (인프라만, AI API 비용 제외)
**총 구현 기간**: 3주 (병렬 작업 기준)

---

## 2. 레퍼럴 추적 인프라

### 2.1 아키텍처 설계

```
[유저 클릭]
    ↓
[bcelab.xyz/go/{exchange}?ref={user_id}]  ← 내부 리다이렉트 URL
    ↓
[Next.js API Route: /api/referral/redirect]
    │
    ├── Supabase에 클릭 이벤트 기록
    │     → referral_clicks (timestamp, user_id, exchange, source, ip_country)
    │
    ├── Geo-Compliance 체크 (섹션 4 연동)
    │     → KR IP → 일반 거래소 URL (레퍼럴 코드 제거)
    │     → Non-KR → 레퍼럴 URL로 리다이렉트
    │
    └── 302 Redirect → 거래소 레퍼럴 URL
```

### 2.2 데이터베이스 스키마

```sql
-- 거래소 레퍼럴 링크 관리
CREATE TABLE exchange_referrals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exchange TEXT NOT NULL,           -- 'binance', 'bybit', 'okx'
  referral_code TEXT NOT NULL,
  referral_url TEXT NOT NULL,
  revshare_pct NUMERIC(5,2),       -- 50.00
  status TEXT DEFAULT 'pending',    -- 'pending', 'active', 'suspended'
  applied_at TIMESTAMPTZ,
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 클릭 추적
CREATE TABLE referral_clicks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id),
  exchange TEXT NOT NULL,
  source TEXT NOT NULL,             -- 'report', 'newsletter', 'web', 'telegram'
  content_id UUID,                  -- 어떤 보고서/뉴스레터에서 클릭했는지
  content_type TEXT,                -- 'report', 'newsletter', 'trade_thesis'
  ip_country TEXT,
  geo_blocked BOOLEAN DEFAULT false,
  clicked_at TIMESTAMPTZ DEFAULT now()
);

-- 월별 수수료 정산 (거래소 대시보드에서 수동/API 입력)
CREATE TABLE referral_earnings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  exchange TEXT NOT NULL,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  referred_users INT DEFAULT 0,
  active_traders INT DEFAULT 0,
  total_volume_usd NUMERIC(18,2) DEFAULT 0,
  commission_usd NUMERIC(10,2) DEFAULT 0,
  status TEXT DEFAULT 'pending',    -- 'pending', 'confirmed', 'paid'
  created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: referral_clicks는 서비스 역할만 INSERT, admin만 SELECT
-- RLS: referral_earnings는 admin만 접근
```

### 2.3 API Route 구현

```
/api/referral/redirect?exchange={exchange}&source={source}&content_id={id}
  → 클릭 기록 + Geo 체크 + 리다이렉트

/api/referral/stats (admin only)
  → 거래소별 클릭 수, 전환 추정, 수익 현황

/api/referral/earnings (admin only)
  → 월별 수수료 정산 CRUD
```

### 2.4 관리 대시보드

기존 `/admin` 페이지에 다음 위젯 추가:

- **Referral Overview**: 거래소별 활성 유저 수, 월 클릭 수, 추정 수익
- **Click Funnel**: 콘텐츠 유형별 → 거래소별 클릭 흐름 Sankey 차트
- **Monthly Earnings**: 정산 내역 테이블 + 추이 차트
- **Top Converting Content**: 가장 높은 레퍼럴 클릭을 유도한 보고서/뉴스레터 순위

### 2.5 비용

| 항목 | 비용 | 비고 |
|------|------|------|
| Supabase (추가 테이블 3개) | $0 (기존 플랜 내) | Free tier 충분 |
| Vercel API Routes | $0 (기존 플랜 내) | Edge Function 불필요 |
| **소계** | **$0/월** | |

---

## 3. 이메일 뉴스레터 발송 인프라

### 3.1 플랫폼 선정

| 기준 | Resend | Mailgun | SendGrid |
|------|--------|---------|----------|
| 가격 (10K 메일/월) | $20/월 | $35/월 | $19.95/월 |
| 개발자 경험 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| React Email 지원 | 네이티브 | 없음 | 없음 |
| Next.js 통합 | 공식 SDK | REST API | REST API |
| 배달률 | 99%+ | 99%+ | 97%+ |
| Webhook (열람/클릭) | 지원 | 지원 | 지원 |
| 무료 티어 | 3K/월 | 5K/월 (3개월) | 100/일 |

**선정: Resend** — Next.js/React 생태계 최적 통합, React Email로 템플릿 관리, 합리적 가격.

### 3.2 아키텍처

```
[CRO 검수 승인]
    ↓
[Supabase: newsletters 테이블 status → 'approved']
    ↓
[Vercel Cron Job OR Supabase Edge Function]
    ↓
[Newsletter Send Worker]
    │
    ├── subscribers 테이블에서 활성 구독자 조회
    │     → opted_in = true, unsubscribed = false
    │
    ├── 구독자 언어별 그룹 분리
    │     → EN 그룹, KO 그룹, ... (7개 언어)
    │
    ├── React Email 템플릿 렌더링
    │     → MarketPulseTemplate / DeepDiveTemplate
    │     → 언어별 콘텐츠 삽입
    │     → 레퍼럴 CTA 삽입 (Geo-Compliance 적용)
    │
    └── Resend API → 배치 발송 (100명/배치)
         → Webhook → newsletter_events 테이블 기록
```

### 3.3 데이터베이스 스키마

```sql
-- 이메일 구독자
CREATE TABLE subscribers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  locale TEXT DEFAULT 'en',        -- 선호 언어
  source TEXT,                     -- 'website', 'report_download', 'referral'
  opted_in BOOLEAN DEFAULT true,
  unsubscribed BOOLEAN DEFAULT false,
  unsubscribed_at TIMESTAMPTZ,
  ip_country TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 뉴스레터 발행물
CREATE TABLE newsletters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL,               -- 'market_pulse', 'deep_dive'
  title_en TEXT NOT NULL,
  title_ko TEXT,
  content_md TEXT NOT NULL,         -- 마크다운 원본
  content_html TEXT,                -- 렌더링된 HTML
  status TEXT DEFAULT 'draft',      -- 'draft', 'review', 'approved', 'sent'
  scheduled_at TIMESTAMPTZ,
  sent_at TIMESTAMPTZ,
  total_recipients INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 이메일 이벤트 (Resend Webhook)
CREATE TABLE newsletter_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  newsletter_id UUID REFERENCES newsletters(id),
  subscriber_id UUID REFERENCES subscribers(id),
  event_type TEXT NOT NULL,         -- 'delivered', 'opened', 'clicked', 'bounced', 'unsubscribed'
  metadata JSONB,                   -- 클릭된 URL 등
  occurred_at TIMESTAMPTZ DEFAULT now()
);

-- 인덱스
CREATE INDEX idx_subscribers_locale ON subscribers(locale) WHERE opted_in = true AND unsubscribed = false;
CREATE INDEX idx_newsletter_events_type ON newsletter_events(event_type, occurred_at);
```

### 3.4 구독/수신거부 플로우

```
[구독]
bcelab.xyz/{locale}/subscribe
  → 이메일 입력 + 약관 동의 (GDPR Double Opt-in)
  → Resend 통해 확인 이메일 발송
  → 확인 클릭 → subscribers.opted_in = true

[수신거부]
뉴스레터 하단 "Unsubscribe" 링크
  → /api/newsletter/unsubscribe?token={jwt}
  → subscribers.unsubscribed = true, unsubscribed_at = now()
  → 즉시 확인 페이지 표시 ("구독이 해제되었습니다")

[열람 추적]
Resend Webhook → newsletter_events INSERT
  → 대시보드에서 열람률, 클릭률, 바운스율 실시간 확인
```

### 3.5 이메일 인증 설정 (SPF/DKIM/DMARC)

스팸 분류 방지를 위해 bcelab.xyz 도메인에 다음 DNS 레코드 설정 필수:

| 레코드 | 유형 | 값 |
|--------|------|-----|
| `resend._domainkey.bcelab.xyz` | CNAME | Resend 제공 DKIM 키 |
| `bcelab.xyz` | TXT (SPF) | `v=spf1 include:resend.com ~all` |
| `_dmarc.bcelab.xyz` | TXT | `v=DMARC1; p=quarantine; rua=mailto:dmarc@bcelab.xyz` |

### 3.6 비용

| 항목 | 비용 | 비고 |
|------|------|------|
| Resend Pro | $20/월 (10K 메일) | 초기 구독자 2K × 주 2회 = 16K/월 → $20 충분 |
| 도메인 DNS | $0 | 기존 Cloudflare DNS |
| **소계** | **$20/월** | 구독자 5K 도달 시 $50/월로 업그레이드 |

---

## 4. KR IP 기반 Geo-Compliance 미들웨어

### 4.1 컴플라이언스 요구사항

CEO-003 지시: "한국 IP에서 접속한 사용자에게 거래소 레퍼럴 링크를 노출하지 않을 것"

| 요구사항 | 기술 구현 |
|----------|----------|
| KR IP 사용자에게 레퍼럴 링크 비노출 | Geo IP 판별 + 조건부 렌더링 |
| 클로즈드 커뮤니티에서만 시범 운영 | TG/Discord 전용 링크 별도 관리 |
| "투자 추천", "거래소 추천" 문구 금지 | 콘텐츠 필터링 규칙 |
| 면책 고지 필수 삽입 | 자동 삽입 미들웨어 |

### 4.2 구현 방안: Vercel Edge Middleware + Supabase RPC

```
[클라이언트 요청]
    ↓
[Vercel Edge Middleware (middleware.ts)]
    │
    ├── request.headers['x-vercel-ip-country'] 확인
    │     → 'KR' → geo_context.is_restricted = true
    │     → Others → geo_context.is_restricted = false
    │
    ├── request.headers에 'x-geo-restricted' 헤더 추가
    │
    └── next()
         ↓
[Page/API Route]
    │
    ├── 보고서 페이지: Action Section 렌더링 분기
    │     → is_restricted? → "Learn More" (일반 링크)
    │     → !is_restricted? → "Trade on Binance →" (레퍼럴 링크)
    │
    ├── 뉴스레터 생성: 발송 시 구독자 ip_country 기반 분기
    │     → KR 구독자 → CTA 제거 또는 교육 콘텐츠로 대체
    │     → Non-KR → 레퍼럴 CTA 삽입
    │
    └── /api/referral/redirect: Geo 체크
          → KR → 일반 URL 리다이렉트 (코드 제거)
          → Non-KR → 레퍼럴 URL 리다이렉트
```

### 4.3 middleware.ts 설계

```typescript
// middleware.ts (Vercel Edge)
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const RESTRICTED_COUNTRIES = ['KR'] // 확장 가능

export function middleware(request: NextRequest) {
  const country = request.headers.get('x-vercel-ip-country') || 
                  request.geo?.country || ''
  
  const isRestricted = RESTRICTED_COUNTRIES.includes(country)
  
  const response = NextResponse.next()
  response.headers.set('x-geo-restricted', isRestricted ? '1' : '0')
  response.headers.set('x-geo-country', country)
  
  return response
}

export const config = {
  matcher: [
    '/api/referral/:path*',
    '/:locale/products/:path*',
    '/:locale/projects/:path*',
  ],
}
```

### 4.4 클라이언트 컴포넌트: ReferralCTA

```typescript
// components/ReferralCTA.tsx
'use client'

interface Props {
  exchange: string
  token: string
  isRestricted: boolean
}

export function ReferralCTA({ exchange, token, isRestricted }: Props) {
  if (isRestricted) {
    return (
      <span className="text-gray-500 text-sm">
        Learn more about {token} on {exchange} →
      </span>
    )
  }
  
  return (
    <a 
      href={`/api/referral/redirect?exchange=${exchange}&source=report`}
      target="_blank"
      rel="noopener noreferrer"
      className="text-indigo-400 hover:text-indigo-300"
    >
      Trade {token} on {exchange} →
    </a>
  )
}
```

### 4.5 뉴스레터 Geo 분기 로직

뉴스레터 발송 시 구독자의 `ip_country`를 확인하여 두 가지 버전을 생성:

| 버전 | 대상 | CTA 내용 |
|------|------|---------|
| Version A (Global) | Non-KR 구독자 | "Trade on Binance →" (레퍼럴 링크) |
| Version B (KR) | KR 구독자 | "Learn more about this analysis →" (보고서 링크) |

Resend의 배치 발송 시 `tags`로 분리하여 별도 버전 발송.

### 4.6 비용

| 항목 | 비용 | 비고 |
|------|------|------|
| Vercel Edge Middleware | $0 | Vercel 기본 제공 |
| Geo IP (Vercel built-in) | $0 | `x-vercel-ip-country` 헤더 |
| **소계** | **$0/월** | |

---

## 5. Freemium 콘텐츠 접근 제어 시스템

### 5.1 요구사항 (CRO RES-001 기준)

| 보고서 | 무료 공개 범위 | 유료 범위 |
|--------|---------------|----------|
| ECON | Executive Summary + Ch.1-3 (약 40%) | Ch.4-10 + 데이터 테이블 |
| MAT | Executive Summary + 종합 점수 + Ch.1-2 (약 35%) | 세부 평가 + 비교 분석 |
| FOR | Alert Level + What + Evidence (약 50%) | Risk Assessment + 시나리오 |

### 5.2 아키텍처

두 가지 접근 방식을 비교 검토했습니다.

| 방식 | 장점 | 단점 | 선택 |
|------|------|------|------|
| A: 별도 무료/유료 파일 생성 | 완전한 분리, 누출 불가 | 파이프라인 복잡도 증가 | **선택** |
| B: 단일 파일 + JS 접근 제어 | 구현 간단 | 클라이언트 우회 가능 | 기각 |

**방식 A 상세**: 파이프라인 Stage 1.5에서 보고서 .md를 두 가지 버전으로 분리

```
[Stage 1: .md 원본]
    ↓
[Stage 1.5: Freemium Splitter (NEW)]
    │
    ├── {report}_free.md    → 무료 요약판 (Executive Summary + 공개 챕터)
    │     → 웹 SEO 공개 + 뉴스레터 발송
    │
    └── {report}_full.md    → 유료 전문 (기존 그대로)
          → 구매자/구독자만 다운로드 가능
```

### 5.3 Freemium Splitter 설계

```python
# tools/freemium_splitter.py
"""
.md 보고서를 무료/유료 버전으로 분리하는 도구.
CRO RES-001의 Freemium 경계선 규격을 따름.
"""

FREEMIUM_RULES = {
    'econ': {
        'free_sections': ['executive_summary', 'ch1', 'ch2', 'ch3'],
        'free_pct': 40,
        'paywall_message': 'Full economic analysis continues with 7 more chapters...',
    },
    'maturity': {
        'free_sections': ['executive_summary', 'overall_score', 'ch1', 'ch2'],
        'free_pct': 35,
        'paywall_message': 'Detailed maturity assessment with scoring breakdown...',
    },
    'forensic': {
        'free_sections': ['alert_level', 'what_happened', 'evidence'],
        'free_pct': 50,
        'paywall_message': 'Complete risk assessment and mitigation strategies...',
    },
}
```

### 5.4 웹 표시 설계

```
[보고서 상세 페이지: /products/{slug}]
    │
    ├── 비인증 / 미구매 사용자
    │     → 무료 요약판 표시
    │     → Paywall UI: "이 보고서의 전문을 읽으려면..."
    │     → CTA: "Buy Full Report ($49)" / "Subscribe ($19/mo)"
    │     → Action Section 프리뷰 (Geo 분기 적용)
    │
    └── 구매자 / 구독자
          → 전문 표시 + 다운로드 링크
          → Action Section 전체 (레퍼럴 CTA 포함)
```

### 5.5 Supabase 스키마 변경

```sql
-- products 테이블에 Freemium 관련 컬럼 추가
ALTER TABLE products ADD COLUMN free_content_md TEXT;       -- 무료 요약 마크다운
ALTER TABLE products ADD COLUMN free_content_html TEXT;     -- 무료 요약 렌더링 HTML
ALTER TABLE products ADD COLUMN paywall_message_en TEXT;    -- Paywall 메시지 (EN)
ALTER TABLE products ADD COLUMN paywall_message_ko TEXT;    -- Paywall 메시지 (KO)

-- project_reports에 무료 파일 URL 추가
ALTER TABLE project_reports ADD COLUMN gdrive_url_free TEXT;  -- 무료 요약판 파일 URL
```

### 5.6 비용

| 항목 | 비용 | 비고 |
|------|------|------|
| Supabase 컬럼 추가 | $0 | 스키마 변경만 |
| Freemium Splitter 스크립트 | $0 | 자체 개발 |
| **소계** | **$0/월** | |

---

## 6. 면책 고지 자동 삽입 시스템

CEO-003 지시: "모든 콘텐츠에 영문 면책 고지 필수 삽입"

### 6.1 면책 고지문 (Legal Disclaimer)

```
DISCLAIMER: This content is produced by Blockchain Economics Lab (bcelab.xyz) 
for informational and educational purposes only. It does not constitute 
financial, investment, or trading advice. Cryptocurrency markets carry 
significant risk. Users are solely responsible for their own trading decisions 
and should verify exchange licensing requirements in their jurisdiction before 
opening any account or executing any trade. Past performance does not guarantee 
future results.
```

### 6.2 삽입 위치

| 콘텐츠 유형 | 삽입 위치 | 방법 |
|-------------|----------|------|
| 보고서 (.md/.pdf) | 첫 페이지 + 마지막 페이지 | 파이프라인 Stage 1 자동 삽입 |
| 웹 보고서 페이지 | 상단 배너 + 하단 고정 | React 컴포넌트 |
| 뉴스레터 | 이메일 하단 | React Email 템플릿 |
| 소셜 포스팅 | 스레드 마지막 | social-agent 규칙 |
| 웹사이트 전역 | Footer | Layout 컴포넌트 |

### 6.3 구현: DisclaimerBanner 컴포넌트

```typescript
// components/DisclaimerBanner.tsx
export function DisclaimerBanner({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <p className="text-xs text-gray-600 mt-4">
        Not financial advice. <a href="/disclaimer" className="underline">Full disclaimer</a>
      </p>
    )
  }
  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 mt-8">
      <p className="text-xs text-gray-500 leading-relaxed">
        <strong>Disclaimer:</strong> This content is produced by Blockchain Economics Lab 
        for informational and educational purposes only. It does not constitute financial, 
        investment, or trading advice. Cryptocurrency markets carry significant risk. 
        Users are solely responsible for their own trading decisions.
        <a href="/disclaimer" className="text-indigo-500 ml-1">Read full disclaimer →</a>
      </p>
    </div>
  )
}
```

---

## 7. 전체 기술 의존성 맵

```
[RES-001 요구]              [OPS-001 인프라]           [MKT-002 채널]

newsletter-agent    ──────→  Email Infra (Resend)  ←────  뉴스레터 채널
                              ↓
                    Subscriber DB + 발송 워커
                              ↓
                    Webhook → 열람/클릭 추적

보고서 Action Section ─────→  Referral Tracking    ←────  거래소 레퍼럴
                              ↓
                    Click 기록 + Redirect
                              ↓
                    Earnings 정산 대시보드

Freemium 경계선 ──────────→  Content Access Control ←──  Freemium 전략
                              ↓
                    Splitter → Free/Full 분리
                              ↓
                    Paywall UI + Auth 체크

컴플라이언스 ─────────────→  Geo-Compliance MW     ←──  규제 대응
                              ↓
                    IP 판별 → CTA 분기
                              ↓
                    면책 고지 자동 삽입
```

---

## 8. 구현 일정

### 8.1 Week 1 (즉시 착수)

| 작업 | 우선순위 | 예상 공수 | 의존성 |
|------|---------|----------|--------|
| Supabase 스키마 생성 (referral + subscriber + newsletter) | P0 | 0.5일 | 없음 |
| Resend 계정 생성 + DNS 설정 (SPF/DKIM/DMARC) | P0 | 0.5일 | 없음 |
| middleware.ts Geo-Compliance 구현 | P0 | 1일 | 없음 |
| DisclaimerBanner 컴포넌트 + 전역 삽입 | P0 | 0.5일 | 없음 |
| /api/referral/redirect API Route | P0 | 1일 | 스키마 생성 |

### 8.2 Week 2

| 작업 | 우선순위 | 예상 공수 | 의존성 |
|------|---------|----------|--------|
| /subscribe 페이지 (Double Opt-in 플로우) | P0 | 1일 | Resend 설정 |
| /api/newsletter/unsubscribe API | P0 | 0.5일 | 구독자 DB |
| React Email 템플릿 (MarketPulse + DeepDive) | P0 | 2일 | Resend SDK |
| 뉴스레터 발송 워커 (배치 + 언어별 분기) | P1 | 1.5일 | 템플릿 |
| ReferralCTA 컴포넌트 (Geo 분기) | P1 | 0.5일 | middleware.ts |

### 8.3 Week 3

| 작업 | 우선순위 | 예상 공수 | 의존성 |
|------|---------|----------|--------|
| Freemium Splitter (tools/freemium_splitter.py) | P1 | 1일 | CRO 경계선 확정 |
| Paywall UI 컴포넌트 | P1 | 1일 | Freemium Splitter |
| products 테이블 free_content 컬럼 + 데이터 입력 | P1 | 0.5일 | Splitter |
| Referral 관리 대시보드 (admin) | P2 | 2일 | referral_clicks |
| Resend Webhook → newsletter_events 연동 | P2 | 0.5일 | 발송 워커 |
| 전체 E2E 테스트 | P0 | 1일 | 전 시스템 |

---

## 9. 비용 총정리

### 9.1 월간 인프라 비용

| 인프라 | 월 비용 | Phase |
|--------|---------|-------|
| Resend (이메일) | $20 | Phase 1 |
| Supabase (기존 플랜) | $0 추가 | - |
| Vercel (기존 플랜) | $0 추가 | - |
| Cloudflare DNS | $0 | - |
| **합계** | **$20/월** | |

### 9.2 구독자 성장에 따른 비용 전망

| 구독자 수 | 월 이메일 수 (주 2회) | Resend 비용 | 비고 |
|-----------|---------------------|-------------|------|
| 1,000 | 8,000 | $20/월 | Free tier 가능 |
| 2,000 | 16,000 | $20/월 | Pro 플랜 |
| 5,000 | 40,000 | $50/월 | Business 플랜 |
| 10,000 | 80,000 | $100/월 | Business 플랜 |
| 50,000 | 400,000 | $400/월 | Enterprise 협의 |

---

## 10. Conclusion

4가지 핵심 인프라를 3주 내 구축 가능하며, 초기 월 운영비는 $20에 불과합니다. Vercel Edge의 내장 Geo IP와 Resend의 React Email 통합을 활용하면 복잡한 Geo-Compliance와 다국어 뉴스레터를 최소 비용으로 운영할 수 있습니다.

가장 시급한 것은 Week 1의 Supabase 스키마 생성과 Resend DNS 설정입니다. 이 두 가지가 완료되면 나머지 인프라가 순차적으로 구축 가능합니다. CRO의 newsletter-agent 구현과 병행하여 Week 3 말까지 첫 뉴스레터 발행이 가능한 기술 기반을 완성하겠습니다.

---

*Prepared by COO Division, Blockchain Economics Lab*
*bcelab.xyz | 2026-04-12*
