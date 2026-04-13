---
report_id: QA-005
date: 2026-04-09
type: board_report
author: CRO
classification: INTERNAL - CONFIDENTIAL
title: "다국어 보고서 생산 파이프라인 점검"
---

# CRO Quality Assurance Report QA-005
## 다국어 보고서 생산 파이프라인 점검

> **Report ID**: QA-005 | **Date**: 2026-04-09 | **Author**: CRO Division
> **Directive**: STR-002 Section 4 (Multilingual Production) | **Classification**: INTERNAL

---

## 1. Executive Summary

STR-002 지침은 모든 보고서를 **7개 언어**(EN, KO, FR, ES, DE, JA, ZH)로 생산하도록 규정합니다. EN은 master, KO는 co-original, 나머지 5개는 번역 언어입니다. CRO는 이 다국어 파이프라인의 현재 구현 상태, 실행 가능성, 그리고 STR-002 목표와의 GAP을 종합적으로 점검했습니다.

### 종합 판정

| 구성요소 | 상태 | 판정 |
|---------|------|------|
| config.py 언어 정의 | 7개 언어 코드 정의 완료 | **PASS** |
| translate.py 모듈 구조 | 486 LOC, 함수 구조 완비 | **PASS** |
| 번역 용어집 (Glossary) | 블록체인 핵심 용어 7개 언어 매핑 | **PASS** |
| translate_text() 실제 번역 | **STUB** (`[KO] text` 태그만 부착) | **FAIL** |
| YAML frontmatter 처리 | **미구현** (.md 파일 직접 처리 불가) | **FAIL** |
| Markdown 구조 보존 | **미구현** (테이블/헤더/코드블록 무시) | **FAIL** |
| orchestrator.py 연동 | **translate.py 미호출** | **FAIL** |
| 번역 출력 파일 | **0건** (번역된 .md 파일 없음) | **FAIL** |
| 번역→슬라이드 연계 | **미구현** | **FAIL** |

**전체 다국어 파이프라인 성숙도: 15%** (구조 설계만 완료, 실행 불가)

---

## 2. Component-Level Audit

### 2.1 config.py — 언어 설정

```
LANGUAGES = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh']
MASTER_LANGUAGES = ['en', 'ko']
TRANSLATION_LANGUAGES = ['fr', 'es', 'de', 'ja', 'zh']
```

| 점검 항목 | 결과 | 판정 |
|-----------|------|------|
| 7개 언어 코드 정의 | en/ko/fr/es/de/ja/zh | PASS |
| Master/Translation 구분 | en,ko (master) vs 5개 (translation) | PASS |
| report_filename() 언어 지원 | `{slug}_{type}_v{ver}_{lang}.ext` | PASS |

### 2.2 translate.py — 번역 모듈

| 점검 항목 | 결과 | 판정 |
|-----------|------|------|
| 코드 규모 | 486 LOC | PASS |
| 함수 구조 | translate_text(), translate_dict_values(), translate_all_languages() | PASS |
| 용어집 | GLOSSARY dict: blockchain, smart contract 등 핵심 용어 × 7개 언어 | PASS |
| 필드 분류 | 숫자/날짜/주소 필드 자동 제외, 텍스트 필드만 번역 | PASS |
| **translate_text() 구현** | **STUB: `[{LANG}] {text}` 반환** | **FAIL** |
| **API 연동** | **미구현** (Google Translate / DeepL TODO 주석만 존재) | **FAIL** |
| **apply_glossary_consistency()** | **STUB: 입력 텍스트 그대로 반환** | **FAIL** |
| **.md 파일 파싱** | **미구현** (dict 입력만 지원) | **FAIL** |
| **YAML frontmatter 보존** | **미구현** | **FAIL** |
| **Markdown 구조 보존** | **미구현** (테이블, 헤더, 코드블록 무시) | **FAIL** |
| 에러 처리 | try/except + fallback to source | PASS |
| 병렬 처리 | 미구현 (순차 처리만) | WARN |

### 2.3 orchestrator.py — 번역 호출

| 점검 항목 | 결과 | 판정 |
|-----------|------|------|
| `--lang` CLI 파라미터 | 지원 (단일 언어 또는 'all') | PASS |
| LANGUAGES 목록 import | config.py에서 정상 로드 | PASS |
| **translate.py import** | **없음** (translate 모듈 미사용) | **FAIL** |
| **Stage 1 → 번역 호출** | **없음** (EN .md 생성 후 번역 없이 Stage 2 진입) | **FAIL** |
| `--lang all` 동작 | 7개 PDF 생성하지만 **모두 동일한 EN 내용** | **FAIL** |

