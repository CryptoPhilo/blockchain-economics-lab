# Forensic Rapid Change Scan

Manifest key: `forensic-rapid-change-scan`
Paperclip pipeline: `Forensic Rapid Change Scan`
Owner: CRO
Status: active
Last reconciliation: 2026-05-16

## Operating Definition

This pipeline scans CoinMarketCap listings for market-relative sudden movers
that may need FOR source work. It is upstream evidence for FOR report intake,
not the FOR report publisher itself.

- Runtime workflow: `.github/workflows/forensic-rapid-change-scan.yml`.
- Current trigger: `workflow_dispatch`.
- Current cadence: operator-dispatched scan; default run is dry-run.
- Runtime entrypoint: `scripts/pipeline/sudden_movers_card_anchor.py`.
- Candidate scanner: `scripts/pipeline/candidates/sudden_movers_scanner.py`.
- Legacy registration contract: `_legacy/pipeline/scan_forensic.py`.
- Required secret: `COINMARKETCAP_API_KEY`, passed to runtime as `CMC_API_KEY`.
- Default input size: top 500 market-cap listings.
- Threshold: workflow input override or
  `scripts/pipeline/config.py::get_forensic_scan_deviation_threshold`.
- Default activation: card-anchor writes are off unless `enable_card_anchor=true`
  and `dry_run=false`.
- Artifact output:
  `scripts/pipeline/output/sudden_movers_card_anchor_${GITHUB_RUN_ID}.json`.
- Optional write outputs:
  `scripts/pipeline/output/sudden_movers_card_anchor_state.json` and
  `scripts/pipeline/output/sudden_movers_card_anchors.jsonl`.
- Durable telemetry: when Supabase telemetry credentials are configured,
  `scripts/pipeline/sudden_movers_card_anchor.py` writes
  `pipeline_runs`, `pipeline_node_runs`, and `pipeline_events` rows under
  pipeline key `forensic-rapid-change-scan`, including scan status,
  candidate/fresh/deduped/registered counts, email notification status,
  GitHub run metadata, artifact path, and source SHA.

## Nodes

1. `candidate_scan` / Sudden mover candidate scan:
   `scripts/pipeline/candidates/sudden_movers_scanner.py`, invoked by
   `scripts/pipeline/sudden_movers_card_anchor.py`.
2. `card_anchor_bridge` / Default-off FOR card anchor bridge:
   `scripts/pipeline/sudden_movers_card_anchor.py`.
3. `scan_result_artifact` / Rapid-change scan evidence artifact:
   GitHub Actions upload artifact
   `forensic-rapid-change-scan-${{ github.run_number }}`.

## Boundary Rules

- `scripts/pipeline/candidates/sudden_movers_scanner.py` is a candidate node.
  It returns a structured candidate envelope from CoinMarketCap data and does
  not register DB rows, send email, or publish reports.
- `scripts/pipeline/sudden_movers_card_anchor.py` is the current workflow
  runtime. It converts candidate envelopes into FOR card-anchor and human
  source handoff contracts. It remains default-off for writes.
- `_legacy/pipeline/scan_forensic.py` remains the legacy registration contract
  for `forensic_triggers`, `project_reports` `coming_soon` rows, and alert
  email behavior. The current workflow in this checkout does not invoke it.
- `for-report-publishing` remains responsible for Slide/FOR intake, report
  synthesis/localization, approval, and website publishing after a FOR source
  and slide asset exist.

## Reconciliation Notes

BCE-1916 reconciled this page with the executable manifest because the rapid
change scan was not represented in `pipelines/bcelab-runtime-pipelines.json`.
The active checkout at SHA `3fbef7a` contains a workflow_dispatch-only
`forensic-rapid-change-scan.yml` that invokes the default-off sudden movers
bridge, while the source issue referenced production-main behavior that invoked
the legacy scanner on a schedule. Treat that as a deployment/runtime-state
difference when diagnosing BCE-1915: verify the running code SHA before
reporting either path as the active production root cause.

BCE-1918 updated the legacy scanner alert path so registered `coming_soon`
alerts are notification-required: the scanner writes `email_required` and
`email_result` into the JSON output artifact, logs failure detail, and exits
nonzero when required alert email delivery fails.

BCE-1917 added durable Supabase telemetry for the current rapid-change runtime
itself. The telemetry records disabled/skipped, successful, and failed bridge
outcomes even though card-anchor writes remain default-off; the email result is
recorded as `not_applicable` for this runtime because it does not invoke the
legacy email registration path.

BCE-1919 wired the default-off bridge workflow to pass Supabase telemetry
secrets and aligned the telemetry row shape with the deployed Supabase
`pipeline_runs` constraints. A workflow_dispatch dry run on branch
`bce-1919-forensic-telemetry-secrets` produced GitHub run `25962140028` at SHA
`8cf9642d456ef04fe3a74aedb453b8265e056796`, artifact
`scripts/pipeline/output/sudden_movers_card_anchor_25962140028.json`, one
`pipeline_runs` row, three `pipeline_node_runs` rows, and one `pipeline_events`
row for pipeline key `forensic-rapid-change-scan`.
