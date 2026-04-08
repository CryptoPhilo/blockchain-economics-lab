# STR-002: 리서치 보고서 생산 파이프라인 구축

> **발행자**: agent-ceo (연구소장)
> **승인자**: Board (Human)
> **발행일**: 2026-04-09
> **상태**: Active
> **Goal Ancestry**: Company Mission → STR-001 → 이 지시서

---

## 1. 배경

블록체인경제연구소의 핵심 상품인 리서치 보고서의 체계적 생산 체제를 구축한다. Board가 제공한 3종의 보고서 템플릿(Economy 설계분석, Project Maturity, Forensic)을 기반으로, 프로젝트별 보고서를 정기적·이벤트 기반으로 발행하는 파이프라인을 수립한다.

**다국어 생산 원칙**: 모든 보고서는 웹사이트가 지원하는 **7개 언어**로 생산한다.

| 코드 | 언어 | 역할 |
|------|------|------|
| `en` | English | 원본 작성 언어 (Master) |
| `ko` | 한국어 | 동시 생산 (공동 원본) |
| `fr` | Français | 번역 |
| `es` | Español | 번역 |
| `de` | Deutsch | 번역 |
| `ja` | 日本語 | 번역 |
| `zh` | 中文 | 번역 |

원본(EN/KO)은 연구원이 직접 작성하고, 나머지 5개 언어는 리포트 편집자가 번역 파이프라인을 통해 생산한다. 모든 언어 버전이 완성되어야 최종 발행이 승인된다.

---

## 2. 보고서 유형 정의

### 2.1 Economy 설계분석 보고서

| 항목 | 내용 |
|------|------|
| **코드** | `RPT-ECON` |
| **목적** | 프로젝트의 경제 설계(토큰이코노믹스, 가치 흐름, 기술 스택, 시스템 아키텍처)를 심층 분석 |
| **갱신 주기** | 6개월 |
| **페이지** | 15~25페이지 |
| **주요 섹션** | 프로젝트 아이덴티티, Core Tech Stack (4 Pillars), On-Chain Infra Spec, System Architecture, Value Flow, Token Economy, Strategic Weight Framework |
| **주 담당** | 토큰이코노믹스 연구원 (`agent-tokenomics-researcher`) |
| **보조 담당** | 온체인 분석가 (`agent-onchain-analyst`) |
| **품질 검수** | CRO → 리포트 편집자 |

### 2.2 Project Maturity 보고서

| 항목 | 내용 |
|------|------|
| **코드** | `RPT-MAT` |
| **목적** | 프로젝트의 성숙도를 정량 평가하고 동종 프로젝트와 비교 분석 |
| **갱신 주기** | 3개월 |
| **페이지** | 10~15페이지 |
| **주요 섹션** | Maturity Score (%), Tech Pillar Progress, Peer Comparison, Risk Matrix, Growth Trajectory |
| **주 담당** | DeFi 연구원 (`agent-defi-researcher`) |
| **보조 담당** | 온체인 분석가 (`agent-onchain-analyst`) |
| **품질 검수** | CRO → 리포트 편집자 |

### 2.3 Forensic 보고서

| 항목 | 내용 |
|------|------|
| **코드** | `RPT-FOR` |
| **목적** | 시장 무결성 포렌식 분석 — 내부자 매도, 쉘 컴퍼니, 믹서, 고래 행동, 캔들 패턴 이상 감지 |
| **갱신 주기** | 이벤트 기반 (일일 모니터링, 급변 발생 시 발간, 최소 간격 1주일) |
| **페이지** | 8~15페이지 |
| **주요 섹션** | Market Risk Alert, Insider Activity, Shell Company Routing, Mixer Usage, Whale Wallet Behavior, Candlestick Pattern Analysis, Dead Cat Bounce Warning |
| **주 담당** | 온체인 분석가 (`agent-onchain-analyst`) |
| **보조 담당** | 매크로 분석가 (`agent-macro-analyst`) |
| **품질 검수** | CRO → 리포트 편집자 |
| **기밀 등급** | CONFIDENTIAL: MARKET RISK ALERT |

---

## 3. 발행 주기 규칙

### 3.1 정기 발행

```
프로젝트 등록 시점 (T=0)
├── T+0:   Economy 설계분석 보고서 초판 발행
├── T+0:   Project Maturity 보고서 초판 발행  
├── T+3M:  Project Maturity 갱신 (1차)
├── T+6M:  Economy 설계분석 갱신 (1차) + Project Maturity 갱신 (2차)
├── T+9M:  Project Maturity 갱신 (3차)
├── T+12M: Economy 설계분석 갱신 (2차) + Project Maturity 갱신 (4차)
└── ... (반복)
```

### 3.2 이벤트 기반 발행 (Forensic)

