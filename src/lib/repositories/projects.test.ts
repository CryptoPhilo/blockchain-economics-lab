import { ProjectsRepository } from './projects'

function makeMarketSnapshotRow(rank: number, recordedAt: string) {
  return {
    slug: `cmc-project-${rank}`,
    price_usd: 100000 - rank,
    market_cap: 1_000_000 - rank,
    change_24h: 0,
    recorded_at: recordedAt,
    cmc_rank: rank,
  }
}

function makeRankRow(rank: number, recordedAt: string) {
  return {
    slug: `cmc-project-${rank}`,
    cmc_rank: rank,
    recorded_at: recordedAt,
  }
}

function makeLatestDateQuery(recordedAt: string | null) {
  return {
    select: jest.fn().mockReturnThis(),
    eq: jest.fn().mockReturnThis(),
    gte: jest.fn().mockReturnThis(),
    lte: jest.fn().mockReturnThis(),
    order: jest.fn().mockReturnThis(),
    limit: jest.fn().mockReturnThis(),
    maybeSingle: jest.fn().mockResolvedValue({
      data: recordedAt ? { recorded_at: recordedAt } : null,
      error: null,
    }),
  }
}

describe('ProjectsRepository.getLatestScoreboardMarketSnapshot', () => {
  it('uses the two-query fast path when the latest CMC Top 500 snapshot is complete', async () => {
    const latestDateQuery = makeLatestDateQuery('2026-05-12')
    const latestSnapshotQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: Array.from({ length: 500 }, (_, index) => makeMarketSnapshotRow(index + 1, '2026-05-12')),
        error: null,
      }),
    }
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(latestDateQuery)
        .mockReturnValueOnce(latestSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestScoreboardMarketSnapshot()

    expect(rows).toHaveLength(500)
    expect(rows[0]).toMatchObject({ recorded_at: '2026-05-12', cmc_rank: 1 })
    expect(rows[499]).toMatchObject({ recorded_at: '2026-05-12', cmc_rank: 500 })
    expect(supabase.from).toHaveBeenCalledTimes(2)
    expect(latestDateQuery.maybeSingle).toHaveBeenCalled()
    expect(latestSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-12')
  })

  it('falls back to the latest complete Top 500 snapshot when the newest CMC date is partial', async () => {
    const latestDateQuery = makeLatestDateQuery('2026-05-12')
    const recentDatesQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: [
          { recorded_at: '2026-05-12' },
          { recorded_at: '2026-05-12' },
          { recorded_at: '2026-05-11' },
        ],
        error: null,
      }),
    }
    const newestSnapshotQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: [makeMarketSnapshotRow(1, '2026-05-12')],
        error: null,
      }),
    }
    const previousSnapshotQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: Array.from({ length: 500 }, (_, index) => makeMarketSnapshotRow(index + 1, '2026-05-11')),
        error: null,
      }),
    }
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(latestDateQuery)
        .mockReturnValueOnce(newestSnapshotQuery)
        .mockReturnValueOnce(recentDatesQuery)
        .mockReturnValueOnce(previousSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestScoreboardMarketSnapshot()

    expect(rows).toHaveLength(500)
    expect(rows[0]).toMatchObject({ recorded_at: '2026-05-11', cmc_rank: 1 })
    expect(rows[499]).toMatchObject({ recorded_at: '2026-05-11', cmc_rank: 500 })
    expect(supabase.from).toHaveBeenCalledTimes(4)
    expect(recentDatesQuery.eq).toHaveBeenCalledWith('source', 'coinmarketcap')
    expect(recentDatesQuery.gte).toHaveBeenCalledWith('cmc_rank', 1)
    expect(recentDatesQuery.lte).toHaveBeenCalledWith('cmc_rank', 500)
    expect(newestSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-12')
    expect(previousSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-11')
  })
})

describe('ProjectsRepository.getLatestCmcRanks', () => {
  it('uses the two-query fast path when the latest rank snapshot is complete', async () => {
    const latestDateQuery = makeLatestDateQuery('2026-05-12')
    const latestRankQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: Array.from({ length: 200 }, (_, index) => makeRankRow(index + 1, '2026-05-12')),
        error: null,
      }),
    }
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(latestDateQuery)
        .mockReturnValueOnce(latestRankQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestCmcRanks(200)

    expect(rows).toHaveLength(200)
    expect(rows[0]).toEqual(makeRankRow(1, '2026-05-12'))
    expect(rows[199]).toEqual(makeRankRow(200, '2026-05-12'))
    expect(supabase.from).toHaveBeenCalledTimes(2)
    expect(latestRankQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-12')
  })

  it('falls back to the latest complete rank snapshot when the newest CMC date is partial', async () => {
    const latestDateQuery = makeLatestDateQuery('2026-05-12')
    const recentDatesQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: [
          { recorded_at: '2026-05-12' },
          { recorded_at: '2026-05-12' },
          { recorded_at: '2026-05-11' },
        ],
        error: null,
      }),
    }
    const newestRankQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: [makeRankRow(1, '2026-05-12')],
        error: null,
      }),
    }
    const previousRankQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: Array.from({ length: 200 }, (_, index) => makeRankRow(index + 1, '2026-05-11')),
        error: null,
      }),
    }
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(latestDateQuery)
        .mockReturnValueOnce(newestRankQuery)
        .mockReturnValueOnce(recentDatesQuery)
        .mockReturnValueOnce(previousRankQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestCmcRanks(200)

    expect(rows).toHaveLength(200)
    expect(rows[0]).toEqual(makeRankRow(1, '2026-05-11'))
    expect(rows[199]).toEqual(makeRankRow(200, '2026-05-11'))
    expect(supabase.from).toHaveBeenCalledTimes(4)
    expect(recentDatesQuery.lte).toHaveBeenCalledWith('cmc_rank', 200)
    expect(newestRankQuery.select).toHaveBeenCalledWith('slug, cmc_rank')
    expect(newestRankQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-12')
    expect(previousRankQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-11')
  })
})
