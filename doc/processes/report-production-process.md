# 리서치 보고서 생산 프로세스 매뉴얼

> **관리 부서**: CRO (연구총괄)
> **협력 부서**: COO (운영총괄 — 편집·발행), CMO (마케팅총괄 — 배포·알림)
> **최초 작성**: 2026-04-09
> **근거 지시서**: STR-002

---

## 1. 보고서 템플릿 사양

### 1.1 Economy 설계분석 보고서 (RPT-ECON)

**형식**: PDF, 15~25페이지, A4

**필수 섹션 구조:**

```
1. 표지
   - 보고서 제목: "{프로젝트명} AI Agent Economy 설계분석 보고서"
   - 발행일, 버전, 기밀등급
   - 블록체인경제연구소 로고

2. Executive Summary (1페이지)
   - 핵심 발견 요약 (3~5개 불릿)
   - Overall Rating (S/A/B/C/D)

3. 프로젝트 아이덴티티 (1~2페이지)
   - 프로젝트 개요, 설립 배경, 팀 정보
   - 핵심 메트릭 요약 테이블 (시총, TVL, 일거래량, 홀더 수)

4. Core Tech Stack — 4 Pillars (3~4페이지)
   - Pillar 1: 핵심 기술 (AI Engine, L1/L2, DeFi Protocol 등)
   - Pillar 2: 인프라 (멀티체인, 브릿지, MPC 등)
   - Pillar 3: 보안 (감사, 버그바운티, 인시던트 이력)
   - Pillar 4: 거버넌스 (DAO, 투표 메커니즘, 탈중앙화 수준)
   - 각 Pillar별 점수 (0~100) 및 시각화

5. On-Chain Infra Spec (2~3페이지)
   - 체인 정보, 컨센서스, TPS, 가스비 구조
   - 스마트 컨트랙트 아키텍처
   - 주요 주소 및 컨트랙트 목록

6. System Architecture (2~3페이지)
   - 아키텍처 다이어그램
   - 핵심 모듈 간 상호작용
   - 외부 의존성 (오라클, 브릿지 등)

7. Value Flow (2페이지)
   - 가치 흐름도 (토큰 → 스테이킹 → 수수료 → 소각 등)
   - 수익 모델 분석
   - 지속가능성 평가

8. Token Economy (3~4페이지)
   - 토큰 분배 차트 (파이차트)
   - 베스팅 스케줄 (타임라인 차트)
   - 인플레이션/디플레이션 메커니즘
   - 토큰 유틸리티 매핑

9. Strategic Weight Framework (1~2페이지)
   - 핵심 요소별 가중치 (합계 100%)
   - 레이더 차트 시각화
   - 종합 평가 및 투자 관점 시사점

10. 리스크 요인 (1페이지)
    - Top 5 리스크 (영향도 × 발생확률 매트릭스)

11. 부록
    - 참고 자료, 데이터 출처, 면책 조항
```

### 1.2 Project Maturity 보고서 (RPT-MAT)

**형식**: PDF, 10~15페이지, A4

**필수 섹션 구조:**

```
1. 표지
   - "{프로젝트명} Project Maturity Report"
   - Maturity Score 대형 표시 (예: 80.25%)
   - 성숙도 단계 뱃지 (Nascent / Growing / Mature / Established)

2. Maturity Overview (1페이지)
   - 종합 Maturity Score
   - 전회 대비 변화 (↑/↓/→)
   - 단계 판정 기준표

3. Tech Pillar Assessment (3~4페이지)
   - 각 Pillar별 Progress Bar (0~100%)
   - 상세 평가 근거
   - 전회 대비 변화 추이 그래프

4. On-Chain Metrics (2~3페이지)
   - TVL 추이 (90일)
   - 일간 활성 주소 (90일)
   - 트랜잭션 수 추이
   - 가스 사용량 추이

5. Peer Comparison (2~3페이지)
   - 동일 카테고리 Top 5~10 프로젝트와 비교
   - 시가총액, TVL, 성숙도 점수 비교 테이블
   - 포지셔닝 맵 (2×2 매트릭스: 성숙도 vs 시장 규모)

6. Risk Matrix (1~2페이지)
   - 기술/시장/규제/운영 리스크 4분면
   - 전회 대비 리스크 수준 변화

7. Growth Trajectory (1페이지)
   - 향후 3개월 전망
   - 핵심 마일스톤 체크리스트
   - 다음 보고서까지의 관전 포인트

8. 부록
```

**성숙도 단계 기준:**

