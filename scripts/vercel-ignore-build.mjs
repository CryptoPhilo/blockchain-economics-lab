#!/usr/bin/env node
import { execFileSync } from 'node:child_process'

const TRACKER_ONLY_FILES = new Set([
  'scripts/pipeline/output/_slide_processed.json',
])

function git(args) {
  return execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
}

function changedFilesForCurrentCommit() {
  try {
    git(['rev-parse', 'HEAD^'])
  } catch {
    return []
  }

  return git(['diff', '--name-only', 'HEAD^', 'HEAD'])
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

const files = changedFilesForCurrentCommit()
const trackerOnly = files.length > 0 && files.every((file) => TRACKER_ONLY_FILES.has(file))

if (trackerOnly) {
  console.log(`Skipping Vercel build for tracker-only commit: ${files.join(', ')}`)
  process.exit(0)
}

process.exit(1)
