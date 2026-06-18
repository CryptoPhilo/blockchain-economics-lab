# X Promo Manual Post

Manifest key: `x-promo-manual-post`
Paperclip pipeline: `X Promo Manual Post`
Owner: CMO
Status: active
Last reconciliation: 2026-06-19

## Operating Definition

This pipeline governs manual X promotion posting for published BCE Lab reports.
It is intentionally manual and confirmation-gated because it can write to an
external social channel.

- Queue generation runs through `.github/workflows/x-promo-manual-post.yml`.
- The workflow requires an exact `confirm_key` and `confirm_slug` pair.
- The `post` input defaults to `false`, so dispatches are dry-run unless the
  board-approved operator explicitly enables posting.
- The posting implementation is `scripts/pipeline/x_promo_pipeline.py`.
- Approval and post evidence are uploaded as `x-promo-manual-post-*` artifacts.

## Safety Boundary

Local execution may be used for dry-run, development, and incident reproduction
only. Production queue reads and X posting must run through the GitHub Actions
workflow with production secrets and explicit single-row confirmation. Do not add
a bulk-post path or local production posting path to the manifest.
