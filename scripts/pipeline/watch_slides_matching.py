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
    'mantle': ['mnt'],
    'uniswap': ['uni'],
    'polkadot': ['dot'],
    'pi-network': ['pi'],
    'cosmos-hub': ['cosmos'],
    'worldcoin': ['world'],
    'siren': ['sirenai', 'siren ai'],
    'gate': ['gatechain', 'gate chain'],
    'venice-token': ['venice ai', 'venice_ai'],
    'virtuals-protocol': ['virtuals', 'virtuals protocol'],
    'zebec-network': ['zebec', 'zbcn'],
    'story-protocol': ['story'],
    'convex-finance': ['convex'],
    'deepbook-protocol': ['deepbook'],
    'golem-network-tokens': ['golem', 'golem network', 'golem_network'],
    'mx-token': ['mexc'],
    'ethereum-name-service': [
        'ens',
        'ens 이더리움 네임 서비스',
        '이더리움 네임 서비스',
        'ens イーサリアムネームサービス',
        'イーサリアムネームサービス',
        'ens 以太坊名称服务',
        '以太坊名称服务',
    ],
}

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
    proj = _match_project_by_text(pdf_name, projects)
    if proj:
        return proj, 'filename'
    if _explicit_report_project_prefix(pdf_name):
        return None, 'filename_unresolved'
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
    min_score_margin = 1 if has_interpretable_text_layer else 12
    expected_score = _score_project_in_text(body, resolved_project)
    expected_slug = (resolved_project.get('slug') or '').lower()
    best_other: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        if (proj.get('slug') or '').lower() == expected_slug:
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
