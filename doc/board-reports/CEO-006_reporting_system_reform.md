---
report_id: CEO-006
date: 2026-04-12
type: board_report
author: CEO
classification: INTERNAL - CONFIDENTIAL
title: "전사 보고 체계 정비 및 티켓 시스템 도입"
references:
  - CEO-005 (전사 갭 분석 및 해소 지시)
  - SEC-001 (Strix 보안 감사 결과 보고)
  - ORGANIZATION.md (에이전트 조직 구성)
---

# CEO Board Report CEO-006
## 전사 보고 체계 정비 및 티켓 시스템 도입

> **Report ID**: CEO-006 | **Date**: 2026-04-12 | **Author**: CEO
> **Classification**: INTERNAL — CONFIDENTIAL

---

## 1. 요약 (Executive Summary)

조직 운영 과정에서 태스크의 진행 상태 추적, 보고 의무, 결재 흐름이 체계적으로 관리되지 않는 문제를 해결하기 위해, **티켓 기반 전사 보고 체계**를 도입합니다. 모든 태스크는 '티켓'으로 관리되며, 실무자 → 임원 → CEO → Board의 명확한 보고 라인을 따릅니다. Supabase에 tickets, ticket_comments, ticket_dependencies 테이블을 생성하고, ORGANIZATION.md의 §6~§7을 전면 개편했습니다.

---

## 2. 도입 배경

### 기존 문제점

1. **진행 상태 불투명**: 태스크가 시작되었는지, 완료되었는지, 누가 담당하는지 일관되게 추적할 방법이 없었음
2. **보고 의무 불명확**: 실행 결과를 누구에게, 어떤 형식으로 보고해야 하는지 명문화되지 않았음
3. **결재 프로세스 부재**: 태스크 완료 후 '종결', '수정 지시', '폐기' 결정 없이 방치되는 경우 발생
4. **목표 발굴 체계 없음**: 임원이 실행 결과를 분석하여 새로운 목표를 제안하는 상향식 흐름이 부재
5. **Board 보고 불규칙**: CEO → Board 보고가 ad-hoc으로 이루어져 전체 현황 파악이 어려웠음

---

## 3. 신규 체계: 티켓 기반 보고 시스템

### 3.1 핵심 규칙

| # | 규칙 | 상세 |
|---|------|------|
| 1 | **모든 업무는 티켓** | 스케줄 태스크, 지시 태스크, 발굴 목표 모두 티켓으로 생성 |
| 2 | **보고는 의무** | 실행자는 '수행 계획'과 '수행 결과'를 팀장/임원에게 코멘트로 보고 |
| 3 | **결재는 명시적** | 팀장/임원은 `approved` / `revision_requested` / `discarded` 중 결정 |
| 4 | **목표는 위에서 발굴** | 임원은 결과 재검토 → 목표 제안 → CEO 승인 → 하위 분배 |
| 5 | **CEO → Board 보고** | CEO는 전사 목표·계획·실행 결과를 Board에 정기 보고 |

### 3.2 티켓 유형 계층

```
[goal] 목표 ─── 전사/팀 수준 방향성 (CEO/임원 생성)
  └── [plan] 계획 ─── 실행 전략 (임원 생성, CEO 승인)
        └── [task] 태스크 ─── 구체적 실행 단위 (임원 배분, 실무자 수행)
```

### 3.3 상태 머신

```
backlog → todo → in_progress → in_review ──→ done (종결)
                                    │    └──→ discarded (폐기)
                                    └──→ in_progress (수정 지시 시 재수행)
```

### 3.4 보고 라인

```
실무 에이전트 ──(계획/결과 보고)──→ 임원 (CRO/COO/CMO)
                                       │
                                  결재 + 목표 발굴
                                       │
                             ──(제안 보고)──→ CEO
                                               │
                                          승인 + 전사 통합
                                               │
                                   ──(Board 보고)──→ Board (Human)
```

---

## 4. 인프라 구축 현황

### 4.1 Supabase DB 스키마 (적용 완료)

| 테이블 | 용도 | 주요 컬럼 |
|--------|------|-----------|
| `tickets` | 모든 티켓 | ticket_code, type, status, assignee, reporter, parent, review_decision |
| `ticket_comments` | 코멘트 스레드 | ticket_id, author_agent, comment_type, content |
| `ticket_dependencies` | blocking/blocked-by | blocking_ticket_id, blocked_ticket_id |

- RLS 활성화 완료
- `updated_at` 자동 갱신 트리거 적용
- 상태 전이 시 `started_at`, `completed_at` 자동 기록

### 4.2 코멘트 유형 (comment_type)

| 유형 | 용도 |
|------|------|
| `plan_submission` | 실행자 → 임원: 수행 계획 보고 |
| `result_report` | 실행자 → 임원: 수행 결과 보고 |
| `review` | 임원: 결재 코멘트 (승인/수정/폐기) |
| `escalation` | 에스컬레이션 |
| `status_change` | 상태 변경 자동 기록 |
| `comment` | 일반 논의 |

