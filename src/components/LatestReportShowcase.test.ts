import {
  dedupeLatestReportCoverCandidates,
  getReportHref,
  getShowcasePreview,
  hasReportCover,
  isPublishedReportCoverCandidate,
  selectLatestReportShowcaseCandidates,
} from '@/lib/latest-report-showcase'
import type { ProjectReport } from '@/lib/types'

function createReport(overrides: Record<string, unknown> = {}) {
  return {
    id: 'report-1',
    project_id: 'project-1',
    product_id: 'product-1',
    report_type: 'forensic',
    version: 1,
    status: 'published',
    language: 'en',
    assigned_at: '2026-05-01T00:00:00.000Z',
    created_at: '2026-05-01T00:00:00.000Z',
    product: {
      id: 'product-1',
      type: 'single_report',
      status: 'published',
      slug: 'report-product',
      title_en: 'Report Product',
      price_usd_cents: 0,
      cover_image_url: 'https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/covers/report.png',
      tags: [],
      featured: false,
      created_at: '2026-05-01T00:00:00.000Z',
    },
    project: {
      id: 'project-1',
      name: 'Pump Fun',
      slug: 'pump-fun',
      symbol: 'PUMP',
      status: 'active',
      discovered_at: '2026-05-01T00:00:00.000Z',
      forensic_monitoring: true,
      created_at: '2026-05-01T00:00:00.000Z',
    },
    ...overrides,
  } as ProjectReport
}

