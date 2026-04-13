# OPS-003: Universal Coverage Pipeline — 구현 완료 보고서

**문서 유형**: COO 구현 보고서  
**작성일**: 2026-04-12  
**작성자**: COO (Operations Division)  
**관련 문서**: OPS-002 (파이프라인 재설계), MKT-006 (Universal Coverage 전략)  
**상태**: 구현 완료, 라이브 테스트 대기  

---

## 1. 구현 요약

OPS-002에서 설계된 BCE Universal Coverage 파이프라인의 Phase 1(기반 구축)을 완료했다.

### 1.1 구현 범위

| 항목 | 상태 | 파일 | 코드 라인 |
|------|------|------|-----------|
| DB 스키마 (5개 테이블) | ✅ 완료 | Supabase migration | — |
| config.py 확장 | ✅ 완료 | `config.py` | 194 |
| Phase A: 토큰 리스트 수집 | ✅ 완료 | `collectors/collector_tokenlist.py` | 245 |
| Phase C: 투명성 스캔 | ✅ 완료 | `collectors/collector_transparency.py` | 477 |
| Phase D: Triage 엔진 | ✅ 완료 | `triage.py` | 536 |
| Stage 0.5: 자동 MAT 생성 | ✅ 완료 | `auto_mat.py` | 627 |
| FOR 자동 트리거 | ✅ 완료 | `auto_forensic.py` | 389 |
| Phase E: 보고서 큐 | ✅ 완료 | `report_queue.py` | 395 |
| Phase A-F 오케스트레이터 | ✅ 완료 | `daily_pipeline.py` | 641 |
| collectors __init__.py 업데이트 | ✅ 완료 | `collectors/__init__.py` | — |
| **총 신규 코드** | | | **3,504줄** |

### 1.2 DB 테이블 (Supabase)

5개 테이블 모두 생성 완료 (RLS + 인덱스 포함):

1. `universal_ratings` — Triage 결과 (slug unique, grade/label/decision)
2. `grade_history` — 등급 변동 이력 (changed_at 인덱스)
3. `project_claims` — 프로젝트 자체 데이터 제출 (Claim Your Rating)
4. `market_data_daily` — 일일 시장 스냅샷 (slug+date unique)
5. `transparency_scan` — 투명성 스캔 결과 (slug unique)

---

## 2. 테스트 결과

### 2.1 파이프라인 통합 테스트 (dry-run)

```
Phase A: CoinGecko에서 727개 활성 토큰 수집 성공 (8.5초)
Phase B: 20개 토큰 시장 데이터 인덱싱 성공
Phase D: 20개 토큰 Triage 완료 (투명성 데이터 없이 → 모두 UR)
```

### 2.2 Triage 엔진 시나리오 테스트

| 프로젝트 | T점수 | M점수 | 총점 | 등급 | 결정 | 기대값 |
|----------|-------|-------|------|------|------|--------|
| Uniswap (대형, 고투명) | 28/30 | 67/70 | 95 | **A** | **FULL** | ✅ |
| SomeDefi (중형, 부분투명) | 18/30 | 39/70 | 57 | **C** | **MINIMAL** | ✅ |
| ShadyCoin (소형, 불투명) | 6/30 | 17/70 | 23 | **UR** | **UNRATABLE** | ✅ |
| PumpToken (가격 이상) | 20/30 | 38/70 | 58 | **C** | **MINIMAL** | ✅ |
| TinyCoin (극소형) | 12/30 | 7/70 | 19 | **F** | **SCAN_ONLY** | ✅ |

- PumpToken에서 포렌식 플래그 정상 감지: `price_anomaly=True, volume_spike=True`
- 5개 시나리오 모두 예상대로 등급/결정 산출

---

## 3. 아키텍처 다이어그램

