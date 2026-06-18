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

function makeCandidateQuery(rows: Array<{ recorded_at: string; cmc_rank: number }>) {
  return {
    select: jest.fn().mockReturnThis(),
    eq: jest.fn().mockReturnThis(),
    gte: jest.fn().mockReturnThis(),
    lte: jest.fn().mockReturnThis(),
    order: jest.fn().mockReturnThis(),
    limit: jest.fn().mockResolvedValue({
      data: rows,
      error: null,
    }),
  }
}

describe('ProjectsRepository.getLatestScoreboardMarketSnapshot', () => {
  it('loads the latest complete CMC Top 500 snapshot without probing partial dates', async () => {
    const candidateQuery = makeCandidateQuery(
      Array.from({ length: 500 }, (_, index) => makeRankRow(index + 1, '2026-05-12')),
    )
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
        .mockReturnValueOnce(candidateQuery)
        .mockReturnValueOnce(latestSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestScoreboardMarketSnapshot()

    expect(rows).toHaveLength(500)
    expect(rows[0]).toMatchObject({ recorded_at: '2026-05-12', cmc_rank: 1 })
    expect(rows[499]).toMatchObject({ recorded_at: '2026-05-12', cmc_rank: 500 })
    expect(supabase.from).toHaveBeenCalledTimes(2)
    expect(candidateQuery.select).toHaveBeenCalledWith('recorded_at, cmc_rank')
    expect(latestSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-12')
  })

  it('selects the latest complete Top 500 snapshot when the newest CMC date is partial', async () => {
    const candidateQuery = makeCandidateQuery([
      makeRankRow(1, '2026-05-12'),
      ...Array.from({ length: 500 }, (_, index) => makeRankRow(index + 1, '2026-05-11')),
    ])
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
        .mockReturnValueOnce(candidateQuery)
        .mockReturnValueOnce(previousSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestScoreboardMarketSnapshot()

    expect(rows).toHaveLength(500)
    expect(rows[0]).toMatchObject({ recorded_at: '2026-05-11', cmc_rank: 1 })
    expect(rows[499]).toMatchObject({ recorded_at: '2026-05-11', cmc_rank: 500 })
    expect(supabase.from).toHaveBeenCalledTimes(2)
    expect(candidateQuery.eq).toHaveBeenCalledWith('source', 'coinmarketcap')
    expect(candidateQuery.gte).toHaveBeenCalledWith('cmc_rank', 1)
    expect(candidateQuery.lte).toHaveBeenCalledWith('cmc_rank', 500)
    expect(previousSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-11')
  })
})

describe('ProjectsRepository.getLatestCmcRanks', () => {
  it('uses the latest complete rank snapshot', async () => {
    const candidateQuery = makeCandidateQuery(
      Array.from({ length: 200 }, (_, index) => makeRankRow(index + 1, '2026-05-12')),
    )
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
        .mockReturnValueOnce(candidateQuery)
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

  it('selects the latest complete rank snapshot when the newest CMC date is partial', async () => {
    const candidateQuery = makeCandidateQuery([
      makeRankRow(1, '2026-05-12'),
      ...Array.from({ length: 200 }, (_, index) => makeRankRow(index + 1, '2026-05-11')),
    ])
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
        .mockReturnValueOnce(candidateQuery)
        .mockReturnValueOnce(previousRankQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestCmcRanks(200)

    expect(rows).toHaveLength(200)
    expect(rows[0]).toEqual(makeRankRow(1, '2026-05-11'))
    expect(rows[199]).toEqual(makeRankRow(200, '2026-05-11'))
    expect(supabase.from).toHaveBeenCalledTimes(2)
    expect(candidateQuery.lte).toHaveBeenCalledWith('cmc_rank', 200)
    expect(previousRankQuery.select).toHaveBeenCalledWith('slug, cmc_rank')
    expect(previousRankQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-11')
  })
})
