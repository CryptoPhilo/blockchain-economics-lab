# STR-003: Report Production Pipeline Architecture v2

> Directive ID: STR-003
> Date: 2026-04-09
> Author: CRO Division
> Status: APPROVED
> Supersedes: STR-002 (pipeline section only; STR-002 report-type definitions remain active)

---

## 1. Design Principle

**.md 파일이 모든 보고서의 단일 진실 원천(Single Source of Truth)이다.**

이전 파이프라인은 텍스트(.md), PDF, 슬라이드가 각각 독립적으로 데이터를 소비했다. v2에서는 .md가 마스터 콘텐츠 레이어로 기능하며, 모든 파생 포맷(보고서 PDF, 슬라이드 PDF, 랜딩페이지 HTML)은 .md에서 추출한 데이터로 생성된다.

```
Stage 0          Stage 1            Stage 2A           Stage 2B
─────────       ──────────         ──────────         ──────────
Data Collect → .md Master Text → Report PDF (A4)  → Slide PDF (16:9)
 (APIs)         (6,000+ words)    (branded pages)    (8 infographics)
                      │                                    │
                      ├──────── Stage 3: Translate (7 langs) ──────┤
                      │                                            │
                      └──────── Stage 4: Publish (GDrive + Web) ──┘
```

## 2. Stage Definitions

### Stage 0: Data Collection (기존 유지)
- **Input**: project slug, report type
- **Output**: enriched `project_data.json`
- **Sources**: CoinGecko, Etherscan, DeFiLlama, GitHub, Fear/Greed Index
- **Script**: `collectors/*.py` → `orchestrator.py --stage 0`

### Stage 1: Master Text Generation (.md)
- **Input**: `project_data.json`
- **Output**: `{slug}_{type}_v{N}_{lang}.md` + `{slug}_{type}_v{N}_meta.json`
- **Scripts**: `gen_text_econ.py`, `gen_text_mat.py`, `gen_text_for.py`
- **Quality Gate**: 최소 6,000 단어, 10개 챕터, 5+ 데이터 테이블, 출처 명시

#### .md 품질 기준 (A+ Level)
| 항목 | 기준 | 비고 |
|------|------|------|
| 단어 수 | ECON ≥8,000 / MAT ≥6,000 / FOR ≥5,000 | 영문 기준 |
| 챕터 구조 | 10개 챕터 (H1), 챕터당 2-5 섹션 (H2) | 일관된 번호 체계 |
| 데이터 테이블 | ≥6개 (Markdown table) | 수치 데이터 필수 |
| YAML 프론트매터 | 필수 (아래 스키마 참조) | 메타데이터 + 슬라이드 데이터 |
| 출처 | ≥10개 1차 출처, 데이터 신선도 명시 | 챕터 10에 집중 배치 |
| 투자 의견 | 명확한 등급 + 시나리오 분석 | 3-시나리오 (Bull/Base/Bear) |

#### .md YAML Frontmatter 스키마 (핵심 혁신)

.md 파일 상단에 YAML frontmatter를 삽입하여, 슬라이드/PDF 생성기가 별도 JSON 없이 .md 파일만으로 모든 시각적 요소를 생성할 수 있게 한다.

```yaml
---
# === 기본 메타데이터 ===
report_type: econ          # econ | mat | for
project_name: "Bitcoin"
token_symbol: "BTC"
slug: "bitcoin"
version: 1
lang: en
date: "2026-04-09"
author: "tokenomics-researcher"
reviewer: "CRO"

# === 핵심 평가 (슬라이드 커버용) ===
overall_rating: "A+"       # ECON: A+~F / MAT: 0-100% / FOR: CRITICAL/HIGH/MEDIUM/LOW
rating_label: "Investment Grade"

# === 슬라이드 데이터 (시각화 전용) ===
slide_data:
  # 공통
  executive_summary: "One-line summary for slide 2"
  key_findings:
    - "Finding 1"
    - "Finding 2"
    - "Finding 3"
    - "Finding 4"

  # ECON 전용
  tech_pillars:
    - { name: "Security", score: 95 }
    - { name: "Decentralization", score: 90 }
    - { name: "Scalability", score: 45 }
    - { name: "Ecosystem", score: 85 }
  token_distribution:
    Mining: 100
  risk_factors:
    - { name: "Regulation", probability: 3, impact: 4, severity: "high" }

  # MAT 전용
  maturity_score: 80.25
  maturity_stage: "mature"
  strategic_objectives:
    - { name: "Objective 1", weight: 35, achievement: 85 }

  # FOR 전용
  risk_level: "HIGH"
  manipulation_scores:
    - { type: "Wash Trading", score: 72, severity: "high" }
  market_data:
    current_price: 0.042
    volume_24h: 8500000
---
```

