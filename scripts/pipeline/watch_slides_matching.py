"""Project matching and publish-guard helpers for slide PDFs."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ALIAS_REGISTRY: Dict[str, List[str]] = {
    'ripple': ['xrpl', 'xrp ledger'],
    'immutable-x': ['immutable', 'imx'],
    'artificial-superintelligence-alliance': ['asi', 'fetch ai', 'fetch-ai', 'fet'],
    'world-liberty-financial': ['wlfi', 'wlf intelligence briefing', 'wlf economic architecture'],
    'pyth-network': ['pyth_network', 'pyth'],
    'lido-dao': ['lido'],
    'aerodrome-finance': ['aerodrome'],
    'bittorrent': ['bttc'],
    'okx': ['x layer economic blueprint', 'x layer money chain analysis', 'x layer economic analysis'],
    'ethereum': ['programmable trust blueprint'],
    'bitcoin-cash': ['bch'],
    'cardano': ['ada'],
    'tether-gold': ['xaut'],
    'global-dollar': ['usdg', 'global dollar usd'],
    'binancecoin': ['bnb', 'bnb chain', 'binance coin'],
    'the-open-network': ['gram', 'ton', 'toncoin', 'the open network'],
    'hedera-hashgraph': ['hedera', 'hbar'],
    'flare-networks': ['flare', 'flare network', 'flr'],
    'mantle': ['mnt'],
    'uniswap': ['uni'],
    'polkadot': ['dot'],
    'pi-network': ['pi'],
    'cosmos-hub': ['cosmos'],
    'worldcoin': ['world', 'worldcoin org', 'worldcoin-org', 'wld'],
    'siren': ['sirenai', 'siren ai'],
    'gate': ['gatechain', 'gate chain', 'gate token', 'gatetoken', 'gt'],
    'usd1': [
        'world liberty financial',
        'world-liberty-financial',
        'world liberty financial usd',
        'world liberty usd',
        'wlfi stablecoin',
        'wlfi usd',
    ],
    'dai': ['makerdao dai', 'multi collateral dai'],
    'gas': ['neo gas', 'neo-gas', 'gas token', 'neo gas token'],
    'venice-token': ['venice ai', 'venice_ai'],
    'virtuals-protocol': ['virtuals', 'virtuals protocol'],
    'zebec-network': ['zebec', 'zbcn'],
    'story-protocol': ['story'],
    'convex-finance': ['convex'],
    'deepbook-protocol': ['deepbook'],
    'golem-network-tokens': ['golem', 'golem network', 'golem_network'],
    'mx-token': ['mexc'],
    '1inch': ['1inch network', '1inch_network', '1inch-network'],
    'instadapp': ['fluid', 'fluid protocol', 'fluid_protocol', 'instadapp fluid'],
    'vision': ['vsn', 'vision token', 'vision-token'],
    'newton': ['newton protocol', 'newton_protocol', 'newt'],
    'reserve-rights': ['reserve protocol', 'reserve_protocol', 'reserve-protocol', 'reserve rights', 'rsr'],
    'synthetix': ['snx', 'havven'],
    'starknet': ['strk', 'stark net', 'stark-net'],
    'wemix': ['wemix network', 'wemix-network', 'wemix_network'],
    'usdai': ['usd ai', 'usd.ai', 'usd_ai', 'usdai', 'usd ai stablecoin', 'chip'],
    'usual-usd': [
        'usual money',
        'usual-money',
        'usual_money',
        'usual protocol',
        'usual-protocol',
        'usual_protocol',
        'usual usd',
        'usual-usd',
        'usual_usd',
        'usd0',
    ],
    'falcon-usd': [
        'falcon usd',
        'falcon-usd',
        'falcon_usd',
        'usdf',
    ],
    'falcon-finance': [
        'falcon finance',
        'falcon-finance',
        'falcon_finance',
    ],
    'river': ['river protocol', 'river_protocol', 'river-protocol'],
    'river-protocol': ['rvr'],
    'eur-coinvertible': ['eurcv', 'eur coinvertible', 'eur coinvertible eurcv'],
    'ab-chain': ['ab', 'ab chain', 'ab_chain'],
    'awe-network': ['awe', 'awe network', 'awe_network'],
    'maplestory-universe': [
        'nexpace',
        'nxpc',
        'maplestory',
        'maplestory universe',
        'maplestory_universe',
        'maple story universe',
        'msu',
    ],
    'soon-network': ['soon', 'soon network', 'soon-network'],
    'yzy': ['yzy money', 'yzy-money'],
    'ethereum-name-service': [
        'ens',
        'ens 이더리움 네임 서비스',
        '이더리움 네임 서비스',
        'ens イーサリアムネームサービス',
        'イーサリアムネームサービス',
        'ens 以太坊名称服务',
        '以太坊名称服务',
    ],
    'ondo-us-dollar-yield': [
        'usdy',
        'ondo usdy',
        'ondo-usdy',
        'ondo_usdy',
        'ondo usd yield',
        'ondo us dollar yield',
        'ondo u.s. dollar yield',
    ],
    'jupiter-perps-lp': [
        'jlp',
        'jupiter perps',
        'jupiter-perps',
        'jupiter_perps',
        'jupiter perps lp',
        'jupiter-perps-lp',
        'jupiter_perps_lp',
        'jupiter perpetuals liquidity provider token',
    ],
    'undeads-games': ['undeads'],
    'circle-internet-group-tokenized-stock-ondo': [
        'crcl',
        'crclon',
        'circle internet group',
        'circle tokenized stock',
    ],
    'us-dollar-tokenized-currency-ondo': [
        'usdon',
        'usd on',
        'u.s. dollar tokenized currency',
        'us dollar tokenized currency',
        'us dollar tokenized currency ondo',
    ],
    'rollbit-coin': ['rollbit', 'rlb'],
    'bitmart-token': ['bitmart', 'bmx'],
    'collector-crypt': ['collector crypt', 'collector_crypt', 'collectorcrypt', 'cards'],
    'backpack-exchange': ['backpack', 'backpack exchange', 'backpack_exchange', 'backpackexchange', 'bp'],
}

CONTENT_MISMATCH_NOISE_SLUGS: Set[str] = {'ethereum-name-service'}
_TOKEN_RE = re.compile(r'[A-Za-z0-9]+')
_ASCII_ONLY_RE = re.compile(r'^[a-z0-9 ]+$')
_SIGNAL_SEPARATOR_RE = re.compile(r'[^a-z0-9]+')
_EXPLICIT_REPORT_FILENAME_RE = re.compile(
    r'^(?P<prefix>.+?)[_\-\s]+(?:ECON|MAT|FOR)(?:[_\-\s.]|$)',
    re.IGNORECASE,
)


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or '')]


def _normalize_signal_text(text: str) -> str:
    return f" {_SIGNAL_SEPARATOR_RE.sub(' ', (text or '').lower()).strip()} "


def _is_ascii_signal(sig: str) -> bool:
    return bool(_ASCII_ONLY_RE.match(sig))


def _score_signal_in_text(sig: str, t: str, normalized_text: str, tokens: Set[str]) -> int:
    """Score one signal without allowing ASCII substring false positives."""
    if not sig:
        return 0

    normalized_sig = _normalize_signal_text(sig)
    normalized_sig_body = normalized_sig.strip()
    ascii_signal = _is_ascii_signal(normalized_sig_body)
    has_phrase_separator = bool(re.search(r'[\s-]', sig))

    if ascii_signal:
        if has_phrase_separator:
            return len(sig) * 2 if normalized_sig in normalized_text else 0
        return len(sig) * 2 if sig in tokens else 0

    if has_phrase_separator and normalized_sig_body and normalized_sig in normalized_text:
        return len(sig) * 2
    if sig in tokens:
        return len(sig) * 2
    if len(sig) >= 2 and sig in t:
        return len(sig) * 2
    return 0


def _project_signal(project: Dict[str, Any]) -> List[str]:
    """Return lowercase tokens that identify a project."""
    sigs: List[str] = []
    for key in ('slug', 'name', 'symbol'):
        v = (project.get(key) or '').strip().lower()
        if v:
            sigs.append(v)
    aliases = project.get('aliases') or []
    if isinstance(aliases, list):
        sigs.extend(
            alias.strip().lower()
            for alias in aliases
            if isinstance(alias, str) and alias.strip()
        )
    sigs.extend(PROJECT_ALIAS_REGISTRY.get((project.get('slug') or '').lower(), []))
    return list({s for s in sigs if s})


def _match_project_by_text(text: str, projects: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Match `text` against project signals. Prefer longer/more specific signals."""
    if not text:
        return None
    t = text.lower()
    normalized_text = _normalize_signal_text(text)
    tokens = set(_tokenize(text))
    best: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        score = 0
        for sig in _project_signal(proj):
            score = max(score, _score_signal_in_text(sig, t, normalized_text, tokens))
        if score and (best is None or score > best[0]):
            best = (score, proj)
    return best[1] if best else None


