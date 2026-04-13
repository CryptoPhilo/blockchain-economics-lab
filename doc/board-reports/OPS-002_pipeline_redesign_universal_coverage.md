# OPS-002: 파이프라인 재설계 — Universal Coverage 대응

**문서 유형**: COO 인프라/파이프라인 보고서  
**작성일**: 2026-04-12  
**작성자**: COO (Operations Division)  
**관련 문서**: MKT-006 (Universal Coverage 전략), MKT-005 (소형 프로젝트 전략)  
**상태**: CEO 검토 대기  

---

## 1. Executive Summary

MKT-006에서 수립된 "크립토의 무디스" 전략(BCE Universal Ratings™)을 실행하기 위해, 기존 파이프라인을 근본적으로 재설계해야 한다. 현재 파이프라인은 **수동 등록된 소수 프로젝트**를 대상으로 설계되었으나, 새 전략은 **전 세계 CEX 상장 ~2,500개 토큰을 매일 자동 스캔**하는 구조를 요구한다.

핵심 변경: 파이프라인 초입에 **"Triage Stage" (투명성·성숙도 판단 단계)**를 신설하여, 각 프로젝트에 대해 어떤 보고서를 생성할 수 있는지(또는 생성 불가인지)를 자동으로 결정한다.

---

## 2. 현재 파이프라인 vs. 필요 파이프라인

### 2.1 현재 (As-Is)

```
[수동 등록] → Stage 0: 데이터 수집 → Stage 1: 텍스트 생성 → Stage 1.5: 번역 → Stage 2: PDF → Stage 3: 업로드
                                          ↑
                                    보고서 유형은 CLI 인자로 수동 지정
                                    (--type econ/mat/for)
```

**한계점:**
- 프로젝트 등록이 수동 (`data/{slug}.json` 수동 생성)
- 보고서 유형 결정이 수동 (운영자가 직접 `--type` 지정)
- 데이터 부족 시 graceful degradation은 있으나, "생산 가치가 있는지" 판단 없음
- MAT 보고서는 `strategic_objectives`와 `total_maturity_score`를 수동 입력해야 생성 가능
- FOR 보고서는 `risk_level`과 `forensic_findings`를 수동 입력해야 생성 가능
- 일 처리량: 1-3개 프로젝트 (수동 운영 기준)

### 2.2 필요 (To-Be): Universal Coverage Pipeline

```
[자동 스캔] → Stage T: Triage → Stage 0: 데이터 수집 → Stage 1: 텍스트 생성 → ...
  ~2,500개        ↓
  매일 갱신    ┌─ FULL: ECON + MAT + FOR 모두 생성 가능
              ├─ STANDARD: ECON + MAT만 생성 (FOR 데이터 부족)
              ├─ MINIMAL: ECON만 생성 (MAT용 정적 데이터 없음)
              ├─ SCAN-ONLY: Auto Scan 등급만 부여 (보고서 생성 불가)
              └─ UNRATABLE: 투명성 극히 낮아 등급 산정 자체 불가 → "UR" 표시
```

---

## 3. 신규 Stage T: Triage (투명성·성숙도 판단) 설계

### 3.1 Triage 개요

파이프라인의 최초 단계로서, 각 프로젝트의 **데이터 가용성**과 **프로젝트 성숙도**를 자동 평가하여 다음을 결정한다:

1. **BCE Grade** (A/B/C/D/F/UR) — 자동 산출
2. **Transparency Label** (OPEN/MOSTLY/PARTIAL/LIMITED/OPAQUE) — 자동 산출
3. **Report Eligibility** — 어떤 보고서를 생성할 수 있는지/할 가치가 있는지
4. **Report Priority** — 제한된 API 쿼터 내에서 어떤 프로젝트를 우선 처리할지

### 3.2 Triage 판단 기준

#### A. 투명성 점수 (Transparency Score, 0-30점)

