#!/usr/bin/env node
/**
 * Fix WalletConnect CoinGecko ID
 * BCE-322: Immediate fix for incorrect WalletConnect ID
 *
 * Changes: walletconnect → connect-token-wct
 */

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!
const supabase = createClient(supabaseUrl, supabaseKey)

async function fixWalletConnect() {
  console.log('🔧 Fixing WalletConnect CoinGecko ID...\n')

  // Find WalletConnect project
  const { data: project, error: fetchError } = await supabase
    .from('tracked_projects')
    .select('id, name, symbol, coingecko_id')
    .eq('symbol', 'WCT')
    .single()

  if (fetchError || !project) {
    console.error('❌ Could not find WalletConnect project (WCT)')
    process.exit(1)
  }

  console.log(`Found: ${project.name} (${project.symbol})`)
  console.log(`Current ID: ${project.coingecko_id}`)

  // Verify the new ID works
  console.log('\n✓ Verifying new ID: connect-token-wct...')
  const testUrl = 'https://api.coingecko.com/api/v3/simple/price?ids=connect-token-wct&vs_currencies=usd'
  const res = await fetch(testUrl)

  if (!res.ok) {
    console.error('❌ API call failed:', res.status)
    process.exit(1)
  }

  const data = await res.json()

  if (!data['connect-token-wct'] || !data['connect-token-wct'].usd) {
    console.error('❌ New ID does not work!')
    console.error('Response:', data)
    process.exit(1)
  }

  console.log(`✅ Verified! Price: $${data['connect-token-wct'].usd}`)

  // Update database
  console.log('\n💾 Updating database...')
  const { error: updateError } = await supabase
    .from('tracked_projects')
    .update({ coingecko_id: 'connect-token-wct' })
    .eq('id', project.id)

  if (updateError) {
    console.error('❌ Update failed:', updateError)
    process.exit(1)
  }

  console.log('✅ WalletConnect ID updated successfully!')
  console.log('   walletconnect → connect-token-wct')
}

fixWalletConnect().catch(console.error)
