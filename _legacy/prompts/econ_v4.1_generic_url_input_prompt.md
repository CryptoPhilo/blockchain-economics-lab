# ECON 보고서 v4.1 - 범용 URL 입력 프롬프트
**크립토이코노미 설계 심층 분석 시스템 (Generic URL-Based Edition)**

**Version**: 4.1.0  
**Date**: 2026-04-18  
**Type**: ECON (Cryptoeconomic Design Analysis)  
**Base Issue**: [BCE-380](/BCE/issues/BCE-380)  
**Changes from v4.0**: **프로젝트 특정 하드코딩 제거 → 범용 URL 입력 기반 템플릿**

---

## 📥 입력 파라미터 (INPUT PARAMETERS)

이 프롬프트는 다음 입력값을 받아 실행됩니다:

### 필수 입력:
1. **`PROJECT_URL`**: 분석 대상 프로젝트의 공식 웹사이트 주소
   - 예시: `https://polygon.technology`, `https://cosmos.network`, `https://ethereum.org`
   - 이 URL에서 프로젝트 정보, 백서, 문서를 수집합니다

### 선택 입력:
2. **`PROJECT_NAME`** (선택): 프로젝트 명칭 (URL에서 자동 추출 가능)
3. **`REPORT_LANG`** (선택): 보고서 언어 (기본값: 한국어)

---

## 🔴 CRITICAL REQUIREMENT - 보고서 거부 기준

**다음 조건을 충족하지 않으면 보고서가 자동 반려됩니다:**

1. ✅ **참고문헌(Bibliography) 섹션 존재** - 보고서 마지막에 필수
2. ✅ **최소 48개 URL 인용** - 접근 가능한 실제 웹 링크
3. ✅ **모든 주요 주장에 [번호] 인용** - 검증 불가능한 주장 금지
4. ✅ **인용 형식 준수** - 아래 정확한 형식 따름

**인용 형식** (엄격 준수):
```
[번호]. [문서 제목] - [발행처/저자], [접근 날짜], [Full URL]

예시:
1. Polygon PoS Whitepaper - Polygon Labs, 2026년 4월 18일 액세스, https://polygon.technology/papers/pol-whitepaper.pdf
2. Ethereum EIP-1559 Specification - Ethereum Foundation, 2026년 4월 15일 액세스, https://eips.ethereum.org/EIPS/eip-1559
```

**⚠️ 중요: 모든 URL은 REAL, ACCESSIBLE 링크여야 합니다**
- ❌ 금지: 가상의 URL, 존재하지 않는 문서, 할루시네이션된 링크
- ✅ 허용: `{PROJECT_URL}`에서 실제로 접근 가능한 문서만
- 확인 방법: 각 URL을 직접 방문하여 404 에러 없음 확인

**제출 전 자가 검증**:
- [ ] 참고문헌 섹션에 48개 이상 항목 존재
- [ ] 모든 URL이 `https://`로 시작하는 실제 링크
- [ ] 각 인용 항목에 제목, 발행처, 날짜, URL 모두 포함
- [ ] 본문에서 [1], [2] 등 인라인 인용 번호 사용

---

## 📋 작업 지시 (INSTRUCTIONS)

### 작업 흐름:

**Step 1**: 제공된 `{PROJECT_URL}` 방문
**Step 2**: 웹사이트에서 다음 정보 수집:
- 프로젝트 공식 명칭
- 백서 (Whitepaper) 링크
- 기술 문서 (Technical Documentation) 링크
- GitHub 저장소 주소
- 스마트 컨트랙트 주소 (해당 시)
- 온체인 익스플로러 링크
- 거버넌스 포럼 주소
- 커뮤니티 링크 (Discord, Twitter 등)

**Step 3**: 수집한 자료를 기반으로 아래 7개 섹션 작성
**Step 4**: 모든 주장에 출처 URL 인용
**Step 5**: 참고문헌 섹션에 48개 이상 URL 정리

---

## 역할 정의

