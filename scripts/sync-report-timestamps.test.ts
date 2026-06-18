import {
  buildReportPublishUpdates,
  buildTimestampUpdates,
  parseArgs,
  resolveReportTimestamp,
  type ReportTimestampRow,
  type TrackedProjectTimestampRow,
} from './sync-report-timestamps'

const PROJECTS: TrackedProjectTimestampRow[] = [
  {
    id: 'bitcoin-id',
    name: 'Bitcoin',
    slug: 'bitcoin',
    last_econ_report_at: '2026-06-01T00:00:00.000Z',
    last_maturity_report_at: null,
    last_forensic_report_at: '2026-06-20T00:00:00.000Z',
  },
  {
    id: 'ethereum-id',
    name: 'Ethereum',
    slug: 'ethereum',
    last_econ_report_at: null,
    last_maturity_report_at: null,
    last_forensic_report_at: null,
  },
]

function report(overrides: Partial<ReportTimestampRow>): ReportTimestampRow {
  return {
    id: 'report-id',
    project_id: 'bitcoin-id',
    report_type: 'econ',
    status: 'published',
    published_at: '2026-06-10T00:00:00.000Z',
    updated_at: '2026-06-09T00:00:00.000Z',
    created_at: '2026-06-08T00:00:00.000Z',
    card_data: null,
    ...overrides,
  }
}

describe('resolveReportTimestamp', () => {
  it('prefers card_data.generated_at over report timestamps', () => {
    expect(resolveReportTimestamp(report({
      card_data: { generated_at: '2026-06-11T00:00:00.000Z' },
      published_at: '2026-06-10T00:00:00.000Z',
    }))).toEqual({
      timestamp: '2026-06-11T00:00:00.000Z',
      source: 'card_data.generated_at',
    })
  })

  it('falls back through published_at, updated_at, and created_at', () => {
    expect(resolveReportTimestamp(report({
      card_data: { generated_at: 'not-a-date' },
      published_at: '2026-06-10T00:00:00.000Z',
    }))?.source).toBe('published_at')
    expect(resolveReportTimestamp(report({
      published_at: null,
      updated_at: '2026-06-09T00:00:00.000Z',
    }))?.source).toBe('updated_at')
    expect(resolveReportTimestamp(report({
      published_at: null,
      updated_at: null,
      created_at: '2026-06-08T00:00:00.000Z',
    }))?.source).toBe('created_at')
    expect(resolveReportTimestamp(report({
      published_at: null,
      updated_at: null,
      created_at: null,
      card_data: { generated_at: 'invalid' },
    }))).toBeNull()
  })
})

describe('buildTimestampUpdates', () => {
  it('creates missing and stale tracked project timestamp updates without downgrades', () => {
    const updates = buildTimestampUpdates([
      report({
        id: 'btc-econ-new',
        card_data: { generated_at: '2026-06-12T00:00:00.000Z' },
      }),
      report({
        id: 'btc-econ-old',
        published_at: '2026-05-01T00:00:00.000Z',
      }),
      report({
        id: 'btc-forensic-older-than-tracked',
        report_type: 'forensic',
        published_at: '2026-06-10T00:00:00.000Z',
      }),
      report({
        id: 'eth-maturity-missing',
        project_id: 'ethereum-id',
        report_type: 'maturity',
        published_at: null,
        updated_at: '2026-06-13T00:00:00.000Z',
      }),
      report({
        id: 'eth-draft',
        project_id: 'ethereum-id',
        report_type: 'econ',
        status: 'draft',
        published_at: '2026-06-14T00:00:00.000Z',
      }),
      report({
        id: 'unknown-type',
        // Runtime DB data can be dirty even though the TS interface is narrow.
        report_type: 'slide' as ReportTimestampRow['report_type'],
        published_at: '2026-06-14T00:00:00.000Z',
      }),
    ], PROJECTS)

    expect(updates).toEqual([
      expect.objectContaining({
        projectId: 'bitcoin-id',
        reportId: 'btc-econ-new',
        reportType: 'econ',
        timestampField: 'last_econ_report_at',
        oldTimestamp: '2026-06-01T00:00:00.000Z',
        newTimestamp: '2026-06-12T00:00:00.000Z',
        source: 'card_data.generated_at',
        reason: 'stale',
      }),
      expect.objectContaining({
        projectId: 'ethereum-id',
        reportId: 'eth-maturity-missing',
        reportType: 'maturity',
        timestampField: 'last_maturity_report_at',
        oldTimestamp: null,
        newTimestamp: '2026-06-13T00:00:00.000Z',
        source: 'updated_at',
        reason: 'missing',
      }),
    ])
  })
})

describe('buildReportPublishUpdates', () => {
  it('corrects project_reports published_at only when card_data.generated_at is materially newer', () => {
    const updates = buildReportPublishUpdates([
      report({
        id: 'needs-correction',
        card_data: { generated_at: '2026-06-10T00:02:01.000Z' },
        published_at: '2026-06-10T00:00:00.000Z',
      }),
      report({
        id: 'within-threshold',
        card_data: { generated_at: '2026-06-10T00:01:00.000Z' },
        published_at: '2026-06-10T00:00:00.000Z',
      }),
      report({
        id: 'invalid-generated-at',
        card_data: { generated_at: 'not-a-date' },
        published_at: '2026-06-10T00:00:00.000Z',
      }),
      report({
        id: 'unsupported-type',
        report_type: 'slide' as ReportTimestampRow['report_type'],
        card_data: { generated_at: '2026-06-11T00:00:00.000Z' },
        published_at: '2026-06-10T00:00:00.000Z',
      }),
    ])

    expect(updates).toEqual([
      {
        reportId: 'needs-correction',
        projectId: 'bitcoin-id',
        reportType: 'econ',
        oldPublishedAt: '2026-06-10T00:00:00.000Z',
        newPublishedAt: '2026-06-10T00:02:01.000Z',
        source: 'card_data.generated_at',
      },
    ])
  })
})

describe('parseArgs', () => {
  it('defaults to dry-run and parses apply/page size flags', () => {
    expect(parseArgs([])).toEqual({ apply: false, pageSize: 1000 })
    expect(parseArgs(['--apply', '--page-size', '250'])).toEqual({ apply: true, pageSize: 250 })
    expect(parseArgs(['--apply', '--dry-run', '--page-size=500'])).toEqual({ apply: false, pageSize: 500 })
  })

  it('rejects unknown flags and invalid page sizes', () => {
    expect(() => parseArgs(['--unknown'])).toThrow('Unknown argument: --unknown')
    expect(() => parseArgs(['--page-size', '0'])).toThrow('--page-size must be a positive integer')
    expect(() => parseArgs(['--page-size'])).toThrow('--page-size requires a positive integer')
  })
})
