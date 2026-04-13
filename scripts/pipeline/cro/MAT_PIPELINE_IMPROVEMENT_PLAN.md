# CRO 분석 보고서: MAT 보고서 파이프라인 개선 계획

> BCE Lab | CRO (Chief Research Officer) 분석  
> 작성일: 2026-04-12  
> 레퍼런스: Immutable (IMX) 생태계 진행률 및 크립토 이코노미 성숙도 정밀 평가 보고서

---

## 1. 비교 분석: 레퍼런스 보고서 vs BCE MAT 보고서

### 1.1 레퍼런스 보고서(IMX) 핵심 특장점

레퍼런스 보고서는 Immutable(IMX) 프로젝트의 크립토 이코노미 성숙도를 8개 챕터에 걸쳐 평가한다. 이 보고서의 핵심 강점은 다음과 같다:

**A. 프로젝트 맞춤형 목표 프레임워크 (Whitepaper-Derived Goals)**
- 프로젝트의 백서에서 직접 추출한 4대 목표(G1~G4)를 평가 축으로 사용
- 각 목표에 맞춤형 가중치 부여: Infrastructure(30%), Content(30%), UX(20%), Tokenomics(20%)
- KPI가 프로젝트-specific: "9,000+ TPS", "400+ game contracts", "4M Passport users" 등

**B. On-Chain/Off-Chain 비율 명시적 정량화**
- 각 목표별 On-Chain:Off-Chain 비율 정의 (예: G1은 70:30, G2는 30:70)
- 데이터 소스 검증 방법론이 목표 수준에서 구분

**C. 실명 파트너/게임 데이터 테이블**
- Ubisoft, Netmarble 등 구체적 파트너명과 개별 게임 타이틀 나열
- 장르, 출시 시기, 온체인 통합 방식까지 명시

**D. 타임라인 기반 마일스톤 추적 (2021-2026)**
- 연도별 주요 마일스톤과 평가를 테이블로 제시
- 과거 실적 + 현재 상태 + 미래 전망을 통합한 시계열 분석

**E. 목표별 세분화된 달성률 및 근거**
- G1: 95%, G2: 65%, G3: 85%, G4: 70%로 세분화
- 각 달성률에 정밀한 근거 제시 (예: "5% gap: 탈중앙화 로드맵 미완성")

**F. 투자 함의 및 리트머스 테스트**
- "Execution Opportunity" 같은 투자 프레임워크 적용
- "2026 Litmus Test" 같은 구체적 검증 기준 제시

### 1.2 현재 BCE MAT 보고서 핵심 특장점

현재 BCE MAT 파이프라인도 주목할 만한 강점이 있다:

**A. 10챕터 심층 서사형 구조 (6,000+ words)**
- 레퍼런스(8섹션)보다 더 방대한 10챕터 구조
- 각 챕터에 방법론 설명 → 데이터 → 해석 → 시사점의 4단계 서사

**B. 조건부 논리 기반 동적 텍스트**
- 점수 구간별(85+, 60-85, 30-60, 0-30) 완전히 다른 분석 텍스트 생성
- 가중치 분포 분석, 개선 효율성 분석 등 고급 연산 로직

**C. Score Sensitivity & Path to Next Stage**
- 다음 단계 진입을 위한 필요 점수 갭 자동 계산
- 목표별 개선 효율성(weight × remaining gap) 순위 분석

**D. 5영역 리스크 프레임워크**
- Technical, Economic, Competitive, Regulatory, Organizational 5축
- 자동 도메인 추론 + 심각도별 차등 분석

**E. auto_mat.py 자동 생성 시스템**
- 수동 데이터 입력 없이 market_data, transparency_scan에서 자동 추출
- 5개 범용 전략목표를 holder count, volume, GitHub 등에서 산출

### 1.3 GAP 분석: BCE MAT가 레퍼런스 대비 부족한 영역