describe('LatestReportShowcase helpers', () => {
  it('detects reports with linked product cover images', () => {
    expect(hasReportCover(createReport())).toBe(true)
    expect(hasReportCover(createReport({ product: { ...createReport().product!, cover_image_url: '' } }))).toBe(false)
  })

  it('keeps latest cover candidates limited to published ECON/MAT/FOR reports with covers', () => {
    expect(isPublishedReportCoverCandidate(createReport(), 'en')).toBe(true)
    expect(isPublishedReportCoverCandidate(createReport({ report_type: 'econ' }), 'en')).toBe(true)
    expect(isPublishedReportCoverCandidate(createReport({ report_type: 'maturity' }), 'en')).toBe(true)
    expect(isPublishedReportCoverCandidate(createReport({ report_type: 'forensic' }), 'en')).toBe(true)
    expect(isPublishedReportCoverCandidate(createReport({ status: 'in_review' }), 'en')).toBe(false)
    expect(isPublishedReportCoverCandidate(
      createReport({ report_type: 'forensic', status: 'coming_soon' }),
      'en',
    )).toBe(false)
    expect(isPublishedReportCoverCandidate(createReport({ language: 'ko' }), 'en')).toBe(true)
    expect(isPublishedReportCoverCandidate(createReport({ language: 'ko' }), 'ko')).toBe(true)
    expect(isPublishedReportCoverCandidate(
      createReport({ product: { ...createReport().product!, cover_image_url: '' } }),
      'en',
    )).toBe(false)
  })

  it('builds report links by report type', () => {
    expect(getReportHref(createReport({ report_type: 'forensic' }), 'en')).toBe('/en/reports/forensic/pump-fun')
    expect(getReportHref(createReport({ report_type: 'econ' }), 'ko')).toBe('/ko/reports/pump-fun/econ')
    expect(getReportHref(createReport({ report_type: 'maturity' }), 'en')).toBe('/en/reports/pump-fun/maturity')
  })

  it('prefers stable product covers over generated slide thumbnails for showcase previews', () => {
    const report = createReport({
      slide_html_urls_by_lang: {
        ko: 'https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/slides/reports/demo.html',
      },
    })

    expect(getShowcasePreview(report, 'ko')).toEqual({
      url: 'https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/covers/report.png',
      kind: 'image',
    })
  })

  it('uses the slide pipeline cover image when a report has no linked product cover', () => {
    const report = createReport({
      product: null,
      product_id: null,
      report_type: 'maturity',
      slide_html_urls_by_lang: {
        ko: 'https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/slides/mat/nockchain/latest/ko.html',
      },
    })

    expect(getShowcasePreview(report, 'ko')).toEqual({
      url: 'https://wbqponoiyoeqlepxogcb.supabase.co/storage/v1/object/public/slides/mat/nockchain/latest/ko-cover.jpg',
      kind: 'image',
    })
  })

  it('dedupes cover candidates by project and report type and keeps newest version', () => {
    const oldEcon = createReport({
      id: 'btc-econ-v1',
      project_id: 'project-bitcoin',
      version: 1,
      is_latest: false,
      report_type: 'econ',
      updated_at: '2026-05-20T00:00:00.000Z',
    })
    const newEcon = createReport({
      id: 'btc-econ-v2',
      project_id: 'project-bitcoin',
      version: 2,
      is_latest: true,
      report_type: 'econ',
      updated_at: '2026-05-26T00:00:00.000Z',
    })
    const newEconEnSibling = createReport({
      id: 'btc-econ-v2-en',
      project_id: 'project-bitcoin',
      version: 2,
      is_latest: true,
      report_type: 'econ',
      language: 'en',
      updated_at: '2026-05-26T01:00:00.000Z',
    })

    const latest = dedupeLatestReportCoverCandidates([oldEcon, newEconEnSibling, newEcon])

    expect(latest).toHaveLength(1)
    expect(latest[0]!.id).toBe('btc-econ-v2-en')
  })

  it('keeps one candidate per report type when a project has multiple types', () => {
    const latestEcon = createReport({
      id: 'btc-econ-v2',
      project_id: 'project-bitcoin',
      version: 2,
      report_type: 'econ',
    })
    const latestMat = createReport({
      id: 'btc-maturity-v2',
      project_id: 'project-bitcoin',
      version: 2,
      report_type: 'maturity',
    })

    const latest = dedupeLatestReportCoverCandidates([latestEcon, latestMat])

    expect(latest).toHaveLength(2)
    expect(latest.map((report) => report.id).sort()).toEqual(['btc-econ-v2', 'btc-maturity-v2'])
  })

  it('orders showcase candidates by report publication date instead of file update time', () => {
    const backfilledOldReport = createReport({
      id: 'old-report-backfilled-later',
      project_id: 'project-old',
      report_type: 'maturity',
      language: 'ko',
      published_at: '2026-05-20T00:00:00.000Z',
      updated_at: '2026-06-11T09:00:00.000Z',
      slide_html_urls_by_lang: { ko: 'https://example.com/old.html' },
    })
    const newlyPublishedReport = createReport({
      id: 'new-report-published-later',
      project_id: 'project-new',
      report_type: 'maturity',
      language: 'ko',
      published_at: '2026-06-10T00:00:00.000Z',
      updated_at: '2026-06-10T01:00:00.000Z',
      slide_html_urls_by_lang: { ko: 'https://example.com/new.html' },
    })

    const latest = selectLatestReportShowcaseCandidates(
      [backfilledOldReport, newlyPublishedReport],
      'ko',
    )

    expect(latest.map((report) => report.id)).toEqual([
      'new-report-published-later',
      'old-report-backfilled-later',
    ])
  })

  it('selects the same showcase project/type groups while preferring locale siblings', () => {
    const enFlare = createReport({
      id: 'flare-econ-v1-en',
      project_id: 'project-flare',
      report_type: 'econ',
      language: 'en',
      updated_at: '2026-06-10T01:00:00.000Z',
      slide_html_urls_by_lang: { en: 'https://example.com/flare-en.html' },
    })
    const koFlare = createReport({
      id: 'flare-econ-v1-ko',
      project_id: 'project-flare',
      report_type: 'econ',
      language: 'ko',
      updated_at: '2026-06-10T00:00:00.000Z',
      slide_html_urls_by_lang: { ko: 'https://example.com/flare-ko.html' },
    })
    const enXrp = createReport({
      id: 'xrp-maturity-v1-en',
      project_id: 'project-xrp',
      report_type: 'maturity',
      language: 'en',
      updated_at: '2026-06-09T01:00:00.000Z',
      slide_html_urls_by_lang: { en: 'https://example.com/xrp-en.html' },
    })
    const koXrp = createReport({
      id: 'xrp-maturity-v1-ko',
      project_id: 'project-xrp',
      report_type: 'maturity',
      language: 'ko',
      updated_at: '2026-06-09T00:00:00.000Z',
      slide_html_urls_by_lang: { ko: 'https://example.com/xrp-ko.html' },
    })

    const enSelection = selectLatestReportShowcaseCandidates([enFlare, koFlare, enXrp, koXrp], 'en')
    const koSelection = selectLatestReportShowcaseCandidates([enFlare, koFlare, enXrp, koXrp], 'ko')

    expect(enSelection.map((report) => `${report.project_id}:${report.report_type}`)).toEqual([
      'project-flare:econ',
      'project-xrp:maturity',
    ])
    expect(koSelection.map((report) => `${report.project_id}:${report.report_type}`)).toEqual([
      'project-flare:econ',
      'project-xrp:maturity',
    ])
    expect(koSelection.map((report) => report.language)).toEqual(['ko', 'ko'])
  })
})
