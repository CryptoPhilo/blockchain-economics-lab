#!/usr/bin/env python3
"""
Translation pipeline module for BCE Lab reports.

Handles multi-language report generation with consistent terminology.
Supports 7 languages: English, Korean, French, Spanish, German, Japanese, Chinese.

Usage:
    from translate import translate_all_languages
    translated = translate_all_languages(project_data)
"""

import copy
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# GLOSSARY: BLOCKCHAIN TERMS IN ALL 7 LANGUAGES
# ============================================================================

GLOSSARY = {
    # Core blockchain concepts
    'blockchain': {
        'en': 'blockchain',
        'ko': '블록체인',
        'fr': 'blockchain',
        'es': 'blockchain',
        'de': 'Blockchain',
        'ja': 'ブロックチェーン',
        'zh': '区块链'
    },
    'smart_contract': {
        'en': 'smart contract',
        'ko': '스마트 계약',
        'fr': 'contrat intelligent',
        'es': 'contrato inteligente',
        'de': 'intelligenter Vertrag',
        'ja': 'スマートコントラクト',
        'zh': '智能合约'
    },
    'cryptocurrency': {
        'en': 'cryptocurrency',
        'ko': '암호화폐',
        'fr': 'cryptomonnaie',
        'es': 'criptomoneda',
        'de': 'Kryptowährung',
        'ja': '暗号資産',
        'zh': '加密货币'
    },
    'token': {
        'en': 'token',
        'ko': '토큰',
        'fr': 'jeton',
        'es': 'token',
        'de': 'Token',
        'ja': 'トークン',
        'zh': '代币'
    },
    'consensus': {
        'en': 'consensus',
        'ko': '합의',
        'fr': 'consensus',
        'es': 'consenso',
        'de': 'Konsens',
        'ja': 'コンセンサス',
        'zh': '共识'
    },

    # Economic terms
    'market_capitalization': {
        'en': 'market capitalization',
        'ko': '시가총액',
        'fr': 'capitalisation boursière',
        'es': 'capitalización de mercado',
        'de': 'Marktkapitalisierung',
        'ja': '時価総額',
        'zh': '市值'
    },
    'liquidity': {
        'en': 'liquidity',
        'ko': '유동성',
        'fr': 'liquidité',
        'es': 'liquidez',
        'de': 'Liquidität',
        'ja': '流動性',
        'zh': '流动性'
    },
    'volatility': {
        'en': 'volatility',
        'ko': '변동성',
        'fr': 'volatilité',
        'es': 'volatilidad',
        'de': 'Volatilität',
        'ja': 'ボラティリティ',
        'zh': '波动性'
    },
    'trading_volume': {
        'en': 'trading volume',
        'ko': '거래량',
        'fr': 'volume de transactions',
        'es': 'volumen de transacciones',
        'de': 'Handelsvolumen',
        'ja': '取引量',
        'zh': '交易量'
    },

    # Technical terms
    'decentralized': {
        'en': 'decentralized',
        'ko': '분산형',
        'fr': 'décentralisé',
        'es': 'descentralizado',
        'de': 'dezentralisiert',
        'ja': '分散型',
        'zh': '分散式'
    },
    'wallet': {
        'en': 'wallet',
        'ko': '지갑',
        'fr': 'portefeuille',
        'es': 'billetera',
        'de': 'Geldbörse',
        'ja': 'ウォレット',
        'zh': '钱包'
    },
    'address': {
        'en': 'address',
        'ko': '주소',
        'fr': 'adresse',
        'es': 'dirección',
        'de': 'Adresse',
        'ja': 'アドレス',
        'zh': '地址'
    },
    'transaction': {
        'en': 'transaction',
        'ko': '거래',
        'fr': 'transaction',
        'es': 'transacción',
        'de': 'Transaktion',
        'ja': 'トランザクション',
        'zh': '交易'
    },
    'mining': {
        'en': 'mining',
        'ko': '채굴',
        'fr': 'minage',
        'es': 'minería',
        'de': 'Mining',
        'ja': 'マイニング',
        'zh': '挖矿'
    },
    'staking': {
        'en': 'staking',
        'ko': '스테이킹',
        'fr': 'mise en jeu',
        'es': 'apuesta',
        'de': 'Staking',
        'ja': 'ステーキング',
        'zh': '质押'
    },

    # Security terms
    'security': {
        'en': 'security',
        'ko': '보안',
        'fr': 'sécurité',
        'es': 'seguridad',
        'de': 'Sicherheit',
        'ja': 'セキュリティ',
        'zh': '安全'
    },
    'audit': {
        'en': 'audit',
        'ko': '감사',
        'fr': 'audit',
        'es': 'auditoría',
        'de': 'Audit',
        'ja': '監査',
        'zh': '审计'
    },
    'vulnerability': {
        'en': 'vulnerability',
        'ko': '취약점',
        'fr': 'vulnérabilité',
        'es': 'vulnerabilidad',
        'de': 'Schwachstelle',
        'ja': '脆弱性',
        'zh': '漏洞'
    },
}


