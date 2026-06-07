import { ProjectsRepository } from './projects'

describe('ProjectsRepository.getLatestScoreboardMarketSnapshot', () => {
  function makeSnapshotDateQuery(recordedAtRows: { recorded_at: string }[]) {
    return {
      select: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      range: jest.fn().mockResolvedValue({
        data: recordedAtRows,
        error: null,
      }),
    }
  }

  function makeMarketSnapshotQuery(rows: unknown[] | null, error: unknown = null) {
    return {
      select: jest.fn().mockReturnThis(),
      eq: jest.fn().mockReturnThis(),
      gte: jest.fn().mockReturnThis(),
      lte: jest.fn().mockReturnThis(),
      order: jest.fn().mockReturnThis(),
      limit: jest.fn().mockResolvedValue({
        data: rows,
        error,
      }),
    }
  }

  function makeMarketSnapshotRow(rank: number, recordedAt = '2026-05-12') {
    return {
      slug: `cmc-project-${rank}`,
      price_usd: 100000 - rank,
      market_cap: 1_000_000 - rank,
      change_24h: 0,
      recorded_at: recordedAt,
      cmc_rank: rank,
      cmc_symbol: `P${rank}`,
      cmc_name: `CMC Project ${rank}`,
    }
  }

  it('queries the latest canonical CMC Top 500 by cmc_rank', async () => {
    const latestSnapshotQuery = makeSnapshotDateQuery([{ recorded_at: '2026-05-12' }])
    const marketSnapshotQuery = makeMarketSnapshotQuery(
      Array.from({ length: 500 }, (_, index) => makeMarketSnapshotRow(index + 1)),
    )
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(latestSnapshotQuery)
        .mockReturnValueOnce(marketSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    await repository.getLatestScoreboardMarketSnapshot()

    expect(latestSnapshotQuery.select).toHaveBeenCalledWith('recorded_at')
    expect(latestSnapshotQuery.gte).toHaveBeenCalledWith('cmc_rank', 1)
    expect(latestSnapshotQuery.lte).toHaveBeenCalledWith('cmc_rank', 500)
    expect(latestSnapshotQuery.order).toHaveBeenCalledWith('recorded_at', { ascending: false })
    expect(latestSnapshotQuery.range).toHaveBeenCalledWith(0, 999)
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

  it('skips a newer partial snapshot and returns the latest complete canonical Top 500 snapshot', async () => {
    const latestSnapshotQuery = makeSnapshotDateQuery([
      { recorded_at: '2026-06-07T07:00:00.000Z' },
      { recorded_at: '2026-06-07T07:00:00.000Z' },
      { recorded_at: '2026-06-07T06:00:00.000Z' },
    ])
    const partialMarketSnapshotQuery = makeMarketSnapshotQuery(
      Array.from({ length: 12 }, (_, index) => makeMarketSnapshotRow(index + 1, '2026-06-07T07:00:00.000Z')),
    )
    const completeMarketSnapshotQuery = makeMarketSnapshotQuery(
      Array.from({ length: 500 }, (_, index) => makeMarketSnapshotRow(index + 1, '2026-06-07T06:00:00.000Z')),
    )
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(latestSnapshotQuery)
        .mockReturnValueOnce(partialMarketSnapshotQuery)
        .mockReturnValueOnce(completeMarketSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestScoreboardMarketSnapshot()

    expect(partialMarketSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-06-07T07:00:00.000Z')
    expect(completeMarketSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-06-07T06:00:00.000Z')
    expect(rows).toHaveLength(500)
    expect(rows[0]).toMatchObject({ cmc_rank: 1, recorded_at: '2026-06-07T06:00:00.000Z' })
    expect(rows[499]).toMatchObject({ cmc_rank: 500, recorded_at: '2026-06-07T06:00:00.000Z' })
  })

  it('paginates snapshot date candidates when recent partial snapshots fill the first response page', async () => {
    const firstDatePageQuery = makeSnapshotDateQuery(
      Array.from({ length: 1000 }, () => ({ recorded_at: '2026-06-07T07:00:00.000Z' })),
    )
    const secondDatePageQuery = makeSnapshotDateQuery([
      { recorded_at: '2026-06-07T06:00:00.000Z' },
    ])
    const partialMarketSnapshotQuery = makeMarketSnapshotQuery(
      Array.from({ length: 12 }, (_, index) => makeMarketSnapshotRow(index + 1, '2026-06-07T07:00:00.000Z')),
    )
    const completeMarketSnapshotQuery = makeMarketSnapshotQuery(
      Array.from({ length: 500 }, (_, index) => makeMarketSnapshotRow(index + 1, '2026-06-07T06:00:00.000Z')),
    )
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(firstDatePageQuery)
        .mockReturnValueOnce(secondDatePageQuery)
        .mockReturnValueOnce(partialMarketSnapshotQuery)
        .mockReturnValueOnce(completeMarketSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestScoreboardMarketSnapshot()

    expect(firstDatePageQuery.range).toHaveBeenCalledWith(0, 999)
    expect(secondDatePageQuery.range).toHaveBeenCalledWith(1000, 1999)
    expect(partialMarketSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-06-07T07:00:00.000Z')
    expect(completeMarketSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-06-07T06:00:00.000Z')
    expect(rows).toHaveLength(500)
  })

  it('returns no rows when no recent candidate is a complete canonical Top 500 snapshot', async () => {
    const latestSnapshotQuery = makeSnapshotDateQuery([
      { recorded_at: '2026-06-07T07:00:00.000Z' },
      { recorded_at: '2026-06-07T06:00:00.000Z' },
    ])
    const firstPartialMarketSnapshotQuery = makeMarketSnapshotQuery(
      Array.from({ length: 100 }, (_, index) => makeMarketSnapshotRow(index + 1, '2026-06-07T07:00:00.000Z')),
    )
    const secondPartialMarketSnapshotQuery = makeMarketSnapshotQuery(
      Array.from({ length: 250 }, (_, index) => makeMarketSnapshotRow(index + 1, '2026-06-07T06:00:00.000Z')),
    )
    const supabase = {
      from: jest.fn()
        .mockReturnValueOnce(latestSnapshotQuery)
        .mockReturnValueOnce(firstPartialMarketSnapshotQuery)
        .mockReturnValueOnce(secondPartialMarketSnapshotQuery),
    }
    const repository = new ProjectsRepository(supabase as never)

    const rows = await repository.getLatestScoreboardMarketSnapshot()

    expect(firstPartialMarketSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-06-07T07:00:00.000Z')
    expect(secondPartialMarketSnapshotQuery.eq).toHaveBeenCalledWith('recorded_at', '2026-06-07T06:00:00.000Z')
    expect(rows).toEqual([])
  })

  it('falls back to the legacy snapshot select while the CMC identity migration is pending', async () => {
    const latestSnapshotQuery = makeSnapshotDateQuery([{ recorded_at: '2026-05-12' }])
    const missingColumnQuery = makeMarketSnapshotQuery(
      null,
      { code: '42703', message: 'column market_data_daily.cmc_symbol does not exist' },
    )
    const legacyMarketSnapshotQuery = makeMarketSnapshotQuery(
      Array.from({ length: 500 }, (_, index) => {
        const { cmc_symbol: _cmcSymbol, cmc_name: _cmcName, ...row } = makeMarketSnapshotRow(index + 1)
        return row
      }),
    )
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
    expect(rows).toHaveLength(500)
  })
})
