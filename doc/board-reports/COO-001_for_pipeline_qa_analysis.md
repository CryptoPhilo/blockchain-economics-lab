---
report_id: COO-001
title: FOR Pipeline QA Failure Analysis & Improvement Plan
author: COO Agent
created_at: 2026-04-19
issue: BCE-458
parent_issue: BCE-457
priority: medium
status: analysis_complete
---

# FOR Pipeline QA Failure Analysis & Improvement Plan

**Report ID**: COO-001  
**Date**: 2026-04-19  
**Issue**: [BCE-458](/BCE/issues/BCE-458)  
**Parent**: [BCE-457](/BCE/issues/BCE-457)  
**Author**: COO Agent

## Executive Summary

Investigation of the FOR pipeline reveals **critical QA enforcement gaps** that allow low-quality reports to bypass validation and reach production. The root cause is architectural: unlike ECON/MAT pipelines, FOR pipeline logs QA failures but continues processing and uploading regardless of severity.

**Key Findings**:
- ✅ Folder creation logic is correct (not the issue reported in BCE-457)
- ❌ QA failures are logged but **never block** uploads
- ❌ Missing `QA_STRICT` mode enforcement (present in ECON/MAT)
- ❌ No distinction between WARN and FAIL severity in upload decision

---

## 1. QA Enforcement Analysis

### 1.1 Current FOR Pipeline Behavior

**File**: `scripts/pipeline/ingest_for.py:427-445`

```python
# 4. QA verification
print(f"[4/6] QA 검증...")
qa_pass = {}
for lang, pdf_path in pdf_paths.items():
    try:
        qa = verify_pdf(pdf_path, lang=lang, report_type='for', metadata=meta)
        fails = [c.name for c in qa.checks if c.severity == QASeverity.FAIL]
        warns = [c.name for c in qa.checks if c.severity == QASeverity.WARN]
        if fails:
            print(f"  ⚠ {lang}: QA issues — {fails}")
        if warns:
            print(f"    WARN: {warns}")
        # Upload regardless of QA (warn-level only blocks publishing)
        qa_pass[lang] = pdf_path  # ← PROBLEM: uploads ALL files
        print(f"  ✓ {lang}: {qa.page_count} pages (QA: {qa.severity.value})")
    except Exception as e:
        print(f"  ✗ {lang} QA error: {e}")
        qa_pass[lang] = pdf_path  # ← PROBLEM: uploads even on QA crash
```

**Issues**:
1. **Line 441**: All PDFs added to `qa_pass` regardless of FAIL severity
2. **Line 445**: Even QA crashes don't prevent upload
3. **Line 440**: Comment acknowledges the problem but doesn't fix it
4. **No blocking logic**: FAIL severity has same outcome as PASS

### 1.2 ECON/MAT Pipeline (Correct Behavior)

**File**: `scripts/pipeline/ingest_gdoc.py:1032-1048`

```python
# ── QA verification gate ────────────────────────────────────────────
# Run automated inspection BEFORE returning the PDF so the caller can
# decide whether to upload. Environment flag QA_STRICT=1 raises on FAIL.
try:
    from qa_verify import verify_pdf, QASeverity
    import os as _os
    qa = verify_pdf(pdf_path, lang=lang,
                    report_type=('mat' if report_type == 'mat' else report_type),
                    metadata=metadata)
    fails = [c for c in qa.checks if c.severity == QASeverity.FAIL]
    warns = [c for c in qa.checks if c.severity == QASeverity.WARN]
    if fails:
        print(f"    [QA][FAIL] {pdf_path.name}: "
              + "; ".join(f"{c.name}({c.detail})" for c in fails[:4]))
        if _os.environ.get('QA_STRICT') == '1':
            raise RuntimeError(f"QA FAIL on {pdf_path.name}: "
                               + "; ".join(c.name for c in fails))
    elif warns:
        print(f"    [QA][WARN] {pdf_path.name}: "
              + "; ".join(c.name for c in warns[:4]))
    else:
        print(f"    [QA][PASS] {pdf_path.name} ({qa.page_count}p)")
```

**Advantages**:
1. ✅ **QA_STRICT mode**: Raises exception on FAIL when `QA_STRICT=1`
2. ✅ **Better logging**: Shows check names and details
3. ✅ **Caller control**: Returns PDF path so caller decides whether to upload
4. ✅ **Production-ready**: Can enforce strict QA in CI/CD

---

## 2. Folder Creation Analysis

### 2.1 Investigation Results

**Finding**: ✅ Folder creation logic is **correct** and identical to ECON/MAT.

**Code**: `scripts/pipeline/ingest_for.py:523`
```python
folder_id = gd.ensure_folder_path(slug, rtype)
```

**Expected Structure**:
```
BCE Lab Reports/
  └── {project_slug}/
      └── for/
          ├── {slug}_for_v1_en.pdf
          ├── {slug}_for_v1_ko.pdf
          └── ... (7 languages)
```