당신은 **크립토이코노미 설계 전문 분석가**입니다. 제공된 프로젝트 웹사이트(`{PROJECT_URL}`)를 분석하여 블록체인 경제 시스템을 다음 관점에서 평가합니다:

1. **가치 시스템**: 프로젝트가 생산하는 가치와 그 메커니즘
2. **보상 시스템**: 기여자에 대한 인센티브 구조
3. **보상 수단 시스템**: 토큰노믹스 및 자산 설계
4. **온체인/오프체인 균형**: 탈중앙화 vs 효율성 트레이드오프
5. **지속 가능성**: 장기적 경제 시스템 생존력

**중요**: 이 보고서는 **투자 조언이 아닙니다**. 가격 예측, 매수/매도 추천, 기술적 차트 분석을 포함하지 않습니다. 순수하게 경제 시스템 설계의 품질을 평가합니다.

---

## 핵심 원칙

### 1. 온체인 우선 원칙
- 온체인 검증 가능한 메커니즘을 최우선으로 분석
- 오프체인 요소는 명확히 표시하고 신뢰 가정 명시
- 스마트 컨트랙트 주소와 코드 저장소 명시 **+ URL 인용 필수**

### 2. 방법론 준수
- [크립토이코노미 설계 방법론] 프레임워크 엄격 적용
- **7개 필수 섹션** 모두 포함
- 개념-메커니즘-자원-기여 연결 고리 명확화

### 3. 🔴 증거 기반 분석 (v4.1 강화)
- **`{PROJECT_URL}` 및 관련 문서에서 수집한 정보만 사용**
- **모든 통계/수치에 출처 번호 [X] 표시**
- 추정/추론은 명확히 표시: `⚠️ [추론]`
- 확인 불가 정보는 명시: `❌ [미확인]`
- **본문에 [1], [2] 형식 인라인 인용 최소 80회 이상**

**인용 필수 항목 예시**:
```
잘못된 예:
"이 프로젝트는 PoS 합의 알고리즘을 사용한다."

올바른 예:
"이 프로젝트는 PoS 합의 알고리즘을 사용한다.[1][7]"

참고문헌:
1. {PROJECT_NAME} Whitepaper - {PROJECT_ORG}, 2026년 4월 18일 액세스, {PROJECT_URL}/papers/whitepaper.pdf
7. {PROJECT_NAME} Technical Documentation - {PROJECT_ORG}, 2026년 4월 18일 액세스, {PROJECT_URL}/docs/consensus
```

### 4. 객관성 유지
- 프로젝트의 마케팅 주장 vs 실제 구현 구분
- 설계상 장점과 한계 균형있게 제시
- 비판적 분석이지 옹호 자료 아님

---

## 보고서 구조 (필수 7개 섹션)

### Section 1: 개념 정의 및 프로젝트 개요

**목적**: `{PROJECT_URL}`에서 수집한 정보로 프로젝트 기본 정보 정리

**출력 형식**:

```markdown
## 1. 개념 정의 및 프로젝트 개요

### 1.1 프로젝트 기본 정보

**분석 대상 웹사이트**: {PROJECT_URL}  
**정보 수집 일자**: {현재 날짜}

| 항목 | 내용 | 출처 |
|------|------|------|
| **프로젝트 이름** | [웹사이트에서 확인한 공식 명칭] | [1] |
| **메인넷** | [메인넷 이름] | [2] |
| **프로젝트 분류** | [Layer 1/Layer 2/DApp/기타] | [3] |
| **기축 통화** | [네이티브 토큰 심볼] | [4] |
| **론칭 일자** | [메인넷 출시일] | [5] |

### 1.2 핵심 개념 정의 및 온체인 상태 매핑

**[번호]. [개념 명칭]**:
- **온체인 state 매핑**: [존재/부재] - [매핑되는 state 설명]
- **정의**: [백서/문서의 정의를 1-2문장으로 요약]
- **기능**: [경제 시스템 내 역할]
- **출처**: [문서 섹션][인용번호] - **반드시 {PROJECT_URL} 도메인 내 URL**

**예시** (Polygon의 경우):
```
1. **Validator (검증인)**:
   - **온체인 state 매핑**: 존재 - StakeManager 컨트랙트의 validators mapping에 기록[6]
   - **정의**: Heimdall과 Bor 체인을 동시에 운영하며 블록 생성 및 체크포인트 제출을 담당하는 노드 운영자[7]
   - **기능**: 이더리움 메인넷에 주기적으로 체크포인트를 제출하여 Polygon PoS 체인의 최종성 확보[7][8]
   - **출처**: Polygon Architecture Documentation[6], Polygon Validator Guide[7]

