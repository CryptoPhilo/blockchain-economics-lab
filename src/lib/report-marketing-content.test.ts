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
})
