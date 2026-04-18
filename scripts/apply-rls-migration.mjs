#!/usr/bin/env node
import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const supabaseUrl = 'https://wbqponoiyoeqlepxogcb.supabase.co'
const supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndicXBvbm9peW9lcWxlcHhvZ2NiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTY1ODcwMCwiZXhwIjoyMDkxMjM0NzAwfQ.npUP3hnP7dvzd6nu4zl0rEzwg6ENR88bjsnOH-Ao1Xg'

const supabase = createClient(supabaseUrl, supabaseKey)

// Workaround: Since Supabase doesn't provide SQL execution via SDK,
// we'll verify the fix by checking if the policy allows coming_soon reports

console.log('Testing current RLS policy...')

// Test with anon key (public access)
const anonClient = createClient(
  supabaseUrl,
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndicXBvbm9peW9lcWxlcHhvZ2NiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU2NTg3MDAsImV4cCI6MjA5MTIzNDcwMH0.Fkf5XOg2pGkCwSELznG3binebAfxsTDEXF_KbRSvO2I'
)

const { data, error, count } = await anonClient
  .from('project_reports')
  .select('*', { count: 'exact', head: false })
  .eq('report_type', 'forensic')
  .in('status', ['published', 'coming_soon'])
  .gte('created_at', new Date(Date.now() - 72 * 60 * 60 * 1000).toISOString())
  .limit(100)

if (error) {
  console.error('Query error:', error)
  process.exit(1)
}

console.log(`\nCurrent state:`)
console.log(`Total FOR reports (anon access): ${count}`)
console.log(`Status breakdown:`)
const statusCounts = {}
data.forEach(r => {
  statusCounts[r.status] = (statusCounts[r.status] || 0) + 1
})
console.log(statusCounts)

if (count === 1 && statusCounts.published === 1) {
  console.log('\n❌ RLS policy is still restrictive - only showing published reports')
  console.log('\nTo fix, please execute this SQL in Supabase dashboard:')
  console.log('---')
  console.log(readFileSync(join(__dirname, '..', 'supabase', 'migrations', '20260418_fix_rls_for_coming_soon_reports.sql'), 'utf-8'))
  process.exit(1)
} else if (count > 1) {
  console.log('\n✅ RLS policy is working correctly - showing both published and coming_soon reports')
  process.exit(0)
}
