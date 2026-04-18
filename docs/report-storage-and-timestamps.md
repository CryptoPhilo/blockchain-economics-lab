# Report Storage and Timestamp System

## Overview

This document describes where ECON/FOR/MAT reports are stored and how the timestamp system works for badge display on the score page.

**Related Issue:** BCE-352

## Report Storage Architecture

### 1. Database Tables

#### `project_reports` Table
Primary table for tracking all reports. Schema:
- `id`: UUID primary key
- `project_id`: Reference to `tracked_projects`
- `report_type`: ENUM('econ', 'maturity', 'forensic')
- `status`: ENUM('assigned', 'in_progress', 'in_review', 'approved', 'published', 'cancelled', 'coming_soon')
- `published_at`: Timestamp when report was published
- `file_url`: Google Drive link to the actual report document
- `page_count`: Number of pages in the report
- Other metadata fields

**Current State (as of 2026-04-18):**
- Total reports: 115
- Published/coming_soon: 114
- Report documents stored in Google Drive

#### `tracked_projects` Table
Stores timestamp fields for badge display:
- `last_econ_report_at`: Timestamp of most recent ECON report
- `last_maturity_report_at`: Timestamp of most recent Maturity report
- `last_forensic_report_at`: Timestamp of most recent Forensic report

These fields are used by the score page to display report badges.

### 2. Document Storage

Report documents (PDFs) are stored in **Google Drive**. The `file_url` field in `project_reports` contains Google Drive links in the format:
```
https://drive.google.com/file/d/{file-id}/view?usp=drivesdk
```

**Examples:**
- Tether Maturity Report: `https://drive.google.com/file/d/1YNKvttZItYgGU_lRVY3uuVUBW0j7tD9G/view?usp=drivesdk`
- Bitcoin Maturity Report: `https://drive.google.com/file/d/1P8B20TH8LX09VCcd2P1evaptheOxc8f4/view?usp=drivesdk`
- RaveDAO Forensic Report: `https://drive.google.com/file/d/1-ZXKhrA1xCdC4QYh7diuiLS6jxhDFAl_/view?usp=drivesdk`

**Note:** Some reports with status `coming_soon` may not have `file_url` populated yet, as the document is still being prepared.

## Timestamp Synchronization System

### Automatic Trigger

A database trigger (`update_tracked_project_report_timestamp`) automatically updates timestamp fields when:
- A report status changes to 'published' or 'coming_soon'
- The report has a valid `published_at` timestamp

**Trigger Code:** `supabase/migrations/20260417_add_report_timestamp_trigger.sql`

### The Issue (BCE-352)

**Problem Identified:**
- 49 projects had reports marked as 'published' or 'coming_soon' but NULL timestamps in `tracked_projects`
- Root cause: Reports with `coming_soon` status often had NULL `published_at`, so the trigger didn't fire properly
- This caused score page badges to not display even though reports existed

**Breakdown:**
- 2 ECON reports with NULL timestamps
- 9 Maturity reports with NULL timestamps
- 38 Forensic reports with NULL timestamps

### The Solution

Created two scripts to audit and fix the timestamps:

#### 1. `scripts/audit-report-timestamps.ts`
Audits the database to find mismatches between report documents and timestamp fields.

**Usage:**
```bash
npx tsx scripts/audit-report-timestamps.ts
```

**Output:**
- Lists all projects with timestamp mismatches
- Generates `report-timestamp-audit.json` with detailed findings
- Identifies reports with NULL `published_at`
- Identifies reports with `file_url` but wrong status

#### 2. `scripts/sync-report-timestamps.ts`
Syncs missing timestamps from report records to tracked_projects.

**Usage:**
```bash
# Preview changes (dry run)
npx tsx scripts/sync-report-timestamps.ts --dry-run

# Apply updates
npx tsx scripts/sync-report-timestamps.ts
```

**Logic:**
- Uses `published_at` if available
- Falls back to `updated_at` if `published_at` is NULL
- Falls back to `created_at` if both above are NULL
- Only updates projects with NULL timestamps (doesn't overwrite existing)

**Results (2026-04-18):**
- ✅ Successfully synced 49 projects
- ✅ All timestamp mismatches resolved
- ✅ All existing reports now display badges correctly

## Verification

After running the sync, the audit shows:
```
Total reports in database: 115
Total tracked projects: 95
Projects with timestamp mismatches: 0
```

✅ All reports now have correct timestamps and badges should display properly on the score page.

## Recommendations for Future

1. **Set `published_at` when publishing:** Ensure reports have a valid `published_at` timestamp when status changes to 'published' or 'coming_soon'

2. **Run periodic audits:** Use `scripts/audit-report-timestamps.ts` to detect timestamp drift

3. **Monitor trigger behavior:** If new reports don't show badges, check:
   - Report status is 'published' or 'coming_soon'
   - Report has valid `published_at` timestamp
   - Trigger is active and functioning

4. **Consider improving the trigger:** The trigger could fall back to `updated_at` or `created_at` when `published_at` is NULL, similar to the sync script logic

## Related Files

- Database schema: `supabase/migrations/20260409_add_tracked_projects_and_project_subscriptions.sql`
- Timestamp trigger: `supabase/migrations/20260417_add_report_timestamp_trigger.sql`
- Audit script: `scripts/audit-report-timestamps.ts`
- Sync script: `scripts/sync-report-timestamps.ts`
- Audit report: `report-timestamp-audit.json`