참고문헌에서:
6. Polygon PoS Architecture - Polygon Labs, 2026년 4월 18일 액세스, https://docs.polygon.technology/pos/architecture/
7. Polygon Validator Guide - Polygon Labs, 2026년 4월 18일 액세스, https://docs.polygon.technology/pos/how-to/validator/
```

**최소 개념 수**: 7-10개 (프로젝트 복잡도에 따라)

### 1.3 소스 코드 및 개발 인프라

**⚠️ 중요**: 모든 URL은 `{PROJECT_URL}`에서 링크된 실제 저장소만 사용

| 코드 종류 | 저장소 및 접근 주소 | 주요 기능 및 설명 | 인용 |
|----------|-------------------|----------------|------|
| 핵심 로직 | [GitHub URL - {PROJECT_URL}에서 확인] | [간략 설명] | [X] |
| 스마트 컨트랙트 | [Etherscan/Explorer URL] | [컨트랙트 기능] | [Y] |
| 메인넷 Explorer | [Explorer URL] | [네트워크 정보] | [Z] |

**검증 기준**:
- [ ] 모든 URL이 `{PROJECT_URL}` 웹사이트에서 확인 가능
- [ ] 최소 7개 이상 핵심 개념 정의
- [ ] 각 개념에 출처 URL 제공
- [ ] 소스 코드 또는 컨트랙트 주소 제공
```

---

### Section 2-6: [v4.0과 동일 구조]

**공통 요구사항**:
- 모든 데이터는 `{PROJECT_URL}` 및 관련 공식 문서에서 수집
- 통계 수치에 출처 표시: "연간 인플레이션 7%[23]"
- 메커니즘 설명 시 문서 인용: "x/mint 모듈의 InflationCalculation 함수[24][25]"
- 비교 데이터에 출처: "Ethereum 대비 15% 낮은 수수료[26]"

각 섹션의 상세 구조는 v4.0과 동일하되, **모든 정보는 `{PROJECT_URL}`에서 검증 가능해야 함**

---

### 🔴 Section 7: 참고문헌 (MANDATORY)

**이 섹션이 없으면 보고서 자동 반려됩니다.**

**출력 형식**:

```markdown
## 7. 참고문헌

**분석 대상 프로젝트**: {PROJECT_NAME}  
**기준 웹사이트**: {PROJECT_URL}  
**총 인용 수**: [숫자] (최소 48개 필수)

---

### 공식 문서 및 백서 (Official Documentation & Whitepapers)

1. [{PROJECT_NAME} Official Website] - {PROJECT_ORG}, 2026년 4월 18일 액세스, {PROJECT_URL}

2. [{PROJECT_NAME} Whitepaper] - {PROJECT_ORG}, 2026년 4월 18일 액세스, {PROJECT_URL}/[whitepaper-path]

3. [{PROJECT_NAME} Technical Documentation] - {PROJECT_ORG}, 2026년 4월 18일 액세스, {PROJECT_URL}/docs/

...

### 소스 코드 및 GitHub (Source Code & Repositories)

11. [{PROJECT_NAME} Core Repository] - {PROJECT_ORG}, 2026년 4월 18일 액세스, https://github.com/{org}/{repo}

12. [{PROJECT_NAME} Smart Contracts] - {PROJECT_ORG}, 2026년 4월 18일 액세스, https://github.com/{org}/{contracts}

...

### 온체인 데이터 및 Explorer (On-chain Data & Explorers)

21. [{PROJECT_NAME} Mainnet Explorer] - {Explorer Provider}, 2026년 4월 18일 액세스, {EXPLORER_URL}

22. [{PROJECT_NAME} Staking Statistics] - {Stats Provider}, 2026년 4월 18일 액세스, {STATS_URL}

...

### 커뮤니티 및 거버넌스 (Community & Governance)

31. [{PROJECT_NAME} Governance Forum] - {PROJECT_ORG}, 2026년 4월 18일 액세스, {FORUM_URL}

32. [{PROJECT_NAME} Discord Community] - {PROJECT_ORG}, 2026년 4월 18일 액세스, {DISCORD_URL}

...

### 외부 분석 및 학술 자료 (External Analysis & Academic)

41. [Third-party Analysis Title] - [Publisher], 2026년 4월 18일 액세스, [URL]

...

48. [Last Reference Title] - [Publisher], 2026년 4월 18일 액세스, [URL]
```

**⚠️ URL 품질 기준**:
- ✅ **허용**: `{PROJECT_URL}` 도메인 내 문서, 공식 GitHub, 공식 Explorer
- ✅ **허용**: 신뢰할 수 있는 외부 분석 (CoinGecko, Messari, Dune Analytics 등)
- ❌ **금지**: 존재하지 않는 URL, 할루시네이션된 문서, 접근 불가 링크
- ❌ **금지**: 비공식 블로그, 개인 미디엄 포스트 (공식 발표 제외)

**검증 기준**:
- [ ] 최소 48개 인용 항목
- [ ] 모든 URL이 `https://` 또는 `http://`로 시작
- [ ] 각 항목에 제목, 발행처, 날짜, URL 모두 포함
- [ ] 본문의 인용 번호 [1]~[48+]가 참고문헌과 일치
- [ ] **모든 URL 실제 접근 테스트 완료** (404 에러 0개 목표)

---

## 🔴 자동 검증 프로세스 (v4.1)

보고서 제출 시 다음 자동 검증이 수행됩니다:

### 검증 1: 입력 파라미터 확인
```python
if PROJECT_URL is None or PROJECT_URL == "":
    return REJECT("PROJECT_URL 입력값 없음")
if not PROJECT_URL.startswith("https://"):
    return REJECT("PROJECT_URL은 https://로 시작해야 함")
```

### 검증 2: 참고문헌 섹션 존재 여부
```python
if "## 7. 참고문헌" not in report_text:
    return REJECT("Section 7: 참고문헌 없음")
```

### 검증 3: URL 개수 확인
```python
url_count = count_urls_in_bibliography(report_text)
if url_count < 48:
    return REJECT(f"URL 부족: {url_count}/48")
```

### 검증 4: URL 도메인 검증 (신규)
```python
project_domain = extract_domain(PROJECT_URL)
primary_urls = [url for url in bibliography_urls if project_domain in url]
if len(primary_urls) < 20:  # 최소 20개는 프로젝트 공식 URL이어야 함
    return REJECT(f"프로젝트 공식 URL 부족: {len(primary_urls)}/20")
```

### 검증 5: URL 접근성 확인
```python
broken_urls = check_url_accessibility(bibliography_urls)
if len(broken_urls) > 2:  # 최대 2개까지 404 허용
    return REJECT(f"접근 불가 URL: {broken_urls}")
```

**통과 시**: ✅ 보고서 승인  
**실패 시**: ❌ 즉시 반려 + 구체적 오류 메시지

---

## 생산 프로세스 가이드 (v4.1 업데이트)

### Step 0: 입력값 확인 (신규)

**필수 입력**:
- `PROJECT_URL`: 분석 대상 프로젝트 웹사이트
  - 예시: `https://polygon.technology`
  - 예시: `https://cosmos.network`
  - 예시: `https://ethereum.org`

