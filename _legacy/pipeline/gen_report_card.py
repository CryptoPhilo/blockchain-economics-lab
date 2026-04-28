"""
BCE Lab — Type-specific report card metadata generators.

FOR reuses the existing forensic card package. ECON and MAT emit lightweight
card payloads so saved card_data matches each report type's contract.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from gen_for_card import extract_summary, generate_for_card

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')


def _read_markdown(path: str | None) -> str:
    if not path or not os.path.exists(path):
        return ''
    return Path(path).read_text(encoding='utf-8')


def _build_base_card_data(
    report_type: str,
    slug: str,
    project_name: str,
    symbol: str,
    ko_md: str,
    en_md: str,
) -> dict:
    summary_ko = extract_summary(ko_md, lang='ko')
    summary_en = extract_summary(en_md, lang='en') if en_md else ''
    return {
        'slug': slug,
        'project_name': project_name,
        'symbol': symbol,
        'report_type': report_type,
        'keywords': [],
        'keywords_en': [],
        'keywords_by_lang': {'ko': [], 'en': []},
        'summary_ko': summary_ko,
        'summary_en': summary_en,
        'summary_by_lang': {'ko': summary_ko, 'en': summary_en},
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def _write_card_data(output_dir: str, slug: str, card_data: dict) -> str:
    os.makedirs(output_dir, exist_ok=True)
    data_path = os.path.join(output_dir, f'card_data_{slug}.json')
    with open(data_path, 'w', encoding='utf-8') as handle:
        json.dump(card_data, handle, ensure_ascii=False, indent=2)
    return data_path


def _extract_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def generate_for_report_card(**kwargs) -> dict:
    return generate_for_card(**kwargs)


def generate_econ_report_card(
    ko_md_path: str,
    en_md_path: str = None,
    trigger_data: dict = None,
    project_name: str = None,
    symbol: str = None,
    slug: str = None,
    output_dir: str = None,
) -> dict:
    del trigger_data
    output_dir = output_dir or OUTPUT_DIR
    slug = slug or 'unknown'
    symbol = symbol or slug.upper()
    project_name = project_name or slug.replace('-', ' ').title()
    ko_md = _read_markdown(ko_md_path)
    en_md = _read_markdown(en_md_path)

    card_data = _build_base_card_data('econ', slug, project_name, symbol, ko_md, en_md)
    rating = _extract_match(
        '\n'.join([ko_md, en_md]),
        [
            r'Overall Rating\s*:\s*([A-Z][+-]?)',
            r'Overall Rating[^A-Z]{0,20}([A-Z][+-]?)',
            r'종합 등급\s*:\s*([A-Z][+-]?)',
            r'평가 등급\s*:\s*([A-Z][+-]?)',
        ],
    )
    if rating:
        card_data['rating'] = rating

    data_path = _write_card_data(output_dir, slug, card_data)
    return {'card_data': card_data, 'card_data_path': data_path}


def generate_mat_report_card(
    ko_md_path: str,
    en_md_path: str = None,
    trigger_data: dict = None,
    project_name: str = None,
    symbol: str = None,
    slug: str = None,
    output_dir: str = None,
) -> dict:
    del trigger_data
    output_dir = output_dir or OUTPUT_DIR
    slug = slug or 'unknown'
    symbol = symbol or slug.upper()
    project_name = project_name or slug.replace('-', ' ').title()
    ko_md = _read_markdown(ko_md_path)
    en_md = _read_markdown(en_md_path)

    card_data = _build_base_card_data('mat', slug, project_name, symbol, ko_md, en_md)
    score_text = _extract_match(
        '\n'.join([ko_md, en_md]),
        [
            r'Maturity Score\s*:\s*([0-9]+(?:\.[0-9]+)?)',
            r'성숙도 점수\s*:\s*([0-9]+(?:\.[0-9]+)?)',
            r'final evaluation score[^0-9]{0,60}([0-9]+(?:\.[0-9]+)?)%',
            r'최종 평가 점수[^0-9]{0,60}([0-9]+(?:\.[0-9]+)?)%',
        ],
    )
    stage = _extract_match(
        '\n'.join([ko_md, en_md]),
        [
            r'Stage\s*:\s*([A-Za-z]+)',
            r'단계\s*:\s*([가-힣A-Za-z]+)',
        ],
    )

    if score_text is not None:
        card_data['maturity_score'] = float(score_text)
    if stage:
        card_data['maturity_stage'] = stage

    data_path = _write_card_data(output_dir, slug, card_data)
    return {'card_data': card_data, 'card_data_path': data_path}
