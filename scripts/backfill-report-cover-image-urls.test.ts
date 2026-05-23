import {
  buildReportCoverCandidates,
  extractFirstEmbeddedImage,
  getPreferredReportLanguage,
  storagePathFromPublicSlidesUrl,
} from './backfill-report-cover-image-urls'

describe('report cover image URL backfill helpers', () => {
  it('builds candidates for linked reports whose products have no cover image', () => {
    const candidates = buildReportCoverCandidates([
      {
        id: 'report-avalanche',
        project_id: 'project-avalanche',
        product_id: 'product-avalanche',
        report_type: 'econ',
        language: 'en',
        status: 'published',
        published_at: '2026-05-02T09:06:00.000Z',
        updated_at: '2026-05-02T09:06:00.000Z',
        created_at: '2026-04-13T11:32:40.000Z',
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
    expect(candidates[0]).toMatchObject({
      reportId: 'report-avalanche',
      productId: 'product-avalanche',
      projectSlug: 'avalanche-2',
      reportType: 'econ',
      language: 'en',
      storagePath: 'econ/avalanche-2/latest/en.html',
      coverStoragePath: 'econ/avalanche-2/latest/en-cover.jpg',
      coverPublicUrl: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/en-cover.jpg',
    })
  })

  it('skips reports whose linked product already has a cover', () => {
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
          cover_image_url: 'https://example.supabase.co/storage/v1/object/public/slides/econ/avalanche-2/latest/en-cover.jpg',
        },
      },
    ], 'https://example.supabase.co')

    expect(candidates).toEqual([])
  })

  it('extracts the first embedded slide image from self-contained HTML', () => {
    const image = extractFirstEmbeddedImage('<img src="data:image/jpeg;base64,aGVsbG8=">')

    expect(image?.mimeType).toBe('image/jpeg')
    expect(image?.extension).toBe('jpg')
    expect(image?.bytes.toString('utf8')).toBe('hello')
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
})