### 2.4 출력물 점검

| 점검 항목 | 결과 | 판정 |
|-----------|------|------|
| output/ 디렉토리 .md 파일 | 14개 (모두 `_en.md`) | — |
| 번역된 .md 파일 (ko/fr/es/de/ja/zh) | **0건** | **FAIL** |
| 번역된 PDF 파일 | **0건** | **FAIL** |
| 번역된 슬라이드 PDF | **0건** | **FAIL** |

---

## 3. STR-002 vs 현재 상태 GAP Analysis

| STR-002 요구사항 | 현재 상태 | GAP |
|-----------------|-----------|-----|
| EN master + KO co-original 동시 작성 | EN만 생성 | **CRITICAL** |
| 5개 언어 자동 번역 (FR/ES/DE/JA/ZH) | 번역 함수 stub | **CRITICAL** |
| 번역 전 용어 일관성 검증 | 용어집 존재하나 적용 로직 없음 | **HIGH** |
| 7개 언어 모두 완료 후 출판 승인 | 출판 게이트 미구현 | **HIGH** |
| Forensic 보고서 EN/KO 우선 배포 | 우선 배포 로직 없음 | **MEDIUM** |
| 번역 리드타임: ECON 3일, MAT 2일, FOR 1일 | 번역 자체 불가 | **CRITICAL** |
| .md YAML frontmatter 번역 (slide_data 값) | frontmatter 파싱 없음 | **HIGH** |
| 번역 .md → 다국어 슬라이드 PDF | 연계 미구현 | **HIGH** |

---

## 4. Execution Test Results

### 4.1 translate.py 단독 테스트

```python
translate_report_data({'description': 'Bitcoin is decentralized.'}, 'en', 'ko')
# 결과: {'description': '[KO] Bitcoin is decentralized.'}
```

**판정: FAIL** — 실제 번역이 아닌 언어 태그 prefix만 부착됨.

### 4.2 orchestrator.py `--lang all` 테스트

```bash
python orchestrator.py --type econ --project bitcoin --version 1 --lang all
```

**예상 동작**: 7개 언어 .md + 7개 PDF 생성
**실제 동작**: EN .md 1개 생성 → 동일 EN 내용으로 7개 PDF 생성 (파일명만 lang 코드 다름)

### 4.3 .md → 번역 → 슬라이드 연계 테스트

**테스트 불가** — translate.py가 .md 파일을 직접 처리하지 못하며, YAML frontmatter 파싱 기능이 없음.

---

## 5. Issues Found

| ID | 심각도 | 대상 | 설명 |
|----|--------|------|------|
| I-1 | **CRITICAL** | translate.py | translate_text()가 stub. 실제 번역 API 미연동 (Google/DeepL) |
| I-2 | **CRITICAL** | orchestrator.py | translate.py 미호출. Stage 1 → Stage 2 사이에 번역 단계 없음 |
| I-3 | **CRITICAL** | translate.py | .md 파일 직접 처리 불가. dict 입력만 지원 |
| I-4 | **HIGH** | translate.py | YAML frontmatter 파싱/보존 미구현 |
| I-5 | **HIGH** | translate.py | Markdown 구조 보존 미구현 (테이블, 헤더, 코드블록) |
| I-6 | **HIGH** | translate.py | slide_data 키 보존 + 값 번역 로직 없음 |
| I-7 | **HIGH** | translate.py | apply_glossary_consistency() stub 상태 |
| I-8 | **MEDIUM** | orchestrator.py | `--lang all` 시 모든 PDF가 동일 EN 내용 |
| I-9 | **MEDIUM** | translate.py | 병렬 번역 미지원 (7개 언어 순차 처리) |
| I-10 | **LOW** | translate.py | 텍스트 필드 감지 휴리스틱이 fragile (길이+공백 기반) |

---

## 6. Recommendations

### 6.1 P0 즉시 조치 (1주 이내)

1. **번역 API 연동 구현**: translate_text()에 실제 번역 엔진 연결
   - 옵션 A: Google Cloud Translation API (v3, Neural MT)
   - 옵션 B: DeepL API (유럽 언어 우수)
   - 옵션 C: Anthropic Claude API (컨텍스트 인지 번역, 블록체인 전문용어 처리 우수)
   - **권장: 옵션 C** — 이미 에이전트 인프라에서 사용 중이며, .md 구조를 이해하고 보존 가능

