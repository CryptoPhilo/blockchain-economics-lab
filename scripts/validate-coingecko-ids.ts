#!/usr/bin/env node
/**
 * CoinGecko ID Validator and Populator
 *
 * Systematically validates and populates CoinGecko IDs for tracked projects.
 *
 * Process:
 * 1. Fetch projects with NULL or suspect coingecko_id
 * 2. Search CoinGecko /search endpoint by name + symbol
 * 3. Test candidate ID via /simple/price endpoint
 * 4. Update database with validated IDs only
 * 5. Log unlisted tokens to file
 * 6. Generate summary report
 *
 * Usage:
 *   npx tsx scripts/validate-coingecko-ids.ts
 *   npx tsx scripts/validate-coingecko-ids.ts --dry-run  # preview only
 *   npx tsx scripts/validate-coingecko-ids.ts --revalidate  # also check existing IDs
 */

import { createClient } from '@supabase/supabase-js'
import { writeFileSync } from 'fs'

const COINGECKO_API_BASE = 'https://api.coingecko.com/api/v3'
const RATE_LIMIT_DELAY = 1200 // ms between API calls (free tier: ~50 calls/minute)

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ Missing required environment variables:')
  console.error('  - NEXT_PUBLIC_SUPABASE_URL')
  console.error('  - SUPABASE_SERVICE_KEY')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

interface Project {
  id: string
  name: string
  symbol: string
  coingecko_id: string | null
}

interface ValidationResult {
  project: Project
  status: 'found' | 'not_found' | 'invalid' | 'already_valid' | 'error'
  candidateId?: string
  validatedId?: string
  priceData?: any
  error?: string
}

// Sleep utility for rate limiting
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Search CoinGecko for a token by name and symbol
 */
async function searchCoinGecko(name: string, symbol: string): Promise<string | null> {
  try {
    const query = encodeURIComponent(name)
    const url = `${COINGECKO_API_BASE}/search?query=${query}`

    const res = await fetch(url)
    if (!res.ok) {
      console.error(`  ⚠️  Search API error: ${res.status} ${res.statusText}`)
      return null
    }

    const data = await res.json()

    if (!data.coins || data.coins.length === 0) {
      return null
    }

    // Try exact symbol match first
    const exactMatch = data.coins.find((coin: any) =>
      coin.symbol.toLowerCase() === symbol.toLowerCase()
    )

    if (exactMatch) {
      return exactMatch.id
    }

    // Try exact name match
    const exactNameMatch = data.coins.find((coin: any) =>
      coin.name.toLowerCase() === name.toLowerCase()
    )

    if (exactNameMatch) {
      return exactNameMatch.id
    }

    // Return first result as best guess
    if (data.coins.length > 0) {
      console.log(`  ℹ️  Multiple results found, using best match: ${data.coins[0].id}`)
      return data.coins[0].id
    }

    return null
  } catch (error) {
    console.error(`  ❌ Search error:`, error)
    return null
  }
}

/**
 * Validate a CoinGecko ID by testing the /simple/price endpoint
 */
async function validateCoinGeckoId(id: string): Promise<boolean> {
  try {
    const url = `${COINGECKO_API_BASE}/simple/price?ids=${id}&vs_currencies=usd`
    const res = await fetch(url)

    if (!res.ok) {
      return false
    }

    const data = await res.json()

    // Check if the ID exists in response and has USD price
    return data[id] && typeof data[id].usd === 'number'
  } catch (error) {
    console.error(`  ❌ Validation error for ${id}:`, error)
    return false
  }
}

/**
 * Validate a single project
 */
async function validateProject(
  project: Project,
  options: { revalidate: boolean }
): Promise<ValidationResult> {
  console.log(`\n🔍 ${project.name} (${project.symbol})`)

  // If already has ID and not revalidating, check if it's valid
  if (project.coingecko_id && !options.revalidate) {
    const isValid = await validateCoinGeckoId(project.coingecko_id)
    await sleep(RATE_LIMIT_DELAY)

    if (isValid) {
      console.log(`  ✅ Already has valid ID: ${project.coingecko_id}`)
      return {
        project,
        status: 'already_valid',
        validatedId: project.coingecko_id
      }
    } else {
      console.log(`  ⚠️  Existing ID invalid: ${project.coingecko_id}`)
    }
  }

  // Search for the token
  console.log(`  🔎 Searching CoinGecko...`)
  const candidateId = await searchCoinGecko(project.name, project.symbol)
  await sleep(RATE_LIMIT_DELAY)

  if (!candidateId) {
    console.log(`  ❌ Not found on CoinGecko`)
    return {
      project,
      status: 'not_found'
    }
  }

  console.log(`  💡 Candidate ID: ${candidateId}`)

  // Validate the candidate ID
  console.log(`  ✓ Validating...`)
  const isValid = await validateCoinGeckoId(candidateId)
  await sleep(RATE_LIMIT_DELAY)

  if (!isValid) {
    console.log(`  ❌ Candidate ID does not work`)
    return {
      project,
      status: 'invalid',
      candidateId
    }
  }

  console.log(`  ✅ Validated: ${candidateId}`)
  return {
    project,
    status: 'found',
    candidateId,
    validatedId: candidateId
  }
}

