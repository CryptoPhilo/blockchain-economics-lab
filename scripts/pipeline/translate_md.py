#!/usr/bin/env python3
"""
BCE Lab — Markdown Report Translation Module (translate_md.py)

Translates .md files while preserving:
  - YAML frontmatter structure (keys stay English, values get translated)
  - Markdown formatting (tables, headers, code blocks, links)
  - slide_data numeric values (scores, percentages, probabilities)
  - File naming convention: {slug}_{type}_v{ver}_{lang}.md

Translation backends (pluggable):
  1. Anthropic Claude API (recommended — structure-aware, blockchain terminology)
  2. Google Cloud Translation API
  3. DeepL API
  4. Offline stub (for testing)

Usage:
    python translate_md.py input.md --lang ko
    python translate_md.py input.md --lang all
    python translate_md.py input.md --lang ko --backend claude
"""

import argparse
import copy
import json
import os
import re
import sys
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# LANGUAGE CONFIG
# ============================================================================

LANGUAGES = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh']
MASTER_LANGUAGES = ['en', 'ko']
TRANSLATION_LANGUAGES = ['fr', 'es', 'de', 'ja', 'zh']

LANG_NAMES = {
    'en': 'English', 'ko': '한국어', 'fr': 'Français',
    'es': 'Español', 'de': 'Deutsch', 'ja': '日本語', 'zh': '中文'
}

# Frontmatter keys whose VALUES should NOT be translated
PRESERVE_KEYS = {
    'report_type', 'slug', 'version', 'lang', 'date', 'token_symbol',
    'overall_rating', 'rating_label', 'report_id', 'classification', 'type',
}

# slide_data keys whose values are numeric / structural — skip translation
NUMERIC_SLIDE_KEYS = {
    'score', 'weight', 'achievement', 'probability', 'impact',
    'current_price', 'volume_24h', 'market_cap', 'maturity_score',
    'onchain_percentage', 'offchain_percentage', 'whale_concentration',
    'exchange_inflows', 'top_holder_pct', 'rsi', 'liquidity_score',
}

# ============================================================================
# GLOSSARY — blockchain terms for consistent terminology
# ============================================================================

GLOSSARY = {
    'blockchain':       {'ko': '블록체인',     'ja': 'ブロックチェーン', 'zh': '区块链',     'fr': 'blockchain',      'es': 'blockchain',      'de': 'Blockchain'},
    'smart contract':   {'ko': '스마트 컨트랙트', 'ja': 'スマートコントラクト', 'zh': '智能合约', 'fr': 'contrat intelligent', 'es': 'contrato inteligente', 'de': 'Smart Contract'},
    'token':            {'ko': '토큰',         'ja': 'トークン',       'zh': '代币',       'fr': 'jeton',           'es': 'token',           'de': 'Token'},
    'consensus':        {'ko': '합의',         'ja': 'コンセンサス',    'zh': '共识',       'fr': 'consensus',       'es': 'consenso',        'de': 'Konsens'},
    'decentralization': {'ko': '탈중앙화',      'ja': '分散化',         'zh': '去中心化',    'fr': 'décentralisation', 'es': 'descentralización', 'de': 'Dezentralisierung'},
    'proof of work':    {'ko': '작업 증명',     'ja': 'プルーフ・オブ・ワーク', 'zh': '工作量证明', 'fr': 'preuve de travail', 'es': 'prueba de trabajo', 'de': 'Proof of Work'},
    'proof of stake':   {'ko': '지분 증명',     'ja': 'プルーフ・オブ・ステーク', 'zh': '权益证明',  'fr': 'preuve d\'enjeu', 'es': 'prueba de participación', 'de': 'Proof of Stake'},
    'mining':           {'ko': '채굴',         'ja': 'マイニング',     'zh': '挖矿',       'fr': 'minage',          'es': 'minería',         'de': 'Mining'},
    'wallet':           {'ko': '지갑',         'ja': 'ウォレット',     'zh': '钱包',       'fr': 'portefeuille',    'es': 'billetera',       'de': 'Wallet'},
    'hash rate':        {'ko': '해시레이트',    'ja': 'ハッシュレート',  'zh': '哈希率',     'fr': 'taux de hachage', 'es': 'tasa de hash',    'de': 'Hashrate'},
    'DeFi':             {'ko': '디파이',       'ja': 'DeFi',          'zh': 'DeFi',       'fr': 'DeFi',            'es': 'DeFi',            'de': 'DeFi'},
    'TVL':              {'ko': 'TVL',          'ja': 'TVL',           'zh': 'TVL',        'fr': 'TVL',             'es': 'TVL',             'de': 'TVL'},
    'NFT':              {'ko': 'NFT',          'ja': 'NFT',           'zh': 'NFT',        'fr': 'NFT',             'es': 'NFT',             'de': 'NFT'},
    'halving':          {'ko': '반감기',       'ja': '半減期',         'zh': '减半',       'fr': 'halving',         'es': 'halving',         'de': 'Halving'},
    'liquidity':        {'ko': '유동성',       'ja': '流動性',         'zh': '流动性',     'fr': 'liquidité',       'es': 'liquidez',        'de': 'Liquidität'},
    'governance':       {'ko': '거버넌스',     'ja': 'ガバナンス',     'zh': '治理',       'fr': 'gouvernance',     'es': 'gobernanza',      'de': 'Governance'},
    'staking':          {'ko': '스테이킹',     'ja': 'ステーキング',    'zh': '质押',       'fr': 'staking',         'es': 'staking',         'de': 'Staking'},
    'whale':            {'ko': '고래',         'ja': 'クジラ',         'zh': '巨鲸',       'fr': 'baleine',         'es': 'ballena',         'de': 'Wal'},
    'forensic':         {'ko': '포렌식',       'ja': 'フォレンジック',  'zh': '取证',       'fr': 'forensique',      'es': 'forense',         'de': 'Forensik'},
    'wash trading':     {'ko': '워시 트레이딩', 'ja': 'ウォッシュトレーディング', 'zh': '刷量交易', 'fr': 'wash trading', 'es': 'wash trading', 'de': 'Wash Trading'},
}

