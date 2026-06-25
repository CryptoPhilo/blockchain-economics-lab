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
- Routine polling excludes Drive source identities that already have a
  `report_summary_jobs.authority_state=promoted` row before applying the
  single-candidate `--limit`. Operator/manual reprocessing may use `--force` to
  include a promoted source intentionally; normal routine polling omits
  `--force` and no-ops when no unpromoted source remains.
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

### BCE-2193 Website Publication Contract for Summary-Only Promoted Rows (2026-06-25 13:39 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d83a1fe` before local changes.
- Primary context checked before implementation:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Issue:
  RealLink ECON job `b9117ac6-dfb6-4297-8317-3e4dead2c7ac` is promoted to
  project report `f60ecf21-6fb6-4b2b-8595-0b17a2d7f636`, but the target row is
  `status=coming_soon` and summary-only with no `slide_html_urls_by_lang`.
  Existing website code queried only `published`/`in_review` rows on project
  pages and required slide HTML on report pages, so promoted metadata was not
  visible.
- Chosen publication contract:
  `project_reports.status=coming_soon` remains hidden by default. A coming-soon
  row becomes website-visible only when `card_data.summary_authority.mode` is
  `llm_active` and localized summary metadata exists for the requested locale.
  This preserves the existing rule that ordinary PDF-only or pre-render slide
  rows remain `locale_pending`, while Summary Authority Gate promoted
  summary-only rows can expose summary and Investment View copy.
- Code changes:
  - `src/app/[locale]/projects/[slug]/page.tsx` now queries
    `published`, `coming_soon`, and `in_review` rows, then filters
    coming-soon rows to active summary-authority rows only.
  - `src/lib/report-locale.ts` treats active summary-authority metadata as
    locale support for report card selection.
  - `src/app/[locale]/reports/[slug]/_components/slide-report-utils.ts`
    treats active summary-authority metadata as an available locale report even
    without slide HTML.
- Local verification:
  - `npm test -- --runTestsByPath 'src/app/[locale]/projects/[slug]/page.test.ts' 'src/app/[locale]/reports/[slug]/_components/SlideReportPage.test.ts' src/lib/report-locale.test.ts --runInBand`
    passed (`76 passed`).
  - `npx tsc --noEmit` passed.
  - `npm run verify:pipeline` passed.
  - `npm run verify:runtime-pipelines` passed.
  - `npm run lint` passed with existing warnings only.
  - `npm run build` passed.
- Deployment status:
  local implementation and verification are complete. Production deployment and
  live RealLink ECON page checks still need the guarded `Production Deploy`
  workflow for BCE-2193 before BCE-2191 can close.

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
  - Migration/e2e evidence is complete. `BCE-2011` paperclip-agent ingestion and dry-run evidence has now been collected (job `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`, `dry_run=true`, `wrote_project_report=false`).
  - `BCE-2005` currently remains blocked pending explicit workflow execution/approval
    for write-mode promotion.
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
  - PR #244 merged:
    - https://github.com/CryptoPhilo/blockchain-economics-lab/pull/244
    - Head SHA: `337b080234fc2cf332ca345986be09ab76bc1d47`
    - Merge commit: `d98fc27628bfdd8e3e696d75f9a2049d790bf346`
    - Merged at: `2026-06-20T06:02:25Z`
    - Merged at: 2026-06-20 15:02 KST
    - CI status: all required checks passed before merge.
    - removes direct GitHub Actions LLM API call / secret dependency in apply mode;
      `--agent-output-json` is now the required input path.
    - Validation checks passed:
      - Python pipeline tests: `15 passed`
      - workflow YAML parse: passed
      - `npm run verify:runtime-pipelines`: passed
      - `npm run verify:pipeline`: passed
  - Remaining before close:
    - Paperclip local agent + `--agent-output-json` evidence is completed in `BCE-2011`.
    - Production promotion remains pending separate explicit approval before any
      `--write` gate invocation.
  - 2026-06-20 run `27861610008` remains useful as negative evidence: it
    prevented runtime or DB candidate writes when the summary-generation
    boundary was unavailable.
  - BCE-2009 endpoint-secret blocker is superseded by the Paperclip-local
    agent output contract and BCE-2011 ingestion evidence.
  - Keep BCE-2005 blocked until explicit workflow execution/approval for
    write-mode promotion is completed.
  - Pipeline state wiki update for this checkpoint was pushed in commit `5db974c`.

### BCE-2011 Paperclip Local Agent Ingestion Evidence (2026-06-20 15:09 KST)

- Workspace/SHA used: `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab` at `337b080`.
- Branch: `codex/paperclip-agent-summary-source`.
- Routine: `CRO Analysis MD Summary JSON Ingestion Routine`
  (`50aff64a-3178-4af7-b67b-49bf4521aedb`).
- Linked issue status: BCE-2011 `done`.
- Source: Google Drive Markdown `TAC 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1_beEKEvrOiCCcdtnXndJ3to6eiQ2pjZl:0B8HYgThT3NByeThlRHAwajFSaWZQdFNnQjJZREZ5MUdKN1FzPQ`.
- Agent output JSON:
  `scripts/pipeline/fixtures/bce-2010-humanity-protocol-agent-output.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug humanity-protocol --drive-root-scope all --agent-output-json scripts/pipeline/fixtures/bce-2010-humanity-protocol-agent-output.json --require-agent-output --limit 1 --force`.
- Candidate ingest result:
  - status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`

  - job id: `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`
  - artifact:
    `scripts/pipeline/output/analysis_md_summary_candidate_econ_humanity-protocol.json`
- Summary Authority Gate dry-run command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5532671b-87ea-4b6c-a72c-fc7ba6bf1d86 --authority-mode llm_candidate --actor "paperclip-routine:CRO:BCE-2011"`.
- Gate dry-run result:
  - `dry_run=true`
  - action: `fallback`
  - state: `fallback_script`
  - reason: `legacy active summary retained`
  - `wrote_project_report=false`
- This satisfies the Paperclip-local JSON ingestion evidence for the candidate
  row and default-off gate dry-run. Production promotion remains separate and
  requires explicit approval before any `--write` gate invocation.

### BCE-2012 Immediate Publish Gate Attempt (2026-06-20 15:45 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `61b0ae6`.
- Board instruction update:
  `BCE-2012` should ignore the stale 06:30 dry-run wording and use the immediate
  publish path once candidate ingest is `valid` and a `job_id` is available.
- Candidate job reused from `BCE-2011`:
  `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`.
- Write gate command executed:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5532671b-87ea-4b6c-a72c-fc7ba6bf1d86 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2012" --write`.
- Result:
  - exit code: `1`
  - no `promote` result returned
  - no `wrote_project_report=true` evidence
  - no `project_report_id` returned
- Blocker:
  - Supabase RPC `public.promote_report_summary_job(...)` failed with
    PostgreSQL error `42883`: `operator does not exist: report_type = text`.
  - The deployed function compares `project_reports.report_type` to
    `v_job.report_type`; current production types require an explicit cast or a
    function signature/body fix before the authority gate can promote.
- Operational status:
  - `BCE-2012` must not be marked done under the board condition.
  - A DataPlatformEngineer/CTO hotfix is required for the promotion RPC, followed
    by rerunning the same `llm_active --write` command and verifying
    `action=promote`, `wrote_project_report=true`, and `project_report_id`.

### BCE-2013 Summary Authority Gate RPC Cast Hotfix (2026-06-20 15:48 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `d89bdc2` for diagnosis, then branch
  `codex/paperclip-agent-summary-source` hotfix commits.
- Primary context checked before implementation:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Hotfix:
  - Migration `supabase/migrations/20260620114500_fix_summary_authority_gate_report_type_cast.sql`
    replaces `public.promote_report_summary_job(...)`.
  - The target lookup now compares `project_reports.report_type::text` to
    `report_summary_jobs.report_type`, clearing PostgreSQL `42883`
    `operator does not exist: report_type = text`.
- Local verification:
  - `python3 -m pytest scripts/pipeline/test_summary_authority_gate.py`
    passed (`7 passed`).
- Remote DB application:
  - Initial selected-migration dispatch on hotfix SHA `702fe15` failed because
    the workflow entered a Supabase CLI history step while CLI setup was skipped.
  - Workflow guard fix pushed at `f053209`.
  - Selected SQL migration rerun succeeded:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27863351352
  - A preceding selected-migration run also succeeded on the same branch:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27863338650
- Promotion evidence:
  - Candidate job:
    `5532671b-87ea-4b6c-a72c-fc7ba6bf1d86`.
  - Promotion actor:
    `paperclip-routine:CRO:BCE-2012`.
  - DB state after hotfix:
    `authority_state=promoted`, `authority_mode=llm_active`,
    `promotion_decision=promote`, `promoted_project_report_id=87fcaaed-41d2-4fec-a907-1c8ba59e6767`.
  - Promotion timestamp:
    `2026-06-20T06:48:43.315601+00:00`.
  - Project report state:
    `project_reports.id=87fcaaed-41d2-4fec-a907-1c8ba59e6767`,
    `report_type=econ`, `language=ko`, `status=published`.
  - `card_data.summary_authority` records `mode=llm_active`, the candidate job
    id, idempotency key, source identity, and the same promotion timestamp.
  - Idempotent verification command:
    `python3 scripts/pipeline/summary_authority_gate.py --job-id 5532671b-87ea-4b6c-a72c-fc7ba6bf1d86 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2012" --write`
    returned `decision.action=noop`, `decision.state=promoted`,
    `project_report_id=87fcaaed-41d2-4fec-a907-1c8ba59e6767` because the job was
    already terminal after the successful promotion.
- Current status:
  - The Summary Authority Gate RPC report_type cast blocker is cleared.
  - BCE-2012 can proceed using the promoted project report evidence above.

### BCE-2130 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-23 16:41 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Meteora의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Source identity:
  `drive:14f6HvNzX85-zBu1Owz8fBDHrZuXuHaZW:0B8HYgThT3NByTCs5SmExbkl4K1FYNlRJbzhyV25jMCtKLytRPQ`.
- Source SHA-256:
  `f39f688a23976f668b26d6fbe78e08d48fb4e7633295fbf07ff77220e85aac34`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_meteora_bce2130.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_meteora.json`.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `meteora`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `bbbe8e1e-fa05-451a-8cdd-62ed9f2d5c00`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id bbbe8e1e-fa05-451a-8cdd-62ed9f2d5c00 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2130" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `7f444a0b-2441-4956-a9f7-7470ad5bd2b3`
  - promoted_at: `2026-06-23T07:41:03.374583+00:00`
- Project report verification:
  - `project_reports.id=7f444a0b-2441-4956-a9f7-7470ad5bd2b3`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=bbbe8e1e-fa05-451a-8cdd-62ed9f2d5c00`

### BCE-2131 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-23 17:07 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Meteora 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1pRIwA1LalWa2dbC7faqjmeW8jG4u_If3:0B8HYgThT3NByNGJSQUNLK0RNK0RXWFhVME9yb3BrWm1sYWtVPQ`.
- Source SHA-256:
  `b26172cd8cc0ed9ebe0224289562acef543607f954f538e9b8369ee71094903f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_meteora_bce2131.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_meteora.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `meteora`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `4c1a8b32-4ed7-4e71-8b7b-054b9b17666c`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 4c1a8b32-4ed7-4e71-8b7b-054b9b17666c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2131" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `d32a0c6f-8ace-49ba-83bd-a400a56c866f`
  - promoted_at: `2026-06-23T08:07:34.547592+00:00`
- Project report verification:
  - `project_reports.id=d32a0c6f-8ace-49ba-83bd-a400a56c866f`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=Meteora는 Solana 유동성 효율과 토큰 런칭 자동화가 강점이지만, MET 가치 포착은 아직 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=4c1a8b32-4ed7-4e71-8b7b-054b9b17666c`

### BCE-2132 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-23 17:47 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Magma Finance의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Source identity:
  `drive:19vllBSiVVbyQO43qoYNFZepd0In8bn3Y:0B8HYgThT3NByVm9JWTlPUnIzb3c3ZGRmUmZRTkU2KzlvdzRzPQ`.
- Source SHA-256:
  `3d3484a57aab66434680149b9a1b608a24f1982b7dfaa4ae2b14ece2759ba936`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_magma-finance_bce2132.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_magma-finance.json`.
- Execution note:
  the generic entrypoint's slug-filter path attempted broader MAT folder
  downloads because Korean MAT filenames are not always parsed into slugs, so
  this run used the same candidate validation/upsert functions against the
  selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `magma-finance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `dba38904-d9ce-428e-9204-6367de9a5005`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id dba38904-d9ce-428e-9204-6367de9a5005 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2132" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `4e092b3f-ef8e-4f1e-b37f-988d67d3c8f0`
  - promoted_at: `2026-06-23T08:47:55.032197+00:00`
