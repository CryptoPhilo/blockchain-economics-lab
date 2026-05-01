import { cleanCardSummary, resolveSlideUrl } from './slide-report-utils'

describe('resolveSlideUrl', () => {
  it('returns the exact locale slide URL', () => {
    expect(resolveSlideUrl({ ko: 'https://example.com/ko.html' }, 'ko')).toBe(
      'https://example.com/ko.html',
    )
  })

  it('does not fall back from Korean to another slide language', () => {
    expect(
      resolveSlideUrl(
        {
          en: 'https://example.com/en.html',
          zh: 'https://example.com/zh.html',
        },
        'ko',
      ),
    ).toBeNull()
  })

  it('ignores empty and non-string locale entries', () => {
    expect(resolveSlideUrl({ ko: '', en: 'https://example.com/en.html' }, 'ko')).toBeNull()
    expect(resolveSlideUrl({ ko: { url: 'https://example.com/ko.html' } }, 'ko')).toBeNull()
  })

  it('rejects a locale key whose storage URL points at another language artifact', () => {
    expect(
      resolveSlideUrl(
        {
          ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/zh.html',
        },
        'ja',
      ),
    ).toBeNull()
  })

  it('accepts matching locale artifacts in the storage path', () => {
    expect(
      resolveSlideUrl(
        {
          ja: 'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/ja.html',
        },
        'ja',
      ),
    ).toBe(
      'https://example.supabase.co/storage/v1/object/public/slides/econ/bitcoin/latest/ja.html',
    )
  })
})

describe('cleanCardSummary', () => {
  it('returns empty string for null/undefined/non-string', () => {
    expect(cleanCardSummary(null)).toBe('')
    expect(cleanCardSummary(undefined)).toBe('')
    expect(cleanCardSummary('')).toBe('')
  })

  it('drops markdown headings that leaked from the source report', () => {
    const raw =
      '솔라나 네트워크의 경제 시스템을 구성하는 핵심 개념들은 온체인 상태(state)와 긴밀하게 연결되어 있다. ### 1.1 프로젝트 기본 정보 | 항목 | 상세 내용 |'
    expect(cleanCardSummary(raw)).toBe(
      '솔라나 네트워크의 경제 시스템을 구성하는 핵심 개념들은 온체인 상태(state)와 긴밀하게 연결되어 있다.',
    )
  })

  it('drops inline table markup', () => {
    const raw =
      "Summarizing key indicators. | Metrics | 2024 | 2025 | | :---- | :---- | :---- |"
    expect(cleanCardSummary(raw)).toBe('Summarizing key indicators.')
  })

  it('strips bold and link markdown', () => {
    expect(cleanCardSummary('See **the docs** at [link](https://x.test) for more.'))
      .toBe('See the docs at link for more.')
  })

  it('removes inline citation markers like [1]', () => {
    expect(cleanCardSummary('First fact [1]. Second fact [12].'))
      .toBe('First fact. Second fact.')
  })

  it('collapses whitespace and trims', () => {
    expect(cleanCardSummary('  A   B\n\nC  ')).toBe('A B C')
  })

  it('passes through clean prose unchanged in meaning', () => {
    const clean = '솔라나는 고성능 PoH 합의 기반의 레이어1 블록체인이다.'
    expect(cleanCardSummary(clean)).toBe(clean)
  })

  it('cuts at the first list bullet rather than retaining structural list', () => {
    expect(cleanCardSummary('Overview. - bullet one - bullet two')).toBe('Overview.')
  })
})