# ============================================================================
# MARKDOWN PARSER — separate translatable text from structure
# ============================================================================

def parse_md_file(md_path: str) -> Tuple[dict, str]:
    """Parse .md file into YAML frontmatter dict and body string."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract YAML frontmatter
    fm = {}
    body = content
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as e:
                logger.warning(f"YAML parse error: {e}")
            body = parts[2].lstrip('\n')

    return fm, body


def classify_body_lines(body: str) -> List[Tuple[str, str]]:
    """
    Classify each line of markdown body as translatable or structural.
    Returns list of (type, content) tuples.

    Types:
      'header'    — # heading text (translate the text after #)
      'table_sep' — |---|---| separator (preserve)
      'table_row' — | cell | cell | (translate cell contents)
      'code_fence'— ``` or ~~~ (preserve)
      'code_line' — inside code block (preserve)
      'link_line' — [text](url) pure link (translate text, preserve url)
      'empty'     — blank line (preserve)
      'text'      — normal text (translate)
      'list_item' — - or * or 1. item (translate the text after marker)
      'blockquote'— > text (translate text after >)
      'html'      — <tag> (preserve)
    """
    lines = body.split('\n')
    classified = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Code fence toggle
        if stripped.startswith('```') or stripped.startswith('~~~'):
            in_code_block = not in_code_block
            classified.append(('code_fence', line))
            continue

        if in_code_block:
            classified.append(('code_line', line))
            continue

        # Empty line
        if not stripped:
            classified.append(('empty', line))
            continue

        # Header
        if re.match(r'^#{1,6}\s', stripped):
            classified.append(('header', line))
            continue

        # Table separator
        if re.match(r'^\|[\s\-:|]+\|$', stripped):
            classified.append(('table_sep', line))
            continue

        # Table row
        if stripped.startswith('|') and stripped.endswith('|'):
            classified.append(('table_row', line))
            continue

        # HTML tag
        if stripped.startswith('<') and stripped.endswith('>'):
            classified.append(('html', line))
            continue

        # Blockquote
        if stripped.startswith('>'):
            classified.append(('blockquote', line))
            continue

        # List item
        if re.match(r'^(\s*)([-*+]|\d+\.)\s', line):
            classified.append(('list_item', line))
            continue

        # Normal text
        classified.append(('text', line))

    return classified


