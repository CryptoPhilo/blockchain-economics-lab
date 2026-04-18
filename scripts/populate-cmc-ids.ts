/**
 * Populate CoinMarketCap IDs for tokens not available on CoinGecko
 *
 * This script searches CoinMarketCap for the 18 unlisted tokens identified in BCE-318
 * and updates the tracked_projects table with their CMC slugs for price data fallback.
 *
 * Usage:
 *   npx tsx scripts/populate-cmc-ids.ts
 *
 * Environment:
 *   Requires COINMARKETCAP_API_KEY in .env.local
 */

import { createClient } from '@supabase/supabase-js'
import { searchCMC, fetchCMCPrices } from '../src/lib/coinmarketcap'
import { config } from 'dotenv'
import { join } from 'path'

// Load .env.local
config({ path: join(__dirname, '..', '.env.local') })

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ Missing Supabase credentials in environment')
  process.exit(1)
}

if (!process.env.COINMARKETCAP_API_KEY) {
  console.error('❌ Missing COINMARKETCAP_API_KEY in environment')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

/**
 * Manual mapping of unlisted tokens to their likely CMC slugs
 * These mappings should be verified by checking CMC API responses
 */
const UNLISTED_TOKENS = [
  { symbol: '2Z', name: 'DoubleZero', cmcSlug: null }, // Search needed
  { symbol: 'EDGE', name: 'edgeX', cmcSlug: null }, // Search needed
  { symbol: 'FORM', name: 'Four', cmcSlug: null }, // Search needed
  { symbol: 'H', name: 'Humanity Protocol', cmcSlug: null }, // Search needed
  { symbol: 'NIGHT', name: 'Midnight', cmcSlug: null }, // Search needed
  { symbol: 'MYX', name: 'MYX Finance', cmcSlug: null }, // Search needed
  { symbol: 'PI', name: 'Pi Network', cmcSlug: null }, // Not traded - skip
  { symbol: 'XPL', name: 'Plasma', cmcSlug: null }, // Search needed
  { symbol: 'RAVE', name: 'RaveDAO', cmcSlug: null }, // Search needed
  { symbol: 'RIVER', name: 'River', cmcSlug: null }, // Search needed
  { symbol: 'SIREN', name: 'siren', cmcSlug: null }, // Search needed
  { symbol: 'SKYAI', name: 'SKYAI', cmcSlug: null }, // Search needed
  { symbol: 'STABLE', name: 'Stable', cmcSlug: null }, // Search needed
  { symbol: 'UP', name: 'Unitas Protocol', cmcSlug: null }, // Search needed
  { symbol: 'USDG', name: 'USDG', cmcSlug: null }, // Search needed
  { symbol: 'WAL', name: 'Walrus', cmcSlug: 'walrus-xyz' }, // Corrected mapping
  { symbol: 'WLFI', name: 'World Liberty Financial', cmcSlug: null }, // Search needed
  { symbol: '币安人生', name: '币安人生', cmcSlug: 'bianrensheng' }, // Verified mapping
]

interface SearchResult {
  symbol: string
  name: string
  foundSlug: string | null
  verified: boolean
  error?: string
}

async function main() {
  console.log('🔍 Searching CoinMarketCap for unlisted tokens...\n')

  const results: SearchResult[] = []

  for (const token of UNLISTED_TOKENS) {
    console.log(`Searching: ${token.name} (${token.symbol})`)

    try {
      // If we have a pre-mapped slug, verify it
      if (token.cmcSlug) {
        const priceData = await fetchCMCPrices([token.cmcSlug])
        if (priceData[token.cmcSlug]) {
          console.log(`  ✅ Verified pre-mapped slug: ${token.cmcSlug}`)
          results.push({
            symbol: token.symbol,
            name: token.name,
            foundSlug: token.cmcSlug,
            verified: true,
          })
        } else {
          console.log(`  ⚠️  Pre-mapped slug not found: ${token.cmcSlug}`)
          results.push({
            symbol: token.symbol,
            name: token.name,
            foundSlug: null,
            verified: false,
            error: 'Pre-mapped slug failed verification',
          })
        }
        continue
      }

      // Search by symbol
      const searchResults = await searchCMC(token.symbol)

      if (searchResults.length === 0) {
        console.log(`  ❌ No results found for ${token.symbol}`)
        results.push({
          symbol: token.symbol,
          name: token.name,
          foundSlug: null,
          verified: false,
          error: 'No CMC results',
        })
        continue
      }

      // Try to find exact match by name
      const exactMatch = searchResults.find(
        (r) => r.name.toLowerCase() === token.name.toLowerCase() || r.symbol === token.symbol
      )

      if (exactMatch) {
        console.log(`  ✅ Found: ${exactMatch.name} (${exactMatch.symbol}) -> ${exactMatch.slug}`)
        results.push({
          symbol: token.symbol,
          name: token.name,
          foundSlug: exactMatch.slug,
          verified: true,
        })
      } else {
        console.log(`  ⚠️  Multiple results, manual verification needed:`)
        searchResults.slice(0, 3).forEach((r) => {
          console.log(`     - ${r.name} (${r.symbol}) -> ${r.slug} [rank: ${r.rank}]`)
        })
        results.push({
          symbol: token.symbol,
          name: token.name,
          foundSlug: searchResults[0].slug, // Take first result
          verified: false,
          error: 'Multiple matches - needs manual verification',
        })
      }
    } catch (error) {
      console.error(`  ❌ Error searching ${token.name}:`, error)
      results.push({
        symbol: token.symbol,
        name: token.name,
        foundSlug: null,
        verified: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      })
    }

    // Rate limiting: wait 1 second between requests
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }

  console.log('\n📊 Search Results Summary:\n')
  console.log(`Total tokens: ${results.length}`)
  console.log(`Verified: ${results.filter((r) => r.verified).length}`)
  console.log(`Needs verification: ${results.filter((r) => !r.verified && r.foundSlug).length}`)
  console.log(`Not found: ${results.filter((r) => !r.foundSlug).length}`)

  console.log('\n📝 Detailed Results:\n')
  results.forEach((r) => {
    if (r.verified && r.foundSlug) {
      console.log(`✅ ${r.name} (${r.symbol}) -> ${r.foundSlug}`)
    } else if (r.foundSlug) {
      console.log(`⚠️  ${r.name} (${r.symbol}) -> ${r.foundSlug} (${r.error})`)
    } else {
      console.log(`❌ ${r.name} (${r.symbol}) - ${r.error}`)
    }
  })

  // Update database with verified results
  const verifiedResults = results.filter((r) => r.verified && r.foundSlug)

  if (verifiedResults.length > 0) {
    console.log(`\n💾 Updating database with ${verifiedResults.length} verified CMC IDs...`)

    for (const result of verifiedResults) {
      const { error } = await supabase
        .from('tracked_projects')
        .update({ cmc_id: result.foundSlug })
        .eq('symbol', result.symbol)

      if (error) {
        console.error(`  ❌ Failed to update ${result.symbol}:`, error.message)
      } else {
        console.log(`  ✅ Updated ${result.symbol} -> ${result.foundSlug}`)
      }
    }

    console.log('\n✅ Database update complete!')
  } else {
    console.log('\n⚠️  No verified results to update in database')
  }

  // Save results to file for manual review
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const fs = require('fs')
  const reportPath = 'cmc_mapping_report.json'
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2))
  console.log(`\n📄 Full report saved to: ${reportPath}`)
}

main().catch(console.error)
