import { getLocalizedMarketingContent } from './report-marketing-content'

describe('getLocalizedMarketingContent', () => {
  it('returns direct locale marketing content first', () => {
    expect(
      getLocalizedMarketingContent(
        {
          marketing_content_by_lang: {
            en: 'English investment view',
            ko: '한국어 투자 관점',
          },
        },
        'ko',
      ),
    ).toBe('한국어 투자 관점')
  })

  it('falls back between Korean and English when the requested locale is missing', () => {
    expect(
      getLocalizedMarketingContent(
        { marketing_content_by_lang: { en: 'English fallback view' } },
        'ko',
      ),
    ).toBe('English fallback view')

    expect(
      getLocalizedMarketingContent(
        { marketing_content_by_lang: { ko: '한국어 대체 관점' } },
        'en',
      ),
    ).toBe('한국어 대체 관점')
  })

  it('does not return empty or duplicate card summary copy', () => {
    expect(
      getLocalizedMarketingContent(
        { marketing_content_by_lang: { en: '  ' } },
        'en',
      ),
    ).toBe('')

    expect(
      getLocalizedMarketingContent(
        { marketing_content_by_lang: { en: '**Same summary**' } },
        'en',
        'Same summary',
      ),
    ).toBe('')
  })

  it('does not render raw LaTeX or formula fragments in investment view copy', () => {
    expect(
      getLocalizedMarketingContent(
        {
          marketing_content_by_lang: {
            ko: String.raw`$$ px i = round(px {i-1} \times 1.003) $$ 각 level 간격은 약 0.3% 전략은 최소 3초마다 조정된다.`,
          },
        },
        'ko',
      ),
    ).toBe('')
  })

  it('does not render markdown table or code fragments in investment view copy', () => {
    expect(
      getLocalizedMarketingContent(
        {
          marketing_content_by_lang: {
            en: '| Metric | Value | `raw_code`',
          },
        },
        'en',
      ),
    ).toBe('')
  })
})
