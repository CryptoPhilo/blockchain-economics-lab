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
- Production write policy: default off. The candidate entrypoint must not write
  `project_reports` or publish website-visible content. `report_summary_jobs`
  writes require `--dry-run` to be omitted and still remain candidate records
  until a separate remote approval authorizes promotion.
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
2. `summary_candidate_generation` / LLM summary candidate generation:
   configured LLM endpoint or deterministic local dry-run fallback.
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
- Resolution status:
  - BCE-2005 remains `blocked` until both `BCE-2006` and `BCE-2007` are resolved.
  - After recovery, rerun migration + production-equivalent E2E and attach successful run IDs that include migration+deploy completion.

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
- Remaining operating step:
  - Rerun `.github/workflows/db-migration.yml` from the recovery commit/ref.
  - If `supabase db push` still requires history repair or schema pull, request
    board approval before any `supabase migration repair` or `supabase db pull`
    based recovery.