- Project report verification:
  - `tracked_projects.slug=magma-finance`
  - `project_reports.id=4e092b3f-ef8e-4f1e-b37f-988d67d3c8f0`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Magma Finance는 Sui 기반 ALMM DEX 구현은 확인되지만, 수수료와 거버넌스 성숙도는 아직 약하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=dba38904-d9ce-428e-9204-6367de9a5005`

### BCE-2133 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-23 18:13 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Magma Finance 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1HAGkmutus6G8MMRPku0iDthdmgN7ISn2:0B8HYgThT3NBybTdONGdIVnVhS3hOUU41a2d1K2tIVFVrWk1vPQ`.
- Source SHA-256:
  `e70af375e55f68cb76a7f899654fb88d2a8139e93900fc45fdfb277d7831ad97`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_magma-finance_bce2133.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_magma-finance.json`.
- Execution note:
  the generic entrypoint's slug-filter path can attempt broader folder scans
  when Korean ECON filenames are not parsed into slugs, so this run used the
  same candidate validation/upsert functions against the selected Drive file id
  only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `magma-finance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d1d5cb1e-7eb9-47c7-b269-189d2db083b0`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d1d5cb1e-7eb9-47c7-b269-189d2db083b0 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2133" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `ef22c31e-1d27-40d1-900f-4e0508b1c9c0`
  - promoted_at: `2026-06-23T09:12:55.44962+00:00`
- Project report verification:
  - `tracked_projects.slug=magma-finance`
  - `project_reports.id=ef22c31e-1d27-40d1-900f-4e0508b1c9c0`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=Magma Finance는 Sui 집중유동성 DEX로 자본 효율은 강하지만, 거래량 품질과 MAGMA 희석 리스크 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=d1d5cb1e-7eb9-47c7-b269-189d2db083b0`

### BCE-2134 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 05:37 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Decentraland MANA 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1FDc-FNV0PeMYoP4nFGKKkGCQZN4bRSNb:0B8HYgThT3NByTU9SSWZhZHpWMFBvTVpDSlArRUxlVlMrWU9ZPQ`.
- Source SHA-256:
  `0f3d994e4324f4ccf0b7569b05413a4b05983983e63407883dba84e1b098e9ba`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_decentraland_bce2134.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_decentraland.json`.
- Execution note:
  the generic entrypoint's slug-filter path can attempt broad FOR folder scans
  when Korean forensic filenames are not parsed into slugs, so this run used the
  same candidate validation/upsert functions against the selected Drive file id
  only.
- Candidate ingest result:
  - report type: `for` / DB type: `forensic`
  - slug: `decentraland`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `fabcc35f-0397-41fa-8621-432437d68441`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fabcc35f-0397-41fa-8621-432437d68441 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2134" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `83cdd187-4203-44d9-b86e-117f3e16f6e3`
  - promoted_at: `2026-06-23T20:37:31.858158+00:00`
- Project report verification:
  - `tracked_projects.slug=decentraland`
  - `project_reports.id=83cdd187-4203-44d9-b86e-117f3e16f6e3`
  - `report_type=forensic`, `language=ko`, `status=published`
  - `card_summary_ko=Decentraland MANA는 중상위 조작 리스크와 선물 우위가 겹쳐, 0.0744 돌파 전까지 고점 분배 압력이 크다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=fabcc35f-0397-41fa-8621-432437d68441`
- BCE-2127 closure verification:
  `BCE-2128` completed, then `BCE-2127` resumed at workspace
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  SHA `fb1f7e8`. `https://www.bcelab.xyz/en/reports/forensic/decentraland`
  and `https://www.bcelab.xyz/en/projects/decentraland` both returned HTTP
  `200` with `cache-control: private, no-cache, no-store, max-age=0,
  must-revalidate`; both HTML responses contained the promoted English text
  `Decentraland MANA has elevated manipulation risk and futures driven flow,
  leaving distribution pressure high until the 0.0744 area breaks.` The stale
  BCE-2126 English text was absent from both pages. Local verification also
  passed: `python3 -m pytest scripts/pipeline/test_summary_authority_gate.py`
  (`7 passed`) and `npm run verify:runtime-pipelines`.

### BCE-2135 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 06:27 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `o1.exchange 크립토이코노미 설계 심층 분석.md`.
- Source identity:
  `drive:1h4tkt3wEgPl3H79_7be_LXN9JqNKGkkb:0B8HYgThT3NByY1JUMGJJTHRUaEJxT0hrUEJ3ZXYrc3JkWWwwPQ`.
- Source SHA-256:
  `560e3c912f5c87c74f52d631117f6bc79fb2feb6188c9a6a743403b6bf0aa1d9`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_o1-exchange_bce2135.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_o1-exchange.json`.
- Execution note:
  the first ingest inserted the candidate row as validation-failed because
  `marketing_by_lang.en.raw_format_fragment` and `marketing_by_lang.zh.too_short`
  tripped the card-quality gate. The CRO JSON was revised to remove the
  hyphenated raw-format fragment and lengthen the zh Investment View, then the
  same idempotency row was rerun with `--force`.
- Candidate ingest result after correction:
  - report type: `econ`
  - slug: `o1-exchange`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `547b9c98-e349-460d-aac7-fcd993b713d2`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 547b9c98-e349-460d-aac7-fcd993b713d2 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2135" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `284a31f2-e4f3-4af9-a793-a0e6f9579af5`
  - promoted_at: `2026-06-23T21:27:56.171973+00:00`
- Project report verification:
  - `tracked_projects.slug=o1-exchange`
  - `project_reports.id=284a31f2-e4f3-4af9-a793-a0e6f9579af5`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=o1.exchange는 Base 거래 애그리게이터 UX가 강점이나, 보상 회계와 거버넌스 투명성 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=547b9c98-e349-460d-aac7-fcd993b713d2`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/o1-exchange/econ` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted English summary plus Investment View.
  - `https://www.bcelab.xyz/en/projects/o1-exchange` returned HTTP `200`
    with the same no-store cache policy and contained the promoted ECON card
    summary plus Investment View.

### BCE-2136 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 07:06 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `o1.exchange의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024 - 2026.md`.
- Source identity:
  `drive:1Jc6BkGU13UZK_8PJirgPZiav2mbuB_FF:0B8HYgThT3NBydjdyZmxsSGNkQk1qRGtPNzlSemlaUGNpRlhNPQ`.
- Source SHA-256:
  `5f9639f57cc8509baf37273ae00a0607a5925fe92208090578d9d952c38f6b1f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_o1-exchange_bce2136.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_o1-exchange.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug o1-exchange --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_o1-exchange_bce2136.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  folder downloads before candidate selection. The run then used the same
  candidate validation, upsert, artifact, and telemetry functions against the
  selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `o1-exchange`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `41f3f461-a9bd-4d5c-b2f8-44bd6a6bda06`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 41f3f461-a9bd-4d5c-b2f8-44bd6a6bda06 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2136" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `58d74ee4-cffd-4e1e-887c-4aeb145e080b`
  - promoted_at: `2026-06-23T22:05:19.580864+00:00`
- Project report verification:
  - `tracked_projects.slug=o1-exchange`
  - `project_reports.id=58d74ee4-cffd-4e1e-887c-4aeb145e080b`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=o1.exchange는 제품 출시는 빠르지만, 수익 지속성과 거버넌스 성숙도는 아직 검증 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=41f3f461-a9bd-4d5c-b2f8-44bd6a6bda06`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/o1-exchange/maturity` returned HTTP
    `200` with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate` and contained the promoted English summary plus
    Investment View.
  - `https://www.bcelab.xyz/en/projects/o1-exchange` returned HTTP `200` with
    the same no-store cache policy and contained the promoted MAT card summary
    plus Investment View.

### BCE-2148 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 18:12 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `Wormhole의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020 - 2026.md`.
- Source identity:
  `drive:142VuboZ_vd3y1003uyPZe7XZg6cVOZqH:0B8HYgThT3NBySEhSYTl3bXZ6c3JRN2pBaVhZKzVNbFV2cy9JPQ`.
- Source SHA-256:
  `73a5a98e5d8181079d1d9fb19976589dfbc78d8dada6f39d1aeef641f9473515`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_wormhole_bce2148.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_wormhole.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug wormhole --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_wormhole_bce2148.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  folder downloads before candidate selection. The run then used the same
  candidate validation, upsert, artifact, and telemetry functions against the
  selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `wormhole`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `acd5661b-a9cc-47c0-b9e7-33d3f399eb23`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id acd5661b-a9cc-47c0-b9e7-33d3f399eb23 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2148" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `bb9a7fc9-7813-49d9-965e-d304c8023e91`
  - promoted_at: `2026-06-24T09:12:15.344188+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2148_wormhole_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=wormhole`
  - `project_reports.id=bb9a7fc9-7813-49d9-965e-d304c8023e91`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Wormhole은 멀티체인 인프라 성숙도는 높지만, W 토큰 수익 포획과 잔여 언락이 핵심 검증 과제다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=acd5661b-a9cc-47c0-b9e7-33d3f399eb23`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2148_wormhole_website_verification.json`.
  KO and EN report/project pages for `wormhole` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier lacked a CA
  chain, so the HTTP/content verification was rerun with certificate
  verification disabled for the check only.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2166 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 00:37 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `Circle Internet Group — Ondo Tokenized Stock, CRCLon의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`.
- Source identity:
  `drive:15U8cvoMOgxZOK3TeAw5cFTpOZObulLwO:0B8HYgThT3NByNWdoMERrVi9ZRk9sNy9JanhCZkIzVXJ4VnpNPQ`.
- Source SHA-256:
  `22fd95ae72ea6ec8fe8000c25b61385492e9f8a4641fdc777d30de97d137fe91`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_circle-internet-group-tokenized-stock-ondo_bce2166.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_circle-internet-group-tokenized-stock-ondo.json`.
- Execution note:
  the filename was not parsed into a slug by the generic Markdown filename
  parser, so this run used the same candidate validation, upsert, artifact, and
  telemetry functions against the selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `circle-internet-group-tokenized-stock-ondo`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `d4c77238-eece-469a-8884-5a698db5752b`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id d4c77238-eece-469a-8884-5a698db5752b --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2166" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `9ddaa0db-1bc2-4198-b609-45b0adf2ac30`
  - promoted_at: `2026-06-24T15:37:02.966492+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2166_crclon_mat_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=circle-internet-group-tokenized-stock-ondo`
  - `project_reports.id=9ddaa0db-1bc2-4198-b609-45b0adf2ac30`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=CRCLon은 담보와 증명 구조가 강하지만, 주주권 부재와 오프체인 의존이 남은 토큰화 주식 성숙 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=d4c77238-eece-469a-8884-5a698db5752b`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2166_crclon_mat_website_verification.json`.
  KO and EN report/project pages for
  `circle-internet-group-tokenized-stock-ondo` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier lacked a CA
  chain, so the HTTP/content verification was rerun with certificate
  verification disabled for the check only.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2180 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 08:00 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `USA₮(USAT)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1IlW8NJtVV8u-AFl7zrCbycK-U7UW4Yyi:0B8HYgThT3NByODJ5bGpGeHJHSEpvS1MvbEJQZk1kSTVNZHpRPQ`.
- Source SHA-256:
  `e2865f5f6bd3fa6b13bdc5c54dbd0b1712135f9851dc0eecf94925f980cb3e35`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_tether-usat_bce2180.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_tether-usat.json`.
- Source audit artifact:
  `scripts/pipeline/output/paperclip_cro_source_mat_tether-usat_bce2180.md`.
- Execution note:
  the filename was not parsed into a slug by the generic Markdown filename
  parser, so this run used the same candidate validation, upsert, artifact, and
  telemetry functions against the selected Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `tether-usat`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `1f9fc5f5-a325-4d52-acdf-a98906a0789f`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 1f9fc5f5-a325-4d52-acdf-a98906a0789f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2180" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `344320b1-e56d-4914-902f-c079c011d56b`
  - promoted_at: `2026-06-24T23:00:58.045229+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2180_tether_usat_mat_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=tether-usat`
  - `project_reports.id=344320b1-e56d-4914-902f-c079c011d56b`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=USAT는 은행 발행과 준비금 증명은 강하지만, 유동성·실사용·증명 최신성은 아직 검증 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=1f9fc5f5-a325-4d52-acdf-a98906a0789f`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2180_tether_usat_mat_website_verification.json`.
  KO and EN report/project pages for `tether-usat` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier used an
  unverified SSL context for the HTTP/content check because the local CA chain
  was incomplete.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2181 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 08:49 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `WeFi 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1oD6z3H1tmKWDT81NhcQkpA3DTs4xVch9:0B8HYgThT3NByZFpRV2dxbGFHTERoa0V1NS8wMkFuK3I2RGdZPQ`.
- Source SHA-256:
  `94d07108cd935552aa3f60a55200e30b911f765fe8b725eb3487585ca66ff096`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_wefi_bce2181.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_wefi.json`.
- Source audit artifact:
  `scripts/pipeline/output/paperclip_cro_source_econ_wefi_bce2181.md`.
- Execution note:
  the first ingest inserted the candidate row as validation-failed because
  `marketing_by_lang.{de,en,es,fr}.raw_format_fragment`,
  `summary_by_lang.de.raw_format_fragment`, and
  `marketing_by_lang.zh.too_short` tripped the card-quality gate. The CRO JSON
  was revised to remove raw-format fragments and lengthen the zh Investment
  View, then the same idempotency row was rerun with `--force`.
- Candidate ingest result after correction:
  - report type: `econ`
  - slug: `wefi`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `5a418e94-e270-4042-a0d4-a7e857403d2c`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 5a418e94-e270-4042-a0d4-a7e857403d2c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2181" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `1ce848dc-4ee5-4eec-905d-8ade66dd6088`
  - promoted_at: `2026-06-24T23:48:49.921171+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2181_wefi_econ_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=wefi`
  - `project_reports.id=1ce848dc-4ee5-4eec-905d-8ade66dd6088`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=WeFi는 금융 실사용과 WFI 보상을 연결하지만, 토큰 외 핵심 회계·Energy·CBM 검증 경로는 아직 제한적이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=5a418e94-e270-4042-a0d4-a7e857403d2c`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2181_wefi_econ_website_verification.json`.
  KO and EN report/project pages for `wefi` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier used an
  unverified SSL context for the HTTP/content check because the local CA chain
  was incomplete.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 5 (2026-06-24 12:18 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/mat.md`,
  `knowledge/pipelines/analysis-md-summary-candidate.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence/backfill context:
  `/private/tmp/mat_backfill_audit_fast.json` showed `needs_processing=259`.
  A current DB comparison found `processed_by_current_db=43` and
  `remaining_by_current_db=216` before this batch item.
- Selected MAT Drive Markdown:
  `Lido DAO의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020 - 2026 (1).md`.
- Source identity:
  `drive:1L9mtXSqFoUWCwlYi59mJ4EFKxgFc8br0:0B8HYgThT3NBya1UzZ24zcDBqWW5DUURqUWdxcWwrMWNBWDg0PQ`.
- Source SHA-256:
  `9da95a81dc0063d29859d8af474998381f3867df6a7775e32731767ebbc7b590`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_lido-dao_bce2055_batch5.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_lido-dao.json`.
