#!/usr/bin/env python3
"""
Batch re-translate reports using paragraph-chunked Google Translate.
Per translate skill: 단락 단위로 2000자 청크를 모아서 한 번에 번역.
라인별 번역 대신 단락 단위 번역으로 API 호출 횟수를 10배 이상 줄인다.

Usage:
  python batch_retranslate_all.py              # Phase 1 only (missing)
  python batch_retranslate_all.py --all        # Phase 1 + 2 (full re-translate)
  python batch_retranslate_all.py --start N    # Resume from report N
"""
import os, sys, time, re, signal, argparse
from pathlib import Path
from deep_translator import GoogleTranslator

SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = SCRIPT_DIR / 'output'
ALL_LANGS = ['en', 'ko', 'ja', 'zh', 'fr', 'es', 'de']
CHUNK_SIZE = 2000  # per translate skill: 최대 2000자

GOOGLE_LANG_MAP = {
    'en': 'en', 'ja': 'ja', 'zh': 'zh-CN',
    'fr': 'fr', 'es': 'es', 'de': 'de', 'ko': 'ko',
}

MUST_PRESERVE = [
    'ELSA', 'USDC', 'BTC', 'ETH', 'SOL', 'ENJ', 'LEO', 'MYX',
    'AVAX', 'MATIC', 'LINK', 'UNI', 'AAVE', 'DOT', 'ADA', 'XRP',
]

# Token symbols to protect during translation
_PRESERVE_TOKENS = [
    'ELSA', 'USDC', 'USDT', 'BTC', 'ETH', 'SOL', 'ENJ', 'LEO', 'MYX',
    'AVAX', 'MATIC', 'LINK', 'UNI', 'AAVE', 'DOT', 'ADA', 'XRP', 'DOGE',
    'SHIB', 'PEPE', 'ARB', 'OP', 'LDO', 'RPL', 'FTM', 'NEAR', 'ATOM',
    'DeFi', 'NFT', 'DEX', 'CEX', 'TVL', 'APY', 'APR', 'AMM',
    'RSI', 'MACD', 'EMA', 'SMA', 'VWAP',
]


def _protect_tokens(text):
    """Replace token symbols with placeholders before translation."""
    mapping = {}
    protected = text
    idx = 0
    for token in _PRESERVE_TOKENS:
        # Match whole word only
        pattern = r'\b' + re.escape(token) + r'\b'
        if re.search(pattern, protected):
            placeholder = f'⟦TK{idx}⟧'
            protected = re.sub(pattern, placeholder, protected)
            mapping[placeholder] = token
            idx += 1
    return protected, mapping


def _restore_tokens(text, mapping):
    """Restore token symbols from placeholders after translation."""
    restored = text
    for placeholder, token in mapping.items():
        if placeholder in restored:
            restored = restored.replace(placeholder, token)
        else:
            # Fuzzy: Google sometimes adds spaces around brackets
            esc = re.escape(placeholder).replace('⟦', '[⟦\\[]').replace('⟧', '[⟧\\]]')
            restored = re.sub(r'\s*' + esc + r'\s*', token, restored)
    return restored


def _timeout_handler(signum, frame):
    raise TimeoutError("Google Translate timed out")


def translate_chunk(text, target_lang, max_retries=3):
    """Translate a single chunk with retry + timeout."""
    if not text or not text.strip():
        return text
    stripped = text.strip()
    if len(stripped) <= 3:
        return text
    # Skip base64 images
    if stripped.startswith('[image') and 'data:image' in stripped:
        return text
    # Skip too long (Google limit ~5000)
    if len(stripped) > 4500:
        return text

    protected, token_map = _protect_tokens(stripped)
    gl = GOOGLE_LANG_MAP.get(target_lang, target_lang)

    for attempt in range(max_retries):
        try:
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(20)  # 20s timeout per chunk
            try:
                result = GoogleTranslator(source='auto', target=gl).translate(protected)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            time.sleep(0.3)  # throttle
            if result:
                return _restore_tokens(result, token_map)
            return text
        except (TimeoutError, Exception) as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 3
                time.sleep(wait)
            else:
                return text  # 최종 실패 시 원본 유지
    return text


