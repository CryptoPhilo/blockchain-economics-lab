# GitHub Secrets Setup Checklist for FOR Pipeline

Use this checklist when configuring GitHub Actions secrets for the FOR pipeline workflow.

## Setup Location
**GitHub Repository → Settings → Secrets and variables → Actions → Repository secrets**

## Checklist

### ✅ Supabase (3 secrets)
- [ ] `NEXT_PUBLIC_SUPABASE_URL`
  - Find in: Supabase project settings → API
  - Format: `https://xxx.supabase.co`
  
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - Find in: Supabase project settings → API → anon public
  - Format: Long JWT token starting with `eyJ`
  
- [ ] `SUPABASE_SERVICE_KEY`
  - Find in: Supabase project settings → API → service_role (secret!)
  - Format: Long JWT token starting with `eyJ`

### ✅ Google Drive (3 secrets)
- [ ] `GDRIVE_ROOT_FOLDER_ID`
  - Find in: Google Drive folder URL
  - Format: Last segment of URL (e.g., `1E87EcasPlrGuet0t6e1CA9kLFO0sTdFq`)
  
- [ ] `GDRIVE_DELEGATE_EMAIL`
  - Format: Email address for domain-wide delegation
  - Example: `zhang@coinlab.co.kr`
  
- [ ] `GDRIVE_SERVICE_ACCOUNT_JSON`
  - Source: Service account JSON key file from Google Cloud Console
  - **Important**: Copy the ENTIRE file content (including `{` and `}`)
  - Verify: Should start with `{"type":"service_account"`

### ✅ API Keys (4 secrets)
- [ ] `ANTHROPIC_API_KEY`
  - Find in: Anthropic Console → API Keys
  - Format: `sk-ant-api03-...`
  
- [ ] `ETHERSCAN_API_KEY`
  - Find in: Etherscan.io → My API Keys
  - Format: Alphanumeric string
  
- [ ] `COINMARKETCAP_API_KEY`
  - Find in: CoinMarketCap API → Developer Portal
  - Format: UUID-style with dashes
  
- [ ] `RESEND_API_KEY`
  - Find in: Resend dashboard → API Keys
  - Format: `re_...`

## Quick Setup Commands

### Using GitHub CLI
```bash
# Set Supabase secrets
gh secret set NEXT_PUBLIC_SUPABASE_URL -b "https://your-project.supabase.co"
gh secret set NEXT_PUBLIC_SUPABASE_ANON_KEY -b "your-anon-key"
gh secret set SUPABASE_SERVICE_KEY -b "your-service-key"

# Set Google Drive secrets
gh secret set GDRIVE_ROOT_FOLDER_ID -b "your-folder-id"
gh secret set GDRIVE_DELEGATE_EMAIL -b "zhang@coinlab.co.kr"
gh secret set GDRIVE_SERVICE_ACCOUNT_JSON < /path/to/service-account.json

# Set API keys
gh secret set ANTHROPIC_API_KEY -b "sk-ant-api03-..."
gh secret set ETHERSCAN_API_KEY -b "your-etherscan-key"
gh secret set COINMARKETCAP_API_KEY -b "your-cmc-key"
gh secret set RESEND_API_KEY -b "re_..."
```

### Using .env.local as Reference
```bash
# If you have .env.local configured locally, extract values:
source .env.local

gh secret set NEXT_PUBLIC_SUPABASE_URL -b "$NEXT_PUBLIC_SUPABASE_URL"
gh secret set NEXT_PUBLIC_SUPABASE_ANON_KEY -b "$NEXT_PUBLIC_SUPABASE_ANON_KEY"
gh secret set SUPABASE_SERVICE_KEY -b "$SUPABASE_SERVICE_KEY"
gh secret set GDRIVE_ROOT_FOLDER_ID -b "$GDRIVE_ROOT_FOLDER_ID"
gh secret set GDRIVE_DELEGATE_EMAIL -b "$GDRIVE_DELEGATE_EMAIL"
gh secret set GDRIVE_SERVICE_ACCOUNT_JSON < "$GDRIVE_SERVICE_ACCOUNT_FILE"
gh secret set ANTHROPIC_API_KEY -b "$ANTHROPIC_API_KEY"
gh secret set ETHERSCAN_API_KEY -b "$ETHERSCAN_API_KEY"
gh secret set COINMARKETCAP_API_KEY -b "$COINMARKETCAP_API_KEY"
gh secret set RESEND_API_KEY -b "$RESEND_API_KEY"
```

## Verification Steps

### 1. List All Secrets
```bash
gh secret list
```
Expected output: 11 secrets listed

### 2. Test Workflow (Dry Run)
1. Go to **Actions** tab
2. Select **FOR Pipeline - Automated Processing**
3. Click **Run workflow**
4. Enable **dry_run** checkbox
5. Click **Run workflow**
6. Wait for completion (~2-5 minutes)
7. Check logs for errors

### 3. Verify Each Secret Category

#### Supabase Test
- Should see: "Connected to Supabase" or database queries succeed
- Error pattern: "Invalid API key" → check service key

#### Google Drive Test
- Should see: "Found X files in drafts/FOR/"
- Error pattern: "403 Forbidden" → check service account permissions
- Error pattern: "Folder not found" → check root folder ID

#### API Keys Test
- Should see: Translation API responses (Anthropic)
- Error pattern: "API key invalid" → check respective key

## Common Issues

### Issue: "Secret not found" in workflow
**Solution**: Ensure secret names match EXACTLY (case-sensitive)

### Issue: Google Drive 403 Forbidden
**Solutions**:
1. Verify service account has read/write access to folders
2. Check domain-wide delegation is configured
3. Verify delegate email is correct

### Issue: Supabase connection failed
**Solutions**:
1. Check URL format (must include `https://`)
2. Verify service key is from correct project
3. Test connection manually with `curl`

### Issue: Invalid JSON for service account
**Solutions**:
1. Re-copy the file ensuring no extra whitespace
2. Verify file starts with `{` and ends with `}`
3. Use `cat file.json | gh secret set ...` to avoid formatting issues

## Security Best Practices

- ✅ Use service role keys only in GitHub Actions (never in frontend code)
- ✅ Rotate API keys quarterly
- ✅ Limit service account permissions to minimum required
- ✅ Never commit secrets to git (use `.env.local` which is gitignored)
- ✅ Use separate API keys for production vs staging if available
- ✅ Monitor GitHub Actions logs for exposed secrets (GitHub auto-masks them)

## Next Steps After Setup

1. ✅ Complete this checklist
2. ✅ Run dry-run test
3. ✅ Run full test with manual trigger
4. ✅ Monitor first scheduled run (wait up to 30 minutes)
5. ✅ Deactivate Paperclip routine once confirmed working
6. ✅ Update team documentation

## Support

If you encounter issues:
1. Check this checklist first
2. Review `doc/FOR_PIPELINE_GITHUB_ACTIONS_SETUP.md`
3. Check GitHub Actions logs
4. Contact DevOps team
