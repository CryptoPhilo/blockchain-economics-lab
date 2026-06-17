export interface ScoreRow {
  rank: number | null
  name: string
  symbol: string
  slug: string
  cmcRank?: number | null
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