| # | GAP 영역 | 레퍼런스 수준 | BCE MAT 현재 수준 | 심각도 |
|---|----------|-------------|-----------------|--------|
| 1 | **프로젝트 맞춤형 목표 체계** | 백서 기반 4대 맞춤 목표 + KPI | 5개 범용 목표 (모든 프로젝트 동일) | **CRITICAL** |
| 2 | **On/Off-Chain 비율 정량화** | 목표별 On:Off 비율 명시 | onchain_ratio/offchain_ratio 단일 값 | HIGH |
| 3 | **실제 파트너/에코시스템 데이터** | 실명 게임 테이블, 출시일, 장르 | 파트너 수 카운트만 (integrations, partnerships count) | **CRITICAL** |
| 4 | **시계열 마일스톤 추적** | 2021-2026 연도별 테이블 | 로드맵 텍스트만 (timeline_milestones 배열) | HIGH |
| 5 | **목표별 세분화 달성 근거** | 95%의 근거: "시퀀서 미이전" 등 | achievement_rate 숫자 + 수학 공식 기반 | HIGH |
| 6 | **재무 건전성 분석** | $140M 보유, $50M 인센티브, 번레이트 | 토큰 이코노믹스 일반론만 | **CRITICAL** |
| 7 | **사용자 메트릭 (MAU/DAU)** | "4M Passport users", "2.5M MAU" | holder_count 외 사용자 메트릭 없음 | HIGH |
| 8 | **투자 함의/리트머스 테스트** | 명시적 투자 프레임워크 | 일반적 결론만 | MEDIUM |
| 9 | **경쟁사 비교 테이블** | Arbitrum/Optimism 대비 UX 우위 언급 | peer_comparison 데이터 구조 있으나 활용 미흡 | MEDIUM |
| 10 | **프로토콜 수수료/수익 분석** | 2% 수수료, 20% IMX 결제, 스테이킹 | token_sustainability 텍스트 의존 | HIGH |

### 1.4 BCE MAT가 레퍼런스보다 우수한 영역

| # | 우위 영역 | BCE MAT | 레퍼런스 |
|---|----------|---------|---------|
| 1 | **보고서 서사 깊이** | 10챕터 6000+ words, 조건부 서사 | 8섹션, 상대적으로 간결 |
| 2 | **Score Sensitivity 분석** | 다음 단계 진입 경로 자동 계산 | 없음 |
| 3 | **리스크 5축 프레임워크** | 5 도메인 자동 분류 + 심각도 분석 | 리스크 섹션 없음 |
| 4 | **자동화 파이프라인** | auto_mat.py + gen_text_mat.py 완전 자동 | 수작업 |
| 5 | **보안 자세 분석** | Ch7에 감사, 버그바운티, 인시던트 대응 체계 | 부분적 언급만 |
| 6 | **개선 효율성 분석** | 목표별 weight×gap 기반 최적 개선 경로 | 없음 |

---

## 2. 개선 계획: 5-Phase 파이프라인 강화

### Phase 1: 프로젝트 맞춤형 목표 시스템 (Priority: CRITICAL, 2주)

**문제:** 현재 auto_mat.py의 STRATEGIC_OBJECTIVES가 모든 프로젝트에 동일한 5개 범용 목표를 사용. 레퍼런스처럼 프로젝트 백서/특성에 따른 맞춤형 목표가 필요.

**개선 방안:**

1.1. **프로젝트 카테고리별 목표 템플릿 시스템**
```
CATEGORY_OBJECTIVES = {
    'gaming': [
        {'name': 'Infrastructure & Scalability', 'weight': 30, 'kpis': ['TPS', 'block_time', 'gas_cost']},
        {'name': 'Ecosystem Content', 'weight': 30, 'kpis': ['game_count', 'aaa_partnerships', 'genre_diversity']},
        {'name': 'User Experience', 'weight': 20, 'kpis': ['wallet_users', 'fiat_onramp', 'orderbook_liquidity']},
        {'name': 'Tokenomics & Sustainability', 'weight': 20, 'kpis': ['protocol_revenue', 'staking_rate', 'runway']}
    ],
    'defi': [
        {'name': 'Protocol Security', 'weight': 30, ...},
        {'name': 'Liquidity & TVL', 'weight': 25, ...},
        ...
    ],
    'ai_blockchain': [...],
    'layer2': [...],
    'nft_marketplace': [...],
}
```

1.2. **CoinGecko 카테고리 기반 자동 매핑**
- 각 프로젝트의 CoinGecko categories를 파싱하여 가장 적합한 CATEGORY_OBJECTIVES 선택
- 복수 카테고리 시 가중 합산

1.3. **동적 KPI 수집기**
- 카테고리별 KPI에 대응하는 collector 함수 매핑
- DeFiLlama TVL, L2Beat TPS, Dune Analytics 쿼리 등

**수정 파일:** `auto_mat.py`, 신규 `maturity_objectives_templates.py`

### Phase 2: 에코시스템 데이터 수집 강화 (Priority: CRITICAL, 2주)

**문제:** 파트너십, 게임/앱 목록, 출시 상태 등 에코시스템 구체 데이터 부재

**개선 방안:**