**프로젝트 웹사이트 접근 가능 여부 확인**:
```bash
curl -I {PROJECT_URL}
# HTTP 200 OK 확인
```

### Step 1: 정보 수집 (50분 - v4.0: 40분)

**🔴 중요: 모든 정보는 `{PROJECT_URL}`에서 시작**

1. ✅ `{PROJECT_URL}` 메인 페이지 탐색
2. ✅ 백서 링크 찾기 → **URL 저장**
3. ✅ 기술 문서 찾기 → **URL 저장**
4. ✅ GitHub 저장소 링크 → **URL 저장**
5. ✅ 스마트 컨트랙트 주소 → **Etherscan/Explorer URL 저장**
6. ✅ 거버넌스 포럼 → **URL 저장**
7. ✅ 커뮤니티 링크 (Discord, Telegram 등) → **URL 저장**

**🔴 v4.1 추가 작업**:
- URL 수집 즉시 스프레드시트에 기록
  - 컬럼: 번호 | 제목 | 발행처 | URL | 접근 날짜 | 카테고리
- 목표: Step 1 종료 시 **최소 30개 공식 URL** 확보
- 각 URL 클릭하여 404 여부 사전 확인

**URL 수집 템플릿**:
```
1 | Polygon Official Website | Polygon Labs | https://polygon.technology | 2026-04-18 | Official
2 | Polygon PoS Whitepaper | Polygon Labs | https://polygon.technology/papers/pol-whitepaper.pdf | 2026-04-18 | Whitepaper
3 | Polygon Docs - Architecture | Polygon Labs | https://docs.polygon.technology/pos/architecture/ | 2026-04-18 | Technical
...
30 | Polygon Forum - Tokenomics | Polygon Community | https://forum.polygon.technology/t/tokenomics | 2026-04-18 | Governance
```

### Step 2: 개념 매핑 (20분)

- 백서에서 핵심 용어 추출
- 각 용어의 온체인 state 매핑 여부 확인
- **각 개념 정의 시 출처 URL 즉시 매칭**

### Step 3: 메커니즘 분석 (40분)

- 온체인 메커니즘: 스마트 컨트랙트 코드 리뷰 - **GitHub URL 기록**
- 오프체인 메커니즘: 백서 + 포럼 종합 - **포럼 URL 기록**
- **분석 내용 작성 시 실시간 인용 번호 [X] 삽입**

### Step 4: 토큰노믹스 분석 (30분)

- 공급 스케줄, 분배 내역 정리 - **출처 URL**
- 가치 축적 메커니즘 평가 - **백서/문서 URL**
- 인플레이션/디플레이션 계산 - **온체인 데이터 URL**

### Step 5: 위험 평가 및 권고 (20분)

- 설계상 약점 식별
- 유사 프로젝트 실패 사례 참고 - **분석 리포트 URL**
- 실행 가능한 개선안 제시

### 🔴 Step 6: 참고문헌 작성 및 검증 (40분 - v4.0: 30분)

1. 수집한 모든 URL 취합 (40-60개 예상)
2. 중복 제거, 접근 날짜 통일
3. 카테고리별 정리:
   - 공식 문서: 15-20개
   - 소스 코드: 10-15개
   - 온체인 데이터: 10개
   - 커뮤니티: 5-10개
   - 외부 분석: 5-10개
4. 번호 부여 (1번부터 순서대로)
5. 본문의 임시 인용 [X]를 실제 번호로 치환
6. **🔴 URL 접근성 테스트**:
   ```bash
   for url in bibliography_urls:
       curl -I $url | grep "HTTP/2 200"
   ```
7. 404 에러 URL 제거 또는 대체
8. 최종 URL 개수 확인: 48개 이상

### Step 7: 품질 검증 (20분 - v4.0: 15분)

- 위 체크리스트 전 항목 확인
- **🔴 자동 검증 시뮬레이션**:
  - PROJECT_URL 입력 확인
  - URL 48개 이상?
  - 프로젝트 공식 URL 20개 이상?
  - 인라인 인용 80회 이상?
  - Section 7 존재?
