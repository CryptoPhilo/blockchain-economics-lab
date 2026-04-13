---
report_id: RES-001
date: 2026-04-12
type: board_report
author: CRO
classification: INTERNAL - CONFIDENTIAL
title: "신규 BM 대응 — 서비스/보고서 라인업 재설계"
references:
  - CEO-003 (MKT-002 검토 및 전사 지시)
  - MKT-002 (마케팅 계획 재수립)
  - STR-002 (보고서 생산 파이프라인)
  - STR-003 (파이프라인 v2)
---

# CRO Board Report RES-001
## 신규 BM 대응 — 서비스/보고서 라인업 재설계

> **Report ID**: RES-001 | **Date**: 2026-04-12 | **Author**: CRO Division
> **Classification**: INTERNAL — CONFIDENTIAL

---

## 1. Executive Summary

CEO-003의 지시에 따라, 거래소 레퍼럴 연동형 BM에 최적화된 콘텐츠/서비스 라인업을 재설계했습니다. 핵심 변화는 기존 3종 보고서(ECON/MAT/FOR)에 **4종의 신규 콘텐츠 유형**을 추가하여, 고객 퍼널의 모든 단계를 커버하는 7종 콘텐츠 체계를 구축하는 것입니다.

### 콘텐츠 퍼널 전체 설계

```
[유입]              [신뢰 구축]           [전환]              [유지/확대]
                                    
Market Pulse     →  Report Summary  →  Full Report      →  Project Sub
(뉴스레터)          (무료 요약)        (유료 보고서)       (프로젝트 구독)
                                    
Forensic Alert   →  Deep Dive       →  거래소 가입       →  활성 거래
(실시간 경보)       (심층 프리뷰)      (레퍼럴 전환)       (RevShare 수익)
                                    
Trade Signal     →                                      →  
(거래 시그널)                                             
```

---

## 2. 7종 콘텐츠 체계

### 2.1 기존 3종 (유지 + 역할 재정의)

기존 ECON/MAT/FOR 보고서는 유지하되, 퍼널에서의 역할을 재정의합니다.

| 유형 | 기존 역할 | 신규 역할 | 가격 | 주기 |
|------|----------|----------|------|------|
| **ECON** (경제 설계) | 판매 상품 | **신뢰 구축 + 유료 전환** 핵심 도구 | $49 | 6개월 |
| **MAT** (성숙도 평가) | 판매 상품 | **투자 의사결정 지원** → 거래 전환 유도 | $39 | 3개월 |
| **FOR** (포렌식 리스크) | 판매 상품 | **긴급성 + FOMO** → 즉시 거래 전환 | $29 | 이벤트 |

**변경 사항**: 각 보고서 말미에 **"Action Section"** 추가 — 분석 결론에 기반한 구체적 거래 시나리오를 제시하고, 해당 거래소 링크를 자연스럽게 포함.

### 2.2 신규 4종 콘텐츠

#### NEW-1: Weekly Market Pulse (주간 시장 요약)

| 항목 | 내용 |
|------|------|
| **유형** | 이메일 뉴스레터 |
| **빈도** | 주 1회 (월요일 발행) |
| **분량** | 1,500-2,000 단어 |
| **가격** | **무료** (이메일 구독) |
| **퍼널 역할** | 유입 → 신뢰 구축 |
| **레퍼럴 위치** | 각 프로젝트 언급 시 "Trade on [Exchange] →" CTA |

**콘텐츠 구조:**

1. **Market Overview** (300 단어) — BTC/ETH 주간 동향, 총 시총, 주요 매크로 이벤트
2. **Tracked Projects Update** (500 단어) — BCE Lab 추적 프로젝트 3-5개의 주간 변동
3. **Forensic Radar** (300 단어) — 이상 징후 감지 프로젝트 경보
4. **New Discovery** (200 단어) — 신규 발굴 프로젝트 1개 소개
5. **Data Table** (표) — 추적 프로젝트 성숙도 점수, 가격 변동, 거래량 변화
6. **Action Items** — 거래소 레퍼럴 CTA 2-3개

**AI 자동 생성 워크플로우:**
```
Supabase data.* → data-engineer 수집 → newsletter-agent 요약 생성 → CRO 검수 (15분) → 발행
```

#### NEW-2: Deep Dive Preview (심층 프리뷰)

| 항목 | 내용 |
|------|------|
| **유형** | 이메일 뉴스레터 + 웹 공개 |
| **빈도** | 주 1회 (목요일 발행) |
| **분량** | 2,000-3,000 단어 |
| **가격** | **무료** (이메일 구독 + 웹 SEO) |
| **퍼널 역할** | 신뢰 구축 → 유료 전환 |
| **레퍼럴 위치** | 분석 결론부에 자연 삽입 |

**콘텐츠 구조:**

