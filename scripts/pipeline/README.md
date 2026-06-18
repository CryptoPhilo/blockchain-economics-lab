# BCE Lab Report Pipeline

## Runtime Governance

The report pipelines are remote-first. Paperclip owns the operating definition,
and this repository maps that definition to executable workflows in
`pipelines/bcelab-runtime-pipelines.json`.

Production-affecting runs must use GitHub Actions or another approved remote
runner. Local commands are limited to dry-run, development, and incident
reproduction. Do not perform production writes from a local shell unless the
board has approved an emergency exception and the result is rerun or reconciled
through the remote workflow.

Before changing pipeline code or workflows, run:

```bash
npm run verify:runtime-pipelines
```

See `doc/runbooks/runtime-pipeline-governance.md` for the full operating rule.

## Current Operational Path

The active publishing watcher is `scripts/pipeline/watch_slides.py`.

- `watch_slides_inspection.py` owns PDF page profiling, text/OCR extraction, and
  language resolution helpers.
- `watch_slides_matching.py` owns project signal matching, watcher-only aliases,
  and slug/content mismatch guards.
- `watch_slides_telemetry.py` owns optional Paperclip run/node/event payloads and
  watcher status taxonomy.
- `watch_slides.py` remains the CLI and orchestration boundary. Keep DB/storage
  writes there until the repository layer is split behind stable signatures.

- Source drafts for report creation live in GDrive `BCE Research Source Drafts`.
  SHIB example: `BCE Research Source Drafts / shiba-inu_econ_v1_en.md`.
- Published operating slide PDFs are watched from the active `Slide2/{TYPE}/`
  folders in `scripts/pipeline/watch_slides.py`.
- Historical `Slide/{TYPE}/` folders are backfill roots only. Use
  `--drive-root-scope legacy` or `--drive-root-scope all` explicitly when a
  repair/backfill must inspect them; scheduled/default runs stay on
  `--drive-root-scope active`.
- Do not use legacy GDrive `drafts/{ECON,MAT,FOR}` folders for current
  operations. Those folders are only for archived reproduction under
  `_legacy/pipeline/`.
- Smoke current watcher without publishing:

```bash
python scripts/pipeline/watch_slides.py --type econ --slug shiba-inu --dry-run --drive-root-scope active
```

When `--slug` is provided, the watcher uses filename/project/folder hints to
avoid traversing unrelated Slide2 folders before full PDF content resolution.
Dry-run logs also include a source-vs-slide diagnostic section: a source draft
such as `BCE Research Source Drafts / okx_econ_v1_en.md` with no publishable
PDF in active `Slide2/econ` is reported as slide generation pending/missing.

- Reprocess a slug after human verification:

```bash
python scripts/pipeline/watch_slides.py --type econ --slug shiba-inu --force --drive-root-scope active
```

Direct Drive file-id targeting is disabled. Put PDFs under the appropriate
`Slide2/{TYPE}` folder for normal operations, or under `Slide/{TYPE}` only for
explicit backfills, then use `--type`, `--slug`, and `--drive-root-scope`
filters so the run follows the defined pipeline path.

The active watcher also runs the active-project backlog guard. It flags active
projects with no `project_reports` row and no report/due timestamp markers so
newly tracked projects are visible from the current pipeline logs.

Scheduled GitHub Actions runs enumerate the full active `Slide2/{TYPE}` tree
with `--drive-root-scope active` and let `_slide_processed.json` skip unchanged
files. Do not put a modified-time lookback on the scheduled path: if the
workflow is paused, gated, or failing for longer than the lookback, unprocessed
PDFs can age out and never reach Storage/DB. Use `--modified-since-minutes` only
for ad hoc diagnostics where a human intentionally accepts that narrower scope.

Audit published slide language consistency after incident repair or before
closing locale-contamination work:

```bash
python scripts/pipeline/audit_public_slide_language.py \
  --rank-limit 100 \
  --report-type econ \
  --report-type maturity \
  --output scripts/pipeline/output/slide_language_audit_top100.json \
  --fail-on-findings
```

