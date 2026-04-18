#!/usr/bin/env node
/**
 * Batch update CoinGecko IDs with proper rate limiting
 * Manually verified IDs for remaining tokens
 */

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!
const supabase = createClient(supabaseUrl, supabaseKey)

// Manually verified CoinGecko IDs
// Format: [symbol, coingecko_id, confidence]
// confidence: 'high' = verified working, 'medium' = likely correct, 'low' = best guess
const MANUAL_IDS: Array<[string, string, string]> = [
  // High confidence - major well-known tokens
  ['DYDX', 'dydx-chain', 'high'],
  ['ENJ', 'enjincoin', 'high'],
  ['KSM', 'kusama', 'high'],
  ['MNT', 'mantle', 'high'],
  ['EGLD', 'elrond-erd-2', 'high'],
  ['OKB', 'okb', 'high'],
  ['ORDI', 'ordinals', 'high'],
  ['PENDLE', 'pendle', 'high'],
  ['LUNC', 'terra-luna', 'high'],
  ['XAUT', 'tether-gold', 'high'],
  ['CFG', 'centrifuge', 'high'],
  ['DEXE', 'dexe', 'high'],
  ['JST', 'just', 'high'],
  ['MEME', 'memecoin-2', 'high'],

  // Medium confidence
  ['DEEP', 'deepbook-protocol', 'medium'],
  ['EIGEN', 'eigenlayer', 'medium'],
  ['SAFE', 'safe', 'medium'],

  // Note: Some tokens may not be on CoinGecko or have different symbols
  // These will be marked as "not listed" if validation fails
]

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function validateCoinGeckoId(id: string): Promise<{ valid: boolean; price?: number }> {
  try {
    const url = `https://api.coingecko.com/api/v3/simple/price?ids=${id}&vs_currencies=usd`
    const res = await fetch(url)

    if (!res.ok) {
      if (res.status === 429) {
        console.log('    ⏸️  Rate limited, waiting 10s...')
        await sleep(10000)
        return validateCoinGeckoId(id) // Retry
      }
      return { valid: false }
    }

    const data = await res.json()

    if (data[id] && typeof data[id].usd === 'number') {
      return { valid: true, price: data[id].usd }
    }

    return { valid: false }
  } catch (error) {
    console.error('    ❌ Error:', error)
    return { valid: false }
  }
}

async function updateProject(symbol: string, coingeckoId: string): Promise<boolean> {
  const { error, data } = await supabase
    .from('tracked_projects')
    .update({ coingecko_id: coingeckoId })
    .eq('symbol', symbol)
    .is('coingecko_id', null)
    .select()

  if (error) {
    console.error('    ❌ DB error:', error.message)
    return false
  }

  if (!data || data.length === 0) {
    console.log('    ⚠️  No rows updated (already has ID or not found)')
    return false
  }

  return true
}

async function main() {
  const dryRun = process.argv.includes('--dry-run')

  console.log('🔧 Batch CoinGecko ID Updater')
  console.log('============================\n')

  if (dryRun) {
    console.log('⚠️  DRY RUN MODE - No database changes\n')
  }

  console.log(`Processing ${MANUAL_IDS.length} tokens with 5s delay between validations...\n`)

  let successful = 0
  let failed = 0
  const failures: Array<{ symbol: string; id: string; reason: string }> = []

  for (const [symbol, coingeckoId, confidence] of MANUAL_IDS) {
    console.log(`\n${symbol} → ${coingeckoId} (${confidence})`)

    // Validate the ID
    console.log('  🔍 Validating...')
    const { valid, price } = await validateCoinGeckoId(coingeckoId)

    await sleep(5000) // 5 second delay between API calls

    if (!valid) {
      console.log('  ❌ Invalid ID')
      failed++
      failures.push({ symbol, id: coingeckoId, reason: 'Invalid CoinGecko ID' })
      continue
    }

    console.log(`  ✅ Validated! Price: $${price}`)

    // Update database
    if (!dryRun) {
      console.log('  💾 Updating database...')
      const updated = await updateProject(symbol, coingeckoId)

      if (updated) {
        console.log('  ✅ Database updated')
        successful++
      } else {
        console.log('  ❌ Database update failed')
        failed++
        failures.push({ symbol, id: coingeckoId, reason: 'Database update failed' })
      }
    } else {
      console.log('  ✓ Would update database')
      successful++
    }
  }

  console.log('\n' + '='.repeat(60))
  console.log('📊 Summary')
  console.log('='.repeat(60))
  console.log(`✅ Successful: ${successful}`)
  console.log(`❌ Failed: ${failed}`)

  if (failures.length > 0) {
    console.log('\n❌ Failures:')
    failures.forEach(f => {
      console.log(`  - ${f.symbol} (${f.id}): ${f.reason}`)
    })
  }

  if (dryRun) {
    console.log('\n⚠️  DRY RUN - Run without --dry-run to apply changes')
  }

  console.log('\n✨ Complete!')
}

main().catch(console.error)
