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


def _normalize_md(text: str) -> str:
    # Google Docs 내보내기는 굵은 글씨를 \*\* 형태로 이스케이프해 출력하므로,
    # 정규식 한 벌로 두 형식을 모두 처리하기 위해 이스케이프를 정규화한다.
    return text.replace('\\*', '*')


def parse_econ_pillar_scores(text: str) -> list[float]:
    """ECON 보고서의 종합 평가 점수표에서 각 pillar 점수(0-10)를 추출."""
    norm = _normalize_md(text)
    raw = re.findall(
        r'\*\*\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*10\s*\*\*',
        norm,
    )
    scores: list[float] = []
    for value in raw:
        try:
            score = float(value)
        except ValueError:
            continue
        if 0 <= score <= 10:
            scores.append(score)
    return scores


def parse_mat_overall_score(text: str) -> float | None:
    """MAT 보고서의 단일 종합 진행률(0-100%)을 추출."""
    if not text:
        return None
    norm = _normalize_md(text)

    # Tier 1: 명시적 헤더 형식
    explicit_patterns = [
        r'최종\s*진행률\s*평가\s*(?:결과)?\s*[:：]?\s*\*?\*?\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        r'(?:Final|Overall)\s+(?:Maturity\s+)?(?:Progress|Evaluation\s+Score|Score)'
        r'\s*[:：]?\s*\*?\*?\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        r'Maturity Score\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)',
        r'성숙도 점수\s*[:：]\s*([0-9]+(?:\.[0-9]+)?)',
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, norm, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            if 0 < value <= 100:
                return value

    # Tier 2: 요약 표 행 — 종합 키워드가 있는 라인의 마지막 비-100% bold percent
    table_keywords = (
        '총 달성률', '총달성률',
        '종합 합계 진행률', '종합합계진행률',
        '총 진행률', '종합 진행률',
        '최종 진행률', '최종 달성률',
    )
    for line in norm.splitlines():
        if '|' not in line:
            continue
        if not any(keyword in line for keyword in table_keywords):
            continue
        pcts = re.findall(r'\*\*\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*\*\*', line)
        non_target = []
        for value in pcts:
            try:
                num = float(value)
            except ValueError:
                continue
            if 0 < num < 100 and abs(num - 100.0) > 0.01:
                non_target.append(num)
        if non_target:
            return non_target[-1]

    # Tier 3: 본문 문장
    inline_patterns = [
        r'진행률\s*은?\s*\*+\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*\*+',
        r'(?:최종|종합|총)[가-힣\s]{0,20}\s+([0-9]+(?:\.[0-9]+)?)\s*%(?:\s*(?:로|를|은|이|로서))?\s*평가',
        r'final evaluation score[^0-9]{0,60}([0-9]+(?:\.[0-9]+)?)\s*%',
        r'최종 평가 점수[^0-9]{0,60}([0-9]+(?:\.[0-9]+)?)\s*%',
    ]
    for pattern in inline_patterns:
        for match in re.finditer(pattern, norm, re.IGNORECASE):
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            if 0 < value < 100:
                return value

    return None


def parse_mat_stage(text: str) -> str | None:
    """MAT 보고서의 성숙도 단계 라벨 추출."""
    if not text:
        return None
    norm = _normalize_md(text)
    stage_words = r'(?:Mature|Maturity|Growth|Emerging|Decline|Maturing)'
    patterns = [
        # Korean label + (English) + 단계, with optional bold/quotes
        r"\*{0,2}\s*['\"]?\s*([가-힣]+)\s*\(\s*"
        + stage_words
        + r"\s*\)['\"]?\s*\*{0,2}\s*단계",
        # English-only stage label inside parens followed by 단계
        r'\(\s*(' + stage_words[3:-1] + r')\s*\)\s*\*{0,2}\s*단계',
        r'Stage\s*[:：]\s*([A-Za-z]+)',
        r'단계\s*[:：]\s*([가-힣A-Za-z]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, norm, re.IGNORECASE | re.MULTILINE)
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

    explicit_rating = _extract_match(
        '\n'.join([ko_md, en_md]),
        [
            r'Overall Rating\s*[:：]\s*([A-D][+-]?)\b',
            r'종합 등급\s*[:：]\s*([A-D][+-]?)\b',
            r'평가 등급\s*[:：]\s*([A-D][+-]?)\b',
        ],
    )
    if explicit_rating:
        card_data['rating'] = explicit_rating

    pillar_scores = parse_econ_pillar_scores(ko_md) or parse_econ_pillar_scores(en_md)
    if pillar_scores:
        card_data['rating_scores'] = pillar_scores
        card_data['rating_score'] = round(sum(pillar_scores) / len(pillar_scores), 2)
        if 'rating' not in card_data:
            card_data['rating'] = card_data['rating_score']

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

    score = parse_mat_overall_score(ko_md)
    if score is None:
        score = parse_mat_overall_score(en_md)
    if score is not None:
        card_data['maturity_score'] = score

    stage = parse_mat_stage(ko_md) or parse_mat_stage(en_md)
    if stage:
        card_data['maturity_stage'] = stage

    data_path = _write_card_data(output_dir, slug, card_data)
    return {'card_data': card_data, 'card_data_path': data_path}