For a route-specific smoke check, build conventional public Storage URLs without
querying Supabase:

```bash
python scripts/pipeline/audit_public_slide_language.py \
  --conventional-urls \
  --slug bitcoin \
  --report-type econ \
  --fail-on-findings
```

The audit fails on two conservative signals: identical HTML bytes across sibling
language slots for the same `(slug, report_type)`, or text/OCR content whose CJK
script contradicts the route language. Use `--ocr` when validating raster-only
slide HTML; the default still catches duplicate latest objects and any text
layer/fixture mismatch.

Full type scans also run a final Drive-vs-DB availability reconcile. The
watcher rebuilds the current `(report_type, slug, language)` set from the
selected Drive root scope. Default/scheduled runs compare against active
`Slide2/{TYPE}` PDFs; explicit backfill runs can compare against historical
`Slide/{TYPE}` PDFs with `--drive-root-scope legacy`. Rows outside the selected
set are cancelled, then the matching `tracked_projects.last_*_report_at` field
is cleared/synced. This prevents historical pipeline rows from making the
website show a report badge for a project that no longer has a readable slide in
the selected Drive source of truth.
Slug-targeted runs skip this reconcile by design; use a full type run after
large Drive folder changes. If an emergency diagnostic run must avoid DB
reconciliation, pass `--skip-db-reconcile`.

## OpenAI API Report POC

`scripts/pipeline/openai_report_poc.py` is a local dry-run spike for generating
canonical report artifacts from an OpenAI Responses API-shaped contract without
calling production services by default.

```bash
python3 scripts/pipeline/openai_report_poc.py \
  --slug uniswap \
  --report-type econ \
  --version 1 \
  --languages ko en ja zh
```

The command writes canonical JSON, Markdown, four-language slide input data, a
sample Responses API request body, and publish metadata under
`scripts/pipeline/output/openai_report_poc/`. See
`scripts/pipeline/OPENAI_REPORT_POC.md` for the input/output contract,
OpenAI API notes, and rate limit/cost/retry/idempotency considerations.

## Marketing Summary Backfill

`scripts/pipeline/marketing_content_pipeline.py` derives website card summaries
and marketing snippets from Korean Markdown reports. It only writes to a
`project_reports` row when a matching Korean slide report already exists for the
same slug, report type, and version, so the website summary remains tied to a
published slide deck.

Production backfills must use Drive sources. Do not use `scripts/pipeline/output`
as a summary source; it contains generated artifacts and historical pipeline
state, not canonical research drafts. The script refuses that path for local
source loading.

### Preconditions

- Apply `supabase/migrations/20260505_add_marketing_content_metadata.sql` before
  running a persisted backfill. The write path expects
  `marketing_content_by_lang`, `summary_source_md_*`, and
  `summary_generated_at` in `project_reports`.
- Confirm `SUPABASE_SERVICE_KEY` is loaded from `.env.local` or
  `scripts/pipeline/.env`.
- Confirm Google credentials are available via
  `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_FILE`,
  or the pipeline-local service account files. Use `--no-translate` only for a
  Korean-only emergency backfill.
- Confirm `BCE_MARKETING_FOR_SOURCE_FOLDER_ID` points to Google Drive
  `analysis/FOR`. FOR no longer falls back to a generic source folder.

### Dry Run

Use `--persist --dry-run` to derive copy and check matching production rows
without writing updates:

```bash
python3 scripts/pipeline/marketing_content_pipeline.py \
  --source drive \
  --slug bitcoin \
  --report-type econ \
  --version 1 \
  --persist \
  --dry-run
```

For a Drive-source batch, omit the local path. ECON and MAT use their configured
analysis folders; FOR requires `BCE_MARKETING_FOR_SOURCE_FOLDER_ID`:

```bash
python3 scripts/pipeline/marketing_content_pipeline.py \
  --source drive \
  --persist \
  --dry-run \
  --limit 20
```

Expected dry-run statuses:

| Status | Meaning |
|--------|---------|
| `matched_dry_run` | A matching Korean slide report row was found; no write was made. |
| `skipped_no_matching_korean_slide` | Source Markdown exists, but no published/approved/coming-soon Korean slide row with a Korean slide HTML URL was found. |
| `skipped_subject_mismatch` | Source Markdown filename/slug matches a row, but the body project name does not match the tracked project. |
| `derived` | Copy was derived without production matching because `--persist` was not set. |

### Execute

Run a small filtered batch first:

```bash
python3 scripts/pipeline/marketing_content_pipeline.py \
  --source drive \
  --slug bitcoin \
  --report-type econ \
  --version 1 \
  --persist
```

Then expand with `--limit`, `--report-type`, or repeated `--slug` filters.
Every updated row receives:

- `card_summary_<lang>` columns for generated summary copy.
- `marketing_content_by_lang` for generated marketing copy.
- `card_data.summary_by_lang`, `card_data.marketing_by_lang`, and
  `card_data.source_md` provenance.
- `summary_source_md_*` and `summary_generated_at` provenance columns.

### Verify

Check representative rows after a persisted run:

```sql
select
  id,
  card_summary_ko,
  card_summary_en,
  marketing_content_by_lang,
  card_data->'source_md' as source_md,
  summary_generated_at
from public.project_reports
where id = '<project_report_id>';
```

Quality-check at least five Korean/English samples before broadening a batch.
Summaries and marketing snippets should be under 100 words, not contain raw
Markdown syntax, and match the report subject instead of generic project copy.

### Rerun and Rollback

Rerun is safe for the same source when the source Markdown or translations need
to be regenerated; the script overwrites the generated fields on the matching
row and refreshes provenance timestamps.

Rollback a bad row by clearing only the generated marketing fields:

```sql
update public.project_reports
set
  marketing_content_by_lang = '{}'::jsonb,
  summary_source_md_file_id = null,
  summary_source_md_name = null,
  summary_source_md_archived_url = null,
  summary_generated_at = null,
  card_summary_ko = null,
  card_summary_en = null,
  card_summary_fr = null,
  card_summary_es = null,
  card_summary_de = null,
  card_summary_ja = null,
  card_summary_zh = null,
  card_data = coalesce(card_data, '{}'::jsonb)
    - 'summary_by_lang'
    - 'marketing_by_lang'
    - 'marketing_generated_at'
    - 'source_md'
where id = '<project_report_id>';
```

## X Promo Approval Queue

`scripts/pipeline/x_promo_pipeline.py` generates X-ready promotional copy from
published report rows that already have `marketing_content_by_lang`. It is a
manual-approval workflow by default: commands dry-run unless an operator passes
the explicit posting flags, and queue generation does not call the X API.

Generated drafts include:

- 280-character validation with the report URL included in the text.
- Language tone rules for `ko`, `en`, `fr`, `es`, `de`, `ja`, and `zh`.
- Three templates: `insight-first`, `chart-report-first`, and
  `risk-opportunity-first`.
- A stable `duplicate_key` from report id, slug, report type, version, language,
  template, and URL.
- Audit metadata with source field, generation time, published time, and manual
  approval default.

Copy source selection prefers `marketing_content_by_lang` for the requested
language. If that is empty, the generator falls back to `card_summary_<lang>`,
then `en` and `ko` sources in the same order. Audit metadata records the actual
field used, for example `project_reports.card_summary_en`.

Dry-run five sample production rows from Supabase:

```bash
python3 scripts/pipeline/x_promo_pipeline.py \
  --source supabase \
  --limit 5 \
  --language ko,en \
  --dry-run
```

Generate CMO review files:

```bash
python3 scripts/pipeline/x_promo_pipeline.py \
  --source supabase \
  --limit 5 \
  --language ko,en \
  --write-queue \
  --output-dir data/x-approval-queue
```

The command writes:

- `x-promo-approval-<run>.jsonl`: machine-readable approval queue. Each row
  starts as `pending_manual_approval`; a sender must only consume rows changed
  to `approved`.
- `x-promo-approval-<run>.md`: reviewer-friendly CMO checklist with copy,
  character count, URL, template, and duplicate key.