### 4.3 ORGANIZATION.md 개편 (완료)

§6 '커뮤니케이션 규칙' + §7 '태스크 상태 머신'을 **'§6 티켓 기반 보고 체계'**로 통합 교체:
- §6.1 핵심 원칙 (5개 규칙)
- §6.2 보고 라인 (실무→임원→CEO→Board)
- §6.3 티켓 유형 및 계층 (goal→plan→task)
- §6.4 상태 머신 (결재 흐름 포함)
- §6.5 운영 프로세스 (A.스케줄 B.지시 C.발굴 D.Board보고)
- §6.6 코멘트 유형
- §6.7 식별자 체계

---

## 5. 운영 시나리오 예시

### 시나리오 A: 일일 온체인 데이터 수집 (스케줄 태스크)

```
1. 스케줄러 → tickets INSERT (RES-040, type:task, origin:scheduled, assignee:agent-onchain-analyst)
2. 온체인 분석가 → 계획 코멘트: "CoinGecko + Etherscan에서 top50 수집 예정"
3. 온체인 분석가 → 수행 완료, 결과 코멘트: "50개 프로젝트 데이터 수집, 3건 이상치 감지"
4. 온체인 분석가 → status: in_review
5. CRO → 리뷰: "approved. 이상치 3건 별도 추적 티켓 생성 바람"
6. CRO → 3건에 대해 RES-041~043 하위 태스크 생성
```

### 시나리오 B: CEO 전략 지시

```
1. CEO → tickets INSERT (STR-020, type:goal, origin:directive, title:"Q3 수익 모델 다각화")
2. CEO → CRO/COO/CMO에게 plan 수립 지시
3. CRO → plan 티켓 생성 (RES-050, parent:STR-020): "DeFi 리서치 구독 상품 기획"
4. CRO → CEO에게 plan 보고 (status: in_review)
5. CEO → approved
6. CRO → task 배분: RES-051(DeFi 연구원), RES-052(토큰 연구원)
7. 실행 → 결과 보고 → CRO 결재 → CEO 주간 리뷰에서 Board 보고
```

---

## 6. CEO → Board 보고 주기

| 보고 유형 | 주기 | 포함 내용 |
|-----------|------|-----------|
| 주간 현황 보고 | 매주 월요일 | 주간 티켓 통계, 주요 결과, 진행 중 목표 |
| 월간 전략 보고 | 매월 1일 | 전사 목표 달성률, KPI, 임원별 성과 |
| 수시 보고 | 즉시 | 긴급 이슈, 중대 의사결정, 보안 감사 결과 |

보고서 형식: exec-report 스킬 (.md → Google Drive → 이메일)

---

## 7. 지시사항

### 즉시 시행 (P0)

| # | 지시 | 담당 | 기한 |
|---|------|------|------|
| 1 | 모든 신규 태스크는 반드시 tickets 테이블에 생성할 것 | 전 에이전트 | 즉시 |
| 2 | 수행 계획은 착수 전 코멘트로 보고할 것 | 전 실무 에이전트 | 즉시 |
| 3 | 수행 결과는 status를 in_review로 변경하고 코멘트로 보고할 것 | 전 실무 에이전트 | 즉시 |
| 4 | 임원은 in_review 티켓을 24시간 내 결재할 것 | CRO, COO, CMO | 즉시 |

### 단기 시행 (P1, 7일 내)

| # | 지시 | 담당 | 기한 |
|---|------|------|------|
| 5 | 기존 doc/board-reports/ 보고서를 board_reports DB에 소급 등록 | COO | 7일 |
| 6 | 스케줄 태스크 자동 티켓 생성 스크립트 구현 | COO (데이터 엔지니어) | 7일 |
| 7 | 주간 CEO → Board 보고 자동화 (티켓 통계 집계) | CEO | 7일 |

### 중기 시행 (P2, 30일 내)

| # | 지시 | 담당 | 기한 |
|---|------|------|------|
| 8 | 티켓 대시보드 (프론트엔드) 구현 | COO (데이터 엔지니어) | 30일 |
| 9 | 에이전트별 KPI 자동 산출 (티켓 처리량, 결재율, 평균 처리 시간) | COO | 30일 |
| 10 | 이메일 알림 연동 (결재 필요 시 임원에게 알림) | COO | 30일 |

---

## 8. 결론

이 체계가 안착되면, Board는 언제든 tickets 테이블을 조회하여 전사 업무 진행 현황을 파악할 수 있고, CEO는 데이터 기반으로 조직 성과를 관리할 수 있습니다. 모든 에이전트는 자신의 보고 의무와 결재 흐름을 명확히 인지하고, 태스크가 '방치'되는 상황을 원천 방지합니다.

Board의 승인을 요청드립니다.

---
*End of Report — CEO-006*
