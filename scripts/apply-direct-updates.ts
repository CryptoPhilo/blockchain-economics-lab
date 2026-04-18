#!/usr/bin/env node
/**
 * Apply pre-verified CoinGecko IDs directly to database
 * Bypasses API rate limits by using known good IDs
 */

import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!
const supabase = createClient(supabaseUrl, supabaseKey)

interface Update {
  symbol: string
  coingeckoId: string
  condition: 'null' | string
}

const UPDATES: Update[] = [
  // Well-known major tokens
  { symbol: 'DYDX', coingeckoId: 'dydx-chain', condition: 'null' },
  { symbol: 'ENJ', coingeckoId: 'enjincoin', condition: 'null' },
  { symbol: 'KSM', coingeckoId: 'kusama', condition: 'null' },
  { symbol: 'MNT', coingeckoId: 'mantle', condition: 'null' },
  { symbol: 'EGLD', coingeckoId: 'elrond-erd-2', condition: 'null' },
  { symbol: 'OKB', coingeckoId: 'okb', condition: 'null' },
  { symbol: 'ORDI', coingeckoId: 'ordinals', condition: 'null' },
  { symbol: 'PENDLE', coingeckoId: 'pendle', condition: 'null' },
  { symbol: 'LUNC', coingeckoId: 'terra-luna', condition: 'null' },
  { symbol: 'XAUT', coingeckoId: 'tether-gold', condition: 'null' },
  { symbol: 'CFG', coingeckoId: 'centrifuge', condition: 'null' },
  { symbol: 'DEXE', coingeckoId: 'dexe', condition: 'null' },
  { symbol: 'JST', coingeckoId: 'just', condition: 'null' },
  { symbol: 'MEME', coingeckoId: 'memecoin-2', condition: 'null' },

  // Fix Story Protocol
  { symbol: 'IP', coingeckoId: 'story-2', condition: 'story-protocol' },

  // Medium confidence
  { symbol: 'DEEP', coingeckoId: 'deepbook-protocol', condition: 'null' },
  { symbol: 'EIGEN', coingeckoId: 'eigenlayer', condition: 'null' },
  { symbol: 'SAFE', coingeckoId: 'safe', condition: 'null' },
]

async function applyUpdate(update: Update): Promise<{ success: boolean; rowsAffected: number }> {
  let query = supabase
    .from('tracked_projects')
    .update({ coingecko_id: update.coingeckoId })
    .eq('symbol', update.symbol)

  if (update.condition === 'null') {
    query = query.is('coingecko_id', null)
  } else {
    query = query.eq('coingecko_id', update.condition)
  }

  const { data, error } = await query.select()

  if (error) {
    console.error(`  ❌ Error:`, error.message)
    return { success: false, rowsAffected: 0 }
  }

  return { success: true, rowsAffected: data?.length || 0 }
}

async function main() {
  const dryRun = process.argv.includes('--dry-run')

  console.log('🗄️  Direct CoinGecko ID Updater')
  console.log('==============================\n')

  if (dryRun) {
    console.log('⚠️  DRY RUN MODE - No changes will be made\n')
  }

  console.log(`Applying ${UPDATES.length} updates...\n`)

  let successful = 0
  let skipped = 0
  let failed = 0

  for (const update of UPDATES) {
    const condition = update.condition === 'null' ? 'IS NULL' : `= '${update.condition}'`
    process.stdout.write(`${update.symbol} → ${update.coingeckoId} (where coingecko_id ${condition}) ... `)

    if (dryRun) {
      console.log('✓ (dry run)')
      successful++
      continue
    }

    const { success, rowsAffected } = await applyUpdate(update)

    if (success) {
      if (rowsAffected > 0) {
        console.log(`✅ (${rowsAffected} row${rowsAffected > 1 ? 's' : ''})`)
        successful++
      } else {
        console.log('⊘ (already updated or not found)')
        skipped++
      }
    } else {
      console.log('❌')
      failed++
    }
  }

  console.log('\n' + '='.repeat(60))
  console.log('📊 Summary')
  console.log('='.repeat(60))
  console.log(`✅ Successful: ${successful}`)
  console.log(`⊘  Skipped: ${skipped}`)
  console.log(`❌ Failed: ${failed}`)

  if (dryRun) {
    console.log('\n⚠️  DRY RUN - Run without --dry-run to apply changes')
  }

  console.log('\n✨ Complete!')
}

main().catch(console.error)
