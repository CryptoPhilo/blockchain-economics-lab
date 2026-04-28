#!/usr/bin/env python3
"""
BCE Lab Report Pipeline Orchestrator — Slide-based Architecture (BCE-1081)

Stage 0: Data Collection (APIs → Supabase warehouse + local enriched JSON)
Stage 1: JSON project data → Markdown text analysis + metadata JSON
Stage 2: Slide PDFs (per language) → embedded HTML viewers
Stage 3: Upload HTML viewers → slide_storage (BCE-1080) + register URLs

Usage:
    python orchestrator.py --type econ|mat|for --project <slug> --version <N> --lang <lang|all>
        [--data <json>] [--skip-collect] [--text-only]
        [--slide-pdf <lang>:<path> ...] [--slide-dir <dir>]

Examples:
    # Text only (Stage 0+1)
    python orchestrator.py --type econ --project uniswap --version 1 --lang en --text-only

    # With per-language slide PDFs (Stage 0+1+2[+3])
    python orchestrator.py --type econ --project uniswap --version 1 --lang all \
        --slide-pdf en:./slides/en.pdf --slide-pdf ko:./slides/ko.pdf

    # With a slide directory using convention {slug}_{type}_slide_{lang}.pdf
    python orchestrator.py --type mat --project heyelsaai --version 1 --lang all \
        --slide-dir ./slides
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Import configuration
try:
    from config import LANGUAGES, OUTPUT_DIR
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

# Stage 2: PDF → HTML slide conversion
from pdf_to_html_slides import convert_pdf_to_html_slides

# Stage 3: Slide HTML storage (BCE-1080 — graceful skip if absent)
try:
    from slide_storage import get_slide_storage
    HAS_SLIDE_STORAGE = True
except ImportError:
    HAS_SLIDE_STORAGE = False


# ─── Dispatchers ───────────────────────────────────────────────

STAGE1_GENERATORS = {
    'econ': generate_text_econ,
    'mat': generate_text_mat,
    'for': generate_text_for,
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
        project_data['_collected'] = collected
        project_data['_data_sources'] = collected.get('data_sources_available', [])

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


def run_stage2_slides(
    report_type: str,
    project_slug: str,
    version: int,
    slide_pdf_by_lang: Dict[str, str],
    output_dir: str,
) -> Dict[str, str]:
    """
    Stage 2: Convert per-language slide PDFs into self-contained HTML viewers.

    Returns:
        Dict of {lang: html_output_path}
    """
    if not slide_pdf_by_lang:
        print("  [Stage 2] No slide PDFs provided. Skipping.")
        return {}

    print(f"\n{'='*60}")
    print(f"  STAGE 2: Slide HTML Generation ({report_type.upper()})")
    print(f"{'='*60}")

    html_paths: Dict[str, str] = {}
    title = f"{project_slug} — {report_type.upper()} v{version}"

    for lang, pdf_path in slide_pdf_by_lang.items():
        if not os.path.exists(pdf_path):
            print(f"  ✗ Slide PDF missing for {lang}: {pdf_path}")
            continue

        out_html = os.path.join(
            output_dir,
            f"{project_slug}_{report_type}_slide_{lang}.html",
        )
        try:
            print(f"  Converting {lang}: {pdf_path}")
            html_path = convert_pdf_to_html_slides(
                pdf_path=pdf_path,
                output_path=out_html,
                title=title,
                lang=lang,
            )
            html_paths[lang] = html_path
            print(f"  ✓ HTML: {html_path}")
        except Exception as e:
            print(f"  ✗ Error converting {lang}: {e}")
            import traceback
            traceback.print_exc()

    return html_paths


def run_stage3_storage(
    report_type: str,
    project_slug: str,
    version: int,
    html_paths_by_lang: Dict[str, str],
) -> Dict[str, Any]:
    """
    Stage 3: Upload generated HTML viewers via slide_storage (BCE-1080).

    Returns dict of {lang: storage_result}. Empty dict if slide_storage missing
    or no HTML paths supplied.
    """
    if not html_paths_by_lang:
        print("  [Stage 3] No HTML paths to upload. Skipping.")
        return {}

    if not HAS_SLIDE_STORAGE:
        print("\n  [Stage 3] slide_storage not available (BCE-1080 pending). Skipping.")
        return {}

    storage = get_slide_storage()

    print(f"\n{'='*60}")
    print(f"  STAGE 3: Slide HTML Storage ({report_type.upper()})")
    print(f"{'='*60}")

    results: Dict[str, Any] = {}
    for lang, html_path in html_paths_by_lang.items():
        try:
            result = storage.upload_slide(
                local_path=html_path,
                project_slug=project_slug,
                report_type=report_type,
                version=version,
                lang=lang,
            )
            if result:
                results[lang] = result
                url = result.get('url') if isinstance(result, dict) else result
                print(f"  ✓ Uploaded {lang}: {url}")
            else:
                print(f"  ✗ Upload failed for {lang}")
        except Exception as e:
            print(f"  ✗ Storage error for {lang}: {e}")
            import traceback
            traceback.print_exc()

    return results


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

    score = metadata.get('total_maturity_score')
    stage = metadata.get('maturity_stage')
    axes_raw = metadata.get('strategic_objectives') or metadata.get('axes') or []

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
                if 0 < candidate < 100:
                    score = candidate
                    break

    if not score:
        print("  [SKIP] No maturity score found in metadata or markdown")
        return

    qa_errors = []
    qa_warnings = []

    if not (0 <= score <= 100):
        qa_errors.append(f"Score {score} out of valid range [0, 100]")

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
        if score < 25:
            stage = 'nascent'
        elif score < 50:
            stage = 'growing'
        elif score < 75:
            stage = 'mature'
        else:
            stage = 'established'

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

    if qa_errors:
        for e in qa_errors:
            print(f"  ✗ QA ERROR: {e}")
        print("  [ABORT] Score NOT written to DB due to QA errors")
        return

    for w in qa_warnings:
        print(f"  ⚠ QA WARN: {w}")

    print(f"  ✓ QA passed — score={score}, stage={stage}, axes={len(valid_axes)}")

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


def collect_slide_pdfs(
    report_type: str,
    project_slug: str,
    languages: List[str],
    slide_pdf_args: Optional[List[str]],
    slide_dir: Optional[str],
) -> Dict[str, str]:
    """
    Resolve slide PDF inputs from --slide-pdf and/or --slide-dir CLI flags.

    Filters to the requested language set. Returns {lang: pdf_path}.
    """
    by_lang: Dict[str, str] = {}

    if slide_dir:
        d = Path(slide_dir)
        if not d.is_dir():
            print(f"  Warning: --slide-dir not a directory: {slide_dir}")
        else:
            for lang in languages:
                candidate = d / f"{project_slug}_{report_type}_slide_{lang}.pdf"
                if candidate.exists():
                    by_lang[lang] = str(candidate)

    if slide_pdf_args:
        for spec in slide_pdf_args:
            if ':' not in spec:
                print(f"  Warning: --slide-pdf '{spec}' missing '<lang>:<path>' format. Skipping.")
                continue
            lang, path = spec.split(':', 1)
            lang = lang.strip()
            path = path.strip()
            if lang not in languages:
                continue
            by_lang[lang] = path

    return by_lang


def run_pipeline(
    report_type: str,
    project_slug: str,
    version: int,
    languages: List[str],
    project_data: Dict[str, Any],
    slide_pdf_by_lang: Optional[Dict[str, str]] = None,
    skip_collect: bool = False,
    text_only: bool = False,
) -> Tuple[str, Dict[str, Any], Dict[str, str], Dict[str, Any]]:
    """
    Run the slide-based pipeline.

    Returns:
        Tuple of (md_path, metadata, html_paths_by_lang, storage_results)
    """
    project_data.setdefault('slug', project_slug)
    project_data.setdefault('version', version)

    output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    project_data = run_stage0(project_data, skip=skip_collect)

    md_path, metadata = run_stage1(report_type, project_data, output_dir)

    html_paths: Dict[str, str] = {}
    storage_results: Dict[str, Any] = {}

    if text_only:
        print("\n  [Stage 2/3] --text-only set; skipping slide and storage stages.")
    else:
        if slide_pdf_by_lang:
            html_paths = run_stage2_slides(
                report_type, project_slug, version,
                slide_pdf_by_lang, output_dir,
            )
            storage_results = run_stage3_storage(
                report_type, project_slug, version, html_paths,
            )
        else:
            print("\n  [Stage 2/3] No --slide-pdf or --slide-dir input; skipping slide stages.")

    if report_type in ('mat', 'maturity') and metadata:
        _persist_maturity_score(project_slug, metadata, md_path)

    return md_path, metadata, html_paths, storage_results


def print_summary(
    report_type: str,
    md_path: str,
    html_paths: Dict[str, str],
    storage_results: Dict[str, Any],
) -> None:
    """Print pipeline completion summary."""
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE — {report_type.upper()}")
    print(f"{'='*60}")
    print(f"  Stage 1 output: {md_path}")
    if html_paths:
        print(f"  Stage 2 outputs ({len(html_paths)} HTML viewer{'s' if len(html_paths) > 1 else ''}):")
        for lang, p in html_paths.items():
            print(f"    - [{lang}] {p}")
    else:
        print(f"  Stage 2: No slide HTML generated")

    if storage_results:
        print(f"  Stage 3 uploads ({len(storage_results)} files):")
        for lang, res in storage_results.items():
            url = res.get('url') if isinstance(res, dict) else res
            print(f"    - [{lang}] {url}")
    else:
        print(f"  Stage 3: No uploads (skipped, no input, or slide_storage absent)")

    print(f"{'='*60}\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='BCE Lab Slide-based Report Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python orchestrator.py --type econ --project uniswap --version 1 --lang en --text-only
  python orchestrator.py --type econ --project uniswap --version 1 --lang ko \\
      --slide-pdf ko:samples/test.pdf --skip-collect
  python orchestrator.py --type mat --project heyelsaai --version 1 --lang all \\
      --slide-dir ./slides
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
    parser.add_argument('--text-only', action='store_true',
                        help='Run Stage 0+1 only; skip slide HTML and storage stages')
    parser.add_argument('--slide-pdf', action='append', default=None,
                        metavar='<lang>:<path>',
                        help='Slide PDF for a language (repeatable). Example: '
                             '--slide-pdf en:./en.pdf --slide-pdf ko:./ko.pdf')
    parser.add_argument('--slide-dir', default=None,
                        help='Directory containing {slug}_{type}_slide_{lang}.pdf files')

    args = parser.parse_args()

    if args.lang != 'all' and args.lang not in LANGUAGES:
        print(f"Error: Invalid language '{args.lang}'. Use: {', '.join(LANGUAGES)} or 'all'")
        sys.exit(1)

    languages = LANGUAGES if args.lang == 'all' else [args.lang]

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

    slide_pdf_by_lang = collect_slide_pdfs(
        report_type=args.type,
        project_slug=args.project,
        languages=languages,
        slide_pdf_args=args.slide_pdf,
        slide_dir=args.slide_dir,
    )

    md_path, metadata, html_paths, storage_results = run_pipeline(
        report_type=args.type,
        project_slug=args.project,
        version=args.version,
        languages=languages,
        project_data=project_data,
        slide_pdf_by_lang=slide_pdf_by_lang,
        skip_collect=args.skip_collect,
        text_only=args.text_only,
    )

    print_summary(args.type, md_path, html_paths, storage_results)


if __name__ == '__main__':
    main()
