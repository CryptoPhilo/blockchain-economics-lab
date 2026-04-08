#!/usr/bin/env node
/**
 * Product Seeder Script
 * =====================
 * Seeds the database with sample products for development/testing.
 *
 * Usage:
 *   node scripts/seed-products.js
 */

const { createClient } = require('@supabase/supabase-js')

const SUPABASE_URL = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

async function seed() {
  console.log('🌱 Seeding database...\n')

  // Check if data already exists
  const { count } = await supabase
    .from('categories')
    .select('id', { count: 'exact', head: true })

  if (count > 0) {
    console.log(`ℹ️  Database already has ${count} categories. Skipping seed.`)
    console.log('   To re-seed, clear the tables first.')
    return
  }

  // Categories
  const { error: catError } = await supabase.from('categories').insert([
    { slug: 'onchain-analytics', name_en: 'On-Chain Analytics', name_ko: '온체인 분석', icon: '📊', sort_order: 1 },
    { slug: 'tokenomics', name_en: 'Tokenomics', name_ko: '토큰이코노믹스', icon: '🪙', sort_order: 2 },
    { slug: 'defi', name_en: 'DeFi Research', name_ko: 'DeFi 리서치', icon: '🏦', sort_order: 3 },
    { slug: 'macro-crypto', name_en: 'Macro & Crypto', name_ko: '매크로 & 크립토', icon: '🌍', sort_order: 4 },
    { slug: 'special-reports', name_en: 'Special Reports', name_ko: '특별 보고서', icon: '⭐', sort_order: 5 },
  ])

  if (catError) {
    console.error('❌ Category seed failed:', catError.message)
    return
  }
  console.log('✅ Categories seeded (5)')

  // Get category IDs
  const { data: cats } = await supabase.from('categories').select('id, slug')
  const catMap = Object.fromEntries(cats.map((c) => [c.slug, c.id]))

  // Products
  const { error: prodError } = await supabase.from('products').insert([
    {
      type: 'single_report', status: 'published', slug: 'eth-gas-q1-2026',
      title_en: 'Ethereum Gas Fee Deep Dive Q1 2026', title_ko: '이더리움 가스비 심층 분석 2026 Q1',
      description_en: 'Comprehensive analysis of gas fee trends and L2 migration patterns.',
      price_usd_cents: 4900, category_id: catMap['onchain-analytics'], featured: true,
      published_at: new Date().toISOString(), tags: ['ethereum', 'gas', 'L2'],
    },
    {
      type: 'single_report', status: 'published', slug: 'defi-yield-spring-2026',
      title_en: 'DeFi Yield Landscape — Spring 2026', title_ko: 'DeFi 수익률 지형도 — 2026 봄',
      description_en: 'Risk-adjusted yield analysis across major DeFi protocols.',
      price_usd_cents: 3900, category_id: catMap['defi'], featured: true,
      published_at: new Date().toISOString(), tags: ['defi', 'yield'],
    },
    {
      type: 'subscription', status: 'published', slug: 'basic-monthly',
      title_en: 'Basic Monthly Plan', title_ko: '베이직 월간 플랜',
      description_en: 'All standard reports. 4-6 per month.',
      price_usd_cents: 2900, subscription_interval: 'monthly', featured: false,
      published_at: new Date().toISOString(), tags: ['subscription'],
    },
    {
      type: 'subscription', status: 'published', slug: 'premium-monthly',
      title_en: 'Premium Monthly Plan', title_ko: '프리미엄 월간 플랜',
      description_en: 'All reports + special reports + data dashboards.',
      price_usd_cents: 7900, subscription_interval: 'monthly', featured: true,
      published_at: new Date().toISOString(), tags: ['subscription', 'premium'],
    },
  ])

  if (prodError) {
    console.error('❌ Product seed failed:', prodError.message)
    return
  }
  console.log('✅ Products seeded (4)')
  console.log('\n🎉 Seeding complete!')
}

seed().catch((err) => {
  console.error('❌ Seed failed:', err)
  process.exit(1)
})
