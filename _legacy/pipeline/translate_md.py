#!/usr/bin/env python3
"""
BCE Lab — Markdown Report Translation Module (translate_md.py)

Translates .md files while preserving:
  - YAML frontmatter structure (keys stay English, values get translated)
  - Markdown formatting (tables, headers, code blocks, links)
  - slide_data numeric values (scores, percentages, probabilities)
  - File naming convention: {slug}_{type}_v{ver}_{lang}.md

Translation backends (pluggable):
  1. Google Cloud Translation Advanced v3 text API (default operational path)
  2. Anthropic Claude API (optional fallback / explicit override)
  3. Offline stub (for testing / dependency fallback)

Usage:
    python translate_md.py input.md --lang ko
    python translate_md.py input.md --lang all
    python translate_md.py input.md --lang ko --backend google_cloud
"""

import argparse
import copy
import contextlib
import hashlib
import json
import os
import re
import requests
import sys
import threading
import time
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone

from config import LANGUAGES, MASTER_LANGUAGES, TRANSLATION_LANGUAGES, LANGUAGE_NAMES
from google_translate_dispatcher import GoogleTranslateDispatcher, GoogleTranslateDispatcherConfig
from pipeline_env import bootstrap_environment

bootstrap_environment()

logger = logging.getLogger(__name__)

_GOOGLE_CLOUD_CLIENT_LOCK = threading.Lock()
_GOOGLE_CLOUD_CLIENT = None

_GOOGLE_RATE_LIMIT_LOCK = threading.Lock()
_GOOGLE_NEXT_REQUEST_TS = 0.0
_GOOGLE_STRICT_ABORT_ON_RATE_LIMIT = False
_GOOGLE_STRICT_RATE_LIMITED = False
_GOOGLE_MIN_INTERVAL_SECONDS = float(os.environ.get('GOOGLE_TRANSLATE_MIN_INTERVAL_SECONDS', '8.0'))
_GOOGLE_BATCH_MAX_CHARS = int(os.environ.get('GOOGLE_TRANSLATE_BATCH_MAX_CHARS', '900'))
_GOOGLE_BATCH_MAX_ITEMS = int(os.environ.get('GOOGLE_TRANSLATE_BATCH_MAX_ITEMS', '8'))
_GOOGLE_SINGLE_TEXT_MAX_CHARS = int(os.environ.get('GOOGLE_TRANSLATE_SINGLE_TEXT_MAX_CHARS', '700'))
_GOOGLE_RATE_LIMIT_COOLDOWN_SECONDS = int(os.environ.get('GOOGLE_TRANSLATE_RATE_LIMIT_COOLDOWN_SECONDS', '1800'))
_GOOGLE_MAX_BLOCKING_WAIT_SECONDS = float(os.environ.get('GOOGLE_TRANSLATE_MAX_BLOCKING_WAIT_SECONDS', '30'))
_GOOGLE_RATE_LIMIT_STATE_PATH = Path(
    os.environ.get(
        'GOOGLE_TRANSLATE_RATE_LIMIT_STATE_PATH',
        str(Path(__file__).resolve().parents[2] / 'tmp' / 'google_translate_rate_limit.json'),
    )
)
_GOOGLE_RATE_LIMIT_LOCK_PATH = Path(
    os.environ.get(
        'GOOGLE_TRANSLATE_RATE_LIMIT_LOCK_PATH',
        str(Path(__file__).resolve().parents[2] / 'tmp' / 'google_translate_rate_limit.lock'),
    )
)
_GOOGLE_SCHEDULER_PROGRESS_DIR = Path(
    os.environ.get(
        'GOOGLE_TRANSLATE_SCHEDULER_PROGRESS_DIR',
        str(Path(__file__).resolve().parents[2] / 'tmp' / 'google_translate_scheduler'),
    )
)
_GOOGLE_LANGUAGE_ORDER = tuple(
    lang.strip()
    for lang in os.environ.get('GOOGLE_TRANSLATE_LANGUAGE_ORDER', 'en,ko').split(',')
    if lang.strip()
)
_GOOGLE_METRICS = threading.local()
_GOOGLE_DISPATCHER = GoogleTranslateDispatcher(
    GoogleTranslateDispatcherConfig(
        min_interval_seconds=_GOOGLE_MIN_INTERVAL_SECONDS,
        rate_limit_cooldown_seconds=_GOOGLE_RATE_LIMIT_COOLDOWN_SECONDS,
        state_path=_GOOGLE_RATE_LIMIT_STATE_PATH,
        lock_path=_GOOGLE_RATE_LIMIT_LOCK_PATH,
        progress_dir=_GOOGLE_SCHEDULER_PROGRESS_DIR,
        language_order=_GOOGLE_LANGUAGE_ORDER,
        batch_max_chars=_GOOGLE_BATCH_MAX_CHARS,
        batch_max_items=_GOOGLE_BATCH_MAX_ITEMS,
        single_text_max_chars=_GOOGLE_SINGLE_TEXT_MAX_CHARS,
    )
)



def _get_google_dispatcher() -> GoogleTranslateDispatcher:
    _GOOGLE_DISPATCHER.update_config(
        GoogleTranslateDispatcherConfig(
            min_interval_seconds=_GOOGLE_MIN_INTERVAL_SECONDS,
            rate_limit_cooldown_seconds=_GOOGLE_RATE_LIMIT_COOLDOWN_SECONDS,
            state_path=_GOOGLE_RATE_LIMIT_STATE_PATH,
            lock_path=_GOOGLE_RATE_LIMIT_LOCK_PATH,
            progress_dir=_GOOGLE_SCHEDULER_PROGRESS_DIR,
            language_order=_GOOGLE_LANGUAGE_ORDER,
            batch_max_chars=_GOOGLE_BATCH_MAX_CHARS,
            batch_max_items=_GOOGLE_BATCH_MAX_ITEMS,
            single_text_max_chars=_GOOGLE_SINGLE_TEXT_MAX_CHARS,
        )
    )
    return _GOOGLE_DISPATCHER


def _get_google_metrics() -> Dict[str, float]:
    metrics = getattr(_GOOGLE_METRICS, 'value', None)
    if metrics is None:
        metrics = {
            'google_request_count': 0,
            'google_429_count': 0,
            'google_scheduler_wait_seconds': 0.0,
            'google_cooldown_seconds': 0.0,
        }
        _GOOGLE_METRICS.value = metrics
    return metrics


def _reset_google_metrics() -> None:
    _GOOGLE_METRICS.value = {
        'google_request_count': 0,
        'google_429_count': 0,
        'google_scheduler_wait_seconds': 0.0,
        'google_cooldown_seconds': 0.0,
    }


def _record_google_metric(name: str, value: float) -> None:
    metrics = _get_google_metrics()
    metrics[name] = metrics.get(name, 0.0) + value


def _snapshot_google_metrics() -> Dict[str, float]:
    metrics = dict(_get_google_metrics())
    metrics['google_request_count'] = int(metrics.get('google_request_count', 0))
    metrics['google_429_count'] = int(metrics.get('google_429_count', 0))
    metrics['google_scheduler_wait_seconds'] = round(float(metrics.get('google_scheduler_wait_seconds', 0.0)), 3)
    metrics['google_cooldown_seconds'] = round(float(metrics.get('google_cooldown_seconds', 0.0)), 3)
    return metrics


@contextlib.contextmanager
def _google_strict_batch_mode(strict: bool):
    global _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT, _GOOGLE_STRICT_RATE_LIMITED

    prev_abort = _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT
    prev_rate_limited = _GOOGLE_STRICT_RATE_LIMITED
    _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT = bool(strict)
    _GOOGLE_STRICT_RATE_LIMITED = False
    try:
        yield
    finally:
        _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT = prev_abort
        _GOOGLE_STRICT_RATE_LIMITED = prev_rate_limited


def _google_scheduler_policy() -> Dict[str, Any]:
    policy = _get_google_dispatcher().policy()
    policy['max_blocking_wait_seconds'] = _GOOGLE_MAX_BLOCKING_WAIT_SECONDS
    return policy


def _load_google_rate_limit_state() -> Dict[str, Any]:
    try:
        return _get_google_dispatcher().load_rate_limit_state()
    except Exception as exc:
        logger.warning(f"Google rate-limit state load failed: {exc}")
        return {}


def _google_scheduler_file_lock():
    return _get_google_dispatcher().file_lock()


