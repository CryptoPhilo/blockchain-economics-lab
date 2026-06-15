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

Initial local verification at workspace
`/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
and SHA `910031e` confirmed the connected Supabase schema cache still lacked
`public.exchange_project_listings`; `/api/exchanges` and representative detail
APIs returned HTTP 500 until the migration was applied.

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
  archived/suspended projects remain excluded from website/API aggregates.

As of 2026-06-15, the remote migration/backfill blocker was resolved through
GitHub Actions migration run `27531173968`, backfill dry-run `27531667649`, and
backfill apply `27531718396`. Runtime verification at workspace
`/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
and SHA `e579472` returned HTTP 200 for `/ko/exchanges`,
`/ko/exchanges/binance`, `/ko/exchanges/gdax`, `/api/exchanges`,
`/api/exchanges/binance/projects`, and `/api/exchanges/gdax/projects`.
Representative aggregate/detail parity:

- Binance: `listedProjectCount=55`, `averageBceScore=65.05`,
  `scoredProjectCount=47`; detail returned `rows=55`,
  `detailScoreRows=47`, `detailAverage=65.05`.
- Coinbase Exchange (`gdax`): `listedProjectCount=76`,
  `averageBceScore=65.38`, `scoredProjectCount=62`; detail returned
  `rows=76`, `detailScoreRows=62`, `detailAverage=65.38`.

Later on 2026-06-15, the exchange menu acceptance baseline was expanded:
the list/menu must include the CoinMarketCap spot exchange ranking Top 30
snapshot from `https://coinmarketcap.com/ko/rankings/exchanges/`, not only
the two seeded venues above. Re-check at SHA `e579472` returned
`/api/exchanges` HTTP 200 with only two rows: `gdax` and `binance`, which was
insufficient for release approval.

The BCE-1972 code boundary adds `src/lib/exchange-top30.ts` as the canonical
CMC Top 30 snapshot and alias map. It records CMC rank/name, internal slug,
CoinGecko id where available, aliases, source URL, and snapshot date. Known
non-identity mappings include Coinbase Exchange -> internal `coinbase` /
CoinGecko `gdax`, OKX -> `okx` / `okex`, Bybit -> `bybit` / `bybit_spot`,
MEXC -> `mexc` / `mxc`, HTX -> `htx` / `huobi`, and Binance TR ->
`binance-tr` with no CoinGecko spot exchange id in the checked CoinGecko
exchange list.

`scripts/backfill-exchange-listings.ts --cmc-top30` seeds all 30 active
`exchanges` rows with CMC snapshot metadata and backfills listing rows only for
venues with mapped CoinGecko ids. `.github/workflows/exchange-listing-backfill.yml`
exposes this as the approved `seed_cmc_top30` production-environment dispatch
input. `/api/exchanges` and `/[locale]/exchanges` aggregate from active
`exchanges` rows first and then overlay active listing counts, so Top 30 venues
with no matched projects appear with `listedProjectCount=0` and
`averageBceScore=null`.

## BCE-1869 Relationship

BCE-1869 affected the report-publishing watcher boundary, not this website
operations pipeline. This page exists because the runtime manifest and
Paperclip pipeline metadata both need a durable state page for every active
pipeline.