For local QA without Supabase, pass a JSON array with `id`, `slug`,
`report_type`, `version`, `marketing_content_by_lang`, and optional
`card_summary_<lang>`/`title_by_lang`:

```bash
python3 scripts/pipeline/x_promo_pipeline.py \
  --source json \
  --input-json /path/to/sample-reports.json \
  --limit 5 \
  --dry-run
```

Dry-run approved posts from a reviewed queue. This does not require X
credentials and does not write the post log:

```bash
python3 scripts/pipeline/x_promo_pipeline.py \
  --queue-jsonl data/x-approval-queue/x-promo-approval-<run>.jsonl \
  --confirm <slug>
```

The dry-run output includes each approved row's `duplicate_key`. Real posting is
single-row by default; if a slug has more than one approved language/template,
the post command fails before any X API call. Post exactly one approved row with
the reviewed duplicate key:

```bash
python3 scripts/pipeline/x_promo_pipeline.py \
  --queue-jsonl data/x-approval-queue/x-promo-approval-<run>.jsonl \
  --post \
  --confirm <slug> \
  --confirm-key <duplicate_key>
```

Real posting requires `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, and
`X_ACCESS_TOKEN_SECRET`. `X_BEARER_TOKEN` can be present for diagnostics, but it
is not enough to create a post. The sender appends every attempt/result to
`data/x-post-attempts.jsonl`; rows with an existing `posted` result for the same
`duplicate_key` are skipped as duplicates. If the operator cancels, leave queue
rows as `pending_manual_approval` or change them to `rejected`; no X call is made
without `--post` and an exact single approved selection. Do not use previously
exposed credentials for live posting; rotate them first, then run a dry-run
again before posting.

## Archived Text Report Generator

The sections below describe the older `orchestrator.py` text-to-PDF generator.
They are retained for incident reproduction and code archaeology only. Current
operations use `watch_slides.py` through `slide-pipeline-cron.yml`; do not start
new production runs from these commands.

This archived pipeline orchestrates the generation of three types of blockchain research reports for BCE Lab projects:

- **Economic Reports** (econ): Market analysis, tokenomics, and economic metrics
- **Materials Reports** (mat): Whitepaper analysis, technical documentation review
- **Forensic Reports** (for): Security analysis, risk assessment, fraud detection

## Architecture

```
pipeline/
├── orchestrator.py          # Main entry point and report orchestration
├── monitor_forensic.py      # Daily forensic monitoring and escalation
├── translate.py             # Multi-language translation engine
├── config.py                # Configuration (languages, paths, naming)
├── gen_econ.py             # Economic report generator (external)
├── gen_mat.py              # Materials report generator (external)
├── gen_for.py              # Forensic report generator (external)
├── __init__.py             # Package initialization
└── README.md               # This file
```

## Archived Quick Start

### 1. Generate a Single-Language Report

Historical reproduction command for an English economic report for Bitcoin v1:

```bash
python orchestrator.py --type econ --project btc --version 1 --lang en
```

### 2. Generate Multi-Language Reports

Generate reports in all 7 languages (English, Korean, French, Spanish, German, Japanese, Chinese):

```bash
python orchestrator.py --type econ --project eth --version 2 --lang all
```

### 3. Specify Custom Data File

```bash
python orchestrator.py --type mat --project sol --version 1 --lang ko --data /path/to/data.json
```

## Command-Line Arguments

### Required Arguments

| Argument | Options | Description |
|----------|---------|-------------|
| `--type` | `econ`, `mat`, `for` | Report type to generate |
| `--project` | any slug | Project identifier (e.g., btc, eth, sol) |
| `--version` | integer >= 1 | Report version number |
| `--lang` | language code or `all` | Target language(s) |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--data` | auto-detected | Path to project data JSON file |

## Supported Languages

The pipeline supports 7 languages with consistent terminology via the integrated glossary:

| Code | Language |
|------|----------|
| `en` | English |
| `ko` | Korean (한국어) |
| `fr` | French (Français) |
| `es` | Spanish (Español) |
| `de` | German (Deutsch) |
| `ja` | Japanese (日本語) |
| `zh` | Chinese (中文) |

