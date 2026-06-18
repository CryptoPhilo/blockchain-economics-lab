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

Existing rows were historically handled by
`scripts/backfill-report-cover-image-urls.ts`, but that script and its dedicated
manual workflow are not present in the current repository. Do not register report
cover backfill as an active runtime node until a real workflow and entrypoint are
landed together with a dry-run-first production approval contract.

## BCE-1932 Homepage Latest Report Cover Boundary

As of 2026-05-25, homepage latest-report showcase cover selection must prefer
persisted report-level cover data in `project_reports.cover_image_urls_by_lang`
before falling back to legacy product cover sources. The production schema has
the report-level cover column applied, and published ECON/MAT reports with real
localized slide covers should not be hidden behind fallback FOR text cards or
missing product cover backfill state.

Legacy viewer HTML can still provide an external slide image fallback when a
stored report cover is absent. Post-deploy verification for PR #95 and PR
#97/#98 covered the Korean homepage showcase cycling eight latest-report slides
with non-zero image natural widths and `/ko/projects/curve-dao` rendering a
latest report cover as the project detail header background.

Backfill evidence for this boundary: initial apply `success=979 failed=279`,
external fallback apply `success=59 failed=0`, and final dry-run
`Reports scanned=1447 Candidates=0`.

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
first and keep the generated diff audit artifact. A dedicated remote workflow is
not registered in the current manifest; production writes remain remote-only and
must not be run locally. Add a real GitHub Actions workflow plus approval evidence
before registering this as an active runtime node.

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

Backfills remain dry-run first through `scripts/pipeline/backfill_card_summaries.py`.
Production writes are still remote-only and approval-gated; the runtime manifest
must only list a card-summary backfill node after a real remote workflow exists.

## BCE-1933 Production Deployment Evidence

As of 2026-06-01 16:35 KST, PR #144 was merged to `main` at
`c94fbc09b8e57cd678aa2f00b67b8d252c2e8ade` after Paperclip board approval
`f728ab13-ae53-42af-a792-b989cd6f0f7a`. Production deploy run
`https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26741357848`
completed successfully with `expected_commit` pinned to that SHA.

Evidence:

- Remote verification passed: report publication policy, pipeline verifier,
  runtime pipeline manifest, TypeScript, test suite, and production build.
- Vercel production URL:
  `https://blockchain-economics-r661ilmrb-michael-zhangs-projects-df54ac7d.vercel.app`.
- Production alias verification returned HTTP 200 for `/ko/reports`,
  `/ko/projects/bitcoin`, and `/ko/reports/bitcoin/econ`.
- The Bitcoin project/report pages rendered the new card summary text, including
  `Bitcoin은 계정 잔고를 직접 저장하지 않고` and `SEC는 2024년 1월`.
- Follow-up deployment for PR #148 ran on 2026-06-02 through
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26791285256`
  with `expected_commit=7a10e2fba84eef8d9a6a04e813c27f732fd5b2ec`.
  Remote verification passed: report publication policy, pipeline verifier,
  runtime pipeline manifest, TypeScript, tests, and production build. Vercel
  production URL was
  `https://blockchain-economics-qvjli8yc8-michael-zhangs-projects-df54ac7d.vercel.app`,
  aliased to `https://www.bcelab.xyz`.
- After the AWE ECON card-summary apply, production verification returned HTTP
  200 for `/ko/projects/awe-network` and `/ko/reports/awe-network/econ`; the old
  `분석 목적은` / `온체인 state 매핑` fragments were absent and the new
  `토큰 가치 포획 불명확성` summary was present.
