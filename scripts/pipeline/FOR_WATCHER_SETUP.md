# FOR Draft Watcher Setup Guide

**Task**: BCE-221  
**Script**: `watch_for_drafts.py`  
**Purpose**: Automated monitoring of GDrive `drafts/FOR/` folder to detect and process new forensic analysis reports.

## Overview

The FOR Draft Watcher automatically scans the Google Drive `drafts/FOR/` folder for new markdown reports and processes them through the full BCE Lab pipeline:

1. **Scan** - Detect new .md files in `drafts/FOR/`
2. **Ingest** - Download and validate the report
3. **Translate** - Generate 7 language versions (en, ko, fr, es, de, ja, zh)
4. **PDF Generation** - Create PDF documents for all languages
5. **QA** - Quality assurance checks
6. **Upload** - Store in Google Drive under appropriate project folders
7. **Publish** - Update Supabase database with report metadata

## Usage

### Scan Only (No Processing)
```bash
python3 watch_for_drafts.py --scan-only
```

### Dry Run (Test Mode)
```bash
python3 watch_for_drafts.py --dry-run
```

### Full Processing
```bash
python3 watch_for_drafts.py
```

## Output

### Logs
All scan results are written to timestamped log files:
- **Location**: `logs/for_pipeline/for_pipeline_run_{timestamp}.md`
- **Contents**: List of detected files with metadata (ID, size, modified date, GDrive link)

### Processed Files Tracking
- **Location**: `logs/for_pipeline/processed_files.json`
- **Purpose**: Prevents reprocessing of already-handled files

## Scheduling

### Option 1: Paperclip Routine (Recommended)

Create a Paperclip routine with a 30-minute cron schedule:

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

### Option 2: System Cron

Add to crontab:
```bash
*/30 * * * * cd /Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab/scripts/pipeline && /usr/bin/python3 watch_for_drafts.py >> /tmp/for_watcher.log 2>&1
```

## Architecture

```
watch_for_drafts.py (Scheduler/Watcher)
    ↓
    Scans GDrive drafts/FOR/
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