## Output Files

Generated reports follow the naming convention:

```
{project_slug}_{report_type}_v{version}_{language}.pdf
```

### Examples

```
btc_econ_v1_en.pdf      # Bitcoin economic report, English
eth_mat_v2_ko.pdf       # Ethereum materials report, Korean
sol_for_v1_zh.pdf       # Solana forensic report, Chinese
```

All files are saved to the configured `OUTPUT_DIR` (see `config.py`).

## Forensic Monitoring

Run daily forensic monitoring for all tracked projects:

```bash
python monitor_forensic.py
```

Monitor specific projects:

```bash
python monitor_forensic.py --projects btc,eth,sol,bnb
```

### Forensic Triggers

The system monitors 5 forensic triggers (STR-002 §3.2):

1. **Price Volatility**: 24h price change >= ±15%
2. **Volume Anomaly**: Daily volume >= 300% of 7-day average
3. **Whale Movement**: Large transfers >= 1% of supply
4. **Exchange Inflow**: Net inflow to exchanges >= 0.5% of supply
5. **Insider Activity**: Abnormal movement from team/insider wallets

### Escalation Routing

- **0 flags**: Log only (INFO level)
- **1 flag**: Alert CRO team (WARNING level)
- **2+ flags**: Request forensic report (CRITICAL level)

Results are saved as JSON logs with timestamp and full details.

## Translation System

The pipeline includes multi-language support with consistent blockchain terminology.

### Key Components

- **`translate.py`**: Core translation engine with glossary support
- **`GLOSSARY`**: Blockchain terms in all 7 languages (120+ terms)
- **Text field detection**: Automatically identifies translatable content
- **Metadata preservation**: Maintains numeric values, dates, addresses

### Example Usage

```python
from translate import translate_all_languages

# Load project data (English)
project_data = load_project_data('btc.json')

# Generate translations for all languages
translations = translate_all_languages(project_data)

# Access specific translation
korean_data = translations['ko']
french_data = translations['fr']
```

## Configuration

Edit `config.py` to customize:

- Output directory path
- Supported languages
- Report file naming convention
- API keys and service endpoints

## Data Format

Project data should be provided as JSON with the following structure:

```json
{
  "name": "Bitcoin",
  "slug": "btc",
  "description": "Digital currency...",
  "market_cap": 1200000000000,
  "price": 45000.50,
  "analysis": {
    "econ": "Economic analysis...",
    "mat": "Materials analysis...",
    "for": "Forensic analysis..."
  },
  "metadata": {
    "created_at": "2024-01-01T00:00:00Z",
    "team": ["..."]
  }
}
```

## Error Handling

- **Missing data file**: Specify with `--data` or ensure default location is populated
- **Invalid language code**: Use `--lang all` or check supported languages
- **Generator errors**: Check logs for detailed error messages
- **API failures**: Monitor_forensic uses mock data; integrate real APIs as needed

## Logging

All components produce logs:

- **Orchestrator**: Console output with summary
- **Monitor_forensic**: `forensic_monitoring.log` + console output
- **Translate**: DEBUG level logging for translation operations
- **Generators**: Check individual generator documentation

## Performance

- Single report generation: ~10-30 seconds (varies by generator)
- Multi-language batch (7 languages): ~1-3 minutes
- Daily monitoring: <1 minute for 5 projects

## TODO / Future Enhancements

- [ ] Integrate real translation API (Google Translate, DeepL)
- [ ] Connect to CoinGecko API for live price/volume data
- [ ] Implement whale/insider tracking via blockchain indexer
- [ ] Add caching for translated glossary terms
- [ ] Implement report versioning and diff tracking
- [ ] Add email notifications for forensic escalations
- [ ] Create web dashboard for monitoring results

## Support

For issues or questions:
1. Check logs for error messages
2. Verify data file format and path
3. Ensure all dependencies are installed
4. Review this README for common patterns

## References

- STR-002 §3.2: Forensic monitoring requirements
- Process Documentation §4: Monitoring log format
- Process Documentation §3.5: Glossary management