2. **orchestrator.py에 번역 단계 삽입**:
   ```
   Stage 1 (EN .md 생성) → Stage 1.5 (번역) → Stage 2A/2B (PDF/Slide)
   ```

### 6.2 P1 단기 과제 (2주 이내)

3. **.md 파일 번역 모듈 구현** (`translate_md.py`):
   - YAML frontmatter 파싱 (md_to_slide_data.py의 parse_frontmatter 재활용)
   - frontmatter 값 번역 (키는 영문 유지)
   - Markdown 본문 번역 (구조 보존: 테이블, 헤더, 코드블록 스킵)
   - 출력: `{slug}_{type}_v{ver}_{lang}.md`

4. **용어집 적용 로직 구현**: GLOSSARY dict 기반 번역 후처리

5. **KO co-original 워크플로우**: EN과 KO를 동시 생성하는 듀얼 마스터 파이프라인

### 6.3 P2 중기 과제 (1개월 이내)

6. **번역 품질 검증 게이트**: 번역 결과 자동 QA (글자 수 비율, 용어 일관성, 구조 보존)
7. **병렬 번역**: asyncio 또는 ThreadPoolExecutor로 7개 언어 동시 번역
8. **번역 캐시**: 동일 문장 재번역 방지 (비용/시간 절감)
9. **Forensic 우선 배포**: EN/KO 2개 언어 먼저 배포 → 24시간 내 5개 언어 추가

---

## 7. Architecture Recommendation

STR-003 v2 파이프라인에 번역 단계를 공식 통합:

```
Stage 0: Data Collection
    ↓
Stage 1: EN Master .md Generation (6,000+ words, YAML frontmatter)
    ↓
Stage 1.5: Translation (NEW)
    ├── KO: co-original (AI 번역 + CRO 검수)
    ├── FR: DeepL/Claude translation
    ├── ES: DeepL/Claude translation
    ├── DE: DeepL/Claude translation
    ├── JA: Claude translation (블록체인 전문용어)
    └── ZH: Claude translation (간체자)
    ↓
Stage 2A: Report PDF × 7 languages
Stage 2B: Slide PDF × 7 languages (via md_to_slide_data bridge)
    ↓
Stage 3: Quality Gate (7개 언어 모두 통과 시 배포 승인)
    ↓
Stage 4: Publish (GDrive + Supabase + Landing Page)
```

### 번역 방식별 비교

| 방식 | 장점 | 단점 | 비용 | 권장도 |
|------|------|------|------|--------|
| Google Translate API | 안정적, 130+ 언어 | 블록체인 용어 부정확 | $20/1M chars | ★★★☆☆ |
| DeepL API | 유럽 언어 최우수 | JA/ZH 지원 제한적 | $25/1M chars | ★★★★☆ |
| Claude API | 구조 보존, 전문용어 이해 | 비용 높음 | ~$15/보고서 | ★★★★★ |
| 하이브리드 (Claude + DeepL) | 최적 품질/비용 밸런스 | 구현 복잡 | ~$10/보고서 | ★★★★☆ |

---

## 8. Conclusion

**다국어 파이프라인은 현재 구조 설계(15%)만 완료된 상태이며, 실제 번역 기능은 전혀 작동하지 않습니다.**

config.py의 7개 언어 정의, translate.py의 함수 구조와 용어집은 준비되어 있으나, 핵심인 `translate_text()` 함수가 stub 상태이고, orchestrator.py에서 번역 모듈을 호출하지 않으며, .md 파일 직접 번역도 불가합니다. 결과적으로 `--lang all` 실행 시 7개 PDF가 생성되지만 모두 동일한 영어 내용입니다.

**우선 과제**: Claude API 기반 .md 파일 번역 모듈 구현 및 orchestrator Stage 1.5 삽입이 가장 시급합니다. 이는 기존 md_to_slide_data.py 브리지의 frontmatter 파서를 재활용하여 빠르게 구현할 수 있습니다.

| 지표 | 현재 | 목표 |
|------|------|------|
| 번역 가능 언어 | 0/7 | 7/7 |
| 번역된 .md 파일 | 0건 | 프로젝트당 6건 (EN 제외) |
| 번역된 슬라이드 PDF | 0건 | 프로젝트당 6건 |
| 파이프라인 성숙도 | 15% | 100% |
| 예상 구현 기간 | — | P0: 1주, P1: 2주, P2: 4주 |

---

*Prepared by CRO Division, Blockchain Economics Lab*
*zhang@coinlab.co.kr | bcelab.xyz*