# ============================================================================
# TRANSLATION BACKENDS
# ============================================================================

def _translate_stub(text: str, target_lang: str, _ctx: str = '') -> str:
    """Stub backend: prefix with language tag. For testing only."""
    if not text or not text.strip():
        return text
    return f"[{target_lang.upper()}] {text}"


def _translate_claude(text: str, target_lang: str, context: str = '') -> str:
    """
    Claude API backend for high-quality context-aware translation.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, falling back to stub")
        return _translate_stub(text, target_lang)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        lang_name = LANG_NAMES.get(target_lang, target_lang)
        system_prompt = (
            f"You are a professional translator specializing in blockchain and cryptocurrency. "
            f"Translate the following text to {lang_name}. "
            f"Preserve all markdown formatting, technical terms, ticker symbols, and numbers. "
            f"Do NOT translate the following — keep them EXACTLY as-is:\n"
            f"  - Token/coin symbols: BTC, ETH, SOL, ELSA, USDC, ENJ, LEO, MYX, etc.\n"
            f"  - Protocol and project names: Uniswap, Solana, Enjin, HeyElsa, etc.\n"
            f"  - Mathematical symbols and variables: μ, σ, ρ, f*, CR, NC, T_finality, etc.\n"
            f"  - Formulas and equations: V ∝ R/S, f* = (p·b - q) / b, etc.\n"
            f"  - URLs, code blocks, and inline code\n"
            f"  - [?] placeholders (if any remain, keep as [?])\n"
            f"Use standard blockchain terminology for {lang_name}. "
            f"Return ONLY the translated text, no explanations."
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": text}]
        )
        return message.content[0].text.strip()

    except ImportError:
        logger.warning("anthropic package not installed, falling back to stub")
        return _translate_stub(text, target_lang)
    except Exception as e:
        logger.error(f"Claude translation error: {e}")
        return _translate_stub(text, target_lang)


def _translate_batch_claude(texts: List[str], target_lang: str) -> List[str]:
    """Batch translate multiple texts in a single Claude call for efficiency."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key or not texts:
        return [_translate_stub(t, target_lang) for t in texts]

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        lang_name = LANG_NAMES.get(target_lang, target_lang)

        # Combine texts with numbered markers
        combined = "\n".join(f"[[[{i}]]] {t}" for i, t in enumerate(texts))

        system_prompt = (
            f"You are a professional blockchain/crypto translator. "
            f"Translate each numbered line below to {lang_name}. "
            f"Keep the [[[N]]] markers. Preserve markdown formatting, "
            f"ticker symbols (BTC, ETH, ELSA, USDC, ENJ, LEO, MYX, SOL, etc.), "
            f"mathematical symbols (μ, σ, ρ, f*, CR, NC, etc.), formulas, "
            f"URLs, numbers, code blocks. Do NOT translate token names or math notation. "
            f"Return ONLY the translations with markers."
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": combined}]
        )

        result_text = message.content[0].text.strip()

        # Parse results
        results = {}
        for match in re.finditer(r'\[\[\[(\d+)\]\]\]\s*(.*?)(?=\[\[\[\d+\]\]\]|$)', result_text, re.DOTALL):
            idx = int(match.group(1))
            translated = match.group(2).strip()
            results[idx] = translated

        return [results.get(i, _translate_stub(t, target_lang)) for i, t in enumerate(texts)]

    except Exception as e:
        logger.error(f"Batch Claude translation error: {e}")
        return [_translate_stub(t, target_lang) for t in texts]


# ── deep-translator (Google Translate) backend ────────────────────

# Language code mapping: our codes → Google Translate codes
_GOOGLE_LANG_MAP = {
    'en': 'en', 'ko': 'ko', 'ja': 'ja', 'zh': 'zh-CN',
    'fr': 'fr', 'es': 'es', 'de': 'de',
}


