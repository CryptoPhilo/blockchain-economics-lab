import { fetchCMCTopListings } from './coinmarketcap'

describe('fetchCMCTopListings', () => {
  const originalEnv = process.env
  const originalFetch = global.fetch

  beforeEach(() => {
    process.env = { ...originalEnv }
    delete process.env.COINMARKETCAP_API_KEY
    delete process.env.CMC_API_KEY
    global.fetch = jest.fn()
    jest.spyOn(console, 'warn').mockImplementation(() => {})
    jest.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    process.env = originalEnv
    global.fetch = originalFetch
    jest.restoreAllMocks()
  })

  it('maps CMC listings into ranked snapshot-compatible rows', async () => {
    process.env.CMC_API_KEY = 'cmc-test-key'
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        data: [
          {
            slug: 'bitcoin',
            name: 'Bitcoin',
            symbol: 'BTC',
            cmc_rank: 1,
            quote: {
              USD: {
                price: 100,
                market_cap: 1000,
                percent_change_24h: 1.5,
              },
            },
          },
        ],
      }),
    })

    const rows = await fetchCMCTopListings(500)

    expect(global.fetch).toHaveBeenCalledWith(
      'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest?start=1&limit=500&sort=market_cap&convert=USD',
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-CMC_PRO_API_KEY': 'cmc-test-key',
        }),
      }),
    )
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({
      slug: 'bitcoin',
      name: 'Bitcoin',
      symbol: 'BTC',
      cmc_rank: 1,
      price_usd: 100,
      market_cap: 1000,
      change_24h: 1.5,
    })
    expect(rows[0].recorded_at).toEqual(expect.any(String))
  })

  it('returns an empty list when the API key is not configured', async () => {
    const rows = await fetchCMCTopListings(500)

    expect(rows).toEqual([])
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('returns an empty list when CMC returns an error response', async () => {
    process.env.COINMARKETCAP_API_KEY = 'cmc-test-key'
    ;(global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 429,
      statusText: 'Too Many Requests',
    })

    await expect(fetchCMCTopListings(500)).resolves.toEqual([])
  })
})
