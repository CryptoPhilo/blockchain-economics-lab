import { ProjectsRepository } from './projects'

describe('ProjectsRepository.getLatestScoreboardMarketSnapshot', () => {
  it('queries the latest canonical CMC Top 500 by cmc_rank', async () => {
    const latestSnapshotQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockReturnThis(),
      maybeSingle: jest.fn().mockResolvedValue({
        data: { recorded_at: '2026-05-12' },
        error: null,
      }),
    }
    const marketSnapshotQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: [
          {
            slug: 'bitcoin',
            price_usd: 100000,
            market_cap: 1,
            change_24h: 0,
            recorded_at: '2026-05-12',
            cmc_rank: 1,
          },
        ],
        error: null,
      }),
    }
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(latestSnapshotQuery)
        .mockReturnValueOnce(marketSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    await repository.getLatestScoreboardMarketSnapshot()

    expect(latestSnapshotQuery.eq).toHaveBeenCalledWith('source', 'coinmarketcap')
    expect(latestSnapshotQuery.gte).toHaveBeenCalledWith('cmc_rank', 1)
    expect(latestSnapshotQuery.lte).toHaveBeenCalledWith('cmc_rank', 500)
    expect(marketSnapshotQuery.select).toHaveBeenCalledWith(
      'slug, price_usd, market_cap, change_24h, recorded_at, cmc_rank',
    )
    expect(marketSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-12')
    expect(marketSnapshotQuery.eq).toHaveBeenCalledWith('source', 'coinmarketcap')
    expect(marketSnapshotQuery.gte).toHaveBeenCalledWith('cmc_rank', 1)
    expect(marketSnapshotQuery.lte).toHaveBeenCalledWith('cmc_rank', 500)
    expect(marketSnapshotQuery.order).toHaveBeenCalledWith(
      'cmc_rank',
      { ascending: true, nullsFirst: false },
    )
    expect(marketSnapshotQuery.limit).toHaveBeenCalledWith(500)
  })
})