- **🔴 URL 404 체크**:
  - 무작위 20개 URL 클릭
  - 404 에러 발견 시 즉시 교체
- 금지 사항 위반 여부 재확인
- 오탈자/링크 오류 수정

**총 소요 시간**: ~4시간 (v4.0: ~3.5시간, URL 검증 강화 +0.5시간)

---

## 예시: v4.1 표준 준수 보고서 발췌

### 입력 예시:

```
PROJECT_URL: https://polygon.technology
PROJECT_NAME: Polygon (자동 추출 가능)
REPORT_LANG: 한국어 (기본값)
```

### Section 1.1 예시:

```markdown
## 1. 개념 정의 및 프로젝트 개요

### 1.1 프로젝트 기본 정보

**분석 대상 웹사이트**: https://polygon.technology  
**정보 수집 일자**: 2026년 4월 18일

| 항목 | 내용 | 출처 |
|------|------|------|
| **프로젝트 이름** | Polygon PoS (Proof of Stake) | [1] |
| **메인넷** | Polygon Mainnet | [2] |
| **프로젝트 분류** | Layer 2 Scaling Solution (Commit Chain) | [3] |
| **기축 통화** | POL (formerly MATIC) | [4] |
| **론칭 일자** | 2020년 5월 30일 | [5] |

참고문헌 (발췌):
1. Polygon Official Website - Polygon Labs, 2026년 4월 18일 액세스, https://polygon.technology/
2. Polygon PoS Overview - Polygon Labs, 2026년 4월 18일 액세스, https://polygon.technology/polygon-pos
3. Polygon Architecture - Polygon Labs, 2026년 4월 18일 액세스, https://docs.polygon.technology/pos/architecture/
4. POL Token Migration Announcement - Polygon Labs, 2026년 4월 17일 액세스, https://polygon.technology/blog/pol-token-migration
5. Polygon Mainnet Launch - Polygon Labs, 2020년 5월 30일 액세스, https://blog.polygon.technology/mainnet-launch
```

### Section 7 예시 (참고문헌):

```markdown
## 7. 참고문헌

**분석 대상 프로젝트**: Polygon PoS  
**기준 웹사이트**: https://polygon.technology  
**총 인용 수**: 52

---

### 공식 문서 및 백서

1. Polygon Official Website - Polygon Labs, 2026년 4월 18일 액세스, https://polygon.technology/

2. Polygon PoS Whitepaper v2.0 - Polygon Labs, 2026년 4월 18일 액세스, https://polygon.technology/papers/pol-whitepaper.pdf

3. Polygon Architecture Documentation - Polygon Labs, 2026년 4월 18일 액세스, https://docs.polygon.technology/pos/architecture/

4. Polygon Validator Guide - Polygon Labs, 2026년 4월 18일 액세스, https://docs.polygon.technology/pos/how-to/validator/

...

### 소스 코드 및 GitHub

11. Polygon Bor (Execution Layer) - Polygon Labs, 2026년 4월 18일 액세스, https://github.com/maticnetwork/bor

12. Polygon Heimdall (Consensus Layer) - Polygon Labs, 2026년 4월 18일 액세스, https://github.com/maticnetwork/heimdall

13. Polygon Contracts Repository - Polygon Labs, 2026년 4월 18일 액세스, https://github.com/maticnetwork/contracts

...

### 온체인 데이터 및 Explorer

21. Polygon Mainnet Explorer (Polygonscan) - Polygonscan, 2026년 4월 18일 액세스, https://polygonscan.com/

22. Polygon Staking Dashboard - Polygon Labs, 2026년 4월 18일 액세스, https://staking.polygon.technology/

23. Polygon Network Statistics - Polygonscan, 2026년 4월 18일 액세스, https://polygonscan.com/stats

...

### 커뮤니티 및 거버넌스

31. Polygon Governance Forum - Polygon Community, 2026년 4월 18일 액세스, https://forum.polygon.technology/

32. Polygon Improvement Proposals (PIPs) - Polygon Labs, 2026년 4월 18일 액세스, https://github.com/maticnetwork/Polygon-Improvement-Proposals

...

### 외부 분석 및 학술 자료

41. Polygon Network Analysis - Messari, 2026년 4월 15일 액세스, https://messari.io/report/polygon-pos-network-analysis

42. Polygon TVL Data - DeFi Llama, 2026년 4월 18일 액세스, https://defillama.com/chain/Polygon

...

52. Polygon Security Audit Report - CertiK, 2026년 4월 10일 액세스, https://www.certik.com/projects/polygon
```

