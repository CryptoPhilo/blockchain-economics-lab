import { ProjectsRepository } from './projects'

describe('ProjectsRepository.getLatestScoreboardMarketSnapshot', () => {
  it('queries the latest canonical CMC Top 500 by cmc_rank', async () => {
    const latestSnapshotQuery = {
      select: jest.fn().mockReturnThis(),
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
            cmc_symbol: 'BTC',
            cmc_name: 'Bitcoin',
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

    expect(marketSnapshotQuery.select).toHaveBeenCalledWith(
      'slug, price_usd, market_cap, change_24h, recorded_at, cmc_rank, cmc_symbol, cmc_name',
    )
    expect(marketSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-05-12')
    expect(marketSnapshotQuery.gte).toHaveBeenCalledWith('cmc_rank', 1)
    expect(marketSnapshotQuery.lte).toHaveBeenCalledWith('cmc_rank', 500)
    expect(marketSnapshotQuery.order).toHaveBeenCalledWith(
      'cmc_rank',
      { ascending: true, nullsFirst: false },
    )
    expect(marketSnapshotQuery.limit).toHaveBeenCalledWith(500)
  })

  it('falls back to the legacy snapshot select while the CMC identity migration is pending', async () => {
    const latestSnapshotQuery = {
      select: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockReturnThis(),
      maybeSingle: jest.fn().mockResolvedValue({
        data: { recorded_at: '2026-05-12' },
        error: null,
      }),
    }
    const missingColumnQuery = {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: null,
        error: { code: '42703', message: 'column market_data_daily.cmc_symbol does not exist' },
      }),
    }
    const legacyMarketSnapshotQuery = {
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
        .mockReturnValueOnce(missingColumnQuery)
        .mockReturnValueOnce(legacyMarketSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestScoreboardMarketSnapshot()

    expect(missingColumnQuery.select).toHaveBeenCalledWith(
      'slug, price_usd, market_cap, change_24h, recorded_at, cmc_rank, cmc_symbol, cmc_name',
    )
    expect(legacyMarketSnapshotQuery.select).toHaveBeenCalledWith(
      'slug, price_usd, market_cap, change_24h, recorded_at, cmc_rank',
    )
    expect(rows).toHaveLength(1)
  })
})