### Stage 2A: Report PDF Generation (A4 Portrait)
- **Input**: `.md` 파일 (frontmatter 포함)
- **Output**: `{slug}_{type}_report_v{N}_{lang}.pdf`
- **Scripts**: `gen_pdf_econ.py`, `gen_pdf_mat.py`, `gen_pdf_for.py`
- **Focus**: 텍스트 가독성, 페이지 레이아웃, 목차, 페이지 번호
- **역할**: .md의 텍스트 콘텐츠를 충실히 재현 + 브랜딩 적용

### Stage 2B: Slide PDF Generation (16:9 Landscape)
- **Input**: `.md` 파일 (frontmatter의 `slide_data` 섹션)
- **Output**: `{slug}_{type}_slide_v{N}_{lang}.pdf`
- **Scripts**: `gen_slide_html_econ.py`, `gen_slide_html_mat.py`, `gen_slide_html_for.py`
- **Focus**: 인포그래픽 시각화, Plotly 차트, 핵심 수치 강조
- **역할**: .md의 데이터를 시각적으로 재해석하여 8장 슬라이드로 압축

#### 핵심 변경: md_to_slide_data 브리지
```python
# 새로운 브리지 모듈
from md_to_slide_data import extract_slide_data

# .md 파일에서 YAML frontmatter + 본문 파싱
slide_data = extract_slide_data("bitcoin_econ_v1_en.md")
# → gen_slide_html_econ.py가 소비하는 dict 반환
```

### Stage 3: Translation (기존 유지)
- **Input**: EN master .md
- **Output**: KO, FR, ES, DE, JA, ZH .md 파일
- **Script**: `translate.py`
- **Note**: YAML frontmatter도 함께 번역 (slide_data 키는 영문 유지)

### Stage 4: Publish (기존 유지)
- GDrive 업로드 + Supabase 등록 + Landing Page 갱신

## 3. File Naming Convention

```
{slug}_{type}_{format}_v{version}_{lang}.{ext}

Examples:
bitcoin_econ_v1_en.md           ← Stage 1: 마스터 텍스트
bitcoin_econ_report_v1_en.pdf   ← Stage 2A: A4 보고서
bitcoin_econ_slide_v1_en.pdf    ← Stage 2B: 16:9 슬라이드
bitcoin_econ_v1_ko.md           ← Stage 3: 한국어 번역
```

## 4. Quality Gate Matrix

| Gate | Stage | 기준 | 담당 |
|------|-------|------|------|
| QG-1 | Stage 1 | .md A+ 품질 (단어수, 테이블, 출처, frontmatter) | AI Agent |
| QG-2 | Stage 2A | PDF 렌더링 정상, 페이지 수 적합 | 자동 검증 |
| QG-3 | Stage 2B | 8 슬라이드 생성, 차트 렌더링, 테마 적용 | 자동 검증 |
| QG-4 | Stage 3 | 번역 품질 검수 (샘플링) | CRO |
| QG-5 | Stage 4 | URL 접근 가능, DB 등록 확인 | 자동 검증 |

## 5. Board Report Format

CRO 보드 보고서를 포함한 모든 내부 보고서는 .md 형식으로 작성한다.

```
blockchain-economics-lab/doc/board-reports/
├── QA-001_initial_pipeline_audit.md
├── QA-002_landing_page_review.md
├── QA-003_report_quality_upgrade.md
├── QA-004_pipeline_3type_audit.md
└── ...
```

### 보드 보고서 .md 템플릿

```markdown
---
report_id: QA-004
date: 2026-04-09
type: board_report
author: CRO
classification: INTERNAL
---

# [Report Title]

## Executive Summary
[2-3 paragraph summary]

## Findings
### Finding 1: [Title]
| 항목 | 결과 | 판정 |
|------|------|------|
| ... | ... | PASS/FAIL/WARN |

## Recommendations
1. **P0 (즉시)**: ...
2. **P1 (2주)**: ...
3. **P2 (1개월)**: ...

## Conclusion
[Final verdict with metrics]
```

## 6. Implementation Roadmap

| Phase | Task | Timeline | Owner |
|-------|------|----------|-------|
| P0 | ECON .md frontmatter 스키마 추가 | Week 1 | tokenomics-researcher |
| P0 | md_to_slide_data.py 브리지 구현 | Week 1 | CRO |
| P1 | MAT/FOR frontmatter 스키마 추가 | Week 2 | defi-researcher / onchain-analyst |
| P1 | Landing Page 3종 탭 UI 구현 | Week 2 | CRO |
| P2 | 7개 언어 번역 파이프라인 통합 | Week 3-4 | report-editor |
| P2 | 자동 품질 게이트 스크립트 | Week 3-4 | CRO |

---

*Approved by CRO Division, Blockchain Economics Lab*
*zhang@coinlab.co.kr | bcelab.xyz*
