# ECON Report Publishing

Manifest key: `econ-report-publishing`
Paperclip pipeline: `ECON Report Publishing`
Owner: CRO
Status: active
Last reconciliation: 2026-05-15

## Operating Definition

This pipeline publishes ECON slide reports for the Blockchain Economics Lab.

- Operating input: slide-form PDFs in Google Drive `Slide2/ECON`.
- Backfill input: historical PDFs in Google Drive `Slide/ECON`, only when the watcher is explicitly run with `--drive-root-scope legacy` or `all`.
- Source confirmation: Korean Markdown source in `analysis2/ECON` for operating runs; `analysis/ECON` is the legacy backfill source.
- Runtime: GitHub Actions workflow `.github/workflows/slide-pipeline-cron.yml`.
- Schedule: workflow cron `*/5 * * * *`, gated by the Supabase `pipeline_schedules` row for `slide-pipeline`; expected effective check interval is 30 minutes. Scheduled runs must enumerate the full active `Slide2/ECON` tree with `--drive-root-scope active` and rely on `_slide_processed.json` to skip unchanged files, not a modified-time lookback that can strand unprocessed PDFs after downtime.
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
  the BCE-1907 migration/backfill is required before remote production writes.

## BCE-1922 Report Cover URL Update

As of 2026-05-23, `website_publish` also produces a public first-page slide
cover image for homepage latest-report display. New ECON slide publishes upload
`slides/econ/{slug}/{version-or-latest}/{lang}-cover.jpg` and update the linked
`products.cover_image_url` when `project_reports.product_id` is present. Existing
rows use `scripts/backfill-report-cover-image-urls.ts` in dry-run first; apply is
reserved for the approved remote production-write path.

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

## BCE-1939 Semantic Insight Quality Gate

As of 2026-06-02, ECON card summaries and card-visible `Investment View` copy
must pass a semantic insight gate, not only a formatting safety gate.
`scripts/pipeline/marketing_content_pipeline.py` separates raw-format rejection
from report-type insight checks, rejects internal prompt/template fragments such
as `요청 템플릿` and `예상 가격 항목`, and refuses to persist raw source fallback
when no safe insight candidate exists.

The card summary provenance contract is `card_summary_v2`, with
`source_sentence_ids` recorded alongside source sentences. Direct post-publish
generation in `scripts/pipeline/watch_slides.py` passes project context into the
same gate used by dry-run/backfill execution.

## BCE-2000 Analysis Markdown Candidate Path

As of 2026-06-20, ECON has a default-off candidate path for Drive
`analysis2/ECON` Markdown summaries. The executable manifest key is
`analysis-md-summary-candidate`; runtime entrypoint is
`scripts/pipeline/analysis_md_summary_candidate.py`.

This is a change-request/candidate path only. It does not change the active
`Slide2/ECON` PDF operating input, `.github/workflows/slide-pipeline-cron.yml`
cadence, approval gate, or `project_reports` production publish contract.
Candidate metadata is stored in `report_summary_jobs` after the BCE-2000
migration and remains out of `project_reports` until separate remote approval.

### BCE-1933 Backfill Execution Evidence

As of 2026-06-01 16:35 KST, the approved remote backfill surface was exercised
from merged `main` commit `c94fbc09b8e57cd678aa2f00b67b8d252c2e8ade`.

Evidence:

- Dry-run:
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26741357754`
  completed successfully with `seen=8`, `matched=8`, `updated=0`, and sample
  slugs `awe-network`, `bitcoin`, `ethereum`, `starknet`, `vision-token`.
- Apply:
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26741467449`
  completed successfully with slug `bitcoin`, `seen=2`, `matched=2`,
  `updated=2`.
- Production URL verification confirmed the updated Bitcoin ECON/MAT card
  summary copy is visible on `/ko/projects/bitcoin` and
  `/ko/reports/bitcoin/econ`.