| 항목 | 점수 | 확인 방법 |
|------|------|-----------|
| 팀 공개 | +6 | CoinGecko profile에 팀 정보 존재 여부 |
| 코드 오픈소스 | +6 | GitHub org/repo 존재 + 최근 90일 내 커밋 |
| 토큰 분배 공개 | +6 | Etherscan 검증 컨트랙트 + 홀더 분포 조회 가능 |
| 감사 완료 | +6 | CertiK/Hacken/Trail of Bits 감사 목록 확인 |
| 컨트랙트 검증 | +6 | Etherscan verified source code |

**투명성 라벨 매핑:**
- 26-30: 🟢 OPEN
- 19-25: 🔵 MOSTLY
- 13-18: 🟡 PARTIAL
- 7-12: 🟠 LIMITED
- 0-6: 🔴 OPAQUE

#### B. 성숙도 점수 (Maturity Score, 0-70점)

| 항목 | 점수 | 확인 방법 |
|------|------|-----------|
| 거래소 상장 수 | 0-15 | CoinGecko tickers API (1개=3, 2-3=6, 4-5=9, 6-10=12, 11+=15) |
| 일 거래량 | 0-15 | volume_24h / market_cap 비율 (5-30%면 만점) |
| 선물 시장 존재 | 0-10 | CoinGecko derivatives 데이터 확인 |
| 시가총액 규모 | 0-10 | log scale (>$1B=10, >$100M=8, >$10M=6, >$1M=4, 이하=2) |
| 온체인 홀더 수 | 0-10 | Etherscan holder count (>10K=10, >1K=7, >100=4, 이하=2) |
| 프로젝트 연령 | 0-10 | CoinGecko genesis_date 기준 (>3년=10, >1년=7, >6개월=4, 이하=2) |

#### C. 종합 점수와 보고서 결정 매트릭스

**종합 점수 = 투명성 + 성숙도 (0-100)**

| 종합 점수 | 투명성 조건 | 보고서 결정 | 설명 |
|-----------|-------------|-------------|------|
| 80-100 | OPEN/MOSTLY | **FULL** (ECON + MAT + FOR 가능) | 데이터 충분, 3종 보고서 모두 생산 가치 있음 |
| 60-79 | MOSTLY/PARTIAL | **STANDARD** (ECON + MAT) | FOR에 필요한 실시간 포렌식 데이터는 부족하나 경제/성숙도 분석 가능 |
| 40-59 | PARTIAL/LIMITED | **MINIMAL** (ECON만) | 시장 데이터 기반 경제 분석만 가능, MAT용 정적 데이터 부재 |
| 20-39 | LIMITED/OPAQUE | **SCAN-ONLY** (등급만) | BCE Auto Scan 등급 부여, 보고서 생산 불가 |
| 0-19 | OPAQUE | **UNRATABLE** (UR 등급) | 투명성 극히 낮아 등급 산정 불가, "UR" 표시 |

**추가 조건:**
- 투명성 점수가 10 미만이면, 종합 점수와 무관하게 **UNRATABLE** (UR)
- FOR 보고서는 투명성 19점 이상 AND 포렌식 이상 징후 감지 시에만 생성
- MAT 보고서는 투명성 13점 이상 AND 성숙도 40점 이상일 때만 생성

### 3.3 Triage 출력

```json
{
  "slug": "uniswap",
  "coingecko_id": "uniswap",
  "transparency_score": 28,
  "transparency_label": "OPEN",
  "maturity_score": 65,
  "total_score": 93,
  "bce_grade": "A",
  "report_eligibility": {
    "econ": true,
    "mat": true,
    "for": true
  },
  "report_decision": "FULL",
  "triage_reason": "High transparency (28/30) + High maturity (65/70). All data sources available.",
  "data_availability": {
    "coingecko": true,
    "etherscan": true,
    "github": true,
    "defillama": true,
    "audit": true,
    "derivatives": true
  },
  "forensic_flags": {
    "price_anomaly": false,
    "volume_spike": false,
    "whale_alert": false,
    "exchange_flow_alert": false
  },
  "triaged_at": "2026-04-12T06:15:00Z"
}
```