def _translate_google(text: str, target_lang: str, _ctx: str = '') -> str:
    """
    Google Translate backend via deep-translator library.
    Free, no API key required, high quality.
    Includes retry with exponential backoff for rate-limiting.
    """
    import time as _time
    if not text or not text.strip():
        return text
    # Skip very short or code-like text
    stripped = text.strip()
    if len(stripped) <= 3 or stripped.isupper() or re.match(r'^[\d.%$,+\-×/()]+$', stripped):
        return text
    # Skip base64 image data (too long, not translatable)
    if stripped.startswith('[image') and 'data:image' in stripped:
        return text
    # Google free API limit ~5000 chars — skip if too long
    if len(stripped) > 4500:
        logger.warning(f"Google translate skip: text too long ({len(stripped)} chars)")
        return text

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            from deep_translator import GoogleTranslator
            gl = _GOOGLE_LANG_MAP.get(target_lang, target_lang)
            result = GoogleTranslator(source='auto', target=gl).translate(stripped)
            # Small throttle to avoid rate limiting
            _time.sleep(0.3)
            return result if result else text
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 3  # 3s, 6s
                logger.warning(f"Google translate retry {attempt+1}: {str(e)[:100]}")
                _time.sleep(wait)
            else:
                logger.warning(f"Google translate error (final): {str(e)[:100]}")
                return text
    return text


def _translate_batch_google(texts: List[str], target_lang: str) -> List[str]:
    """Batch translate using deep-translator Google backend."""
    if not texts:
        return []

    try:
        from deep_translator import GoogleTranslator
        gl = _GOOGLE_LANG_MAP.get(target_lang, target_lang)
        translator = GoogleTranslator(source='auto', target=gl)

        results = []
        # Google Translate has a ~5000 char limit per call, batch accordingly
        for text in texts:
            stripped = text.strip()
            if not stripped or len(stripped) <= 3:
                results.append(text)
                continue
            try:
                translated = translator.translate(stripped)
                results.append(translated if translated else text)
            except Exception as e:
                logger.warning(f"Batch Google translate error for text: {e}")
                results.append(text)
        return results

    except ImportError:
        logger.warning("deep-translator not installed, falling back to stub")
        return [_translate_stub(t, target_lang) for t in texts]
    except Exception as e:
        logger.error(f"Batch Google translate error: {e}")
        return [_translate_stub(t, target_lang) for t in texts]


# Backend registry
BACKENDS = {
    'stub': _translate_stub,
    'claude': _translate_claude,
    'google': _translate_google,
}


def get_translate_fn(backend: str = 'auto'):
    """Get translation function. 'auto' tries Claude → Google → stub."""
    if backend == 'auto':
        if os.environ.get('ANTHROPIC_API_KEY'):
            return _translate_claude
        # Try Google Translate via deep-translator
        try:
            from deep_translator import GoogleTranslator
            return _translate_google
        except ImportError:
            pass
        return _translate_stub
    if backend == 'google':
        return _translate_google
    return BACKENDS.get(backend, _translate_stub)


# ============================================================================
# FRONTMATTER TRANSLATION
# ============================================================================

def translate_frontmatter(fm: dict, target_lang: str, translate_fn) -> dict:
    """
    Translate YAML frontmatter values. Keys stay English.
    Numeric/structural values preserved. Only text values translated.
    """
    translated = copy.deepcopy(fm)
    translated['lang'] = target_lang

    def _translate_value(key: str, value, parent_key: str = '') -> Any:
        full_key = f"{parent_key}.{key}" if parent_key else key

        # Skip preserved keys
        if key in PRESERVE_KEYS:
            return value

        # Skip numeric slide_data fields
        if key in NUMERIC_SLIDE_KEYS:
            return value

        # Handle different types
        if isinstance(value, str):
            # Skip short values that look like codes/symbols
            if len(value) <= 3 or value.isupper() or re.match(r'^[\d.%$]+$', value):
                return value
            return translate_fn(value, target_lang, full_key)

        elif isinstance(value, list):
            return [_translate_value(str(i), item, full_key) for i, item in enumerate(value)]

        elif isinstance(value, dict):
            return {k: _translate_value(k, v, full_key) for k, v in value.items()}

        else:
            return value  # numbers, bools, None

    for key, value in fm.items():
        if key == 'slide_data':
            translated['slide_data'] = _translate_slide_data(value, target_lang, translate_fn)
        elif key not in PRESERVE_KEYS:
            translated[key] = _translate_value(key, value)

    return translated