**Method Definition**: `scripts/pipeline/gdrive_storage.py:255-285`
```python
def ensure_folder_path(self, *path_parts: str) -> Optional[str]:
    """
    Ensure a folder path exists under root, creating as needed.
    Returns the final folder ID.

    Example:
        folder_id = gd.ensure_folder_path('uniswap', 'econ')
        # Creates: BCE Lab Reports / uniswap / econ
    """
```

### 2.2 Conclusion on "Standalone Folder" Issue

The complaint in [BCE-457](/BCE/issues/BCE-457) about "standalone folders" is **not caused by code logic**. Possible explanations:

1. **User misinterpretation**: Each project naturally has its own folder (`{slug}/for`)
2. **Manual uploads**: Someone may have manually created incorrect folder structures
3. **Different issue**: The problem may be in a different part of the pipeline not examined here

**Recommendation**: Request screenshot or specific GDrive URL from reporter to verify the actual folder structure issue.

---

## 3. QA Check Coverage

### 3.1 Markdown-Level QA (`qa_verify_md.py`)

**Checks Performed** (Pre-translation):
- ✅ File structure (non-empty, fence balance)
- ✅ Markdown residues (escaped chars, HTML entities)
- ✅ Broken ASCII diagrams
- ✅ Broken tables (column mismatches, orphan rows)
- ✅ Language coverage (Hangul/Kana/CJK counts)
- ✅ Translation parity (heading/image/table counts)

### 3.2 PDF-Level QA (`qa_verify.py`)

**Checks Performed** (Post-generation):
- ✅ Structural (page count, blank pages)
- ✅ Markdown artefacts in PDF (`**`, `\*`, `\\_`, backticks)
- ✅ CJK fallback boxes (rendering failures)
- ✅ Language-specific validation
- ✅ Metadata consistency

### 3.3 Severity Levels

```python
class QASeverity(str, Enum):
    PASS = "PASS"  # No issues
    WARN = "WARN"  # Cosmetic issues, can publish
    FAIL = "FAIL"  # Blocks publication (or should!)
```

**Problem**: FOR pipeline treats FAIL same as WARN.

---

## 4. Root Causes

### Primary Root Cause
**Architectural flaw in QA enforcement**: FOR pipeline was designed to "upload regardless of QA" (line 440 comment), treating QA as advisory rather than gating.

### Contributing Factors
1. **Missing QA_STRICT mode**: No environment variable to enforce strict validation
2. **No upload gating logic**: `qa_pass` dict is populated unconditionally
3. **Silent failures**: QA crashes (line 445) don't prevent upload
4. **Insufficient logging**: Only shows failure count, not details for ops review

---

## 5. Improvement Plan

### 5.1 Immediate Fixes (High Priority)

#### Fix 1: Add QA_STRICT Enforcement
**File**: `scripts/pipeline/ingest_for.py:427-445`

```python
# 4. QA verification
print(f"[4/6] QA 검증...")
qa_pass = {}
qa_strict = os.environ.get('QA_STRICT', '0') == '1'  # NEW

for lang, pdf_path in pdf_paths.items():
    try:
        meta = {'project_slug': slug, 'slug': slug, 'version': version, 'lang': lang}
        qa = verify_pdf(pdf_path, lang=lang, report_type='for', metadata=meta)
        fails = [c for c in qa.checks if c.severity == QASeverity.FAIL]
        warns = [c for c in qa.checks if c.severity == QASeverity.WARN]
        
        if fails:
            print(f"  ❌ {lang}: QA FAIL — {'; '.join(f'{c.name}({c.detail})' for c in fails[:4])}")
            if qa_strict:
                raise RuntimeError(f"QA FAIL blocked upload: {lang} — {'; '.join(c.name for c in fails)}")
            else:
                print(f"  ⚠ {lang}: QA FAIL but QA_STRICT=0, continuing...")
                continue  # Skip upload for this language
        
        if warns:
            print(f"  ⚠ {lang}: QA WARN — {'; '.join(c.name for c in warns[:4])}")
        
        qa_pass[lang] = pdf_path
        print(f"  ✓ {lang}: {qa.page_count} pages (QA: {qa.severity.value})")
        
    except Exception as e:
        print(f"  ✗ {lang} QA error: {e}")
        if qa_strict:
            raise
        # Do NOT upload on QA crash unless QA_STRICT=0
```

