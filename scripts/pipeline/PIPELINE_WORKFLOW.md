# BCE Lab 보고서 생산 파이프라인 워크플로

## 1. 워크플로 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                    Daily Pipeline (Orchestrator)                │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                      ┌─────────────────┐
                      │  Phase A: Data  │
                      │  Ingestion      │
                      └────────┬────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  auto-analysis       │
                    │  (enriched data)     │
                    └────────┬─────────────┘
                             │
                             ▼
                    ┌──────────────────────┐
         Phase B-D  │  report-pipeline     │
                    │  (7-language PDFs)   │
         CRO Agent  └────────┬─────────────┘
         Validation          │
                             ▼
                    ┌──────────────────────┐
                    │  gdrive-upload       │
                    │  (Drive URLs)        │
                    └────────┬─────────────┘
                             │
                             ▼
                    ┌──────────────────────┐
                    │  resend-email        │
                    │  (email delivery)    │
                    └──────────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │       Independent Slides (Manual or Parallel)            │
    │  slide-econ  /  slide-mat  /  slide-for                 │
    │  (각 독립 실행, 메타데이터 JSON 입력)                     │
    └──────────────────────────────────────────────────────────┘
```

---

## 2. 스킬 의존성 매트릭스

### auto-analysis
- **역할**: 원본 프로젝트 데이터 분석 및 데이터 정제
- **입력**: `project_data.json` (시장 데이터, 핵심 지표)
- **출력**: `enriched_data.json` (분석 결과, 메트릭 추강화)
- **처리 시간**: ~5분
- **후행 스킬**: `report-pipeline`
- **에러 처리**: 데이터 검증 실패 시 Phase A에서 정지

### report-pipeline
- **역할**: 다국어 보고서 생성 (한국어, 영어, 중국어, 일본어, 스페인어, 불어, 독일어)
- **입력**: `enriched_data.json` (auto-analysis 출력)
- **출력**: 7개 PDF 파일 (각 언어별, ~20-30MB)
  - `report_ko.pdf`, `report_en.pdf`, `report_zh.pdf`, ...
- **처리 시간**: ~15-20분
- **후행 스킬**: `gdrive-upload`
- **병렬 처리**: 각 언어별 독립적 렌더링 가능
- **의존성**: auto-analysis 완료 필수

### gdrive-upload
- **역할**: 생성된 PDF를 Google Drive에 업로드
- **입력**: 7개 PDF 파일 경로
- **출력**: Google Drive URLs (각 파일별 공유 링크)
- **처리 시간**: ~3분
- **후행 스킬**: `resend-email`
- **인증**: OAuth 토큰 (재인증 불필요, 자동 갱신)
- **스토리지**: `/reports/2026-04/` 폴더 구조

### resend-email
- **역할**: 생성된 보고서 링크를 메일 수신자에게 전송
- **입력**: Google Drive URLs + 보고서 메타데이터 (제목, 요약, 생성 일시)
- **출력**: 이메일 배송 확인 (배송 통계)
- **처리 시간**: ~1분
- **수신자**: 설정된 구독자 리스트
- **템플릿**: HTML 이메일 (브랜딩 포함)
- **추적**: Resend API 배송 로그

### slide-econ / slide-mat / slide-for
- **역할**: 경제학, 수학, 포레스팅 주제별 슬라이드 생성 (독립 실행)
- **입력**: `slide_metadata.json` (주제, 데이터 포인트, 스타일)
- **출력**: `slides_econ.pdf`, `slides_mat.pdf`, `slides_for.pdf`
- **처리 시간**: 각 3-5분
- **의존성**: 없음 (auto-analysis 결과 선택적 활용 가능)
- **실행 방식**: 독립 수동 호출 또는 Phase E에서 병렬 실행

---

## 3. 일일 자동화 흐름 (Phase 매핑)

### Phase A: Data Ingestion & Validation
- **시간**: 06:00 KST
- **작업**: 외부 소스(API, DB)에서 `project_data.json` 수집
- **스킬 호출**: (스킬 불필요, 데이터 수집 레이어)
- **산출물**: `project_data.json` 준비 완료
- **조건**: 데이터 무결성 검증 통과

### Phase B: Auto-Analysis
- **시간**: 06:30 KST
- **작업**: `auto-analysis` 스킬 실행
- **입력**: Phase A의 `project_data.json`
- **출력**: `enriched_data.json`
- **CRO 에이전트 위치**: ✓ 수동 검증 포인트
  - CRO가 분석 결과 검토 및 검증
  - 이상 데이터 또는 부정확성 발견 시 단계 반복
- **조건**: CRO 승인 (자동 또는 수동)

### Phase C: Report Generation
- **시간**: 07:00-07:20 KST
- **작업**: `report-pipeline` 스킬 실행 (7개 언어 병렬)
- **입력**: Phase B의 `enriched_data.json`
- **출력**: 7개 PDF 파일
- **병렬화**: 언어별 독립적 렌더링
- **조건**: Phase B 완료

### Phase D: PDF Validation & Optimization
- **시간**: 07:20-07:30 KST
- **작업**: 생성된 PDF 무결성 검증, 파일 크기 최적화
- **스킬 호출**: (검증 로직, 스킬 불필요)
- **산출물**: 최종 PDF 확인

### Phase E: Google Drive Upload
- **시간**: 07:30-07:35 KST
- **작업**: `gdrive-upload` 스킬 실행
- **입력**: 최종 PDF 파일 7개
- **출력**: Google Drive URLs
- **동시에**: `slide-econ`, `slide-mat`, `slide-for` 병렬 실행 가능
- **조건**: Phase D 완료

### Phase F: Email Distribution
- **시간**: 07:35-07:40 KST
- **작업**: `resend-email` 스킬 실행
- **입력**: Google Drive URLs + 메타데이터
- **출력**: 이메일 배송 완료 확인
- **조건**: Phase E 완료
- **결과**: 파이프라인 완료, 구독자에게 보고서 배포

---

## 4. 수동 실행 시나리오

### 시나리오 A: 단건 보고서 생성
**상황**: 특정 데이터에 대해 즉시 보고서 필요

```
입력: project_data.json (수동 제공)
  ↓
