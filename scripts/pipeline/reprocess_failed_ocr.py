#!/usr/bin/env python3
"""
Reprocess [?] OCR failures using Gemini 2.0 Flash (fast, free tier).

Strategy:
  1. Process ONLY Korean files (source of truth)
  2. Batch all [?] in a file into ONE Gemini call
  3. Propagate results to all 6 translated language files

Usage:
  export GEMINI_API_KEY=key1
  export GEMINI_API_KEY_2=key2
  export GEMINI_API_KEY_3=key3
  python reprocess_failed_ocr.py
"""
import json, os, re, sys, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / 'output'
TRANS_LANGS = ['en', 'ja', 'zh', 'fr', 'es', 'de']


def get_api_keys():
    keys = []
    k1 = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_AI_API_KEY', '')
    if k1: keys.append(k1)
    for s in ['_2', '_3', '_4', '_5']:
        k = os.environ.get(f'GEMINI_API_KEY{s}', '')
        if k: keys.append(k)
    return keys


def gemini_call(api_keys, key_idx, prompt):
    """Make a Gemini call with key rotation on 429."""
    from google import genai
    from google.genai import types

    for attempt in range(len(api_keys) * 2):
        key = api_keys[key_idx[0] % len(api_keys)]
        try:
            client = genai.Client(api_key=key)
            r = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0, max_output_tokens=500),
            )
            return (r.text or '').strip()
        except Exception as e:
            if '429' in str(e) or 'RESOURCE_EXHAUSTED' in str(e):
                key_idx[0] += 1
                wait = 15
                print(f"    [429] → key{key_idx[0] % len(api_keys)}, wait {wait}s")
                time.sleep(wait)
            else:
                print(f"    [ERR] {type(e).__name__}: {str(e)[:100]}")
                return None
    return None


def process_korean_file(ko_path, api_keys, key_idx):
    """Process all [?] in a Korean file with a single batched Gemini call."""
    content = ko_path.read_text(encoding='utf-8')
    if '[?]' not in content:
        return {}, False

    # Collect all lines with [?] and their context
    lines = content.split('\n')
    q_lines = []
    for li, line in enumerate(lines):
        cnt = line.count('[?]')
        if cnt > 0:
            ctx_s = max(0, li - 2)
            ctx_e = min(len(lines), li + 3)
            ctx = '\n'.join(lines[ctx_s:ctx_e])
            q_lines.append({'line_idx': li, 'count': cnt, 'line': line, 'context': ctx})

    if not q_lines:
        return {}, False

    total_qs = sum(q['count'] for q in q_lines)

    # Build a single batched prompt
    sections = []
    for qi, q in enumerate(q_lines, 1):
        sections.append(
            f"## 위치 {qi} (줄 {q['line_idx']+1}, [?] {q['count']}개)\n"
            f"문맥:\n```\n{q['context']}\n```\n"
            f"대상 줄:\n```\n{q['line']}\n```"
        )

    prompt = (
        "블록체인/암호화폐 분석 보고서에서 OCR 실패로 [?]가 된 부분을 복원해주세요.\n\n"
        "규칙:\n"
        "- 수학 변수/기호: ρ, β, T_finality, N, f*\n"
        "- 토큰 심볼: ELSA, ENJ ($기호 없이)\n"
        "- 숫자: 0.026, 10⁻⁸\n"
        "- 수식: S = Σ(s_i)\n"
        "- 불확실하면 [?] 유지\n\n"
        + '\n\n'.join(sections) + '\n\n'
        "응답 형식 (정확히 따를 것):\n"
        "위치1-1: 값\n"
        "위치1-2: 값\n"
        "위치2-1: 값\n"
        "...\n"
        "예: 위치1-1: ρ\n위치1-2: T_finality\n위치2-1: 0.026"
    )

    answer = gemini_call(api_keys, key_idx, prompt)
    if not answer:
        return {}, False

    # Parse: "위치1-1: ρ" → {(0, 0): 'ρ'}
    replacements = {}
    for resp_line in answer.split('\n'):
        resp_line = resp_line.strip()
        m = re.match(r'위치\s*(\d+)\s*-\s*(\d+)\s*:\s*(.+)', resp_line)
        if m:
            pos_idx = int(m.group(1)) - 1  # 0-based
            q_idx = int(m.group(2)) - 1
            val = m.group(3).strip().strip('`').strip('"').strip("'")
            if val and val != '[?]':
                replacements[(pos_idx, q_idx)] = val

    if not replacements:
        return {}, False

    # Apply to Korean file
    changed = False
    result_map = {}  # line_idx → list of (q_idx, val)
    for (pos_idx, q_idx), val in replacements.items():
        if pos_idx < len(q_lines):
            li = q_lines[pos_idx]['line_idx']
            if li not in result_map:
                result_map[li] = []
            result_map[li].append((q_idx, val))

    for li, fixes in result_map.items():
        line = lines[li]
        # Replace nth [?] from last to first
        for q_idx, val in sorted(fixes, reverse=True):
            pos = -1
            for _ in range(q_idx + 1):
                pos = line.find('[?]', pos + 1)
                if pos == -1:
                    break
            if pos >= 0:
                line = line[:pos] + val + line[pos + 3:]
                changed = True
        lines[li] = line

    if changed:
        ko_path.write_text('\n'.join(lines), encoding='utf-8')

    # Build simple [?] → val mapping for propagation
    flat_map = {}
    for (pos_idx, q_idx), val in replacements.items():
        flat_map[f'p{pos_idx}q{q_idx}'] = val

    return replacements, changed


