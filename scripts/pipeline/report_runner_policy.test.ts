import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const policyScript = path.join(process.cwd(), 'scripts/pipeline/report_runner_policy.py')
const workflowFile = path.join(process.cwd(), '.github/workflows/report-pipeline-cron.yml')

type RunnerPolicy = {
  report_type: string
  long_runner_required: string
  runner_labels: string[]
  timeout_minutes: number
  runner_class: string
  route_reason: string
}

function runPolicy(args: string[]): RunnerPolicy {
  const output = execFileSync('python3', [policyScript, ...args], {
    cwd: process.cwd(),
    encoding: 'utf8',
  })

  return JSON.parse(output) as RunnerPolicy
}

describe('report_runner_policy', () => {
  it('keeps scheduled runs on github-hosted runners', () => {
    const policy = runPolicy(['--event-name', 'schedule'])

    expect(policy.report_type).toBe('all')
    expect(policy.long_runner_required).toBe('false')
    expect(policy.runner_labels).toEqual(['ubuntu-latest'])
    expect(policy.timeout_minutes).toBe(240)
  })

  it('routes forced manual reruns to the long runner', () => {
    const policy = runPolicy([
      '--event-name',
      'workflow_dispatch',
      '--report-type',
      'for',
      '--force',
      'true',
    ])

    expect(policy.long_runner_required).toBe('true')
    expect(policy.runner_labels).toEqual(['self-hosted', 'linux', 'x64', 'bce-long-report'])
    expect(policy.timeout_minutes).toBe(720)
    expect(policy.route_reason).toContain('force rerun')
  })

  it('routes full econ and mat manual runs to the long runner', () => {
    const econPolicy = runPolicy([
      '--event-name',
      'workflow_dispatch',
      '--report-type',
      'econ',
    ])
    const matPolicy = runPolicy([
      '--event-name',
      'workflow_dispatch',
      '--report-type',
      'mat',
    ])

    expect(econPolicy.long_runner_required).toBe('true')
    expect(matPolicy.long_runner_required).toBe('true')
  })

  it('keeps targeted manual runs on github-hosted runners', () => {
    const policy = runPolicy([
      '--event-name',
      'workflow_dispatch',
      '--report-type',
      'mat',
      '--slug',
      'bitcoin',
    ])

    expect(policy.long_runner_required).toBe('false')
    expect(policy.runner_labels).toEqual(['ubuntu-latest'])
  })

  it('is wired into the workflow definition', () => {
    const workflow = fs.readFileSync(workflowFile, 'utf8')

    expect(workflow).toContain('resolve-runner:')
    expect(workflow).toContain('scripts/pipeline/report_runner_policy.py')
    expect(workflow).toContain('needs.resolve-runner.outputs.runner_labels')
  })
})
