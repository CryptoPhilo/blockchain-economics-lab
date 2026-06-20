# Drive Analysis Markdown Summary Candidate

Manifest key: `analysis-md-summary-candidate`
Paperclip pipeline: `Drive Analysis Markdown Summary Candidate`
Owner: DataPlatformEngineer
Status: candidate
Last reconciliation: 2026-06-20

## Operating Definition

This candidate pipeline evaluates Drive analysis Markdown as a pre-publication
source for report card summaries and `Investment View` copy. It is not an active
replacement for the ECON/MAT/FOR slide publishing pipelines.

- Active candidate input: Google Drive `analysis2/{ECON,MAT,FOR}` Markdown, or
  a development-only local `--source-path`.
- Legacy candidate input: Google Drive `analysis/{ECON,MAT,FOR}` only when
  `--drive-root-scope legacy` or `all` is explicitly selected.
- Runtime entrypoint: `scripts/pipeline/analysis_md_summary_candidate.py`.
- Operator command shape:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug solana --drive-root-scope active --dry-run`.
- Paperclip local agent apply shape:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug solana --drive-root-scope active --agent-output-json <paperclip-agent-output.json> --require-agent-output`.
- Production write policy: default off. The candidate entrypoint must not write
  `project_reports` or publish website-visible content. `report_summary_jobs`
  writes require `--dry-run` to be omitted and still remain candidate records
  until a separate remote approval authorizes promotion.
- LLM boundary: Paperclip local agents generate the summary JSON. This pipeline
  validates and persists that agent output; it must not call an LLM provider API
  directly from GitHub Actions or pipeline scripts.
- Telemetry state store: Supabase `pipeline_runs`, `pipeline_node_runs`, and
  `pipeline_events` under `pipeline_name=analysis-md-summary-candidate`.

## Candidate Contract

- Source identity is provenance: `drive:{driveFileId}:{revisionId}` when Drive
  revision identity exists, otherwise `sha256:{normalized_markdown_sha256}`.
- Candidate job idempotency is keyed by `reportCode + reportSlug + locale +
  driveFileId + revision/hash + promptVersion + schemaVersion`. Duplicate
  `idempotency_key` rows are skipped unless `--force` is set, in which case the
  existing candidate job is updated. `source_identity` remains indexed only for
  provenance and lookup.
- Candidate persistence uses `report_summary_jobs`; `project_reports` alone is
  not sufficient for pre-approval LLM metadata such as source revision/hash,
  summarizer model, prompt/schema version, generated timestamp, validation
  status, candidate patch, and failed validation artifacts.
- Summary Authority Gate persistence adds `authority_state`, `authority_mode`,
  locale-aware `idempotency_key`, promotion audit fields, and
  `report_summary_promotion_locks`. The allowed state machine is
  `detected -> llm_candidate -> validation_failed | validation_passed -> promotion_pending -> promoted | rejected | fallback_script`.
- Authority modes are `legacy_script`, `llm_candidate`, and `llm_active`.
  `legacy_script` and `llm_candidate` retain the legacy active
  `project_reports` summary; only `llm_active` may promote a validation-passed
  candidate through the gate.
- LLM payloads must include `summary_by_lang` and `marketing_by_lang` for all
  seven locales (`ko`, `en`, `fr`, `es`, `de`, `ja`, `zh`), source evidence,
  and card-quality-safe text. Schema, missing-language, length, forbidden
  pattern, script mismatch, and source-grounding failures block candidate upsert
  as ready.
- Valid candidate patches reuse `marketing_content_pipeline.py` Markdown parsing,
  card summary quality gates, and `card_summary_v2` provenance.

## Nodes

1. `analysis_md_source_scan` / Drive analysis Markdown scan:
   `scripts/pipeline/analysis_md_summary_candidate.py`.
2. `summary_candidate_generation` / Paperclip local agent summary generation:
   local Paperclip agent run against the selected Drive Markdown source. The
   agent writes schema-conformant JSON for ingestion via `--agent-output-json`.
