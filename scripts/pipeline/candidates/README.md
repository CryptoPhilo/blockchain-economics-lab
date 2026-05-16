# Candidate FOR Input Nodes

This directory is an inactive candidate workspace. Code here is not imported by
the production FOR watcher, scanner, report registration, or slide publishing
paths unless a future activation task explicitly wires it in.

## `sudden_movers_scanner.py`

Candidate node: `급변동 종목 스캐닝`

Purpose:

- Fetch CoinMarketCap listings.
- Compute a market-average 24h move from the top market-cap listings.
- Emit assets whose absolute 24h move deviation from the market average is at
  least the configured scanner threshold, currently
  `FORENSIC_TRIGGERS.relative_deviation_24h_pct` in `scripts/pipeline/config.py`.

Output contract for the card-generation anchor:

- `node`: candidate node id/name and inactive marker.
- `status`: `ok` or `failed`.
- `observed_at`: scan observation timestamp.
- `threshold_pct_points`: configured relative deviation threshold.
- `market_average_change_24h`: weighted market-average 24h movement.
- `source`: CoinMarketCap endpoint, requested limit, credit count, source
  timestamp, and source age when available.
- `candidates[]`: `symbol`, `name`, `slug`, `rank`, `price`,
  `market_average_change_24h`, `token_change_24h`, `relative_deviation`,
  `signed_relative_deviation`, `direction`, `observed_at`, and per-token source
  metadata.
- `error`: stable failure envelope when status is `failed`.
- `warnings[]`: non-fatal monitoring signals such as empty results or stale
  source data.

Failure and monitoring behavior:

- Missing CMC key: returns `status=failed`, `error.code=missing_cmc_api_key`,
  `retryable=false`.
- API rate limit: returns `status=failed`, `error.code=cmc_rate_limited`,
  `retryable=true`.
- API non-200: returns `status=failed`, `error.code=cmc_non_200`,
  `retryable=true`.
- Malformed JSON/data: returns `status=failed`, `error.code=cmc_malformed_json`
  or `cmc_malformed_data`, `retryable=true`.
- Empty result set: returns `status=ok` with no candidates and an
  `empty_result_set` warning.
- Stale source data: returns `status=ok` with a `stale_source_data` warning when
  CMC's source timestamp is older than the configured stale window.

Offline test command:

```bash
python3 -m pytest scripts/pipeline/test_candidate_sudden_movers_scanner.py
```

## Default-off card-anchor bridge

`scripts/pipeline/sudden_movers_card_anchor.py` is the guarded integration point
from the candidate scanner into the nearest FOR card-generation input surface.
It emits JSONL card anchors only when explicitly enabled. With
`ENABLE_SUDDEN_MOVERS_CARD_ANCHOR` unset or false, the bridge returns
`status=disabled`, does not call CMC, does not write state/output files, and the
current FOR publishing behavior is unchanged.

Credential precedence is intentional: `CMC_API_KEY` wins when set, then
`COINMARKETCAP_API_KEY`. Keep `COINMARKETCAP_API_KEY` as the GitHub secret unless
the owning operator chooses to add the shorter alias.

Live CMC smoke test without writes:

```bash
ENABLE_SUDDEN_MOVERS_CARD_ANCHOR=true \
CMC_API_KEY="$COINMARKETCAP_API_KEY" \
python3 scripts/pipeline/sudden_movers_card_anchor.py --enable --dry-run --limit 100
```

First production run is owned by the data platform operator plus CTO sign-off.
The explicit write action is:

```bash
ENABLE_SUDDEN_MOVERS_CARD_ANCHOR=true \
python3 scripts/pipeline/sudden_movers_card_anchor.py --enable --write --limit 500
```

Monitor the first run for `missing_cmc_api_key`, `cmc_rate_limited`,
`cmc_non_200`, `cmc_malformed_json`, `cmc_malformed_data`,
`empty_result_set`, and `stale_source_data`. Confirm the emitted JSONL anchors
have unique `anchor_id` values of `slug:observation_window`, then sample at
least five `card_data_patch` payloads before wiring any downstream publisher.

Rollback is config-only: set `ENABLE_SUDDEN_MOVERS_CARD_ANCHOR=false` in the
runtime environment or rerun the GitHub Action with `enable_card_anchor=false`.
If a write run emitted bad anchors, move the JSONL artifact out of the consumer
path and restore `SUDDEN_MOVERS_CARD_ANCHOR_STATE` from the previous state file
before the next enabled write.