2.1. **에코시스템 데이터 수집기 (ecosystem_collector.py)**
```python
class EcosystemCollector:
    """프로젝트 에코시스템 데이터 수집"""
    
    def collect_partnerships(self, project_id):
        """공식 웹사이트, 미디어 기사에서 파트너십 추출"""
        
    def collect_dapps_on_chain(self, chain_id):
        """체인 위의 활성 dApp 목록 수집 (DappRadar API)"""
        
    def collect_user_metrics(self, project_id):
        """MAU, DAU, wallet creation 등 사용자 메트릭"""
        
    def collect_developer_activity(self, github_org):
        """GitHub org 전체의 커밋, PR, 이슈 활동"""
```

2.2. **DappRadar API 통합**
- 프로젝트 체인의 활성 dApp 수, DAU, 트랜잭션 수 수집
- 게임별 장르, 출시 상태, 사용자 수 데이터

2.3. **DefiLlama 확장 데이터**
- TVL 히스토리, 프로토콜 수수료/수익, 체인별 비교 데이터
- 이미 CRO에 등록된 DefiLlama 소스 활용 강화

2.4. **gen_text_mat.py Chapter 4 강화**
- 파트너/게임 테이블 자동 생성 (레퍼런스 수준)
- 출시 상태별 분류 (Live, Planned, Beta)

**수정 파일:** 신규 `collectors/collector_dappradar.py`, `collectors/collector_ecosystem.py`, `gen_text_mat.py`

### Phase 3: 재무 건전성 & 토큰 수익 분석 (Priority: CRITICAL, 1주)

**문제:** 프로토콜 수수료, 수익, 재무 런웨이 등 정량적 재무 데이터 부재

**개선 방안:**

3.1. **프로토콜 수익 데이터 수집기**
```python
class ProtocolRevenueCollector:
    """DefiLlama Fees/Revenue API를 통한 프로토콜 수익 수집"""
    
    def collect_protocol_fees(self, protocol_slug):
        """일별/월별 프로토콜 수수료"""
        
    def collect_protocol_revenue(self, protocol_slug):
        """프로토콜 수익 (수수료 중 프로토콜 귀속분)"""
        
    def compute_runway_estimate(self, treasury_data, burn_rate):
        """재무 런웨이 추정"""
```

3.2. **Token Terminal / DefiLlama Fees 연동**
- 프로토콜별 수수료, 수익, P/E 비율 수집
- 30일/90일/1년 수익 추이

3.3. **gen_text_mat.py Chapter 8 강화**
- 수수료 구조 정량 테이블
- 수익 vs 인센티브 비용 비교
- 재무 런웨이 추정치 + 자급자족 도달 시점

**수정 파일:** 신규 `collectors/collector_protocol_revenue.py`, `gen_text_mat.py` Chapter 8 강화

### Phase 4: 시계열 마일스톤 & 경쟁사 비교 강화 (Priority: HIGH, 1주)

**문제:** 타임라인 분석이 텍스트 의존적이고, 경쟁사 비교가 형식적

**개선 방안:**

4.1. **자동 시계열 마일스톤 구축**
- CoinGecko 프로젝트 생성일 → 현재까지의 주요 이벤트 자동 추출
- GitHub release history에서 버전 마일스톤 추출
- 가격/TVL 변곡점에서의 주요 이벤트 상관 분석

4.2. **gen_text_mat.py Chapter 4 타임라인 테이블**
```markdown
| 기간 | 주요 마일스톤 | 평가 |
|------|-------------|------|
| 2021-2022 | 메인넷 출시, 토큰 제네시스 | 초기 단일 의존성 높음 |
| 2023 | zkEVM 개발 발표, 파트너십 확대 | 전략적 전환기 |
| ...  | ... | ... |
```

4.3. **경쟁사 비교 자동화**
- CoinGecko 카테고리 기반 동종 프로젝트 자동 선정
- market_cap, TVL, 사용자 수, 개발 활동 등 다차원 비교
- 레이더 차트용 데이터 구조 출력

4.4. **gen_text_mat.py Chapter 6 경쟁사 분석 섹션 추가**
- 동종 프로젝트 비교 테이블
- 카테고리 내 순위 및 상대적 성숙도 포지셔닝

**수정 파일:** `auto_mat.py`, `gen_text_mat.py` Chapter 4/6 강화

### Phase 5: 투자 함의 & 리트머스 테스트 프레임워크 (Priority: MEDIUM, 1주)

**문제:** 결론이 일반적이고 실행 가능한 투자 프레임워크 부재

**개선 방안:**

