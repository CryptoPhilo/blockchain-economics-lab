# FOR Report Publishing

Manifest key: `for-report-publishing`
Paperclip pipeline: `FOR Report Publishing`
Owner: CRO
Status: active
Last reconciliation: 2026-05-15

## Operating Definition

This pipeline publishes FOR slide reports for the Blockchain Economics Lab. It
inherits the shared report-publishing node structure from
`econ-report-publishing` and specializes the report type and source paths.

- Input: slide-form PDFs in Google Drive `Slide/FOR`.
- Source confirmation: Korean Markdown source in `analysis/FOR`.
- Runtime: GitHub Actions workflow `.github/workflows/slide-pipeline-cron.yml`.
- Schedule: workflow cron `*/5 * * * *`, gated by the Supabase `pipeline_schedules` row for `slide-pipeline`; expected effective check interval is 30 minutes.
- Telemetry state store: Supabase `pipeline_runs`, `pipeline_node_runs`, and
  `pipeline_events`. Paperclip REST telemetry is secondary opt-in only via
  `PAPERCLIP_TELEMETRY_SECONDARY_ENABLED=true`.
- Local execution: dry-run, development, and incident reproduction only. Production writes must run remotely.
- Output: website-visible report records and slide assets.

## Website Visibility Baseline

As of PR #60 / commit `a16addc1`, agents must treat the website report
visibility baseline as follows:

- `reportSupportsLocale` is the canonical website report exposure policy.
- Google Drive/PDF assets are valid report exposure evidence for FOR reports.
- `slide_html_urls_by_lang` is a preferred rendering asset, not the general
  website visibility gate.
- FOR pipeline diagnostics must use `a16addc1` or a later production baseline
  before comparing current behavior to prior report visibility fixes.
- `coming_soon` FOR rows without Drive/PDF/HTML assets are rapid-change
  pre-slide placeholders. They are not published FOR report availability and
  must not be cancelled only because no active `Slide/FOR` PDF exists.
- Once a FOR row has a Drive/PDF/HTML asset, or once its status advances beyond
  the placeholder state, the active `Slide/FOR` PDF source-of-truth rule applies.
  Placeholder age should be monitored separately and escalated if the report
  slide is not produced within the expected operations window.

## Nodes

1. `source_collection` / Slide PDF intake: `scripts/pipeline/watch_slides.py --type for`.
2. `research_synthesis` / Analysis source confirmation: `scripts/pipeline/watch_slides.py`.
3. `draft_report` / Summary and marketing extraction: `scripts/pipeline/marketing_content_pipeline.py`, invoked by `scripts/pipeline/watch_slides.py`.
4. `summary_marketing_localization` / 7-language summary and marketing localization: `scripts/pipeline/marketing_content_pipeline.py`, invoked by `scripts/pipeline/watch_slides.py`.
5. `editorial_review` / Publication review: Paperclip approval gate, owner COO.
6. `website_publish` / Website publishing: `scripts/pipeline/watch_slides.py`.
7. `post_publish_monitoring` / Post-publish monitoring: `.github/workflows/pipeline-daily-report.yml` and `scripts/pipeline/daily_pipeline_report.py`.

## BCE-1869 Boundary Update

BCE-1869 did not add or remove FOR pipeline nodes and did not change the trigger,
approval gate, or output contract. It changed the shared watcher implementation
boundary used by this inherited pipeline:

- `scripts/pipeline/watch_slides_inspection.py` owns PDF page profiling, text/OCR extraction, and language resolution helpers.
- `scripts/pipeline/watch_slides_matching.py` owns project signal matching, watcher-only aliases, and slug/content mismatch guards.
- `scripts/pipeline/watch_slides_telemetry.py` owns Supabase run/node/event telemetry, optional secondary Paperclip payloads, and watcher status taxonomy.
- `scripts/pipeline/watch_slides.py` remains the CLI and orchestration boundary, including DB/storage write orchestration.

The runtime manifest records that the `draft_report` and
`summary_marketing_localization` nodes use `marketing_content_pipeline` through
the `watch_slides.py` runtime caller. `npm run verify:runtime-pipelines` must
pass before deployment or remote execution.

## BCE-1900 Telemetry State Store Update

BCE-1900 moved report pipeline telemetry from default Paperclip REST writes to
the Supabase durable state store. `scripts/pipeline/watch_slides_telemetry.py`
now writes run rows, node snapshots, completion events, counts, GitHub metadata,
and log artifact paths to Supabase by default when `SUPABASE_URL` or
`NEXT_PUBLIC_SUPABASE_URL` plus `SUPABASE_SERVICE_KEY` are present. GitHub
Actions no longer exports Paperclip API secrets in the default slide pipeline
run step.

## BCE-1907 Report Version Identity Update

BCE-1907 keeps the same FOR pipeline nodes and runtime caller, but changes the
DB publication contract behind `website_publish`:

- `scripts/pipeline/watch_slides.py` derives a stable Drive source identity from
  canonical project identity, report type, locale, Drive file id, modifiedTime,
  file size, optional checksum, and filename.
- Reprocessing the same Drive PDF reuses the existing `project_reports` version.
- A new Drive PDF for the same project/report_type/locale creates the next
  versioned `project_reports` row, links `previous_report_id`, and moves the
  `is_latest` default pointer to the new row.
- Backfill chooses the default row by visible/publishable status first, highest
  `version` second, and timestamp only as a tie-breaker.
- Slide-backed rows with website-visible assets are published/default latest;
  FOR `coming_soon` placeholders without assets remain governed by the existing
  placeholder policy. Production DB rollout requires the BCE-1907
  migration/backfill before remote production writes.

## BCE-1939 Semantic Insight Quality Gate

As of 2026-06-02, FOR card summaries share the semantic insight gate in
`scripts/pipeline/marketing_content_pipeline.py`. FOR candidates are prioritized
for event/risk signals, abnormal movement, liquidity, volatility, buy/sell
pressure, and short-term observation points, while source-provenance,
methodology, table, prompt-template, and raw-format fragments remain rejected.

This does not change FOR pipeline nodes or placeholder policy; it narrows the
accepted card-visible text contract inside the existing shared summary and
marketing localization node.