이것은 최근 발행된 유료 보고서(ECON/MAT/FOR)의 **핵심 발견사항 + 첫 3개 챕터**를 공개하는 형식입니다.

1. **Executive Summary** (전문 공개)
2. **Key Findings Top 5** (전문 공개)
3. **Chapter 1-3 발췌** (전문 공개)
4. **"Full Analysis continues..."** → 유료 벽 (Paywall)
5. **Data Preview** — 핵심 차트/테이블 1-2개 (워터마크 포함)
6. **Action Section** — "이 분석에 기반한 포지션 →" (거래소 레퍼럴)

#### NEW-3: Forensic Alert (포렌식 실시간 경보)

| 항목 | 내용 |
|------|------|
| **유형** | 이메일 + Telegram + 웹 푸시 |
| **빈도** | 이벤트 기반 (주 0-5회) |
| **분량** | 300-500 단어 |
| **가격** | **프로젝트 구독자 전용** |
| **퍼널 역할** | 구독 유지 + 긴급 거래 전환 |
| **레퍼럴 위치** | 경보 직후 "Hedge/Trade Now →" CTA |

**트리거 조건 (STR-002 기준):**
- 24시간 가격 변동 ±15% 이상
- 거래량 300% 이상 급등
- 고래 이동 전체 유통량의 1% 이상
- 내부자 거래 의심 패턴 감지

**콘텐츠 구조:**

1. **Alert Level** — 🟡 CAUTION / 🟠 WARNING / 🔴 CRITICAL
2. **What Happened** — 이벤트 요약 (2-3 문장)
3. **On-Chain Evidence** — 트랜잭션 해시, 지갑 주소, 차트
4. **Risk Assessment** — CRO 분석 의견
5. **Suggested Actions** — 방어 전략 + 거래소 CTA

**AI 자동 생성 워크플로우:**
```
forensic_monitoring_logs → 임계값 초과 감지 → onchain-analyst 경보 생성 → CRO 즉시 승인 → 발송
```

#### NEW-4: Trade Thesis (거래 시나리오)

| 항목 | 내용 |
|------|------|
| **유형** | 웹 + 뉴스레터 부록 |
| **빈도** | 월 2-4회 |
| **분량** | 800-1,200 단어 |
| **가격** | **무료** (레퍼럴 전환 최적화) |
| **퍼널 역할** | **직접적 거래 전환** |
| **레퍼럴 위치** | 시나리오 전체가 거래 행동 유도 → CTA 필수 |

**콘텐츠 구조:**

기존 보고서의 분석 결론을 **구체적 거래 시나리오**로 변환합니다.

1. **Thesis** — 한 문장 핵심 주장 (예: "UNI is undervalued vs. TVL growth trajectory")
2. **Evidence** — 보고서에서 추출한 핵심 데이터 3-5개
3. **Scenario Analysis** — Bull/Base/Bear 3가지 시나리오
4. **Entry/Exit Framework** — 가격대별 진입/청산 기준 (투자 조언 아님, 교육 목적)
5. **Risk Factors** — FOR 보고서 연계 리스크
6. **Execute** — "Open Position →" (거래소 레퍼럴)

**주의**: 면책 고지 필수. "This is not financial advice" 문구 반드시 포함.

---

## 3. Freemium 경계선 설계

CEO 지시에 따라 무료/유료 경계선을 명확히 정의합니다.

### 3.1 보고서별 무료 공개 범위

| 보고서 | 무료 공개 | 유료 벽 뒤 | 근거 |
|--------|----------|-----------|------|
| **ECON** | Executive Summary + Ch.1-3 (약 40%) | Ch.4-10 + 전체 데이터 테이블 | 핵심 분석은 후반부 |
| **MAT** | Executive Summary + 종합 점수 + Ch.1-2 (약 35%) | 세부 평가 + 비교 분석 + 권고 | 점수로 호기심 유발 |
| **FOR** | Alert Level + What Happened + Evidence (약 50%) | 전체 Risk Assessment + 시나리오 | 긴급성으로 전환 |

### 3.2 품질 기준

**무료 콘텐츠 기준 (CRO 품질 게이트):**

- 독자적으로도 가치가 있어야 함 — "읽고 나서 시간 낭비라는 느낌이 들면 안 됨"
- 구체적 데이터/수치를 최소 5개 이상 포함
- 유료 전문에 대한 호기심을 자연스럽게 유발하는 "cliffhanger" 포함
- 레퍼럴 CTA가 분석 흐름에 자연스럽게 통합 (강매 느낌 금지)

**유료 콘텐츠 기준:**

- 기존 QA-004 품질 기준 유지 (6K+ 단어, 10장, 5+ 테이블, 10+ 소스)
- 무료에서 다루지 않은 **독점 분석** 반드시 포함
- "Action Section" 추가 — 거래 시나리오 + 거래소 CTA