| 단계 | 점수 범위 | 설명 |
|------|----------|------|
| Nascent | 0~30% | 초기 단계, 컨셉 검증 중 |
| Growing | 31~60% | 성장 단계, 핵심 기능 구축 중 |
| Mature | 61~85% | 성숙 단계, 안정적 운영 |
| Established | 86~100% | 확립 단계, 업계 리더 |

### 1.3 Forensic 보고서 (RPT-FOR)

**형식**: PDF, 8~15페이지, A4, CONFIDENTIAL 마크

**필수 섹션 구조:**

```
1. 표지 (경고 형식)
   - "CONFIDENTIAL: MARKET RISK ALERT"
   - 프로젝트명, 토큰 심볼
   - Risk Level: 🔴 Critical / 🟡 Warning / 🟢 Watch
   - 발행 트리거 사유

2. Alert Summary (1페이지)
   - 발생 이벤트 요약
   - 타임라인 (최초 감지 → 현재)
   - 즉각적 리스크 판단

3. Insider Activity Analysis (2~3페이지)
   - 내부자 지갑 거래 추적
   - 매도 규모 및 패턴
   - 쉘 컴퍼니 라우팅 경로 (있을 경우)
   - 믹서/텀블러 사용 여부

4. Whale Wallet Behavior (2~3페이지)
   - 주요 고래 지갑 목록 (상위 10개)
   - 최근 30일 거래 패턴
   - 순매수/순매도 추이
   - 거래소 입출금 흐름

5. Market Microstructure (2~3페이지)
   - 캔들스틱 패턴 분석 (일봉/4시간봉)
   - 거래량 이상 탐지
   - 오더북 분석 (있을 경우)
   - Dead Cat Bounce 패턴 여부

6. External Factor Assessment (1~2페이지)
   - 관련 뉴스/규제 동향
   - 매크로 환경 영향
   - 유사 사례 비교

7. Risk Conclusion (1페이지)
   - 종합 리스크 레벨 판정
   - 권고 사항 (투자자 관점)
   - 다음 모니터링 일정

8. 면책 조항
```

---

## 2. 품질 기준

### 2.1 데이터 기준

| 항목 | 기준 |
|------|------|
| 데이터 최신성 | 발행일 기준 48시간 이내 데이터 사용 |
| 출처 명시 | 모든 수치에 출처 표기 (Dune, DefiLlama, CoinGecko 등) |
| 교차 검증 | 핵심 수치는 2개 이상 소스에서 확인 |
| 시각화 | 모든 차트에 축 라벨, 범례, 기간 명시 |

### 2.2 편집 기준

| 항목 | 기준 |
|------|------|
| 원본 언어 | EN (영어) + KO (한국어) 동시 작성 |
| 번역 언어 | FR, ES, DE, JA, ZH — EN 원본 기준 번역 |
| 분량 | 각 보고서 유형별 권장 페이지 수 준수 (전 언어 동일) |
| 포맷 | 공식 PDF 템플릿 적용 (언어별 로케일 설정) |
| 검수 | CRO 1차 검수(EN/KO) → 편집자 교정 → 번역 → CRO 최종 승인 |

### 2.3 번역 품질 기준

| 항목 | 기준 |
|------|------|
| 용어 일관성 | 블록체인 전문 용어 사전(Glossary) 준수 — 언어별 공인 번역 사용 |
| 수치 정확성 | 모든 숫자, 날짜, 금액이 원본과 100% 일치 |
| 차트/시각화 | 축 라벨, 범례, 주석 모두 해당 언어로 번역 |
| 문화적 적합성 | 날짜 형식(MM/DD vs DD/MM), 숫자 표기(1,000 vs 1.000) 현지화 |
| 면책 조항 | 각 언어별 법률 검토된 면책 문구 사용 |

### 2.4 발행 전 체크리스트

**원본 (EN/KO) 체크리스트:**
- [ ] 모든 데이터가 48시간 이내인가?
- [ ] 출처가 모두 명시되었는가?
- [ ] 핵심 수치가 교차 검증되었는가?
- [ ] 시각화(차트/그래프)가 정확한가?
- [ ] 오탈자/문법 검수가 완료되었는가?
- [ ] 적절한 기밀 등급이 표시되었는가? (Forensic)
- [ ] 면책 조항이 포함되었는가?
- [ ] PDF 렌더링이 정상인가?
- [ ] CRO 최종 승인을 받았는가?

**번역 (FR/ES/DE/JA/ZH) 체크리스트 (언어별 각각):**
- [ ] 전문 용어가 Glossary와 일치하는가?
- [ ] 모든 수치가 EN 원본과 동일한가?
- [ ] 차트 라벨/범례가 번역되었는가?
- [ ] 날짜/숫자 형식이 현지화되었는가?
- [ ] 면책 조항이 해당 언어 버전으로 포함되었는가?
- [ ] PDF 렌더링이 정상인가? (CJK 폰트, RTL 없음 확인)
- [ ] 페이지 수가 원본 대비 ±20% 이내인가?