# ============================================================================
# TEXT FIELD DETECTION
# ============================================================================

TEXT_FIELD_KEYS = [
    'description',
    'summary',
    'analysis',
    'content',
    'details',
    'overview',
    'background',
    'methodology',
    'findings',
    'conclusion',
    'title',
    'name',
    'report',
    'note',
    'comment',
    'text',
]

NUMERIC_FIELD_KEYS = [
    'price', 'market_cap', 'volume', 'supply', 'change', 'percentage',
    'count', 'amount', 'value', 'number', 'ratio', 'rate', 'index',
    'fee', 'balance', 'total', 'average', 'minimum', 'maximum',
]

DATE_FIELD_KEYS = [
    'date', 'timestamp', 'created_at', 'updated_at', 'published_at',
    'start_date', 'end_date', 'launch_date',
]


def is_text_field(key: str, value: Any) -> bool:
    """
    Determine if a field should be translated.

    Args:
        key: Field key/name
        value: Field value

    Returns:
        True if field should be translated, False otherwise
    """
    if not isinstance(value, str):
        return False

    key_lower = key.lower()

    # Exclude numeric, date, and technical fields
    if any(x in key_lower for x in NUMERIC_FIELD_KEYS):
        return False
    if any(x in key_lower for x in DATE_FIELD_KEYS):
        return False
    if key_lower in ['address', 'wallet', 'id', 'hash', 'tx_hash', 'contract']:
        return False

    # Include obvious text fields
    if any(x in key_lower for x in TEXT_FIELD_KEYS):
        return True

    # For unknown fields, use heuristic: include if value is reasonably long
    return len(value) > 10 and value.count(' ') > 2


def translate_text(text: str, target_lang: str) -> str:
    """
    Translate a text field to target language.
    Uses Claude API if ANTHROPIC_API_KEY is set, otherwise falls back to stub.

    Args:
        text: Text to translate
        target_lang: Target language code (en, ko, fr, es, de, ja, zh)

    Returns:
        Translated text
    """
    if target_lang == 'en' or not text:
        return text

    # Skip very short or code-like strings
    if len(text) <= 3 or text.isupper():
        return text

    # Try Claude API
    import os
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if api_key:
        try:
            return _translate_text_claude(text, target_lang, api_key)
        except Exception as e:
            logger.warning(f"Claude translation failed, using stub: {e}")

    # Fallback: stub with language tag
    return f"[{target_lang.upper()}] {text}"


_LANG_NAMES = {
    'en': 'English', 'ko': '한국어/Korean', 'fr': 'French',
    'es': 'Spanish', 'de': 'German', 'ja': 'Japanese', 'zh': 'Chinese',
}


