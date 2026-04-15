#!/usr/bin/env python3
"""
BCE Lab Report Pipeline Orchestrator — 4-Stage Architecture

Stage 0: Data Collection (APIs → Supabase warehouse + local enriched JSON)
Stage 1: JSON project data → Markdown text analysis + metadata JSON
Stage 2: Markdown + metadata → Branded graphical PDF
Stage 3: Upload → Google Drive + register URLs in Supabase

Usage:
    python orchestrator.py --type econ|mat|for --project <slug> --version <N> --lang <lang|all> [--data <json>] [--skip-collect] [--skip-upload]

    python orchestrator.py --type econ --project uniswap --version 1 --lang en
    python orchestrator.py --type mat --project heyelsaai --version 1 --lang all
    python orchestrator.py --type for --project heyelsaai --version 1 --lang en --data data/elsa_forensic.json
    python orchestrator.py --type econ --project uniswap --version 1 --lang en --skip-collect --skip-upload
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Import configuration
try:
    from config import LANGUAGES, report_filename, OUTPUT_DIR
except ImportError as e:
    print(f"Error: Failed to import config: {e}")
    sys.exit(1)

# Stage 0: Data Collection
try:
    from collectors.collect_all import collect_all_data
    from collectors.warehouse import get_warehouse
    HAS_COLLECTORS = True
except ImportError:
    HAS_COLLECTORS = False

# Stage 1: Text generators
from gen_text_econ import generate_text_econ
from gen_text_mat import generate_text_mat
from gen_text_for import generate_text_for

# Stage 2: PDF generators
from gen_pdf_econ import generate_pdf_econ
from gen_pdf_mat import generate_pdf_mat
from gen_pdf_for import generate_pdf_for

# Stage 1.5: Translation
try:
    from translate_md import translate_md_file, translate_md_all_languages
    HAS_TRANSLATE_MD = True
except ImportError:
    HAS_TRANSLATE_MD = False

# Stage 3: Google Drive upload
try:
    from gdrive_storage import get_gdrive
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False


# ─── Dispatchers ───────────────────────────────────────────────

STAGE1_GENERATORS = {
    'econ': generate_text_econ,
    'mat': generate_text_mat,
    'for': generate_text_for,
}

STAGE2_GENERATORS = {
    'econ': generate_pdf_econ,
    'mat': generate_pdf_mat,
    'for': generate_pdf_for,
}


def load_project_data(json_path: str) -> Dict[str, Any]:
    """Load project data from JSON file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Data file not found: {json_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {json_path}: {e}")
        sys.exit(1)


def run_stage0(
    project_data: Dict[str, Any],
    skip: bool = False,
) -> Dict[str, Any]:
    """
    Stage 0: Collect real-time data from APIs and persist to warehouse.
    Merges collected data into project_data.
    """
    if skip or not HAS_COLLECTORS:
        if not HAS_COLLECTORS:
            print("  [Stage 0] Collectors not available. Skipping.")
        else:
            print("  [Stage 0] Skipped by user request.")
        return project_data

    print(f"\n{'='*60}")
    print(f"  STAGE 0: Data Collection")
    print(f"{'='*60}")

    try:
        collected = collect_all_data(project_data, skip_whale=True, persist=True)
        # Merge collected data into project_data
        project_data['_collected'] = collected
        project_data['_data_sources'] = collected.get('data_sources_available', [])

        # Inject key market data into top-level for Stage 1 access
        if 'market_data' in collected:
            project_data['live_market'] = collected['market_data']
        if 'macro_global' in collected:
            project_data['live_macro'] = collected['macro_global']
        if 'fear_greed' in collected:
            project_data['live_fear_greed'] = collected['fear_greed']
        if 'defi_tvl' in collected:
            project_data['live_tvl'] = collected['defi_tvl']
        if 'github_data' in collected:
            project_data['live_github'] = collected['github_data']
        if 'price_history_90d' in collected:
            project_data['live_price_history'] = collected['price_history_90d']

        sources = project_data.get('_data_sources', [])
        print(f"  ✓ Data collected from {len(sources)} sources: {', '.join(sources)}")

    except Exception as e:
        print(f"  ✗ Stage 0 error (non-fatal): {e}")
        import traceback
        traceback.print_exc()

    return project_data


def run_stage1(
    report_type: str,
    project_data: Dict[str, Any],
    output_dir: str,
) -> Tuple[str, Dict[str, Any]]:
    """Stage 1: Generate text analysis (Markdown + metadata)."""
    print(f"\n{'='*60}")
    print(f"  STAGE 1: Text Analysis ({report_type.upper()})")
    print(f"{'='*60}")

    stage1_gen = STAGE1_GENERATORS[report_type]
    md_path, metadata = stage1_gen(project_data, output_dir=output_dir)

    print(f"  ✓ Markdown: {md_path}")
    return md_path, metadata


def run_stage2(
    report_type: str,
    project_slug: str,
    version: int,
    languages: List[str],
    md_path: str,
    metadata: Dict[str, Any],
    output_dir: str,
    translated_paths: Dict[str, str] = None,
) -> List[str]:
    """
    Stage 2: Generate branded PDFs from markdown.

    Args:
        translated_paths: Dict of {lang: translated_md_path} from Stage 1.5.
                          If provided, each language uses its translated .md file.
                          If None, all languages use the EN master md_path.
    """
    print(f"\n{'='*60}")
    print(f"  STAGE 2: PDF Generation ({report_type.upper()})")
    print(f"{'='*60}")

    stage2_gen = STAGE2_GENERATORS[report_type]
    pdf_paths = []

    for lang in languages:
        try:
            # Use translated markdown for this language, fallback to EN master
            lang_md = md_path
            if translated_paths and lang in translated_paths:
                lang_md = translated_paths[lang]
                if lang_md != md_path:
                    print(f"  Generating PDF for {project_slug} (v{version}, {lang}) from translated .md")
                else:
                    print(f"  Generating PDF for {project_slug} (v{version}, {lang})")
            else:
                print(f"  Generating PDF for {project_slug} (v{version}, {lang})")

            out_pdf = os.path.join(output_dir, report_filename(project_slug, report_type, version, lang))
            pdf_path = stage2_gen(
                md_path=lang_md,
                metadata=metadata,
                lang=lang,
                output_path=out_pdf,
            )
            pdf_paths.append(pdf_path)
            print(f"  ✓ PDF: {pdf_path}")
        except Exception as e:
            print(f"  ✗ Error generating {lang} PDF: {e}")
            import traceback
            traceback.print_exc()

    return pdf_paths


def run_stage3(
    report_type: str,
    project_slug: str,
    version: int,
    languages: List[str],
    md_path: str,
    pdf_paths: List[str],
    skip: bool = False,
) -> Dict[str, Dict[str, str]]:
    """
    Stage 3: Upload to Google Drive and register URLs in Supabase.
    Returns dict of lang -> upload_result.
    """
    if skip:
        print("\n  [Stage 3] Upload skipped by user request.")
        return {}

    if not HAS_GDRIVE:
        print("\n  [Stage 3] gdrive_storage not available. Skipping upload.")
        return {}

    gd = get_gdrive()
    if not gd.connected:
        print("\n  [Stage 3] Google Drive not connected. Skipping upload.")
        print("           Set GDRIVE_SERVICE_ACCOUNT_FILE and GDRIVE_ROOT_FOLDER_ID")
        return {}

    print(f"\n{'='*60}")
    print(f"  STAGE 3: Upload & Publish ({report_type.upper()})")
    print(f"{'='*60}")

    upload_results: Dict[str, Dict[str, str]] = {}

    # Upload PDFs
    for pdf_path in pdf_paths:
        # Extract lang from filename: {slug}_{type}_v{ver}_{lang}.pdf
        fname = Path(pdf_path).stem
        parts = fname.split('_')
        lang = parts[-1] if parts else 'en'

        result = gd.upload_report(
            local_path=pdf_path,
            project_slug=project_slug,
            report_type=report_type,
            version=version,
            lang=lang,
        )

        if result:
            upload_results[lang] = result
            print(f"  ✓ Uploaded {lang}: {result['url']}")

            # Register in Supabase
            _register_gdrive_url(
                project_slug=project_slug,
                report_type=report_type,
                version=version,
                lang=lang,
                gdrive_result=result,
            )
        else:
            print(f"  ✗ Upload failed for {lang}")

    # Upload source markdown (internal, not public)
    if md_path and os.path.exists(md_path):
        md_result = gd.upload_source_markdown(
            local_path=md_path,
            project_slug=project_slug,
            report_type=report_type,
            version=version,
            lang='en',
        )
        if md_result:
            print(f"  ✓ Source MD archived: {md_result['url']}")

    return upload_results


def _persist_maturity_score(
    project_slug: str,
    metadata: Dict[str, Any],
    md_path: str,
) -> None:
    """
    Stage 4: Persist maturity score to tracked_projects after MAT report generation.
    Includes QA validation to prevent bad data from entering the database.
    """
    if not HAS_COLLECTORS:
        print("\n  [Stage 4] Supabase not available — score not persisted")
        return

    print(f"\n{'='*60}")
    print(f"  STAGE 4: Maturity Score Persistence + QA")
    print(f"{'='*60}")

    # ── Extract score from metadata ──
    score = metadata.get('total_maturity_score')
    stage = metadata.get('maturity_stage')
    axes_raw = metadata.get('strategic_objectives') or metadata.get('axes') or []

    # ── Fallback: extract from markdown text ──
    if not score and md_path and os.path.exists(md_path):
        import re as _re
        text = Path(md_path).read_text(encoding='utf-8')
        for pat in [
            r'합계 달성률.*?(\d+\.?\d+)%',
            r'종합 진행률.*?(\d+\.?\d+)%',
            r'최종 합계.*?(\d+\.?\d+)%',
            r'\*\*(\d+\.?\d+)%\*\*로\s*(?:평가|산출)',
        ]:
            m = _re.search(pat, text)
            if m:
                candidate = float(m.group(1))
                if 0 < candidate < 100:  # Skip 100% weight matches
                    score = candidate
                    break

    if not score:
        print("  [SKIP] No maturity score found in metadata or markdown")
        return

    # ── QA Validation ──
    qa_errors = []
    qa_warnings = []

    # QA-1: Score range check
    if not (0 <= score <= 100):
        qa_errors.append(f"Score {score} out of valid range [0, 100]")

    # QA-2: Stage consistency check
    if stage:
        expected_stages = {
            (0, 25): 'nascent',
            (25, 50): 'growing',
            (50, 75): 'mature',
            (75, 100.01): 'established',
        }
        expected = None
        for (lo, hi), s in expected_stages.items():
            if lo <= score < hi:
                expected = s
                break
        # Allow flexible stage names (growth ≈ growing, bootstrap ≈ nascent, etc.)
        stage_aliases = {
            'growth': 'growing', 'bootstrap': 'nascent',
            'maturity': 'mature', 'mature': 'mature',
        }
        normalized = stage_aliases.get(stage.lower(), stage.lower())
        if expected and normalized != expected:
            qa_warnings.append(
                f"Stage '{stage}' may not match score {score} "
                f"(expected '{expected}', got '{normalized}')"
            )
    else:
        # Auto-assign stage from score
        if score < 25:
            stage = 'nascent'
        elif score < 50:
            stage = 'growing'
        elif score < 75:
            stage = 'mature'
        else:
            stage = 'established'

    # QA-3: Axes data validation
    valid_axes = []
    if axes_raw:
        for ax in axes_raw:
            name = ax.get('name', '')
            weight = ax.get('weight', 0)
            achievement = ax.get('achievement', 0)

            if not name:
                qa_warnings.append(f"Axis with empty name skipped")
                continue
            if not (0 <= weight <= 100):
                qa_warnings.append(f"Axis '{name}' weight {weight} invalid — clamped")
                weight = max(0, min(100, weight))
            if not (0 <= achievement <= 100):
                qa_warnings.append(f"Axis '{name}' achievement {achievement} invalid — clamped")
                achievement = max(0, min(100, achievement))

            valid_axes.append({
                'name': name,
                'weight': round(weight, 1),
                'achievement': round(achievement, 1),
            })

    # QA-4: Cross-check — recalculate total from axes and compare
    if valid_axes:
        total_weight = sum(a['weight'] for a in valid_axes)
        if total_weight > 0:
            recalc = sum(a['weight'] * a['achievement'] / total_weight for a in valid_axes)
            recalc = round(recalc, 2)
            diff = abs(recalc - score)
            if diff > 5.0:
                qa_warnings.append(
                    f"Recalculated score ({recalc}) differs from reported ({score}) by {diff:.1f}pts"
                )
            elif diff > 0.5:
                qa_warnings.append(
                    f"Minor score discrepancy: recalc={recalc} vs reported={score} (diff={diff:.2f})"
                )

    # ── QA Report ──
    if qa_errors:
        for e in qa_errors:
            print(f"  ✗ QA ERROR: {e}")
        print("  [ABORT] Score NOT written to DB due to QA errors")
        return

    for w in qa_warnings:
        print(f"  ⚠ QA WARN: {w}")

    print(f"  ✓ QA passed — score={score}, stage={stage}, axes={len(valid_axes)}")

    # ── Write to DB ──
    try:
        wh = get_warehouse()
        if not wh.connected:
            print("  [SKIP] Warehouse not connected")
            return

        import json as _json
        update_data = {
            'maturity_score': score,
            'maturity_stage': stage,
        }
        if valid_axes:
            update_data['maturity_axes'] = _json.dumps(valid_axes, ensure_ascii=False)

        wh.sb.table('tracked_projects').update(update_data).eq('slug', project_slug).execute()
        print(f"  ✓ tracked_projects.maturity_score = {score} ({stage})")
        if valid_axes:
            print(f"  ✓ tracked_projects.maturity_axes = {len(valid_axes)} axes")
    except Exception as e:
        print(f"  ✗ DB write error: {e}")


def _register_gdrive_url(
    project_slug: str,
    report_type: str,
    version: int,
    lang: str,
    gdrive_result: Dict[str, str],
) -> None:
    """Register Google Drive URL in Supabase project_reports table."""
    if not HAS_COLLECTORS:
        return
    try:
        wh = get_warehouse()
        if not wh.connected:
            return

        wh._rpc('wh_register_report_gdrive', {
            'p_project_slug': project_slug,
            'p_report_type': report_type,
            'p_version': version,
            'p_lang': lang,
            'p_gdrive_file_id': gdrive_result.get('id', ''),
            'p_gdrive_url': gdrive_result.get('url', ''),
            'p_gdrive_download_url': gdrive_result.get('download_url', ''),
            'p_gdrive_folder_id': '',
        })
    except Exception as e:
        print(f"  [Supabase] URL registration error: {e}")


def run_stage1_5(
    md_path: str,
    languages: List[str],
    output_dir: str,
    backend: str = 'auto',
    skip: bool = False,
) -> Dict[str, str]:
    """
    Stage 1.5: Translate EN master .md to target languages.

    Returns:
        Dict of {lang: translated_md_path}
    """
    translated_paths = {'en': md_path}

    if skip or not HAS_TRANSLATE_MD:
        if not HAS_TRANSLATE_MD:
            print("  [Stage 1.5] translate_md not available, skipping translation")
        else:
            print("  [Stage 1.5] Translation skipped")
        # Copy EN path for all requested languages
        for lang in languages:
            translated_paths[lang] = md_path
        return translated_paths

    target_langs = [l for l in languages if l != 'en']
    if not target_langs:
        return translated_paths

    print(f"\n{'─'*50}")
    print(f"  STAGE 1.5: Translation → {len(target_langs)} languages")
    print(f"{'─'*50}")

    for lang in target_langs:
        try:
            print(f"  Translating → {lang}...")
            path, meta = translate_md_file(
                md_path,
                target_lang=lang,
                output_dir=output_dir,
                backend=backend,
            )
            translated_paths[lang] = path
            words = meta.get('word_count_target', 0)
            print(f"  ✓ {lang}: {path} ({words} words)")
        except Exception as e:
            print(f"  ✗ {lang}: Translation failed: {e}")
            translated_paths[lang] = md_path  # fallback to EN

    return translated_paths


def run_pipeline(
    report_type: str,
    project_slug: str,
    version: int,
    languages: List[str],
    project_data: Dict[str, Any],
    skip_collect: bool = False,
    skip_upload: bool = False,
    skip_translate: bool = False,
    translate_backend: str = 'auto',
) -> Tuple[str, Dict[str, Any], List[str], Dict]:
    """
    Run the full 5-stage pipeline.

    Returns:
        Tuple of (md_path, metadata, pdf_paths, upload_results)
    """
    project_data.setdefault('slug', project_slug)
    project_data.setdefault('version', version)

    output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Stage 0: Data Collection
    project_data = run_stage0(project_data, skip=skip_collect)

    # Stage 1: Text Analysis (EN master)
    md_path, metadata = run_stage1(report_type, project_data, output_dir)

    # Stage 1.5: Translation
    translated_paths = run_stage1_5(
        md_path, languages, output_dir,
        backend=translate_backend,
        skip=skip_translate,
    )

    # Stage 2: PDF Generation (for each language, using translated .md files)
    pdf_paths = run_stage2(
        report_type, project_slug, version, languages,
        md_path, metadata, output_dir,
        translated_paths=translated_paths,
    )

    # Stage 3: Upload & Publish
    upload_results = run_stage3(
        report_type, project_slug, version, languages,
        md_path, pdf_paths, skip=skip_upload,
    )

    # Stage 4: Persist maturity score to tracked_projects (MAT reports only)
    if report_type in ('mat', 'maturity') and metadata:
        _persist_maturity_score(project_slug, metadata, md_path)

    return md_path, metadata, pdf_paths, upload_results


def print_summary(
    report_type: str,
    md_path: str,
    pdf_paths: List[str],
    upload_results: Dict,
) -> None:
    """Print pipeline completion summary."""
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE — {report_type.upper()}")
    print(f"{'='*60}")
    print(f"  Stage 1 output: {md_path}")
    print(f"  Stage 2 outputs ({len(pdf_paths)} PDF{'s' if len(pdf_paths) > 1 else ''}):")
    for p in pdf_paths:
        print(f"    - {p}")

    if upload_results:
        print(f"  Stage 3 uploads ({len(upload_results)} files):")
        for lang, res in upload_results.items():
            print(f"    - [{lang}] {res.get('url', 'N/A')}")
    else:
        print(f"  Stage 3: No uploads (skipped or not configured)")

    print(f"{'='*60}\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='BCE Lab 4-Stage Report Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python orchestrator.py --type econ --project uniswap --version 1 --lang en
  python orchestrator.py --type mat  --project heyelsaai --version 1 --lang all
  python orchestrator.py --type for  --project heyelsaai --version 1 --lang en --data data.json
  python orchestrator.py --type econ --project uniswap --version 1 --lang en --skip-collect
  python orchestrator.py --type econ --project uniswap --version 1 --lang en --skip-upload
        """
    )
    parser.add_argument('--type', required=True, choices=['econ', 'mat', 'for'],
                        help='Report type: econ, mat, or for')
    parser.add_argument('--project', required=True, help='Project slug')
    parser.add_argument('--version', type=int, required=True, help='Report version')
    parser.add_argument('--lang', required=True,
                        help=f"Language or 'all' ({', '.join(LANGUAGES)})")
    parser.add_argument('--data', help='Path to project data JSON')
    parser.add_argument('--skip-collect', action='store_true',
                        help='Skip Stage 0 data collection')
    parser.add_argument('--skip-upload', action='store_true',
                        help='Skip Stage 3 Google Drive upload')

    args = parser.parse_args()

    # Validate
    if args.lang != 'all' and args.lang not in LANGUAGES:
        print(f"Error: Invalid language '{args.lang}'. Use: {', '.join(LANGUAGES)} or 'all'")
        sys.exit(1)

    languages = LANGUAGES if args.lang == 'all' else [args.lang]

    # Load data
    if args.data:
        project_data = load_project_data(args.data)
    else:
        default_path = Path(__file__).parent.parent.parent / 'data' / f'{args.project}.json'
        if default_path.exists():
            project_data = load_project_data(str(default_path))
        else:
            print(f"Error: No data file. Expected: {default_path}")
            print("Use --data to specify the project data JSON file")
            sys.exit(1)

    # Run pipeline
    md_path, metadata, pdf_paths, upload_results = run_pipeline(
        report_type=args.type,
        project_slug=args.project,
        version=args.version,
        languages=languages,
        project_data=project_data,
        skip_collect=args.skip_collect,
        skip_upload=args.skip_upload,
    )

    print_summary(args.type, md_path, pdf_paths, upload_results)


if __name__ == '__main__':
    main()
