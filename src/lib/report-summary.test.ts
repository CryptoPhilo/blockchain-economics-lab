import { cleanCardSummary, getLocalizedCardSummary } from './report-summary'

describe('cleanCardSummary', () => {
  it('cleans project detail card summaries before rendering', () => {
    expect(cleanCardSummary('Token economy overview. ### Risk Factors')).toBe(
      'Token economy overview.',
    )
  })

  it('cleans forensic detail summaries before rendering', () => {
    expect(cleanCardSummary('Suspicious wallet activity detected. | Metric | Value |')).toBe(
      'Suspicious wallet activity detected.',
    )
  })

  it('cleans forensic slide card summaries before rendering', () => {
    expect(cleanCardSummary('Market anomaly context. - Exchange flow spike - Whale exits')).toBe(
      'Market anomaly context.',
    )
  })

  it('removes leaked Korean section titles from report card summaries', () => {
    expect(
      cleanCardSummary(
        "1. 개요 및 개념 정의 (Concept Definition List) 본 보고서는 The Open Network (TON)의 경제 구조를 기술적, 경제적 관점에서 심층 분석한다.",
      ),
    ).toBe(
      '본 보고서는 The Open Network (TON)의 경제 구조를 기술적, 경제적 관점에서 심층 분석한다.',
    )
  })

  it('removes truncated Korean section-title fragments from card summaries', () => {
    expect(
      cleanCardSummary(
        "및 개념 정의 본 보고서는 '크립토 이코노미 설계 방법론'과 '분석 보고서 작성 방법'에 의거하여 The Open Network (TON)의 경제 구조를 기술적, 경제적 관점에서 심층 분석한다.",
      ),
    ).toBe(
      'The Open Network (TON)의 경제 구조를 기술적, 경제적 관점에서 심층 분석한다.',
    )
  })

  it('removes internal methodology boilerplate from the beginning of summaries', () => {
    expect(
      cleanCardSummary(
        "본 보고서는 '크립토 이코노미 설계 방법론'과 '분석 보고서 작성 방법'에 의거하여 The Open Network (TON)의 경제 구조를 기술적, 경제적 관점에서 심층 분석한다.",
      ),
    ).toBe('The Open Network (TON)의 경제 구조를 기술적, 경제적 관점에서 심층 분석한다.')
  })

  it('removes bare reference numbers that leak after sentence punctuation', () => {
    expect(
      cleanCardSummary(
        '공급 압력은 완화되고 있으나 거래소 유입은 높은 수준이다. 2 단기 변동성은 여전히 크다.1',
      ),
    ).toBe('공급 압력은 완화되고 있으나 거래소 유입은 높은 수준이다. 단기 변동성은 여전히 크다.')
  })

  it('removes Korean sentence-final reference numbers before punctuation', () => {
    expect(cleanCardSummary('온체인 활성도는 전주 대비 회복됐다2. 유동성은 제한적이다³.')).toBe(
      '온체인 활성도는 전주 대비 회복됐다. 유동성은 제한적이다.',
    )
  })

  it('preserves meaningful non-citation numbers at the end of English summaries', () => {
    expect(cleanCardSummary('The protocol relies on Layer 2. Revenue improved in 2025.')).toBe(
      'The protocol relies on Layer 2. Revenue improved in 2025.',
    )
  })

  it('preserves meaningful Korean numeric terms before punctuation', () => {
    expect(cleanCardSummary('확장 전략은 레이어2. 생태계와 직접 연결된다.')).toBe(
      '확장 전략은 레이어2. 생태계와 직접 연결된다.',
    )
  })
})

describe('getLocalizedCardSummary', () => {
  it('uses card_data summary_by_lang when row columns are empty', () => {
    expect(
      getLocalizedCardSummary({
        language: 'ko',
        card_data: {
          summary_by_lang: {
            ko: 'Banana For Scale은 밈 수요와 유동성 집중에 의존한다.',
          },
        },
      }, 'ko'),
    ).toBe('Banana For Scale은 밈 수요와 유동성 집중에 의존한다.')
  })

  it('falls back from summary_by_lang to localized row columns', () => {
    expect(
      getLocalizedCardSummary({
        language: 'ja',
        card_data: {
          summary_by_lang: {},
        },
        card_summary_ja: '日本語のカード要約。',
      }, 'ja'),
    ).toBe('日本語のカード要約。')
  })

  it('does not use English fallback on non-English project cards by default', () => {
    expect(
      getLocalizedCardSummary({
        language: 'ko',
        card_summary_en: 'English summary.',
      }, 'ko'),
    ).toBe('')
  })

  it('allows English fallback for showcase-style surfaces', () => {
    expect(
      getLocalizedCardSummary({
        language: 'ko',
        card_summary_en: 'English summary.',
      }, 'ko', { allowEnglishFallback: true }),
    ).toBe('English summary.')
  })
})