def propagate_to_translations(ko_name, replacements, q_lines_info):
    """Apply Korean [?] → text mapping to translated files by line matching."""
    if not replacements:
        return

    for lang in TRANS_LANGS:
        t_name = ko_name.replace('_ko.md', f'_{lang}.md')
        t_path = OUTPUT_DIR / t_name
        if not t_path.exists():
            continue

        content = t_path.read_text(encoding='utf-8')
        if '[?]' not in content:
            continue

        # Simple approach: replace [?] sequentially with the same order as Korean
        vals = []
        for pos_idx in sorted(set(p for p, _ in replacements)):
            for q_idx in sorted(q for p, q in replacements if p == pos_idx):
                vals.append(replacements[(pos_idx, q_idx)])

        result = content
        replaced = 0
        for val in vals:
            if '[?]' in result:
                result = result.replace('[?]', val, 1)
                replaced += 1

        if replaced > 0:
            t_path.write_text(result, encoding='utf-8')
            print(f"    {lang}: {replaced} replaced")


def main():
    api_keys = get_api_keys()
    if not api_keys:
        print("ERROR: Set GEMINI_API_KEY"); sys.exit(1)
    print(f"Using {len(api_keys)} API key(s)\n")

    # Find Korean files with [?]
    ko_files = sorted(OUTPUT_DIR.glob('*_ko.md'))
    affected = [(f, f.read_text().count('[?]')) for f in ko_files if '[?]' in f.read_text()]

    total_qs = sum(c for _, c in affected)
    print(f"Found {total_qs} [?] across {len(affected)} Korean files\n")

    key_idx = [0]
    total_resolved = 0

    for i, (ko_path, q_count) in enumerate(affected, 1):
        name = ko_path.name
        print(f"[{i}/{len(affected)}] {name} ({q_count} [?])")

        replacements, changed = process_korean_file(ko_path, api_keys, key_idx)
        resolved = len(replacements)
        total_resolved += resolved

        if replacements:
            for (pos, qi), val in sorted(replacements.items()):
                print(f"    위치{pos+1}-{qi+1}: {val}")

            # Propagate
            propagate_to_translations(name, replacements, None)

        # Rate limit between files
        key_idx[0] += 1
        time.sleep(5)
        print()

    # Final count
    remaining = sum(1 for f in ko_files for _ in re.finditer(r'\[\?\]', f.read_text()))
    print(f"{'='*50}")
    print(f"DONE: {total_resolved} resolved, {remaining} [?] remaining")


if __name__ == '__main__':
    main()