def translate_md_chunked(md_text, target_lang):
    """
    단락 단위 청크 번역 (translate skill 패턴).
    단락(\n\n)으로 분할 → 2000자 버퍼에 모아서 번역 → 재조립.
    API 호출을 최소화한다.
    """
    paragraphs = md_text.split('\n\n')
    translated_parts = []
    buffer = ''
    fail_count = 0

    def flush_buffer(buf):
        nonlocal fail_count
        if not buf.strip():
            return
        # Split if buffer exceeds chunk size
        pieces = _split_long_text(buf.strip(), CHUNK_SIZE)
        for piece in pieces:
            try:
                translated_parts.append(translate_chunk(piece, target_lang))
            except Exception:
                translated_parts.append(piece)
                fail_count += 1
            time.sleep(0.3)

    for para in paragraphs:
        if not para.strip():
            translated_parts.append('')
            continue

        # Skip code blocks entirely
        if para.strip().startswith('```'):
            if buffer:
                flush_buffer(buffer)
                buffer = ''
            translated_parts.append(para)
            continue

        if len(buffer) + len(para) + 2 > CHUNK_SIZE:
            if buffer:
                flush_buffer(buffer)
            buffer = para + '\n\n'
        else:
            buffer += para + '\n\n'

    if buffer.strip():
        flush_buffer(buffer)

    return '\n\n'.join(translated_parts), fail_count


def _split_long_text(text, max_len):
    """Split text exceeding max_len: newlines → sentences → forced cut."""
    if len(text) <= max_len:
        return [text]
    lines = text.split('\n')
    if len(lines) > 1:
        chunks, buf = [], ''
        for line in lines:
            if len(buf) + len(line) + 1 > max_len:
                if buf:
                    chunks.append(buf)
                if len(line) > max_len:
                    chunks.extend(_split_by_sentence(line, max_len))
                else:
                    buf = line
                continue
            buf = buf + '\n' + line if buf else line
        if buf:
            chunks.append(buf)
        return chunks
    return _split_by_sentence(text, max_len)


