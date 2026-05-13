# BCELab Website Development and Operations

Manifest key: `bcelab-website-development-and-operations`
Paperclip pipeline: `BCELab Website Development and Operations`
Owner: CTO
Status: active
Last reconciliation: 2026-05-14

## Operating Definition

This pipeline governs website changes and production deployment for the
Blockchain Economics Lab website.

- Intake: Paperclip issue-based change request.
- Implementation: isolated branch or temporary workspace.
- Definition alignment: `scripts/verify-website-pipeline.mjs` through `.github/workflows/ci.yml`.
- Quality and build verification: `.github/workflows/ci.yml`.
- Deployment approval: Paperclip plus GitHub production environment approval.
- Production deployment: `.github/workflows/production-deploy.yml`.
- Post-deploy monitoring: Vercel cron route `/api/cron/heartbeat`.

## Report Visibility Baseline

As of PR #60 / commit `a16addc1`, agents must treat the website report
visibility baseline as follows:

- `reportSupportsLocale` is the canonical website report exposure policy.
- Google Drive/PDF assets are valid report exposure evidence.
- `slide_html_urls_by_lang` is a preferred rendering asset, not the general
  website visibility gate.
- Pipeline, report, and website diagnostics must use `a16addc1` or a later
  production baseline before comparing current behavior to prior fixes.

## BCE-1869 Relationship

BCE-1869 affected the report-publishing watcher boundary, not this website
operations pipeline. This page exists because the runtime manifest and
Paperclip pipeline metadata both need a durable state page for every active
pipeline.
