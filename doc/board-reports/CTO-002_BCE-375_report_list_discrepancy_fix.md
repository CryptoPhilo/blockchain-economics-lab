# CTO-002: BCE-375 Report List Discrepancy - Root Cause & Fix

**Issue**: BCE-375 리포트 노출 목록 차이  
**Status**: Fixed (requires database migration)  
**Date**: 2026-04-18  
**Reporter**: CTO

## Executive Summary

The `/ko/reports` (급변동 종목) page was showing only 1 FOR report instead of the expected 28 reports created within the last 72 hours. Root cause identified as a Row Level Security (RLS) policy mismatch between the database and application code.

**Impact**: 96% of recent FOR reports were hidden from users due to restrictive RLS policy.

## Root Cause Analysis

### The Problem

1. **Database State**: 28 FOR reports exist within 72 hours, but 27 have `status='coming_soon'` and only 1 has `status='published'`

2. **Application Code** (`src/app/[locale]/reports/page.tsx`):
   ```typescript
   // Lines 81-82: Query includes both statuses
   .in('status', ['published', 'coming_soon'])
   ```

3. **Database RLS Policy** (`supabase/migrations/20260409_...sql` line 134):
   ```sql
   CREATE POLICY "Public can view published reports" 
   ON project_reports FOR SELECT 
   USING (status = 'published');  -- ❌ Only allows 'published'
   ```

### Verification Tests

```bash
# With SERVICE_ROLE_KEY (bypasses RLS): 28 reports ✅
# With ANON_KEY (public access): 1 report ❌
```

The RLS policy was created before OPS-007, which added support for `coming_soon` reports. The policy was never updated to reflect this change.

## Solution

### Migration File Created

**File**: `supabase/migrations/20260418_fix_rls_for_coming_soon_reports.sql`

```sql
-- Drop the old restrictive policy
DROP POLICY IF EXISTS "Public can view published reports" ON project_reports;

-- Create new policy that allows both published and coming_soon reports
CREATE POLICY "Public can view published and coming soon reports"
  ON project_reports
  FOR SELECT
  USING (status IN ('published', 'coming_soon'));
```

### How to Apply

**Option 1: Supabase Dashboard (Recommended)**
1. Open [Supabase Dashboard](https://supabase.com/dashboard/project/wbqponoiyoeqlepxogcb)
2. Go to SQL Editor
3. Paste and execute the migration SQL above
4. Verify with: `SELECT count(*) FROM project_reports WHERE report_type='forensic' AND status='coming_soon'`

**Option 2: Supabase CLI**
```bash
npx supabase login
npx supabase link --project-ref wbqponoiyoeqlepxogcb
npx supabase db push
```

### Verification Script

Run this to confirm the fix:
```bash
node scripts/apply-rls-migration.mjs
```

Expected output after fix:
```
✅ RLS policy is working correctly - showing both published and coming_soon reports
Total FOR reports (anon access): 28
```

## Impact Assessment

### Before Fix
- Public users: 1 report visible (3.6%)
- Admin users (service role): 28 reports visible (100%)

### After Fix
- All users: 28 reports visible (100%)
- User experience: Rapid change alerts page now shows all recent reports as intended

## Related Issues

- **OPS-007**: Added `coming_soon` status support
- **BCE-356**: Added 72-hour filter for FOR reports
- **BCE-375**: This fix (RLS policy update)

## Recommendations

1. **Immediate**: Apply the migration via Supabase dashboard
2. **Process**: Add RLS policy validation to pre-deployment checklist
3. **Testing**: Create E2E tests that verify public access matches admin access for public endpoints
4. **Documentation**: Document RLS policies alongside status enum changes

## Files Modified

- ✅ `supabase/migrations/20260418_fix_rls_for_coming_soon_reports.sql` (new)
- ✅ `scripts/apply-rls-migration.mjs` (verification script)

## Next Steps

1. Board member to execute migration SQL in Supabase dashboard
2. Verify fix with verification script
3. Test `/ko/reports` page shows all 28 reports
4. Close BCE-375

---

**Prepared by**: CTO  
**Report ID**: CTO-002  
**Related Ticket**: [BCE-375](/BCE/issues/BCE-375)
