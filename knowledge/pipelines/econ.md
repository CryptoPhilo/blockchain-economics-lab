# ECON Report Publishing

Manifest key: `econ-report-publishing`
Paperclip pipeline: `ECON Report Publishing`
Owner: CRO
Status: active
Last reconciliation: 2026-05-15

## Operating Definition

This pipeline publishes ECON slide reports for the Blockchain Economics Lab.

- Input: slide-form PDFs in Google Drive `Slide/ECON`.
- Source confirmation: Korean Markdown source in `analysis/ECON`.
- Runtime: GitHub Actions workflow `.github/workflows/slide-pipeline-cron.yml`.
- Schedule: workflow cron `*/5 * * * *`, gated by the Supabase `pipeline_schedules` row for `slide-pipeline`; expected effective check interval is 30 minutes. Scheduled runs must enumerate the full active `Slide/ECON` tree and rely on `_slide_processed.json` to skip unchanged files, not a modified-time lookback that can strand unprocessed PDFs after downtime.
- Telemetry state store: Supabase `pipeline_runs`, `pipeline_node_runs`, and
  `pipeline_events`. Paperclip REST telemetry is secondary opt-in only via
  `PAPERCLIP_TELEMETRY_SECONDARY_ENABLED=true`.
- Local execution: dry-run, development, and incident reproduction only. Production writes must run remotely.
- Output: website-visible report records and slide assets.

## Website Visibility Baseline

As of PR #60 / commit `a16addc1`, agents must treat the website report
visibility baseline as follows:

- `reportSupportsLocale` is the canonical website report exposure policy.
- Google Drive/PDF assets are valid report exposure evidence for ECON reports.
- `slide_html_urls_by_lang` is a preferred rendering asset, not the general
  website visibility gate.
- ECON pipeline diagnostics must use `a16addc1` or a later production baseline
  before comparing current behavior to prior report visibility fixes.

## Nodes

1. `source_collection` / Slide PDF intake: `scripts/pipeline/watch_slides.py --type econ`.
2. `research_synthesis` / Analysis source confirmation: `scripts/pipeline/watch_slides.py`.
3. `draft_report` / Summary and marketing extraction: `scripts/pipeline/marketing_content_pipeline.py`, invoked by `scripts/pipeline/watch_slides.py`.
4. `summary_marketing_localization` / 7-language summary and marketing localization: `scripts/pipeline/marketing_content_pipeline.py`, invoked by `scripts/pipeline/watch_slides.py`.
5. `editorial_review` / Publication review: Paperclip approval gate, owner COO.
6. `website_publish` / Website publishing: `scripts/pipeline/watch_slides.py`.
7. `post_publish_monitoring` / Post-publish monitoring: `.github/workflows/pipeline-daily-report.yml` and `scripts/pipeline/daily_pipeline_report.py`.

## BCE-1869 Boundary Update

BCE-1869 did not add or remove ECON pipeline nodes and did not change the trigger,
approval gate, or output contract. It changed the executable implementation
boundary behind the existing nodes:

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

BCE-1907 keeps the same ECON pipeline nodes and runtime caller, but changes the
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
  production DB rollout requires the BCE-1907 migration/backfill before remote
  production writes.

## BCE-1933 Card Summary Quality Gate

As of 2026-06-01, the shared summary/marketing node treats report card summary
copy as a separate contract from longer marketing copy. `scripts/pipeline/marketing_content_pipeline.py`
derives card summaries through `derive_card_copy`, gates them against
disclaimer/methodology/table/metadata fragments, locale script mismatch, length
limits, and project subject mismatch, then stores summary provenance under
`card_data.summary_quality`.

The report-type extraction priority is:

- ECON: project identity, economic design, core risk or sustainability judgment.
- MAT: maturity stage/score, strengths/weaknesses, investor or operating implication.
- FOR: event/risk type, core signal, short-term observation point.

Existing rows must be audited before writes with
`scripts/pipeline/backfill_card_summaries.py`, which defaults to dry-run and
writes `scripts/pipeline/output/card_summary_backfill_audit.json`. Approved
remote execution uses `.github/workflows/report-card-summary-backfill.yml`; apply
mode requires a slug-scoped dispatch and remains reserved for the approved
production-write path.

## BCE-1937 Card Auxiliary Text Quality Gate

As of 2026-06-02, the shared summary/marketing node also applies the card text
quality gate to auxiliary card copy such as `marketing_content_by_lang` /
`card_data.marketing_by_lang`, which the website labels as `Investment View`.
LaTeX/math tokens, raw markdown, table/code fragments, formula fragments, and
overlong source excerpts must not be published as card-visible auxiliary text.
When a safe natural-language auxiliary sentence cannot be derived, the field is
omitted instead of falling back to raw report text.

The website helper `src/lib/report-marketing-content.ts` is a display-time
last-resort guard for existing rows that may still contain unsafe auxiliary
copy before a remote production backfill/update is applied.

## BCE-1940 AWE ECON Backfill Target Selection

As of 2026-06-02, report card summary backfill target selection uses the same
website-visible status boundary as report display: `published`, `coming_soon`,
and `in_review`, combined with the shared locale asset support check. This keeps
`scripts/pipeline/backfill_card_summaries.py` and
`find_matching_korean_slide_row()` aligned for slide-backed ECON rows such as
AWE Network ECON, which are visible on website cards while still `in_review`.