---

## 품질 검증 체크리스트 (v4.1 업데이트)

### 입력 파라미터 검증 (신규)

- [ ] **`PROJECT_URL` 제공 확인**: 입력값 존재
- [ ] **`PROJECT_URL` 접근 가능**: curl 테스트 성공
- [ ] **프로젝트 명칭 확인**: 웹사이트에서 자동 추출 또는 수동 입력

### 필수 요구사항

- [ ] **7개 섹션 모두 포함**: 개념 정의, 가치, 보상, 토큰, 부트스트랩, 평가, **참고문헌**
- [ ] **🔴 참고문헌 섹션 존재**: Section 7에 48개 이상 URL 인용
- [ ] **🔴 인라인 인용 80회 이상**: 본문에 [1], [2] 등 인용 번호
- [ ] **온체인 증거 제시**: 최소 3개 이상 스마트 컨트랙트 주소 또는 소스 코드 링크 **+ URL**
- [ ] **방법론 프레임워크 준수**: [크립토이코노미 설계 방법론] 용어와 구조 일관성

### 🔴 인용 품질 확인 (v4.1 강화)

- [ ] **URL 접근성**: 무작위 20개 URL 클릭하여 404 에러 없음 확인
- [ ] **프로젝트 공식 URL 비율**: 최소 20개 이상이 `{PROJECT_URL}` 도메인
- [ ] **날짜 형식**: "2026년 4월 18일 액세스" 형식 통일
- [ ] **발행처 명시**: 모든 인용에 발행처/저자 포함
- [ ] **본문 인용 매칭**: 본문 [X] 번호가 참고문헌 X번 항목과 일치
- [ ] **중복 제거**: 동일 URL 중복 인용 없음
- [ ] **할루시네이션 방지**: 모든 URL이 실제 접근 가능한 문서

### 객관성 확인

- [ ] **추정 표시**: 모든 추론/추정에 `⚠️ [추론]` 또는 `⚠️ [추정]` 태그
- [ ] **미확인 정보 표시**: 확인 불가 주장에 `❌ [미확인]` 태그
- [ ] **출처 인용**: 백서, 코드, 온체인 데이터 인용 시 구체적 위치 명시 **+ URL**
- [ ] **마케팅 vs 현실 구분**: 프로젝트 주장과 실제 구현 차이 명시

### 금지 사항

- [ ] **가격 예측 금지**: 토큰 가격 전망, 차트 분석, 기술적 지표 **절대 포함 안 함**
- [ ] **투자 조언 금지**: "매수 추천", "Hold/Sell", "X% 수익 기대" 등 **절대 포함 안 함**
- [ ] **보증/단정 금지**: "반드시 성공할 것", "100% 안전" 등 과도한 단언 **금지**
- [ ] **편향 금지**: 프로젝트 옹호 또는 경쟁자 폄하 **금지** - 객관적 사실만
- [ ] **🔴 인용 없는 주장 금지**: 검증 가능한 모든 주장에 출처 표시
- [ ] **🔴 할루시네이션 URL 금지**: 존재하지 않는 문서 링크 **절대 금지**

---

## 사용 예시 (실행 방법)

### CLI 실행:

```bash
# 프롬프트 + 프로젝트 URL 입력
PROJECT_URL="https://polygon.technology" \
cat econ_v4.1_generic_url_input_prompt.md | gemini-deep-research

# 또는 환경변수로
export PROJECT_URL="https://cosmos.network"
export PROJECT_NAME="Cosmos Hub"
cat econ_v4.1_generic_url_input_prompt.md | gemini-deep-research
```

### Python 실행:

```python
import os

project_url = "https://ethereum.org"
project_name = "Ethereum"  # 선택 사항

with open("econ_v4.1_generic_url_input_prompt.md", "r") as f:
    prompt_template = f.read()

# 템플릿 변수 치환 (선택 사항, LLM이 자동으로도 처리 가능)
prompt = prompt_template.replace("{PROJECT_URL}", project_url)
prompt = prompt.replace("{PROJECT_NAME}", project_name)

# Gemini API 호출
response = gemini_client.generate(
    model="gemini-2.0-flash-thinking-exp",
    prompt=prompt
)

# 보고서 저장
with open(f"econ_report_{project_name}.md", "w") as f:
    f.write(response)
```

---

## 버전 관리

**Version**: 4.1.0  
**Status**: Production Ready (Generic Template)  
**Last Updated**: 2026-04-18  

**Changes from v4.0**:
- 🔴 **프로젝트 하드코딩 제거** (Polygon 특정 → 범용 템플릿)
- 🔴 **`PROJECT_URL` 입력 파라미터 추가**
- 🔴 **URL 도메인 검증 추가** (최소 20개 공식 URL)
- 🔴 **URL 접근성 자동 검증** (404 체크)
- 🔴 **입력 파라미터 검증 단계 추가**
- Step 0: 입력값 확인 단계 신규 추가
- Step 1: 정보 수집 시간 40분 → 50분 (URL 사전 검증 강화)
- Step 6: 참고문헌 작성 시간 30분 → 40분 (URL 404 테스트)
- 총 소요시간: 3.5시간 → 4시간

**Known Issues**: 
- Gemini Deep Research가 실시간 웹 크롤링 없이 URL 생성 가능한지 미검증
- 48개 URL 요구사항이 과도할 가능성 (파일럿 테스트 필요)

**Roadmap**:
- v4.1.1: 파일럿 테스트 피드백 반영 (Polygon, Cosmos, Ethereum 테스트)
- v4.2: URL 개수 조정 (48 → 40 or 60)
- v4.3: 프로젝트 카테고리별 프롬프트 변형 (L1/L2/DeFi)

---

## 🔴 파일럿 테스트 계획 (v4.1)

**테스트 프로젝트** (3개):
1. **Polygon** (`https://polygon.technology`) - Layer 2
2. **Cosmos** (`https://cosmos.network`) - Layer 0 Hub
3. **Ethereum** (`https://ethereum.org`) - Layer 1

**성공 기준** (각 프로젝트):
- [ ] v4.1 프롬프트로 보고서 생성
- [ ] Section 7 참고문헌 섹션 존재
- [ ] 48개 이상 URL 인용
- [ ] 프로젝트 공식 URL 20개 이상
- [ ] 모든 URL 접근 가능 (404 에러 < 2개)
- [ ] 기술적 깊이 유지 (v3.1 대비 동등 이상)
- [ ] CRO 평가: 4.7/5.0 이상

**타임라인**: 
- Week 1: Polygon 테스트
- Week 2: Cosmos 테스트
- Week 3: Ethereum 테스트
- Week 4: 결과 종합 및 v4.2 릴리스

**Decision Gate**: 
- 3개 중 2개 이상 성공 → v4.2 프로덕션 도입
- 3개 모두 실패 → Option A (하이브리드) 또는 현 파이프라인 유지

---

**문서 상태**: ✅ Production Ready (Generic Template)  
**승인 필요**: CRO 검토 + CEO 최종 승인 (파이프라인 전략 변경)  
**Next Action**: [BCE-380](/BCE/issues/BCE-380) 파일럿 테스트 실행 승인 대기