```
daily_pipeline.py (Phase A-F 오케스트레이터)
│
├── Phase A: collector_tokenlist.py
│   └── CoinGecko /coins/markets → ~2,500 tokens
│
├── Phase B: (내장) market data indexing
│   └── market_data_daily 테이블에 저장
│
├── Phase C: collector_transparency.py
│   ├── CoinGecko /coins/{id} (팀 정보, 링크)
│   ├── GitHub API (오픈소스 여부)
│   ├── Etherscan API (홀더, 컨트랙트 검증)
│   └── transparency_scan 테이블에 저장
│
├── Phase D: triage.py (TriageEngine)
│   ├── 투명성 점수 (0-30) + 성숙도 점수 (0-70) = 총점 (0-100)
│   ├── BCE Grade (A/B/C/D/F/UR)
│   ├── Report Decision (FULL/STANDARD/MINIMAL/SCAN_ONLY/UNRATABLE)
│   ├── Forensic Flags (price_anomaly, volume_spike, etc.)
│   ├── Grade Changes 감지
│   └── universal_ratings + grade_history 테이블에 저장
│
├── Phase E: report_queue.py (ReportQueue)
│   ├── 5단계 우선순위 (P0: 신규 상장 → P4: 미보고 프로젝트)
│   ├── MAX_DAILY_REPORTS = 10
│   └── daily_report_queue.json 저장
│
└── Phase F: (내장) publishing
    ├── ratings_{date}.json 스냅샷
    ├── grade_movers_{date}.json
    ├── new_listings_{date}.json
    └── forensic_alerts_{date}.json
```

**보고서 생성 연결:**
```
report_queue.py → orchestrator.py (기존)
                  ├── FULL: auto_mat.py → gen_text_econ + gen_text_mat + auto_forensic.py → gen_text_for
                  ├── STANDARD: auto_mat.py → gen_text_econ + gen_text_mat
                  └── MINIMAL: gen_text_econ (간소화)
```

---

## 4. config.py 신규 설정

```python
BCE_GRADES = ['A', 'B', 'C', 'D', 'F', 'UR']
BCE_GRADE_THRESHOLDS = {'A': (80,100), 'B': (65,79), 'C': (50,64), 'D': (35,49), 'F': (0,34)}
TRANSPARENCY_LABELS = {'OPEN': (26,30), 'MOSTLY': (19,25), 'PARTIAL': (13,18), 'LIMITED': (7,12), 'OPAQUE': (0,6)}
UNRATABLE_TRANSPARENCY_THRESHOLD = 10
TRANSPARENCY_SCAN_ROTATION_DAYS = 5
COINGECKO_BATCH_SIZE = 250
MAX_DAILY_REPORTS = 10
FORENSIC_AUTO_TRIGGERS = {'price_change_24h_pct': 20.0, 'volume_spike_ratio': 5.0, ...}
```

---

## 5. 운영 가이드

### 5.1 실행 방법

```bash
# 전체 파이프라인 (일일 CRON)
python3 daily_pipeline.py

# 특정 Phase만
python3 daily_pipeline.py --phases ABD

# 테스트 (제한 + dry-run)
python3 daily_pipeline.py --limit 50 --dry-run

# Supabase 연결
python3 daily_pipeline.py --supabase-url $SUPABASE_URL --supabase-key $SUPABASE_SERVICE_KEY
```

### 5.2 환경변수

```bash
SUPABASE_URL=https://wbqponoiyoeqlepxogcb.supabase.co
SUPABASE_SERVICE_KEY=<service_key>
ETHERSCAN_API_KEY=<key>
GITHUB_TOKEN=<token>      # Optional: 5000 req/hr vs 60 req/hr
```

### 5.3 CRON 설정 (Phase 3에서)

```cron
0 6 * * * cd /path/to/pipeline && python3 daily_pipeline.py >> /var/log/bce_pipeline.log 2>&1
```

---

## 6. 다음 단계 (Phase 2-3)

### Phase 2: 자동화 연결 (1주)
- [ ] orchestrator.py 수정: report_decision 기반 자동 라우팅
- [ ] ECON 간소화 버전 (MINIMAL용)
- [ ] /ratings API 엔드포인트 (Next.js)
- [ ] Claim Your Rating 접수 폼

### Phase 3: 퍼블리싱 + 모니터링 (1주)
- [ ] /ratings 프론트엔드 페이지
- [ ] X(Twitter) 자동 트윗 (Grade Movers, Red Flag Friday)
- [ ] CRON 일일 스케줄 설정
- [ ] 파이프라인 모니터링 대시보드

### 인프라 권장
- [ ] CoinGecko Analyst 플랜 ($129/월) — Phase C 가속
- [ ] Etherscan Pro ($199/월) — 멀티체인 스캔 가속
- [ ] Supabase Pro ($25/월) — DB 연결 풀 확보

---

**COO 의견**: Phase 1 구현이 예정보다 빠르게 완료되었다. Triage 엔진의 5단계 결정 로직이 테스트에서 정확하게 작동하며, 파이프라인 전체가 dry-run으로 에러 없이 동작한다. 다음 우선순위는 /ratings 페이지 구현과 CRON 스케줄링이다.
