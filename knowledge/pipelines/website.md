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

## BCE-1971 Exchange Pages Production Deployment Evidence

As of 2026-06-15, PR #203 deployed the exchange list/detail pages and exchange
APIs to Vercel production after the production exchange listing migration and
scoped `binance,gdax` backfill were completed.

- Paperclip deployment approval:
  `28077e9b-7d61-4ca5-90c2-d507dceccc08`.
- BCE-1945 single-GitHub-account waiver:
  `08b7c9f6-dc58-470a-a8f3-b19a279c996a`.
- PR #203 merge commit on `main`:
  `a6161e1764912cc9286b4de5feb0e2064e252035`.
- The approved PR head `49ac038fc16e8fefc99c9dd73b03bf9ea324cdbd` and merged
  main commit have the same Git tree:
  `2bf85e86f467e70f1e4f52dbccfaf4da1dffed79`.
- Production deploy workflow:
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/27534546339`.
- Vercel production deployment URL:
  `https://blockchain-economics-o8qhpdq1c-michael-zhangs-projects-df54ac7d.vercel.app`.
- Production alias: `https://www.bcelab.xyz`.
- Remote verification passed in the deploy workflow: report publication policy,
  pipeline verifier, runtime pipeline manifest, TypeScript, test suite, and
  production build.
- Post-deploy production verification returned HTTP 200 for `/api/exchanges`,
  `/api/exchanges/gdax/projects`, `/api/exchanges/binance/projects`,
  `/ko/exchanges`, `/en/exchanges`, `/ko/exchanges/gdax`, and
  `/ko/exchanges/binance` on both the Vercel deployment URL and
  `https://www.bcelab.xyz`.
- `/api/exchanges` reported `binance` with 55 listed projects, average BCE Score
  65.05, and 47 scored projects; `gdax` reported 76 listed projects, average
  BCE Score 65.38, and 62 scored projects.
- Detail APIs reported 55 Binance rows and 76 Coinbase Exchange rows.

## BCE-1978 Exchange Top 30 CoinGecko Rate-Limit Recovery

As of 2026-06-15, the approved exchange listing backfill retries recoverable
CoinGecko ticker fetch failures before failing a mapped venue. The script
honors bounded `Retry-After` delays and retries HTTP 429, 408, and 5xx
responses up to four attempts per exchange ticker page.

`.github/workflows/exchange-listing-backfill.yml` exposes
`request_delay_ms`, defaulting to 2500 milliseconds, so Top 30 public API
dry-run/apply dispatches can slow request pacing even when `COINGECKO_API_KEY`
is blank. `pipelines/bcelab-runtime-pipelines.json` documents this input under
the `exchange_listing_backfill` node. Production writes remain remote-only:
dispatch `mode=dry_run` first, then `mode=apply` only after the relevant
release/backfill approval covers the same scope.

## BCE-1979 Exchange Top 30 Partial Apply Continuation

As of 2026-06-15, CMC Top 30 exchange listing backfill apply is tolerant of
partial progress when a mapped CoinGecko venue exhausts recoverable HTTP 429,
408, or 5xx retries after the BCE-1978 retry policy. In `--cmc-top30` mode, the
script records the venue as a skipped listing fetch, preserves the seeded CMC
exchange row/evidence at zero listings, and continues processing remaining Top
30 venues.

Explicit scoped `--exchange` backfills remain fail-fast on fetch exhaustion.
The stdout evidence summary reports seeded exchange count, listing-backfilled
exchange count, fetch-failed/skipped exchange count, and skipped exchange slugs
with reasons.

## BCE-1975 Top 30 Remote Backfill Evidence

As of 2026-06-15, the BCE-1972/BCE-1974 exchange release candidate is merged
through PR #206, PR #207, PR #208, and PR #210. The accepted main commit for the
Top 30 continuation fix is `c6777693f2bb9917c4eae35b3ef8425a61da19fb`.

Remote exchange listing backfill evidence:

- Dry-run `27550608987` ran on `main` at `c677769`, with `mode=dry_run`,
  `seed_cmc_top30=true`, `page_limit=1`, and `request_delay_ms=10000`.
  It completed successfully with `Seeded exchange count: 30`,
  `Listing backfilled exchange count: 29`, and
  `Fetch failed/skipped exchange count: 0`.
