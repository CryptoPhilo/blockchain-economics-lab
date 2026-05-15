import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const manifestPath = 'pipelines/bcelab-runtime-pipelines.json'
const allowedRemoteModes = new Set([
  'github_actions',
  'vercel_cron',
  'paperclip_issue',
  'paperclip_agent',
  'isolated_branch_or_workspace',
])

const failures = []

function read(file) {
  return fs.readFileSync(path.join(root, file), 'utf8')
}

function exists(file) {
  return fs.existsSync(path.join(root, file))
}

function pass(message) {
  console.log(`PASS ${message}`)
}

function fail(message) {
  failures.push(message)
}

function routeToFile(route) {
  return route.replace(/^\/api\//, 'src/app/api/').replace(/$/, '/route.ts')
}

function assertFile(file, label) {
  if (exists(file)) pass(label)
  else fail(`${label}: missing ${file}`)
}

function assertContains(file, needle, label) {
  if (!exists(file)) {
    fail(`${label}: missing ${file}`)
    return
  }
  if (read(file).includes(needle)) pass(label)
  else fail(`${label}: ${file} does not contain ${needle}`)
}

function resolvePipeline(pipeline, byKey) {
  if (!pipeline.extends) return pipeline
  const base = byKey.get(pipeline.extends)
  if (!base) {
    fail(`${pipeline.key}: extends unknown pipeline ${pipeline.extends}`)
    return pipeline
  }
  return {
    ...base,
    ...pipeline,
    nodes: pipeline.nodes ?? base.nodes,
    cadence: pipeline.cadence ?? base.cadence,
  }
}

assertFile(manifestPath, 'Runtime pipeline manifest exists')
const manifest = JSON.parse(read(manifestPath))

if (manifest.remoteFirst === true) pass('Manifest is remote-first')
else fail('Manifest must set remoteFirst=true')

if (manifest.localExecutionPolicy?.productionWritesAllowed === false) {
  pass('Local production writes are forbidden')
} else {
  fail('localExecutionPolicy.productionWritesAllowed must be false')
}

const pipelineByKey = new Map((manifest.pipelines ?? []).map((pipeline) => [pipeline.key, pipeline]))

for (const rawPipeline of manifest.pipelines ?? []) {
  const pipeline = resolvePipeline(rawPipeline, pipelineByKey)
  if (!pipeline.key || !pipeline.paperclipName) fail('Every pipeline needs key and paperclipName')

  if (pipeline.status === 'active') {
    if (!pipeline.owner) fail(`${pipeline.key}: active pipeline needs owner`)
    else pass(`${pipeline.key}: active owner declared`)
  }

  if (pipeline.cadence?.workflow) {
    assertFile(pipeline.cadence.workflow, `${pipeline.key}: cadence workflow exists`)
    if (pipeline.cadence.cron) {
      assertContains(pipeline.cadence.workflow, pipeline.cadence.cron, `${pipeline.key}: cadence cron is in workflow`)
    }
  }

  if (pipeline.cadence?.postDeployCron) {
    assertFile(routeToFile(pipeline.cadence.postDeployCron), `${pipeline.key}: post-deploy cron route exists`)
  }

  for (const node of pipeline.nodes ?? []) {
    const prefix = `${pipeline.key}.${node.key}`
    if (!node.paperclipLabel) fail(`${prefix}: paperclipLabel is required`)

    if (node.approvalGate?.required) {
      pass(`${prefix}: approval gate declared`)
      continue
    }

    const execution = node.execution
    if (!execution) {
      fail(`${prefix}: needs execution or approvalGate`)
      continue
    }

    if (!allowedRemoteModes.has(execution.mode)) {
      fail(`${prefix}: unsupported execution mode ${execution.mode}`)
    } else {
      pass(`${prefix}: execution mode ${execution.mode}`)
    }

    if (execution.workflow) {
      assertFile(execution.workflow, `${prefix}: workflow exists`)
      if (execution.commandContains) {
        assertContains(execution.workflow, execution.commandContains, `${prefix}: workflow invokes expected command`)
      }
    }

    if (execution.entrypoint) {
      assertFile(execution.entrypoint, `${prefix}: entrypoint exists`)
    }

    if (execution.route) {
      assertFile(routeToFile(execution.route), `${prefix}: route exists`)
    }

    const localAllowed = execution.localAllowed ?? []
    if (localAllowed.includes('production')) {
      fail(`${prefix}: localAllowed must not include production`)
    }
  }
}

assertContains('package.json', '"verify:runtime-pipelines"', 'package script verify:runtime-pipelines is registered')
assertContains('.github/workflows/ci.yml', 'npm run verify:runtime-pipelines', 'CI runs runtime pipeline verification')
assertContains('.github/workflows/slide-pipeline-cron.yml', 'npm run verify:runtime-pipelines', 'Slide workflow verifies runtime manifest before execution')
assertFile(
  'supabase/migrations/20260515_add_pipeline_telemetry_tables.sql',
  'Remote pipeline state store migration exists',
)
assertContains(
  'scripts/pipeline/watch_slides_telemetry.py',
  'class RemotePipelineState',
  'Slide watcher writes remote pipeline state',
)
assertContains(
  'scripts/pipeline/watch_slides_telemetry.py',
  "self.request('POST', 'pipeline_runs'",
  'Slide watcher creates Supabase pipeline run records',
)

const slideWorkflow = read('.github/workflows/slide-pipeline-cron.yml')
for (const localOnlyPaperclipEnv of [
  'PAPERCLIP_API_URL',
  'PAPERCLIP_API_KEY',
  'PAPERCLIP_AGENT_TOKEN',
  'PAPERCLIP_TOKEN',
]) {
  if (slideWorkflow.includes(localOnlyPaperclipEnv)) {
    fail(`Slide workflow must not inject ${localOnlyPaperclipEnv}; GitHub Actions cannot depend on local Paperclip`)
  }
}

if (exists('.github/workflows/production-deploy.yml')) {
  assertContains(
    '.github/workflows/production-deploy.yml',
    'npm run verify:runtime-pipelines',
    'Production deploy verifies runtime manifest before deployment',
  )
}

if (failures.length > 0) {
  console.error('\nRuntime pipeline verification failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('\nRuntime pipeline manifest verified.')
