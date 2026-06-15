# BCELab Website Development and Operations

Manifest key: `bcelab-website-development-and-operations`
Paperclip pipeline: `BCELab Website Development and Operations`
Owner: CTO
Status: active
Last reconciliation: 2026-05-14

## Operating Definition

This pipeline governs website changes and production deployment for the
Blockchain Economics Lab website.

- Intake: Paperclip issue-based change request.
- Implementation: isolated branch or temporary workspace.
- Definition alignment: `scripts/verify-website-pipeline.mjs` through `.github/workflows/ci.yml`.
- Quality and build verification: `.github/workflows/ci.yml`.
- Deployment approval: Paperclip plus GitHub production environment approval.
- Production deployment: `.github/workflows/production-deploy.yml`.
- Post-deploy monitoring: Vercel cron route `/api/cron/heartbeat`.

## Report Visibility Baseline

As of PR #60 / commit `a16addc1`, agents must treat the website report
visibility baseline as follows:

- `reportSupportsLocale` is the canonical website report exposure policy.
- Google Drive/PDF assets are valid report exposure evidence.
- `slide_html_urls_by_lang` is a preferred rendering asset, not the general
  website visibility gate.
- Pipeline, report, and website diagnostics must use `a16addc1` or a later
  production baseline before comparing current behavior to prior fixes.

## BCE-1894 Scoreboard Availability Boundary

As of 2026-05-14, `/[locale]/score` reads report badge availability through a
server-only Supabase service-role boundary and still applies
`reportSupportsLocale` before exposing badges. This keeps `project_reports` RLS
private for anon clients while allowing scoreboard badges to reflect
website-visible `published`, `coming_soon`, and `in_review` report rows that
have localized Google Drive/PDF/file/slide assets.

## BCE-1896 Production Deploy Hang

As of 2026-05-14, production deploy runs for BCE-1893 at commit
`671faba1360f2be7a2838ce1490106c8da6006d6` repeatedly passed deployment
evidence verification but hung in the `amondnet/vercel-action@v25` Vercel
production deployment step before a GitHub production deployment success status
was emitted. The workflow now uses the Vercel CLI `pull`, `build`, and
`deploy --prebuilt --prod` path with explicit job and step timeouts so future
production deploy attempts fail closed instead of remaining indefinitely
in-progress.

## BCE-1911 Production Deploy Evidence

As of 2026-05-15, BCE-1911 deployed the board-approved BCE-1906 release commit
`e33f14e31c0dbab1780615acfade3fb6551b1d70` from PR #64 branch
`bce-1909-bce-1906-clean-release` through `.github/workflows/production-deploy.yml`.
The workflow used `expected_commit` to fail closed if the selected SHA differed
from the approved commit.

- Paperclip approval: `29e707ac-af14-4b99-b6d7-553fbfc976b0`.
- GitHub Actions run: `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/25918509079`.
- Vercel production deployment URL: `https://blockchain-economics-nk4tbfe9z-michael-zhangs-projects-df54ac7d.vercel.app`.
- Production alias: `https://www.bcelab.xyz`.
- Remote verification passed in the deploy workflow: `npm run verify:pipeline`,
  `npm run verify:runtime-pipelines`, `npx tsc --noEmit`, `npm test -- --passWithNoTests`,
  and `npm run build`.
- Post-deploy read verification covered `/en/reports`, `/en/score`,
  `/en/projects/pump-fun`, and `/en/reports/pump-fun/maturity`.

## BCE-1922 Latest Report Cover Boundary

As of 2026-05-23, the homepage latest-report showcase depends on
`project_reports.product_id -> products.cover_image_url`. The report publishing
pipeline now uploads first-page slide cover images to the public `slides` bucket
at `{type}/{slug}/{version-or-latest}/{lang}-cover.jpg` and updates the linked
product cover during `website_publish`.

Existing rows are handled by
`scripts/backfill-report-cover-image-urls.ts`, which defaults to dry-run and
must be applied only through the approved remote production-write path. Local
dry-run evidence at checkout `c7666ba` found 1 candidate:
Uniswap MAT/en product `b195234f-cbbb-4cd6-b696-f065054d911d`.

As of BCE-1923, approved report cover backfills have a dedicated manual GitHub
Actions execution surface at `.github/workflows/report-cover-backfill.yml`.
The workflow runs in the `production` environment, defaults to `dry_run`, reuses
the existing Supabase production secrets, and requires a project `slug` when
`mode=apply` so production writes stay scoped to the board-approved target.
For the BCE-1922 one-row backfill, dispatch `mode=dry_run`, `report_type=maturity`,
and `slug=uniswap` first; dispatch `mode=apply` only after approval covers that
same target.

## BCE-1928 Next.js Build Environment Boundary

As of 2026-05-24, the website build gate must force `NODE_ENV=production` in
the `npm run build` script before invoking `next build`. Local Paperclip
heartbeats can inherit `NODE_ENV=development`; with Next.js 16.2.2 and React
19.2.4 that environment caused App Router prerendering of generated error/404
routes to fail with `Cannot read properties of null (reading 'useContext')`.
The executable pipeline manifest still runs the website quality gate through
`npm run build`; `scripts/verify-website-pipeline.mjs` accepts this production
environment prefix as part of the build script contract.

## BCE-1933 Report Card Summary Boundary

As of 2026-06-01, website report cards should receive concise, card-specific
summary copy from the report publishing pipeline instead of relying on the first
available report body sentences. The semantic quality gate lives in
`scripts/pipeline/marketing_content_pipeline.py`; frontend cleanup remains a
last-resort display defense only.

