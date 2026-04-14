#!/usr/bin/env python3
"""Batch 3: remaining translations + PDF gen."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translate_md import translate_md_file
from gen_pdf_for import generate_pdf_for

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

todo = [
    {'ko_md': 'stable-포렌식-분석-보고서_for_v1_ko.md',
     'slug_prefix': 'stable-포렌식-분석-보고서_for_v1', 'out_slug': 'stable',
     'project_name': 'Stable', 'symbol': 'STABLE', 'risk_level': 'high',
     'need_translate': ['zh','fr','es','de'],
     'need_pdf': ['ja','zh','fr','es','de']},
    {'ko_md': 'skyai-포렌식-분석-보고서_for_v1_ko.md',
     'slug_prefix': 'skyai-포렌식-분석-보고서_for_v1', 'out_slug': 'skyai',
     'project_name': 'SKYAI', 'symbol': 'SKYAI', 'risk_level': 'high',
     'need_translate': ['ja','zh','fr','es','de'],
     'need_pdf': ['ja','zh','fr','es','de']},
    {'ko_md': 'xpl-포렌식-분석-보고서_for_v1_ko.md',
     'slug_prefix': 'xpl-포렌식-분석-보고서_for_v1', 'out_slug': 'plasma-xpl',
     'project_name': 'Plasma', 'symbol': 'XPL', 'risk_level': 'elevated',
     'need_translate': ['zh','fr','es','de'],
     'need_pdf': ['zh','fr','es','de']},
    {'ko_md': 'midnight-시장-무결성-보고서_for_v1_ko.md',
     'slug_prefix': 'midnight-시장-무결성-보고서_for_v1', 'out_slug': 'midnight-network',
     'project_name': 'Midnight', 'symbol': 'NIGHT', 'risk_level': 'elevated',
     'need_translate': ['en','ja','zh','fr','es','de'],
     'need_pdf': ['en','ja','zh','fr','es','de']},
]

for info in todo:
    print(f"\n{'='*50}", flush=True)
    print(f"  {info['project_name']} ({info['symbol']})", flush=True)
    print(f"{'='*50}", flush=True)
    ko_path = os.path.join(OUTPUT_DIR, info['ko_md'])

    for lang in info['need_translate']:
        md_out = os.path.join(OUTPUT_DIR, f"{info['slug_prefix']}_{lang}.md")
        if os.path.exists(md_out) and os.path.getsize(md_out) > 500:
            print(f"  [{lang}] skip (exists)", flush=True)
            continue
        print(f"  [{lang}] translating...", flush=True)
        try:
            out_path, meta = translate_md_file(ko_path, target_lang=lang, output_dir=OUTPUT_DIR, backend='google')
            print(f"  [{lang}] ✓ {meta.get('word_count_target','?')} words", flush=True)
            time.sleep(0.3)
        except Exception as e:
            print(f"  [{lang}] ✗ {e}", flush=True)

    meta = {'project_name': info['project_name'], 'token_symbol': info['symbol'],
            'slug': info['out_slug'], 'version': 1, 'risk_level': info['risk_level'],
            'trigger_reason': 'Market analysis alert', 'charts_data': {}}
    for lang in info['need_pdf']:
        md = os.path.join(OUTPUT_DIR, f"{info['slug_prefix']}_{lang}.md")
        pdf = os.path.join(OUTPUT_DIR, f"{info['out_slug']}_for_v1_{lang}.pdf")
        if not os.path.exists(md):
            print(f"  PDF [{lang}] SKIP", flush=True)
            continue
        try:
            generate_pdf_for(md, meta, lang=lang, output_path=pdf)
        except Exception as e:
            print(f"  PDF [{lang}] ✗ {e}", flush=True)

print("\n✓ ALL DONE!", flush=True)
