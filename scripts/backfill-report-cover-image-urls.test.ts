import {
  buildReportCoverCandidates,
  extractFirstEmbeddedImage,
  extractFirstExternalSlideImageUrl,
  getPreferredReportLanguage,
  mergeCoverImageUrlsByLang,
  storagePathFromPublicSlidesUrl,
} from './backfill-report-cover-image-urls'

describe('report cover image URL backfill helpers', () => {
  it('builds candidates for all report languages even when no product is linked', () => {
    const candidates = buildReportCoverCandidates([
      {
        id: 'report-avalanche',
        project_id: 'project-avalanche',
        product_id: null,
        report_type: 'econ',
        language: 'en',
        status: 'published',
        published_at: '2026-05-02T09:06:00.000Z',
        updated_at: '2026-05-02T09:06:00.000Z',
        created_at: '2026-04-13T11:32:40.000Z',
        slide_html_urls_by_lang: {
          en: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/en.html',
          ko: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/ko.html',
        },
        tracked_projects: {
          id: 'project-avalanche',
          name: 'Avalanche',
          slug: 'avalanche-2',
        },
      },
    ], 'https://example.supabase.co')

    expect(candidates).toHaveLength(2)
    expect(candidates[0]).toMatchObject({
      reportId: 'report-avalanche',
      productId: null,
      projectSlug: 'avalanche-2',
      reportType: 'econ',
      language: 'en',
      storagePath: 'econ/avalanche-2/latest/en.html',
      coverStoragePath: 'econ/avalanche-2/latest/en-cover.jpg',
      coverPublicUrl: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/en-cover.jpg',
      shouldUpdateProductCover: false,
    })
    expect(candidates[1]).toMatchObject({
      language: 'ko',
      storagePath: 'econ/avalanche-2/latest/ko.html',
      coverStoragePath: 'econ/avalanche-2/latest/ko-cover.jpg',
    })
  })

  it('skips report languages that already have cover URLs unless force is enabled', () => {
    const report = {
      id: 'report-avalanche',
      project_id: 'project-avalanche',
      product_id: 'product-avalanche',
      report_type: 'econ',
      language: 'en',
      status: 'published',
      published_at: null,
      updated_at: null,
      created_at: null,
      slide_html_urls_by_lang: {
        en: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/en.html',
      },
      cover_image_urls_by_lang: {
        en: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/en-cover.png',
      },
      tracked_projects: {
        id: 'project-avalanche',
        name: 'Avalanche',
        slug: 'avalanche-2',
      },
      products: {
        id: 'product-avalanche',
        cover_image_url: null,
      },
    } as const

    expect(buildReportCoverCandidates([report], 'https://example.supabase.co')).toEqual([])
    expect(buildReportCoverCandidates([report], 'https://example.supabase.co', { force: true })).toHaveLength(1)
  })

  it('marks the preferred language candidate for legacy product cover compatibility', () => {
    const candidates = buildReportCoverCandidates([
      {
        id: 'report-avalanche',
        project_id: 'project-avalanche',
        product_id: 'product-avalanche',
        report_type: 'econ',
        language: 'en',
        status: 'published',
        published_at: null,
        updated_at: null,
        created_at: null,
        slide_html_urls_by_lang: {
          en: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/en.html',
        },
        tracked_projects: {
          id: 'project-avalanche',
          name: 'Avalanche',
          slug: 'avalanche-2',
        },
        products: {
          id: 'product-avalanche',
          cover_image_url: null,
        },
      },
    ], 'https://example.supabase.co')

    expect(candidates).toHaveLength(1)
    expect(candidates[0].shouldUpdateProductCover).toBe(true)
  })

  it('extracts the first embedded slide image from self-contained HTML', () => {
    const image = extractFirstEmbeddedImage('<img src="data:image/jpeg;base64,aGVsbG8=">')

    expect(image?.mimeType).toBe('image/jpeg')
    expect(image?.extension).toBe('jpg')
    expect(image?.bytes.toString('utf8')).toBe('hello')
  })

  it('extracts the first externally stored slide image from viewer HTML', () => {
    expect(extractFirstExternalSlideImageUrl(`
      <img id="slideImg" src="" alt="Slide">
      <script>
        const slides = [
          "https://example.supabase.co/storage/v1/object/public/slides/econ/aerodrome-finance/1/en_assets/page-001.png",
          "https://example.supabase.co/storage/v1/object/public/slides/econ/aerodrome-finance/1/en_assets/page-002.png"
        ];
      </script>
    `)).toBe(
      'https://example.supabase.co/storage/v1/object/public/slides/econ/aerodrome-finance/1/en_assets/page-001.png',
    )
  })

  it('falls back to img src when the viewer does not expose a slides array', () => {
    expect(extractFirstExternalSlideImageUrl(
      '<img src="https://example.supabase.co/storage/v1/object/public/slides/mat/okx/1/ko_assets/page-001.webp">',
    )).toBe('https://example.supabase.co/storage/v1/object/public/slides/mat/okx/1/ko_assets/page-001.webp')
  })

  it('resolves preferred language and public storage object paths', () => {
    expect(getPreferredReportLanguage({
      id: 'report-1',
      project_id: 'project-1',
      product_id: 'product-1',
      report_type: 'maturity',
      language: null,
      status: 'published',
      published_at: null,
      updated_at: null,
      created_at: null,
      slide_html_urls_by_lang: { ko: 'https://example.test/ko.html', en: 'https://example.test/en.html' },
    })).toBe('en')

    expect(storagePathFromPublicSlidesUrl(
      'https://example.supabase.co/storage/v1/object/public/slides/mat/bitcoin/latest/en.html?download=1',
    )).toBe('mat/bitcoin/latest/en.html')
  })

  it('merges generated cover URLs without dropping existing languages', () => {
    expect(mergeCoverImageUrlsByLang(
      { en: 'https://example.com/en-cover.png' },
      'ko',
      'https://example.com/ko-cover.png',
    )).toEqual({
      en: 'https://example.com/en-cover.png',
      ko: 'https://example.com/ko-cover.png',
    })
  })

  it('skips statuses outside published and in_review', () => {
    const candidates = buildReportCoverCandidates([
      {
        id: 'report-avalanche',
        project_id: 'project-avalanche',
        product_id: null,
        report_type: 'econ',
        language: 'en',
        status: 'coming_soon',
        published_at: null,
        updated_at: null,
        created_at: null,
        slide_html_urls_by_lang: {
          en: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/en.html',
        },
        tracked_projects: {
          id: 'project-avalanche',
          name: 'Avalanche',
          slug: 'avalanche-2',
        },
      },
    ], 'https://example.supabase.co')

    expect(candidates).toEqual([])
  })
})