---

## 4. 재설계된 파이프라인 전체 흐름

### 4.1 Daily Pipeline (Phase A-F, 06:00-12:00 UTC)

```
Phase A (06:00): 토큰 리스트 수집
├── CoinGecko /coins/list → 전체 토큰 리스트
├── CoinMarketCap /listings/latest → CEX 상장 토큰 (선택적 크로스체크)
├── 필터: has_cex_listing = true → ~2,500개
├── 신규 상장 감지 (added_today)
└── 상장 폐지 감지 (removed_today)

Phase B (07:00): 시장 데이터 수집
├── CoinGecko /coins/markets (batch 250개씩, ~10회 요청)
│   → price, market_cap, volume_24h, change_24h/7d/30d
├── 이상 징후 1차 감지
│   → price_change_24h > 15%? volume_ratio > 3x?
└── 저장: market_data_daily 테이블

Phase C (08:00): 투명성 스캔
├── 팀 정보: CoinGecko profile 확인
├── 오픈소스: GitHub API (org 존재 + 커밋 활동)
├── 감사: CertiK/Hacken 리스트 크로스체크
├── 토큰 분배: Etherscan Top Holders (상위 체인만 — ETH, BSC, Polygon)
├── 컨트랙트 검증: Etherscan verified 상태
└── 저장: transparency_scan 테이블

Phase D (09:00): Triage (등급 산출 + 보고서 결정)
├── 투명성 점수 계산 (0-30)
├── 성숙도 점수 계산 (0-70)
├── BCE Grade 산출 (A/B/C/D/F/UR)
├── Transparency Label 부여
├── Report Eligibility 결정
├── 전일 대비 등급 변동 감지 (Grade Movers)
└── 저장: universal_ratings 테이블 + grade_history

Phase E (09:30): 보고서 생성 큐 결정
├── FULL 대상 중 보고서 미생성/갱신 필요 → Report Queue
├── STANDARD 대상 중 보고서 미생성/갱신 필요 → Report Queue
├── MINIMAL 대상 중 보고서 미생성/갱신 필요 → Report Queue
├── 우선순위: 신규 상장 > 등급 변동 > 갱신 필요 > 일반
└── 일일 생산 가능량 감안하여 상위 N개만 큐에 투입

Phase F (10:00): 퍼블리싱
├── /ratings 페이지 갱신 (ISR/SSG)
├── 신규 상장 트윗 자동 생성
├── Grade Movers 콘텐츠 생성
├── Red Flag 알림 발행
└── 일일 통계 기록
```

### 4.2 Report Generation Pipeline (기존 Stage 0-3 개편)

Triage 결과에 따라 보고서 생성 파이프라인이 동작한다:

```
[Report Queue에서 프로젝트 수신]
    │
    ├── report_decision == "FULL"
    │   ├── Stage 0: 전체 데이터 수집 (5 collectors 모두)
    │   ├── Stage 0.5: 자동 MAT 데이터 생성
    │   │   └── strategic_objectives, maturity_score를 온체인/시장 데이터에서 자동 추론
    │   ├── Stage 1a: ECON 텍스트 생성
    │   ├── Stage 1b: MAT 텍스트 생성
    │   ├── Stage 1c: FOR 텍스트 생성 (포렌식 플래그 있을 때만)
    │   └── Stage 2-3: PDF + 업로드
    │
    ├── report_decision == "STANDARD"
    │   ├── Stage 0: 데이터 수집 (whale collector 제외 가능)
    │   ├── Stage 0.5: 자동 MAT 데이터 생성
    │   ├── Stage 1a: ECON 텍스트 생성
    │   ├── Stage 1b: MAT 텍스트 생성
    │   └── Stage 2-3: PDF + 업로드
    │
    ├── report_decision == "MINIMAL"
    │   ├── Stage 0: 시장 데이터만 수집 (CoinGecko + macro)
    │   ├── Stage 1a: ECON 텍스트 생성 (간소화 버전)
    │   └── Stage 2-3: PDF + 업로드
    │
    ├── report_decision == "SCAN-ONLY"
    │   └── 보고서 생성 없음 — Triage 등급만 /ratings 페이지에 반영
    │
    └── report_decision == "UNRATABLE"
        └── 보고서 생성 없음 — UR 등급 + OPAQUE 라벨만 표시
```

