# X Promo Manual Post

Manifest key: `x-promo-manual-post`
Paperclip pipeline: `X Promo Manual Post`
Owner: CMO
Status: active
Last reconciliation: 2026-06-25

## Operating Definition

This pipeline prepares and optionally posts manually approved promotional copy
to X for already published BCELab report rows.

- Runtime workflow: `.github/workflows/x-promo-manual-post.yml`.
- Runtime entrypoint: `scripts/pipeline/x_promo_pipeline.py`.
- Production input: Supabase `project_reports` rows that already contain
  card-safe `marketing_content_by_lang` or summary fallback copy.
- Local execution: dry-run, development, and incident reproduction only.
- Production posting: remote GitHub Actions workflow dispatch only, with exact
  `confirm_slug`, exact `confirm_key`, and `post=true`.
- Secrets boundary: real posting requires X API key/secret and access
  token/secret from GitHub Secrets. Secret values must never be copied into
  Paperclip comments, logs, or repo files.

## Nodes

1. `approval_queue_generation` / Build approval queue:
   `.github/workflows/x-promo-manual-post.yml` runs
   `scripts/pipeline/x_promo_pipeline.py --source supabase --write-queue`.
2. `manual_row_approval` / Approve exactly one queue row:
   workflow inline Python matches `confirm_slug` and `confirm_key`; it must find
   exactly one row before any dry-run or post step can continue.
3. `selected_post_dry_run` / Dry-run selected row:
   workflow runs `scripts/pipeline/x_promo_pipeline.py --queue-jsonl ...`
   without `--post` when `post=false`.
4. `selected_real_post` / Post selected row to X:
   workflow runs `scripts/pipeline/x_promo_pipeline.py --post --confirm
   <slug> --confirm-key <duplicate_key>` only when `post=true`.
5. `artifact_upload` / Upload approval and post logs:
   workflow uploads queue and post-attempt artifacts for review.

## Operational Guardrails

- Queue rows start as `pending_manual_approval`; a sender must only consume rows
  changed to `approved`.
- Real posting is single-row by default. If `confirm_slug` plus `confirm_key`
  does not identify exactly one approved row, the workflow fails before any X
  API call.
- Dry-run selected posts do not require X credentials and do not write the post
  log.
- `data/x-post-attempts.jsonl` records every real post attempt/result, and
  duplicate `duplicate_key` rows with a prior `posted` result are skipped.
- If X Developer Console, OAuth permission, access token, or GitHub Secrets
  state is uncertain, run only dry-runs until a secret-free credential status
  report confirms readiness.

## BCE-1825 Readiness Boundary

As of 2026-06-25, `BCE-1825` cannot close real-post readiness until
`BCE-1824` provides a secret-free confirmation of:

- X Developer Console tier.
- OAuth permission of `Read and write` or stronger.
- Access token regeneration or reconfirmation.
- GitHub Secrets update or reconfirmation.
- Workflow rerun readiness.

This page restores the missing state wiki context for the active workspace. It
does not by itself certify external X credentials or authorize a real post.