def _save_google_rate_limit_state(
    next_request_ts: float,
    reason: str = '',
    *,
    scheduler: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        _get_google_dispatcher().save_rate_limit_state(
            next_request_ts,
            reason=reason,
            scheduler=scheduler,
        )
    except Exception as exc:
        logger.warning(f"Google rate-limit state save failed: {exc}")


def _ordered_google_languages(languages: List[str], source_lang: str) -> List[str]:
    candidates = [lang for lang in languages if lang != source_lang]
    priority = {lang: idx for idx, lang in enumerate(_GOOGLE_LANGUAGE_ORDER)}
    return sorted(candidates, key=lambda lang: (priority.get(lang, len(priority)), languages.index(lang)))


def _build_google_scheduler_job_id(
    texts: List[str],
    target_lang: str,
    *,
    source_lang: str,
) -> str:
    digest = hashlib.sha1()
    digest.update(target_lang.encode('utf-8'))
    digest.update(b'\0')
    digest.update(source_lang.encode('utf-8'))
    digest.update(b'\0')
    for text in texts:
        digest.update(text.encode('utf-8'))
        digest.update(b'\0')
    return digest.hexdigest()


def _google_scheduler_checkpoint_path(job_id: str) -> Path:
    return _get_google_dispatcher().checkpoint_path(job_id)


def _load_google_scheduler_checkpoint(job_id: str) -> Dict[str, Any]:
    try:
        return _get_google_dispatcher().load_checkpoint(job_id)
    except Exception as exc:
        logger.warning(f"Google scheduler checkpoint load failed: {exc}")
    return {}


def _save_google_scheduler_checkpoint(job_id: str, payload: Dict[str, Any]) -> Path:
    try:
        return _get_google_dispatcher().save_checkpoint(job_id, payload)
    except Exception as exc:
        logger.warning(f"Google scheduler checkpoint save failed: {exc}")
    return _google_scheduler_checkpoint_path(job_id)


def _save_google_scheduler_status(
    *,
    next_request_ts: float,
    reason: str,
    status: str,
    job_id: str = '',
    target_lang: str = '',
    source_lang: str = '',
    completed_units: int = 0,
    total_units: int = 0,
    current_unit: str = '',
    checkpoint_path: str = '',
) -> None:
    _get_google_dispatcher().save_scheduler_status(
        next_request_ts=next_request_ts,
        reason=reason,
        status=status,
        job_id=job_id,
        target_lang=target_lang,
        source_lang=source_lang,
        completed_units=completed_units,
        total_units=total_units,
        current_unit=current_unit,
        checkpoint_path=checkpoint_path,
    )


def _wait_for_google_slot(*, context: str, remaining_units: int = 0) -> Dict[str, float]:
    import time as _time
    global _GOOGLE_NEXT_REQUEST_TS

    dispatcher = _get_google_dispatcher()
    dispatcher.next_request_ts = _GOOGLE_NEXT_REQUEST_TS
    reservation = dispatcher.reserve_slot(remaining_units=remaining_units)
    _GOOGLE_NEXT_REQUEST_TS = dispatcher.next_request_ts
    wait = reservation['wait_seconds']
    if wait > _GOOGLE_MAX_BLOCKING_WAIT_SECONDS:
        logger.warning(
            "Google scheduler deferring %s because shared cooldown requires %.1fs wait",
            context,
            wait,
        )
        raise TranslationDeferredError(
            f"Google scheduler cooldown active for {wait:.1f}s",
            wait_seconds=wait,
            reason_code='google_rate_limit',
        )
    if wait > 0:
        logger.info(
            "Google scheduler waiting %.1fs before %s (remaining_units=%s)",
            wait,
            context,
            remaining_units,
        )
        _record_google_metric('google_scheduler_wait_seconds', wait)
        _time.sleep(wait)
    return reservation


class TranslationQualityError(RuntimeError):
    """Raised when a translation run fails strict quality gates."""

    def __init__(self, message: str, issues: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.issues = issues or []


class TranslationDeferredError(RuntimeError):
    """Raised when translation should be retried later instead of blocking."""

    def __init__(self, message: str, *, wait_seconds: float, reason_code: str):
        super().__init__(message)
        self.wait_seconds = float(wait_seconds)
        self.reason_code = reason_code


_TRANSLATION_ISSUES: List[Dict[str, Any]] = []


def _reset_translation_issues() -> None:
    _TRANSLATION_ISSUES.clear()


def _record_translation_issue(
    code: str,
    message: str,
    *,
    context: str = '',
    target_lang: str = '',
    snippet: str = '',
    retryable: bool = False,
) -> None:
    _TRANSLATION_ISSUES.append({
        'code': code,
        'message': message,
        'context': context,
        'target_lang': target_lang,
        'snippet': snippet[:160],
        'retryable': retryable,
    })


def _get_translation_issues() -> List[Dict[str, Any]]:
    return [dict(item) for item in _TRANSLATION_ISSUES]


def _format_translation_issues(issues: List[Dict[str, Any]]) -> str:
    if not issues:
        return "No translation issues recorded."

    lines = []
    for issue in issues:
        detail = issue['message']
        if issue.get('context'):
            detail += f" [context={issue['context']}]"
        if issue.get('snippet'):
            detail += f" :: {issue['snippet']}"
        lines.append(f"- {detail}")
    return '\n'.join(lines)


def _get_blocking_translation_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter informational issues that should not fail strict mode."""
    return [issue for issue in issues if issue.get('code') not in {'fallback_used'}]


def _detect_source_lang(input_path: str) -> str:
    """Infer the source language from frontmatter first, then filename suffix."""
    source_lang = 'en'
    try:
        frontmatter, _ = parse_md_file(input_path)
    except Exception:
        frontmatter = {}

    detected = frontmatter.get('lang')
    if detected in LANGUAGES:
        return detected

    match = re.search(r'_(en|ko)\.md$', os.path.basename(input_path))
    if match:
        return match.group(1)
    return source_lang


def _resolve_all_target_languages(input_path: str, languages: Optional[List[str]] = None) -> List[str]:
    """Resolve the operational translation targets for the detected source language."""
    source_lang = _detect_source_lang(input_path)
    candidates = list(languages) if languages is not None else list(TRANSLATION_LANGUAGES)
    return [lang for lang in candidates if lang != source_lang]

LANG_NAMES = LANGUAGE_NAMES

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
      'math_fence'— $$ delimiter line (preserve)
      'math_line' — inside $$...$$ block (preserve)
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
    in_math_block = False

    for line in lines:
        stripped = line.strip()

        # Math block ($$) toggle — must check before code fence
        if stripped == '$$' and not in_code_block:
            in_math_block = not in_math_block
            classified.append(('math_fence', line))
            continue

        if in_math_block:
            classified.append(('math_line', line))
            continue

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


# ── Google Translate HTTP backend ──────────────────────────────────

# Language code mapping: our codes → Google Translate codes
_GOOGLE_LANG_MAP = {
    'en': 'en', 'ko': 'ko', 'ja': 'ja', 'zh': 'zh-CN',
    'fr': 'fr', 'es': 'es', 'de': 'de',
}

_LIBRETRANSLATE_LANG_MAP = {
    'en': 'en', 'ko': 'ko', 'ja': 'ja', 'zh': 'zh',
    'fr': 'fr', 'es': 'es', 'de': 'de',
}

_GOOGLE_CLOUD_LANG_MAP = dict(_GOOGLE_LANG_MAP)

# Token symbols and math notation to preserve during Google Translate
# These get replaced with placeholders before translation and restored after
_PRESERVE_TOKENS = [
    # Long multi-char tokens first (order matters for replacement)
    'T_finality', 'δ_prop', 't_signal', 'E[r_v]', 'C_vote', 'S_min', 'C_op',
    'V ∝ R/S', 'f* = (p·b - q) / b', 'CR = 담보 자산 가치 / 발행 부채',
    # Greek letters
    'μ', 'σ', 'ρ', 'α', 'β', 'γ', 'δ', 'ε', 'λ', 'π', 'Σ',
    # Common token symbols (uppercase, 2-6 chars)
    'ELSA', 'USDC', 'USDT', 'WBTC', 'WETH', 'stETH',
    'SOL', 'ETH', 'BTC', 'ENJ', 'LEO', 'MYX', 'XPL', 'DEGEN',
    'AVAX', 'MATIC', 'LINK', 'UNI', 'AAVE', 'CRO', 'DOT', 'ADA',
    'ATOM', 'NEAR', 'APT', 'SUI', 'ARB', 'OP', 'FTM', 'HBAR',
    'XRP', 'XLM', 'ALGO', 'ICP', 'FIL', 'LDO', 'MKR', 'SNX',
    'COMP', 'YFI', 'SUSHI', 'TRUMP', 'NIGHT', 'SKYAI', 'RAVE',
    'STABLE', 'USDG', 'PYUSD', 'XAUt', 'PAXG',
    # Math notation
    'f*', 'w_i', 'NC', 'CR', 's_i',
]


_KO_DATE_RE = re.compile(
    r'(\d{1,2})월\s*(\d{1,2}),?\s*(\d{4})년?에?\s*액세스'
)
_KO_DATE_ACCESSED_RE = re.compile(
    r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일에?\s*액세스'
)

_MONTH_NAMES = {
    'en': ['January','February','March','April','May','June','July','August','September','October','November','December'],
    'fr': ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre'],
    'es': ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'],
    'de': ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'],
    'ja': ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
    'zh': ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'],
}

_ACCESSED_WORD = {
    'en': 'Accessed', 'fr': 'Consulté le', 'es': 'Consultado el',
    'de': 'Abgerufen am', 'ja': 'アクセス日', 'zh': '访问日期',
}

_COMMON_KO_RESIDUE_MAP = {
    'ja': {
        '서론': '序論',
        '핵심 목표': 'コア目標',
        '목표 항목': '目標項目',
        '평가 항목': '評価項目',
        '평가 시점': '評価時点',
        '데이터 유형': 'データ型',
        '구성 요소': '構成要素',
        '구성 요소 예시': '構成要素の例',
        '상세 내용 및 전략적 가치': '詳細と戦略的価値',
        '세부 내용': '詳細内容',
        '세부 추진 내용': '詳細推進内容',
        '포함 요소': '包含要素',
        '관련 비고': '関連備考',
        '주요 수치 및 지표': '主要数値・指標',
        '출처': '出典',
        '가중치 반영 점수': '重み反映スコア',
        '가중치 적용 점수': '重み適用スコア',
        '가중 달성률': '加重達成率',
        '현재 달성률': '現在達成率',
        '현 시점 달성률': '現時点達成率',
        '요소별 달성률': '要素別達成率',
        '달성률': '達成率',
        '달성도': '達成度',
        '달성 여부': '達成可否',
        '합계': '合計',
        '상호운용성': '相互運用性',
        '가중치': '重み',
        '비중': '比重',
        '구분': '区分',
        '수치': '数値',
        '온체인': 'オンチェーン',
        '오프체인': 'オフチェーン',
        '제도권': '制度圏',
        '기관': '機関',
        '탈중앙화 거버넌스': '分散型ガバナンス',
        '거버넌스': 'ガバナンス',
        '시기': '時期',
        '시장 가격': '市場価格',
        '블록 시간': 'ブロック時間',
        '초당 트랜잭션': '秒間トランザクション',
        '유통 공급량': '流通供給量',
        '기관 보유량': '機関保有量',
        '주요 하드포크': '主要ハードフォーク',
        '현재 시점': '現時点',
        '주요 활용도': '主要活用度',
        '실시간 결제': 'リアルタイム決済',
        '전송 효율화': '転送効率化',
        '에이전트': 'エージェント',
        '머신': 'マシン',
        '경제': '経済',
        '확장': '拡張',
        '리텐션': 'リテンション',
        '실물 자산': '実物資産',
        '실물 경제': '実体経済',
        '자본 효율성 증대': '資本効率性向上',
        '표준 도입': '標準導入',
        '유동화 지원': '流動化支援',
        '브릿지 활성화': 'ブリッジ活性化',
        '자격 증명': '資格証明',
        '허가형 도메인': '許可型ドメイン',
        '제도권 통합': '制度圏統合',
        '투표 중': '投票中',
        '활성': '有効',
        '머신 이코노미': 'マシンエコノミー',
        '연도': '年',
        '최초 출시': '初回ローンチ',
        '런칭': 'ローンチ',
        '표준 제시': '標準提示',
        '경제 본격화': '経済本格化',
        '아크 메인넷': 'アークメインネット',
        '재무 지표': '財務指標',
        '수치': '数値',
        '조정': '調整',
        '마진': 'マージン',
        '주당 순이익': '1株当たり利益',
        '유통비용 차감 후 매출 마진': '流通費用控除後売上マージン',
        '차감 후': '控除後',
        '매출 마진': '売上マージン',
        '에 액세스': 'アクセス日',
        '에이스': 'アクセス日',
        '4월': '4月',
        '발행:': '発行:',
        '액세스': 'アクセス日',
        '발행': '発行',
        '및': 'および',
    },
    'en': {
        '상호운용성': 'interoperability',
        '전송 효율화': 'transfer optimization',
        '에이전트': 'agent',
        '머신': 'machine',
        '경제': 'economy',
        '확장': 'expansion',
        '머신 이코노미': 'machine economy',
        '연도': 'year',
        '최초 출시': 'initial launch',
        '런칭': 'launch',
        '표준 제시': 'standardization',
        '경제 본격화': 'economic expansion',
        '아크 메인넷': 'Arc mainnet',
        '재무 지표': 'financial metrics',
        '수치': 'value',
        '조정': 'adjusted',
        '마진': 'margin',
        '주당 순이익': 'earnings per share',
        '유통비용 차감 후 매출 마진': 'revenue margin net of distribution costs',
        '차감 후': 'net of',
        '매출 마진': 'revenue margin',
        '액세스': 'Accessed',
        '발행': 'Published',
        '및': 'and',
    },
    'de': {
        '상호운용성': 'Interoperabilität',
        '전송 효율화': 'Transferoptimierung',
        '에이전트': 'Agent',
        '머신': 'Maschine',
        '경제': 'Wirtschaft',
        '확장': 'Erweiterung',
        '머신 이코노미': 'Maschinenökonomie',
        '연도': 'Jahr',
        '최초 출시': 'Erststart',
        '런칭': 'Start',
        '표준 제시': 'Standardsetzung',
        '경제 본격화': 'Wirtschaftsausweitung',
        '아크 메인넷': 'Arc-Mainnet',
        '재무 지표': 'Finanzkennzahlen',
        '수치': 'Wert',
        '조정': 'bereinigt',
        '마진': 'Marge',
        '주당 순이익': 'Gewinn je Aktie',
        '유통비용 차감 후 매출 마진': 'Umsatzmarge nach Vertriebskosten',
        '차감 후': 'nach Abzug',
        '매출 마진': 'Umsatzmarge',
        '액세스': 'Abgerufen am',
        '발행': 'Veröffentlicht',
        '및': 'und',
    },
    'fr': {
        '상호운용성': 'interopérabilité',
        '전송 효율화': 'optimisation des transferts',
        '에이전트': 'agent',
        '머신': 'machine',
        '경제': 'économie',
        '확장': 'expansion',
        '머신 이코노미': 'économie des machines',
        '연도': 'année',
        '최초 출시': 'lancement initial',
        '런칭': 'lancement',
        '표준 제시': 'normalisation',
        '경제 본격화': 'essor économique',
        '아크 메인넷': 'mainnet Arc',
        '재무 지표': 'indicateurs financiers',
        '수치': 'valeur',
        '조정': 'ajusté',
        '마진': 'marge',
        '주당 순이익': 'bénéfice par action',
        '유통비용 차감 후 매출 마진': 'marge de revenus après coûts de distribution',
        '차감 후': 'après déduction',
        '매출 마진': 'marge de revenus',
        '액세스': 'Consulté le',
        '발행': 'Publié',
        '및': 'et',
    },
}

_KO_SOURCE_NORMALIZATION_MAP = {
    'Concept 디파이nition': 'Concept Definition',
    'Concept 디파이nitions': 'Concept Definitions',
    '토큰ization': 'tokenization',
    '스마트 컨트랙트s': '스마트 컨트랙트',
    '프로토콜 want to provide': '프로토콜이 제공하려는',
    "The user 자신의": '사용자 자신의',
    "Don't sell 않고도": '매도하지 않고도',
    '이 in the process occurring': '이 과정에서 발생하는',
    'The risk is 거버넌스 To the participants 의해 분산 managed': '리스크는 거버넌스 참여자들에 의해 분산 관리된다',
    "to anyone fair and 투명한 금융 of the system 구축": '누구에게나 공정하고 투명한 금융 시스템 구축',
    "Bitcoin's 단일 가치 저장 수단을 넘어선 'programming 가능한 통화 정책'을 make it happen": "비트코인의 단일 가치 저장 수단을 넘어선 '프로그래밍 가능한 통화 정책'을 구현",
    'To stablecoins 대한': '스테이블코인에 대한',
    'real assets(RWA) 연계': '실물자산(RWA) 연계',
    'endgame in steps essential 역할을 하는': '엔드게임 단계에서 핵심 역할을 하는',
    'off-chain 계약을 통해 현실 세계의 자산': '오프체인 계약을 통해 현실 세계 자산',
    'of the system 담보로 use.': '시스템 담보로 활용한다.',
    'off-chain 자산의 상태는 regular 감사와 법적 문서를 통해 It is on-chain, 이는': '오프체인 자산 상태는 정기 감사와 법적 문서를 통해 검증되며, 이는',
    "'스카이 agent'들에 의해 is monitored.": "'스카이 에이전트'에 의해 모니터링된다.",
}


def _normalize_korean_dates(text: str, target_lang: str) -> str:
    """Convert Korean date expressions (e.g. '4월 16, 2026에 액세스') to target language."""
    if target_lang == 'ko':
        return text

    def _replace_date(m):
        month_num = int(m.group(1))
        day = m.group(2)
        year = m.group(3)
        months = _MONTH_NAMES.get(target_lang, _MONTH_NAMES['en'])
        accessed = _ACCESSED_WORD.get(target_lang, 'Accessed')
        month_name = months[month_num - 1] if 1 <= month_num <= 12 else str(month_num)
        if target_lang in ('ja', 'zh'):
            return f"{year}年{month_name}{day}日 {accessed}"
        return f"{accessed} {month_name} {day}, {year}"

    def _replace_date_ymd(m):
        year = m.group(1)
        month_num = int(m.group(2))
        day = m.group(3)
        months = _MONTH_NAMES.get(target_lang, _MONTH_NAMES['en'])
        accessed = _ACCESSED_WORD.get(target_lang, 'Accessed')
        month_name = months[month_num - 1] if 1 <= month_num <= 12 else str(month_num)
        if target_lang in ('ja', 'zh'):
            return f"{year}年{month_name}{day}日 {accessed}"
        return f"{accessed} {month_name} {day}, {year}"

    text = _KO_DATE_RE.sub(_replace_date, text)
    text = _KO_DATE_ACCESSED_RE.sub(_replace_date_ymd, text)
    return text


def _normalize_common_korean_residue(text: str, target_lang: str) -> str:
    if target_lang == 'ko':
        return text

    replacements = _COMMON_KO_RESIDUE_MAP.get(target_lang, {})
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, target)
    return text


def _normalize_source_markdown(text: str, source_lang: str) -> str:
    """
    Clean up known KO master export artifacts before translation.

    This keeps the strict path focused on translation quality instead of
    re-failing on malformed mixed-language source strings copied from GDocs.
    """
    if source_lang != 'ko' or not text:
        return text

    normalized = text

    for source, target in _KO_SOURCE_NORMALIZATION_MAP.items():
        normalized = normalized.replace(source, target)

    # Bold table/header labels sometimes arrive as "** label **".
    normalized = re.sub(r'\*\*\s+([^*\n][^*\n]*?)\s+\*\*', r'**\1**', normalized)
    # Trim accidental double spaces around markdown separators without
    # disturbing code or table pipes.
    normalized = re.sub(r'(?<=\S) {2,}(?=\S)', ' ', normalized)

    return normalized


def _protect_tokens(text: str) -> tuple:
    """Replace token symbols and inline math with numbered placeholders before translation."""
    protected = text
    mapping = {}
    counter = 0

    # Protect inline $...$ and $$...$$ math expressions first
    def _protect_math(m):
        nonlocal counter
        placeholder = f'⟦TK{counter}⟧'
        mapping[placeholder] = m.group(0)
        counter += 1
        return placeholder
    protected = re.sub(r'\$\$[\s\S]*?\$\$', _protect_math, protected)
    protected = re.sub(r'\$[^\n$]+?\$', _protect_math, protected)

    for token in _PRESERVE_TOKENS:
        if token in protected:
            placeholder = f'⟦TK{counter}⟧'
            protected = protected.replace(token, placeholder)
            mapping[placeholder] = token
            counter += 1
    return protected, mapping


def _restore_tokens(text: str, mapping: dict) -> str:
    """Restore token symbols from placeholders after translation."""
    restored = text
    for placeholder, token in mapping.items():
        # Google Translate sometimes adds spaces around placeholders
        # or changes bracket characters
        import re as _re
        # Try exact match first
        if placeholder in restored:
            restored = restored.replace(placeholder, token)
        else:
            # Fuzzy: spaces around brackets, different bracket chars
            esc = _re.escape(placeholder).replace('⟦', '[⟦\\[]').replace('⟧', '[⟧\\]]')
            restored = _re.sub(r'\s*' + esc + r'\s*', token, restored)
    return restored


def _get_google_cloud_translate_settings() -> Dict[str, str]:
    project_id = (
        os.environ.get('GOOGLE_CLOUD_TRANSLATE_PROJECT_ID', '').strip()
        or os.environ.get('GOOGLE_CLOUD_PROJECT', '').strip()
        or os.environ.get('GOOGLE_PROJECT_ID', '').strip()
        or os.environ.get('GCLOUD_PROJECT', '').strip()
    )
    location = os.environ.get('GOOGLE_CLOUD_TRANSLATE_LOCATION', 'global').strip() or 'global'
    model = os.environ.get('GOOGLE_CLOUD_TRANSLATE_MODEL', '').strip()
    glossary = os.environ.get('GOOGLE_CLOUD_TRANSLATE_GLOSSARY', '').strip()
    credentials_file = (
        os.environ.get('GOOGLE_CLOUD_TRANSLATE_CREDENTIALS_FILE', '').strip()
        or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '').strip()
    )
    return {
        'project_id': project_id,
        'location': location,
        'model': model,
        'glossary': glossary,
        'credentials_file': credentials_file,
    }


def _google_cloud_translate_available() -> bool:
    settings = _get_google_cloud_translate_settings()
    if not settings['project_id']:
        return False
    try:
        from google.cloud import translate_v3  # noqa: F401
    except ImportError:
        return False
    return True


def _get_google_cloud_translate_client():
    global _GOOGLE_CLOUD_CLIENT

    if _GOOGLE_CLOUD_CLIENT is not None:
        return _GOOGLE_CLOUD_CLIENT

    with _GOOGLE_CLOUD_CLIENT_LOCK:
        if _GOOGLE_CLOUD_CLIENT is None:
            from google.cloud import translate_v3

            _GOOGLE_CLOUD_CLIENT = translate_v3.TranslationServiceClient()
    return _GOOGLE_CLOUD_CLIENT


def _google_cloud_parent(project_id: str, location: str) -> str:
    return f"projects/{project_id}/locations/{location}"


def _google_cloud_model_path(project_id: str, location: str, model: str) -> str:
    if not model:
        return ''
    if model.startswith('projects/'):
        return model
    return f"projects/{project_id}/locations/{location}/models/{model}"


def _google_cloud_glossary_path(project_id: str, location: str, glossary: str) -> str:
    if not glossary:
        return ''
    if glossary.startswith('projects/'):
        return glossary
    return f"projects/{project_id}/locations/{location}/glossaries/{glossary}"


def _get_libretranslate_endpoint() -> str:
    base_url = os.environ.get('LIBRETRANSLATE_URL', '').strip()
    if not base_url:
        return ''
    return f"{base_url.rstrip('/')}/translate"


def _translate_libretranslate(
    text: str,
    target_lang: str,
    _ctx: str = '',
    *,
    source_lang: str = 'auto',
    record_errors: bool = True,
) -> str:
    """LibreTranslate backend via a self-hosted /translate endpoint."""
    endpoint = _get_libretranslate_endpoint()
    if not endpoint or not text or not text.strip():
        return text

    payload = {
        'q': text,
        'source': _LIBRETRANSLATE_LANG_MAP.get(source_lang, source_lang) if source_lang != 'auto' else 'auto',
        'target': _LIBRETRANSLATE_LANG_MAP.get(target_lang, target_lang),
        'format': 'text',
    }
    api_key = os.environ.get('LIBRETRANSLATE_API_KEY', '').strip()
    if api_key:
        payload['api_key'] = api_key

    try:
        response = requests.post(endpoint, json=payload, timeout=20)
        response.raise_for_status()
        translated = response.json().get('translatedText')
        if isinstance(translated, str) and translated:
            return translated
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        if record_errors:
            _record_translation_issue(
                'libretranslate_error',
                f"LibreTranslate fallback error: {str(exc)[:100]}",
                context=_ctx,
                target_lang=target_lang,
                snippet=text.strip(),
                retryable=False,
            )
    return text


def _attempt_google_fallback(
    protected_text: str,
    original_text: str,
    token_map: dict,
    target_lang: str,
    *,
    source_lang: str,
    context: str,
    reason_code: str,
    reason_message: str,
    record_errors: bool,
) -> str:
    """Try LibreTranslate after Google fails; otherwise return the original text."""
    if _get_libretranslate_endpoint():
        fallback_result = _translate_libretranslate(
            protected_text,
            target_lang,
            context,
            source_lang=source_lang,
            record_errors=record_errors,
        )
        if fallback_result and fallback_result != protected_text:
            if record_errors:
                _record_translation_issue(
                    'fallback_used',
                    f"Used LibreTranslate fallback after Google failure: {reason_message}",
                    context=context,
                    target_lang=target_lang,
                    snippet=original_text.strip(),
                    retryable=False,
                )
            return _restore_tokens(fallback_result, token_map)

    if record_errors:
        _record_translation_issue(
            reason_code,
            reason_message,
            context=context,
            target_lang=target_lang,
            snippet=original_text.strip(),
            retryable=reason_code in {'google_timeout', 'google_rate_limit'},
        )
    return original_text


def _translate_google(
    text: str,
    target_lang: str,
    _ctx: str = '',
    *,
    record_errors: bool = True,
    source_lang: str = 'auto',
) -> str:
    """
    Google Cloud Translation Advanced v3 text backend.
    Uses the official client with retry/backoff for rate-limiting and timeouts.
    Token symbols and math notation are protected via placeholder substitution.
    """
    import time as _time
    global _GOOGLE_NEXT_REQUEST_TS, _GOOGLE_STRICT_RATE_LIMITED

    if not text or not text.strip():
        return text
    if _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT and _GOOGLE_STRICT_RATE_LIMITED:
        return text
    # Skip very short or code-like text. Keep short Hangul fragments eligible
    # so residue cleanup can retranslate labels like "자산".
    stripped = text.strip()
    if (
        (len(stripped) <= 3 and not _has_korean(stripped))
        or (stripped.isascii() and stripped.isupper())
        or re.match(r'^[\d.%$,+\-×/()]+$', stripped)
    ):
        return text
    # Skip base64 image data (too long, not translatable)
    if stripped.startswith('[image') and 'data:image' in stripped:
        return text
    if len(stripped) > 25000:
        logger.warning(f"Google Cloud Translation skip: text too long ({len(stripped)} chars)")
        return text

    settings = _get_google_cloud_translate_settings()
    if not settings['project_id']:
        message = "Google Cloud Translation is not configured: missing GOOGLE_CLOUD_TRANSLATE_PROJECT_ID"
        logger.warning(message)
        return _attempt_google_fallback(
            stripped,
            text,
            {},
            target_lang,
            source_lang=source_lang,
            context=_ctx,
            reason_code='google_error',
            reason_message=message,
            record_errors=record_errors,
        )

    try:
        from google.api_core import exceptions as google_exceptions
    except ImportError:
        class _GoogleExceptions:
            class DeadlineExceeded(Exception):
                pass

            class ResourceExhausted(Exception):
                pass

            class TooManyRequests(Exception):
                pass

        google_exceptions = _GoogleExceptions()

    # Protect token symbols before translation
    protected, token_map = _protect_tokens(stripped)

    MAX_RETRIES = 5
    for attempt in range(MAX_RETRIES):
        try:
            gl = _GOOGLE_CLOUD_LANG_MAP.get(target_lang, target_lang)
            source = _GOOGLE_CLOUD_LANG_MAP.get(source_lang, source_lang) if source_lang and source_lang != 'auto' else ''
            _wait_for_google_slot(context=_ctx or 'google_translate', remaining_units=1)
            _record_google_metric('google_request_count', 1)
            parent = _google_cloud_parent(settings['project_id'], settings['location'])
            request = {
                'parent': parent,
                'contents': [protected],
                'mime_type': 'text/plain',
                'target_language_code': gl,
            }
            if source:
                request['source_language_code'] = source
            model_path = _google_cloud_model_path(
                settings['project_id'],
                settings['location'],
                settings['model'],
            )
            if model_path:
                request['model'] = model_path
            glossary_path = _google_cloud_glossary_path(
                settings['project_id'],
                settings['location'],
                settings['glossary'],
            )
            if glossary_path:
                try:
                    from google.cloud import translate_v3
                except ImportError as exc:
                    message = f"Google Cloud Translation client not installed: {exc}"
                    logger.warning(message)
                    return _attempt_google_fallback(
                        protected,
                        text,
                        token_map,
                        target_lang,
                        source_lang=source_lang,
                        context=_ctx,
                        reason_code='google_error',
                        reason_message=message,
                        record_errors=record_errors,
                    )
                request['glossary_config'] = translate_v3.TranslateTextGlossaryConfig(glossary=glossary_path)

            response = _get_google_cloud_translate_client().translate_text(
                request=request,
                timeout=20,
            )
            translations = list(getattr(response, 'glossary_translations', []) or [])
            if not translations:
                translations = list(getattr(response, 'translations', []) or [])
            result = ''.join(
                translation.translated_text
                for translation in translations
                if getattr(translation, 'translated_text', None)
            )
            if result:
                return _restore_tokens(result, token_map)
            return text
        except TranslationDeferredError as e:
            _record_google_metric('google_cooldown_seconds', e.wait_seconds)
            logger.warning(str(e))
            return _attempt_google_fallback(
                protected,
                text,
                token_map,
                target_lang,
                source_lang=source_lang,
                context=_ctx,
                reason_code=e.reason_code,
                    reason_message=str(e),
                    record_errors=record_errors,
                )
        except (google_exceptions.DeadlineExceeded, TimeoutError):
            if attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 5  # 5s, 10s
                logger.warning(f"Google Cloud Translation timeout retry {attempt+1}, waiting {wait}s")
                _time.sleep(wait)
            else:
                message = "Google Cloud Translation timeout (final)"
                logger.error(message)
                return _attempt_google_fallback(
                    protected,
                    text,
                    token_map,
                    target_lang,
                    source_lang=source_lang,
                    context=_ctx,
                    reason_code='google_timeout',
                    reason_message=message,
                    record_errors=record_errors,
                )
        except Exception as e:
            status_code = getattr(e, 'code', None) or getattr(getattr(e, 'response', None), 'status_code', None)
            is_rate_limited = isinstance(e, (
                google_exceptions.ResourceExhausted,
                google_exceptions.TooManyRequests,
            )) or status_code == 429 or 'Too Many Requests' in str(e)
            if is_rate_limited:
                _record_google_metric('google_429_count', 1)
                if _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT:
                    _GOOGLE_STRICT_RATE_LIMITED = True
            if attempt < MAX_RETRIES - 1:
                if is_rate_limited:
                    wait = max(_GOOGLE_RATE_LIMIT_COOLDOWN_SECONDS, 300 * (attempt + 1))
                    _record_google_metric('google_cooldown_seconds', wait)
                    dispatcher = _get_google_dispatcher()
                    dispatcher.next_request_ts = _GOOGLE_NEXT_REQUEST_TS
                    _GOOGLE_NEXT_REQUEST_TS = dispatcher.apply_rate_limit_cooldown(
                        wait_seconds=wait,
                        now=_time.time(),
                    )
                    message = (
                        f"Google Cloud Translation rate-limit retry {attempt+1}, waiting {wait}s: {str(e)[:100]}"
                    )
                    logger.warning(message)
                    if _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT:
                        return _attempt_google_fallback(
                            protected,
                            text,
                            token_map,
                            target_lang,
                            source_lang=source_lang,
                            context=_ctx,
                            reason_code='google_rate_limit',
                            reason_message=(
                                f"Google Cloud Translation deferred after strict-mode rate limit: {str(e)[:100]}"
                            ),
                            record_errors=record_errors,
                        )
                    if wait > _GOOGLE_MAX_BLOCKING_WAIT_SECONDS:
                        return _attempt_google_fallback(
                            protected,
                            text,
                            token_map,
                            target_lang,
                            source_lang=source_lang,
                            context=_ctx,
                            reason_code='google_rate_limit',
                            reason_message=(
                                f"Google Cloud Translation deferred instead of blocking for {wait}s cooldown: {str(e)[:100]}"
                            ),
                            record_errors=record_errors,
                        )
                else:
                    wait = (attempt + 1) * 3
                    logger.warning(f"Google Cloud Translation retry {attempt+1}: {str(e)[:100]}")
                _time.sleep(wait)
            else:
                reason_code = 'google_rate_limit' if is_rate_limited else 'google_error'
                message = f"Google Cloud Translation error (final): {str(e)[:100]}"
                logger.error(message)
                return _attempt_google_fallback(
                    protected,
                    text,
                    token_map,
                    target_lang,
                    source_lang=source_lang,
                    context=_ctx,
                    reason_code=reason_code,
                    reason_message=message,
                    record_errors=record_errors,
                )
    return text


def _translate_batch_google(
    texts: List[str],
    target_lang: str,
    *,
    source_lang: str = 'auto',
) -> List[str]:
    """
    Batch translate multiple prose lines while preserving stable markers.

    The scheduler is intentionally conservative:
      - document/language work is processed sequentially
      - each batch is capped by both characters and item count
      - progress is checkpointed so interrupted reruns can continue
    """
    if not texts:
        return []
    if _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT and _GOOGLE_STRICT_RATE_LIMITED:
        return list(texts)

    max_batch_chars = _GOOGLE_BATCH_MAX_CHARS
    max_batch_items = max(_GOOGLE_BATCH_MAX_ITEMS, 1)
    translated_map: Dict[int, str] = {}
    started_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    job_id = _build_google_scheduler_job_id(texts, target_lang, source_lang=source_lang)
    checkpoint = _load_google_scheduler_checkpoint(job_id)
    checkpoint_path = str(_google_scheduler_checkpoint_path(job_id))
    if checkpoint.get('job_id') == job_id:
        translated_map.update({
            int(idx): value
            for idx, value in (checkpoint.get('translated_map') or {}).items()
        })

    def _translate_entries(entries: List[Tuple[int, str]]) -> None:
        global _GOOGLE_STRICT_RATE_LIMITED

        combined_lines = [f"[[[{idx}]]] {text}" for idx, text in entries]
        combined_text = '\n'.join(combined_lines)
        translated_text = _translate_google(
            combined_text,
            target_lang,
            _ctx=f'batch_google[{entries[0][0]}:{entries[-1][0]}]',
            record_errors=True,
            source_lang=source_lang,
        )
        if translated_text == combined_text and _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT and _GOOGLE_STRICT_RATE_LIMITED:
            for idx, text in entries:
                translated_map[idx] = text
            return
        if translated_text == combined_text and len(entries) > 1:
            mid = len(entries) // 2
            _translate_entries(entries[:mid])
            _translate_entries(entries[mid:])
            return

        parsed_results = {
            int(match.group(1)): match.group(2).strip()
            for match in re.finditer(
                r'\[\[\[(\d+)\]\]\]\s*(.*?)(?=\n\[\[\[\d+\]\]\]|\Z)',
                translated_text,
                re.DOTALL,
            )
        }

        for idx, text in entries:
            translated = parsed_results.get(idx)
            if translated:
                translated_map[idx] = translated
            elif _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT and _GOOGLE_STRICT_RATE_LIMITED:
                translated_map[idx] = text
            else:
                retry = _translate_google(
                    text,
                    target_lang,
                    _ctx=f'batch_google_fallback[{idx}]',
                    record_errors=False,
                    source_lang=source_lang,
                )
                translated_map[idx] = retry

    throttled = False
    chunk_plan: List[List[Tuple[int, str]]] = []
    pending_batch: List[Tuple[int, str]] = []
    pending_chars = 0
    for idx, text in enumerate(texts):
        stripped = text.strip()
        if not stripped or len(stripped) <= 3:
            translated_map[idx] = text
            continue
        if len(stripped) > _GOOGLE_SINGLE_TEXT_MAX_CHARS:
            if pending_batch:
                chunk_plan.append(pending_batch)
                pending_batch = []
                pending_chars = 0
            chunk_plan.append([(idx, text)])
            continue

        entry_size = len(stripped) + 16
        if pending_batch and (
            pending_chars + entry_size > max_batch_chars
            or len(pending_batch) >= max_batch_items
        ):
            chunk_plan.append(pending_batch)
            pending_batch = []
            pending_chars = 0
        pending_batch.append((idx, stripped))
        pending_chars += entry_size

    if pending_batch:
        chunk_plan.append(pending_batch)

    total_units = len(chunk_plan)
    for chunk_idx, entries in enumerate(chunk_plan, 1):
        if all(idx in translated_map for idx, _ in entries):
            continue

        current_unit = f'chunk {chunk_idx}/{total_units}'
        _save_google_scheduler_status(
            next_request_ts=float(_load_google_rate_limit_state().get('next_request_ts', 0.0) or 0.0),
            reason='scheduler_progress',
            status='running',
            job_id=job_id,
            target_lang=target_lang,
            source_lang=source_lang,
            completed_units=chunk_idx - 1,
            total_units=total_units,
            current_unit=current_unit,
            checkpoint_path=checkpoint_path,
        )
        logger.info(
            "Google scheduler processing %s for %s (%s entries)",
            current_unit,
            target_lang,
            len(entries),
        )
        _translate_entries(entries)
        checkpoint_payload = {
            'job_id': job_id,
            'target_lang': target_lang,
            'source_lang': source_lang,
            'started_at': checkpoint.get('started_at') or started_at,
            'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'total_entries': len(texts),
            'total_units': total_units,
            'completed_units': chunk_idx,
            'translated_map': {str(idx): value for idx, value in translated_map.items()},
        }
        _save_google_scheduler_checkpoint(job_id, checkpoint_payload)
        _save_google_scheduler_status(
            next_request_ts=float(_load_google_rate_limit_state().get('next_request_ts', 0.0) or 0.0),
            reason='scheduler_progress',
            status='running',
            job_id=job_id,
            target_lang=target_lang,
            source_lang=source_lang,
            completed_units=chunk_idx,
            total_units=total_units,
            current_unit=current_unit,
            checkpoint_path=checkpoint_path,
        )
        if _GOOGLE_STRICT_ABORT_ON_RATE_LIMIT and _GOOGLE_STRICT_RATE_LIMITED:
            throttled = True
            logger.warning(
                "Google scheduler stopping remaining batches after rate limit in strict mode"
            )
            break

    if throttled:
        _save_google_scheduler_status(
            next_request_ts=float(_load_google_rate_limit_state().get('next_request_ts', 0.0) or 0.0),
            reason='scheduler_deferred',
            status='deferred',
            job_id=job_id,
            target_lang=target_lang,
            source_lang=source_lang,
            completed_units=chunk_idx,
            total_units=total_units,
            current_unit=current_unit,
            checkpoint_path=checkpoint_path,
        )
    else:
        _save_google_scheduler_status(
            next_request_ts=float(_load_google_rate_limit_state().get('next_request_ts', 0.0) or 0.0),
            reason='scheduler_complete',
            status='complete',
            job_id=job_id,
            target_lang=target_lang,
            source_lang=source_lang,
            completed_units=total_units,
            total_units=total_units,
            current_unit='complete',
            checkpoint_path=checkpoint_path,
        )

    return [translated_map.get(idx, text) for idx, text in enumerate(texts)]


# Backend registry
BACKENDS = {
    'stub': _translate_stub,
    'claude': _translate_claude,
    'google_cloud': _translate_google,
    'google': _translate_google,
    'libretranslate': _translate_libretranslate,
}


def resolve_backend(backend: str = 'auto') -> str:
    """Resolve the requested backend to the concrete runtime backend name."""
    if backend == 'auto':
        if _google_cloud_translate_available():
            return 'google_cloud'
        if os.environ.get('ANTHROPIC_API_KEY'):
            return 'claude'
        return 'stub'
    if backend == 'google':
        return 'google_cloud'
    return backend if backend in BACKENDS else 'stub'


def get_translate_fn(backend: str = 'auto'):
    """Get translation function. 'auto' prefers Google Cloud → Claude → stub."""
    return BACKENDS[resolve_backend(backend)]


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

def translate_body(
    body: str,
    target_lang: str,
    translate_fn,
    batch: bool = True,
    *,
    backend_name: str = '',
) -> str:
    """
    Translate markdown body while preserving structure.
    Uses batch mode when possible for efficiency.
    """
    classified = classify_body_lines(body)

    if batch and translate_fn == _translate_claude:
        return _translate_body_batch(
            classified,
            target_lang,
            batch_translate_fn=_translate_batch_claude,
            line_translate_fn=translate_fn,
        )
    if batch and backend_name in {'google', 'google_cloud'} and _is_google_translate_fn(translate_fn):
        return _translate_body_batch(
            classified,
            target_lang,
            batch_translate_fn=lambda texts, lang: _translate_batch_google(
                texts,
                lang,
                source_lang=_detect_source_lang_from_callable(translate_fn),
            ),
            line_translate_fn=translate_fn,
        )

    translated_lines = []
    for line_type, line in classified:
        translated_lines.append(_translate_line(line_type, line, target_lang, translate_fn))

    return '\n'.join(translated_lines)


def _detect_source_lang_from_callable(translate_fn) -> str:
    return getattr(translate_fn, '_paperclip_source_lang', 'auto')


def _is_google_translate_fn(translate_fn) -> bool:
    return translate_fn == _translate_google or getattr(translate_fn, '_paperclip_google', False)


def _translate_line(line_type: str, line: str, target_lang: str, translate_fn) -> str:
    """Translate a single classified line."""

    if line_type in ('code_fence', 'code_line', 'math_fence', 'math_line', 'table_sep', 'empty', 'html'):
        return line  # preserve as-is

    if line_type == 'header':
        match = re.match(r'^(#{1,6}\s+)(.*)', line)
        if match:
            prefix, text = match.groups()
            # Strip bold markup before translating, restore after
            bold_wrap = False
            inner = text
            if re.match(r'^\*\*.*\*\*$', text.strip()):
                bold_wrap = True
                inner = text.strip()[2:-2]
            chapter_match = re.match(r'^(Chapter\s+\d+[.:]\s*)(.*)', inner)
            if chapter_match:
                ch_prefix, ch_text = chapter_match.groups()
                translated = f"{translate_fn(ch_prefix, target_lang)}{translate_fn(ch_text, target_lang)}"
            else:
                translated = translate_fn(inner, target_lang)
            if bold_wrap:
                translated = f"**{translated}**"
            return f"{prefix}{translated}"
        return line

    if line_type == 'table_row':
        cells = line.split('|')
        translated_cells = []
        retry_candidates: List[Tuple[int, str, int]] = []
        fallback_fn = translate_fn if _is_google_translate_fn(translate_fn) else _translate_google
        if not _is_google_translate_fn(translate_fn) and os.environ.get('ANTHROPIC_API_KEY'):
            fallback_fn = _translate_claude

        for idx, cell in enumerate(cells):
            stripped = cell.strip()
            if not stripped:
                translated_cells.append(cell)
            elif re.match(r'^[\d.,\-$%+×/()EHMBLNTPS:]+$', stripped):
                translated_cells.append(cell)
            elif stripped in ('PASS', 'FAIL', 'WARN', 'GAP', 'N/A', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'):
                translated_cells.append(cell)
            else:
                padding = len(cell) - len(cell.lstrip())
                translated = translate_fn(stripped, target_lang)
                translated = translated.replace('\n', ' ').replace('|', ' ').replace('\uff5c', ' ').strip()
                if not translated:
                    translated = stripped
                if target_lang != 'ko' and _has_korean(translated):
                    retry_candidates.append((idx, stripped, padding))
                translated_cells.append({'padding': padding, 'text': translated})

        if retry_candidates and target_lang != 'ko':
            for _idx, stripped, _padding in retry_candidates:
                logger.warning(f"Korean residue in table cell, retrying: {stripped[:60]}")

            if _is_google_translate_fn(fallback_fn):
                batched_retries = _translate_batch_google(
                    [stripped for _, stripped, _ in retry_candidates],
                    target_lang,
                    source_lang=_detect_source_lang_from_callable(translate_fn),
                )
            else:
                batched_retries = [fallback_fn(stripped, target_lang) for _, stripped, _ in retry_candidates]

            for (idx, stripped, _padding), retry in zip(retry_candidates, batched_retries):
                cleaned_retry = retry.replace('\n', ' ').replace('|', ' ').replace('\uff5c', ' ').strip()
                if cleaned_retry and not _has_korean(cleaned_retry):
                    translated_cells[idx]['text'] = cleaned_retry
                elif not translated_cells[idx]['text']:
                    translated_cells[idx]['text'] = stripped

        rendered_cells = []
        for cell in translated_cells:
            if isinstance(cell, str):
                rendered_cells.append(cell)
                continue
            translated = cell['text']
            padding = cell['padding']
            if target_lang != 'ko' and _has_korean(translated):
                translated = _retranslate_korean_residue(translated, target_lang, fallback_fn).strip()
            if target_lang != 'ko' and _has_korean(translated):
                translated = _normalize_common_korean_residue(translated, target_lang).strip()
            rendered_cells.append(' ' * padding + translated + ' ')
        return '|'.join(rendered_cells)

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


def _extract_batchable_line_payload(line_type: str, line: str) -> Optional[Dict[str, Any]]:
    """Extract translatable content from a markdown line when it is safe to batch."""
    if line_type == 'text':
        stripped = line.strip()
        if not stripped or len(stripped) <= 3:
            return None
        indent = len(line) - len(line.lstrip())
        return {
            'line_type': line_type,
            'text': stripped,
            'prefix': ' ' * indent,
            'bold_wrap': False,
        }

    if line_type == 'list_item':
        match = re.match(r'^(\s*(?:[-*+]|\d+\.)\s+)(.*)', line)
        if not match:
            return None
        prefix, text = match.groups()
        stripped = text.strip()
        if not stripped or len(stripped) <= 3:
            return None
        return {
            'line_type': line_type,
            'text': stripped,
            'prefix': prefix,
            'bold_wrap': False,
        }

    if line_type == 'blockquote':
        match = re.match(r'^(>\s*)(.*)', line)
        if not match:
            return None
        prefix, text = match.groups()
        stripped = text.strip()
        if not stripped or len(stripped) <= 3:
            return None
        return {
            'line_type': line_type,
            'text': stripped,
            'prefix': prefix,
            'bold_wrap': False,
        }

    if line_type == 'header':
        match = re.match(r'^(#{1,6}\s+)(.*)', line)
        if not match:
            return None
        prefix, text = match.groups()
        stripped = text.strip()
        if not stripped:
            return None

        bold_wrap = False
        inner = stripped
        if re.match(r'^\*\*.*\*\*$', stripped):
            bold_wrap = True
            inner = stripped[2:-2].strip()

        if re.match(r'^(Chapter\s+\d+[.:]\s*)(.*)', inner):
            return None
        if len(inner) <= 3:
            return None

        return {
            'line_type': line_type,
            'text': inner,
            'prefix': prefix,
            'bold_wrap': bold_wrap,
        }

    return None


def _reconstruct_batchable_line(payload: Dict[str, Any], translated: str) -> str:
    translated_text = translated
    if payload.get('bold_wrap'):
        translated_text = f"**{translated_text}**"
    return f"{payload['prefix']}{translated_text}"


def _translate_body_batch(
    classified: List[Tuple[str, str]],
    target_lang: str,
    *,
    batch_translate_fn,
    line_translate_fn,
) -> str:
    """Batch-translate prose lines while preserving markdown structure."""
    # Collect translatable texts, including safe structured lines, so the
    # Google scheduler does not have to wait on each markdown item separately.
    to_translate = []
    payloads: Dict[int, Dict[str, Any]] = {}

    for i, (line_type, line) in enumerate(classified):
        payload = _extract_batchable_line_payload(line_type, line)
        if payload is None:
            continue
        to_translate.append(payload['text'])
        payloads[i] = payload

    if not to_translate:
        return '\n'.join(line for _, line in classified)

    translated = batch_translate_fn(to_translate, target_lang)

    # Rebuild lines
    result_lines = []
    trans_map = dict(zip(payloads.keys(), translated))

    for i, (line_type, line) in enumerate(classified):
        if i in trans_map:
            result_lines.append(_reconstruct_batchable_line(payloads[i], trans_map[i]))
        elif line_type in ('header', 'list_item', 'blockquote', 'text'):
            result_lines.append(_translate_line(line_type, line, target_lang, line_translate_fn))
        elif line_type in ('code_fence', 'code_line', 'math_fence', 'math_line', 'table_sep', 'empty', 'html'):
            result_lines.append(line)
        elif line_type == 'table_row':
            # Table rows stay per-cell to preserve column structure.
            result_lines.append(_translate_line(line_type, line, target_lang, line_translate_fn))
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
# KOREAN RESIDUE DETECTION — QA guard for non-Korean translations
# ============================================================================

_HANGUL_RE = re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F]')
_HANGUL_WORD_RE = re.compile(r'[\uAC00-\uD7AF]+')


def _has_korean(text: str) -> bool:
    """Return True if *text* contains Korean (Hangul) characters."""
    return bool(_HANGUL_RE.search(text))


def _korean_ratio(text: str) -> float:
    """Fraction of non-whitespace characters that are Hangul."""
    non_ws = re.sub(r'\s', '', text)
    if not non_ws:
        return 0.0
    hangul_chars = _HANGUL_RE.findall(non_ws)
    return len(hangul_chars) / len(non_ws)


def _retranslate_korean_residue(text: str, target_lang: str, translate_fn) -> str:
    """
    If *text* still contains Korean after translation to a non-Korean language,
    extract the Korean fragments and re-translate them individually.
    """
    if target_lang == 'ko' or not _has_korean(text):
        return text

    lines = text.split('\n')
    residue_indices = [idx for idx, line in enumerate(lines) if _has_korean(line)]
    if residue_indices and _is_google_translate_fn(translate_fn):
        residue_lines = [lines[idx] for idx in residue_indices]
        retranslations = _translate_batch_google(
            residue_lines,
            target_lang,
            source_lang=_detect_source_lang_from_callable(translate_fn),
        )
        for idx, translated in zip(residue_indices, retranslations):
            if translated and not _has_korean(translated):
                lines[idx] = translated
        text = '\n'.join(lines)
        if not _has_korean(text):
            return text

    fragment_matches = list(_HANGUL_WORD_RE.finditer(text))
    if fragment_matches and _is_google_translate_fn(translate_fn):
        seen_fragments = []
        for match in fragment_matches:
            fragment = match.group(0)
            if fragment not in seen_fragments:
                seen_fragments.append(fragment)

        fragment_translations = _translate_batch_google(
            seen_fragments,
            target_lang,
            source_lang='ko',
        )
        fragment_map = {
            fragment: translated
            for fragment, translated in zip(seen_fragments, fragment_translations)
            if translated and not _has_korean(translated)
        }
        if fragment_map:
            text = _HANGUL_WORD_RE.sub(lambda m: fragment_map.get(m.group(0), m.group(0)), text)
            if not _has_korean(text):
                return text

    def _replace_korean_span(m):
        fragment = m.group(0)
        retranslated = translate_fn(fragment, target_lang)
        if _has_korean(retranslated):
            return retranslated
        return retranslated

    result = _HANGUL_WORD_RE.sub(_replace_korean_span, text)
    return result


def qa_check_korean_residue(text: str, target_lang: str, source_path: str = '') -> List[dict]:
    """
    Scan translated text for Korean residue. Returns list of findings.
    Each finding: {'line': int, 'content': str, 'ratio': float}
    """
    if target_lang == 'ko':
        return []

    findings = []
    for i, line in enumerate(text.split('\n'), 1):
        if _has_korean(line):
            ratio = _korean_ratio(line)
            findings.append({
                'line': i,
                'content': line.strip()[:120],
                'ratio': round(ratio, 3),
            })
    if findings:
        logger.warning(
            f"Korean residue in {target_lang} translation ({source_path}): "
            f"{len(findings)} lines with Hangul"
        )
    return findings


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
    strict: bool = False,
) -> Tuple[str, dict]:
    """
    Translate a .md report file to target language.

    Args:
        input_path: Path to source .md file (EN master)
        target_lang: Target language code (ko, fr, es, de, ja, zh)
        output_dir: Output directory (default: same as input)
        backend: Translation backend ('auto' resolves Google Cloud -> Claude -> stub)
        apply_gloss: Apply glossary post-processing
        strict: Fail fast when translation backend/quality checks detect issues

    Returns:
        (output_path, metadata_dict)
    """
    input_path = str(input_path)
    start_time = time.monotonic()
    logger.info(f"Translating {input_path} → {target_lang}")
    _reset_translation_issues()
    _reset_google_metrics()

    # Parse source .md
    fm, body = parse_md_file(input_path)
    source_lang = _detect_source_lang(input_path)
    body = _normalize_source_markdown(body, source_lang)
    resolved_backend = resolve_backend(backend)
    if strict and resolved_backend == 'stub':
        _record_translation_issue(
            'stub_backend',
            "Strict translation aborted because backend resolved to stub",
            context='backend',
            target_lang=target_lang,
            snippet=os.path.basename(input_path),
            retryable=False,
        )
        issues = _get_translation_issues()
        raise TranslationQualityError(
            f"Strict translation failed for {target_lang}: backend resolved to stub.\n"
            f"{_format_translation_issues(issues)}",
            issues=issues,
        )
    translate_fn = BACKENDS[resolved_backend]
    if resolved_backend in {'google', 'google_cloud'} and translate_fn == _translate_google:
        def _google_translate(text: str, target_lang: str, _ctx: str = '') -> str:
            return _translate_google(
                text,
                target_lang,
                _ctx,
                source_lang=source_lang,
            )

        _google_translate._paperclip_google = True
        _google_translate._paperclip_source_lang = source_lang
        translate_fn = _google_translate

    # Translate frontmatter
    with _google_strict_batch_mode(strict):
        translated_fm = translate_frontmatter(fm, target_lang, translate_fn)

        # Translate body
        translated_body = translate_body(
            body,
            target_lang,
            translate_fn,
            batch=(resolved_backend in {'claude', 'google', 'google_cloud'}),
            backend_name=resolved_backend,
        )

        # Apply glossary
        if apply_gloss:
            translated_body = apply_glossary(translated_body, target_lang)

        # Normalize Korean date expressions before QA
        if target_lang != 'ko':
            translated_body = _normalize_korean_dates(translated_body, target_lang)
            translated_body = _normalize_common_korean_residue(translated_body, target_lang)

        # QA: detect and fix Korean residue in non-Korean translations
        if target_lang != 'ko':
            residue = qa_check_korean_residue(translated_body, target_lang, input_path)
            if residue:
                logger.info(f"Attempting Korean residue cleanup ({len(residue)} lines)...")
                translated_body = _retranslate_korean_residue(
                    translated_body, target_lang, translate_fn
                )
                translated_body = _normalize_common_korean_residue(translated_body, target_lang)
                residue_after = qa_check_korean_residue(translated_body, target_lang, input_path)
                if residue_after:
                    logger.warning(
                        f"Korean residue remains after cleanup: {len(residue_after)} lines "
                        f"(was {len(residue)})"
                    )

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

        # Final QA scan for metadata
        final_residue = qa_check_korean_residue(translated_body, target_lang, input_path) if target_lang != 'ko' else []
        if final_residue:
            _record_translation_issue(
                'korean_residue',
                f"Final translation still contains Hangul on {len(final_residue)} line(s)",
                context='qa_check_korean_residue',
                target_lang=target_lang,
                snippet=final_residue[0].get('content', ''),
                retryable=False,
            )

        translation_issues = _get_translation_issues()
        blocking_issues = _get_blocking_translation_issues(translation_issues)
        fallback_issue = next((issue for issue in translation_issues if issue.get('code') == 'fallback_used'), None)
        cloud_settings = _get_google_cloud_translate_settings()
        cloud_model = None
        cloud_glossary = None
        if resolved_backend in {'google', 'google_cloud'}:
            cloud_model = _google_cloud_model_path(
                cloud_settings['project_id'],
                cloud_settings['location'],
                cloud_settings['model'],
            ) or None
            cloud_glossary = _google_cloud_glossary_path(
                cloud_settings['project_id'],
                cloud_settings['location'],
                cloud_settings['glossary'],
            ) or None

        # Metadata
        meta = {
            'source': input_path,
            'target_lang': target_lang,
            'output': output_path,
            'backend': resolved_backend,
            'backend_requested': backend,
            'glossary_applied': apply_gloss,
            'source_lang': source_lang,
            'translated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'word_count_source': len(body.split()),
            'word_count_target': len(translated_body.split()),
            'korean_residue_lines': len(final_residue),
            'strict': strict,
            'duration_seconds': round(max(time.monotonic() - start_time, 0.0), 3),
            'translation_issue_count': len(translation_issues),
            'translation_issues': translation_issues,
            'fallback_used': fallback_issue is not None,
            'fallback_backend': 'libretranslate' if fallback_issue else None,
            'fallback_reason': fallback_issue.get('message') if fallback_issue else None,
            'google_scheduler_policy': _google_scheduler_policy() if resolved_backend in {'google', 'google_cloud'} else None,
            'google_scheduler_state_path': str(_GOOGLE_RATE_LIMIT_STATE_PATH) if resolved_backend in {'google', 'google_cloud'} else None,
            'google_scheduler_checkpoint_path': (
                str(_load_google_rate_limit_state().get('scheduler', {}).get('checkpoint_path', '')) or None
            ) if resolved_backend in {'google', 'google_cloud'} else None,
            'google_cloud_model': cloud_model,
            'google_cloud_glossary': cloud_glossary,
        }
        if resolved_backend in {'google', 'google_cloud'}:
            meta.update(_snapshot_google_metrics())
        meta['timed_out'] = any(
            issue.get('code') == 'google_timeout' for issue in translation_issues
        )

        if strict and blocking_issues:
            raise TranslationQualityError(
                f"Strict translation failed for {target_lang}.\n"
                f"{_format_translation_issues(blocking_issues)}",
                issues=blocking_issues,
            )

        # Write output only after strict quality gates pass.
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_content)

        logger.info(f"✓ Written: {output_path} ({meta['word_count_target']} words)")
        return output_path, meta


def translate_md_all_languages(
    input_path: str,
    output_dir: str = None,
    backend: str = 'auto',
    languages: List[str] = None,
    strict: bool = False,
) -> Dict[str, Tuple[str, dict]]:
    """
    Translate .md file to all target languages.

    Returns:
        Dict of {lang: (output_path, metadata)}
    """
    if languages is None:
        languages = _resolve_all_target_languages(input_path)
    else:
        source_lang = _detect_source_lang(input_path)
        languages = [lang for lang in languages if lang != source_lang]
    source_lang = _detect_source_lang(input_path)
    languages = _ordered_google_languages(languages, source_lang)

    results = {}
    failed_languages: List[Dict[str, Any]] = []
    for lang in languages:
        started_at = time.monotonic()
        logger.info("translate_md_all_languages start lang=%s input=%s", lang, input_path)
        try:
            path, meta = translate_md_file(
                input_path,
                lang,
                output_dir,
                backend,
                strict=strict,
            )
            results[lang] = (path, meta)
            logger.info(
                "translate_md_all_languages done lang=%s output=%s elapsed=%.3fs timeout=%s issues=%s",
                lang,
                path,
                meta.get('duration_seconds', round(max(time.monotonic() - started_at, 0.0), 3)),
                'yes' if meta.get('timed_out') else 'no',
                meta.get('translation_issue_count', 0),
            )
        except Exception as e:
            elapsed = round(max(time.monotonic() - started_at, 0.0), 3)
            logger.error(
                "translate_md_all_languages failed lang=%s elapsed=%.3fs error=%s",
                lang,
                elapsed,
                e,
            )
            results[lang] = (None, {'error': str(e), 'strict': strict})
            failed_languages.append({
                'code': 'language_failed',
                'message': f"Translation failed for {lang}: {e}",
                'context': 'translate_md_all_languages',
                'target_lang': lang,
                'snippet': str(e).splitlines()[0],
                'retryable': False,
            })

    if strict and failed_languages:
        raise TranslationQualityError(
            "Strict translation failed for one or more languages.\n"
            f"{_format_translation_issues(failed_languages)}",
            issues=failed_languages,
        )

    return results


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description='Translate BCE Lab .md reports')
    parser.add_argument('input', help='Input .md file path')
    parser.add_argument('--lang', default='all',
                        help=f"Target language or 'all' ({', '.join(LANGUAGES)})")
    parser.add_argument('--backend', default='auto',
                        choices=['auto', 'google_cloud', 'google', 'claude', 'stub'],
                        help='Translation backend (auto prefers Google Cloud when available)')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory')
    parser.add_argument('--no-glossary', action='store_true',
                        help='Skip glossary post-processing')
    parser.add_argument('--strict', action='store_true',
                        help='Fail fast on backend fallback, translation backend errors, or Korean residue')

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        return 1

    if args.lang == 'all':
        target_langs = _resolve_all_target_languages(args.input)
        print(f"Translating {args.input} → {len(target_langs)} languages...")
        try:
            results = translate_md_all_languages(
                args.input,
                output_dir=args.output_dir,
                backend=args.backend,
                languages=target_langs,
                strict=args.strict,
            )
        except TranslationQualityError as exc:
            print(f"\n✗ Translation failed: {exc}")
            return 2
        print(f"\n{'='*60}")
        print(f"Translation Results:")
        for lang, (path, meta) in results.items():
            status = '✓' if path else '✗'
            words = meta.get('word_count_target', 0)
            print(f"  {status} [{lang}] {path or 'FAILED'} ({words} words)")
    else:
        try:
            path, meta = translate_md_file(
                args.input,
                target_lang=args.lang,
                output_dir=args.output_dir,
                backend=args.backend,
                apply_gloss=not args.no_glossary,
                strict=args.strict,
            )
        except TranslationQualityError as exc:
            print(f"\n✗ Translation failed: {exc}")
            return 2

        print(f"\n✓ Output: {path}")
        print(f"  Words: {meta['word_count_target']}")
        print(f"  Backend: {meta['backend']}")
        if meta['backend_requested'] != meta['backend']:
            print(f"  Requested backend: {meta['backend_requested']}")
        if meta.get('translation_issue_count'):
            print("  Issues:")
            for issue in meta['translation_issues']:
                print(f"    - {issue['message']}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
