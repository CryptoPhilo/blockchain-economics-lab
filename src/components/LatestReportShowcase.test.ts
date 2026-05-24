import {
  getReportCoverAsset,
  getReportHref,
  hasReportCover,
  isPublishedReportCoverCandidate,
} from './LatestReportShowcase'
import type { ProjectReport } from '@/lib/types'

function createReport(overrides: Partial<ProjectReport> = {}) {
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

  it('does not treat slide HTML as a cover asset when product cover backfill is missing', () => {
    const report = createReport({
      product: { ...createReport().product!, cover_image_url: '' },
      language: 'ko',
      slide_html_urls_by_lang: {
        ko: 'https://example.supabase.co/storage/v1/object/public/slides/econ/sei/latest/ko.html',
        en: 'https://example.supabase.co/storage/v1/object/public/slides/econ/sei/latest/en.html',
      },
    })

    expect(getReportCoverAsset(report)).toBeNull()
    expect(isPublishedReportCoverCandidate(report, 'ko')).toBe(false)
  })

  it('keeps latest cover candidates limited to published reports with locale support and covers', () => {
    expect(isPublishedReportCoverCandidate(createReport(), 'en')).toBe(true)
    expect(isPublishedReportCoverCandidate(createReport({ report_type: 'econ' }), 'en')).toBe(true)
    expect(isPublishedReportCoverCandidate(createReport({ report_type: 'maturity' }), 'en')).toBe(true)
    expect(isPublishedReportCoverCandidate(createReport({ status: 'in_review' }), 'en')).toBe(false)
    expect(isPublishedReportCoverCandidate(createReport({ status: 'coming_soon' }), 'en')).toBe(false)
    expect(isPublishedReportCoverCandidate(createReport({ language: 'ko' }), 'en')).toBe(false)
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
})
