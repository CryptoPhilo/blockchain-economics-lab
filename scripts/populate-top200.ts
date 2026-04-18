#!/usr/bin/env node
/**
 * Populate tracked_projects with top 200 cryptocurrencies by market cap
 * from CoinGecko's /coins/markets endpoint.
 *
 * Upserts by coingecko_id — existing projects are updated with fresh
 * market cap data; new projects are inserted as 'active'.
 *
 * Usage: npx tsx scripts/populate-top200.ts
 */

import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!
const supabase = createClient(supabaseUrl, supabaseKey)

interface CoinGeckoMarket {
  id: string
  symbol: string
  name: string
  current_price: number
  market_cap: number
  market_cap_rank: number
  price_change_percentage_24h: number
  total_volume: number
}

async function fetchTopCoins(page: number): Promise<CoinGeckoMarket[]> {
  const url = `https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=${page}&sparkline=false`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`CoinGecko API error: ${res.status} ${res.statusText}`)
  return res.json()
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

async function main() {
  console.log('Fetching top 200 coins from CoinGecko...')

  // Fetch page 1 and page 2 (100 each) with a delay to avoid rate limiting
  const page1 = await fetchTopCoins(1)
  console.log(`  Page 1: ${page1.length} coins`)
  await new Promise((r) => setTimeout(r, 1500))
  const page2 = await fetchTopCoins(2)
  console.log(`  Page 2: ${page2.length} coins`)

  const allCoins = [...page1, ...page2]

  // Load existing projects keyed by coingecko_id and slug
  const { data: existing } = await supabase
    .from('tracked_projects')
    .select('id, slug, coingecko_id, status')

  const byCoingeckoId = new Map<string, (typeof existing)[0]>()
  const bySlug = new Map<string, (typeof existing)[0]>()
  for (const p of existing || []) {
    if (p.coingecko_id) byCoingeckoId.set(p.coingecko_id, p)
    bySlug.set(p.slug, p)
  }

  let inserted = 0
  let updated = 0
  let skipped = 0

  for (const coin of allCoins) {
    const slug = slugify(coin.name)
    const existingByCg = byCoingeckoId.get(coin.id)
    const existingBySlug = bySlug.get(slug)
    const match = existingByCg || existingBySlug

    if (match) {
      // Update market cap + coingecko_id if missing
      const updates: Record<string, unknown> = {
        market_cap_usd: coin.market_cap ? Math.round(coin.market_cap) : null,
      }
      if (!match.coingecko_id) {
        updates.coingecko_id = coin.id
      }

      const { error } = await supabase
        .from('tracked_projects')
        .update(updates)
        .eq('id', match.id)

      if (error) {
        console.error(`  Error updating ${coin.name}: ${error.message}`)
      } else {
        updated++
      }
    } else {
      // Insert new project
      const { error } = await supabase.from('tracked_projects').insert({
        name: coin.name,
        slug,
        symbol: coin.symbol.toUpperCase(),
        coingecko_id: coin.id,
        market_cap_usd: coin.market_cap ? Math.round(coin.market_cap) : null,
        status: 'active',
      })

      if (error) {
        if (error.code === '23505') {
          // Unique constraint on slug — try with coingecko_id suffix
          const altSlug = `${slug}-${coin.id}`
          const { error: err2 } = await supabase.from('tracked_projects').insert({
            name: coin.name,
            slug: altSlug,
            symbol: coin.symbol.toUpperCase(),
            coingecko_id: coin.id,
            market_cap_usd: coin.market_cap ? Math.round(coin.market_cap) : null,
            status: 'active',
          })
          if (err2) {
            console.error(`  Error inserting ${coin.name} (alt slug): ${err2.message}`)
            skipped++
          } else {
            inserted++
          }
        } else {
          console.error(`  Error inserting ${coin.name}: ${error.message}`)
          skipped++
        }
      } else {
        inserted++
      }
    }
  }

  console.log(`\nDone! Inserted: ${inserted}, Updated: ${updated}, Skipped: ${skipped}`)

  // Verify final count
  const { count } = await supabase
    .from('tracked_projects')
    .select('*', { count: 'exact', head: true })
    .in('status', ['active', 'monitoring_only'])

  console.log(`Total active/monitoring projects: ${count}`)
}

main().catch(console.error)
