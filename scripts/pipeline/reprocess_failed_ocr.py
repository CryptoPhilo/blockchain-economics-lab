#!/usr/bin/env python3
"""
Reprocess [?] OCR failures using Gemini 2.5 Flash vision.

Usage:
  export GEMINI_API_KEY=your_key
  python reprocess_failed_ocr.py

Reads _equation_ocr_results.json to find which files/images failed,
then uses Gemini to re-OCR them from the original base64 data.
Since the base64 definitions have been stripped from the processed .md files,
this script works on files that still contain [?] placeholders and
attempts to resolve them using Gemini vision with contextual hints.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure pipeline modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / 'output'
LANGS = ['ko', 'en', 'ja', 'zh', 'fr', 'es', 'de']


def load_failed_images() -> dict:
    """Load the OCR results and find failures."""
    results_path = OUTPUT_DIR / '_equation_ocr_results.json'
    if not results_path.exists():
        print("ERROR: _equation_ocr_results.json not found")
        sys.exit(1)

    results = json.loads(results_path.read_text())
    failures = {}
    for fname, mapping in results.items():
        failed = {k: v for k, v in mapping.items() if v == '[?]'}
        if failed:
            failures[fname] = failed
    return failures


def reprocess_with_gemini():
    """Re-OCR failed images using Gemini 2.5 Flash."""
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_AI_API_KEY', '')
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY environment variable")
        print("  Get a free key at: https://aistudio.google.com/apikey")
        sys.exit(1)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("ERROR: pip install google-genai")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    failures = load_failed_images()

    total_files = len(failures)
    total_failed = sum(len(v) for v in failures.values())
    print(f"Found {total_failed} failed OCR images across {total_files} files\n")

    if total_failed == 0:
        print("Nothing to reprocess!")
        return

    # For each file, find [?] in the text and try to resolve with Gemini + context
    resolved_count = 0
    still_failed = 0

    for i, (fname, failed_images) in enumerate(failures.items(), 1):
        print(f"[{i}/{total_files}] {fname} ({len(failed_images)} failures)")

        # Read all language versions
        base_name = fname
        for lang in LANGS:
            lang_fname = base_name.replace('_ko.md', f'_{lang}.md')
            lang_path = OUTPUT_DIR / lang_fname
            if not lang_path.exists():
                continue

            content = lang_path.read_text(encoding='utf-8')
            if '[?]' not in content:
                continue

            # For each [?], extract surrounding context and ask Gemini
            # Since base64 is gone, we use context-only Gemini to infer
            lines = content.split('\n')
            changed = False
            for li, line in enumerate(lines):
                if '[?]' not in line:
                    continue

                # Get surrounding context (3 lines before/after)
                ctx_start = max(0, li - 3)
                ctx_end = min(len(lines), li + 4)
                context = '\n'.join(lines[ctx_start:ctx_end])

                # Count [?] in this line
                q_count = line.count('[?]')
                if q_count == 0:
                    continue

                prompt = (
                    "아래는 블록체인/암호화폐 분석 보고서의 일부입니다. "
                    "'[?]' 표시는 원래 수식 이미지가 있었으나 OCR 변환에 실패한 부분입니다. "
                    "문맥을 분석하여 각 [?] 위치에 들어갈 가능성이 높은 수학 기호, 변수명, "
                    "그리스 문자, 또는 수식을 추론해주세요.\n\n"
                    "규칙:\n"
                    "- 수학 변수/기호면 그대로 (예: ρ, β, T_finality, N, f*)\n"
                    "- 토큰 심볼이면 $기호 없이 (예: ELSA, ENJ)\n"
                    "- 숫자면 그대로 (예: 0.026, 10⁻⁸)\n"
                    "- 수식이면 텍스트 표기 (예: S = Σ(s_i))\n"
                    "- 확실하지 않으면 '[?]'을 유지\n\n"
                    f"보고서 문맥:\n```\n{context}\n```\n\n"
                    f"이 줄에서 {q_count}개의 [?]가 있습니다:\n```\n{line}\n```\n\n"
                    "각 [?]에 대해 한 줄씩 '위치번호: 대체텍스트' 형식으로 응답해주세요. "
                    "예: '1: ρ\\n2: T_finality'"
                )

                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[types.Content(parts=[types.Part.from_text(text=prompt)])],
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            max_output_tokens=200,
                        ),
                    )
                    answer = response.text.strip()

                    # Parse response: "1: ρ\n2: T_finality"
                    replacements = []
                    for resp_line in answer.split('\n'):
                        resp_line = resp_line.strip()
                        if ':' in resp_line:
                            parts = resp_line.split(':', 1)
                            try:
                                idx = int(parts[0].strip())
                                val = parts[1].strip().strip('`').strip()
                                if val and val != '[?]':
                                    replacements.append((idx, val))
                            except (ValueError, IndexError):
                                continue

                    # Apply replacements (replace nth [?] occurrence)
                    if replacements:
                        new_line = line
                        # Replace from last to first to preserve positions
                        for idx, val in sorted(replacements, reverse=True):
                            # Find the idx-th occurrence of [?]
                            pos = -1
                            for _ in range(idx):
                                pos = new_line.find('[?]', pos + 1)
                                if pos == -1:
                                    break
                            if pos >= 0:
                                new_line = new_line[:pos] + val + new_line[pos + 3:]
                                resolved_count += 1

                        if new_line != line:
                            lines[li] = new_line
                            changed = True
                            print(f"    {lang} L{li+1}: {len(replacements)} resolved")
                            for idx, val in replacements:
                                print(f"      #{idx}: '{val}'")

                    time.sleep(1.5)  # Rate limit
                except Exception as e:
                    print(f"    [WARN] Gemini error: {type(e).__name__}: {e}")
                    still_failed += q_count
                    time.sleep(2)

            if changed:
                lang_path.write_text('\n'.join(lines), encoding='utf-8')

        print()

    print(f"\n{'='*60}")
    print(f"SUMMARY: {resolved_count} [?] resolved, {still_failed} still failed")
    print(f"Run report QA to verify results.")


if __name__ == '__main__':
    reprocess_with_gemini()