auto-analysis (수동 실행)
  ↓
report-pipeline (수동 실행, 전체 7개 언어)
  ↓
gdrive-upload (선택적, 로컬 저장 가능)
  ↓
resend-email (선택적)
```

**실행 명령**:
```bash
# Phase B만 실행
python scripts/orchestrator.py --phase B --manual

# Phase C 실행 (자동 분석 결과 재활용)
python scripts/orchestrator.py --phase C --manual
```

### 시나리오 B: 특정 언어 재생성
**상황**: 한국어 보고서만 재생성 필요 (예: 번역 오류 수정)

```
입력: enriched_data.json (기존 사용)
  ↓
report-pipeline --language ko (언어 필터)
  ↓
gdrive-upload --replace (기존 파일 덮어쓰기)
  ↓
resend-email (선택적)
```

**실행 명령**:
```bash
python scripts/orchestrator.py --phase C --language ko --manual
```

### 시나리오 C: 슬라이드만 생성
**상황**: 보고서는 기존 것 사용, 슬라이드만 새로 생성

```
입력: slide_metadata.json (수동 제공)
  ↓
slide-econ (독립 실행)
slide-mat  (독립 실행)
slide-for  (독립 실행)
  ↓
gdrive-upload (선택적)
  ↓
resend-email (선택적, 슬라이드 링크만 포함)
```

**실행 명령**:
```bash
python scripts/orchestrator.py --slide econ,mat,for --manual
```

---

## 5. CRO 에이전트 위치 및 역할

### CRO 에이전트 설정
- **실행 모드**: `manual-invoke-only` (자동 실행 불가)
- **데이터 접근**: read-only (검증 및 승인 목적)
- **위치**: Phase B (Auto-Analysis 후)

### Phase B 검증 워크플로
```
auto-analysis 완료
  ↓
enriched_data.json 생성
  ↓
CRO 에이전트 호출 (수동)
  ├─ 데이터 무결성 검증
  ├─ 이상 값 감지 (outliers, NaN, 타입 오류)
  ├─ 논리적 일관성 검증 (예: 합계 검증)
  └─ 승인 결과 반환
    ├─ ✓ APPROVED → Phase C 진행
    ├─ ✗ REJECTED → Phase A 재시작 (데이터 재수집)
    └─ ⚠ REVIEW → 수동 개입 필요
```

### CRO 검증 체크리스트
- [ ] JSON 스키마 유효성
- [ ] 필수 필드 존재 여부
- [ ] 수치 범위 (min/max 범위 내)
- [ ] 날짜 형식 및 순서
- [ ] 통계 합계 일치성
- [ ] 언어 필드 완전성

---

## 6. 오류 처리 및 롤백

### 에러 발생 지점별 대응

| Phase | 오류 유형 | 대응 조치 |
|-------|---------|---------|
| A | 데이터 수집 실패 | 재시도 (3회), 최종 실패 시 관리자 알림 |
| B | 분석 오류 | Phase A 재시작 또는 CRO 수동 개입 |
| C | PDF 렌더링 오류 | 해당 언어만 재시도, 다른 언어 계속 진행 |
| D | PDF 무결성 오류 | Phase C 재시작 |
| E | Drive 업로드 실패 | 재인증 시도, 실패 시 로컬 저장 |
| F | 이메일 배송 실패 | 재시도 (지수 백오프), 로그 기록 |

---

## 7. 설정 및 실행

### 필수 환경 변수
```bash
GOOGLE_DRIVE_FOLDER_ID="{Drive 폴더 ID}"
RESEND_API_KEY="{Resend API 키}"
PROJECT_DATA_SOURCE="http://api.example.com/data"
CRO_VALIDATION_REQUIRED=true  # Phase B 자동 검증 필수 여부
```

### Orchestrator 실행 명령어
```bash
# 전체 파이프라인 자동 실행
python scripts/orchestrator.py --full

# 특정 Phase만 실행
python scripts/orchestrator.py --phase {A|B|C|D|E|F}

# 특정 언어만 생성
python scripts/orchestrator.py --language ko,en,zh

# 슬라이드 생성 (독립)
python scripts/orchestrator.py --slide econ,mat,for

# 수동 검증 모드 (CRO 승인 대기)
python scripts/orchestrator.py --full --manual
```

### 로그 및 모니터링
- **로그 경로**: `/logs/pipeline_{YYYYMMDD}.log`
- **모니터링**: Phase별 실행 시간, 오류율, 배송 통계
- **알림**: Slack 채널 `#bce-pipeline` 에 Phase F 완료 시 통지

---

**문서 작성일**: 2026-04-12  
**버전**: 1.0  
**관리자**: BCE Lab Engineering Team
