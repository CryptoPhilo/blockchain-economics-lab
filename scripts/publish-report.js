#!/usr/bin/env node
/**
 * Report Publishing Script
 * ========================
 * Publishes research reports: uploads to Supabase Storage,
 * creates/updates product record, and triggers marketing pipeline.
 *
 * Usage:
 *   node scripts/publish-report.js --slug=ethereum-gas-q2-2026
 *   node scripts/publish-report.js --file=content/reports/eth-gas-q2.pdf --slug=ethereum-gas-q2-2026
 */

const fs = require('fs')
const path = require('path')
const { createClient } = require('@supabase/supabase-js')

const SUPABASE_URL = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

// Parse CLI args
function parseArgs() {
  const args = {}
  process.argv.slice(2).forEach((arg) => {
    const [key, val] = arg.replace(/^--/, '').split('=')
    args[key] = val
  })
  return args
}

async function uploadReport(filePath, slug) {
  const fileBuffer = fs.readFileSync(filePath)
  const ext = path.extname(filePath)
  const storagePath = `reports/${slug}${ext}`

  console.log(`📤 Uploading ${filePath} → ${storagePath}`)

  const { data, error } = await supabase.storage
    .from('reports')
    .upload(storagePath, fileBuffer, {
      contentType: ext === '.pdf' ? 'application/pdf' : 'application/octet-stream',
      upsert: true,
    })

  if (error) throw new Error(`Upload failed: ${error.message}`)

  const { data: publicUrl } = supabase.storage
    .from('reports')
    .getPublicUrl(storagePath)

  console.log(`✅ Uploaded: ${publicUrl.publicUrl}`)
  return publicUrl.publicUrl
}

async function updateProduct(slug, fileUrl) {
  console.log(`🔄 Updating product record: ${slug}`)

  const { data: existing } = await supabase
    .from('products')
    .select('id, status')
    .eq('slug', slug)
    .single()

  if (existing) {
    const { error } = await supabase
      .from('products')
      .update({
        file_url: fileUrl,
        status: 'published',
        published_at: new Date().toISOString(),
      })
      .eq('id', existing.id)

    if (error) throw new Error(`Update failed: ${error.message}`)
    console.log(`✅ Product updated: ${slug} → published`)
  } else {
    console.log(`⚠️  No product found with slug: ${slug}`)
    console.log('   Create the product in the database first, then re-run.')
  }
}

async function triggerMarketingPipeline(slug) {
  console.log('\n── 📢 Marketing Pipeline ──')
  console.log(`  → agent-content-marketer: Create summary content for ${slug}`)
  console.log(`  → agent-community-manager: Announce in community channels`)
  console.log(`  → agent-cmo: Review marketing metrics after 24h`)

  // In production, this would create GitHub issues or send webhooks
  // to trigger actual agent tasks
  console.log('  ℹ️  Pipeline notifications queued (implement webhook in production)')
}

async function main() {
  const args = parseArgs()

  if (!args.slug) {
    console.error('Usage: node scripts/publish-report.js --slug=<report-slug> [--file=<path>]')
    process.exit(1)
  }

  console.log('═══════════════════════════════════════════════')
  console.log('  📝 Blockchain Economics Lab — Report Publisher')
  console.log(`  📅 ${new Date().toISOString()}`)
  console.log('═══════════════════════════════════════════════\n')

  let fileUrl = null

  if (args.file) {
    const filePath = path.resolve(args.file)
    if (!fs.existsSync(filePath)) {
      console.error(`❌ File not found: ${filePath}`)
      process.exit(1)
    }
    fileUrl = await uploadReport(filePath, args.slug)
  }

  await updateProduct(args.slug, fileUrl)
  await triggerMarketingPipeline(args.slug)

  console.log('\n═══════════════════════════════════════════════')
  console.log('  ✅ Publishing complete')
  console.log('═══════════════════════════════════════════════')
}

main().catch((err) => {
  console.error('❌ Publishing failed:', err)
  process.exit(1)
})
