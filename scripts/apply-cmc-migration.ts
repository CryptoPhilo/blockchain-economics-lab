/**
 * Apply CMC migration directly to Supabase database
 * This script runs the 20260418_add_cmc_id_to_tracked_projects migration
 *
 * Usage: npx tsx scripts/apply-cmc-migration.ts
 */

import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'
import { join } from 'path'
import { config } from 'dotenv'

// Load .env.local
config({ path: join(__dirname, '..', '.env.local') })

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!

if (!supabaseUrl || !supabaseKey) {
  console.error('❌ Missing Supabase credentials in environment')
  process.exit(1)
}

const supabase = createClient(supabaseUrl, supabaseKey)

async function main() {
  console.log('📦 Applying CMC migration...\n')

  const migrationPath = join(
    __dirname,
    '..',
    'supabase',
    'migrations',
    '20260418_add_cmc_id_to_tracked_projects.sql'
  )

  const sql = readFileSync(migrationPath, 'utf-8')

  // Split by semicolons and execute each statement
  const statements = sql
    .split(';')
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !s.startsWith('--'))

  for (let i = 0; i < statements.length; i++) {
    const statement = statements[i]
    console.log(`Executing statement ${i + 1}/${statements.length}...`)

    const { error } = await supabase.rpc('exec_sql', { sql: statement + ';' })

    if (error) {
      // Try direct query method if RPC fails
      const { error: directError } = await supabase.from('tracked_projects').select('cmc_id').limit(1)

      if (directError && directError.message.includes('column "cmc_id" does not exist')) {
        // Column doesn't exist, need to add it manually
        console.log('\n⚠️  Unable to apply migration automatically.')
        console.log('Please apply the migration manually in Supabase dashboard:')
        console.log('\n1. Go to: https://supabase.com/dashboard/project/wbqponoiyoeqlepxogcb/sql')
        console.log('2. Run the following SQL:\n')
        console.log(sql)
        console.log('\nOr run these commands:')
        console.log('ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS cmc_id TEXT;')
        console.log(
          'CREATE INDEX IF NOT EXISTS idx_tracked_projects_cmc_id ON tracked_projects(cmc_id) WHERE cmc_id IS NOT NULL;'
        )
        process.exit(1)
      } else if (!directError) {
        console.log('✅ Column cmc_id already exists, migration previously applied')
        return
      }
    }
  }

  console.log('\n✅ Migration applied successfully!')
}

main().catch(console.error)