3. `candidate_validation` / Schema, language, quality, and grounding validation:
   shared card quality gates plus candidate-specific evidence checks.
4. `candidate_job_upsert` / Default-off report summary job upsert:
   Supabase `report_summary_jobs` when not in dry-run mode.
5. `summary_authority_gate` / Default-off candidate promotion, rejection, or
   fallback:
   `scripts/pipeline/summary_authority_gate.py`.

## Summary Authority Gate

- Runtime command shape:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id <uuid> --authority-mode llm_active --write`.
- Default behavior is dry-run. Omitting `--write` must not update
  `project_reports`, `report_summary_jobs`, locks, or telemetry.
- Promotion lock scope is `project_slug/report_type/locale`; only one active
  promotion can run for that scope at a time.
- Validation-failed candidates cannot be promoted and must not erase or
  overwrite legacy active summaries.
- Promotion/rejection/fallback emits `pipeline_events` under the
  `analysis-md-summary-candidate` pipeline contract.

## BCE-2000 Candidate Boundary

BCE-2000 adds a change-request/candidate path only. It does not change the active
`Slide2/*` PDF operating input, GitHub Actions cadence, approval gate, or
website publishing contract for `econ-report-publishing`,
`mat-report-publishing`, or `for-report-publishing`.

## BCE-2005 Remote Migration/Deploy Evidence (Blocked)

- Workspace: `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
- Current branch SHA when analyzed: `2a25add` (`HEAD` on `codex/fix-exchange-production-regressions`)
- Migration contract added for authority-gate tables/functions:
  - `supabase/migrations/20260620111400_add_summary_authority_gate.sql`
    - Adds `report_summary_jobs.authority_state`, `authority_mode`, promotion
      audit fields, and `report_summary_promotion_locks`
    - Adds PostgreSQL RPC `public.promote_report_summary_job(...)`
- Remote migration workflow path:
  - `.github/workflows/db-migration.yml`
  - Triggers on `supabase/migrations/**` changes or manual dispatch
  - Applies migrations with `supabase db push` in `environment: production`
- Deployment workflow path:
  - `.github/workflows/production-deploy.yml`
  - Verifies pipeline manifests/runtime checks before production deploy
  - Enforces `expected_branch` / optional `expected_commit` evidence in inputs
- Summary gate write path remains default-off:
  - `scripts/pipeline/summary_authority_gate.py` only persists on `--write`
  - Tests assert lock/rejection/promotion transitions in
    `scripts/pipeline/test_summary_authority_gate.py`
- 2026-06-20 `local-board` executed required remote steps on branch `codex/fix-exchange-production-regressions` commit `2a25add8416211029725d887ab882ca63e638364` (Board approval `f969099e-589f-4dc6-8e46-49aaac9e1c59`).
- Remote migration attempt:
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857395766
  - Final result: failed (`Apply Migrations` / `supabase db push`)
  - Failure reason: remote migration history contains `202604...` versions that are not present in current branch `supabase/migrations` directory, so `supabase db push` aborted.
  - Recovery issue opened: `BCE-2006` (Supabase migration history mismatch / fix authority gate migration application failure)
- Production deploy attempt:
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857395760
  - `Verify Deployment Evidence` job: success (`npm ci`, `verify:pipeline`, `verify:runtime-pipelines`, `tsc`, tests, build)
  - Vercel deploy: success (`https://blockchain-economics-hhllxrvk3-michael-zhangs-projects-df54ac7d.vercel.app`)
  - Aliased domain: `https://www.bcelab.xyz`
  - Final result: failed (`Verify Top500 and exchange regression gates`)
  - Failure item: Top500 page includes Bitcoin row, CMC rank, ECON badge, MAT badge
  - Passed item: exchange list API / Binance listing API / Binance exchange page Bitcoin row/rank/ECON/MAT badge
  - Recovery issue opened: `BCE-2007` (Top500 regression gate failure after production deploy)
- Resolution status snapshot:
  - At 2026-06-20 11:42 KST, BCE-2005 remained `blocked`.
  - Latest `BCE-2006` update:
    - Repo-side migration compatibility fix was pushed on branch `codex/fix-exchange-production-regressions` at commit `6bc8302`.
    - Migration rerun succeeded at: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857730221
      - The original “remote-only version blocker” is cleared.
      - Supabase now requests an explicit decision for earlier local April migrations before the latest remote migration.
    - Board approval `35a8e2b7-6813-45ab-af09-4bfb00a2570b` approved the metadata-only
      `supabase migration repair --status applied` path and rollback guidance.
    - At 11:42 KST, `BCE-2006` was blocked on valid GitHub Actions
      dispatch/execution credentials for the approved remote repair path; this
      agent's local `gh` credential returned HTTP 401 on Actions API calls during
      the continuation heartbeat.
  - `BCE-2007` has been resolved:
    - Root-cause fix commit: `c5dd9fe34df0da1eae4047ed662312150220fc3c`
    - Deployment branch/SHA: `codex/fix-exchange-production-regressions@6bc83027e19f1336e78de035295f28ab4e77086a`
    - Production deploy run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857785244
    - Deploy job: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857785244/job/82448388296
    - Vercel URL: https://blockchain-economics-5e4fztf4h-michael-zhangs-projects-df54ac7d.vercel.app
    - Direct alias validation passed (`BCE_REGRESSION_BASE_URL=https://bcelab.xyz npm run verify:production-regressions`) and browser DOM check confirms Bitcoin row/CMC #1/ECON/MAT.
    - Workflow evidence: `Workflow gate passed: Verify Top500 and exchange regression gates`
- Next step after `BCE-2006` + `BCE-2007` resolution:
    - rerun remote migration and production-equivalent E2E on deploy path,
    - attach successful run IDs proving migration success and production gate pass,
    - then close BCE-2005.

- Current status after approved BCE-2006 recovery:
  - Migration recovery is now complete and verified (`BCE-2006` blocker cleared
    in `27860631382` and `27860660544`).
  - Production-equivalent deploy evidence has been produced:
    - https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860761456
    - Head SHA: `35fa6cfa1129ce0453cd40df9cd6a5ecb600fc9b`
    - `Verify Deployment Evidence`: success
    - `Deploy Production`: success
  - `27860761456` includes successful run and rerun evidence after migration:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860688271
  - Migration/deploy evidence path is now satisfied:
    - migration: `27860631382`, `27860660544`
    - deploy/E2E: `27860761456`
  - PR for the production changes was merged:
    - https://github.com/CryptoPhilo/blockchain-economics-lab/pull/242
    - branch `codex/analysis-summary-gate-main` @ `288784acd231ad36c6bbc5f8083bdf49caa1abbe`
    - merge commit `06406aba7ad039718659fd0c66fcccd1ad170c2a`
    - superseded PR #241 was closed.
  - Merge was performed with CEO/operator waiver evidence because no non-author
    GitHub reviewer was available:
    - Paperclip approval `7b7ad020-6ac9-430f-bcc0-16da1e386720`
    - PR #242 Release Gate records the waiver.
  - Migration/e2e evidence is complete, but `BCE-2005` is still blocked until a
    Paperclip local agent produces schema-conformant summary JSON and candidate
    ingestion can produce a valid job plus gate dry-run evidence.
  - Post-merge workflow evidence:
    - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27861381155
    - Mode: `apply`, report type: `econ`, slug: `humanity-protocol`, drive scope: `all`, gate authority mode: `llm_candidate`
    - Result: failed in `Generate candidate` with exit code 2 because the candidate was invalid.
    - Candidate job row was inserted as validation-failed only:
      `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`.
    - Artifact:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27861381155/artifacts/7762372421
    - Validation failures included missing `marketing_by_lang` languages and
      overlong/raw-format summaries. Gate dry-run did not execute because no
      valid candidate existed.
  - Runtime secret audit:
    - Repository secrets include Supabase and Google Drive credentials.
    - The previous design incorrectly required `BCE_ANALYSIS_MD_LLM_ENDPOINT`,
      `BCE_ANALYSIS_MD_LLM_BEARER_TOKEN`, and
      `BCE_ANALYSIS_MD_SUMMARY_MODEL`.
    - That was the wrong boundary for this request: summary generation should
      be performed by a Paperclip local agent using its local LLM runtime, and
      this pipeline should only validate and persist the agent output.
  - Required closeout evidence after Paperclip agent apply setup:
    - Paperclip local agent run that records the selected Drive source and
      writes schema-conformant summary JSON.
    - candidate ingestion with `--agent-output-json` and
      `--require-agent-output`.
    - candidate `report_summary_jobs` artifacts/logs and
      `Summary Authority Gate` dry-run output showing `dry_run=true` and no
      `project_reports` writes.
  - PR #243 (`0c2a725137989bd0100333d4e475808e70fef913`) was a safety patch
    that prevented deterministic fallback writes in apply mode, but its
    endpoint-secret requirement is superseded by the Paperclip agent output
    contract.
  - PR #244 opened:
    - https://github.com/CryptoPhilo/blockchain-economics-lab/pull/244
    - removes direct GitHub Actions LLM API call / secret dependency in apply mode;
      `--agent-output-json` is now the required input path.
    - Validation checks passed:
      - Python pipeline tests: `15 passed`
      - workflow YAML parse: passed
      - `npm run verify:runtime-pipelines`: passed
      - `npm run verify:pipeline`: passed
    - Remaining before close:
      - PR #244 must pass checks and merge.
      - Paperclip local agent must generate schema-conformant summary JSON from
        Drive analysis markdown and provide it via `--agent-output-json`.
      - Post-merge run must collect valid `report_summary_jobs` row and
        `Summary Authority Gate` dry-run evidence (`dry_run=true`, no
        `project_reports` writes).
  - 2026-06-20 run `27861610008` remains useful as negative evidence: it
    prevented runtime or DB candidate writes when the summary-generation
    boundary was unavailable.
  - BCE-2009 endpoint-secret blocker is superseded. The remaining blocker is a
    Paperclip-local apply run that produces and ingests agent output JSON, then
    runs the Summary Authority Gate in dry-run mode.
  - Keep BCE-2005 blocked until Paperclip agent output ingestion produces valid
    `report_summary_jobs` rows and gate dry-run evidence.
  - Pipeline state wiki update for this checkpoint was pushed in commit `5db974c`.

### BCE-2005 additional migration recovery evidence (2026-06-20 13:35 KST, latest)

- Workspace/SHA used: `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab` at `6bc8302`.
- Remote execution ref: `codex/fix-exchange-production-regressions@e1b3fc8`.
- Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860177261
- `supabase migration repair --status applied 20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429`
  - approved and executed successfully
  - log: `Repaired migration history: [20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429] => applied`
- `supabase db push` still fails after repair:
  - Supabase rejects repaired short-date versions as non-matching local migration files
  - suggests reverting at least `20260409 20260412 20260414 20260418 20260427`
- Related concurrent run / regression:
  - https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860170061
  - command path regressed to pre-repair local-insertion blocker
- New board approval requested for revised metadata repair path:
  - `7b7ad020-6ac9-430f-bcc0-16da1e386720`
- Blocker status:
  - `BCE-2006` remains blocked pending board-approved revised repair/rollback direction and a successful `supabase db push`.

### BCE-2005 follow-up recovery evidence (2026-06-20 13:40 KST)

- Auditable workflow support commit added for Actions-based repair on branch
  `codex/fix-exchange-production-regressions`:
  - `7d0be87bae6d53a25e59182649f97ead04014e8c`
- Revised no-op/include-all attempt:
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860351179
  - `supabase migration repair --status applied 20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429` succeeded
    (log: `Repaired migration history: [...] => applied`)
  - `supabase db push --include-all` still failed:
    - `Remote migration versions not found in local migrations directory`
    - suggested reverting `20260409 20260412 20260414 20260418 20260427`
- Approved rollback execution:
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860406003
  - Rollback evidence:
    - `Repaired migration history: [20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429] => reverted`
- Post-rollback state:
  - Workflow again fails at the original `supabase db push` blocker (oldest local
    April migrations still required before last remote migration).
- Current conclusion:
  - No successful production migration application for Summary Authority Gate has occurred in these runs.
  - BCE-2006 and thus BCE-2005 remain blocked pending board-approved revised metadata
    repair/rollback (approval: `7b7ad020-6ac9-430f-bcc0-16da1e386720`) and a successful `supabase db push`.

## BCE-2006 Supabase Migration History Recovery

- Workspace: `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
- Diagnosis SHA: `2a25add`
- Failed run reviewed:
  - https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857395766
  - Failed at `supabase db push` on 2026-06-20 02:25 UTC.
- Exact Supabase CLI blocker:
  - Remote migration versions were present in production history but absent from
    local `supabase/migrations`.
  - Missing local versions:
    `20260408162734`, `20260408181632`, `20260408182202`,
    `20260409015605`, `20260409020123`, `20260409020317`,
    `20260409020850`, `20260409024008`, `20260409062305`,
    `20260409062417`, `20260409062817`, `20260412030602`,
    `20260412030614`, `20260412040231`, `20260412042509`,
    `20260412053802`, `20260412061311`, `20260412113418`,
    `20260412114712`, `20260412115731`, `20260412121557`,
    `20260412130501`, `20260414045616`, `20260414052828`,
    `20260414053057`, `20260414062525`, `20260414233936`,
    `20260414235633`, `20260415061008`, `20260415061036`,
    `20260415092004`, `20260416022513`, `20260416050723`,
    `20260416062634`, `20260416062714`, `20260416073329`,
    `20260418101155`, `20260418151054`, `20260422144324`,
    `20260422234642`, `20260427222305`, `20260430083533`.
- Root cause:
  - Production Supabase history contains timestamped April 2026 migrations that
    are not present in any local branch/ref inspected in this checkout.
  - The current branch also introduced two new date-only `20260620_*`
    migrations; those were renamed to timestamped versions so the new Summary
    Authority Gate migrations have stable ordering and unique versions:
    - `supabase/migrations/20260620111300_add_report_summary_jobs.sql`
    - `supabase/migrations/20260620111400_add_summary_authority_gate.sql`
- Recovery action taken in repo:
  - Added no-op `*_remote_history_compat.sql` marker migrations for each exact
    remote-only version reported by Supabase CLI.
  - No `supabase migration repair`, `supabase db pull`, or production DB write
    was executed locally.
- Recovery rerun:
  - Commit/ref: `a209daf` on `codex/fix-exchange-production-regressions`
  - Run: https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27857730221
  - Result: failed after clearing the first remote-only-version blocker.
  - New Supabase CLI blocker: local migrations would need insertion before the
    last remote migration:
    - `20260409_add_tracked_projects_and_project_subscriptions.sql`
    - `20260412_add_referral_subscriber_newsletter.sql`
    - `20260412_add_rls_core_tables.sql`
    - `20260414_add_coming_soon_and_forensic_trigger.sql`
    - `20260417_add_report_timestamp_trigger.sql`
    - `20260418_add_cmc_id_to_tracked_projects.sql`
    - `20260418_fix_rls_for_coming_soon_reports.sql`
    - `20260427_add_aliases_to_tracked_projects.sql`
    - `20260428_add_slide_html_urls_by_lang.sql`
    - `20260429_backfill_project_reports_language_support.sql`
- Remaining operating step:
  - Do not rerun with `supabase db push --include-all`; these files include
    non-idempotent schema creation and may duplicate production objects.
  - Board approval `35a8e2b7-6813-45ab-af09-4bfb00a2570b` approved a
    metadata-only repair that marks the listed local April versions as applied
    in Supabase migration history, with rollback by marking the same versions
    reverted.
  - A runner/operator with valid GitHub Actions execution credentials must run
    the approved repair remotely, then rerun `.github/workflows/db-migration.yml`
    from `codex/fix-exchange-production-regressions@6bc8302` so only genuinely
    pending migrations, including the Summary Authority Gate, are applied.
  - 2026-06-20 CTO follow-up:
    - Current CTO heartbeat verified the same workspace at SHA `6bc8302`.
    - `gh auth status` now shows a valid `workflow`-scoped GitHub credential,
      but `.github/workflows/db-migration.yml` still exposes only
      `supabase db push`; it has no approved `supabase migration repair`
      execution path.
    - Remote repair execution has been delegated to DataPlatformEngineer via
      Paperclip so the repair surface, execution evidence, rerun URL, and wiki
      update are handled as an auditable production operation.
  - 2026-06-20 13:28 KST DataPlatformEngineer follow-up:
    - Workspace verified:
      `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
      at SHA `6bc8302` before execution; remote execution used approved
      follow-up SHA `e1b3fc8` on branch `codex/fix-exchange-production-regressions`.
    - Remote workflow repair surface:
      `.github/workflows/db-migration.yml` gained manual-dispatch inputs
      `repair_status` and `repair_versions`, runs under `environment:
      production`, links Supabase from production secrets, runs
      `supabase migration repair` before `supabase db push`, and logs the exact
      command inputs.
    - Remote repair/db-push run:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860177261
    - Repair step result: success. Log evidence:
      `Repaired migration history: [20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429] => applied`.
    - Apply Migrations result: failed. New Supabase CLI blocker:
      remote migration versions are now present in history but not accepted as
      matching local migration files for at least
      `20260409`, `20260412`, `20260414`, `20260418`, and `20260427`.
      CLI suggested rollback:
      `supabase migration repair --status reverted 20260409 20260412 20260414 20260418 20260427`.
    - A concurrent earlier remote run
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860170061
      executed the rollback form for the full approved version set, then failed
      `supabase db push` with the prior "local migration files to be inserted
      before the last migration" blocker. The later run above re-applied the
      approved repair.
    - No additional repair variant was executed because the approved command
      succeeded but produced a new reconciliation blocker; any alternative
      version identifiers or rollback/apply sequence should be explicitly
      approved before another production migration-history write.
  - 2026-06-20 board follow-up:
    - Auditable GitHub Actions repair support is present on
      `codex/fix-exchange-production-regressions` at commit
      `7d0be87bae6d53a25e59182649f97ead04014e8c`.
    - Revised no-op/include-all attempt:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860351179
      - `supabase migration repair --status applied 20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429`
        succeeded and logged `=> applied`.
      - `supabase db push --include-all` still failed with
        `Remote migration versions not found in local migrations directory` and
        suggested reverting `20260409`, `20260412`, `20260414`, `20260418`,
        and `20260427`.
    - Approved rollback run:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860406003
      - Rollback evidence:
        `Repaired migration history: [20260409 20260412 20260414 20260417 20260418 20260427 20260428 20260429] => reverted`.
      - After rollback, the workflow returned to the original blocker: normal
        `supabase db push` refuses to insert older local April migrations before
        the last remote migration.
    - No successful production Summary Authority Gate migration application has
      occurred in these runs.
    - Further automatic retries are not safe without revised board approval
      `7b7ad020-6ac9-430f-bcc0-16da1e386720` or a DB-owner migration-history
      rebaseline via `supabase db pull` / manual Supabase audit.
  - 2026-06-20 safety cleanup:
    - Removed failed experimental workflow inputs `skip_local_versions` and
      `noop_include_versions` after confirming they did not resolve Supabase
      history reconciliation and could invite unsafe reuse.
    - Cleanup commits pushed to `codex/fix-exchange-production-regressions`:
      - `013fb74` reverts `BCE-2006 no-op legacy migrations for production push`.
      - `f4b6b41` reverts `BCE-2006 skip obsolete local migrations in production push`.
    - Current branch HEAD verified locally and remotely:
      `f4b6b41a519ef83e1da50658e4790e05e52674d3`.
    - `.github/workflows/db-migration.yml` now retains only the approved repair
      execution surface: `repair_status` + `repair_versions`, then normal
      `supabase db push`.
    - `BCE-2006` remains blocked because normal `db push` still fails after
      rollback with the April local-migration insertion blocker. Pending
      decision remains board approval `7b7ad020-6ac9-430f-bcc0-16da1e386720`
      or a DB-owner migration-history rebaseline / manual Supabase audit.
  - 2026-06-20 13:50 KST approved recovery completion:
    - Board approval `7b7ad020-6ac9-430f-bcc0-16da1e386720` approved the
      revised remote-only repair/rebaseline path.
    - Repo compatibility commits on `codex/fix-exchange-production-regressions`
      archived obsolete local migrations that were already represented in
      production history:
      - `3d6d225` archives short-date April local migrations.
      - `fb9d8ef` archives pre-summary migrations already applied in production.
      - `65880c5` adds a read-only `supabase migration list --linked` audit step
        before `supabase db push`.
    - Migration application run:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860631382
      - Ref/SHA: `codex/fix-exchange-production-regressions@fb9d8ef0efd41fbe3432bc30309fce848624e8fb`
      - Result: success.
      - `supabase db push` applied:
        - `20260620111300_add_report_summary_jobs.sql`
        - `20260620111400_add_summary_authority_gate.sql`
      - Log evidence: `Finished supabase db push.`
    - Audit rerun:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860660544
      - Ref/SHA: `codex/fix-exchange-production-regressions@65880c5e918b3e0e6f2f8f22ea46d07947273d1e`
      - Result: success.
      - `supabase migration list --linked` shows both local and remote entries
        for `20260620111300` and `20260620111400`.
      - `supabase db push` result: `Remote database is up to date.`
    - `BCE-2006` migration blocker is cleared. Next `BCE-2005` step is to run
      the production-equivalent deploy/E2E evidence path and close remaining
      blockers only after that evidence passes.
    - Production-equivalent deploy/E2E run:
      https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27860761456
      - Ref/SHA: `codex/fix-exchange-production-regressions@35fa6cfa1129ce0453cd40df9cd6a5ecb600fc9b`
      - Result: success.
      - Verification passed: `npm ci`, `npm run verify:pipeline`,
        `npm run verify:runtime-pipelines`, `npx tsc --noEmit`, `npm test`,
        and `npm run build`.
      - Vercel production URL:
        `https://blockchain-economics-bec9ql0oq-michael-zhangs-projects-df54ac7d.vercel.app`
      - Production regression gate passed against that URL, including Top500
        Bitcoin row/CMC rank/ECON badge/MAT badge and Binance exchange/listing
        API/page checks.
    - `BCE-2005` migration/deploy E2E evidence requirement is satisfied by the
      migration runs above plus production deploy run `27860761456`.

### BCE-2010 Paperclip Agent Boundary Correction (2026-06-20)

- Workspace/SHA used for diagnosis:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `b622168` before local runtime-adapter edits.
- Primary context checked before implementation:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Boundary correction:
  - The interim GitHub Models / remote LLM endpoint design was rejected as the
    wrong boundary for BCE-1999.
  - Summary generation belongs to the local Paperclip agent and its local LLM
    runtime.
  - `scripts/pipeline/analysis_md_summary_candidate.py` validates and persists
    Paperclip agent JSON output via `--agent-output-json`; it does not call
    remote LLM endpoints.
  - `.github/workflows/analysis-md-summary-candidate.yml` no longer injects LLM
    endpoint/model/token secrets. `apply` mode requires an explicit
    `agent_output_json` path and otherwise fails before candidate writes.
- Local verification:
  - `python3 -m pytest scripts/pipeline/test_analysis_md_summary_candidate.py`
    covers the Paperclip agent output ingestion contract.
- Remaining closeout evidence:
  - Run a Paperclip local agent on a selected Drive analysis Markdown source and
    capture schema-conformant JSON output.
  - Ingest that JSON with `--agent-output-json` and `--require-agent-output`.
  - Capture valid `report_summary_jobs` job evidence and Summary Authority Gate
    dry-run output showing `dry_run=true` and no `project_reports` write.