---

## 5. Stage 0.5: 자동 MAT 데이터 생성 (신규)

현재 MAT 보고서는 `strategic_objectives`, `total_maturity_score`, `tech_pillars`를 수동 입력해야 생성 가능하다. ~2,500개 토큰을 커버하려면 이 데이터를 자동 생성해야 한다.

### 5.1 자동 추론 로직

```python
def auto_generate_mat_data(project_data, triage_result):
    """
    온체인/시장 데이터에서 MAT 보고서용 정적 데이터를 자동 추론한다.
    수동 입력 대비 정밀도는 낮지만, 커버리지를 위해 허용.
    """
    mat_data = {}
    
    # 1. 성숙도 점수 → Triage에서 이미 계산됨
    mat_data['total_maturity_score'] = triage_result['maturity_score']
    mat_data['maturity_stage'] = classify_maturity(triage_result['maturity_score'])
    
    # 2. 전략 목표 → 자동 추론 (5개 범용 목표)
    mat_data['strategic_objectives'] = [
        {
            'name': 'Market Adoption',
            'weight': 25,
            'achievement_rate': estimate_from_holders_and_volume(project_data),
            'milestones': auto_detect_milestones(project_data)
        },
        {
            'name': 'Technical Development',
            'weight': 25,
            'achievement_rate': estimate_from_github(project_data),
            'milestones': []
        },
        {
            'name': 'Ecosystem Growth',
            'weight': 20,
            'achievement_rate': estimate_from_tvl_and_integrations(project_data),
            'milestones': []
        },
        {
            'name': 'Security & Transparency',
            'weight': 15,
            'achievement_rate': triage_result['transparency_score'] / 30 * 100,
            'milestones': []
        },
        {
            'name': 'Market Position & Liquidity',
            'weight': 15,
            'achievement_rate': estimate_from_exchange_listings(project_data),
            'milestones': []
        }
    ]
    
    # 3. 기술 기둥 → 데이터 가용성 기반 자동 생성
    mat_data['tech_pillars'] = auto_detect_tech_pillars(project_data)
    
    return mat_data
```

### 5.2 자동 MAT 한계

- 수동 입력 MAT 대비 정밀도 약 60-70%
- `strategic_objectives`가 범용적 (프로젝트 고유 목표 반영 불가)
- "BCE Auto-Generated" 라벨을 보고서에 표시하여 수동 분석과 구분
- "Claim Your Rating" 프로세스를 통해 프로젝트가 직접 데이터를 제출하면 정밀도 향상

---

## 6. FOR 보고서 생성 기준 재정의

### 6.1 기존: 수동 트리거

```
운영자가 risk_level + forensic_findings를 수동 입력 → FOR 생성
```

### 6.2 개편: 자동 트리거 + 투명성 게이트

```
Phase B에서 이상 징후 감지
    ↓
투명성 점수 ≥ 13 (PARTIAL 이상)?
    ├── YES → 자동 FOR 생성 큐 추가
    │         risk_level = auto_classify(anomaly_data)
    │         forensic_findings = auto_detect(market + whale + exchange data)
    │
    └── NO → FOR 생성 불가 (데이터 부족)
             SCAN-ONLY 등급에 "⚠ Alert" 플래그만 추가
             /ratings 페이지에 경고 아이콘 표시
```

### 6.3 이상 징후 자동 감지 기준

| 지표 | 임계값 | 심각도 |
|------|--------|--------|
| 24시간 가격 변동 | > ±20% | ELEVATED |
| 거래량 급등 | > 5× 7일 평균 | HIGH |
| 고래 이동 | > 2% 공급량 24시간 내 | HIGH |
| 거래소 순유입 | > 1% 공급량 | CRITICAL |
| 복합 (2개 이상 동시) | 위 중 2개 이상 | CRITICAL |

