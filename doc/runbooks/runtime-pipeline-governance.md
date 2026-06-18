# Runtime Pipeline Governance

## Rule

Paperclip owns the operating definition. This repository owns the executable
manifest. CI verifies that both stay aligned before code can be deployed or
remote jobs can run.

The executable manifest is:

```text
pipelines/bcelab-runtime-pipelines.json
```

## Execution Boundary

Production pipeline work must run through remote, versioned execution:

- GitHub Actions for scheduled or manually dispatched report pipeline jobs.
- Vercel Cron for website heartbeat checks.
- GitHub Actions production deployment with GitHub `production` environment
  approval for production website deploys.
- Paperclip issues and approvals for board-governed changes.

Local execution is allowed only for:

- dry-run checks,
- development,
- incident reproduction.

Local execution must not perform production writes. If a local reproduction is
needed, link it to a Paperclip issue and rerun the production-affecting path
through the remote workflow before requesting approval.

## Required Checks

Run these before requesting board approval or deploying pipeline code:

```bash
npm run verify:runtime-pipelines
npm run verify:pipeline
npx tsc --noEmit
npm test -- --passWithNoTests
npm run build
```

`npm run verify:runtime-pipelines` checks:

- every active Paperclip pipeline has an owner,
- every executable node maps to a remote execution mode,
- referenced workflow files exist,
- referenced script entrypoints exist,
- scheduled nodes have a schedule,
- Vercel cron routes exist,
- active nodes are not declared as local-only,
- CI, slide cron, and production deploy workflows run the manifest verifier.

## Release Review Gate

Pipeline, deploy, and production-facing website PRs require approval from a
GitHub identity that is not the PR author identity before merge. An approval
from the same GitHub account that authored the PR does not satisfy the release
gate, even if the same person or agent is performing multiple roles in
Paperclip.

A single-account exception is allowed only when both conditions are true:

- the CEO has granted an explicit waiver for that release, and
- the PR links Paperclip issue evidence that records the waiver and the release
  scope.

Before merging a pipeline or deploy PR, the reviewer must confirm:

- remote checks passed in GitHub Actions or Vercel, as applicable,
- the relevant state page under `knowledge/pipelines/` was read and still
  matches the change,
- `pipelines/bcelab-runtime-pipelines.json` still maps the affected pipeline
  nodes to their executable remote runtime, and
- any production deployment or production-write path remains approval-gated
  through Paperclip and the GitHub `production` environment.

## Change Procedure

1. Create or update a Paperclip issue that names the affected pipeline and node.
2. Change the pipeline definition in Paperclip if the operating behavior changes.
3. Update `pipelines/bcelab-runtime-pipelines.json` to map the definition to
   actual workflows, scripts, routes, or approval gates.
4. Implement code in an isolated branch or temporary workspace.
5. Run the required checks.
6. Open a PR and fill in the Paperclip Pipeline Evidence section.
7. Use preview deployment for review.
8. Request board approval.
9. Deploy through `.github/workflows/production-deploy.yml`.
10. Confirm post-deploy heartbeat and affected report surfaces.

## Current Remote Runtime Map

| Pipeline | Remote runtime | Entry point |
| --- | --- | --- |
| ECON Report Publishing | GitHub Actions | `.github/workflows/slide-pipeline-cron.yml` |
| MAT Report Publishing | GitHub Actions | `.github/workflows/slide-pipeline-cron.yml` |
| FOR Report Publishing | GitHub Actions | `.github/workflows/slide-pipeline-cron.yml` |
| Website Development and Operations | GitHub Actions + Vercel Cron | `.github/workflows/production-deploy.yml`, `/api/cron/heartbeat` |

## Known Governance Risk

If Vercel is configured to auto-deploy production directly from `main`, it can
bypass the GitHub Actions production workflow. The CTO must either disable that
setting or record explicit board acceptance of the bypass risk.