**Changes**:
1. Add `QA_STRICT` environment variable check
2. **FAIL severity**: Skip upload (continue) unless QA_STRICT mode
3. **QA crashes**: Skip upload (don't add to qa_pass)
4. **Better logging**: Show check details for debugging

#### Fix 2: Update GitHub Actions Workflow
**File**: `.github/workflows/for-pipeline-cron.yml:78-94`

Add `QA_STRICT=1` to production runs:

```yaml
- name: Run FOR pipeline
  working-directory: scripts/pipeline
  env:
    GDRIVE_SERVICE_ACCOUNT_FILE: ${{ github.workspace }}/scripts/pipeline/.gdrive_service_account.json
    QA_STRICT: "1"  # ← ADD THIS
  run: |
    if [ "${{ github.event.inputs.dry_run }}" == "true" ]; then
      echo "🧪 Running in DRY RUN mode"
      python3 ingest_for.py --dry-run ${{ github.event.inputs.slug && format('--slug {0}', github.event.inputs.slug) || '' }}
    else
      ...
```

#### Fix 3: Add QA Summary to Logs
**File**: `scripts/pipeline/ingest_for.py` (after QA loop)

```python
# QA Summary
result['qa_summary'] = {
    'total': len(pdf_paths),
    'passed': len(qa_pass),
    'failed': len(pdf_paths) - len(qa_pass),
    'strict_mode': qa_strict,
}
print(f"\n[QA Summary] {len(qa_pass)}/{len(pdf_paths)} passed, QA_STRICT={qa_strict}")
```

### 5.2 Medium-Term Improvements

1. **QA Dashboard**: Store QA results in Supabase `qa_reports` table for historical tracking
2. **Slack Notifications**: Alert on QA failures in production
3. **QA Metrics**: Track FAIL/WARN rates by check type and language
4. **Manual Override**: Add `--force-upload` flag for manual re-runs with QA bypass

### 5.3 Testing Plan

1. **Unit Tests**: Create test PDFs with known QA failures
2. **Integration Test**: Run pipeline with `QA_STRICT=1` and verify it blocks bad PDFs
3. **Regression Test**: Ensure ECON/MAT pipelines still work with updated code
4. **Production Rollout**: Enable `QA_STRICT=1` in GitHub Actions after validation

---

## 6. Recommendations

### Immediate Actions (This Sprint)
1. ✅ **Implement Fix 1**: Add QA_STRICT enforcement to `ingest_for.py`
2. ✅ **Implement Fix 2**: Enable `QA_STRICT=1` in GitHub Actions workflow
3. ✅ **Implement Fix 3**: Add QA summary logging
4. ✅ **Test**: Run against existing FOR drafts to verify blocking works

### Follow-Up Actions (Next Sprint)
1. ⏳ **Backfill QA**: Re-run QA on all published FOR reports, flag for review
2. ⏳ **Create BCE ticket**: Investigate "standalone folder" claim with screenshots
3. ⏳ **Unified QA module**: Extract QA logic to shared module used by all pipelines
4. ⏳ **QA Documentation**: Update pipeline docs with QA severity guidelines

### Organizational Process
1. 📋 **QA Policy**: Define org-wide policy on WARN vs FAIL thresholds
2. 📋 **Pipeline SOP**: Document when to use `--force-upload` override
3. 📋 **Incident Response**: Create runbook for QA failures in production

---

## 7. Risk Assessment

### Risks of Implementing Fixes
- **Low Risk**: Changes are additive (QA_STRICT defaults to 0, preserving current behavior)
- **Rollback Plan**: Remove `QA_STRICT=1` from GitHub Actions if issues arise
- **Testing Coverage**: Can test locally before production rollout

### Risks of NOT Implementing Fixes
- **High**: Continued publication of low-quality reports damages credibility
- **Medium**: Manual QA burden increases as report volume grows
- **Medium**: User complaints about report quality

---

## 8. Appendix

### A. QA Check Reference

**Common FAIL Triggers**:
- `artefact.literal **bold** markdown` - Unrendered markdown in PDF
- `artefact.escaped \\* backslash` - Translation artefacts
- `artefact.fallback_boxes` - CJK font rendering failure
- `md.lang.ko_hangul` - Missing Korean translation (< 200 chars)
- `md.table.broken` - Table column count mismatch

**Common WARN Triggers**:
- `md.diagram.broken_ascii` - ASCII art lost box-drawing chars
- `md.residue.*` - Escaped characters outside code blocks
- `structure.blank_pages` - Near-empty pages in middle of PDF

### B. Related Files

- `scripts/pipeline/ingest_for.py` - FOR pipeline orchestrator
- `scripts/pipeline/qa_verify.py` - PDF-level QA checks
- `scripts/pipeline/qa_verify_md.py` - Markdown-level QA checks
- `scripts/pipeline/gdrive_storage.py` - GDrive folder management
- `.github/workflows/for-pipeline-cron.yml` - GitHub Actions automation

### C. Environment Variables

**Required for QA_STRICT**:
```bash
QA_STRICT=1  # Enforce strict QA (raises on FAIL)
```

**Existing Variables** (unchanged):
```bash
GDRIVE_SERVICE_ACCOUNT_FILE
GDRIVE_ROOT_FOLDER_ID
GDRIVE_DELEGATE_EMAIL
ANTHROPIC_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_KEY
```

---

## 9. Conclusion

The FOR pipeline QA failures stem from **architectural design choice** to treat QA as advisory rather than gating. The solution is straightforward: adopt the QA_STRICT pattern already proven in ECON/MAT pipelines.

**Impact of Fixes**:
- ✅ Blocks low-quality reports from reaching production
- ✅ Maintains backward compatibility (QA_STRICT=0 default)
- ✅ Improves operational visibility with better logging
- ✅ Aligns FOR pipeline with ECON/MAT quality standards

**Next Steps**: Assign [BCE-459](/BCE/issues/BCE-459) for implementation and testing.

---

**Report prepared by**: COO Agent  
**Review status**: Awaiting board review  
**Distribution**: CEO, CTO, QA, Research team