### 6.4 투명성 부족 시 대응

투명성이 낮아 FOR 보고서를 생성할 수 없는 프로젝트에서 이상 징후가 감지되면:

- /ratings 페이지에 **"⚠ Anomaly Detected — Insufficient Data for Analysis"** 표시
- 해당 프로젝트의 등급 옆에 경고 아이콘 추가
- 이 자체가 마케팅 효과: "이 프로젝트는 투명성이 부족하여 분석할 수조차 없다"
- 프로젝트 관계자가 "Claim Your Rating"으로 데이터를 제출하면 분석 가능해짐

---

## 7. CoinGecko API 쿼터 관리

### 7.1 현재 사용 중인 API

- CoinGecko Free Tier: 10-30 req/min
- Etherscan Free Tier: 5 req/sec
- DeFiLlama: 무제한 (무료)
- GitHub: 60 req/hr (미인증), 5000 req/hr (인증)

### 7.2 ~2,500 토큰 일일 처리 시 쿼터 계산

| Phase | API 호출 수 | 소요 시간 (Free Tier) |
|-------|-------------|----------------------|
| A: 토큰 리스트 | 1 req | < 1분 |
| B: 시장 데이터 | 10 req (250개/batch) | ~1분 |
| C: 투명성 스캔 | ~2,500 req (개별 조회) | ~120분 (rate limited) |
| D: Triage 계산 | 0 req (로컬 연산) | < 1분 |

**병목: Phase C (투명성 스캔)**

### 7.3 최적화 전략

1. **점진적 스캔**: 전체 2,500개를 매일 스캔하지 않고, 5일 로테이션 (일 500개)
2. **변동 기반 스캔**: Phase B에서 가격/거래량 변동이 큰 프로젝트 우선 스캔
3. **캐시 활용**: 투명성 데이터는 변동이 적으므로 7일 캐시 TTL 적용
4. **CoinGecko Pro 업그레이드**: 월 $129에 500 req/min → Phase C를 5분 내 완료
5. **Etherscan Multi-chain**: ETH, BSC, Polygon 각 별도 API 키 → 병렬 처리

### 7.4 권장 API 투자

| 서비스 | 현재 | 권장 | 월 비용 | 효과 |
|--------|------|------|---------|------|
| CoinGecko | Free (30 req/min) | Analyst ($129) | $129 | Phase C: 120분 → 5분 |
| Etherscan | Free (5 req/sec) | Standard ($199) | $199 | 온체인 스캔 5× 가속 |
| GitHub | Free (60 req/hr) | Token (무료) | $0 | 5000 req/hr |
| **합계** | | | **$328/월** | |

---

## 8. 데이터베이스 스키마 확장

### 8.1 신규 테이블

