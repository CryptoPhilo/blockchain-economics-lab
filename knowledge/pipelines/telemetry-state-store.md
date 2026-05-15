# Report Pipeline Telemetry State Store

Last reconciliation: 2026-05-15

## Scope

BCE-1900 makes Supabase the primary durable telemetry sink for the ECON, MAT,
and FOR slide report pipelines.

Runtime writer:

- `scripts/pipeline/watch_slides_telemetry.py`

Supabase tables:

- `pipeline_runs`
- `pipeline_node_runs`
- `pipeline_events`

## Current Production State

2026-05-15 BCE-1904 applied
`supabase/migrations/20260515_add_pipeline_telemetry_tables.sql` to production
through the selected SQL fallback workflow, not `supabase db push` or migration
repair. Evidence run:
`https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/25894759115`.

Post-apply REST schema read returned HTTP 200 for:

- `pipeline_runs`
- `pipeline_node_runs`
- `pipeline_events`

The production `pipeline_runs.status` column still has the legacy state-tracker
check constraint. Supabase telemetry writers must use legacy parent-run status
values there (`processing`, `dry_run`, `done`, `content_failed_terminal`, or
`processing_error`) and keep richer watcher status values in child node/event
telemetry.

## Required Environment

The primary sink is enabled when both are present:

- `SUPABASE_URL` or `NEXT_PUBLIC_SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

Paperclip REST sync is disabled by default. To mirror telemetry to Paperclip as
a secondary sink, set:

- `PAPERCLIP_TELEMETRY_SECONDARY_ENABLED=true`
- `PAPERCLIP_API_URL`
- `PAPERCLIP_API_KEY`
- `PAPERCLIP_COMPANY_ID`
- Optional per-type pipeline IDs such as `PAPERCLIP_ECON_PIPELINE_ID`

## Migration Procedure

1. Apply `supabase/migrations/20260515_add_pipeline_telemetry_tables.sql`.
2. Confirm the existing `pipeline_runs` reader contract still works:
   `id`, `report_type`, `project_slug`, `version`, `status`,
   `source_filename`, `retry_count`, `started_at`, `completed_at`,
   `languages_completed`, and `error_detail`.
3. Run a safe watcher dry run and confirm a row is written to `pipeline_runs`
   with child rows in `pipeline_node_runs` and `pipeline_events`.
4. Run `scripts/generate-pipeline-ops-snapshot.mjs` with Supabase credentials
   to confirm dashboard readers can still query recent runs.

## Backfill Procedure

No historical Paperclip run backfill is required for BCE-1900. Historical
`pipeline_runs` rows, if present, remain readable because the migration adds
columns without deleting legacy columns.

If operations needs historical node/event rows, backfill from the markdown logs
under `logs/slide_pipeline/` by creating one `pipeline_node_runs` row per
manifest node and one `pipeline_events` completion row per historical run. Use
the log filename as `artifact_path` and leave unavailable GitHub metadata null.

## Paperclip Sync Procedure

Paperclip is no longer the source of truth for scheduled run telemetry.
Paperclip issues and pipeline state wiki pages remain the coordination and
approval layer. If Paperclip requires a live mirror, enable the secondary sink
explicitly through `PAPERCLIP_TELEMETRY_SECONDARY_ENABLED=true`; do not restore
Paperclip secrets to the default GitHub Actions run environment.