def _split_by_sentence(text, max_len):
    """Split by sentence boundaries. Forced cut as last resort."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, buf = [], ''
    for sent in sentences:
        if len(buf) + len(sent) + 1 > max_len:
            if buf:
                chunks.append(buf)
            if len(sent) > max_len:
                for i in range(0, len(sent), max_len):
                    chunks.append(sent[i:i + max_len])
                buf = ''
            else:
                buf = sent
        else:
            buf = buf + ' ' + sent if buf else sent
    if buf:
        chunks.append(buf)
    return chunks


def find_source(prefix):
    ko = OUTPUT_DIR / f"{prefix}_ko.md"
    en = OUTPUT_DIR / f"{prefix}_en.md"
    if ko.exists():
        return ko, 'ko'
    if en.exists():
        return en, 'en'
    return None, None


def validate(prefix, src_lang):
    src_path = OUTPUT_DIR / f"{prefix}_{src_lang}.md"
    src_text = src_path.read_text(encoding='utf-8') if src_path.exists() else ''
    src_tokens = [t for t in MUST_PRESERVE if t in src_text]
    ok = True
    langs_info = []
    for lang in ALL_LANGS:
        if lang == src_lang:
            continue
        fp = OUTPUT_DIR / f"{prefix}_{lang}.md"
        if not fp.exists() or fp.stat().st_size < 500:
            langs_info.append(f'✗{lang}')
            ok = False
            continue
        c = fp.read_text(encoding='utf-8')
        q = c.count('[?]')
        lost = [t for t in src_tokens if t not in c]
        sym = '✓'
        extra = ''
        if q > 0:
            extra += f'[?]×{q}'
            ok = False
            sym = '⚠'
        if lost:
            extra += f'↓{",".join(lost[:2])}'
            sym = '⚠'
        langs_info.append(f'{sym}{lang}{extra}')
    return ok, ' '.join(langs_info)


def translate_report(prefix, num, total, only_missing=True):
    src_path, src_lang = find_source(prefix)
    if not src_path:
        print(f"[{num}/{total}] SKIP {prefix}: no source", flush=True)
        return 0, 0

    targets = []
    for l in ALL_LANGS:
        if l == src_lang:
            continue
        fp = OUTPUT_DIR / f"{prefix}_{l}.md"
        if only_missing and fp.exists() and fp.stat().st_size > 500:
            continue
        targets.append(l)

    if not targets:
        return 0, 0

    src_text = src_path.read_text(encoding='utf-8')
    print(f"[{num}/{total}] {prefix} ({src_lang}→{','.join(targets)}) {len(src_text)} chars",
          flush=True)

    ok_count, fail_count = 0, 0
    for lang in targets:
        t0 = time.time()
        try:
            translated, fc = translate_md_chunked(src_text, lang)
            out_path = OUTPUT_DIR / f"{prefix}_{lang}.md"
            out_path.write_text(translated, encoding='utf-8')
            elapsed = time.time() - t0
            wc = len(translated.split())
            print(f"  ✓ [{lang}] {wc} words, {elapsed:.1f}s"
                  + (f" ({fc} chunks failed)" if fc else ""), flush=True)
            ok_count += 1
            time.sleep(1)  # cooldown between languages
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ✗ [{lang}] {str(e)[:100]} ({elapsed:.1f}s)", flush=True)
            fail_count += 1
            time.sleep(2)

    # Per-report validation
    passed, detail = validate(prefix, src_lang)
    print(f"  검증: {'PASS ✓' if passed else 'WARN ⚠'} | {detail}", flush=True)
    return ok_count, fail_count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', help='Phase 1+2 (re-translate all)')
    parser.add_argument('--start', type=int, default=1, help='Resume from report N')
    args = parser.parse_args()

    all_ko = sorted(OUTPUT_DIR.glob('*_ko.md'))
    prefixes = [f.name.replace('_ko.md', '') for f in all_ko]
    total = len(prefixes)

    # Phase 1: Missing translations
    print(f"{'=' * 60}")
    print(f"PHASE 1: 미번역 파일 채우기 ({total}개 보고서 스캔)")
    print(f"{'=' * 60}\n")

    total_ok, total_fail = 0, 0
    for i, prefix in enumerate(prefixes, 1):
        if i < args.start:
            continue
        ok, fail = translate_report(prefix, i, total, only_missing=True)
        total_ok += ok
        total_fail += fail

    print(f"\nPhase 1 완료: {total_ok} 번역 성공, {total_fail} 실패\n")

    # Phase 2: Re-translate all (if --all)
    if args.all:
        print(f"{'=' * 60}")
        print(f"PHASE 2: 전체 재번역 ({total}개 보고서)")
        print(f"{'=' * 60}\n")
        for i, prefix in enumerate(prefixes, 1):
            if i < args.start:
                continue
            ok, fail = translate_report(prefix, i, total, only_missing=False)
            total_ok += ok
            total_fail += fail

    # Final summary
    print(f"\n{'=' * 60}")
    print(f"전체 완료: {total_ok} 번역, {total_fail} 실패")
    for lang in ALL_LANGS:
        count = len(list(OUTPUT_DIR.glob(f'*_{lang}.md')))
        print(f"  {lang}: {count} files")

    q_total = sum(f.read_text(encoding='utf-8').count('[?]') for f in OUTPUT_DIR.glob('*.md'))
    print(f"  [?] 잔여: {q_total}")


if __name__ == '__main__':
    main()
