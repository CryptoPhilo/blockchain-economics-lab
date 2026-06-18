import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8')
}

function exists(file) {
  return fs.existsSync(path.join(root, file))
}

function pass(label) {
  console.log(`PASS ${label}`)
}

function fail(label, detail) {
  failures.push(`${label}${detail ? `: ${detail}` : ''}`)
}

function requireFile(file, label = file) {
  if (exists(file)) pass(label)
  else fail(label, `${file} is missing`)
}

function requireText(file, pattern, label) {
  if (!exists(file)) {
    fail(label, `${file} is missing`)
    return
  }
  const text = read(file)
  const matched = typeof pattern === 'string' ? text.includes(pattern) : pattern.test(text)
  if (matched) pass(label)
  else fail(label, `${file} does not match ${pattern}`)
}

const failures = []

const packageJson = JSON.parse(read('package.json'))
if (packageJson.scripts?.test && !packageJson.scripts.test.includes('No tests configured')) {
  pass('npm test runs a real test command')
} else {
  fail('npm test runs a real test command', 'package.json still uses a placeholder test script')
}

for (const [script, expected] of [
  ['dev', 'next dev'],
  ['build', 'next build'],
  ['lint', 'eslint'],
  ['verify:pipeline', 'node scripts/verify-website-pipeline.mjs'],
]) {
  if (packageJson.scripts?.[script] === expected) pass(`package script ${script}`)
  else fail(`package script ${script}`, `expected ${expected}`)
}

const vercel = JSON.parse(read('vercel.json'))
if (vercel.framework === 'nextjs' && vercel.buildCommand === 'npm run build') pass('Vercel Next.js build configuration')
else fail('Vercel Next.js build configuration')

for (const cron of vercel.crons ?? []) {
  const routePath = cron.path.replace(/^\/api\//, 'src/app/api/').replace(/$/, '/route.ts')
  requireFile(routePath, `Vercel cron route ${cron.path}`)
}

requireText('.github/workflows/ci.yml', 'npm run verify:pipeline', 'CI runs pipeline definition alignment check')
requireText('.github/workflows/ci.yml', 'npm test -- --passWithNoTests', 'CI runs Jest test command')
requireText('.github/workflows/ci.yml', 'npm run build', 'CI runs production build')
requireText('.github/workflows/deploy-preview.yml', 'Preview Deployment', 'PR preview deployment posts URL')
requireText('.github/workflows/production-deploy.yml', 'environment: production', 'Production deploy requires GitHub production environment')
requireText('.github/workflows/production-deploy.yml', '--prod', 'Production deploy uses Vercel production flag')
requireText('.github/PULL_REQUEST_TEMPLATE.md', 'Paperclip Pipeline Evidence', 'PR template captures Paperclip pipeline evidence')
requireText('.github/PULL_REQUEST_TEMPLATE.md', 'Board approval', 'PR template captures board approval evidence')

for (const file of [
  'public/images/score-header-bg.png',
  'public/images/exchanges-header-bg.png',
  'public/images/exchange-detail-header-base.png',
]) {
  requireFile(file, `Header background asset ${file}`)
}

for (const file of [
  'src/app/[locale]/page.tsx',
  'src/app/[locale]/score/page.tsx',
  'src/app/[locale]/projects/[slug]/page.tsx',
  'src/app/[locale]/reports/page.tsx',
  'src/app/[locale]/reports/forensic/[slug]/page.tsx',
  'src/lib/repositories/reports.ts',
]) {
  requireFile(file, `Report visibility surface ${file}`)
}

for (const file of [
  'src/app/[locale]/score/page.tsx',
  'src/lib/repositories/reports.ts',
]) {
  requireText(file, 'in_review', `${file} includes review-ready slide reports`)
}

requireText(
  'src/app/[locale]/score/page.tsx',
  'slide_html_urls_by_lang',
  'src/app/[locale]/score/page.tsx requires slide HTML assets'
)
requireText(
  'src/lib/repositories/reports.ts',
  'reportSupportsLocale',
  'src/lib/repositories/reports.ts delegates locale asset checks'
)

requireText('src/app/[locale]/projects/[slug]/page.tsx', 'in_review', 'src/app/[locale]/projects/[slug]/page.tsx includes review-ready slide reports')
requireText('src/app/[locale]/projects/[slug]/page.tsx', 'reportSupportsLocale', 'src/app/[locale]/projects/[slug]/page.tsx delegates locale asset checks')
requireText('src/lib/report-locale.ts', 'slide_html_urls_by_lang', 'src/lib/report-locale.ts requires slide HTML assets')
requireText('src/app/[locale]/projects/[slug]/page.tsx', 'getProjectDetailHeaderStyle', 'src/app/[locale]/projects/[slug]/page.tsx renders project header background')
requireText('src/app/[locale]/projects/[slug]/page.tsx', 'PROJECT_HEADER_FALLBACK_IMAGE', 'src/app/[locale]/projects/[slug]/page.tsx keeps fallback header background')
requireText('src/app/[locale]/exchanges/page.tsx', 'getExchangesHeaderStyle', 'src/app/[locale]/exchanges/page.tsx renders exchange list header background')
requireText('src/app/[locale]/exchanges/[slug]/page.tsx', 'getExchangeDetailHeaderStyle', 'src/app/[locale]/exchanges/[slug]/page.tsx renders exchange detail header background')
requireText('src/lib/exchange-header-art.ts', 'EXCHANGES_HEADER_BACKGROUND_IMAGE', 'src/lib/exchange-header-art.ts defines exchange list background asset')
requireText('src/lib/exchange-header-art.ts', 'EXCHANGE_DETAIL_HEADER_BASE_IMAGE', 'src/lib/exchange-header-art.ts defines exchange detail background asset')

if (failures.length > 0) {
  console.error('\nWebsite pipeline alignment failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('\nWebsite pipeline alignment verified.')