def _translate_slide_data(sd: dict, target_lang: str, translate_fn) -> dict:
    """Translate slide_data section. Numeric scores preserved, text translated."""
    if not sd:
        return sd

    result = copy.deepcopy(sd)

    # Text fields to translate
    text_keys = [
        'executive_summary', 'supply_model', 'trigger_reason',
        'architecture_summary', 'investment_thesis',
    ]
    for key in text_keys:
        if key in result and isinstance(result[key], str):
            result[key] = translate_fn(result[key], target_lang, f'slide_data.{key}')

    # List-of-string fields
    list_str_keys = [
        'project_identity', 'key_findings', 'token_utility',
        'recommendations', 'monitoring_checklist',
    ]
    for key in list_str_keys:
        if key in result and isinstance(result[key], list):
            result[key] = [
                translate_fn(item, target_lang, f'slide_data.{key}')
                if isinstance(item, str) else item
                for item in result[key]
            ]

    # List-of-dict fields: translate 'name', 'description', 'type' etc. but keep numeric fields
    dict_list_keys = [
        'tech_pillars', 'risk_factors', 'roadmap_phases',
        'strategic_objectives', 'manipulation_scores',
        'risk_indicators', 'threat_vectors', 'team_wallet_flows',
        'timeline_milestones',
    ]
    for key in dict_list_keys:
        if key in result and isinstance(result[key], list):
            for item in result[key]:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if isinstance(v, str) and k not in NUMERIC_SLIDE_KEYS:
                            item[k] = translate_fn(v, target_lang, f'slide_data.{key}.{k}')

    # Nested dict fields: translate values but not keys
    nested_keys = ['chain_info', 'crypto_economy', 'market_data',
                   'onchain_data', 'technical_analysis']
    for key in nested_keys:
        if key in result and isinstance(result[key], dict):
            for k, v in result[key].items():
                if isinstance(v, str) and k not in NUMERIC_SLIDE_KEYS:
                    result[key][k] = translate_fn(v, target_lang, f'slide_data.{key}.{k}')

    # token_distribution: keep as-is (key=name, value=number)
    # But translate the names (keys)
    if 'token_distribution' in result and isinstance(result['token_distribution'], dict):
        new_dist = {}
        for k, v in result['token_distribution'].items():
            new_key = translate_fn(k, target_lang, 'slide_data.token_distribution')
            new_dist[new_key] = v
        result['token_distribution'] = new_dist

    return result


# ============================================================================
# BODY TRANSLATION
# ============================================================================

def translate_body(body: str, target_lang: str, translate_fn, batch: bool = True) -> str:
    """
    Translate markdown body while preserving structure.
    Uses batch mode when possible for efficiency.
    """
    classified = classify_body_lines(body)

    if batch and translate_fn == _translate_claude:
        return _translate_body_batch(classified, target_lang)

    translated_lines = []
    for line_type, line in classified:
        translated_lines.append(_translate_line(line_type, line, target_lang, translate_fn))

    return '\n'.join(translated_lines)


