# Google Docs Support for ECON/MAT Pipeline

## Issue: BCE-454

## Changes Implemented

### 1. Enhanced `scan_new_md_files()` function

**Location**: `ingest_gdoc.py` lines 328-362

**Changes**:
- Added Google Docs detection query (`application/vnd.google-apps.document`)
- Merged results from both .md files and Google Docs
- Added `_gdoc` flag to track Google Docs for special handling
- Added synthetic `.md` extension to Google Docs for slug parsing

**Implementation**:
```python
# Query 2: Google Docs (may be uploaded via web without .md extension)
q_gdocs = (f"'{folder_id}' in parents "
           f"and mimeType='application/vnd.google-apps.document' "
           f"and trashed=false")
```

### 2. Enhanced `download_md_file()` function

**Location**: `ingest_gdoc.py` lines 349-360

**Changes**:
- Added `is_gdoc` parameter to handle Google Docs export
- Google Docs are exported as `text/plain` mimetype
- Handles both string and bytes response from export API

**Implementation**:
```python
def download_md_file(drive, file_id: str, is_gdoc: bool = False) -> str:
    if is_gdoc:
        content = drive.files().export(fileId=file_id, mimeType='text/plain').execute()
        if isinstance(content, str):
            content = content.encode('utf-8')
    else:
        content = drive.files().get_media(fileId=file_id).execute()
    return content.decode('utf-8')
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

1. **Upload a Google Doc to drafts/econ/**
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
- ✅ Follows same architecture as FOR pipeline (`ingest_for.py`)
- ✅ Reuses proven equation stripping logic
- ✅ No breaking changes to existing functionality

## Reference

- **FOR Pipeline**: `ingest_for.py` lines 223-235 (Google Docs query), 296-308 (export handling), 64-92 (equation stripping)
- **Issue**: [BCE-454](/BCE/issues/BCE-454)
- **Parent Issue**: [BCE-450](/BCE/issues/BCE-450)

## Next Steps

1. ✅ Code implementation complete
2. ⏳ Create test Google Doc in drafts/econ/
3. ⏳ Run dry-run validation
4. ⏳ Run full pipeline test
5. ⏳ Update issue status to done