```
일일 모니터링 (매일 00:00 UTC)
│
├── 급변 미감지 → 로그 기록, 다음 날 계속 모니터링
│
└── 급변 감지 (아래 트리거 중 1개 이상)
    ├── 24시간 내 가격 ±15% 이상 변동
    ├── 거래량 7일 평균 대비 300% 이상 급증
    ├── 고래 지갑 대량 이동 (총 공급량의 1% 이상)
    ├── 내부자 지갑 비정상 활동 감지
    └── 믹서/텀블러 자금 유입 급증
    │
    ├── 마지막 Forensic 발행일 ≥ 7일 전 → 즉시 보고서 작성 착수
    └── 마지막 Forensic 발행일 < 7일 전 → 내부 알림만 발행 (CRO에게 보고)
        └── 7일 경과 후 상황 재평가하여 발행 여부 결정
```

---

## 4. 프로젝트 발굴 파이프라인

### 4.1 주간 발굴 목표

매주 **3개의 신규 프로젝트**를 발굴하여 분석 대상으로 편입한다.

### 4.2 발굴 기준

| 우선순위 | 기준 | 설명 |
|---------|------|------|
| 🔴 1순위 | 시가총액 상위 100위 이내 | 주목도가 높은 메이저 프로젝트 |
| 🟡 2순위 | 최근 30일 TVL 성장률 Top 20 | DeFi 생태계 내 급성장 프로젝트 |
| 🟡 2순위 | 주요 거래소 신규 상장 | Binance, Coinbase, Upbit 등 Tier-1 |
| 🟢 3순위 | 커뮤니티 수요 | 구독자 투표/요청 기반 |
| 🟢 3순위 | 혁신 기술 | 새로운 카테고리 또는 기술적 돌파구 |

### 4.3 발굴 프로세스

```
[매주 월요일 09:00 KST]
│
├── DeFi 연구원: DeFiLlama TVL 급등 프로젝트 3~5개 후보 추출
├── 온체인 분석가: 온체인 활성도 급증 프로젝트 3~5개 후보 추출
├── 토큰 연구원: 신규 상장/토큰 이벤트 프로젝트 3~5개 후보 추출
├── 매크로 분석가: 규제/매크로 테마 관련 프로젝트 2~3개 후보 추출
│
└── [매주 화요일 09:00 KST] CRO 주관 선정 회의
    ├── 후보 풀에서 3개 확정
    ├── 각 프로젝트에 RPT-ECON + RPT-MAT 초판 태스크 생성
    ├── Forensic 일일 모니터링 대상 등록
    └── CEO에게 선정 결과 보고
```

### 4.4 프로젝트 관리 상태

```
discovered → under_review → active → monitoring_only → archived
                                 ↓
                            suspended (규제 이슈 등)
```

- `active`: 모든 보고서 유형 생산 대상
- `monitoring_only`: 더 이상 신규 보고서 미발행, Forensic 모니터링만 유지
- `archived`: 완전 종료 (프로젝트 소멸, 러그풀 확인 등)

---

## 5. 보고서 생산 워크플로우

### 5.1 Economy 설계분석 보고서 (RPT-ECON)

```
[CRO] RES-xxx: {프로젝트명} Economy 설계분석 보고서 v{N} 할당
  │
  ├── [토큰 연구원] RES-xxx-a: 토큰이코노믹스 분석 (5일)
  │     ├── 프로젝트 아이덴티티 조사
  │     ├── Token Economy 모델링
  │     ├── Strategic Weight Framework 산출
  │     └── 초고 작성 (EN + KO 동시)
  │
  ├── [온체인 분석가] RES-xxx-b: 온체인 인프라 분석 (3일)
  │     ├── Core Tech Stack 4 Pillars 평가
  │     ├── On-Chain Infra Spec 수집
  │     ├── System Architecture 매핑
  │     └── Value Flow 다이어그램 작성
  │
  ├── [리포트 편집자] RES-xxx-c: 편집·검수 (2일)
  │     ├── EN/KO 초고 통합 편집
  │     ├── 데이터 시각화 검수
  │     └── CRO 최종 승인 (EN/KO 원본)
  │
  └── [리포트 편집자] RES-xxx-d: 다국어 번역·발행 (3일)
        ├── EN 원본 → FR, ES, DE, JA, ZH 번역 (5개 언어 병렬)
        ├── 번역 품질 검수 (용어 일관성, 수치 정확성)
        ├── 7개 언어 PDF 최종 렌더링
        └── 전 언어 동시 발행 + 구독자 알림
```

**총 리드타임**: 약 13일 (병렬 진행 기준 10일, 번역 포함)

### 5.2 Project Maturity 보고서 (RPT-MAT)

```
[CRO] RES-xxx: {프로젝트명} Maturity Report v{N} 할당
  │
  ├── [DeFi 연구원] RES-xxx-a: 성숙도 정량 평가 (3일)
  │     ├── Tech Pillar별 진척도 평가
  │     ├── Maturity Score 산출
  │     └── Peer Comparison 데이터 수집 + 초고 (EN/KO)
  │
  ├── [온체인 분석가] RES-xxx-b: 온체인 지표 수집 (2일)
  │     ├── TVL, 거래량, 활성 주소 추이
  │     └── 시가총액 비교 데이터
  │
  ├── [리포트 편집자] RES-xxx-c: 편집·검수 (2일)
  │     ├── EN/KO 통합 편집 + Progress Bar 시각화
  │     └── CRO 최종 승인 (EN/KO 원본)
  │
  └── [리포트 편집자] RES-xxx-d: 다국어 번역·발행 (2일)
        ├── EN 원본 → FR, ES, DE, JA, ZH 번역 (5개 언어 병렬)
        ├── 번역 품질 검수
        ├── 7개 언어 PDF 최종 렌더링
        └── 전 언어 동시 발행 + 구독자 알림
```

