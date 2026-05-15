import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const failures = []

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8')
}

function exists(file) {
  return fs.existsSync(path.join(root, file))
}

function fail(message) {
  failures.push(message)
}

function pass(message) {
  console.log(`PASS ${message}`)
}

function requireText(file, needle, label) {
  if (!exists(file)) {
    fail(`${label}: missing ${file}`)
    return
  }
  if (read(file).includes(needle)) pass(label)
  else fail(`${label}: ${file} does not contain ${needle}`)
}

function rejectText(file, needle, label) {
  if (!exists(file)) {
    fail(`${label}: missing ${file}`)
    return
  }
  if (read(file).includes(needle)) fail(`${label}: ${file} must not contain ${needle}`)
  else pass(label)
}

function extractFunction(source, name) {
  const start = source.indexOf(`def ${name}(`)
  if (start < 0) return ''
  const next = source.indexOf('\ndef ', start + 1)
  return source.slice(start, next < 0 ? source.length : next)
}

const watcherPath = 'scripts/pipeline/watch_slides.py'
const watcher = read(watcherPath)
const targetPublicationStatus = extractFunction(watcher, '_target_publication_status')

requireText(
  watcherPath,
  'status: str = PUBLICATION_PUBLISHED_STATUS',
  'Slide-created report rows default to published',
)
requireText(
  watcherPath,
  'if status in {REVIEW_READY_STATUS, PUBLICATION_APPROVED_STATUS}:',
  'Legacy review/approved inputs are normalized before DB writes',
)
requireText(
  watcherPath,
  'return PUBLICATION_PUBLISHED_STATUS',
  'Target publication status is published',
)

if (targetPublicationStatus.includes('REVIEW_READY_STATUS')) {
  fail('_target_publication_status must not return or reference REVIEW_READY_STATUS')
} else {
  pass('_target_publication_status does not reference REVIEW_READY_STATUS')
}

rejectText(watcherPath, 'review_ready_created', 'Slide watcher must not create review-ready rows')
rejectText(watcherPath, 'DB prepared for editorial review', 'Slide watcher must not prepare editorial-review DB rows')
rejectText(watcherPath, 'DB created for editorial review', 'Slide watcher must not create editorial-review DB rows')
rejectText(watcherPath, 'review_ready=', 'Slide watcher summary must not report review-ready publication output')

requireText(
  'supabase/migrations/20260515_normalize_slide_report_publication_status.sql',
  'normalize_slide_report_publication_status',
  'Database has final slide-report status normalization trigger',
)
requireText(
  '.github/workflows/ci.yml',
  'npm run verify:report-publication-policy',
  'CI verifies report publication policy',
)
requireText(
  '.github/workflows/slide-pipeline-cron.yml',
  'npm run verify:report-publication-policy',
  'Slide workflow verifies report publication policy before execution',
)
requireText(
  '.github/workflows/production-deploy.yml',
  'npm run verify:report-publication-policy',
  'Production readiness verifies report publication policy',
)
requireText(
  'package.json',
  '"verify:report-publication-policy"',
  'Package script verify:report-publication-policy is registered',
)

if (failures.length > 0) {
  console.error('\nReport publication policy verification failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('\nReport publication policy verified.')
