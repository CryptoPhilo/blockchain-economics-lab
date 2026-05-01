import { cleanCardSummary } from './report-summary'

describe('cleanCardSummary', () => {
  it('cleans project detail card summaries before rendering', () => {
    expect(cleanCardSummary('Token economy overview. ### Risk Factors')).toBe(
      'Token economy overview.',
    )
  })

  it('cleans forensic detail summaries before rendering', () => {
    expect(cleanCardSummary('Suspicious wallet activity detected. | Metric | Value |')).toBe(
      'Suspicious wallet activity detected.',
    )
  })

  it('cleans forensic slide card summaries before rendering', () => {
    expect(cleanCardSummary('Market anomaly context. - Exchange flow spike - Whale exits')).toBe(
      'Market anomaly context.',
    )
  })
})
