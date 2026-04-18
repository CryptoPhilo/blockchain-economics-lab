/**
 * Fix cmc_id column type in tracked_projects table
 * Changes column from integer to text if needed
 */

import { createClient } from '@supabase/supabase-js'
import { config } from 'dotenv'
import { join } from 'path'

config({ path: join(__dirname, '..', '.env.local') })

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseKey = process.env.SUPABASE_SERVICE_KEY!

const supabase = createClient(supabaseUrl, supabaseKey)

async function main() {
  console.log('🔧 Checking cmc_id column type...\n')

  // Try to insert a test text value
  const testSymbol = 'TEST_CMC_' + Date.now()

  const { error: insertError } = await supabase
    .from('tracked_projects')
    .insert({
      name: 'Test CMC Column',
      symbol: testSymbol,
      slug: 'test-cmc-' + Date.now(),
      cmc_id: 'test-slug',
    })

  if (insertError) {
    if (insertError.message.includes('invalid input syntax for type integer')) {
      console.log('❌ Column cmc_id is integer type, needs to be text')
      console.log('\n📝 Please run this SQL in Supabase dashboard:')
      console.log('   https://supabase.com/dashboard/project/wbqponoiyoeqlepxogcb/sql\n')
      console.log('ALTER TABLE tracked_projects ALTER COLUMN cmc_id TYPE TEXT USING cmc_id::TEXT;')
      console.log(
        'CREATE INDEX IF NOT EXISTS idx_tracked_projects_cmc_id ON tracked_projects(cmc_id) WHERE cmc_id IS NOT NULL;'
      )
      console.log('\nOr if cmc_id column does not exist yet:')
      console.log('ALTER TABLE tracked_projects ADD COLUMN IF NOT EXISTS cmc_id TEXT;')
      console.log(
        'CREATE INDEX IF NOT EXISTS idx_tracked_projects_cmc_id ON tracked_projects(cmc_id) WHERE cmc_id IS NOT NULL;'
      )
    } else if (insertError.message.includes('column "cmc_id" does not exist')) {
      console.log('❌ Column cmc_id does not exist')
      console.log('\n📝 Please run this SQL in Supabase dashboard:')
      console.log('   https://supabase.com/dashboard/project/wbqponoiyoeqlepxogcb/sql\n')
      console.log('ALTER TABLE tracked_projects ADD COLUMN cmc_id TEXT;')
      console.log(
        'CREATE INDEX idx_tracked_projects_cmc_id ON tracked_projects(cmc_id) WHERE cmc_id IS NOT NULL;'
      )
    } else {
      console.log('❌ Unexpected error:', insertError.message)
    }
    process.exit(1)
  }

  // Clean up test record
  await supabase.from('tracked_projects').delete().eq('symbol', testSymbol)

  console.log('✅ Column cmc_id exists and accepts text values')
  console.log('Migration is ready!')
}

main().catch(console.error)