- Execution note:
  the local `--source-path` dry-run/write was used first to validate summary
  copy, but that produced a local `sha256:` source identity. The final
  production record was corrected by running the same candidate validation and
  upsert functions against the selected Drive file id only, because the generic
  MAT Drive folder path can begin broad downloads before slug selection on
  Korean filenames.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `lido-dao`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `e9a415a7-24f7-4785-b719-d895c78cbf92`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id e9a415a7-24f7-4785-b719-d895c78cbf92 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2055-batch5" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `85ba306e-910f-4eb6-b997-d7e24dc91d5d`
  - promoted_at: `2026-06-24T03:17:40.296728+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2055_batch5_lido_dao_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=lido-dao`
  - `project_reports.id=85ba306e-910f-4eb6-b997-d7e24dc91d5d`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Lido는 stETH 유동성과 Ethereum 스테이킹 인프라에서 높은 성숙도를 보이지만, 검증인 집중도와 LDO 가치 포착이 핵심 한계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=e9a415a7-24f7-4785-b719-d895c78cbf92`
  - audit item check for the exact Drive file/revision returned
    `processed_by_current_db=true`.
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/lido-dao/maturity` returned HTTP `200`
    and contained the promoted Korean summary and Investment View.
  - `https://www.bcelab.xyz/en/reports/lido-dao/maturity` returned HTTP `200`
    and contained the promoted English summary and Investment View.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because this was a single-candidate backfill execution under the
  existing `analysis-md-summary-candidate` contract.

### BCE-2055 CRO MAT Summary Backfill Batch 6 (2026-06-24 12:52 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/mat.md`,
  `knowledge/pipelines/analysis-md-summary-candidate.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- Operator wake context:
  the issue had been reopened from `blocked`; the requested action was to
  continue from the latest MAT audit queue rather than stale batch-local
  candidates.
- Latest audit queue:
  `/private/tmp/mat_backfill_audit_fast.json` showed
  `needs_processing_items=259`. The first five queue entries were selected:
  `superfortune`, `re-protocol`, `nockchain`,
  `amd-tokenised-stock-xstock`, and `deepbook-protocol`.
- Duplicate-slug handling:
  `deepbook-protocol` appeared more than once in the audit list. The final
  promoted job used the queue-head file `deepbook-protocol_mat_v1.md` with
  Drive file id `1qhyVyKmjp_TC9gltXp0LMG0GinWErx1x`, not the later duplicate.
- Paperclip CRO JSON outputs:
  - `scripts/pipeline/output/paperclip_cro_summary_mat_superfortune_bce2055_batch6.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_re-protocol_bce2055_batch6.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_nockchain_bce2055_batch6.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_amd-tokenised-stock-xstock_bce2055_batch6.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_deepbook-protocol_bce2055_batch6.json`
- Candidate ingest and promotion results:
  - `superfortune`:
    source identity
    `drive:1KgSEgykSieiGJX3iBu5-qHY-UcDg8blf:0B8HYgThT3NBybTcvVW52c3k5RlFTSXl2RE1FR2w2NnBWL2lnPQ`;
    source SHA-256
    `9f833d8a7019d35b837e93b7647d9c9e8ab08caa09fc96b3eb88a316100d6953`;
    job `167afd1d-e115-491c-9ae9-1a25117173c4`;
    promoted report `286394ca-ee84-4f25-b09a-a53ef46b715b`.
  - `re-protocol`:
    source identity
    `drive:1rhEbhdIh03XwHybt7-rhsgiGbF08d_Hx:0B8HYgThT3NBySmVJT0RwM3AyUHdEeWpFYndWa1djNjAxMmRvPQ`;
    source SHA-256
    `e28322b9ec9474b995e6bee0d6cdb897804f9004a18ddcccc539cae11bbb08b8`;
    job `01ba1a28-a1b9-41a4-918d-38a0f2f2cf1f`;
    promoted report `ee4f7205-0b69-4531-aa9a-4e9b20f5f382`.
  - `nockchain`:
    source identity
    `drive:1yZKETgeqRg9U8dGe6ZoaJWBvLDZfwqCn:0B8HYgThT3NByL1RDRjcvbzBwSmVxaE5ydlJIWHV0Q0NXNk80PQ`;
    source SHA-256
    `b2c17ee477d02e1c5d11ccd502a2207d9a22f40ec22b5744280cea89d65bf84f`;
    job `498bb3a0-0e10-4725-b93c-b9d50bcbb3f8`;
    promoted report `f6825e19-34cd-449c-9aef-ec302f2eeeda`.
  - `amd-tokenised-stock-xstock`:
    source identity
    `drive:1Z3Z9HU7VOndfouQgWERQN8CiOhAQWeBi:0B8HYgThT3NByRTN6Z3NKakRXU2FhZGdKUkhDTmVHbjZZZkdnPQ`;
    source SHA-256
    `12f815294de1ee37ec5e607625a03ca9fcd516958cb372b98de0db86a32eb98a`;
    job `9647caf2-c38f-4d33-a3c0-c1a6813c5b0d`;
    promoted report `fad85639-f2df-458e-b6bc-dd9dd8e49272`.
  - `deepbook-protocol`:
    source identity
    `drive:1qhyVyKmjp_TC9gltXp0LMG0GinWErx1x:0B8HYgThT3NByVTJtbGVqR1dLaFlWWklpbmtpMlRDcnpKQnRNPQ`;
    source SHA-256
    `e8c3d4d2ae3ec2b8f6fd4cf113a835ee555950d3016849733bfb5475d4e10c9c`;
    job `56df0ad2-4b0e-4a91-8804-9bed5ff73b17`;
    promoted report `66438dae-e9e2-4732-825a-d46f9508ac29`.
- Summary Authority Gate write command pattern:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id <job-id> --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2055-batch6" --write`.
- DB verification artifact:
  `scripts/pipeline/output/bce2055_batch6_db_verification.json`.
  All five jobs are `authority_state=promoted`,
  `authority_mode=llm_active`, and linked to `project_reports.status=published`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2055_batch6_website_verification.json`.
  KO and EN report pages for all five slugs returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier lacked a CA
  chain, so the HTTP/content verification was rerun with certificate
  verification disabled for the check only.
- Current DB-audit comparison after this batch:
  `processed_by_current_db_in_needs_after_batch=44` and
  `remaining_by_current_db_after_batch=215`.
- Next queue candidates after this batch:
  `solstice-eusx`, `rollbit-coin`, `usdf`, `frax-usd`,
  `nvidia-tokenized-stock-xstock`, then `alphabet-tokenized-stock-xstock`,
  `swissborg`, `nasdaq-tokenized-stock-xstock`, `gusd`, and `allora`.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 7 (2026-06-24 12:59 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/mat.md`,
  `knowledge/pipelines/analysis-md-summary-candidate.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- Current audit selection:
  `/private/tmp/mat_backfill_audit_fast.json` still contained processed queue
  entries, so selection was made by filtering `needs_processing_items` against
  current DB rows where `report_summary_jobs.authority_state=promoted`.
  Before this batch the DB comparison showed `processed_in_audit=44` and
  `remaining=215`.
- Selected MAT Drive Markdown entries:
  `solstice-eusx`, `rollbit-coin`, `usdf`, `frax-usd`, and
  `nvidia-tokenized-stock-xstock`.
- Paperclip CRO JSON outputs:
  - `scripts/pipeline/output/paperclip_cro_summary_mat_solstice-eusx_bce2055_batch7.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_rollbit-coin_bce2055_batch7.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_usdf_bce2055_batch7.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_frax-usd_bce2055_batch7.json`
  - `scripts/pipeline/output/paperclip_cro_summary_mat_nvidia-tokenized-stock-xstock_bce2055_batch7.json`
- Candidate ingest and promotion results:
  - `solstice-eusx`:
    source identity
    `drive:1NSObkzBkosbfIPRJadDU5Xs27g7DDltO:0B8HYgThT3NBySlZpaGJQd3JWUkorTDlkajRMUGgwSnNPQjkwPQ`;
    source SHA-256
    `5d33aceb12ad75fd05132cd897a66c403bf01c13c09ca397998678dbbedcd7ed`;
    job `8dc670a5-677b-4fb5-8326-97553bd09106`;
    promoted report `893c4658-8c6d-4b78-888a-820b0aac91b0`.
  - `rollbit-coin`:
    source identity
    `drive:1b7QYlt5yar88SGL8xt1TrDQBVWycHSmu:0B8HYgThT3NByamZWNzNOT1BUaUJabWdLa04vdTJ6a092RDZjPQ`;
    source SHA-256
    `a05959bb40db6d00c2b3a52254f101132d7f4bfacf2c6a1abe15c90d22d6653f`;
    job `08894768-fd31-471d-8897-976141b1d648`;
    promoted report `416bb0d1-41a7-43f1-8bd2-0c7788214550`.
  - `usdf`:
    source identity
    `drive:1cItBJ6hGn7_3mrn2jP25tCiQiU-YHhOA:0B8HYgThT3NByZkNpK0c5RHprMlo1bmNEdldTcVd5SDA1NVEwPQ`;
    source SHA-256
    `7f2654da58bffb0a2d718921b8da39e4c3ebbaab309ba60ee07bcf1ab9398820`;
    job `4f4cbb2b-3c19-4d57-8d57-5de83baa5a3f`;
    promoted report `d5477a8d-ac49-41bc-ac3c-625f0a62dec0`.
  - `frax-usd`:
    source identity
    `drive:1XTGas2NAGX2rbb2DHMnnUDCkNk2I0ARK:0B8HYgThT3NByVWpyUm9zbTdYYjlnVGlXdDdrb0hlMXdsTnpFPQ`;
    source SHA-256
    `a958cd645e5896e42ba9391c840810633a851f89984b8d42f90c953ec8690aa8`;
    job `0c413b4c-371a-4184-94ad-2afb5e018ddc`;
    promoted report `ee57d944-e3bb-43d2-905d-620af42d9d81`.
  - `nvidia-tokenized-stock-xstock`:
    source identity
    `drive:1yGFOLsHpduxJcAxisc0LQ7AIzsb6hsdP:0B8HYgThT3NByWXByQ2hnZ0s0dm9NOEpNRTJvUTJBM0RYeVpjPQ`;
    source SHA-256
    `ae7caa737563fa6a86e3590888defe1526ba1c0f2004ca70a1eb2f02b83c85c9`;
    job `03b69501-0db8-4529-9f74-0c5175ab6a1d`;
    promoted report `47a26dfa-387c-46f6-a4e3-3808398f1930`.
- DB verification artifact:
  `scripts/pipeline/output/bce2055_batch7_db_verification.json`.
  All five jobs are `authority_state=promoted`,
  `authority_mode=llm_active`, and linked to `project_reports.status=published`.
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2055_batch7_website_verification.json`.
  KO and EN report pages for all five slugs returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. As in Batch 6, local CA chain verification
  was disabled for the HTTP/content check only.
- Current DB-audit comparison after this batch:
  `processed_by_current_db_in_needs_after_batch=49` and
  `remaining_by_current_db_after_batch=210`.
- Next queue candidates after this batch:
  `alphabet-tokenized-stock-xstock`, `swissborg`,
  `nasdaq-tokenized-stock-xstock`, `gusd`, `allora`,
  `sp500-tokenized-stock-xstock`, `slimex`,
  `intel-tokenized-stock-xstock`, `myx-finance`, and `wefi`.
- Pipeline state wiki was updated with this batch evidence. No manifest change
  was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

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

### BCE-2138 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 12:29 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest Drive Markdown selected by metadata scan:
  `Zama의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020-2026.md`.
- Source identity:
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Source SHA-256:
  `9364c13aa5054fec008bdf4713cd0ed9393bdba3e259199a01c455e573b42a0d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_zama.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_zama.json`.
- Execution note:
  the generic entrypoint's slug-filter path can attempt broad folder downloads
  when Korean MAT filenames are not parsed into slugs, so this run used the
  same candidate validation/upsert functions against the selected Drive file id
  only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `zama`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `32df6eff-e158-4b87-ae57-272517755613`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 32df6eff-e158-4b87-ae57-272517755613 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2138" --write`.
- Promotion result:
  - result: blocked by target report lookup failure
  - error: `website-visible project_reports target not found: zama/maturity/ko`
  - job state after failure: `validation_passed`
  - wrote_project_report: `false`
  - promoted_project_report_id: none