5.1. **성숙도 기반 투자 분류 시스템**
```python
INVESTMENT_FRAMEWORKS = {
    'nascent': {
        'classification': 'High-Risk Venture',
        'litmus_test': '핵심 기술 PoC 완성 여부',
        'time_horizon': '24-36개월',
    },
    'growing': {
        'classification': 'Growth Opportunity',
        'litmus_test': '사용자 메트릭 유의미한 증가세 여부',
        'time_horizon': '12-24개월',
    },
    'mature': {
        'classification': 'Execution Opportunity',
        'litmus_test': '프로토콜 수익이 운영 비용 초과 여부',
        'time_horizon': '6-12개월',
    },
    'established': {
        'classification': 'Value Investment',
        'litmus_test': '시장 점유율 방어 및 확장 여부',
        'time_horizon': '지속적',
    },
}
```

5.2. **프로젝트별 리트머스 테스트 자동 생성**
- 가장 낮은 달성률 목표에서 리트머스 테스트 도출
- "2026년 내 프로토콜 수수료가 인센티브 비용을 초과할 것인가?" 형태

5.3. **gen_text_mat.py Chapter 10 강화**
- 투자 분류 및 시간 지평 명시
- 리트머스 테스트 섹션 추가
- 시나리오별 성숙도 예측 (bull/base/bear)

**수정 파일:** `gen_text_mat.py` Chapter 10, `auto_mat.py`

---

## 3. 구현 로드맵

| Phase | 기간 | 주요 산출물 | 의존성 |
|-------|------|-----------|--------|
| Phase 1 | Week 1-2 | maturity_objectives_templates.py, auto_mat.py 개선 | 없음 |
| Phase 2 | Week 1-2 | collector_dappradar.py, collector_ecosystem.py | CRO 데이터소스 검증 |
| Phase 3 | Week 3 | collector_protocol_revenue.py, Chapter 8 강화 | DefiLlama Fees API |
| Phase 4 | Week 4 | Chapter 4/6 강화, 경쟁사 비교 자동화 | Phase 1 완료 |
| Phase 5 | Week 5 | Chapter 10 투자함의, 리트머스 테스트 | Phase 1-3 완료 |

---

## 4. 품질 목표 (Phase 5 완료 후)

### 4.1 정량적 목표

| 메트릭 | 현재 | 레퍼런스 | 목표 |
|--------|------|---------|------|
| 프로젝트 맞춤형 목표 수 | 5 (범용) | 4 (맞춤) | 4-6 (카테고리별 맞춤) |
| 에코시스템 데이터 소스 | 2 (CoinGecko, Transparency) | 5+ (Scan, L2Beat, Dune, etc.) | 5+ (DappRadar, DefiLlama, GitHub, etc.) |
| 재무 데이터 포인트 | 0 | 4+ (reserve, burn, incentive, revenue) | 4+ (fees, revenue, runway, P/E) |
| 파트너/dApp 테이블 | 없음 | 5+ rows 상세 테이블 | 자동 생성 테이블 |
| 타임라인 테이블 | 텍스트만 | 5+ rows 연도별 테이블 | 자동 생성 테이블 |
| 경쟁사 비교 | 형식적 | 정성적 언급 | 정량적 다차원 비교 |
| 투자 프레임워크 | 일반 결론 | Execution Opportunity + Litmus Test | 성숙도별 분류 + 자동 리트머스 |

### 4.2 정성적 목표

- 보고서를 읽은 투자자가 해당 프로젝트의 고유한 발전 경로를 명확히 이해
- 범용적 분석이 아닌, 프로젝트 카테고리와 목표에 최적화된 평가
- 구체적인 데이터(실명 파트너, 정확한 수수료율, MAU 수치)로 뒷받침된 달성률
- "이 프로젝트에 대해 어떤 질문을 해야 하는가"를 명확히 제시하는 리트머스 테스트

---

## 5. 우선순위 요약

```
[CRITICAL] Phase 1: 프로젝트 맞춤형 목표 시스템 → 보고서의 근본적 차별화
[CRITICAL] Phase 2: 에코시스템 데이터 수집 강화 → 빈 테이블을 실제 데이터로 채움
[CRITICAL] Phase 3: 재무 건전성 분석 → 투자 판단에 핵심적인 데이터
[HIGH]     Phase 4: 시계열/경쟁사 비교 → 맥락과 포지셔닝 제공
[MEDIUM]   Phase 5: 투자 함의/리트머스 → 보고서의 실행 가능성 강화
```

---

*CRO Analysis Report — Generated 2026-04-12*
*Reference: IMX Crypto Economy Maturity Precision Assessment Report (2025-2026)*
