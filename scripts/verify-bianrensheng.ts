/**
 * Verify 币安人生 (bianrensheng) CMC slug
 */

import { fetchCMCPrices } from '../src/lib/coinmarketcap'
import { config } from 'dotenv'
import { join } from 'path'

config({ path: join(__dirname, '..', '.env.local') })

async function main() {
  console.log('🔍 Verifying 币安人生 (bianrensheng) CMC slug...\n')

  const result = await fetchCMCPrices(['bianrensheng'])

  if (result['bianrensheng']) {
    console.log('✅ bianrensheng verified!')
    console.log('Price:', result['bianrensheng'].usd)
    console.log('24h change:', result['bianrensheng'].usd_24h_change)
    console.log('Market cap:', result['bianrensheng'].usd_market_cap)
  } else {
    console.log('❌ bianrensheng not found')
  }
}

main().catch(console.error)