- Target report verification:
  - `tracked_projects.slug=zama`
  - existing `project_reports` rows for Zama include only
    `forensic/en/status=coming_soon`.
  - No website-visible `maturity/ko` target exists for Summary Authority Gate
    promotion.

### BCE-2139 Zama MAT Summary Authority Target Backfill (2026-06-24 12:35 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before implementation:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `knowledge/pipelines/website.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- Root cause:
  candidate job `32df6eff-e158-4b87-ae57-272517755613` is valid and remains
  `authority_state=validation_passed`, but Summary Authority Gate promotion
  requires an existing website-visible `project_reports` target. Production has
  `tracked_projects.slug=zama` and only `forensic/en/status=coming_soon`; it has
  no `maturity/ko/version=1` row.
- Resolution path:
  `supabase/migrations/20260624033500_seed_zama_maturity_ko_summary_target.sql`
  creates a scoped Zama `maturity/ko/version=1` `coming_soon` shell with
  `source_identity=summary-authority-target:zama/maturity/ko/version:1` and
  links the backfill to BCE-2139 and the Zama candidate job.
- Boundary:
  the migration creates only the website-visible target shell. It does not
  promote candidate job `32df6eff-e158-4b87-ae57-272517755613`; the gate must be
  rerun through the approved remote production-write path before the candidate
  can become `llm_active`.

### BCE-2140 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 13:02 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before diagnosis:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  [BCE-2139](/BCE/issues/BCE-2139) remains blocked on production migration
  approval/apply for the Zama `maturity/ko` Summary Authority Gate target.
- Production DB verification repeated:
  `tracked_projects.slug=zama` exists, but `project_reports` still contains
  only `forensic/en/status=coming_soon`; no `maturity/ko/version=1` target is
  available for promotion.
- Routine decision:
  no new candidate ingest or `llm_active --write` promotion was run in BCE-2140.
  The routine remains blocked by the unresolved Zama target migration because
  rerunning the gate before that target exists would reproduce the BCE-2138
  failure.

### BCE-2141 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 13:30 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before diagnosis:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  [BCE-2139](/BCE/issues/BCE-2139) is still the active blocker for Zama
  `maturity/ko` Summary Authority Gate target creation/apply. BCE-2140 already
  recorded that rerunning the gate before this target exists would reproduce
  the BCE-2138 failure.
- Drive scan context:
  - Latest raw MAT Markdown was `ZRX ... 0x Protocol.md`, but no matching
    `tracked_projects` row was found for `0x`, `0x-protocol`, or `zrx`.
  - Latest eligible known candidate remains Zama MAT source identity
    `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Candidate job state:
  `32df6eff-e158-4b87-ae57-272517755613` remains
  `status=candidate_ready`, `validation_status=valid`,
  `authority_state=validation_passed`, `report_type=maturity`, `locale=ko`.
- Production DB verification repeated:
  `tracked_projects.slug=zama` exists, but `project_reports` still contains
  only `forensic/en/status=coming_soon`; no website-visible
  `maturity/ko/version=1` target is available for promotion.
- Gate check:
  a direct `llm_active --write` retry against job
  `32df6eff-e158-4b87-ae57-272517755613` failed with
  `website-visible project_reports target not found: zama/maturity/ko`, matching
  the known BCE-2138/BCE-2140 blocker.
- Routine decision:
  BCE-2141 remains blocked by BCE-2139. No candidate or `project_reports` write
  was completed in this heartbeat.

### BCE-2142 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 14:07 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before diagnosis:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  [BCE-2139](/BCE/issues/BCE-2139) remains `blocked` on board/operator approval
  and remote production apply for the Zama `maturity/ko/version=1` Summary
  Authority Gate target. BCE-2140 and BCE-2141 already recorded the same
  blocker.
- Drive scan context:
  latest raw metadata still places `ZRX ... 0x Protocol.md` ahead of Zama, but
  no `tracked_projects` row exists for `zrx`, `0x`, or `0x-protocol`. The latest
  eligible known candidate remains the previously ingested Zama MAT source
  identity
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Production DB verification repeated:
  `tracked_projects.slug=zama` exists, but `project_reports` still has no
  `maturity/ko/version=1` target; Zama `maturity/ko` promotion would still fail
  target lookup.
- Routine decision:
  BCE-2142 is blocked by [BCE-2139](/BCE/issues/BCE-2139). No new candidate
  ingest or `llm_active --write` promotion was run because it would repeat the
  known target-missing failure before the migration is approved and applied.

### BCE-2143 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 14:31 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before diagnosis:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  [BCE-2139](/BCE/issues/BCE-2139) remains `blocked` on the production target
  creation/apply path for Zama `maturity/ko/version=1`.
- Drive scan context:
  the newest raw Markdown remains `ZRX ... 0x Protocol.md`, but no
  `tracked_projects` row exists for `zrx`, `0x`, or `0x-protocol`. The latest
  eligible known candidate remains Zama MAT source identity
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Production DB verification repeated:
  `tracked_projects.slug=zama` exists; `project_reports` still contains only
  `forensic/en/status=coming_soon`; `zama/maturity/ko/version=1` is still
  absent.
- Candidate job state:
  `32df6eff-e158-4b87-ae57-272517755613` remains
  `status=candidate_ready`, `validation_status=valid`,
  `authority_state=validation_passed`, `report_type=maturity`, `locale=ko`.
- Routine decision:
  BCE-2143 is blocked by [BCE-2139](/BCE/issues/BCE-2139). No new candidate
  ingest or `llm_active --write` promotion was run because the required
  website-visible target is still absent and rerunning the gate would reproduce
  the known target lookup failure.

### BCE-2144 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 15:42 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Recurrence check:
  BCE-2140 through BCE-2143 were blocked because the valid Zama MAT candidate
  job had no website-visible `zama/maturity/ko` target for Summary Authority
  Gate promotion. In this heartbeat, production DB state showed the target now
  exists:
  `project_reports.id=9d8e5d61-5333-431e-a240-3625d37d0662`,
  `report_type=maturity`, `language=ko`, `status=published`.
- Candidate job reused:
  `32df6eff-e158-4b87-ae57-272517755613`.
- Source identity:
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Source SHA-256:
  `9364c13aa5054fec008bdf4713cd0ed9393bdba3e259199a01c455e573b42a0d`.
- Existing candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_zama.json`.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 32df6eff-e158-4b87-ae57-272517755613 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2144" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `9d8e5d61-5333-431e-a240-3625d37d0662`
  - promoted_at: `2026-06-24T06:42:15.039977+00:00`
- DB verification:
  - `report_summary_jobs.authority_state=promoted`
  - `report_summary_jobs.authority_mode=llm_active`
  - `report_summary_jobs.promotion_decision=promote`
  - `project_reports.card_data.summary_authority.mode=llm_active`
  - `project_reports.card_data.summary_authority.job_id=32df6eff-e158-4b87-ae57-272517755613`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/zama/maturity` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted Korean summary and Investment View.
  - `https://www.bcelab.xyz/en/reports/zama/maturity` returned HTTP `200` with
    the same no-store cache policy and contained the promoted English summary
    and Investment View.
  - `https://www.bcelab.xyz/ko/projects/zama` and
    `https://www.bcelab.xyz/en/projects/zama` both returned HTTP `200` with
    the same no-store cache policy and contained the promoted localized MAT card
    summary plus Investment View.
- Pipeline state wiki was updated with this promotion evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2145 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 16:50 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Drive scan context:
  the newest raw Markdown remained `ZRX ... 0x Protocol.md`, but no
  `tracked_projects` row exists for `zrx`, `0x`, or `0x-protocol`. The latest
  eligible website-targeted candidate was Zama MAT.
- Source selected:
  `Zama의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2020-2026.md`.
- Source identity:
  `drive:1-mSEZTiOkWO_3lBoYBPea-mkKY-fajRr:0B8HYgThT3NByU0ZtVHhDSGpWQWp6WEl4dGswZENycWlhczhjPQ`.
- Source SHA-256:
  `9364c13aa5054fec008bdf4713cd0ed9393bdba3e259199a01c455e573b42a0d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_zama_bce2145.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_zama.json`.
- Execution note:
  the generic entrypoint's slug-filter path can attempt broad MAT folder
  downloads when Korean filenames are not parsed into slugs, so this run used
  the same candidate validation/upsert functions against the selected Drive file
  id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `zama`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `32df6eff-e158-4b87-ae57-272517755613`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 32df6eff-e158-4b87-ae57-272517755613 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2145" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `9d8e5d61-5333-431e-a240-3625d37d0662`
  - promoted_at: `2026-06-24T07:50:21.817733+00:00`
- DB verification:
  - `report_summary_jobs.authority_state=promoted`
  - `report_summary_jobs.authority_mode=llm_active`
  - `report_summary_jobs.promotion_actor=paperclip-routine:CRO:BCE-2145`
  - `project_reports.card_summary_ko=Zama는 FHE 기반 기밀성 인프라로 기술·기관 서사는 빠르게 성숙했지만 fee burn과 operator 탈중앙화 검증은 아직 초기 단계다.`
  - `project_reports.card_data.summary_authority.mode=llm_active`
  - `project_reports.card_data.summary_authority.job_id=32df6eff-e158-4b87-ae57-272517755613`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/reports/zama/maturity` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted Korean summary and Investment View.
  - `https://www.bcelab.xyz/en/reports/zama/maturity` returned HTTP `200` with
    the same no-store cache policy and contained the promoted English summary
    and Investment View.
