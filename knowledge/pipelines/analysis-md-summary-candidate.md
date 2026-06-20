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
