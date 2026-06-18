"""PDF inspection and language helpers for the slide watcher."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SUPPORTED_LANGS = {'ko', 'en', 'fr', 'es', 'de', 'ja', 'zh'}
PDF_TEXT_PAGES = 3
MIN_SLIDE_ASPECT_RATIO = 1.25

TESSERACT_LANG_CODES: Dict[str, str] = {
    'ko': 'kor',
    'en': 'eng',
    'fr': 'fra',
    'es': 'spa',
    'de': 'deu',
    'ja': 'jpn',
    'zh': 'chi_sim',
}
_TESSERACT_AVAILABLE: Optional[bool] = None

LANG_HINTS: List[Tuple[str, str]] = [
    ('korean', 'ko'), ('한국어', 'ko'), ('한글', 'ko'),
    ('english', 'en'),
    ('français', 'fr'), ('francais', 'fr'), ('french', 'fr'),
    ('español', 'es'), ('espanol', 'es'), ('spanish', 'es'),
    ('deutsch', 'de'), ('german', 'de'),
    ('日本語', 'ja'), ('japanese', 'ja'),
    ('中文', 'zh'), ('简体', 'zh'), ('繁體', 'zh'), ('chinese', 'zh'),
]

FILENAME_LANG_HINTS: List[Tuple[str, str]] = [
    ('ko', 'ko'), ('kor', 'ko'), ('kr', 'ko'),
    ('en', 'en'), ('eng', 'en'),
    ('fr', 'fr'), ('fre', 'fr'), ('fra', 'fr'),
    ('es', 'es'), ('spa', 'es'),
    ('de', 'de'), ('ger', 'de'), ('deu', 'de'),
    ('ja', 'ja'), ('jp', 'ja'), ('jpn', 'ja'),
    ('zh', 'zh'), ('cn', 'zh'), ('chn', 'zh'),
]


def _extract_pdf_meta_and_text(pdf_path: str, max_pages: int = PDF_TEXT_PAGES) -> Tuple[Dict[str, str], str]:
    """Return (metadata, first-pages text). Best-effort; returns ({}, "") on failure."""
    try:
        import fitz  # pymupdf
    except Exception:
        return {}, ''
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return {}, ''
    meta = dict(doc.metadata or {})
    text_parts: List[str] = []
    try:
        for i in range(min(max_pages, doc.page_count)):
            try:
                text_parts.append(doc.load_page(i).get_text() or '')
            except Exception:
                continue
    finally:
        doc.close()
    return meta, '\n'.join(text_parts)


def _pdf_page_profile(pdf_path: str) -> Dict[str, float | int | bool]:
    """Return basic first-page dimensions used to reject legacy portrait reports."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(pdf_path)
    except Exception:
        return {'page_count': 0, 'width': 0.0, 'height': 0.0, 'aspect_ratio': 0.0, 'is_landscape_slide': False}
    try:
        if doc.page_count <= 0:
            return {'page_count': 0, 'width': 0.0, 'height': 0.0, 'aspect_ratio': 0.0, 'is_landscape_slide': False}
        rect = doc.load_page(0).rect
        width = float(rect.width)
        height = float(rect.height)
        aspect = width / height if height else 0.0
        return {
            'page_count': doc.page_count,
            'width': width,
            'height': height,
            'aspect_ratio': aspect,
            'is_landscape_slide': aspect >= MIN_SLIDE_ASPECT_RATIO,
        }
    finally:
        doc.close()


def _ocr_first_page_text(pdf_path: str, max_pages: int = PDF_TEXT_PAGES) -> str:
    """Render the first pages and OCR them with tesseract. Returns "" on failure."""
    try:
        import fitz  # pymupdf
        import pytesseract
        from PIL import Image
    except Exception as e:
        print(f"    [WARN] OCR deps unavailable: {e}")
        return ''
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is None:
        _TESSERACT_AVAILABLE = shutil.which('tesseract') is not None
        if not _TESSERACT_AVAILABLE:
            print("    [WARN] OCR binary unavailable: tesseract is not installed or not in PATH")
    if not _TESSERACT_AVAILABLE:
        return ''
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return ''

    pages_to_ocr = min(max_pages, doc.page_count)
    if pages_to_ocr <= 0:
        doc.close()
        return ''

    tess_langs = '+'.join(TESSERACT_LANG_CODES[c] for c in sorted(SUPPORTED_LANGS))
    text_parts: List[str] = []
    try:
        for i in range(pages_to_ocr):
            try:
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
                img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                text_parts.append(pytesseract.image_to_string(img, lang=tess_langs) or '')
            except Exception as e:
                print(f"    [WARN] OCR page {i} failed: {e}")
                continue
    finally:
        doc.close()
    return '\n'.join(text_parts)


def _lang_from_metadata(meta: Dict[str, str]) -> Optional[str]:
    haystack = ' '.join(
        (meta.get(k) or '') for k in ('title', 'Title', 'subject', 'Subject', 'keywords', 'Keywords')
    ).lower()
    if not haystack:
        return None
    for hint, code in LANG_HINTS:
        if hint in haystack:
            return code
    return None


def _lang_from_filename(pdf_name: str) -> Optional[str]:
    """Resolve explicit filename language tokens before content heuristics."""
    stem = Path(pdf_name).stem.lower()
    tokens = [t for t in re.split(r'[^a-z0-9]+', stem) if t]
    for token in reversed(tokens):
        normalized = re.sub(r'\d+$', '', token)
        for hint, code in FILENAME_LANG_HINTS:
            if normalized == hint:
                return code
    return None