---

## 3. 생산 일정 계산

### 3.1 신규 프로젝트 편입 시

| 일차 | 작업 | 담당 |
|------|------|------|
| D+0 | CRO: 프로젝트 등록, 태스크 생성, 담당자 배정 | CRO |
| D+1~5 | ECON 초고 작성 EN/KO (토큰 연구원 + 온체인 분석가 병렬) | 연구원 |
| D+1~3 | MAT 초고 작성 EN/KO (DeFi 연구원 + 온체인 분석가 병렬) | 연구원 |
| D+3~4 | MAT 편집·검수 (EN/KO) | 편집자 |
| D+4 | CRO 최종 검수 MAT (EN/KO) | CRO |
| D+5~6 | ECON 편집·검수 (EN/KO) + MAT 번역 (5개 언어 병렬) | 편집자 |
| D+6 | CRO 최종 검수 ECON (EN/KO) + MAT 번역 검수 | CRO |
| D+7~9 | ECON 번역 (5개 언어 병렬) + MAT 번역 검수 완료 | 편집자 |
| D+9 | ECON 번역 검수 완료 | 편집자 |
| D+10 | ECON + MAT 전 언어(7개) 동시 발행 | 편집자 + COO |
| D+10 | Forensic 모니터링 시작 | 온체인 분석가 |

### 3.2 동시 생산 역량

| 연구원 | 동시 태스크 수 | 주당 처리량 |
|--------|-------------|------------|
| 토큰 연구원 | 2건 | ECON 1건 완성 (EN/KO) |
| DeFi 연구원 | 2건 | MAT 2건 완성 (EN/KO) |
| 온체인 분석가 | 3건 (모니터링 포함) | 보조 분석 2건 + 일일 모니터링 |
| 매크로 분석가 | 2건 | FOR 보조 1건 + 주간 브리핑 |
| 리포트 편집자 | 3건 | 편집(EN/KO) 2건 + 번역 관리 1건 |

**주간 최대 생산량**: ECON 1건 + MAT 2건 + FOR 1건 = 4건/주 (각각 7개 언어 = 최대 28개 PDF/주)

---

## 3.5 다국어 번역 파이프라인

### 번역 워크플로우

```
원본 확정 (EN/KO, CRO 승인 완료)
│
├── Step 1: 번역 준비 (편집자, 0.5일)
│   ├── 용어 사전(Glossary) 확인 — 신규 전문 용어 추가
│   ├── 차트/시각화 내 텍스트 추출
│   └── 번역 태스크 5건 생성 (FR/ES/DE/JA/ZH)
│
├── Step 2: AI 번역 + 편집자 검수 (병렬, 1~2일)
│   ├── [FR] 본문 번역 → 용어 대조 → 수치 확인
│   ├── [ES] 본문 번역 → 용어 대조 → 수치 확인
│   ├── [DE] 본문 번역 → 용어 대조 → 수치 확인
│   ├── [JA] 본문 번역 → 용어 대조 → 수치 확인
│   └── [ZH] 본문 번역 → 용어 대조 → 수치 확인
│
├── Step 3: 시각화 현지화 (편집자, 0.5일)
│   ├── 차트 축 라벨/범례 번역 반영
│   ├── 날짜/숫자 형식 현지화
│   └── 표지/헤더/푸터 언어별 적용
│
└── Step 4: 최종 PDF 렌더링 (편집자, 0.5일)
    ├── 7개 언어 PDF 일괄 생성
    ├── CJK 폰트 렌더링 확인 (JA/ZH/KO)
    ├── 페이지 레이아웃 이상 여부 점검
    └── 파일명 규칙: {slug}_{type}_v{N}_{lang}.pdf
```

### 파일 명명 규칙

```
{project_slug}_{report_type}_v{version}_{language}.pdf

예시:
heyelsa_econ_v1_en.pdf
heyelsa_econ_v1_ko.pdf
heyelsa_econ_v1_fr.pdf
heyelsa_econ_v1_es.pdf
heyelsa_econ_v1_de.pdf
heyelsa_econ_v1_ja.pdf
heyelsa_econ_v1_zh.pdf
```

### 용어 사전 (Glossary) 관리

리포트 편집자가 관리하는 블록체인 전문 용어 사전을 유지한다.

