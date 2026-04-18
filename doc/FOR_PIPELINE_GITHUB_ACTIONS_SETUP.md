# FOR Pipeline - GitHub Actions Setup Guide

**Task**: BCE-364  
**Workflow**: `.github/workflows/for-pipeline-cron.yml`  
**Purpose**: Automated FOR report processing using GitHub Actions cron instead of Paperclip routine

## Overview

The FOR pipeline has been migrated from Paperclip routine scheduling to GitHub Actions for:
- Better reliability and visibility
- Integrated CI/CD with the main repository
- Built-in logging and artifact storage
- No dependency on external Paperclip infrastructure

## Workflow Schedule

- **Cron**: Every 30 minutes (`*/30 * * * *`)
- **Manual Trigger**: Available via workflow_dispatch with optional parameters
- **Timeout**: 60 minutes per run

## Required GitHub Secrets

Configure these secrets in: **Settings → Secrets and variables → Actions → Repository secrets**

### Supabase Credentials

| Secret Name | Description | Example |
|------------|-------------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | `https://your-project.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |

### Google Drive Credentials

| Secret Name | Description | Example |
|------------|-------------|---------|
| `GDRIVE_ROOT_FOLDER_ID` | Root folder ID in Google Drive | `1E87EcasPlrGuet0t6e1CA9kLFO0sTdFq` |
| `GDRIVE_DELEGATE_EMAIL` | Email for domain-wide delegation | `zhang@coinlab.co.kr` |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | Full JSON content of service account key | `{"type":"service_account",...}` |

**Important**: For `GDRIVE_SERVICE_ACCOUNT_JSON`, copy the **entire contents** of your `.gdrive_service_account.json` file as-is.

### API Keys

| Secret Name | Description | Example |
|------------|-------------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key for translation | `sk-ant-api03-...` |
| `ETHERSCAN_API_KEY` | Etherscan API key for blockchain data | `ABC123...` |
| `COINMARKETCAP_API_KEY` | CoinMarketCap API key | `abc-123-def...` |
| `RESEND_API_KEY` | Resend email API key | `re_...` |

## Manual Workflow Trigger

### Process All New Reports
1. Go to **Actions** tab in GitHub
2. Select **FOR Pipeline - Automated Processing**
3. Click **Run workflow**
4. Leave inputs empty
5. Click **Run workflow**

### Process Specific Project
1. Go to **Actions** tab
2. Select **FOR Pipeline - Automated Processing**
3. Click **Run workflow**
4. Enter slug in **slug** field (e.g., `bitcoin`)
5. Click **Run workflow**

### Dry Run (Test Mode)
1. Go to **Actions** tab
2. Select **FOR Pipeline - Automated Processing**
3. Click **Run workflow**
4. Check the **dry_run** checkbox
5. Click **Run workflow**

This will download files from GDrive but skip processing, useful for testing configuration.

## Monitoring

### View Logs
1. Go to **Actions** tab
2. Click on a workflow run
3. Expand **Process FOR Reports** job
4. View individual step logs

### Download Artifacts
After each run, pipeline logs are stored as artifacts:
- Location: Workflow run page → **Artifacts** section
- Name: `for-pipeline-logs-{run-number}`
- Retention: 30 days
- Contents:
  - `scripts/pipeline/output/*.json` - Processing results
  - `scripts/pipeline/output/*.log` - Detailed logs
  - `logs/for_pipeline/*.md` - Scan logs

### Check Summary
Each workflow run generates a summary with:
- Trigger type (scheduled or manual)
- Run ID and timestamp
- Slug filter (if specified)
- Preview of latest log file

## Troubleshooting

### Workflow Fails to Start
- **Check**: All required secrets are configured
- **Verify**: Repository has Actions enabled (Settings → Actions → General)

### Authentication Errors
- **Google Drive**: Verify `GDRIVE_SERVICE_ACCOUNT_JSON` is valid JSON
- **Supabase**: Check service key has necessary permissions
- **APIs**: Ensure API keys haven't expired

### No Files Detected
- **Verify**: `drafts/FOR/` folder exists in Google Drive
- **Check**: Service account has read access to the folder
- **Test**: Run with dry_run mode to test GDrive scanning

### Pipeline Processing Fails
- **View Logs**: Download artifacts and check detailed error messages
- **Verify API Keys**: Ensure Anthropic, Etherscan keys are valid
- **Check Supabase**: Verify database connection and schema

### Timeout Issues
- Default timeout: 60 minutes
- If needed, increase in workflow file: `timeout-minutes: 90`

## Migration from Paperclip Routine

### Before Migration
- Ensure all GitHub secrets are configured
- Test workflow manually with dry_run mode
- Verify at least one successful full run

### Deactivate Paperclip Routine

#### Option 1: Via Paperclip UI
1. Log into Paperclip dashboard
2. Navigate to **Routines**
3. Find **FOR Draft Watcher** routine
4. Click **Pause** or **Delete**

#### Option 2: Via Paperclip API
```bash
# List all routines
curl -H "Authorization: Bearer $PAPERCLIP_TOKEN" \
  https://api.paperclip.ai/api/companies/{companyId}/routines

# Pause the routine
curl -X PATCH \
  -H "Authorization: Bearer $PAPERCLIP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "paused"}' \
  https://api.paperclip.ai/api/routines/{routineId}

# Or delete the routine
curl -X DELETE \
  -H "Authorization: Bearer $PAPERCLIP_TOKEN" \
  https://api.paperclip.ai/api/routines/{routineId}
```

### After Migration
- Monitor GitHub Actions runs for 24-48 hours
- Verify processed files are tracked correctly
- Confirm no duplicate processing occurs
- Update documentation to reference GitHub Actions workflow

## Comparison: Paperclip vs GitHub Actions

| Feature | Paperclip Routine | GitHub Actions |
|---------|------------------|----------------|
| **Scheduling** | 30-min cron | 30-min cron |
| **Logging** | External logs | Built-in GitHub logs |
| **Artifacts** | Manual storage | Automatic artifact storage |
| **Monitoring** | Paperclip dashboard | GitHub Actions UI |
| **Debugging** | Remote access needed | All logs in GitHub |
| **Cost** | Paperclip subscription | GitHub Actions minutes (free tier: 2000/month) |
| **Reliability** | Depends on Paperclip | GitHub infrastructure |

## Cost Estimation

GitHub Actions free tier includes:
- **2,000 minutes/month** for private repos
- **Unlimited** for public repos

Estimated usage:
- **Per run**: ~5-10 minutes (with reports to process)
- **Frequency**: 48 runs/day (every 30 minutes)
- **Monthly**: ~1,440 runs × 5 min = **7,200 minutes**

**Recommendation**: Upgrade to GitHub Team plan ($4/user/month) which includes 3,000 minutes, or adjust schedule to hourly (`0 * * * *`) to reduce usage.

## Related Files

- `.github/workflows/for-pipeline-cron.yml` - Main workflow definition
- `scripts/pipeline/ingest_for.py` - FOR pipeline processor
- `scripts/pipeline/FOR_WATCHER_SETUP.md` - Original Paperclip setup guide (deprecated)
- `scripts/pipeline/output/_for_processed.json` - Processed files tracker

## Support

For issues or questions:
1. Check workflow logs first
2. Review this documentation
3. Test with dry_run mode to isolate issues
4. Contact DevOps team if infrastructure issues persist