def _cjk_script_counts(text: str) -> Dict[str, int]:
    """Count CJK script families in a bounded sample."""
    sample = (text or '')[:8000]
    return {
        'kana': sum(1 for ch in sample if '぀' <= ch <= 'ヿ'),
        'hangul': sum(1 for ch in sample if '가' <= ch <= '힯'),
        'han': sum(1 for ch in sample if '一' <= ch <= '鿿'),
    }


def _cjk_script_signature(text: str) -> Optional[str]:
    """High-confidence CJK script detection by Unicode block counts."""
    counts = _cjk_script_counts(text)
    hiragana_katakana = counts['kana']
    hangul = counts['hangul']
    han = counts['han']
    if hiragana_katakana >= 4:
        return 'ja'
    if hangul >= 4:
        return 'ko'
    if han >= 10 and hiragana_katakana == 0 and hangul == 0:
        return 'zh'
    return None


def _is_han_dominant_zh(counts: Dict[str, int]) -> bool:
    """Return true when Chinese Han text clearly outweighs OCR kana noise."""
    han = counts.get('han', 0)
    kana = counts.get('kana', 0)
    hangul = counts.get('hangul', 0)
    return hangul == 0 and han >= 20 and (kana == 0 or han >= kana * 4)


def _high_confidence_ocr_cjk_mismatch(
    resolved_lang: str,
    counts: Dict[str, int],
) -> Optional[str]:
    """Return a CJK mismatch from OCR when the signal is too strong to be noise.

    Filename language hints are trusted over ordinary OCR because raster slide OCR
    can hallucinate small CJK fragments. Full-slide wrong-language contamination,
    however, produces dozens of characters from another script. This helper keeps
    the noisy-fragment tolerance while still failing closed on obvious locale swaps.
    """
    hangul = counts.get('hangul', 0)
    kana = counts.get('kana', 0)
    han = counts.get('han', 0)

    if resolved_lang != 'ko':
        if hangul >= 18:
            return 'ko'
    if resolved_lang != 'ja':
        if kana >= 18 and hangul < 4:
            return 'ja'
    if resolved_lang != 'zh':
        if han >= 40 and hangul < 4 and kana < 4:
            return 'zh'
    return None


def _lang_from_text(text: str) -> Optional[str]:
    if not text or len(text.strip()) < 30:
        return _cjk_script_signature(text or '')
    cjk = _cjk_script_signature(text)
    if cjk:
        return cjk
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0
        code = detect(text[:4000])
    except Exception:
        return None
    code = code.split('-')[0].lower()
    return code if code in SUPPORTED_LANGS else None


def _resolve_lang(
    pdf_name: str,
    meta: Dict[str, str],
    text: str,
    ocr_text: str,
) -> Tuple[Optional[str], str]:
    code = _lang_from_filename(pdf_name)
    if code:
        return code, 'filename'
    code = _lang_from_metadata(meta)
    if code:
        return code, 'metadata'
    code = _lang_from_text(text)
    if code:
        return code, 'langdetect'
    code = _lang_from_text(ocr_text)
    if code:
        return code, 'ocr_langdetect'
    return None, 'none'


def _detect_language_content_mismatch(
    resolved_lang: Optional[str],
    pdf_text: str,
    ocr_text: str,
    lang_source: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Flag high-confidence CJK body text that contradicts resolved language."""
    if not resolved_lang:
        return None
    if resolved_lang not in {'ko', 'ja', 'zh'}:
        return None

    for source, text in (('text', pdf_text), ('ocr', ocr_text)):
        if source == 'ocr' and lang_source == 'filename':
            counts = _cjk_script_counts(text or '')
            detected = _high_confidence_ocr_cjk_mismatch(resolved_lang, counts)
            if detected:
                return {
                    'resolved_lang': resolved_lang,
                    'detected_lang': detected,
                    'source': source,
                    'reason': 'high_confidence_ocr_cjk_script',
                }
            continue
        counts = _cjk_script_counts(text or '')
        if resolved_lang == 'ja' and counts['hangul'] >= 4:
            return {
                'resolved_lang': resolved_lang,
                'detected_lang': 'ko',
                'source': source,
                'reason': 'mixed_cjk_script',
            }
        if resolved_lang == 'zh':
            if counts['hangul'] >= 4:
                return {
                    'resolved_lang': resolved_lang,
                    'detected_lang': 'ko',
                    'source': source,
                    'reason': 'mixed_cjk_script',
                }
            if counts['kana'] >= 4:
                if not _is_han_dominant_zh(counts):
                    return {
                        'resolved_lang': resolved_lang,
                        'detected_lang': 'ja',
                        'source': source,
                        'reason': 'mixed_cjk_script',
                    }
        if resolved_lang == 'ko' and counts['kana'] >= 4:
            return {
                'resolved_lang': resolved_lang,
                'detected_lang': 'ja',
                'source': source,
                'reason': 'mixed_cjk_script',
            }

        detected = _cjk_script_signature(text or '')
        if resolved_lang == 'zh' and detected == 'ja' and _is_han_dominant_zh(counts):
            continue
        if detected and detected != resolved_lang:
            return {
                'resolved_lang': resolved_lang,
                'detected_lang': detected,
                'source': source,
            }

    return None
