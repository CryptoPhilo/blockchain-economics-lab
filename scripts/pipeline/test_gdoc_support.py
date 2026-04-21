#!/usr/bin/env python3
"""
Test script for Google Docs support in ingest_gdoc.py
Validates the new functionality without requiring actual GDrive access.
"""
import sys
from pathlib import Path

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_strip_equation_images():
    """Test _strip_equation_images function."""
    from ingest_gdoc import _strip_equation_images

    # Test case 1: Markdown with equation images
    test_md = """
# Test Document

Some text with equation ![][image1] inline.

Another equation: ![][image2]

More content here.

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA>
[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA>
"""

    cleaned, count = _strip_equation_images(test_md)

    assert count == 2, f"Expected 2 images stripped, got {count}"
    assert '![][image1]' not in cleaned, "Image reference 1 not removed"
    assert '![][image2]' not in cleaned, "Image reference 2 not removed"
    assert '[image1]:' not in cleaned, "Image definition 1 not removed"
    assert '[image2]:' not in cleaned, "Image definition 2 not removed"
    assert '# Test Document' in cleaned, "Content was removed"

    print("✓ test_strip_equation_images passed")
    return True

def test_scan_logic_structure():
    """Verify scan_new_md_files delegates to the shared draft scanner."""
    import inspect
    from ingest_gdoc import scan_new_md_files
    from gdrive_drafts import scan_markdown_drafts

    sig = inspect.signature(scan_new_md_files)
    params = list(sig.parameters.keys())

    assert 'drive' in params, "Missing 'drive' parameter"
    assert 'folder_id' in params, "Missing 'folder_id' parameter"
    assert 'tracker' in params, "Missing 'tracker' parameter"

    source = inspect.getsource(scan_new_md_files)
    assert 'scan_markdown_drafts' in source, \
        "Missing shared draft scanner usage"

    shared_source = inspect.getsource(scan_markdown_drafts)
    assert 'application/vnd.google-apps.document' in shared_source, \
        "Missing Google Docs query in shared scanner"
    assert '_gdoc' in shared_source, \
        "Missing _gdoc flag handling in shared scanner"

    print("✓ test_scan_logic_structure passed")
    return True

def test_download_signature():
    """Verify download_md_file delegates to the shared download helper."""
    import inspect
    from ingest_gdoc import download_md_file
    from gdrive_drafts import download_markdown_text

    sig = inspect.signature(download_md_file)
    params = list(sig.parameters.keys())

    assert 'drive' in params, "Missing 'drive' parameter"
    assert 'file_id' in params, "Missing 'file_id' parameter"
    assert 'is_gdoc' in params, "Missing 'is_gdoc' parameter"

    # Check default value
    is_gdoc_default = sig.parameters['is_gdoc'].default
    assert is_gdoc_default is False, \
        f"is_gdoc default should be False, got {is_gdoc_default}"

    source = inspect.getsource(download_md_file)
    assert 'download_markdown_text' in source, \
        "Missing shared download helper usage"

    shared_source = inspect.getsource(download_markdown_text)
    assert 'export' in shared_source, "Missing export() call for Google Docs"
    assert 'text/plain' in shared_source, "Missing text/plain mimetype"

    print("✓ test_download_signature passed")
    return True

def test_process_single_md_integration():
    """Verify process_single_md uses the new _gdoc flag."""
    import inspect
    from ingest_gdoc import process_single_md

    source = inspect.getsource(process_single_md)

    assert '_gdoc' in source, "Missing _gdoc flag check"
    assert 'is_gdoc=' in source, "Missing is_gdoc parameter pass"
    assert 'Google Doc export' in source, \
        "Missing Google Doc export message"

    print("✓ test_process_single_md_integration passed")
    return True

def run_all_tests():
    """Run all validation tests."""
    print("="*60)
    print("Google Docs Support Validation Tests")
    print("="*60)

    tests = [
        ("Equation Image Stripping", test_strip_equation_images),
        ("Scan Logic Structure", test_scan_logic_structure),
        ("Download Function Signature", test_download_signature),
        ("Process Integration", test_process_single_md_integration),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"\n[TEST] {name}...")
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"✗ {name} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name} ERROR: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)

    if failed == 0:
        print("\n✓ All tests passed! Implementation ready for integration testing.")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed. Review implementation.")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())
