/**
 * Verify Walrus CMC slug
 */

import { fetchCMCPrices } from '../src/lib/coinmarketcap'
import { config } from 'dotenv'
import { join } from 'path'

config({ path: join(__dirname, '..', '.env.local') })

async function main() {
  console.log('🔍 Verifying Walrus CMC slug...\n')

  const result = await fetchCMCPrices(['walrus-xyz'])

  if (result['walrus-xyz']) {
    console.log('✅ walrus-xyz verified!')
    console.log('Price:', result['walrus-xyz'].usd)
    console.log('24h change:', result['walrus-xyz'].usd_24h_change)
    console.log('Market cap:', result['walrus-xyz'].usd_market_cap)
  } else {
    console.log('❌ walrus-xyz not found')
  }
}

main().catch(console.error)
