# Google Docs Support for ECON/MAT Pipeline

## Issue: BCE-454

## Changes Implemented

> Note: As of `BCE-634`, the draft ingress path is shared via `gdrive_drafts.py`.
> `ingest_gdoc.py` now delegates folder resolution, markdown/Google Docs scanning,
> and content download to the common helper used by `ingest_for.py`.

### 1. Enhanced `scan_new_md_files()` function

**Location**: `ingest_gdoc.py` + `gdrive_drafts.py`

**Changes**:
- Uses shared draft scanner from `gdrive_drafts.py`
- Includes Google Docs detection query (`application/vnd.google-apps.document`)
- Merges results from both `.md` files and Google Docs
- Adds `_gdoc` flag to track Google Docs for special handling
- Adds synthetic `.md` extension to Google Docs for slug parsing

**Implementation**:
```python
docs = scan_markdown_drafts(drive, folder_id)
```

### 2. Enhanced `download_md_file()` function

**Location**: `ingest_gdoc.py` + `gdrive_drafts.py`

**Changes**:
- Delegates to shared `download_markdown_text()`
- Supports `is_gdoc` parameter for Google Docs export
- Google Docs are exported as `text/plain` mimetype
- Handles both string and bytes response from export API

**Implementation**:
```python
def download_md_file(drive, file_id: str, is_gdoc: bool = False) -> str:
    return download_markdown_text(drive, file_id, is_gdoc=is_gdoc)
```

### 3. Added `_strip_equation_images()` function

**Location**: `ingest_gdoc.py` lines 263-298

**Changes**:
- Ported from `ingest_for.py` (lines 64-92)
- Removes base64 PNG equation images from Google Docs export
- Cleans up `![][imageN]` references and their definitions

**Why**: Google Docs converts LaTeX expressions to inline PNG images. When exported to text/markdown, these become base64 data URLs that need to be stripped.

### 4. Updated `process_single_md()` to use Google Docs flag

**Location**: `ingest_gdoc.py` lines 1026-1039

**Changes**:
- Detects `_gdoc` flag from document metadata
- Passes `is_gdoc` parameter to `download_md_file()`
- Uses local `_strip_equation_images()` function instead of importing

## Testing

### Syntax Validation
✓ Module imports successfully without errors

### Manual Testing Steps

1. **Upload a Google Doc to `drafts/ECON/`**
   ```bash
   # Upload via GDrive web interface or API
   ```

2. **Run dry-run test**
   ```bash
   python3 ingest_gdoc.py --type econ --dry-run
   ```

3. **Verify detection**
   - Check console output for Google Doc detection
   - Verify download with "(Google Doc export)" message
   - Confirm equation stripping if LaTeX present

4. **Full pipeline test**
   ```bash
   python3 ingest_gdoc.py --type econ
   ```

5. **Verify output**
   - Check translation completion
   - Verify PDF generation (7 languages)
   - Confirm GDrive upload
   - Validate Supabase registration

## Compatibility

- ✅ Maintains backward compatibility with .md files
- ✅ Shares the same Drive ingress architecture as FOR pipeline (`ingest_for.py`)
- ✅ Reuses proven equation stripping logic
- ✅ No breaking changes to existing functionality

## Reference

- **Shared helper**: `gdrive_drafts.py`
- **FOR Pipeline**: `ingest_for.py`
- **Issue**: [BCE-454](/BCE/issues/BCE-454)
- **Parent Issue**: [BCE-450](/BCE/issues/BCE-450)

## Next Steps

1. ✅ Code implementation complete
2. ⏳ Create test Google Doc in `drafts/ECON/`
3. ⏳ Run dry-run validation
4. ⏳ Run full pipeline test
5. ⏳ Update issue status to done