- Apply `27551222306` ran on the same commit and inputs with `mode=apply`.
  It completed successfully, applied all 30 CMC Top 30 exchange rows, and
  reported `Fetch failed/skipped exchange count: 0`. `binance-tr` remained a
  seeded zero-listing venue because the snapshot has no mapped CoinGecko spot
  exchange id.

Post-apply live verification against `https://www.bcelab.xyz` returned HTTP 200
for `/api/exchanges`, `/ko/exchanges`, `/ko/exchanges/mexc`,
`/api/exchanges/binance/projects?locale=ko`, and
`/api/exchanges/mexc/projects?locale=ko`. `/api/exchanges` contained all 30 CMC
Top 30 slugs with no missing expected slug, versioned `bceExchangeScore` fields,
and one pre-existing extra active legacy row: `gdax` for Coinbase Exchange. The
legacy duplicate is operationally separate from Top 30 coverage and should be
cleaned up through a scoped follow-up rather than local production writes.

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

As of BCE-1980 on 2026-06-15, `/api/exchanges` suppresses active legacy alias
exchange rows when a canonical CMC Top 30 row exists. The observed production
case was the BCE-1963 legacy Coinbase row `gdax` remaining active after the
BCE-1972/BCE-1975 canonical Top 30 row `coinbase` was seeded with CoinGecko id
`gdax`, causing 31 active aggregate rows. `src/lib/repositories/exchanges.ts`
now aggregates exchange list rows by the CMC alias key, prefers the canonical
Top 30 exchange row for display, and deduplicates listed projects across legacy
and canonical rows. Detail lookup remains alias-compatible: requests such as
`/api/exchanges/gdax/projects` are expected to resolve through the canonical
Coinbase exchange mapping while the legacy row remains active. Production DB
cleanup, if still desired, must use the approved remote-first
`exchange-listing-backfill`/migration path after dry-run evidence; local
production writes remain forbidden.

Final BCE-1963 verification on 2026-06-15 at workspace
`/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
and SHA `cbbe92d` passed after the Top 30, BCE Exchange Score, report badge,
and alias-dedup blockers were resolved:

- `/api/exchanges` returned HTTP 200 with 30 rows and all CMC Top 30 names.
- Aggregate rows expose `bceExchangeScore`,
  `bceExchangeScoreFormulaVersion=bce-exchange-score-v1`, and
  `bceExchangeScoreComponents`; `averageBceScore` is not exposed as the
  representative exchange score.
- Representative aggregates: Binance `listedProjectCount=60`,
  `scoredProjectCount=50`, `bceExchangeScore=65.67`; Coinbase Exchange
  `listedProjectCount=80`, `scoredProjectCount=65`,
  `bceExchangeScore=64.69`; MEXC `listedProjectCount=80`,
  `scoredProjectCount=64`, `bceExchangeScore=63.77`; Binance TR
  `listedProjectCount=0`, `bceExchangeScore=null`.
- Detail APIs returned HTTP 200 for `/api/exchanges/binance/projects?locale=ko`,
  `/api/exchanges/coinbase/projects?locale=ko`, and
  `/api/exchanges/mexc/projects?locale=ko`; their top-level exchange score
  fields matched the aggregate score contract.
- Binance detail retained NEAR report availability:
  `reportTypes=econ,maturity`.
- HTML checks returned HTTP 200 for `/ko/exchanges`, `/ko/exchanges/binance`,
  and `/ko/score`; `/ko/exchanges` rendered Top 30 representatives including
  Binance, Coinbase Exchange, MEXC, and Deepcoin, while `/ko/exchanges/binance`
  and `/ko/score` both rendered NEAR ECON/MAT badge evidence.

As of BCE-1981 on 2026-06-15, the Coinbase/GDAX alias contract was tightened
at the shared CMC Top 30 reference boundary. `src/lib/exchange-top30.ts` maps
`coinbase`, `gdax`, `coinbase-pro`, `coinbase_exchange`, `coinbase-exchange`,
and display-name variants to the canonical CMC Coinbase Exchange row. Runtime
exchange aggregation and detail helpers continue to union listings by canonical
exchange key, so duplicate legacy rows do not change listed-project counts or
`BCE Exchange Score`. No local production database cleanup was performed; any
physical merge/archive of legacy exchange rows remains subject to the
remote-first production-write policy and the approved
`.github/workflows/exchange-listing-backfill.yml` path.

## BCE-1869 Relationship

BCE-1869 affected the report-publishing watcher boundary, not this website
operations pipeline. This page exists because the runtime manifest and
Paperclip pipeline metadata both need a durable state page for every active
pipeline.