---

## 4. 시장 사이클별 생산 전략

### 4.1 불 마켓 (현재)

| 콘텐츠 | 월 생산량 | 에이전트 | 비고 |
|--------|----------|---------|------|
| ECON | 2건 | tokenomics-researcher | 신흥 프로젝트 중심 |
| MAT | 2건 | defi-researcher | 고성장 프로젝트 |
| FOR | 2-4건 | onchain-analyst | 이벤트 기반, 빈도 증가 |
| Weekly Pulse | 4건 | newsletter-agent (NEW) | 매주 월요일 |
| Deep Dive | 4건 | newsletter-agent (NEW) | 매주 목요일 |
| Forensic Alert | 4-10건 | onchain-analyst | 자동 트리거 |
| Trade Thesis | 3-4건 | tokenomics-researcher | 주요 보고서 연계 |
| **월 총계** | **21-30건** | | |

**에이전트 배정:**
- tokenomics-researcher: ECON 2건 + Trade Thesis 2건 = 주 1건 페이스
- defi-researcher: MAT 2건 = 격주 1건 페이스
- onchain-analyst: FOR 2-4건 + Forensic Alert = 이벤트 대응
- newsletter-agent (신규): Weekly Pulse + Deep Dive = 주 2건 자동 생성
- social-agent (신규): 전 콘텐츠 소셜 배포 자동화

### 4.2 베어 마켓

| 콘텐츠 | 월 생산량 | 변화 | 비고 |
|--------|----------|------|------|
| ECON | 1건 | ↓ | 블루칩 방어 분석 중심 |
| MAT | 1건 | ↓ | 생존 프로젝트 식별 |
| FOR | 4-8건 | ↑↑ | 사기/러그풀 경보 강화 |
| Weekly Pulse | 4건 | = | 매주 유지 |
| Deep Dive | 4건 | = | 방어 전략 프리뷰 |
| Forensic Alert | 8-15건 | ↑↑ | 경보 빈도 대폭 증가 |
| Trade Thesis | 2건 | ↓ | 헤지 전략 중심 |
| **월 총계** | **24-39건** | | FOR 비중 확대 |

**베어 마켓 핵심 전환:** ECON/MAT ↓, FOR/Forensic Alert ↑↑. 공포 시장에서 포렌식 콘텐츠가 가장 높은 가치를 가짐.

---

## 5. 뉴스레터 자동 생산 파이프라인 설계

### 5.1 newsletter-agent 아키텍처

```
[입력]                      [처리]                    [출력]
                                                    
Supabase data.*          → newsletter-agent        → .md (뉴스레터 원고)
 - price_daily              - 시장 요약 생성           - Market Pulse
 - onchain_daily            - 프로젝트 업데이트         - Deep Dive Preview
 - whale_transfers          - 포렌식 레이더           
 - market_snapshots         - 데이터 테이블 생성       
                                                    
project_reports          → newsletter-agent        → CRO 검수 큐
 - latest published          - Executive Summary 추출  
 - key_findings              - Paywall 경계 적용       
                                                    
config.referral_links    → newsletter-agent        → CTA 삽입
 - binance_ref               - 거래소별 CTA 생성       
 - bybit_ref                 - 컴플라이언스 필터        
 - okx_ref                                           
```

### 5.2 파이프라인 워크플로우

**Weekly Market Pulse (매주 월요일 06:00 UTC):**

| 시간 | 단계 | 자동/수동 |
|------|------|-----------|
| 일 23:00 | data-engineer가 주간 데이터 수집 완료 | 자동 (cron) |
| 월 00:00 | newsletter-agent가 Market Pulse .md 생성 | 자동 |
| 월 00:30 | CRO 검수 큐에 등록, 알림 발송 | 자동 |
| 월 01:00-05:00 | CRO 검수 + 승인 (15분 소요) | 수동 |
| 월 06:00 | 이메일 발송 + 웹 게시 | 자동 |

**Deep Dive Preview (매주 목요일 06:00 UTC):**

| 시간 | 단계 | 자동/수동 |
|------|------|-----------|
| 수 00:00 | newsletter-agent가 최신 보고서 기반 Deep Dive 생성 | 자동 |
| 수 00:30 | Freemium 경계선 적용 (Ch.1-3 공개, Ch.4+ 잠금) | 자동 |
| 수-목 | CRO 검수 + 승인 | 수동 |
| 목 06:00 | 이메일 발송 + 웹 게시 | 자동 |

### 5.3 기술 요구사항 (COO 전달)

