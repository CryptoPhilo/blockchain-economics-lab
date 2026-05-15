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

function basename(file) {
  return path.basename(file)
}

function moduleName(file) {
  return basename(file).replace(/\.[^.]+$/, '')
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

function assertEntrypointWorkflowRelationship(execution, prefix) {
  if (!execution.workflow || !execution.entrypoint) return

  const entrypointName = basename(execution.entrypoint)
  const workflowText = exists(execution.workflow) ? read(execution.workflow) : ''
  const commandText = execution.commandContains ?? ''
  const commandMentionsEntrypoint =
    commandText.includes(entrypointName) || workflowText.includes(entrypointName)

  if (commandMentionsEntrypoint) {
    pass(`${prefix}: workflow directly invokes entrypoint`)
    return
  }

  if (exists('package.json')) {
    const packageJson = JSON.parse(read('package.json'))
    const scripts = packageJson.scripts ?? {}
    for (const [scriptName, scriptCommand] of Object.entries(scripts)) {
      if (
        commandText.includes(`npm run ${scriptName}`) &&
        String(scriptCommand).includes(entrypointName)
      ) {
        pass(`${prefix}: workflow invokes entrypoint through package script ${scriptName}`)
        return
      }
    }
  }

  if (!execution.invokedBy) {
    fail(
      `${prefix}: entrypoint ${execution.entrypoint} is not directly invoked by ` +
        `${execution.workflow}; declare invokedBy plus requiredImport when it is called by another runtime script`,
    )
    return
  }

  assertFile(execution.invokedBy, `${prefix}: declared runtime caller exists`)

  const callerName = basename(execution.invokedBy)
  const commandMentionsCaller =
    commandText.includes(callerName) || workflowText.includes(callerName)
  if (commandMentionsCaller) {
    pass(`${prefix}: workflow invokes declared runtime caller`)
  } else {
    fail(`${prefix}: workflow does not invoke declared runtime caller ${execution.invokedBy}`)
  }

  if (!exists(execution.invokedBy)) return

  const callerText = read(execution.invokedBy)
  const importNeedle = execution.requiredImport ?? moduleName(execution.entrypoint)
  if (callerText.includes(importNeedle)) {
    pass(`${prefix}: runtime caller references entrypoint module`)
  } else {
    fail(
      `${prefix}: ${execution.invokedBy} does not reference ${importNeedle}; ` +
        'entrypoint/caller relationship is not explainable',
    )
  }
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

  if (!rawPipeline.statePage) {
    fail(`${rawPipeline.key}: statePage is required`)
  } else {
    assertFile(rawPipeline.statePage, `${rawPipeline.key}: state page exists`)
    assertContains(rawPipeline.statePage, rawPipeline.key, `${rawPipeline.key}: state page names manifest key`)
    assertContains(
      rawPipeline.statePage,
      rawPipeline.paperclipName,
      `${rawPipeline.key}: state page names Paperclip pipeline`,
    )
  }

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

    if (execution.mode === 'local_only') {
      fail(`${prefix}: local_only execution is forbidden for active pipelines`)
    }

    if (execution.workflow) {
      assertFile(execution.workflow, `${prefix}: workflow exists`)
      if (execution.commandContains) {
        assertContains(execution.workflow, execution.commandContains, `${prefix}: workflow invokes expected command`)
      }
    }

    if (execution.entrypoint) {
      assertFile(execution.entrypoint, `${prefix}: entrypoint exists`)
      assertEntrypointWorkflowRelationship(execution, prefix)
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
