#!/usr/bin/env node
/**
 * Quick diagnostic script to check current CoinGecko ID status
 */

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!

const supabase = createClient(supabaseUrl, supabaseKey)

async function checkStatus() {
  console.log('Checking CoinGecko ID status...\n')

  // Get all tracked projects
  const { data: projects, error } = await supabase
    .from('tracked_projects')
    .select('id, name, symbol, coingecko_id, status')
    .in('status', ['active', 'monitoring_only'])
    .order('name')

  if (error) {
    console.error('Error fetching projects:', error)
    return
  }

  if (!projects || projects.length === 0) {
    console.log('No tracked projects found.')
    return
  }

  const withId = projects.filter(p => p.coingecko_id)
  const withoutId = projects.filter(p => !p.coingecko_id)

  console.log(`Total active/monitoring projects: ${projects.length}`)
  console.log(`With CoinGecko ID: ${withId.length}`)
  console.log(`Without CoinGecko ID (NULL): ${withoutId.length}\n`)

  if (withoutId.length > 0) {
    console.log('Projects WITHOUT CoinGecko ID:')
    withoutId.forEach((p, i) => {
      console.log(`  ${i + 1}. ${p.name} (${p.symbol})`)
    })
    console.log()
  }

  if (withId.length > 0) {
    console.log('Projects WITH CoinGecko ID:')
    withId.forEach((p, i) => {
      console.log(`  ${i + 1}. ${p.name} (${p.symbol}) → ${p.coingecko_id}`)
    })
    console.log()
  }

  // Check for potentially problematic IDs mentioned in the issue
  const suspect = withId.filter(p =>
    p.coingecko_id === 'walletconnect' ||
    p.coingecko_id === 'story-protocol'
  )

  if (suspect.length > 0) {
    console.log('⚠️  Suspect IDs mentioned in BCE-319:')
    suspect.forEach(p => {
      console.log(`  - ${p.name}: "${p.coingecko_id}"`)
    })
  }
}

checkStatus().catch(console.error)
