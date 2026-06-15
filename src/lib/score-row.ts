export interface ScoreRow {
  rank: number
  name: string
  symbol: string
  slug: string
  change24h: number | null
  marketCap: number
  score: number | null
  category: string
  reportTypes: string[]
  reportDates: {
    econ: string | null
    maturity: string | null
    forensic: string | null
  }
}