def _translate_line(line_type: str, line: str, target_lang: str, translate_fn) -> str:
    """Translate a single classified line."""

    if line_type in ('code_fence', 'code_line', 'table_sep', 'empty', 'html'):
        return line  # preserve as-is

    if line_type == 'header':
        # Translate text after # markers
        match = re.match(r'^(#{1,6}\s+)(.*)', line)
        if match:
            prefix, text = match.groups()
            # Don't translate chapter numbers like "Chapter 1:"
            chapter_match = re.match(r'^(Chapter\s+\d+[.:]\s*)(.*)', text)
            if chapter_match:
                ch_prefix, ch_text = chapter_match.groups()
                return f"{prefix}{translate_fn(ch_prefix, target_lang)}{translate_fn(ch_text, target_lang)}"
            return f"{prefix}{translate_fn(text, target_lang)}"
        return line

    if line_type == 'table_row':
        # Translate cell contents, preserve | structure.
        # CRITICAL: translator output must NOT contain '|' (would break table
        # geometry). If it does, fall back to original cell.
        cells = line.split('|')
        translated_cells = []
        for cell in cells:
            stripped = cell.strip()
            if not stripped:
                translated_cells.append(cell)
            elif re.match(r'^[\d.,\-$%+×/()EHMBLNTPS:]+$', stripped):
                translated_cells.append(cell)  # numeric / code
            elif stripped in ('PASS', 'FAIL', 'WARN', 'GAP', 'N/A', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'):
                translated_cells.append(cell)  # status labels — keep
            else:
                padding = len(cell) - len(cell.lstrip())
                translated = translate_fn(stripped, target_lang)
                # Defensive: strip any pipe characters the translator may have
                # emitted (including full-width ｜). Keep original if the
                # translation is empty after cleaning.
                translated = translated.replace('|', ' ').replace('\uff5c', ' ').strip()
                if not translated:
                    translated = stripped
                translated_cells.append(' ' * padding + translated + ' ')
        return '|'.join(translated_cells)

    if line_type == 'list_item':
        match = re.match(r'^(\s*(?:[-*+]|\d+\.)\s+)(.*)', line)
        if match:
            prefix, text = match.groups()
            return f"{prefix}{translate_fn(text, target_lang)}"
        return line

    if line_type == 'blockquote':
        match = re.match(r'^(>\s*)(.*)', line)
        if match:
            prefix, text = match.groups()
            if text.strip():
                return f"{prefix}{translate_fn(text, target_lang)}"
        return line

    if line_type == 'text':
        if not line.strip():
            return line
        # Preserve leading whitespace
        indent = len(line) - len(line.lstrip())
        return ' ' * indent + translate_fn(line.strip(), target_lang)

    return line


def _translate_body_batch(classified: List[Tuple[str, str]], target_lang: str) -> str:
    """Batch-translate body lines using Claude for efficiency."""
    # Collect translatable texts
    to_translate = []
    indices = []

    for i, (line_type, line) in enumerate(classified):
        if line_type in ('text', 'header', 'list_item', 'blockquote'):
            text = line.strip()
            if text and len(text) > 3:
                to_translate.append(text)
                indices.append(i)

    if not to_translate:
        return '\n'.join(line for _, line in classified)

    # Batch translate
    translated = _translate_batch_claude(to_translate, target_lang)

    # Rebuild lines
    result_lines = []
    trans_map = dict(zip(indices, translated))

    for i, (line_type, line) in enumerate(classified):
        if i in trans_map:
            # Reconstruct with original formatting
            result_lines.append(_reconstruct_line(line_type, line, trans_map[i]))
        elif line_type in ('code_fence', 'code_line', 'table_sep', 'empty', 'html'):
            result_lines.append(line)
        elif line_type == 'table_row':
            # Per-cell Claude translation with pipe-sanitization.
            # We use single-call Claude (not batched) because each cell is
            # small — sending through `_translate_claude` honours ANTHROPIC
            # env and falls back to stub if unavailable.
            result_lines.append(_translate_line(line_type, line, target_lang, _translate_claude))
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


def _reconstruct_line(line_type: str, original: str, translated: str) -> str:
    """Reconstruct a line with translated content preserving markdown prefix."""
    if line_type == 'header':
        match = re.match(r'^(#{1,6}\s+)', original)
        if match:
            return f"{match.group(1)}{translated}"
    elif line_type == 'list_item':
        match = re.match(r'^(\s*(?:[-*+]|\d+\.)\s+)', original)
        if match:
            return f"{match.group(1)}{translated}"
    elif line_type == 'blockquote':
        match = re.match(r'^(>\s*)', original)
        if match:
            return f"{match.group(1)}{translated}"
    indent = len(original) - len(original.lstrip())
    return ' ' * indent + translated


# ============================================================================
# GLOSSARY POST-PROCESSING
# ============================================================================

def apply_glossary(text: str, target_lang: str) -> str:
    """Apply glossary terms for consistent blockchain terminology."""
    if target_lang == 'en' or not text:
        return text

    for en_term, translations in GLOSSARY.items():
        if target_lang in translations:
            # Case-insensitive replacement of English terms with target language
            pattern = re.compile(re.escape(en_term), re.IGNORECASE)
            text = pattern.sub(translations[target_lang], text)

    return text


# ============================================================================
# MAIN TRANSLATION PIPELINE
# ============================================================================

def translate_md_file(
    input_path: str,
    target_lang: str,
    output_dir: str = None,
    backend: str = 'auto',
    apply_gloss: bool = True,
) -> Tuple[str, dict]:
    """
    Translate a .md report file to target language.

    Args:
        input_path: Path to source .md file (EN master)
        target_lang: Target language code (ko, fr, es, de, ja, zh)
        output_dir: Output directory (default: same as input)
        backend: Translation backend ('auto', 'claude', 'stub')
        apply_gloss: Apply glossary post-processing

    Returns:
        (output_path, metadata_dict)
    """
    input_path = str(input_path)
    logger.info(f"Translating {input_path} → {target_lang}")

    # Parse source .md
    fm, body = parse_md_file(input_path)
    translate_fn = get_translate_fn(backend)

    # Translate frontmatter
    translated_fm = translate_frontmatter(fm, target_lang, translate_fn)

    # Translate body
    translated_body = translate_body(body, target_lang, translate_fn, batch=(backend == 'claude'))

    # Apply glossary
    if apply_gloss:
        translated_body = apply_glossary(translated_body, target_lang)

    # Assemble output
    fm_yaml = yaml.dump(translated_fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    output_content = f"---\n{fm_yaml}---\n\n{translated_body}"

    # Determine output path
    if not output_dir:
        output_dir = os.path.dirname(input_path)

    # Replace language code in filename (support any source lang suffix)
    base = os.path.basename(input_path)
    out_name = re.sub(r'_(en|ko|ja|zh|fr|es|de)\.md$', f'_{target_lang}.md', base)
    if out_name == base:  # no recognised lang suffix
        name, ext = os.path.splitext(base)
        out_name = f"{name}_{target_lang}{ext}"

    output_path = os.path.join(output_dir, out_name)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_content)

    # Metadata
    meta = {
        'source': input_path,
        'target_lang': target_lang,
        'output': output_path,
        'backend': backend,
        'glossary_applied': apply_gloss,
        'source_lang': fm.get('lang', 'en'),
        'translated_at': datetime.utcnow().isoformat() + 'Z',
        'word_count_source': len(body.split()),
        'word_count_target': len(translated_body.split()),
    }

    logger.info(f"✓ Written: {output_path} ({meta['word_count_target']} words)")
    return output_path, meta


def translate_md_all_languages(
    input_path: str,
    output_dir: str = None,
    backend: str = 'auto',
    languages: List[str] = None,
) -> Dict[str, Tuple[str, dict]]:
    """
    Translate .md file to all target languages.

    Returns:
        Dict of {lang: (output_path, metadata)}
    """
    if languages is None:
        languages = [l for l in LANGUAGES if l != 'en']

    results = {}
    for lang in languages:
        try:
            path, meta = translate_md_file(input_path, lang, output_dir, backend)
            results[lang] = (path, meta)
        except Exception as e:
            logger.error(f"Failed to translate to {lang}: {e}")
            results[lang] = (None, {'error': str(e)})

    return results


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Translate BCE Lab .md reports')
    parser.add_argument('input', help='Input .md file path')
    parser.add_argument('--lang', default='all',
                        help=f"Target language or 'all' ({', '.join(LANGUAGES)})")
    parser.add_argument('--backend', default='auto',
                        choices=['auto', 'claude', 'stub'],
                        help='Translation backend')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory')
    parser.add_argument('--no-glossary', action='store_true',
                        help='Skip glossary post-processing')

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    if args.lang == 'all':
        print(f"Translating {args.input} → 6 languages...")
        results = translate_md_all_languages(
            args.input,
            output_dir=args.output_dir,
            backend=args.backend,
            languages=[l for l in LANGUAGES if l != 'en'],
        )
        print(f"\n{'='*60}")
        print(f"Translation Results:")
        for lang, (path, meta) in results.items():
            status = '✓' if path else '✗'
            words = meta.get('word_count_target', 0)
            print(f"  {status} [{lang}] {path or 'FAILED'} ({words} words)")
    else:
        path, meta = translate_md_file(
            args.input,
            target_lang=args.lang,
            output_dir=args.output_dir,
            backend=args.backend,
            apply_gloss=not args.no_glossary,
        )
        print(f"\n✓ Output: {path}")
        print(f"  Words: {meta['word_count_target']}")
        print(f"  Backend: {meta['backend']}")