def _translate_text_claude(text: str, target_lang: str, api_key: str) -> str:
    """Translate using Claude API."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    lang_name = _LANG_NAMES.get(target_lang, target_lang)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=(
            f"You are a professional translator for blockchain/cryptocurrency content. "
            f"Translate the text to {lang_name}. Preserve technical terms, ticker symbols, "
            f"URLs, numbers, and formatting. Return ONLY the translated text."
        ),
        messages=[{"role": "user", "content": text}]
    )
    return message.content[0].text.strip()


def translate_dict_values(data: Dict[str, Any], source_lang: str, target_lang: str) -> Dict[str, Any]:
    """
    Recursively translate text values in a dictionary.

    Args:
        data: Dictionary to translate
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        Dictionary with translated values
    """
    translated = {}

    for key, value in data.items():
        if isinstance(value, dict):
            # Recursively translate nested dicts
            translated[key] = translate_dict_values(value, source_lang, target_lang)

        elif isinstance(value, list):
            # Translate list items if they're strings
            translated[key] = [
                translate_text(item, target_lang) if isinstance(item, str) else item
                for item in value
            ]

        elif isinstance(value, str):
            # Translate text fields, preserve other strings
            if is_text_field(key, value):
                translated[key] = translate_text(value, target_lang)
            else:
                translated[key] = value

        else:
            # Preserve numeric, boolean, null, and other types
            translated[key] = value

    return translated


def translate_report_data(project_data: Dict[str, Any], source_lang: str,
                         target_lang: str) -> Dict[str, Any]:
    """
    Translate project report data to a target language.

    Deep-copies the project data, translates text fields while preserving
    numeric values, dates, and addresses.

    Args:
        project_data: Dictionary containing project data (assumed to be in source_lang)
        source_lang: Source language code (e.g., 'en')
        target_lang: Target language code (e.g., 'ko')

    Returns:
        New dictionary with translated project data

    Example:
        en_data = {'name': 'Bitcoin', 'description': 'Digital currency...'}
        ko_data = translate_report_data(en_data, 'en', 'ko')
        # ko_data['description'] will be translated to Korean
    """
    # Deep copy to avoid modifying original
    translated_data = copy.deepcopy(project_data)

    # If source and target are the same, return as-is
    if source_lang == target_lang:
        return translated_data

    logger.info(f"Translating project data from {source_lang} to {target_lang}")

    # Translate all text fields
    translated_data = translate_dict_values(translated_data, source_lang, target_lang)

    # Add metadata
    if isinstance(translated_data, dict):
        translated_data['_translation_metadata'] = {
            'source_lang': source_lang,
            'target_lang': target_lang,
            'translated_at': datetime.utcnow().isoformat(),
        }

    return translated_data


def translate_all_languages(project_data: Dict[str, Any],
                            source_lang: str = 'en') -> Dict[str, Dict[str, Any]]:
    """
    Translate project data to all 7 supported languages.

    Takes English master data and returns a dictionary keyed by language code,
    with translated project_data for each language.

    Args:
        project_data: Project data in source language (default: English)
        source_lang: Source language code (default: 'en')

    Returns:
        Dictionary: {lang_code: translated_data_dict}

    Example:
        en_data = load_project_data('btc.json')
        all_langs = translate_all_languages(en_data)
        # all_langs['ko'] has Korean translation
        # all_langs['fr'] has French translation
        # etc.
    """
    target_languages = ['en', 'ko', 'fr', 'es', 'de', 'ja', 'zh']

    logger.info(f"Translating project data to {len(target_languages)} languages")

    translations = {}

    for target_lang in target_languages:
        try:
            translations[target_lang] = translate_report_data(
                project_data,
                source_lang=source_lang,
                target_lang=target_lang
            )
            logger.debug(f"✓ Translated to {target_lang}")
        except Exception as e:
            logger.error(f"Failed to translate to {target_lang}: {e}")
            # Fall back to source language on error
            translations[target_lang] = copy.deepcopy(project_data)

    return translations


def apply_glossary_consistency(text: str, target_lang: str) -> str:
    """
    Apply glossary terms to ensure consistent blockchain terminology.
    Replaces English terms with their target-language equivalents
    using case-insensitive word-boundary matching.
    """
    import re

    if target_lang == 'en' or not text:
        return text

    for en_term, translations in GLOSSARY.items():
        if target_lang in translations:
            target_term = translations[target_lang]
            # Case-insensitive replacement with word boundary awareness
            pattern = re.compile(re.escape(en_term), re.IGNORECASE)
            text = pattern.sub(target_term, text)

    return text


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Example usage
    example_data = {
        'name': 'Bitcoin',
        'slug': 'btc',
        'description': 'Bitcoin is a decentralized digital currency.',
        'market_cap': 1200000000000,
        'price': 45000.50,
        'analysis': 'The cryptocurrency has shown strong market performance.',
        'metadata': {
            'created_at': '2024-01-01T00:00:00Z',
            'tags': [
                'cryptocurrency',
                'blockchain'
            ]
        }
    }

    print("Original (EN):")
    print(example_data)
    print("\n" + "="*70 + "\n")

    # Translate to Korean
    ko_data = translate_report_data(example_data, 'en', 'ko')
    print("Translated (KO):")
    print(ko_data)
    print("\n" + "="*70 + "\n")

    # Translate to all languages
    all_translations = translate_all_languages(example_data)
    print("Available translations:")
    for lang_code in all_translations.keys():
        print(f"  - {lang_code}: {type(all_translations[lang_code])}")