- BCE-1947 production audit on 2026-06-03 added a read-only coverage artifact
  for report-card summary visibility and found Banana For Scale ECON v2 visible
  on `/ko/projects/banana-for-scale` with empty rendered summary. Board approval
  `81ebbaf5-ca6d-42da-86b0-0428e03000da` authorized a scoped manual production
  patch after the existing Drive Markdown backfill path returned `seen=0`.
  Banana ECON v2 rows now carry localized `card_summary_*`,
  `card_data.summary_by_lang`, and `card_data.summary_quality` provenance. URL
  verification confirmed the Korean project page renders the new ECON card
  summary. Whole-production after-audit
  `scripts/pipeline/output/card_summary_coverage_audit_after_banana_patch.json`
  reported 116 row-level findings and 170 selected project-card findings still
  requiring slug-scoped follow-up.
- BCE-1947 PR #156 later deployed the shared `getLocalizedCardSummary`
  resolver, read-only coverage audit, generalized Drive-source target
  selection, and same project/type/version multi-row persistence. It merged at
  `8c825606d6e1d6526170cbbaaf5e6c276e19e90a`, passed main CI
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26929961332`,
  and deployed to Vercel production
  `https://vercel.com/michael-zhangs-projects-df54ac7d/blockchain-economics-lab/A4waoFwD46WdNRHFQASnSFfMBXDP`.
  The approved 31-slug production apply batch completed successfully. PR #157
  then fixed the remaining logic-level source/target cases and merged at
  `34f164b9e5a1773507e9fd6cc31d959ba7a23b04`; main CI
  `https://github.com/CryptoPhilo/blockchain-economics-lab/actions/runs/26935674801`
  and Vercel production deployment
  `https://vercel.com/michael-zhangs-projects-df54ac7d/blockchain-economics-lab/9hG53RvWYaip3s1DtpFzRtmXNT3E`
  completed. Six follow-up applies succeeded for `injective` (`26935838970`),
  `canton-network` (`26935840099`), `flare` (`26935841411`), `lido-dao`
  (`26935842648`), `berachain` (`26935843707`), and `bnb` (`26935844807`).
  Production audit counts moved from `row_findings=212`, `selected=178` before
  apply to `row_findings=109`, `selected=75` after PR #157 and the six applies.
  The remaining selected-card misses are source availability issues for 13
  slug/type/version groups where Drive analysis Markdown was not found; the
  current quality contract intentionally does not synthesize summaries from PDF
  or slide HTML alone.

## BCE-1945 Non-Author Release Review Boundary

As of 2026-06-02, pipeline, deploy, and production-facing website PRs must not
merge on author self-approval. The release gate requires approval from a GitHub
identity that is not the PR author identity. A same-account approval is not
valid release evidence.

If BCELab temporarily has only one usable GitHub account for a release, the
exception requires both an explicit CEO waiver and linked Paperclip issue
evidence for the release scope. The PR must also show that remote checks passed,
the applicable `knowledge/pipelines/` state page was checked, and
`pipelines/bcelab-runtime-pipelines.json` still matches the affected executable
runtime boundary.

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
`bceExchangeScore=null`.

## BCE-1973 Exchange Detail Report Badge Boundary

As of 2026-06-15, exchange detail rows must resolve report badge availability
through the same locale-aware `project_reports` policy used by `/[locale]/score`,
not only through `tracked_projects.last_*_report_at` timestamps. The Binance
NEAR listing exposed the failure mode: the active exchange listing points to
`tracked_projects.slug=near`, while the published ECON/MAT reports are attached
to the canonical monitoring row `tracked_projects.slug=near-protocol`. Exchange
detail availability now loads localized report rows with the service-role
boundary, applies exact project alias/name/canonical-key availability mapping,
and then renders the existing Top500 `ScoreTableGate` row schema.

BCE-1963 final runtime closure must include a NEAR regression check after the
Top 30 coverage blocker is resolved: `/api/exchanges/binance/projects` must
return the NEAR row with `reportTypes` containing `econ` and `maturity`, and
`/ko/exchanges/binance` must render those report badges consistently with
`/ko/score`.

## BCE-1974 BCE Exchange Score Boundary

As of 2026-06-15, exchange-level scoring must be labeled and exposed as
`BCE Exchange Score`, not as a per-project `BCE Score` average. The official
formula version is `bce-exchange-score-v1`:

- `CoreBceQuality`: CMC-rank-weighted average of listed projects that have a
  BCE Score, with missing ranks treated conservatively as rank 5000.
- `RankQuality`: average CMC rank quality across all DB-matched listed
  projects, assigning 0 to missing or rank > 5000 projects.
- `ScoreCoverage`: `100 * sqrt(scoredListedProjectCount /
  dbMatchedListedProjectCount)`.
- `LongTailPenalty`: up to 15 points once missing or rank > 1000 listings
  exceed 30% of DB-matched listings.

`src/lib/repositories/exchanges.ts` owns the runtime calculator and returns
`bceExchangeScore`, `bceExchangeScoreFormulaVersion`, and
`bceExchangeScoreComponents` for `/api/exchanges` and exchange detail APIs.
The calculator deduplicates listings by `project_id`, excludes inactive or
delisted rows per the BCE-1963 contract, and returns `bceExchangeScore=null`
when an active exchange has no DB-matched listed projects.

The score rank input comes from the latest CoinMarketCap `market_data_daily`
snapshot and is merged by project slug at read time. Do not add a
`tracked_projects.cmc_rank` dependency unless a separate schema migration is
approved and deployed.

Local verification at workspace
`/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
and SHA `f42fee1` showed `/ko/exchanges` rendering HTTP 200 and the UI label
`BCE Exchange Score`. `/api/exchanges` and detail APIs returned the new
versioned fields for the two currently seeded exchange rows:

- Binance: `listedProjectCount=55`, `scoredProjectCount=47`,
  `bceExchangeScore=66.01`, components `coreBceQuality=67.86`,
  `rankQuality=45.70`, `scoreCoverage=92.44`, `longTailPenalty=0`,
  `longTailRatio=0.20`.
- Coinbase Exchange / `gdax`: `listedProjectCount=76`,
  `scoredProjectCount=62`, `bceExchangeScore=64.43`, components
  `coreBceQuality=67.75`, `rankQuality=40.92`, `scoreCoverage=90.32`,
  `longTailPenalty=0`, `longTailRatio=0.22`.

The connected database still returned only two rows from `/api/exchanges` at
that verification point, and `/api/exchanges/mexc/projects` returned HTTP 404.
The required third Top 30 long-tail representative API case therefore depends
on the BCE-1972 Top 30 seed/backfill state being present in the connected
database before release approval cites live representative evidence.

As of 2026-06-15, BCE-1975 prepared local release-candidate commit `480c5c2`
combining BCE-1972 Top 30 coverage with BCE-1974 `BCE Exchange Score`
API/UI/backfill evidence fields. Local gates reported for the RC: exchange
repository tests, backfill exchange listing tests, exchange page contract test,
`npx tsc --noEmit`, and `npm run verify:runtime-pipelines`.

Production evidence is still pending the BCE-1945 release boundary: valid
non-author GitHub review or CEO waiver, merge, then approved remote
`.github/workflows/exchange-listing-backfill.yml` dispatch with
`seed_cmc_top30=true`. BCE-1963 must not close until that remote Top 30
backfill evidence is present and runtime verification passes against the
post-backfill API/UI.

## BCE-1986 Exchange-Listed Long-Tail Report Availability

As of 2026-06-16, exchange detail report availability is explicitly independent
from the Top500 score page universe. Top500 remains the score/ranking page
scope, but exchange detail rows are driven by canonical `tracked_projects`
joined through active `exchange_project_listings`.

The report watcher project resolver loads canonical `tracked_projects` with
slug, name, symbol, aliases, `coingecko_id`, and `cmc_id`, and marks projects
that are present in active `exchange_project_listings`. It does not require a
project to be in the Top500 CMC snapshot before resolving a Drive slide/report
file. Unresolved Drive PDFs continue to be recorded in the slide manifest and
processed output with `status=unresolved` or
`db_reconcile_unresolved_drive_pdf` rather than being silently dropped.

The exchange detail API and UI continue to use the existing score-table row
shape for visual consistency, but the rows represent active exchange listings,
not Top500 membership. Report badges and dates are loaded from visible
`project_reports` by canonical project id plus alias/name/coin-id matching, so
an OpenGradient-like Binance listing with CMC rank greater than 500 can show
ECON/MAT/FOR availability when a report row exists. Missing or rank greater
than 500 entries are treated as long-tail score inputs, not report-availability
exclusions.

As of BCE-1978 on 2026-06-15, the exchange Top 30 listing backfill retries
recoverable CoinGecko ticker fetch failures before treating a venue as
unavailable. `scripts/backfill-exchange-listings.ts` honors bounded
`Retry-After` delays and retries HTTP 429, 408, and 5xx responses up to four
attempts per exchange ticker page. This preserves the approved workflow and
manifest boundary while reducing transient CoinGecko rate-limit zero-listing
skips during `.github/workflows/exchange-listing-backfill.yml` runs.

As of BCE-1979 on 2026-06-15, CMC Top 30 backfill apply is partial-apply
tolerant for mapped venue fetch exhaustion after the BCE-1978 retry policy.
In `--cmc-top30` mode, an exhausted CoinGecko 429/408/5xx fetch records the
venue as a skipped listing fetch, keeps the seeded CMC exchange evidence at
zero listings, and continues remaining Top 30 venues. Explicit scoped
`--exchange` runs still fail fast on fetch exhaustion. The stdout evidence
summary reports seeded exchange count, listing-backfilled exchange count,
fetch-failed/skipped exchange count, and skipped slugs with reasons.

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

As of BCE-1987 on 2026-06-16, Binance remains only the representative example
for Top500-outside exchange detail report availability. The verified contract is
all active `exchange_project_listings` rows across exchanges: report badge
availability is keyed by canonical project identity plus alias/name/coin-id
matching, and one published report metadata row can surface on every active
exchange detail page where that project is listed. Regression coverage includes
non-Binance OKX, Bybit, and Coinbase Exchange long-tail fixtures, plus a project
listed on both Binance and OKX. Watcher coverage marks multiple active listing
rows as `exchange_listed` without inspecting exchange slug and preserves the
numeric `cmc_id` false-positive guard.

As of BCE-1988 on 2026-06-16, exchange detail project rows expose `rank` and
`cmcRank` as the same CoinMarketCap asset rank when available. The UI displays
that value next to the asset name as a CMC badge; rows without a CMC rank do not
receive a synthetic exchange-detail row number. The runtime rank resolver first
uses the latest CMC Top5000 snapshot and then fills missing exchange-listed
assets from their own latest `market_data_daily` CMC rows by
`tracked_projects.slug`, `coingecko_id`, or `cmc_id`. `coingecko_id` is only a
market-data lookup alias, not the source of rank semantics. This allows
OpenGradient-like long-tail listings to show ranks such as CMC #481 even when
they are absent from the Top500 score universe or were populated by a scoped CMC
lookup/backfill at a different `recorded_at`.

As of BCE-1992 on 2026-06-19, the residual stash deletion of dashboard,
products, subscribe, newsletter, and commerce-support files is rejected. These
surfaces remain part of the website contract until a separate product decision
removes them with navigation, API, test, and documentation updates in the same
change. `scripts/verify-website-pipeline.mjs` now fails if the retained
dashboard, products, subscribe, newsletter, ProductCard/ProductFilter,
ReferralTab, DashboardBetaSignalsSection, or dashboard repository files are
removed. This prevents unrelated report/CMC/slide recovery work from
accidentally deleting user-facing routes.

## BCE-1869 Relationship

BCE-1869 affected the report-publishing watcher boundary, not this website
operations pipeline. This page exists because the runtime manifest and
Paperclip pipeline metadata both need a durable state page for every active
pipeline.
