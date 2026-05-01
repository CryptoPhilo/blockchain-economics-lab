# Legacy Pipeline (Archived)

이 폴더의 코드는 **2026년 4월 슬라이드 기반 파이프라인 전환(BCE-1073)** 으로 폐기된 구 PDF 기반 보고서 파이프라인입니다.

## 폐기 시점 / 사유

- 폐기 PR: BCE-1082
- 선행 작업:
  - BCE-1086 (#29) — `orchestrator.py`를 슬라이드 단계(`pdf_to_html_slides`)로 교체
  - BCE-1085 (#25) — 신규 `watch_slides.py` + Supabase Storage + slide-pipeline-cron 도입
  - BCE-1089 (#30) — 레거시 cron schedule 비활성화

## 활성 대체

| 구 모듈 | 신규 대체 |
|---------|-----------|
| `orchestrator.py` (.md→번역→PDF) | `scripts/pipeline/orchestrator.py` (텍스트→pdf_to_html_slides) |
| `gen_pdf_*.py` | `scripts/pipeline/pdf_to_html_slides.py` |
| `gen_slide_html_*.py` | NotebookLM에서 직접 언어별 슬라이드 생성 |
| `translate_md.py`, `google_translate_dispatcher.py` | 번역 단계 자체가 제거됨 (NotebookLM 다국어 슬라이드) |
| `watch_drafts.py`, `watch_for_drafts.py` | `scripts/pipeline/watch_slides.py` |
| `ingest_*.py` | watch_slides가 GDrive Slide/ 폴더 직접 처리 |
| `qa_verify*.py` | (PDF QA 단계 제거) |
| `report_runner_policy.py` | (cron 정책 단순화) |
| `daily_pipeline.py` (구) | `scripts/pipeline/daily_pipeline_report.py` (신규 — 운영 리포팅 전용) |

## 실행 금지

- `scripts/pipeline/`에 있던 `from config import ...` 등 사이블링 import는 새 위치(`_legacy/pipeline/`)에서 동작하지 않습니다 (의도된 동작).
- 본 폴더 코드는 **참고용/히스토리 보존용**입니다. 운영에서 호출되는 곳은 없습니다.
- 삭제된 워크플로우: `.github/workflows/for-pipeline-cron.yml`, `report-pipeline-cron.yml`

## git 히스토리

`git log --follow _legacy/pipeline/<파일>` 로 원래 위치(`scripts/pipeline/<파일>`) 시절 이력 추적 가능.
