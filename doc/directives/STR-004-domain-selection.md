# STR-004: 웹사이트 도메인 선정 — C-Level 검토 보고서

> **주관**: agent-ceo (연구소장)
> **참석**: agent-cro, agent-coo, agent-cmo
> **일시**: 2026-04-09
> **상태**: Board 승인 요청
> **Goal Ancestry**: Company Mission → STR-001 → 이 보고서

---

## 1. 배경

현재 웹사이트는 Vercel 기본 도메인(`blockchain-economics-lab.vercel.app`)으로 운영 중이다. 브랜드 신뢰도, SEO, 고객 인지도를 위해 자체 도메인을 확보하고 연결해야 한다.

### 1.1 업계 벤치마크

주요 크립토 리서치 기업들의 도메인 패턴을 분석했다:

| 기업 | 도메인 | TLD | 특징 |
|------|--------|-----|------|
| Messari | messari.io | `.io` | 짧고 브랜드 중심 |
| Glassnode | glassnode.com | `.com` | 전통적 TLD, 신뢰감 |
| Chainalysis | chainalysis.com | `.com` | 기업 신뢰도 극대화 |
| Nansen | nansen.ai | `.ai` | 기술 트렌드 반영 |
| Coin Metrics | coinmetrics.io | `.io` | 테크 스타트업 이미지 |
| Delphi Digital | delphi.digital | `.digital` | 독특한 브랜딩 |
| The Block | theblock.co | `.co` | 미디어 느낌, 간결 |
| DefiLlama | defillama.com | `.com` | 대중적 접근성 |

**패턴 분석**: `.com`과 `.io`가 크립토 리서치 업계의 양대 주류. 최근 `.ai`, `.digital` 등 특수 TLD도 채택 증가.

---

## 2. 도메인 후보 평가

### 2.1 DNS 조회 기반 가용성 조사

| 도메인 | DNS 레코드 | 가용 가능성 | 비고 |
|--------|-----------|------------|------|
| `bcelab.io` | 없음 | 🟢 높음 | 간결, 기억하기 쉬움 |
| `bcelab.com` | 있음 | 🔴 등록됨 | 구매 협상 필요 |
| `bcelab.co` | 없음 | 🟢 높음 | .co는 미디어/스타트업 느낌 |
| `bcelab.org` | 없음 | 🟢 높음 | 연구소 느낌에 적합 |
| `bcelab.xyz` | 없음 | 🟢 높음 | 저렴, web3 친화적 |
| `bce-lab.com` | 없음 | 🟢 높음 | 하이픈 포함 |
| `bce-lab.io` | 없음 | 🟢 높음 | 하이픈 포함 |
| `bcel.io` | 없음 | 🟢 높음 | 매우 짧음 (4글자) |
| `blockchain-economics.com` | 없음 | 🟡 중간 | 서술적, 길이 긴 편 |
| `blockchaineconomicslab.com` | 없음 | 🟡 중간 | 매우 서술적, 너무 긴 편 |
| `blockchaineconomicslab.io` | 없음 | 🟡 중간 | 매우 서술적, 너무 긴 편 |
| `chaineconomics.io` | 없음 | 🟢 높음 | 간결하면서 서술적 |
| `bceresearch.io` | 없음 | 🟢 높음 | 연구 정체성 명확 |
| `bce.institute` | 없음 | 🟢 높음 | .institute TLD, 연구소 정체성 |
| `blockchain.institute` | 없음 | 🟢 높음 | 프리미엄 느낌, 가격 높을 수 있음 |

> 주의: DNS 레코드가 없다는 것이 반드시 미등록을 의미하지는 않음. 실제 등록 여부는 레지스트라에서 확인 필요.

---

## 3. C-Level 의견

### 3.1 CEO 의견 (agent-ceo)

도메인 선택의 핵심은 **브랜드 인지도 + 신뢰감 + 간결성**의 균형이다. 우리 연구소의 정체성은 "블록체인 경제 분석의 권위 있는 연구소"이므로, 너무 캐주얼하거나 트렌디한 느낌보다는 전문성이 드러나야 한다.

**1순위 추천: `bcelab.io`**
- "BCE"는 Blockchain Economics의 약칭으로 브랜드화 가능
- "Lab"은 연구소/실험실 느낌으로 업계에서 흔히 사용 (DefiLlama → Llama, CryptoEconLab 등)
- `.io`는 크립토/테크 업계 표준 TLD (Messari, CoinMetrics 등)
- 8글자로 간결하고 기억하기 쉬움
- 발음이 명확 (비-씨-이-랩-닷-아이오)

### 3.2 CRO 의견 (agent-cro)

연구 콘텐츠의 권위를 뒷받침할 도메인이 필요하다. 보고서 PDF에 도메인이 인쇄되므로 너무 길면 안 되고, 학술/전문적 느낌이 있어야 한다.

**1순위: `bcelab.io`** — 간결하면서 전문적. 보고서 표지에 인쇄해도 깔끔함.
**2순위: `chaineconomics.io`** — 무엇을 하는 곳인지 도메인만 보고 바로 알 수 있음. 다만 BCE라는 약칭과 불일치.

### 3.3 COO 의견 (agent-coo)

운영 관점에서 고려 사항:

- `.io` 도메인은 연간 약 $30~50, `.com`은 약 $10~15. 비용 차이 미미.
- 이메일 주소로도 사용할 가능성 고려 (`research@bcelab.io` 등).
- SSL 인증서는 Let's Encrypt로 무료 자동 발급 (Vercel 기본 지원).
- Vercel에 커스텀 도메인 연결은 DNS 설정만으로 완료 (5분 이내).
- `.io`는 영국령 인도양 지역 국가코드 TLD이나, 테크 업계에서 "Input/Output"으로 인식되어 사실상 gTLD처럼 사용됨.

**1순위: `bcelab.io`** — 운영 효율 최적. 간결한 이메일 주소 생성 가능.
**보조 추천: `bcelab.com`도 확보 시도** — 이미 등록되어 있으나, 파킹 도메인일 경우 합리적 가격에 매입 가능할 수 있음. `.com`을 `.io`로 리다이렉트 설정하면 두 경로 모두 커버.

### 3.4 CMO 의견 (agent-cmo)

마케팅 관점에서 도메인은 브랜드의 첫인상이다:

- **SEO**: `.com`과 `.io` 모두 Google 검색에서 동등하게 취급됨. 차이 없음.
- **브랜드 인지도**: "BCE Lab"은 짧아서 구전, SNS 공유, 프레젠테이션에서 효과적.
- **글로벌 접근성**: 7개 언어 지원 사이트이므로, 특정 언어에 치우치지 않는 중립적 도메인이 좋음. "bcelab"은 언어 중립적.
- **소셜 미디어 일관성**: @bcelab 핸들이 Twitter/X, Telegram 등에서 가용한지도 확인 필요.

**1순위: `bcelab.io`** — 마케팅 효과 최적화. 짧고, 글로벌하고, 전문적.

**도메인 패밀리 확보 제안:**

| 도메인 | 용도 | 우선순위 |
|--------|------|---------|
| `bcelab.io` | 메인 웹사이트 | 🔴 필수 |
| `bcelab.com` | 리다이렉트 → .io (확보 가능 시) | 🟡 권장 |
| `bcelab.org` | 리다이렉트 → .io | 🟢 선택 |
| `bcelab.xyz` | Web3 프레즌스 / 예비 | 🟢 선택 |

---

## 4. 종합 결론 및 권고안

### 4.1 만장일치 합의

**메인 도메인: `bcelab.io`**

| 평가 기준 | 점수 | 설명 |
|-----------|------|------|
| 간결성 | ★★★★★ | 8글자, 쉬운 발음 |
| 전문성 | ★★★★☆ | Lab = 연구소, .io = 테크 업계 표준 |
| 기억 용이성 | ★★★★★ | BCE + Lab, 직관적 |
| 글로벌 중립성 | ★★★★★ | 특정 언어에 치우치지 않음 |
| 업계 적합성 | ★★★★★ | Messari.io, CoinMetrics.io와 동일 패턴 |
| SEO | ★★★★☆ | .io는 .com과 동등한 검색 효과 |
| 비용 | ★★★★☆ | 연간 $30~50 수준 |
| 이메일 적합성 | ★★★★★ | research@bcelab.io — 간결하고 전문적 |

### 4.2 실행 계획

| 단계 | 작업 | 담당 | 목표일 |
|------|------|------|--------|
| 1 | Board 승인 | Board | 즉시 |
| 2 | `bcelab.io` 도메인 구매 (Namecheap/Cloudflare) | COO + 데이터 엔지니어 | 승인 후 1일 |
| 3 | Vercel 커스텀 도메인 연결 | 데이터 엔지니어 | 구매 후 즉시 |
| 4 | SSL 인증서 자동 발급 확인 | 데이터 엔지니어 | 연결 후 즉시 |
| 5 | 이메일 설정 (선택) | COO | 1주 내 |
| 6 | `bcelab.com` 매입 타진 (선택) | COO | 2주 내 |
| 7 | 소셜 미디어 핸들 확보 (@bcelab) | CMO | 병렬 진행 |
| 8 | 보고서 템플릿에 도메인 반영 | CRO + 편집자 | 도메인 활성화 후 |

### 4.3 예상 비용

| 항목 | 비용 | 주기 |
|------|------|------|
| `bcelab.io` 등록 | ~$40 | 연간 |
| `bcelab.org` 등록 (선택) | ~$12 | 연간 |
| `bcelab.xyz` 등록 (선택) | ~$10 | 연간 |
| `bcelab.com` 매입 (선택) | $100~2,000 (협상) | 1회 |
| 이메일 호스팅 (선택) | $0~$6/월 | 월간 |
| **필수 합계** | **~$40/년** | |

---

## 5. Board 승인 요청

**승인 항목:**
1. 메인 도메인 `bcelab.io` 구매 및 연결
2. 보조 도메인 `bcelab.org`, `bcelab.xyz` 확보 (선택)
3. `bcelab.com` 매입 타진 (선택, 예산 상한 $500)
4. 소셜 미디어 핸들 @bcelab 확보

```
[Board] ✅ Approved — bcelab.xyz 선정 — 2026-04-09
[CEO]   ✅ Acknowledged — 2026-04-09
[CRO]   ✅ Acknowledged — 2026-04-09
[COO]   ✅ Acknowledged — 2026-04-09
[CMO]   ✅ Acknowledged — 2026-04-09
```

> **Board 결정**: 임원 추천안(bcelab.io) 대신 `bcelab.xyz`로 확정.
> `.xyz`는 저렴하고($10/년), Web3 친화적이며, Alphabet(Google 모회사)의 abc.xyz 사례처럼 테크 업계에서도 신뢰도 있는 TLD.
