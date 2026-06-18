import {
  applyProjectReportAvailabilityAliases,
  buildReportAvailabilityByProjectId,
  createEmptyReportAvailability,
  getMatchingProjectReportAliasIds,
} from './report-availability'

describe('report availability alias matching', () => {
  it('keeps an older localized report available when the global latest version is not localized', () => {
    const availability = buildReportAvailabilityByProjectId([
      {
        id: 'bitcoin-mat-v3-en',
        project_id: 'bitcoin-project',
        report_type: 'maturity',
        version: 3,
        language: 'en',
        published_at: '2026-06-17T08:42:17.463762+00:00',
        slide_html_urls_by_lang: { en: 'https://www.bcelab.xyz/slides/mat/bitcoin/latest/en.html' },
      },
      {
        id: 'bitcoin-mat-v2-ko',
        project_id: 'bitcoin-project',
        report_type: 'maturity',
        version: 2,
        language: 'ko',
        published_at: '2026-06-17T08:43:27.074239+00:00',
        slide_html_urls_by_lang: { ko: 'https://www.bcelab.xyz/slides/mat/bitcoin/latest/ko.html' },
      },
    ], 'ko')

    expect(availability.get('bitcoin-project')).toEqual({
      reportTypes: ['maturity'],
      reportDates: {
        econ: null,
        maturity: '2026-06-17T08:43:27.074239+00:00',
        forensic: null,
      },
    })
  })

  it('matches USD.AI report aliases across duplicate tracked project rows', () => {
    const project = {
      id: 'usd-ai-chip',
      slug: 'usd-ai',
      name: 'USD.AI',
      symbol: 'CHIP',
      coingecko_id: null,
      cmc_id: 39870,
      aliases: [],
    }
    const candidates = [
      project,
      {
        id: 'usdai-usdai',
        slug: 'usdai',
        name: 'USDai',
        symbol: 'USDAI',
        coingecko_id: 'usdai',
        cmc_id: null,
        aliases: ['USD.AI', 'usd.ai', 'usd ai', 'usdai'],
      },
    ]

    expect(getMatchingProjectReportAliasIds(project, candidates)).toEqual([
      'usd-ai-chip',
      'usdai-usdai',
    ])
  })

  it('maps canonical report availability back onto the listed project row', () => {
    const listedProject = {
      id: 'usd-ai-chip',
      slug: 'usd-ai',
      name: 'USD.AI',
      symbol: 'CHIP',
      coingecko_id: null,
      cmc_id: 39870,
      aliases: [],
    }
    const canonicalProject = {
      id: 'usdai-usdai',
      slug: 'usdai',
      name: 'USDai',
      symbol: 'USDAI',
      coingecko_id: 'usdai',
      cmc_id: null,
      aliases: ['USD.AI', 'usd.ai', 'usd ai', 'usdai'],
    }

    const availabilityByProjectId = new Map([
      ['usd-ai-chip', createEmptyReportAvailability()],
      ['usdai-usdai', {
        reportTypes: ['econ', 'maturity'],
        reportDates: {
          econ: '2026-06-08T22:13:03.696846+00:00',
          maturity: '2026-06-08T10:42:28+00:00',
          forensic: null,
        },
      }],
    ])

    applyProjectReportAvailabilityAliases(
      availabilityByProjectId,
      [listedProject],
      [listedProject, canonicalProject],
    )

    expect(availabilityByProjectId.get('usd-ai-chip')).toEqual(
      availabilityByProjectId.get('usdai-usdai'),
    )
  })
})