def _match_project_by_explicit_prefix(prefix: str, projects: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Match an explicit filename prefix before considering the full filename.

    Operators often name reports as `Context_Asset_MAT_ko.pdf`, for example
    `Aave_GHO_MAT_ko.pdf`. In that shape the trailing token is the asset being
    reported on, while the leading token is context. Prefer suffix matches so
    parent projects do not capture child assets.
    """
    if not prefix:
        return None
    prefix_tokens = _tokenize(prefix)
    best_suffix: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        for sig in _project_signal(proj):
            sig_tokens = _tokenize(sig)
            if not sig_tokens or len(sig_tokens) > len(prefix_tokens):
                continue
            if prefix_tokens[-len(sig_tokens):] == sig_tokens:
                score = 1000 + len(sig) * 2
                if best_suffix is None or score > best_suffix[0]:
                    best_suffix = (score, proj)
    if best_suffix:
        return best_suffix[1]
    return _match_project_by_text(prefix, projects)


def _explicit_report_project_prefix(pdf_name: str) -> Optional[str]:
    """Return the explicit project prefix from names like `bitcoin_MAT_ko.pdf`.

    When a Drive slide filename has this shape, the prefix is the operator's
    source-of-truth project hint. Falling through to OCR/body matching after an
    unresolved explicit prefix can attach the file to an unrelated project whose
    generic body terms scored higher.
    """
    stem = re.sub(r'\.[^.]+$', '', pdf_name or '')
    match = _EXPLICIT_REPORT_FILENAME_RE.match(stem)
    if not match:
        return None
    prefix = _normalize_signal_text(match.group('prefix')).strip()
    return prefix or None


def _resolve_slug(
    pdf_name: str,
    pdf_text: str,
    ocr_text: str,
    projects: List[Dict[str, str]],
) -> Tuple[Optional[Dict[str, str]], str]:
    """Return (project, source) where source is filename, pdf_text, ocr, or none."""
    explicit_prefix = _explicit_report_project_prefix(pdf_name)
    if explicit_prefix:
        proj = _match_project_by_explicit_prefix(explicit_prefix, projects)
        if proj:
            return proj, 'filename'
        return None, 'filename_unresolved'

    proj = _match_project_by_text(pdf_name, projects)
    if proj:
        return proj, 'filename'
    proj = _match_project_by_text(pdf_text, projects)
    if proj:
        return proj, 'pdf_text'
    proj = _match_project_by_text(ocr_text, projects)
    if proj:
        return proj, 'ocr'
    return None, 'none'


def _score_project_in_text(text: str, proj: Dict[str, str]) -> int:
    """Return the per-project match score used by _match_project_by_text."""
    if not text:
        return 0
    t = text.lower()
    normalized_text = _normalize_signal_text(text)
    tokens = set(_tokenize(text))
    score = 0
    for sig in _project_signal(proj):
        score = max(score, _score_signal_in_text(sig, t, normalized_text, tokens))
    return score


def _detect_slug_content_mismatch(
    resolved_project: Optional[Dict[str, str]],
    pdf_text: str,
    ocr_text: str,
    projects: List[Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    """Publish guard: flag PDFs whose body contradicts the filename-resolved slug."""
    if resolved_project is None:
        return None
    body = (pdf_text or '') + '\n' + (ocr_text or '')
    if len(body.strip()) < 200:
        return None
    has_interpretable_text_layer = len((pdf_text or '').strip()) >= 200
    min_other_score = 12 if has_interpretable_text_layer else 24
    expected_score = _score_project_in_text(body, resolved_project)
    # When the filename-resolved project is present in the body, treat a longer
    # competing alias as corroborating evidence only if it is overwhelmingly
    # stronger. Otherwise localized reports that compare against named peers can
    # be falsely blocked because a single long peer alias out-scores a short
    # project slug such as "rain".
    min_score_margin = 32 if expected_score > 0 else (1 if has_interpretable_text_layer else 12)
    expected_slug = (resolved_project.get('slug') or '').lower()
    best_other: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        other_slug = (proj.get('slug') or '').lower()
        if other_slug == expected_slug:
            continue
        if other_slug in CONTENT_MISMATCH_NOISE_SLUGS:
            continue
        score = _score_project_in_text(body, proj)
        if score >= min_other_score and (best_other is None or score > best_other[0]):
            best_other = (score, proj)
    if best_other and best_other[0] >= expected_score + min_score_margin:
        other_slug = (best_other[1].get('slug') or '').lower()
        return {
            'expected_slug': expected_slug,
            'expected_score': expected_score,
            'detected_slug': other_slug,
            'detected_score': best_other[0],
        }
    return None
