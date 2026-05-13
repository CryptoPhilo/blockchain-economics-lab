# MAT Report Publishing

Manifest key: `mat-report-publishing`
Paperclip pipeline: `MAT Report Publishing`
Owner: CRO
Status: active
Last reconciliation: 2026-05-14

## Operating Definition

This pipeline publishes MAT slide reports for the Blockchain Economics Lab. It
inherits the shared report-publishing node structure from
`econ-report-publishing` and specializes the report type and source paths.

- Input: slide-form PDFs in Google Drive `Slide/MAT`.
- Source confirmation: Korean Markdown source in `analysis/MAT`.
- Runtime: GitHub Actions workflow `.github/workflows/slide-pipeline-cron.yml`.
- Schedule: workflow cron `*/5 * * * *`, gated by the Supabase `pipeline_schedules` row for `slide-pipeline`; expected effective check interval is 30 minutes. Scheduled runs must enumerate the full active `Slide/MAT` tree and rely on `_slide_processed.json` to skip unchanged files, not a modified-time lookback that can strand unprocessed PDFs after downtime.
- Local execution: dry-run, development, and incident reproduction only. Production writes must run remotely.
- Output: website-visible report records and slide assets.

## Website Visibility Baseline

As of PR #60 / commit `a16addc1`, agents must treat the website report
visibility baseline as follows:

- `reportSupportsLocale` is the canonical website report exposure policy.
- Google Drive/PDF assets are valid report exposure evidence for MAT reports.
- `slide_html_urls_by_lang` is a preferred rendering asset, not the general
  website visibility gate.
- MAT pipeline diagnostics must use `a16addc1` or a later production baseline
  before comparing current behavior to prior report visibility fixes.

## Nodes

1. `source_collection` / Slide PDF intake: `scripts/pipeline/watch_slides.py --type mat`.
2. `research_synthesis` / Analysis source confirmation: `scripts/pipeline/watch_slides.py`.
3. `draft_report` / Summary and marketing extraction: `scripts/pipeline/marketing_content_pipeline.py`, invoked by `scripts/pipeline/watch_slides.py`.
4. `summary_marketing_localization` / 7-language summary and marketing localization: `scripts/pipeline/marketing_content_pipeline.py`, invoked by `scripts/pipeline/watch_slides.py`.
5. `editorial_review` / Publication review: Paperclip approval gate, owner COO.
6. `website_publish` / Website publishing: `scripts/pipeline/watch_slides.py`.
7. `post_publish_monitoring` / Post-publish monitoring: `.github/workflows/pipeline-daily-report.yml` and `scripts/pipeline/daily_pipeline_report.py`.

## BCE-1869 Boundary Update

BCE-1869 did not add or remove MAT pipeline nodes and did not change the trigger,
approval gate, or output contract. It changed the shared watcher implementation
boundary used by this inherited pipeline:

- `scripts/pipeline/watch_slides_inspection.py` owns PDF page profiling, text/OCR extraction, and language resolution helpers.
- `scripts/pipeline/watch_slides_matching.py` owns project signal matching, watcher-only aliases, and slug/content mismatch guards.
- `scripts/pipeline/watch_slides_telemetry.py` owns optional Paperclip run/node/event payloads and watcher status taxonomy.
- `scripts/pipeline/watch_slides.py` remains the CLI and orchestration boundary, including DB/storage write orchestration.

The runtime manifest records that the `draft_report` and
`summary_marketing_localization` nodes use `marketing_content_pipeline` through
the `watch_slides.py` runtime caller. `npm run verify:runtime-pipelines` must
pass before deployment or remote execution.