**총 리드타임**: 약 9일 (병렬 진행 기준 7일, 번역 포함)

### 5.3 Forensic 보고서 (RPT-FOR)

```
[온체인 분석가] → 일일 모니터링 중 급변 감지
  │
  ├── CRO에게 즉시 에스컬레이션
  │
  └── [CRO] RES-xxx: {프로젝트명} Forensic Alert 할당 (긴급)
        │
        ├── [온체인 분석가] RES-xxx-a: 포렌식 분석 (2일, 긴급시 1일)
        │     ├── Insider Activity 추적
        │     ├── Whale Wallet Behavior 분석
        │     ├── Candlestick Pattern + Volume Analysis
        │     └── Risk Level 판정
        │
        ├── [매크로 분석가] RES-xxx-b: 외부 요인 분석 (1일)
        │     ├── 규제/뉴스 영향 확인
        │     └── 매크로 환경 상관관계
        │
        ├── [리포트 편집자] RES-xxx-c: 긴급 편집 (1일)
        │     ├── CONFIDENTIAL 마크 적용
        │     ├── EN/KO 동시 편집
        │     └── CRO 긴급 승인 (EN/KO 원본)
        │
        └── [리포트 편집자] RES-xxx-d: 긴급 번역·발행 (1일)
              ├── EN 원본 → FR, ES, DE, JA, ZH 긴급 번역 (5개 언어 병렬)
              ├── 7개 언어 PDF 렌더링 (CONFIDENTIAL 마크 전 언어 적용)
              └── 전 언어 동시 발행 + 구독자 긴급 알림
```

**총 리드타임**: 3~5일 (긴급 모드 3일, 번역 포함)

> **Forensic 긴급 발행 예외**: 시장 상황이 극히 긴급한 경우 CRO 판단 하에 EN/KO 2개 언어만 우선 발행하고, 나머지 5개 언어는 24시간 내 후속 발행할 수 있다.

---

## 6. CRO 위임 범위

CEO는 이 지시서를 통해 CRO에게 다음을 위임한다:

| 위임 사항 | 설명 |
|-----------|------|
| 프로젝트 발굴 | 주간 3개 프로젝트 발굴 프로세스 운영 |
| 연구원 배정 | 보고서별 담당 연구원 할당 및 일정 관리 |
| 품질 관리 | 모든 보고서의 최종 품질 검수 및 발행 승인 |
| 다국어 품질 관리 | 7개 언어 번역 품질 감독, 용어 사전 관리 |
| 갱신 스케줄 관리 | 프로젝트별 보고서 갱신 일정 추적 및 리마인더 |
| Forensic 트리거 판단 | 일일 모니터링 결과에 기반한 Forensic 보고서 발행 판단 |
| 에스컬레이션 | 인력 부족, 예산 초과, 긴급 상황 시 CEO에게 보고 |

**에스컬레이션 기준:**
- 동시 진행 보고서 8건 이상 → CEO에게 우선순위 조정 요청
- Forensic 트리거가 3일 연속 발생 → CEO + Board 알림
- 프로젝트 러그풀/스캠 확정 시 → CEO + Board 즉시 보고

---

## 7. 즉시 실행 태스크

| ID | 태스크 | 담당 | 우선순위 | 목표일 |
|----|--------|------|---------|--------|
| RES-010 | 보고서 템플릿 3종 공식화 (PDF 템플릿 기반) | 리포트 편집자 | 🔴 Critical | 04-14 |
| RES-011 | 주간 프로젝트 발굴 첫 라운드 실행 | CRO + 연구원 4명 | 🔴 Critical | 04-15 |
| RES-012 | Forensic 일일 모니터링 스크립트 구축 | 온체인 분석가 + 데이터 엔지니어 | 🟡 High | 04-18 |
| RES-013 | 프로젝트 관리 DB 테이블 생성 | 데이터 엔지니어 | 🟡 High | 04-14 |
| RES-014 | 보고서 발행 자동화 (COO 편집팀 연계) | COO + 데이터 엔지니어 | 🟡 High | 04-21 |
| STR-003 | 종목별 구독 상품 모델 임원 논의 | CEO + CRO + COO + CMO | 🔴 Critical | 04-12 |

---

## 8. 승인

이 지시서는 Board의 승인을 받아 즉시 시행된다.

```
[Board] ✅ Approved — 2026-04-09
[CEO]   ✅ Issued — 2026-04-09
[CRO]   ⏳ Acknowledged — pending
[COO]   ⏳ Acknowledged — pending (편집·발행 연계)
[CMO]   ⏳ Acknowledged — pending (구독자 알림 연계)
```