| EN (기준) | KO | FR | ES | DE | JA | ZH |
|-----------|----|----|----|----|----|----|
| Token Economy | 토큰 경제 | Économie des tokens | Economía de tokens | Token-Ökonomie | トークンエコノミー | 代币经济 |
| Smart Contract | 스마트 컨트랙트 | Contrat intelligent | Contrato inteligente | Smart Contract | スマートコントラクト | 智能合约 |
| Whale Wallet | 고래 지갑 | Portefeuille baleine | Billetera ballena | Wal-Wallet | クジラウォレット | 巨鲸钱包 |
| Dead Cat Bounce | 데드캣 바운스 | Rebond du chat mort | Rebote del gato muerto | Tote-Katze-Sprung | デッドキャットバウンス | 死猫反弹 |

> 용어 사전은 지속적으로 확장하며, 신규 보고서 작성 시 새로운 전문 용어가 등장하면 편집자가 즉시 추가한다.

### Forensic 긴급 번역 프로토콜

시장 급변 시 Forensic 보고서는 시간이 생명이므로 특별 절차를 따른다:

```
긴급 모드 (CRO 판단):
├── 1단계: EN/KO 우선 발행 (분석 완료 후 즉시)
│   └── 구독자 알림: "Full multilingual version within 24h"
│
└── 2단계: 나머지 5개 언어 후속 발행 (24시간 이내)
    └── 구독자 알림: "Translated versions now available"

일반 모드:
└── 전 언어(7개) 동시 발행 (분석 후 +2일)
```

---

## 4. Forensic 일일 모니터링 절차

### 4.1 모니터링 체크리스트 (매일 00:00 UTC)

온체인 분석가가 활성 프로젝트 전체에 대해 수행:

```
각 프로젝트에 대해:
1. 24시간 가격 변동률 확인 (CoinGecko API)
   → ±15% 이상 시 플래그

2. 24시간 거래량 / 7일 평균 거래량 비율 확인
   → 300% 이상 시 플래그

3. 고래 지갑 대량 이동 확인 (상위 50 지갑)
   → 총 공급량 1% 이상 단일 이동 시 플래그

4. 거래소 순입금/순출금 확인
   → 24시간 순입금이 총 공급량 0.5% 이상 시 플래그

5. 내부자 지갑 활동 확인 (팀/투자자/어드바이저)
   → 비정상 이동 시 플래그

결과:
- 플래그 0개: 로그 기록, 정상 계속
- 플래그 1개: CRO에게 주의 알림
- 플래그 2개 이상: CRO에게 Forensic 발행 검토 요청
```

### 4.2 모니터링 로그 형식

```json
{
  "date": "2026-04-09T00:00:00Z",
  "project_slug": "heyElsa",
  "checks": {
    "price_change_24h": { "value": -3.2, "flag": false },
    "volume_ratio": { "value": 1.5, "flag": false },
    "whale_movement": { "value": 0.02, "flag": false },
    "exchange_netflow": { "value": 0.001, "flag": false },
    "insider_activity": { "value": "none", "flag": false }
  },
  "total_flags": 0,
  "action": "log_only",
  "analyst": "agent-onchain-analyst"
}
```

---

## 5. COO 편집팀 연계 프로토콜

### 5.1 CRO → COO 핸드오프

```
CRO가 최종 검수 완료 후 (EN/KO 원본 + 5개 번역 모두):
1. 태스크 상태를 "approved_for_publish"로 변경
2. COO에게 코멘트: "RES-xxx 전 언어(7개) 발행 승인 완료, 편집팀 발행 요청"
3. COO가 편집자에게 발행 태스크 할당

편집자 발행 절차:
1. 7개 언어 PDF 최종 렌더링 확인
2. Supabase Storage에 7개 파일 업로드
   - 경로: reports/{project_slug}/{report_type}/v{N}/{lang}.pdf
3. project_reports 테이블에 7개 언어 레코드 생성
4. products 테이블에 보고서 상품 레코드 생성/갱신 (7개 언어 제목/설명)
5. 구독자 알림 트리거 (CMO 팀 연계, 구독자 언어 설정에 맞는 알림)
6. 태스크를 "done"으로 변경
```

### 5.2 CMO 알림 연계

```
보고서 발행 시:
1. 편집자 → CMO에게 발행 알림 코멘트
2. CMO → 콘텐츠 마케터에게 배포 태스크 할당
   - 해당 종목 구독자 이메일 알림
   - SNS 요약 콘텐츠 (Twitter/Telegram)
   - 뉴스레터 포함 (주간 발행 시)
3. Forensic의 경우 추가:
   - 긴급 알림 전용 채널 발송
   - "MARKET RISK ALERT" 태그
```