/**
 * Update database with validated ID
 */
async function updateDatabase(projectId: string, coingeckoId: string): Promise<boolean> {
  const { error } = await supabase
    .from('tracked_projects')
    .update({ coingecko_id: coingeckoId })
    .eq('id', projectId)

  if (error) {
    console.error(`  ❌ Database update failed:`, error)
    return false
  }

  console.log(`  💾 Database updated`)
  return true
}

/**
 * Main validation flow
 */
async function main() {
  const args = process.argv.slice(2)
  const dryRun = args.includes('--dry-run')
  const revalidate = args.includes('--revalidate')

  console.log('🚀 CoinGecko ID Validator')
  console.log('========================\n')

  if (dryRun) {
    console.log('⚠️  DRY RUN MODE - No database changes will be made\n')
  }

  if (revalidate) {
    console.log('🔄 REVALIDATE MODE - Will check existing IDs too\n')
  }

  // Fetch projects to validate
  let query = supabase
    .from('tracked_projects')
    .select('id, name, symbol, coingecko_id')
    .in('status', ['active', 'monitoring_only'])
    .order('name')

  if (!revalidate) {
    // Only fetch NULL IDs by default
    query = query.is('coingecko_id', null)
  }

  const { data: projects, error } = await query

  if (error) {
    console.error('❌ Error fetching projects:', error)
    process.exit(1)
  }

  if (!projects || projects.length === 0) {
    console.log('✅ No projects need validation!')
    return
  }

  console.log(`📊 Found ${projects.length} project(s) to validate\n`)
  console.log('─'.repeat(60))

  // Validate each project
  const results: ValidationResult[] = []

  for (const project of projects) {
    const result = await validateProject(project, { revalidate })
    results.push(result)

    // Update database if valid ID found and not in dry-run mode
    if (!dryRun && result.validatedId && result.status === 'found') {
      await updateDatabase(project.id, result.validatedId)
    }
  }

  // Generate summary report
  console.log('\n' + '='.repeat(60))
  console.log('📋 SUMMARY REPORT')
  console.log('='.repeat(60) + '\n')

  const found = results.filter(r => r.status === 'found')
  const notFound = results.filter(r => r.status === 'not_found')
  const invalid = results.filter(r => r.status === 'invalid')
  const alreadyValid = results.filter(r => r.status === 'already_valid')
  const errors = results.filter(r => r.status === 'error')

  console.log(`Total processed: ${results.length}`)
  console.log(`✅ Found and validated: ${found.length}`)
  console.log(`✓  Already valid: ${alreadyValid.length}`)
  console.log(`❌ Not found: ${notFound.length}`)
  console.log(`⚠️  Invalid: ${invalid.length}`)
  console.log(`🔥 Errors: ${errors.length}`)

  // Write unlisted tokens to file
  if (notFound.length > 0) {
    const unlistedContent = [
      '# Tokens Not Found on CoinGecko',
      '',
      'The following tokens could not be found on CoinGecko:',
      '',
      ...notFound.map(r => `- ${r.project.name} (${r.project.symbol})`)
    ].join('\n')

    writeFileSync('unlisted_tokens.txt', unlistedContent)
    console.log(`\n📝 Unlisted tokens written to: unlisted_tokens.txt`)
  }

  // Write validation report
  const reportLines = [
    '# CoinGecko ID Validation Report',
    `Generated: ${new Date().toISOString()}`,
    '',
    '## Summary',
    `- Total processed: ${results.length}`,
    `- Found and validated: ${found.length}`,
    `- Already valid: ${alreadyValid.length}`,
    `- Not found on CoinGecko: ${notFound.length}`,
    `- Invalid candidates: ${invalid.length}`,
    `- Errors: ${errors.length}`,
    '',
  ]

  if (found.length > 0) {
    reportLines.push('## Newly Validated IDs', '')
    found.forEach(r => {
      reportLines.push(`- **${r.project.name}** (${r.project.symbol}) → \`${r.validatedId}\``)
    })
    reportLines.push('')
  }

  if (notFound.length > 0) {
    reportLines.push('## Not Found on CoinGecko', '')
    reportLines.push('These tokens may need manual research or alternative data sources:', '')
    notFound.forEach(r => {
      reportLines.push(`- ${r.project.name} (${r.project.symbol})`)
    })
    reportLines.push('')
  }

  if (invalid.length > 0) {
    reportLines.push('## Invalid Candidates', '')
    invalid.forEach(r => {
      reportLines.push(`- ${r.project.name} (${r.project.symbol}) - tried: ${r.candidateId}`)
    })
    reportLines.push('')
  }

  const reportContent = reportLines.join('\n')
  writeFileSync('validation_report.md', reportContent)
  console.log(`📝 Full report written to: validation_report.md`)

  if (dryRun) {
    console.log('\n⚠️  DRY RUN - No database changes were made')
    console.log('Run without --dry-run to apply changes')
  }

  console.log('\n✨ Validation complete!')
}

main().catch(error => {
  console.error('\n💥 Fatal error:', error)
  process.exit(1)
})
