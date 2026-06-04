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
})

describe('getLocalizedCardSummary', () => {
  it('prefers card_data summary_by_lang for the active locale', () => {
    expect(getLocalizedCardSummary({
      card_summary_ko: 'legacy Korean summary',
      card_data: {
        summary_by_lang: {
          ko: 'localized metadata summary',
        },
      },
    }, 'ko')).toBe('localized metadata summary')
  })

  it('falls back to localized card_summary columns', () => {
    expect(getLocalizedCardSummary({
      card_summary_ko: 'column summary',
      card_data: {},
    }, 'ko')).toBe('column summary')
  })

  it('falls back to localized summary fields in card_data', () => {
    expect(getLocalizedCardSummary({
      card_data: {
        summary_ko: 'card data summary',
      },
    }, 'ko')).toBe('card data summary')
  })

  it('uses source summary only when the row language matches the locale', () => {
    expect(getLocalizedCardSummary({
      language: 'ko',
      card_data: {
        summary: 'same-language source summary',
      },
    }, 'ko')).toBe('same-language source summary')

    expect(getLocalizedCardSummary({
      language: 'en',
      card_data: {
        summary: 'english source summary',
      },
    }, 'ko')).toBe('')
  })

  it('does not fall back to English for localized project cards by default', () => {
    expect(getLocalizedCardSummary({
      card_summary_en: 'english fallback summary',
      card_data: {
        summary_by_lang: {
          en: 'english metadata summary',
        },
      },
    }, 'ko')).toBe('')
  })

  it('can use English fallback for homepage showcase cards', () => {
    expect(getLocalizedCardSummary({
      card_summary_en: 'english fallback summary',
    }, 'ko', { allowEnglishFallback: true })).toBe('english fallback summary')
  })

  it('cleans summaries before returning them', () => {
    expect(getLocalizedCardSummary({
      card_data: {
        summary_by_lang: {
          ko: 'Useful insight. ### Raw section',
        },
      },
    }, 'ko')).toBe('Useful insight.')
  })
})