```sql
-- Triage 결과 (매일 갱신)
CREATE TABLE universal_ratings (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL,
    coingecko_id TEXT,
    transparency_score SMALLINT DEFAULT 0,
    transparency_label TEXT DEFAULT 'OPAQUE',
    maturity_score SMALLINT DEFAULT 0,
    total_score SMALLINT DEFAULT 0,
    bce_grade CHAR(2) DEFAULT 'UR',
    report_decision TEXT DEFAULT 'UNRATABLE',
    data_availability JSONB DEFAULT '{}',
    forensic_flags JSONB DEFAULT '{}',
    triaged_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(slug)
);

-- 등급 변동 이력
CREATE TABLE grade_history (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL,
    old_grade CHAR(2),
    new_grade CHAR(2),
    old_label TEXT,
    new_label TEXT,
    reason TEXT,
    changed_at TIMESTAMPTZ DEFAULT now()
);

-- 프로젝트 자체 데이터 제출 (Claim Your Rating)
CREATE TABLE project_claims (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL,
    contact_email TEXT,
    team_info JSONB,
    token_distribution JSONB,
    audit_reports JSONB,
    roadmap JSONB,
    submitted_at TIMESTAMPTZ DEFAULT now(),
    verified_at TIMESTAMPTZ,
    verification_status TEXT DEFAULT 'pending'
);

-- 일일 시장 스냅샷 (Phase B 저장)
CREATE TABLE market_data_daily (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL,
    price_usd NUMERIC,
    market_cap NUMERIC,
    volume_24h NUMERIC,
    change_24h NUMERIC,
    change_7d NUMERIC,
    change_30d NUMERIC,
    recorded_at DATE DEFAULT CURRENT_DATE,
    UNIQUE(slug, recorded_at)
);

-- 투명성 스캔 결과 (Phase C 저장)
CREATE TABLE transparency_scan (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL,
    team_public BOOLEAN DEFAULT false,
    code_opensource BOOLEAN DEFAULT false,
    token_distribution_public BOOLEAN DEFAULT false,
    audit_completed BOOLEAN DEFAULT false,
    contract_verified BOOLEAN DEFAULT false,
    github_org TEXT,
    github_last_commit TIMESTAMPTZ,
    github_stars INT,
    audit_provider TEXT,
    scanned_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(slug)
);
```

### 8.2 기존 테이블과의 관계

```
tracked_projects (기존)
    └── 1:1 → universal_ratings (신규)
    └── 1:N → grade_history (신규)
    └── 1:N → market_data_daily (신규)
    └── 1:1 → transparency_scan (신규)
    └── 0:N → project_claims (신규)
    └── 1:N → project_reports (기존, report 생성 시)
```

---

## 9. 신규 코드 모듈 설계

### 9.1 파일 구조

```
scripts/pipeline/
├── collectors/
│   ├── collect_all.py          (기존, 수정)
│   ├── collector_exchange.py   (기존)
│   ├── collector_macro.py      (기존)
│   ├── collector_onchain.py    (기존)
│   ├── collector_whale.py      (기존)
│   ├── collector_fundamentals.py (기존)
│   ├── collector_tokenlist.py  (신규) — Phase A: 전체 토큰 리스트 수집
│   └── collector_transparency.py (신규) — Phase C: 투명성 스캔
├── triage.py                   (신규) — Phase D: Triage 엔진
├── auto_mat.py                 (신규) — Stage 0.5: 자동 MAT 데이터 생성
├── auto_forensic.py            (신규) — FOR 자동 트리거 + 이상 징후 분석
├── daily_pipeline.py           (신규) — Phase A-F 통합 오케스트레이터
├── report_queue.py             (신규) — Phase E: 보고서 생성 큐 관리
├── orchestrator.py             (기존, 수정) — report_decision 기반 자동 라우팅
└── config.py                   (기존, 확장) — Triage 임계값 설정
```

### 9.2 핵심 모듈: triage.py

```python
class TriageEngine:
    """
    프로젝트의 투명성과 성숙도를 평가하여 보고서 생성 여부를 결정한다.
    """
    
    def evaluate(self, slug: str, market_data: dict, transparency_data: dict) -> TriageResult:
        transparency_score = self._calc_transparency(transparency_data)
        maturity_score = self._calc_maturity(market_data)
        total_score = transparency_score + maturity_score
        
        grade = self._assign_grade(total_score, transparency_score)
        label = self._assign_label(transparency_score)
        decision = self._decide_reports(total_score, transparency_score, maturity_score)
        
        return TriageResult(
            slug=slug,
            transparency_score=transparency_score,
            transparency_label=label,
            maturity_score=maturity_score,
            total_score=total_score,
            bce_grade=grade,
            report_decision=decision,
        )
    
    def _decide_reports(self, total, transparency, maturity) -> str:
        if transparency < 10:
            return "UNRATABLE"
        if total >= 80 and transparency >= 19:
            return "FULL"
        if total >= 60 and transparency >= 13:
            return "STANDARD"
        if total >= 40:
            return "MINIMAL"
        return "SCAN-ONLY"
```

