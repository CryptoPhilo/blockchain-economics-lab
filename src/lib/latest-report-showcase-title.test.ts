import { getShowcaseDisplayTitle, type ReportWithCover } from './latest-report-showcase'

describe('getShowcaseDisplayTitle', () => {
  it('uses project names instead of file-like English product titles', () => {
    const report = {
      report_type: 'maturity',
      product: {
        title_en: 'Velvet MAT en',
        title_ko: 'Velvet MAT ko',
      },
      project: {
        name: 'Velvet',
        symbol: 'VELVET',
      },
    } as ReportWithCover

    expect(getShowcaseDisplayTitle(report)).toBe('Velvet')
    expect(getShowcaseDisplayTitle(report)).not.toMatch(/\b(?:ECON|MAT|FOR)\s+(?:en|ko|fr|es|de|ja|zh)\b/i)
  })

  it('prefers joined tracked project names when available', () => {
    const report = {
      report_type: 'econ',
      tracked_projects: {
        name: 'Ondo Finance',
        symbol: 'ONDO',
      },
      product: {
        title_en: 'Ondo Finance ECON en',
      },
      project: {
        name: 'Ondo',
        symbol: 'ONDO',
      },
    } as ReportWithCover

    expect(getShowcaseDisplayTitle(report)).toBe('Ondo Finance')
  })
})