| 요구사항 | 설명 | 우선순위 |
|----------|------|----------|
| newsletter-agent 구현 | gen_text 계열 신규 에이전트 | P0 |
| 뉴스레터 .md 템플릿 | TEMPLATE_PULSE.md, TEMPLATE_DEEPDIVE.md | P0 |
| CRO 검수 큐 | Supabase 테이블 + 알림 시스템 | P1 |
| 레퍼럴 CTA 자동 삽입 | config.py에 거래소 레퍼럴 URL 관리 | P1 |
| KR IP 필터 | CTA 삽입 시 대상 IP 기반 분기 | P1 |
| 이메일 발송 API 연동 | Resend/Mailgun SDK | P0 |

---

## 6. 보고서 "Action Section" 규격

기존 3종 보고서에 추가되는 새 섹션의 표준 규격입니다.

### 6.1 ECON Action Section

```markdown
## 11. Action Framework

### Investment Thesis
[보고서 분석을 한 문장으로 요약한 투자 논리]

### Scenario-Based Entry Points
| Scenario | Probability | Price Range | Rationale |
|----------|------------|-------------|-----------|
| Bull     | 30%        | $XX - $XX   | [근거]     |
| Base     | 50%        | $XX - $XX   | [근거]     |
| Bear     | 20%        | $XX - $XX   | [근거]     |

### Key Metrics to Monitor
- [지표 1]: 현재 값 → 목표 값
- [지표 2]: 현재 값 → 경고 값
- [지표 3]: ...

### Execute Your Analysis
> Ready to act on this research? Open your position on a trusted exchange.
> [Trade {TOKEN} on Binance →](ref_link) | [Trade on Bybit →](ref_link)

*Disclaimer: This content is for educational purposes only and does not constitute financial advice.*
```

### 6.2 FOR Action Section (긴급 버전)

```markdown
## Risk Response Actions

### Threat Level: 🔴 CRITICAL / 🟠 WARNING / 🟡 CAUTION

### Immediate Actions
1. [구체적 방어 행동 1]
2. [구체적 방어 행동 2]

### Hedge Strategies
- Strategy A: [설명] → [Trade on Exchange →](ref_link)
- Strategy B: [설명]

### Monitoring Checklist
- [ ] [모니터링 항목 1]
- [ ] [모니터링 항목 2]

*This is risk analysis, not financial advice. Act according to your own risk tolerance.*
```

---

## 7. 신규 에이전트 명세

### 7.1 newsletter-agent

| 항목 | 내용 |
|------|------|
| ID | newsletter-agent |
| 역할 | Weekly Pulse, Deep Dive 자동 생성 |
| 입력 | Supabase data.*, project_reports, config.referral_links |
| 출력 | .md (뉴스레터 원고) |
| 품질 기준 | 1,500-3,000 단어, 데이터 5+개, CTA 2-3개 |
| 검수 | CRO 승인 필수 |
| 스케줄 | 일/수 자동 실행 (주 2회) |

### 7.2 social-agent

| 항목 | 내용 |
|------|------|
| ID | social-agent |
| 역할 | X(Twitter), Telegram 자동 포스팅 |
| 입력 | 발행된 뉴스레터/보고서, Forensic Alert |
| 출력 | 소셜 포스트 (280자 트윗 + TG 메시지) |
| 빈도 | 일 2-3 포스트 |
| 검수 | 자동 발행 (CRO 사후 모니터링) |

---

## 8. 구현 우선순위

| 순위 | 항목 | 의존성 | 기간 |
|------|------|--------|------|
| P0 | TEMPLATE_PULSE.md 작성 | 없음 | 2일 |
| P0 | TEMPLATE_DEEPDIVE.md 작성 | 없음 | 2일 |
| P0 | 기존 보고서 Action Section 추가 | 없음 | 3일 |
| P0 | Freemium 경계선 적용 (기존 5건) | 없음 | 1일 |
| P1 | newsletter-agent 구현 | COO 이메일 인프라 | 5일 |
| P1 | Forensic Alert 자동 트리거 | COO 알림 시스템 | 3일 |
| P2 | Trade Thesis 템플릿 | P0 완료 | 2일 |
| P2 | social-agent 구현 | CMO 소셜 계정 | 5일 |

---

## 9. Conclusion

새로운 BM에 대응하여 기존 3종 보고서에 4종 신규 콘텐츠를 추가한 **7종 콘텐츠 체계**를 제안합니다. 핵심은 무료 콘텐츠(Pulse, Deep Dive, Trade Thesis)로 고객을 유입시키고, 유료 보고서로 신뢰를 구축한 뒤, 모든 콘텐츠에 자연스럽게 내재된 거래소 레퍼럴로 수익을 창출하는 구조입니다.

가장 시급한 것은 뉴스레터 템플릿 2종과 보고서 Action Section 규격 확정이며, newsletter-agent 구현은 COO의 이메일 인프라 구축과 병행하여 2주 내 첫 뉴스레터 발행을 목표로 합니다.

---

*Prepared by CRO Division, Blockchain Economics Lab*
*bcelab.xyz | 2026-04-12*