- Follow-up AWE ECON target-selection fix from PR #148 was deployed from merged
  `main` commit `7a10e2fba84eef8d9a6a04e813c27f732fd5b2ec` on 2026-06-02.
  Remote dry-run
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26791375107`
  completed with slug `awe-network`, report type `econ`, `seen=1`,
  `matched=1`, `updated=0`, `skipped=0`, and `quality_reasons=[]`.
  Remote apply
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26791423052`
  completed with the same scope, `seen=1`, `matched=1`, `updated=1`,
  `skipped=0`, and `quality_reasons=[]` for project report
  `b00f01a8-1ace-4751-b47a-22f6b165bb1a`.
- Production URL verification after the AWE ECON apply returned HTTP 200 for
  `/ko/projects/awe-network` and `/ko/reports/awe-network/econ`; the previous
  low-quality fragments `분석 목적은` and `온체인 state 매핑` were absent, and
  the new AWE ECON summary text containing `토큰 가치 포획 불명확성` was present.
- BCE-1947 production audit on 2026-06-03 found Banana For Scale ECON v2
  `project_reports` rows had no `card_summary_*`, `card_data.summary_by_lang`,
  or generic `card_data.summary`. Board approval
  `81ebbaf5-ca6d-42da-86b0-0428e03000da` authorized a scoped manual production
  patch because the Drive Markdown backfill source was not found. Four ECON v2
  rows (`ko`, `en`, `ja`, `zh`) were patched with `card_summary_v2` provenance
  under `card_data.summary_quality.source = approved_manual_patch`. Production
  verification confirmed `/ko/projects/banana-for-scale` renders the new ECON
  card summary. After-audit evidence:
  `scripts/pipeline/output/card_summary_coverage_audit_after_banana_patch.json`
  reported remaining selected project-card findings at 170.
- BCE-1947 follow-up release PR #156 generalized the card summary resolver,
  coverage audit, source selection, and multi-row persistence contract; it was
  merged at `8c825606d6e1d6526170cbbaaf5e6c276e19e90a`, passed main CI
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26929961332`,
  and deployed to Vercel production
  `https://vercel.com/michael-zhangs-projects-df54ac7d/blockchain-economics-lab/A4waoFwD46WdNRHFQASnSFfMBXDP`.
  A 31-slug `report-card-summary-backfill` `mode=apply` batch then completed
  successfully. PR #157 fixed the remaining logic-level cases (Lido DAO alias,
  Korean-row target constraint, and deterministic fallbacks for Berachain and
  Canton), merged at `34f164b9e5a1773507e9fd6cc31d959ba7a23b04`, passed main
  CI `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26935674801`,
  and deployed to Vercel production
  `https://vercel.com/michael-zhangs-projects-df54ac7d/blockchain-economics-lab/9hG53RvWYaip3s1DtpFzRtmXNT3E`.
  Six post-PR #157 apply runs succeeded for `injective`
  (`26935838970`), `canton-network` (`26935840099`), `flare`
  (`26935841411`), `lido-dao` (`26935842648`), `berachain`
  (`26935843707`), and `bnb` (`26935844807`). Production audit moved from
  `row_findings=212`, `selected=178` before apply to `row_findings=109`,
  `selected=75` after PR #157 plus the six applies. The remaining selected-card
  findings are not logic failures; they are source-availability misses where
  the current Drive analysis Markdown source cannot be found.

### BCE-1910 Production DB Evidence

As of 2026-05-15 21:26 KST, the production DB migration
`supabase/migrations/20260515_add_report_source_identity_and_latest_contract.sql`
was applied through GitHub Actions run
`https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/25917698841`
using board-approved expected commit
`e33f14e31c0dbab1780615acfade3fb6551b1d70`.

Evidence:

- Preflight production `project_reports`: 920 rows; `source_identity` column was
  absent; duplicate `is_latest=true` groups: 0.
- Migration run: `workflow_dispatch` on branch
  `bce-1909-bce-1906-clean-release`; job `Apply selected SQL migration`
  completed successfully and executed the selected SQL file.
- Postflight production `project_reports`: `source_*` columns queryable;
  `source_identity` non-null rows: 640; `source_file_id` non-null rows: 640;
  duplicate `source_identity` groups: 0; duplicate `is_latest=true` groups: 0.
