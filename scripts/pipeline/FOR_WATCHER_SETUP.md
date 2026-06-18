# FOR Draft Watcher Setup Guide

**Status**: Deprecated archive. Do not use for current operations.
**Task**: BCE-221  
**Legacy script**: `_legacy/pipeline/watch_for_drafts.py`
**Replacement**: `scripts/pipeline/watch_slides.py`

This guide is retained only as historical context for the BCE-221 FOR draft
watcher. The watcher scanned the obsolete Google Drive `drafts/FOR/` folder and
is now disabled by default. Do not create Paperclip routines, system cron jobs,
or manual recovery procedures from this document.

Current operations use:

- Source material: Google Drive `BCE Research Source Drafts`
- Published PDFs: Google Drive `Slide/{TYPE}/`
- Active watcher: `scripts/pipeline/watch_slides.py`

Current smoke command:

```bash
python scripts/pipeline/watch_slides.py --type for --slug <slug> --dry-run
```

Current reprocess command after human verification:

```bash
python scripts/pipeline/watch_slides.py --type for --slug <slug> --force
```

Direct `--file-id` targeting is disabled in the active watcher. Put the PDF in
the relevant `Slide/{TYPE}/` folder and use `--type` plus `--slug` filters so
the run exercises the same path as GitHub Actions.

Historical reproduction only:

```bash
ALLOW_LEGACY_DRAFT_WATCHER=1 python _legacy/pipeline/watch_for_drafts.py --scan-only
```

## Archived Overview

The old FOR Draft Watcher used `ingest_for.scan_for_drafts()` and the shared
Drive draft helper to scan `drafts/FOR/` markdown reports and process them
through the former PDF pipeline:

1. **Scan** - Detect new .md files in `drafts/FOR/`
2. **Ingest** - Download and validate the report
3. **Translate** - Generate 7 language versions (en, ko, fr, es, de, ja, zh)
4. **PDF Generation** - Create PDF documents for all languages
5. **QA** - Quality assurance checks
6. **Upload** - Store in Google Drive under appropriate project folders
7. **Publish** - Update Supabase database with report metadata

## Output

### Logs
All scan results are written to timestamped log files:
- **Location**: `logs/for_pipeline/for_pipeline_run_{timestamp}.md`
- **Contents**: List of detected files with metadata (ID, size, modified date, GDrive link)

### Processed Files Tracking
- **Location**: `scripts/pipeline/output/_for_processed.json`
- **Purpose**: Shared state tracker used by both `ingest_for.py` and `watch_for_drafts.py`

## Archived Scheduling

Do not recreate these schedules. They are listed only to explain what has been
retired.

### Retired Paperclip Routine

```bash
# Via Paperclip API
POST /api/companies/{companyId}/routines
{
  "name": "FOR Draft Watcher",
  "assigneeAgentId": "{cto-agent-id}",
  "templateTitle": "FOR Draft Scan - {{timestamp}}",
  "templateDescription": "Automated scan of drafts/FOR/ folder",
  "concurrencyPolicy": "skip",
  "catchUpPolicy": "skip_all"
}

# Add cron trigger
POST /api/routines/{routineId}/triggers
{
  "type": "schedule",
  "config": {
    "cron": "*/30 * * * *",  # Every 30 minutes
    "timezone": "UTC"
  }
}
```

### Retired System Cron

The retired cron invoked the FOR draft watcher every 30 minutes. Do not restore
that crontab entry; use `slide-pipeline-cron.yml` for current publishing.

## Architecture

```
watch_for_drafts.py (Scheduler/Watcher)
    ↓
    Calls ingest_for.scan_for_drafts()
    ↓
    Shared helper resolves drafts/FOR/ and scans markdown + Google Docs
    ↓
    For each new .md file:
        ↓
        Calls ingest_for.py --slug {extracted-slug}
        ↓
        ingest_for.py handles:
            - Download
            - Translation (7 languages)
            - PDF generation
            - QA verification
            - GDrive upload
            - Supabase publishing
```

## Requirements

- **Python 3.9+**
- **Google Drive credentials**: `.gdrive_service_account.json` in pipeline directory
- **Environment variables** (auto-loaded from `.env.local`):
  - `GDRIVE_SERVICE_ACCOUNT_FILE`
  - `GDRIVE_ROOT_FOLDER_ID`
  - `GDRIVE_DELEGATE_EMAIL` (optional)
  - All translation and pipeline variables (see `.env.example`)

## Troubleshooting

### No files detected
- Verify `drafts/FOR/` folder exists in Google Drive
- Check `GDRIVE_ROOT_FOLDER_ID` points to correct root folder
- Ensure service account has read access to the folder

### Pipeline failures
- Check `ingest_for.py` logs in `scripts/pipeline/output/`
- Verify all required API keys are configured (Anthropic, Etherscan, etc.)
- Check Supabase connection

### Permission errors
- Ensure service account has write access to destination folders
- Verify domain-wide delegation is configured if using `GDRIVE_DELEGATE_EMAIL`

## Related Files

- `ingest_for.py` - Main FOR pipeline processor
- `ingest_gdoc.py` - Google Docs variant ingestor
- `gdrive_storage.py` - Google Drive storage abstraction
- `translate_md.py` - Translation pipeline
- `gen_pdf_for.py` - PDF generation for FOR reports
