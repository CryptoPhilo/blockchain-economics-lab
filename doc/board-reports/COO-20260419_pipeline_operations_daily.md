# Pipeline Operations Daily Report — COO-20260419

**보고 일자**: 2026-04-18
**보고 기간**: 최근 24시간
**보고 대상**: FOR Pipeline (Forensic Reports)

---

## Executive Summary

**처리 현황** (최근 24시간):
- ✅ **성공**: 2건
- ❌ **실패**: 3건
- ⏸️ **처리 중 (Stale)**: 0건
- 📊 **성공률**: 40.0%


## Failures by Category


### Processing Timeout (1건)

- **Ethereum 포렌식 분석 보고서.md** (`ethereum`)
  - 재시도 횟수: 2
  - 실패 시각: 2026-04-18T19:35:00Z
  - 오류: Processing exceeded 30 minute timeout


### Supabase Publishing Error (1건)

- **Cardano 포렌식 분석 보고서.md** (`cardano`)
  - 재시도 횟수: 0
  - 실패 시각: 2026-04-18T22:20:00Z
  - 오류: Supabase connection timeout


### QA Critical Failure (1건)

- **Solana 포렌식 분석 보고서.md** (`solana`)
  - 재시도 횟수: 1
  - 실패 시각: 2026-04-18T21:10:00Z
  - 오류: QA Critical: Missing required sections


## Recent Successes (2건)


### First-Pass Success (1건)

- Bitcoin 포렌식 분석 보고서.md (`bitcoin`)

### Retried and Succeeded (1건)

- Polkadot 포렌식 분석 보고서.md (`polkadot`) — 2 retries

---

## Action Items


### 2. QA Failures Review (1건)

QA 검증 실패 케이스를 검토하여 원문 품질 개선 또는 QA 룰 조정 필요.


### 3. Timeout Issues (1건)

처리 시간이 30분을 초과한 케이스. 파이프라인 성능 최적화 또는 타임아웃 임계값 조정 검토 필요.


### 4. Database Publishing Errors (1건)

PDF 생성 및 GDrive 업로드는 완료되었으나 Supabase 발행 단계에서 실패. DB 연결 및 스키마 검증 필요.


---

## Technical Details

**Pipeline**: FOR (Forensic Reports)
**Tracking File**: `scripts/pipeline/output/_for_processed.json`
**Log Directory**: `logs/for_pipeline`
**Report Generated**: 2026-04-18T22:31:52.464714+00:00Z
**Issue**: [BCE-461](/BCE/issues/BCE-461)