- Pipeline state wiki was updated with this promotion evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2055 CRO MAT Summary Backfill Batch 8 (2026-06-24 17:26 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, `pipelines/bcelab-runtime-pipelines.json`.
- 처리 결과:
  - `alphabet-tokenized-stock-xstock`: job
    `e5770923-1b63-45e9-8214-4a29fb701e63`, report
    `721553f7-3900-4ad9-bfbe-964b8a315c3c`
  - `swissborg`: job `2c818ec5-f0c1-461a-9a57-8ea28401eeea`,
    report `af17048e-8201-47af-8040-e04814c2311b`
  - `nasdaq-tokenized-stock-xstock`: job
    `6160319b-495f-4b57-843c-de64b61c2cf7`, report
    `1d47af7c-730a-45c5-9ca6-fb6ee4fb57ea`
  - `allora`: job `1539fbd0-4088-4bd1-bba1-8824d7d5f33b`,
    report `c53423d0-ae37-47ce-8dcf-2e1d17d6b2a8`
  - `sp500-tokenized-stock-xstock`: job
    `e920bdc0-476f-4c72-a100-861dce625f33`, report
    `45aaecc1-1b35-4dbe-a37b-6655c0799770`
- 안전 스킵:
  `gusd`는 DB/audit 대상이 `Gemini Dollar/GUSD`이나 Drive 원문 파일명과 본문이
  `GUSD(Gate USD)`를 가리켜 동일 프로젝트 source identity gate를 통과하지 못했다.
  따라서 후보 ingest 및 Summary Authority promotion을 실행하지 않았다.
- 산출물:
  - 후보 ingest:
    `scripts/pipeline/output/analysis_md_summary_candidate_mat_bce2055-batch8.json`
  - promotion 결과:
    `scripts/pipeline/output/bce2055_batch8_promotion_results.json`
  - DB 검증:
    `scripts/pipeline/output/bce2055_batch8_db_verification.json`
  - 웹 검증:
    `scripts/pipeline/output/bce2055_batch8_website_verification.json`
- DB 검증:
  다섯 job 모두 `validation_status=valid`,
  `authority_state=promoted`, `authority_mode=llm_active`,
  `promotion_actor=paperclip-routine:CRO:BCE-2055-batch8`이며, audit source
  file/revision과 일치한다. KO/EN `project_reports.card_data.summary_authority`
  역시 각 job id와 `llm_active` 모드를 가리킨다.
- 웹 검증:
  다섯 slug의 KO/EN 성숙도 보고서 10개 URL이 모두 HTTP `200`과
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`를
  반환했고, 승격된 로컬라이즈 카드 요약과 Investment View가 렌더 payload에
  포함됐다. 로컬 검증은 CA 체인 문제를 피하려고 TLS 검증만 비활성화했다.
- 현재 백필 집계:
  `/private/tmp/mat_backfill_audit_fast.json`의 `needs_processing_items=259`를
  현재 DB promoted/current-revision job과 재대조한 결과, 처리 완료 54개,
  남은 current-revision 205개다. 위 안전 스킵 1개를 제외하면 다음 실행 가능
  후보는 204개다.
- 다음 큐:
  `slimex`, `intel-tokenized-stock-xstock`, `myx-finance`, `wefi`,
  `bnb48-club-token`, `keeta`, `billions-network`, `ape-and-pepe`,
  `strategy-pp-variable-tokenized-stock-xstock`,
  `tbll-tokenized-etf-xstock`, `ducky`, `usdgo`.

### BCE-2146 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 17:38 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- 최신 Drive Markdown metadata scan 결과:
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`.
- Source metadata:
  - report type: `mat` / DB type: `maturity`
  - drive file id: `10FHhLUz-RqXfzj-BmFviF54az6c4U4XY`
  - revision id:
    `0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`
  - modified time: `2026-06-23T08:20:21.000Z`
- Blocker:
  `tracked_projects` has no matching target for `0x Protocol`, `0x-protocol`,
  or `ZRX`, and `report_summary_jobs` has no existing row for the selected Drive
  file. The routine cannot safely ingest or promote because Summary Authority
  Gate requires an existing target project/report row.
- Required unblock:
  Data/platform owner must add or map the 0x Protocol/ZRX target project and
  KO maturity report seed, then rerun this routine against the same Drive
  file/revision.
- Manifest change:
  no change needed. This is a target data/backfill blocker under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2153 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 19:36 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Drive source:
  `io.net 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1UnRw-bWnnNKn7FsuxRd6A9bLznVgiGG9:0B8HYgThT3NByK0NQMXpFWW84OWxGSUwvd3AvTkJSRHhLWTZRPQ`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_econ_io-net_bce2153.json`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_io-net.json`.
- Candidate ingest result:
  - slug/report: `io-net/econ`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `43837f75-e014-428a-af4a-d72e2b4a9f52`
- Summary Authority Gate:
  - command mode: `llm_active --write`
  - actor: `paperclip-routine:CRO:BCE-2153`
  - decision: `promote`
  - authority state: `promoted`
  - wrote project report: `true`
  - project report id: `0c73691e-38fa-43d9-bd22-ab0aaa234228`
  - promoted at: `2026-06-24T10:36:10.031799+00:00`
- Project report verification:
  - `project_reports.id=0c73691e-38fa-43d9-bd22-ab0aaa234228`
  - `tracked_projects.id=fb282651-3a6b-44f9-beef-fd90ce2ac3ec`
  - `report_type=econ`
  - `summary_source_md_file_id=1UnRw-bWnnNKn7FsuxRd6A9bLznVgiGG9`
  - `card_summary_ko=io.net은 AI 컴퓨트 수요와 DePIN 보상을 연결하지만, IO 가치포획은 유료 사용과 투명성에 달려 있다.`
- Manifest change:
  no change needed. This was a normal successful run under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2147 0x Protocol/ZRX MAT Target Seed (2026-06-24 17:42 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- 원인:
  [BCE-2146](/BCE/issues/BCE-2146)이 선택한 최신 MAT Markdown
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`에 대해
  `tracked_projects` canonical target이 없어서 Drive source lookup이
  차단됐다.
- 대상 source identity:
  `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`.
- Repo-side seed:
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`
  adds/repairs canonical `tracked_projects.slug=0x`, `symbol=ZRX`,
  `coingecko_id=0x`, aliases `0x protocol`, `0x-protocol`, `zrx`, `zero ex`,
  and a KO `project_reports` `maturity/version=1` Summary Authority Gate target.
- Backfill behavior:
  the migration is idempotent, preserves existing non-cancelled report status,
  reactivates archived project rows, merges aliases, records the Drive
  file/revision in `card_data.summary_authority_target`, and updates
  `last_maturity_report_at` only from an eligible `published`, `coming_soon`,
  or `in_review` target.
- Manifest change:
  no change needed. This remains target data/backfill work under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.
- Next step:
  after the migration is applied in the target DB, resume
  [BCE-2146](/BCE/issues/BCE-2146) and rerun candidate ingest plus
  `llm_active --write` promotion against the same Drive file/revision.

### BCE-2150 0x/ZRX Target Apply Still Pending (2026-06-24 19:21 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/mat.md`, and
  `pipelines/bcelab-runtime-pipelines.json`.
- New recurrence evidence:
  [BCE-2150](/BCE/issues/BCE-2150) produced candidate job
  `885624b8-1a5e-4265-970e-d14adb86b790` for source identity
  `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`.
- Candidate state:
  `validation_status=valid`, `authority_state=validation_passed`.
- Gate failure:
  `summary_authority_gate.py --job-id 885624b8-1a5e-4265-970e-d14adb86b790 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2150" --write`
  failed with `tracked project not found: 0x`; no `project_reports` write
  occurred.
- Approval/apply state:
  board approval
  [44bc62b2-ff81-43f4-bf86-faed5172ac7b](/BCE/approvals/44bc62b2-ff81-43f4-bf86-faed5172ac7b)
  for applying
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`
  remained `pending`.
- Escalation:
  created [BCE-2151](/BCE/issues/BCE-2151) for CTO-owned remote apply/verify
  of the 0x/ZRX target seed and linked [BCE-2147](/BCE/issues/BCE-2147) as
  blocked by it.
- Next step:
  after [BCE-2151](/BCE/issues/BCE-2151) applies and verifies
  `tracked_projects.slug=0x` plus the KO `maturity/version=1` target, resume
  [BCE-2150](/BCE/issues/BCE-2150) with the same gate write command.

### BCE-2149 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 18:39 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Drive source:
  `Wormhole 크립토 이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1KSoYyYBp_2lhOIgsrk8QyrH8bg0q31M_:0B8HYgThT3NBybGptR09JRVBTd1IvdHJXVnFTVXUrczkvUi9jPQ`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_econ_wormhole.json`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_wormhole.json`.
- Candidate ingest result:
  - slug/report: `wormhole/econ`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `390cefbc-b87a-4146-9770-0248bd88aaa4`
- Summary Authority Gate:
  - command mode: `llm_active --write`
  - actor: `paperclip-routine:CRO:BCE-2149`
  - decision: `promote`
  - authority state: `promoted`
  - wrote project report: `true`
  - project report id: `cefaffd4-bb1b-4ffa-a89a-f72fcca1cf10`
- Manifest change:
  no change needed. This was a normal successful run under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2150 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 19:22 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  process-lost retry; the issue had no prior comments, so the run resumed from
  workspace artifacts and Paperclip heartbeat context.
- Drive source:
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`.
- Source identity:
  `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`.
- Source SHA-256:
  `1714ef8196b372f387ebfe36bbee9fc87719bd12aa2fe78ac05e4d55c873f0d7`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_mat_0x_bce2150.json`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_0x.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug 0x --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_0x_bce2150.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  downloads before candidate selection. The run then used the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `0x`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `885624b8-1a5e-4265-970e-d14adb86b790`
  - authority state: `validation_passed`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 885624b8-1a5e-4265-970e-d14adb86b790 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2150" --write`.
- Promotion result:
  - blocked before project report write
  - error: `tracked project not found: 0x`
  - `wrote_project_report=false`
- Production DB verification:
  - `tracked_projects` has no matching row for `slug=0x`, `symbol=ZRX`, or
    `name ilike %0x%`.
  - `project_reports` therefore has no website-visible `0x/maturity/ko`
    Summary Authority Gate target.
- Blocker:
  [BCE-2147](/BCE/issues/BCE-2147) remains blocked on applying the repo-side
  target seed migration
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`.
- Routine decision:
  [BCE-2150](/BCE/issues/BCE-2150) is blocked by
  [BCE-2147](/BCE/issues/BCE-2147). No `project_reports` write was completed;
  the valid candidate job is ready to promote after the 0x/ZRX target seed is
  applied.
- Manifest change:
  no change needed. This is a target data/backfill blocker under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2154 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 20:00 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB scan:
  latest unpromoted source remains
  `ZRX 크립토 이코노미 성숙도 평가 보고서_ 0x Protocol.md`.
- Source identity:
  `drive:10FHhLUz-RqXfzj-BmFviF54az6c4U4XY:0B8HYgThT3NByT1JocHdFY0E5aEFic0loQ0g2REh2SVh1RTVFPQ`.
- Existing candidate job:
  `885624b8-1a5e-4265-970e-d14adb86b790`.
- Candidate state:
  - `validation_status=valid`
  - `authority_state=validation_passed`
  - `promoted_project_report_id=null`
- Production DB verification repeated:
  - no `tracked_projects` row matched `slug=0x`, `symbol=ZRX`, or
    `name ilike %0x%`.
  - no `project_reports` target exists for `0x/maturity/ko`.
- Routine decision:
  no new JSON generation, candidate ingest, or `llm_active --write` promotion
  was run. The next valid action is applying/verifying
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`
  through [BCE-2151](/BCE/issues/BCE-2151), then rerunning the existing valid
  candidate job promotion.
- Manifest change:
  no change needed. This is the same target data/backfill blocker under the
  existing `analysis-md-summary-candidate` and `summary_authority_gate`
  contracts.

### BCE-2155 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 20:31 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Candidate selection:
  the newest Drive source remains the known ZRX/0x MAT source blocked by missing
  `tracked_projects` / `project_reports` target. Because that blocker is already
  recorded in BCE-2154/BCE-2147/BCE-2151, this run processed the next
  unprocessed source with an existing website-visible target:
  `Zama 크립토 이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1F7w0cCsbhZHsvKbM7zYFPgx7W_Kf_lAz:0B8HYgThT3NByRkd2c0xTQ2RHSUxCWEtSdE9GbW51VEs1eTFvPQ`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_econ_zama.json`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_zama.json`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `zama`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `94bcfd9a-ba6e-4ec3-9d8d-f66da606a135`
- Execution note:
  the generic entrypoint command was attempted first but delayed in Supabase
  telemetry after broad Drive candidate selection. The run then used the same
  candidate validation, upsert, artifact, and gate functions against the
  selected Drive file id only, preserving Drive source identity.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 94bcfd9a-ba6e-4ec3-9d8d-f66da606a135 --authority-mode llm_active --actor "paperclip-routine:CRO:d32c5062-3fce-4aa8-aeb4-3ee951b634d1" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `18cfc837-cfea-4671-b0ba-aa06445f392e`
- Deployment/cache implication:
  the promotion updated Supabase `project_reports` directly through the Summary
  Authority Gate RPC. No repo deploy was required; website visibility depends on
  the existing report data fetch/cache behavior.
- Manifest change:
  no change needed. This execution used the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2157 0x/ZRX MAT Target Seed Applied (2026-06-24 21:40 KST)

- Workspace/SHA before repair:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `fb1f7e8`.
- Repair commit:
  `bab7d76` on branch `codex/paperclip-agent-summary-source`.
- Applied migration:
  `supabase/migrations/20260624084500_seed_0x_protocol_maturity_ko_summary_target.sql`.
- Remote apply evidence:
  GitHub Actions database migration run
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28098879427`
  completed successfully through the selected SQL migration path.
- Target verification:
  dry-run Summary Authority Gate for candidate job
  `885624b8-1a5e-4265-970e-d14adb86b790` resolved a website-visible
  `0x/maturity/ko` target and would promote to project report
  `7cc38496-9e3d-44a0-8413-f69cbffe006a`.
- Dry-run command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 885624b8-1a5e-4265-970e-d14adb86b790 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2156"`.
- Dry-run result:
  `dry_run=true`, `action=promote`, `wrote_project_report=false`, reason
  `dry-run promotion would call atomic DB RPC`.
- Manifest change:
  no change needed. This was target seed data under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2158 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 22:19 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `3765764`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Candidate selection:
  processed the newest Drive Markdown source:
  `AWE 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1ApDo2bVWFAykInB4mdh0rzQKMtzULmJ9:0B8HYgThT3NByQm0xcUlySGE4RzFpM1J1V2Q2NWlHSTRyOWs4PQ`.
- Agent output JSON:
  `scripts/pipeline/output/paperclip_cro_summary_for_awe-network_bce2158.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug awe-network --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_awe-network_bce2158.json --require-agent-output --limit 1 --force`.
- Candidate ingest artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_awe-network.json`.
- Candidate ingest result:
  - report type: `for`
  - DB report type: `forensic`
  - slug: `awe-network`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `de5600d2-6b4d-4691-82cd-4d69a08b2a62`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id de5600d2-6b4d-4691-82cd-4d69a08b2a62 --authority-mode llm_active --actor "paperclip-routine:CRO:5db9bfc2-1afb-47e2-9277-93f149152cf0" --write`.
- Promotion result:
  blocked by Supabase RPC error
  `website-visible project_reports target not found: awe-network/forensic/ko`.
- Production DB verification:
  - `tracked_projects.slug=awe-network` exists with symbol `AWE`.
  - `project_reports` has `awe-network/forensic/en` with status `coming_soon`.
  - no `awe-network/forensic/ko` website-visible target row exists.
  - candidate job remains `status=candidate_ready`,
    `validation_status=valid`, `authority_state=validation_passed`, and
    `promoted_project_report_id=null`.
- Required unblock:
  seed/backfill a website-visible `awe-network/forensic/ko` target row, then
  rerun the existing valid candidate job promotion.
- Manifest change:
  no change needed. This is target data/backfill under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2161 Arcium ARX Forensic KO Summary Target Seed (2026-06-24 22:44 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Migration added:
  `supabase/migrations/20260624134500_seed_arcium_forensic_ko_summary_target.sql`.
- Target scope:
  create or repair the missing website-visible
  `arcium/forensic/ko/version:1` target row required by Summary Authority Gate
  job `0334ab47-dfa6-44ae-aa43-884fcb8d74ae`.
- Production apply/verification:
  because local `supabase` and `psql` CLIs were unavailable, the seed payload
  was applied through the existing Supabase service-role API using the same
  row contract as the migration.
  - inserted/verified `project_reports.id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`
  - slug/report target: `arcium/forensic/ko/version:1`
  - status: `coming_soon`
  - source identity:
    `summary-authority-target:arcium/forensic/ko/version:1`
- Gate dry-run verification:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0334ab47-dfa6-44ae-aa43-884fcb8d74ae --authority-mode llm_active --actor "paperclip:DataPlatformEngineer:BCE-2161-dry-run"`
  returned `dry_run=true`, `wrote_project_report=false`, action `promote`,
  and `project_report_id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`.
- Production write boundary:
  this is target seed/backfill data only. It did not invoke
  `summary_authority_gate.py --write`, did not promote the candidate, and did
  not write candidate summary content to `project_reports`.
- Manifest change:
  no change needed. This remains under the existing
  `analysis-md-summary-candidate` authority gate contract; the active FOR slide
  publishing contract is unchanged.

### BCE-2158 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 22:27 KST)

- Resume reason:
  `issue_children_completed` after `BCE-2159` completed the missing target-row
  backfill.
- Workspace/SHA at resume:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Unblock evidence from `BCE-2159`:
  - migration:
    `supabase/migrations/20260624132200_seed_awe_network_forensic_ko_summary_target.sql`
  - remote migration run:
    https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/28101735345
  - target row:
    `project_reports.id=b2cf33e4-e157-44ae-97bc-1698e18d045a`,
    `report_type=forensic`, `language=ko`, `version=1`,
    `status=coming_soon`.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id de5600d2-6b4d-4691-82cd-4d69a08b2a62 --authority-mode llm_active --actor "paperclip-routine:CRO:5db9bfc2-1afb-47e2-9277-93f149152cf0" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `b2cf33e4-e157-44ae-97bc-1698e18d045a`
  - promoted at: `2026-06-24T13:27:35.92693+00:00`
- DB verification after promotion:
  - candidate job `de5600d2-6b4d-4691-82cd-4d69a08b2a62` now has
    `authority_state=promoted` and
    `promoted_project_report_id=b2cf33e4-e157-44ae-97bc-1698e18d045a`.
  - promoted report `card_summary_ko`:
    `AWE는 급등 후 고점 거래량과 되돌림이 겹쳐 단기 조작 취약성이 높아진 상태다.`
  - promoted report `marketing_content_by_lang.ko`:
    `투자 관점에서는 0.0576 지지와 0.0639 돌파를 확인하기 전까지 추격 매수를 피해야 한다.`
  - `card_data.summary_authority.mode=llm_active` with the same job id,
    idempotency key, source identity, and promoted timestamp.
- Deployment/cache implication:
  promotion updated Supabase `project_reports` directly through the Summary
  Authority Gate RPC. No repo deploy was required; website visibility follows
  the existing report data fetch/cache behavior for `coming_soon` report rows.
- Manifest change:
  no change needed. This was target data plus Summary Authority Gate execution
  under the existing `analysis-md-summary-candidate` contract.

### BCE-2172 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 03:10 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Circle xStock(CRCLx)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1dCpNj9lr08J3dyEaKVKZbeXGfam6BYwh:0B8HYgThT3NByaGd6ZnlyYlZvMmVEVkNmdVZDTDNIRHRTWmdnPQ`.
- Source SHA-256:
  `9c9747bc1b89fcc33959b3cf95d46778c7d8d79f15a1f22bd16124e454a43409`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_circle-tokenized-stock-xstock_bce2172.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_circle-tokenized-stock-xstock.json`.
- Execution note:
  the generic entrypoint's slug-filter path attempted broader MAT Drive
  downloads because this Korean MAT filename is not parsed into a slug, so this
  run used the same candidate validation/upsert functions against the selected
  Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `circle-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `22a76093-dd7f-480e-9d02-f00f628a6824`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 22a76093-dd7f-480e-9d02-f00f628a6824 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2172" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `60c9fd00-2327-480b-a51c-3b931dbedac1`
  - promoted_at: `2026-06-24T18:10:15.986421+00:00`
- Project report verification:
  - `tracked_projects.slug=circle-tokenized-stock-xstock`
  - `project_reports.id=60c9fd00-2327-480b-a51c-3b931dbedac1`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=CRCLx는 실사용 RWA 선두권이지만, 성숙도는 담보 검증과 가격추적 투명성에 좌우된다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=22a76093-dd7f-480e-9d02-f00f628a6824`
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2171 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 02:35 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by current Drive/DB scan:
  `CRCLx 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1ivu6JKJBX4lW4vI3ja0TE1vKffginfUB:0B8HYgThT3NByenF1dlprUFMrMUp3NG5nanlpWUFtclVScjBNPQ`.
- Source SHA-256:
  `25f66e96b6bc1966f43fb67cf5edc5547881de2954b7d8bd18274120bf703252`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_circle-tokenized-stock-xstock_bce2171.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_circle-tokenized-stock-xstock.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug circle-tokenized-stock-xstock --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_circle-tokenized-stock-xstock_bce2171.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known broad Drive folder download path started
  before final candidate selection. The run then used the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  Drive file id only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `circle-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `27234d89-1f7d-440e-945d-79c49f5bfbf7`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 27234d89-1f7d-440e-945d-79c49f5bfbf7 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2171" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `6f526c63-efea-4802-a166-fa0baddff107`
  - promoted_at: `2026-06-24T17:35:56.646539+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2171_crclx_econ_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=circle-tokenized-stock-xstock`
  - `project_reports.id=6f526c63-efea-4802-a166-fa0baddff107`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=CRCLx는 1:1 담보형 xStock으로 접근성과 DeFi 조합성은 강하지만, 주주권 부재와 가격 괴리 리스크가 남는다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=27234d89-1f7d-440e-945d-79c49f5bfbf7`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2171_crclx_econ_website_verification.json`.
  KO and EN report/project pages for `circle-tokenized-stock-xstock` returned
  HTTP `200` with `cache-control: private, no-cache, no-store, max-age=0,
  must-revalidate` and contained the promoted summaries plus Investment View.
  The local Python TLS verifier lacked a CA chain, so the HTTP/content
  verification was rerun with certificate verification disabled for the check
  only.
- Pipeline state wiki was updated with this execution evidence. No manifest
  change was needed because execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2170 GUSD Project Metadata Correction (2026-06-25 02:25 KST)

- Wake reason:
  `process_lost_retry` after [BCE-2169](/BCE/issues/BCE-2169) completed the
  `gusd/maturity/ko` summary promotion.
- Workspace/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before data correction:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Diagnosis:
  `tracked_projects.slug=gusd` still displayed `Gemini Dollar` with alias
  `gemini dollar`, while promoted jobs for the same slug target Gate USD:
  - econ job `6a83d86a-531e-49c9-b9e2-299e1c0731ca`
  - maturity job `bbe4f358-3ca0-4e1b-81b4-b593bb960fa4`
- Live market identity check:
  CoinGecko `id=gusd` resolves to GUSD/Gate, while Gemini Dollar resolves to
  `id=gemini-dollar`.
- Data correction:
  `supabase/migrations/20260624172500_fix_gusd_gate_usd_metadata.sql` updates
  only the `tracked_projects` display metadata for `slug=gusd`:
  `name=Gate USD`, `symbol=GUSD`, aliases
  `gusd`, `gate usd`, `gate gusd`, `gateusd`, and default
  `website_url=https://www.gate.com/gusd` when absent.
- Provenance boundary:
  no `project_reports` or `report_summary_jobs` rows were changed; existing
  summary authority job ids, source identities, and promoted report ids remain
  intact.
- Manifest change:
  no change needed. This was a metadata/backfill correction under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2167 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 01:11 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `EUR CoinVertible의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Source identity:
  `drive:1N0EVlVA6OuftBI7sa6LdS_yVdkykxDbt:0B8HYgThT3NByWXpsUEMwMThJN0w5TWpKUVYveklvKzNEQzljPQ`.
- Source SHA-256:
  `7c1be166059571d47e9431b5a322f641213d1d374a66a9ee5946dcac51b89db1`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_eur-coinvertible_bce2167.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_eur-coinvertible.json`.
- Execution note:
  the generic entrypoint dry-run command was attempted first, but the MAT
  slug-filter path began downloading broader folder candidates because the
  Korean maturity filename pattern is not always parsed into the target slug.
  The production candidate was therefore generated through the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  EUR CoinVertible Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `eur-coinvertible`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `a678eabf-060e-4a9b-b238-c378b9537ed1`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id a678eabf-060e-4a9b-b238-c378b9537ed1 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2167" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `8012a7bc-3fbb-4d2f-9f65-366908c3d191`
  - promoted_at: `2026-06-24T16:11:22.389658+00:00`
- Project report verification:
  - `project_reports.id=8012a7bc-3fbb-4d2f-9f65-366908c3d191`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=CoinVertible은 MiCA 준수와 은행 담보 신뢰가 강하지만, 실사용 유동성과 XRPL 감사 공백 검증이 필요하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=a678eabf-060e-4a9b-b238-c378b9537ed1`
- Manifest change:
  no change needed. This was a routine candidate ingest and Summary Authority
  Gate execution under the existing `analysis-md-summary-candidate` contract.

### BCE-2168 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 01:35 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Current Drive/DB metadata scan:
  491 Drive Markdown candidates were scanned across `analysis2` and legacy
  `analysis`; 299 revision source identities remained unpromoted after the
  promoted-source guard. The newest raw unpromoted candidate was the previously
  safety-skipped `GUSD(Gate USD)` MAT source, so this run selected the next
  eligible source with an existing website-visible target.
- Selected Drive Markdown:
  `Slime Miner _ SLIMEX 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1tqKbaF4K0mjSXCSsTdz7_ERk_bH7PjSs:0B8HYgThT3NBybnN2RlU2TytLQjc2eEwrM21xYWlKWXJ5SCtBPQ`.
- Source SHA-256:
  `d9bbe144365d4035898f1606174f8e566af098b10784333c45f6334dd8729738`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_slimex_bce2168.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_econ_slimex_bce2168.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_slimex.json`.
- Candidate ingest command:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type econ --slug slimex --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_econ_slimex_bce2168.json --require-agent-output --limit 1`.
- Candidate ingest result:
  - report type: `econ`
  - slug: `slimex`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `2a01c5cc-e963-43e0-b224-4c85bede343e`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 2a01c5cc-e963-43e0-b224-4c85bede343e --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2168" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `27a4a053-4b07-4ce6-91ee-c44bf6515c97`
  - promoted_at: `2026-06-24T16:34:47.816259+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2168_slimex_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=slimex`
  - `project_reports.id=27a4a053-4b07-4ce6-91ee-c44bf6515c97`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=SLIMEX는 시즌 보상과 모바일 접근성이 강점이나, 오프체인 산정과 공급 투명성이 핵심 리스크다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=2a01c5cc-e963-43e0-b224-4c85bede343e`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2168_slimex_website_verification.json`.
  KO and EN report/project pages for `slimex` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. Local verification used TLS verification
  disabled for the HTTP/content check only.
- Manifest change:
  no change needed. This execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2169 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 02:18 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  491 Drive Markdown candidates were scanned across `analysis2` and legacy
  `analysis`; 298 revision source identities remained unpromoted after the
  promoted-source guard. The newest unpromoted candidate was selected after
  confirming a website-visible `gusd/maturity/ko` target existed.
- Selected Drive Markdown:
  `GUSD(Gate USD)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`.
- Source identity:
  `drive:1nCZ7DX8aYSVGVTlP9C5haNZJisnZoOKd:0B8HYgThT3NByK2MyOCtBellrR0tid2Z3QzE0SUVWVGo1TFlVPQ`.
- Source SHA-256:
  `cf6a89e071c55290601b8887b99d157beb56abaa197d547a05771184c24d743a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_gusd_bce2169.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_gusd_bce2169.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_gusd.json`.
- Execution note:
  the generic CLI dry-run command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug gusd --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_gusd_bce2169.json --require-agent-output --limit 1 --force --dry-run`.
  It was interrupted after more than 90 seconds in broad Drive downloads.
  The production candidate was generated through the same candidate validation,
  upsert, artifact, and telemetry functions against the selected GUSD Drive
  file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `gusd`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `bbe4f358-3ca0-4e1b-81b4-b593bb960fa4`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id bbe4f358-3ca0-4e1b-81b4-b593bb960fa4 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2169" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote_project_report: `true`
  - project_report_id: `890149f4-f875-410e-ade6-6e708603c37f`
- DB verification artifact:
  `scripts/pipeline/output/bce2169_gusd_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=gusd`
  - `tracked_projects.name=Gemini Dollar` at verification time, while the
    selected source and previous GUSD pipeline artifacts are Gate GUSD/Gate USD.
    This metadata naming mismatch is pre-existing and should be corrected
    separately; this routine followed the existing `gusd` source/target
    contract.
  - `project_reports.id=890149f4-f875-410e-ade6-6e708603c37f`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=GUSD는 Gate 유틸리티와 1:1 상환 구조가 강점이나, 준비금 공시와 외부 유동성이 병목이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=bbe4f358-3ca0-4e1b-81b4-b593bb960fa4`
- Website/cache verification:
  - `https://www.bcelab.xyz/ko/projects/gusd` and
    `https://www.bcelab.xyz/en/projects/gusd` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and contained the promoted KO/EN summaries.
  - `https://www.bcelab.xyz/{ko,en}/reports/gusd` returned `404`; the project
    pages are the current website-visible surface for this target.
- Manifest change:
  no change needed. This execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2165 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 00:11 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  `scripts/pipeline` helpers found 491 Drive Markdown candidates, skipped 189
  already-promoted revision source identities, and left 302 unpromoted metadata
  candidates. The newest unpromoted candidate was selected.
- Selected Drive Markdown:
  `Rollbit 크립토 이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1hImcdjI8FsTJu5D7n4tmWOC69NBao0Qv:0B8HYgThT3NByTWFTZTdRd3MxWlZCYXRET3hVSXJpbFYrVk5FPQ`.
- Source SHA-256:
  `fd1b768ba80e04ed5116287a6c468102e6aa1b0b698a1507f246ce595fe02d2f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_rollbit-coin_bce2165.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_rollbit-coin.json`.
- Execution note:
  local `--source-path` dry-run validation passed first. The production
  candidate was generated through the same candidate validation, upsert,
  artifact, and telemetry functions against the selected Rollbit Drive file id
  only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `rollbit-coin`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `c64d732a-36e7-4d08-9b2f-44791e7e2f0c`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id c64d732a-36e7-4d08-9b2f-44791e7e2f0c --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2165" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `4e7568af-9a4e-4816-9268-562f5d770b7b`
- DB verification artifact:
  `scripts/pipeline/output/bce2165_rollbit_coin_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=rollbit-coin`
  - `project_reports.id=4e7568af-9a4e-4816-9268-562f5d770b7b`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=Rollbit RLB는 실제 플랫폼 매출과 소각 구조가 강점이나, 오프체인 회계와 규제 리스크가 크다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=c64d732a-36e7-4d08-9b2f-44791e7e2f0c`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2165_rollbit_coin_website_verification.json`.
  KO and EN report/project pages for `rollbit-coin` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries.
- Manifest change:
  no change needed. This execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2163 CRO Analysis MD Summary JSON Ingestion Routine Duplicate Replay (2026-06-24 23:43 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Duplicate source detected:
  the latest Drive source selected by the routine was the same 0x Protocol
  ECON source already promoted in [BCE-2162](/BCE/issues/BCE-2162).
- Source identity:
  `drive:1D2ELgge9v4dFPTBLdxbFaMP0JgH-YfuR:0B8HYgThT3NByWkVvaG5zTE5tSXh1RGUydVFCUWdBQWVYeURrPQ`.
- Existing promoted job:
  `bfd75e71-d937-4adf-ab6c-9f7ca85fddd3`.
- Existing promoted project report:
  `08a33ed1-9c43-48c0-b4b2-81061628e178`.
- Replay result:
  `report_summary_jobs` upsert returned `updated_existing`, and the Summary
  Authority Gate write path returned `promoted` / `wrote_project_report=true`
  for the same project report id. No new Drive Markdown was identified.
- Current DB state after replay:
  - candidate job remains `authority_state=promoted`,
    `authority_mode=llm_active`, and
    `promoted_project_report_id=08a33ed1-9c43-48c0-b4b2-81061628e178`.
  - promoted report remains `0x/econ/ko`, `status=published`.
- Follow-up opened:
  [BCE-2164](/BCE/issues/BCE-2164) to make the routine skip source identities
  that already have a promoted candidate job and finish with
  `no-op: no new analysis markdown` when no eligible source remains.
- Manifest change:
  no change needed. This was a duplicate routine replay under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2164 Promoted Source Polling Guard (2026-06-24 23:51 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Fix:
  `scripts/pipeline/analysis_md_summary_candidate.py` now loads promoted
  `report_summary_jobs.source_identity` values for the report type and excludes
  those Drive identities during candidate selection before applying `--limit`.
- Manual reprocessing boundary:
  `--force` remains the explicit manual override and includes promoted source
  identities intentionally; normal routine polling must omit `--force`.
- No-op behavior:
  when no unpromoted Drive Markdown candidate remains, the entrypoint prints
  `no-op: no new analysis markdown`, writes the empty artifact, records
  successful zero-count telemetry when available, and exits `0`.
- Regression tests:
  `python3 -m pytest scripts/pipeline/test_analysis_md_summary_candidate.py`
  passed with `11 passed`, covering promoted-source skip before download,
  force override, and the no-op path.
- Manifest change:
  no change needed. This is a candidate-selection/runtime guard under the
  existing `analysis-md-summary-candidate` contract.

### BCE-2162 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-24 23:08 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  `scripts/pipeline` helpers found 491 Drive Markdown candidates and 303
  unpromoted candidates by revision source identity. The newest unpromoted
  candidate was selected.
- Selected Drive Markdown:
  `0x Protocol ZRX 크립토이코노미 설계 분석 보고서.md`.
- Source identity:
  `drive:1D2ELgge9v4dFPTBLdxbFaMP0JgH-YfuR:0B8HYgThT3NByWkVvaG5zTE5tSXh1RGUydVFCUWdBQWVYeURrPQ`.
- Source SHA-256:
  `6b0db134e5b8d55e3113ee430718ee88628a27aa324a4ff447124e86fa880d0f`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_econ_0x_bce2162.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_econ_0x.json`.
- Execution note:
  local `--source-path` dry-run validation passed first. The generic Drive
  entrypoint was then attempted, but it spent more than 60 seconds in broad
  Drive downloads before candidate selection. The production candidate was
  generated through the same candidate validation, upsert, artifact, and
  telemetry functions against the selected 0x Drive file id only.
- Candidate ingest result:
  - report type: `econ`
  - slug: `0x`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `bfd75e71-d937-4adf-ab6c-9f7ca85fddd3`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id bfd75e71-d937-4adf-ab6c-9f7ca85fddd3 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2162" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `08a33ed1-9c43-48c0-b4b2-81061628e178`
  - promoted at: `2026-06-24T14:08:06.325073+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2162_0x_db_verification.json`.
- Project report verification:
  - `tracked_projects.slug=0x`
  - `project_reports.id=08a33ed1-9c43-48c0-b4b2-81061628e178`
  - `report_type=econ`, `language=ko`, `status=published`
  - `card_summary_ko=0x는 다중 유동성 라우팅과 API 인프라 경쟁력이 강하지만, ZRX의 직접 수익 포획은 약하다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=bfd75e71-d937-4adf-ab6c-9f7ca85fddd3`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2162_0x_website_verification.json`.
  KO and EN report/project pages for `0x` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries. The local Python TLS verifier lacked a CA
  chain, so the HTTP/content verification was run with certificate verification
  disabled for the check only.
- Manifest change:
  no change needed. This execution stayed within the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2159 AWE Forensic KO Target Seed Prepared (2026-06-24 22:55 KST)

- Workspace/SHA when reconciled:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context read before reconciliation:
  `knowledge/pipelines/analysis-md-summary-candidate.md`,
  `knowledge/pipelines/for.md`, and `pipelines/bcelab-runtime-pipelines.json`.
- Seed migration:
  `supabase/migrations/20260624132200_seed_awe_network_forensic_ko_summary_target.sql`.
- Target scope:
  create or repair the missing website-visible
  `awe-network/forensic/ko/version:1` target row required by Summary Authority
  Gate job `de5600d2-6b4d-4691-82cd-4d69a08b2a62`.
- Production write boundary:
  this is target seed/backfill data only. It does not invoke
  `summary_authority_gate.py --write`, does not promote the candidate, and does
  not write report summary content to `project_reports`.
- Manifest change:
  no change needed. This remains under the existing
  `analysis-md-summary-candidate` authority gate contract; the active FOR slide
  publishing contract is unchanged.

### BCE-2160 CRO Analysis MD Summary JSON Ingestion Routine Blocked (2026-06-24 22:40 KST)

- 사용 워크스페이스/SHA:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- 실행 전 1차 컨텍스트:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Candidate selection:
  the current Drive/DB scan found the newest unprocessed source as
  `ARX 시장 무결성 및 심층 포렌식 리스크 보고서.md`.
- Source identity:
  `drive:1y_edFrd7AW9I0RwVU7BeTyGohj4uxWG-:0B8HYgThT3NBydHJ3cmdQYjFJUVBwK0hBVXVBVUpWelo4QkxBPQ`.
- Source SHA-256:
  `957a19ae2fbba18dd1a91e4650665a79215367b3a9d53cc7a58fb189036a187a`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_for_arcium_bce2160.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_for_arcium.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type for --slug arcium --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_for_arcium_bce2160.json --require-agent-output --limit 1 --force`.
  Because the forensic Korean filename path can score broader folder candidates
  before slug selection, that command selected the already promoted AWE source
  and inserted an invalid arcium/AWE candidate job
  `c70818f1-47ad-49a2-b047-ad67a7bee594`. The production candidate for this
  run was then generated through the same candidate validation, upsert,
  artifact, and telemetry functions against the selected ARX Drive file id
  only.
- Candidate ingest result:
  - report type: `for` / DB type: `forensic`
  - slug: `arcium`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `0334ab47-dfa6-44ae-aa43-884fcb8d74ae`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0334ab47-dfa6-44ae-aa43-884fcb8d74ae --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2160" --write`.
- Promotion result:
  blocked by Supabase RPC error
  `website-visible project_reports target not found: arcium/forensic/ko`.
- Production DB verification:
  - `tracked_projects.slug=arcium` exists with symbol `ARX`.
  - `project_reports` has `arcium/forensic/en` with status `coming_soon`.
  - no `arcium/forensic/ko` website-visible target row exists.
  - candidate job remains `status=candidate_ready`,
    `validation_status=valid`, `authority_state=validation_passed`, and
    `promoted_project_report_id=null`.
- Required unblock:
  [BCE-2161](/BCE/issues/BCE-2161) must seed/backfill a website-visible
  `arcium/forensic/ko` target row, then CRO should rerun the existing valid
  candidate job promotion.
- Manifest change:
  no change needed. This is target data/backfill under the existing
  `analysis-md-summary-candidate` and `summary_authority_gate` contracts.

### BCE-2160 CRO Analysis MD Summary JSON Ingestion Routine Promoted (2026-06-24 22:46 KST)

- Resume reason:
  `issue_children_completed` after [BCE-2161](/BCE/issues/BCE-2161)
  completed the missing target-row backfill.
- Workspace/SHA at resume:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before promotion:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Unblock evidence from [BCE-2161](/BCE/issues/BCE-2161):
  - migration:
    `supabase/migrations/20260624134500_seed_arcium_forensic_ko_summary_target.sql`
  - production target row:
    `project_reports.id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`,
    `report_type=forensic`, `language=ko`, `version=1`,
    `status=coming_soon`.
  - dry-run Summary Authority Gate result before CRO resume:
    `dry_run=true`, action `promote`, `wrote_project_report=false`,
    `project_report_id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`.
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 0334ab47-dfa6-44ae-aa43-884fcb8d74ae --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2160" --write`.
- Promotion result:
  - decision action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `5be04e6d-7126-4224-8153-2f1cfc58e4b5`
  - promoted at: `2026-06-24T13:46:28.719494+00:00`
- DB verification after promotion:
  - candidate job `0334ab47-dfa6-44ae-aa43-884fcb8d74ae` now has
    `authority_state=promoted`, `authority_mode=llm_active`, and
    `promoted_project_report_id=5be04e6d-7126-4224-8153-2f1cfc58e4b5`.
  - promoted report `card_summary_ko`:
    `ARX는 상장 초기 거래량이 체인 유동성을 크게 앞서며, 고점 후퇴와 얕은 호가로 조작 리스크가 높다.`
  - promoted report `marketing_content_by_lang.ko`:
    `투자 관점에서는 ARX가 0.325와 0.347 회복을 확인하기 전까지 추격 매수를 피하고 0.284 이탈을 경계해야 한다.`
  - `card_data.summary_authority.mode=llm_active` with the same job id,
    idempotency key, source identity, and promoted timestamp.
- Website/cache verification:
  - KO/EN report and project URLs for `arcium` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - The promoted report row remains `status=coming_soon`; current public HTML
    did not render the promoted summary text during this check. The promotion
    updated Supabase `project_reports` directly through the Summary Authority
    Gate RPC, and no repo deploy was required.
- Manifest change:
  no change needed. This was target data plus Summary Authority Gate execution
  under the existing `analysis-md-summary-candidate` contract.

### BCE-2173 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 03:45 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Slime Miner _ SLIMEX의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1yA0C1Gp160eXMQX2To75VZxP3kNgjE_o:0B8HYgThT3NByeHdQdE85LzhnK0EyVmNZeEF5dkJ2RTdVMUNBPQ`.
- Source SHA-256:
  `a6a589a4f956996ed54775793ad91aafbfbd3e70ecb23791d51c176152114644`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_slimex_bce2173.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_slimex.json`.
- Execution note:
  the generic entrypoint's slug-filter path attempted broader MAT folder
  downloads, so this run used the same candidate validation, upsert, artifact,
  and telemetry functions against the selected SLIMEX Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `slimex`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `9bc3e1ee-766e-4a47-90f2-b047b6c58e56`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 9bc3e1ee-766e-4a47-90f2-b047b6c58e56 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2173" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `b2579ad0-3ae7-45d2-abe7-bb2ccfb821a1`
  - promoted at: `2026-06-24T18:44:26.019599+00:00`
- Project report verification:
  - `project_reports.id=b2579ad0-3ae7-45d2-abe7-bb2ccfb821a1`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=SLIMEX는 게임 견인력은 높지만, 보상 경제와 온체인 검증성이 미성숙해 성숙도는 61.7점에 그친다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=9bc3e1ee-766e-4a47-90f2-b047b6c58e56`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/slimex/maturity` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`
    and rendered the promoted English text.
  - `https://www.bcelab.xyz/en/projects/slimex` returned HTTP `200` with the
    same cache policy and rendered the promoted MAT report card text.
  - The promotion updated Supabase `project_reports` directly through the
    Summary Authority Gate RPC, and no repo deploy was required.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2176 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 05:31 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `MYX Finance의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2023 - 2026.md`.
- Source identity:
  `drive:1wPnSga4AHlEdKUCp0ziMzlY8Jsa9YW3m:0B8HYgThT3NBycHhRRzR6QW9KalpFcU5EOTR3WS93aW1QSVNrPQ`.
- Source SHA-256:
  `9e24c94d625c9d569dbbe6566591b2008ec458698b98320e1245c3cc0ea8b26e`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_myx-finance_bce2176.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_myx-finance.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug myx-finance --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_myx-finance_bce2176.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  folder downloads before candidate selection. The run then used the same
  candidate validation, upsert, artifact, and telemetry functions against the
  selected MYX Finance Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `myx-finance`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `876dc087-0af5-4b1b-85e2-29a5ffd21013`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 876dc087-0af5-4b1b-85e2-29a5ffd21013 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2176" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `31829b10-aeb3-42fe-bdfc-a50b2db60d8f`
  - promoted at: `2026-06-24T20:31:47.254441+00:00`
- DB verification artifact:
  `scripts/pipeline/output/bce2176_myx_finance_db_verification.json`.
- Project report verification:
  - `project_reports.id=31829b10-aeb3-42fe-bdfc-a50b2db60d8f`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=MYX Finance는 거래량 효율은 높지만 수익 포착, Keeper 투명성, 거버넌스 성숙도는 아직 검증 단계다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=876dc087-0af5-4b1b-85e2-29a5ffd21013`
- Website/cache verification artifact:
  `scripts/pipeline/output/bce2176_myx_finance_website_verification.json`.
  KO and EN report/project pages for `myx-finance` returned HTTP `200` with
  `cache-control: private, no-cache, no-store, max-age=0, must-revalidate` and
  contained the promoted summaries and Investment View text. The local Python
  TLS verifier lacked a CA chain, so the HTTP/content verification was rerun
  with certificate verification disabled for the check only.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2174 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 04:08 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `INTCx(Intel xStock)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025–2026.md`.
- Source identity:
  `drive:1oP28EeRwR_CMsHo520TcjW71a4ozmU2X:0B8HYgThT3NByQUxvdHp0U21CWDNwZjkrdzVXa2lxWFQ2UU5VPQ`.
- Source SHA-256:
  `41477f6e7913546a309c12808db86eca2c0d325e09da28365d821d1aaa372f30`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_intel-tokenized-stock-xstock_bce2174.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_intel-tokenized-stock-xstock.json`.
- Execution note:
  the full helper scan was interrupted after it spent several minutes
  downloading all candidate Markdown bodies. The production candidate used the
  same candidate validation, upsert, artifact, and telemetry functions against
  the selected INTCx Drive file id only, after a metadata scan excluded
  promoted source identities.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `intel-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `fe5e8d95-6bf5-4742-a76d-96cf8b1be13f`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id fe5e8d95-6bf5-4742-a76d-96cf8b1be13f --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2174" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `236955d6-2737-44a2-9e0c-d431b457a631`
  - promoted at: `2026-06-24T19:08:23.448558+00:00`
- Project report verification:
  - `project_reports.id=236955d6-2737-44a2-9e0c-d431b457a631`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=INTCx는 법률, 담보, 멀티체인 구조는 작동하지만 유동성과 DeFi 담보 채택이 약해 성숙도는 65.3점이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=fe5e8d95-6bf5-4742-a76d-96cf8b1be13f`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/intel-tokenized-stock-xstock/maturity`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate` and rendered the promoted English text.
  - `https://www.bcelab.xyz/en/projects/intel-tokenized-stock-xstock`
    returned HTTP `200` with the same cache policy and rendered the promoted
    MAT report card text.
  - The promotion updated Supabase `project_reports` directly through the
    Summary Authority Gate RPC, and no repo deploy was required.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2175 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 04:41 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Latest unprocessed/changed Drive Markdown selected by metadata scan:
  `Marvell xStock(MRVLx)의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025-2026.md`.
- Source identity:
  `drive:1uo_mzJ7qYKDcRdrfuBW8LwI9SJMjJ-dP:0B8HYgThT3NByMDFTZVZqRkxGS09XL3BUckpVdWJHS0pQV0hRPQ`.
- Source SHA-256:
  `e5eca19fa6f2a548cf721cbcdf52ab755b5cd5dca89601a451a32aea379ea016`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_marvell-tokenized-stock-xstock_bce2175.json`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_marvell-tokenized-stock-xstock.json`.
- Execution note:
  the generic entrypoint's slug-filter path attempted broader MAT downloads
  because Korean MAT filenames are not always parsed into slugs, so this run
  used the same candidate validation/upsert/artifact functions against the
  selected Marvell xStock Drive file id only after metadata scan excluded
  promoted source identities.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `marvell-tokenized-stock-xstock`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `20de48bc-3407-4048-bfb7-30352303f2d9`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 20de48bc-3407-4048-bfb7-30352303f2d9 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2175" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `fe8c1f7d-d0dd-4031-9af9-cc6a861a551e`
  - promoted at: `2026-06-24T19:41:00.439517+00:00`
- Project report verification:
  - `project_reports.id=fe8c1f7d-d0dd-4031-9af9-cc6a861a551e`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=MRVLx는 1:1 담보와 멀티체인 발행은 갖췄지만, 개별 DEX 유동성은 아직 얕은 전개 단계 RWA다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=20de48bc-3407-4048-bfb7-30352303f2d9`
- Website/cache verification:
  - `https://www.bcelab.xyz/en/reports/marvell-tokenized-stock-xstock/maturity`
    returned HTTP `200` with `cache-control: private, no-cache, no-store,
    max-age=0, must-revalidate` and rendered the promoted English text.
  - `https://www.bcelab.xyz/en/projects/marvell-tokenized-stock-xstock`
    returned HTTP `200` with the same cache policy and rendered the promoted
    MAT report card text.
  - The promotion updated Supabase `project_reports` directly through the
    Summary Authority Gate RPC, and no repo deploy was required.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2177 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 06:07 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  assigned execution issue with no pending comments; harness had already
  checked out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  286 unpromoted metadata candidates remained after excluding promoted source
  identities. The newest eligible candidate with a website-visible KO target row
  was selected.
- Selected Drive Markdown:
  `WeFi의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2024 - 2026.md`.
- Source identity:
  `drive:1S-miHHiZ_69Q6Tj573xY0Blf3Yl9Xnoh:0B8HYgThT3NByVUpVK2YzZXptKzdXTWMxbXNhbjJ4LzA2aEdjPQ`.
- Source SHA-256:
  `eb23f12b8cb958d802d214d33d76fdb3f98ec7fc6db382178b85c16b3d2dd14d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_wefi_bce2177.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_wefi_bce2177.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_wefi.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug wefi --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_wefi_bce2177.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known MAT Korean filename path began broad
  folder downloads. The production candidate then used the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  WeFi Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `wefi`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `eb88e5f6-c134-4fb9-8e9f-606e75951acf`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id eb88e5f6-c134-4fb9-8e9f-606e75951acf --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2177" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `24007844-e84a-4f2c-b798-4caf4be875cb`
  - promoted at: `2026-06-24T21:07:31.967537+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2177_wefi_db_website_verification.json`.
- Project report verification:
  - `project_reports.id=24007844-e84a-4f2c-b798-4caf4be875cb`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=WeFi는 Deobank 결제 서사는 강하지만, 온체인 검증성과 거버넌스 투명성이 부족해 성숙도는 55점에 머문다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=eb88e5f6-c134-4fb9-8e9f-606e75951acf`
- Website/cache verification:
  - KO and EN report/project pages for `wefi` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0, must-revalidate`.
  - KO pages contained the promoted Korean summary.
  - EN pages contained the promoted English summary and Investment View text.
  - The local Python TLS verifier lacked a CA chain, so the HTTP/content
    verification was rerun with certificate verification disabled for the check
    only.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2178 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 06:40 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  process-lost retry with no pending comments; the harness had already checked
  out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  290 unpromoted metadata candidates remained after excluding promoted source
  identities. The newest eligible candidate with a website-visible KO target
  row was selected.
- Selected Drive Markdown:
  `48 Club의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2017–2026.md`.
- Source identity:
  `drive:1MHsTOZ0OZxvqMevfWMtFYGlvGAhvLuaL:0B8HYgThT3NByMHFOUFJVQVJ2TFhKZ3hUOXZYZVBwdzNwTVZBPQ`.
- Source SHA-256:
  `6bd1835282d8f2330c975a7012415c9583ec19c268a59c1718595d6c3fa9265d`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_bnb48-club-token_bce2178.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_bnb48-club-token_bce2178.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_bnb48-club-token.json`.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `bnb48-club-token`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `inserted`
  - job id: `8a32e6af-89a5-45d3-828f-15e65c1cbf70`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 8a32e6af-89a5-45d3-828f-15e65c1cbf70 --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2178" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `5bcda7f8-bc36-41d6-979d-27d56bea0896`
  - promoted at: `2026-06-24T21:40:03.572801+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2178_bnb48_club_token_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=bnb48-club-token`
  - `tracked_projects.symbol=KOGE`
  - `project_reports.id=5bcda7f8-bc36-41d6-979d-27d56bea0896`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=48 Club은 BNB Chain MEV 인프라 점유율이 높지만, 재무와 거버넌스 투명성 보완이 필요한 성숙 초입 프로젝트다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=8a32e6af-89a5-45d3-828f-15e65c1cbf70`
- Website/cache verification:
  - KO and EN report/project pages for `bnb48-club-token` returned HTTP `200`
    with `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO pages contained the promoted Korean summary.
  - EN pages contained the promoted English summary and Investment View text.
  - The local Python TLS verifier lacked a CA chain, so the HTTP/content
    verification was rerun with certificate verification disabled for the check
    only.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.

### BCE-2179 CRO Analysis MD Summary JSON Ingestion Routine (2026-06-25 07:10 KST)

- Workspace/SHA used:
  `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
  at `13d4d03`.
- Primary context checked before execution:
  `knowledge/pipelines/analysis-md-summary-candidate.md` and
  `pipelines/bcelab-runtime-pipelines.json`.
- Wake context:
  issue-assigned wake with no pending comments; the harness had already checked
  out the issue, so no duplicate checkout was made.
- Current Drive/DB metadata scan:
  289 unpromoted Drive file ids remained after excluding promoted source file
  ids. The newest eligible candidate with a website-visible KO target row was
  selected.
- Selected Drive Markdown:
  `Keeta의 크립토 이코노미 발전 단계 및 서사 진화 평가 보고서_ 2025 - 2026.md`.
- Source identity:
  `drive:1QY7EGuw2_gQx6RrZDjB97Ur1Ip3YuYUt:0B8HYgThT3NByRytlVzFncnBDMHgzZ3JmRXI1dUd1MFVQcGpjPQ`.
- Source SHA-256:
  `b2ae4757e333d05d5c6a97e3b5cc1b41b6160238a60358a2b1f63e6fdaa44987`.
- Paperclip CRO JSON output:
  `scripts/pipeline/output/paperclip_cro_summary_mat_keeta_bce2179.json`.
- Source snapshot:
  `scripts/pipeline/output/paperclip_cro_source_mat_keeta_bce2179.md`.
- Candidate artifact:
  `scripts/pipeline/output/analysis_md_summary_candidate_mat_keeta.json`.
- Execution note:
  the generic entrypoint command was attempted first:
  `python3 scripts/pipeline/analysis_md_summary_candidate.py --type mat --slug keeta --drive-root-scope all --agent-output-json scripts/pipeline/output/paperclip_cro_summary_mat_keeta_bce2179.json --require-agent-output --limit 1 --force`.
  It was interrupted after the known broad Drive candidate download path ran for
  more than two minutes. The production candidate then used the same candidate
  validation, upsert, artifact, and telemetry functions against the selected
  Keeta Drive file id only.
- Candidate ingest result:
  - report type: `mat` / DB type: `maturity`
  - slug: `keeta`
  - validation status: `valid`
  - validation reasons: none
  - upsert result: `updated_existing`
  - job id: `53f55bc4-d5d9-4c3c-9c11-4369a1c66a2d`
- Summary Authority Gate write command:
  `python3 scripts/pipeline/summary_authority_gate.py --job-id 53f55bc4-d5d9-4c3c-9c11-4369a1c66a2d --authority-mode llm_active --actor "paperclip-routine:CRO:BCE-2179" --write`.
- Promotion result:
  - action: `promote`
  - state: `promoted`
  - wrote project report: `true`
  - project report id: `d35f3295-b290-455a-bfb9-18a1d434c62c`
  - promoted at: `2026-06-24T22:10:32.566798+00:00`
- DB and website verification artifact:
  `scripts/pipeline/output/bce2179_keeta_db_website_verification.json`.
- Project report verification:
  - `tracked_projects.slug=keeta`
  - `tracked_projects.symbol=KTA`
  - `project_reports.id=d35f3295-b290-455a-bfb9-18a1d434c62c`
  - `report_type=maturity`, `language=ko`, `status=published`
  - `card_summary_ko=Keeta는 금융 결제와 토큰화 서사가 강하지만, 메인넷 사용량·TVL·거버넌스 공개가 아직 초기라 성숙도는 제한적이다.`
  - `card_data.summary_authority.mode=llm_active`
  - `card_data.summary_authority.job_id=53f55bc4-d5d9-4c3c-9c11-4369a1c66a2d`
- Website/cache verification:
  - KO and EN report/project pages for `keeta` returned HTTP `200` with
    `cache-control: private, no-cache, no-store, max-age=0,
    must-revalidate`.
  - KO pages contained the promoted Korean summary.
  - EN pages contained the promoted English summary and Investment View text.
  - The local Python TLS verifier used certificate verification disabled for
    the content check only because the local CA chain may be unavailable.
- Manifest change:
  no change needed. This was a routine execution under the existing
  `analysis-md-summary-candidate` contract.