Backfills must use `scripts/pipeline/backfill_card_summaries.py` in dry-run
first and keep the generated diff audit artifact. Approved remote execution is
available through `.github/workflows/report-card-summary-backfill.yml`.
Production writes remain remote-only and require approval plus slug-scoped
`mode=apply`.

## BCE-1937 Report Card Auxiliary Text Boundary

As of 2026-06-02, website report cards treat `Investment View` /
`marketing_content_by_lang` as short card-visible copy, not as unrestricted
body excerpt text. `src/lib/report-marketing-content.ts` cleans and suppresses
unsafe auxiliary text that contains LaTeX/math tokens, raw markdown, table/code
fragments, formula fragments, or excessive excerpt length. This display guard is
a last-resort defense for existing rows; the primary generation gate remains in
`scripts/pipeline/marketing_content_pipeline.py`.

## BCE-1939 Report Card Insight Boundary

As of 2026-06-02, website report cards depend on `card_summary_v2` output from
the report publishing pipeline for semantic insight quality. The website layer
does not rewrite weak summaries; the pipeline must reject definitions,
methodology/table fragments, internal prompt/template leakage, and raw fallback
source text before persistence.

Backfills remain dry-run first through `scripts/pipeline/backfill_card_summaries.py`
or the approved remote workflow. Production writes are still remote-only and
approval-gated.

## BCE-1959 Exchange Listing Boundary

As of 2026-06-15, exchange pages and `/api/exchanges` depend on normalized
`exchanges` and `exchange_project_listings` tables, introduced by
`supabase/migrations/20260615_add_exchange_listing_model.sql`. The website API
counts distinct active `tracked_projects` joined through active exchange
listings and active exchanges. Average BCE Score excludes null
`tracked_projects.maturity_score` values and returns null when no listed
project has a score.

The production Supabase schema checked during BCE-1959 implementation did not
yet expose `public.exchanges` or `public.exchange_project_listings`; it only
had the older referral-oriented `exchange_referrals` table. Real exchange count
and average-score evidence therefore requires the migration to be applied
through the approved remote path and a scoped listing backfill before release
approval can cite representative venue counts.

## BCE-1963 Exchange Page Contract and Migration No-Go

As of 2026-06-15, the exchange list and detail pages must use
`src/lib/repositories/exchanges.ts` and the normalized `exchanges` /
`exchange_project_listings` contract. They must not fall back to the legacy
`tracked_projects.category ilike %exchange%` token-category path.

Local verification at workspace
`/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
and SHA `910031e` confirmed the connected Supabase schema cache still lacks
`public.exchange_project_listings`; `/api/exchanges` and representative detail
APIs therefore return HTTP 500 until the migration is applied. Production
release is no-go while this condition remains.

Migration and backfill path:

- Local/dev: apply `supabase/migrations/20260615_add_exchange_listing_model.sql`
  to a local Supabase database or disposable development database, then run a
  dry-run listing backfill that reports exchange row count, distinct listed
  projects, and average BCE Score for at least two representative venues.
- Remote/prod: production writes must follow the manifest remote-first policy.
  Apply the migration only through the approved remote Supabase migration path
  after board/release approval, then run a scoped service-role backfill.
- Initial backfill: use `.github/workflows/exchange-listing-backfill.yml`.
  The workflow runs in the GitHub `production` environment, defaults to
  `dry_run`, validates a comma-separated CoinGecko exchange-id scope, uploads a
  log artifact, and invokes `scripts/backfill-exchange-listings.ts`.
  The script reads production `tracked_projects`, fetches CoinGecko
  `/exchanges/{id}/tickers` as the production-available listing source, seeds
  canonical `exchanges` rows, and upserts one active
  `exchange_project_listings` row per exchange/project. Duplicate ticker pairs
  collapse to one project listing; inactive/delisted exchanges/listings and
  archived projects remain excluded by the API aggregation contract. Verify
  `/api/exchanges`, two `/api/exchanges/{slug}/projects` endpoints,
  `/ko/exchanges`, and two `/ko/exchanges/{slug}` pages before resuming release
  validation.

## BCE-1938 Production Deployment Evidence

As of 2026-06-02 07:55 KST, BCE-1937/BCE-1938 was deployed through
`.github/workflows/production-deploy.yml` at expected commit
`8a7ab63b8d7be1c64c2325867fc17812ffd8a70a`.

Evidence:

- Production deploy:
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26786922309`
  completed successfully. Remote verification passed report publication policy,
  pipeline verifier, runtime pipeline manifest, TypeScript, full Jest suite, and
  production build.
- Vercel production URL:
  `https://blockchain-economics-16w9n8urt-michael-zhangs-projects-df54ac7d.vercel.app`.
- Production alias and Vercel URL returned HTTP 200 for
  `/ko/projects/hyperliquid`. Rendered HTML/text verification found `px i`,
  `round(px`, `\times`, and `{i-1}` absent. The remaining `투자 관점` label
  rendered safe natural-language copy: `리스크: HyperEVM 앱 생태계가 실제 수요를 만들지 못하면, 시장은 Hyperliquid를 “수익성 높은 perp DEX”로만 재평가할 수 있다.`

## BCE-1869 Relationship

BCE-1869 affected the report-publishing watcher boundary, not this website
operations pipeline. This page exists because the runtime manifest and
Paperclip pipeline metadata both need a durable state page for every active
pipeline.
