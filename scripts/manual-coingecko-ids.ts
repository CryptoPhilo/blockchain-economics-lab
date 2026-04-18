#!/usr/bin/env node
/**
 * Manual CoinGecko ID population for well-known tokens
 * These are tokens where the CoinGecko ID is known and can be directly applied
 */

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!
const supabase = createClient(supabaseUrl, supabaseKey)

// Well-known CoinGecko IDs based on token symbol/name
const KNOWN_IDS: Record<string, string> = {
  'TIA': 'celestia',           // Celestia
  'CHZ': 'chiliz',             // Chiliz
  'CFX': 'conflux-token',      // Conflux
  'DEEP': 'deepbook-protocol', // DeepBook Protocol
  'DEXE': 'dexe',              // DeXe
  'DYDX': 'dydx-chain',        // dYdX (v4 chain)
  'EIGEN': 'eigenlayer',       // EigenLayer
  'ENJ': 'enjincoin',          // Enjin Coin
  'JST': 'just',               // JUST
  'KSM': 'kusama',             // Kusama
  'MNT': 'mantle',             // Mantle Network
  'MEME': 'memecoin-2',        // MemeCore
  'EGLD': 'elrond-erd-2',      // MultiversX (formerly Elrond)
  'OKB': 'okb',                // OKX Token
  'ORDI': 'ordinals',          // ORDI
  'PENDLE': 'pendle',          // Pendle
  'LUNC': 'terra-luna',        // Terra Classic
  'XAUT': 'tether-gold',       // Tether Gold
  'SAFE': 'safe',              // Safe
  'CFG': 'centrifuge',         // Centrifuge
  'WLFI': 'world-liberty-financial-wlfi', // World Liberty Financial
}

async function validateAndUpdate(symbol: string, coingeckoId: string): Promise<boolean> {
  // Validate the ID works
  const url = `https://api.coingecko.com/api/v3/simple/price?ids=${coingeckoId}&vs_currencies=usd`
  const res = await fetch(url)

  if (!res.ok) {
    return false
  }

  const data = await res.json()
  if (!data[coingeckoId] || typeof data[coingeckoId].usd !== 'number') {
    return false
  }

  // Update database
  const { error } = await supabase
    .from('tracked_projects')
    .update({ coingecko_id: coingeckoId })
    .eq('symbol', symbol)
    .is('coingecko_id', null)

  return !error
}

async function main() {
  console.log('🔧 Manually populating known CoinGecko IDs...\n')

  let successful = 0
  let failed = 0

  for (const [symbol, coingeckoId] of Object.entries(KNOWN_IDS)) {
    process.stdout.write(`${symbol} → ${coingeckoId} ... `)

    const success = await validateAndUpdate(symbol, coingeckoId)

    if (success) {
      console.log('✅')
      successful++
    } else {
      console.log('❌')
      failed++
    }

    // Rate limiting: 2 seconds between calls
    await new Promise(resolve => setTimeout(resolve, 2000))
  }

  console.log(`\n✨ Complete!`)
  console.log(`✅ Successful: ${successful}`)
  console.log(`❌ Failed: ${failed}`)
}

main().catch(console.error)