### 9.3 핵심 모듈: daily_pipeline.py

```python
class DailyPipeline:
    """
    매일 06:00 UTC에 실행되는 전체 파이프라인 오케스트레이터.
    Phase A → B → C → D → E → F 순서로 실행.
    """
    
    async def run(self):
        # Phase A: 토큰 리스트
        tokens = await self.phase_a_collect_token_list()
        
        # Phase B: 시장 데이터
        market_data = await self.phase_b_collect_market_data(tokens)
        
        # Phase C: 투명성 스캔 (로테이션)
        transparency = await self.phase_c_scan_transparency(tokens)
        
        # Phase D: Triage
        ratings = await self.phase_d_triage(tokens, market_data, transparency)
        
        # Phase E: 보고서 큐
        queue = await self.phase_e_build_report_queue(ratings)
        
        # Phase F: 퍼블리싱
        await self.phase_f_publish(ratings, queue)
```

---

## 10. 구현 로드맵

### Phase 1: 기반 구축 (2주)

| 작업 | 우선순위 | 소요 |
|------|----------|------|
| DB 스키마 생성 (5개 테이블) | P0 | 1일 |
| collector_tokenlist.py 구현 | P0 | 2일 |
| collector_transparency.py 구현 | P0 | 3일 |
| triage.py 구현 + 테스트 | P0 | 3일 |
| daily_pipeline.py 기본 구조 | P0 | 2일 |
| CoinGecko API 쿼터 최적화 | P1 | 1일 |

### Phase 2: 자동화 연결 (1주)

| 작업 | 우선순위 | 소요 |
|------|----------|------|
| auto_mat.py 구현 | P1 | 2일 |
| auto_forensic.py 구현 | P1 | 2일 |
| orchestrator.py 수정 (report_decision 기반 라우팅) | P1 | 1일 |
| report_queue.py 구현 | P1 | 1일 |
| /ratings 페이지 API 엔드포인트 | P1 | 1일 |

### Phase 3: 퍼블리싱 + 모니터링 (1주)

| 작업 | 우선순위 | 소요 |
|------|----------|------|
| /ratings 프론트엔드 페이지 | P1 | 3일 |
| 자동 트윗 생성 (Grade Movers) | P2 | 1일 |
| Claim Your Rating 접수 폼 | P2 | 2일 |
| 일일 파이프라인 CRON 설정 | P1 | 1일 |

**총 예상 소요: 4주**

---

## 11. 요약: 핵심 변경사항

1. **Stage T (Triage) 신설** — 투명성(0-30) + 성숙도(0-70) 자동 평가로 5단계 보고서 결정
2. **UNRATABLE/SCAN-ONLY 도입** — 투명성이 낮아 보고서 자체를 생산하지 않는 경우 포함
3. **자동 MAT 데이터 생성** — 수동 입력 없이 온체인/시장 데이터에서 MAT용 데이터 추론
4. **FOR 자동 트리거** — 이상 징후 감지 시 자동 생성, 투명성 게이트 적용
5. **일일 파이프라인** — Phase A-F 6단계로 ~2,500개 토큰 매일 처리
6. **5일 로테이션 스캔** — API 쿼터 관리를 위한 투명성 스캔 분산 처리
7. **DB 스키마 5개 테이블 신설** — universal_ratings, grade_history, project_claims, market_data_daily, transparency_scan

---

**COO 의견**: 이 재설계는 MKT-006 전략을 기술적으로 실현 가능하게 하며, 기존 파이프라인의 Stage 0-3 구조를 최대한 재활용한다. 가장 큰 리스크는 CoinGecko Free Tier의 API 쿼터 제한이며, Analyst 플랜($129/월) 업그레이드를 강력 권장한다. 4주 내 MVP 운영 가능하며, 초기 한 달간은 Auto Scan + SCAN-ONLY/UNRATABLE 등급 부여만으로도 마케팅 효과를 낼 수 있다.
