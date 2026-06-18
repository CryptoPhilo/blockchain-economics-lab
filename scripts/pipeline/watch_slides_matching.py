"""Project matching and publish-guard helpers for slide PDFs."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ALIAS_REGISTRY: Dict[str, List[str]] = {
    'ripple': ['xrpl', 'xrp ledger'],
    'world-liberty-financial': ['wlf intelligence briefing', 'wlf economic architecture'],
    'okx': ['x layer economic blueprint', 'x layer money chain analysis', 'x layer economic analysis'],
    'ethereum': ['programmable trust blueprint'],
    'bitcoin-cash': ['bch'],
    'cardano': ['ada'],
    'tether-gold': ['xaut'],
    'usdg': ['global-dollar', 'global dollar', 'global dollar usd'],
    'hedera-hashgraph': ['hedera', 'hbar', 'hedera hashgraph'],
    'mantle': ['mnt'],
    'uniswap': ['uni'],
    'polkadot': ['dot'],
    'pi-network': ['pi'],
    'cosmos-hub': ['cosmos'],
    'worldcoin': ['world'],
    'siren': ['sirenai', 'siren ai'],
    'gate': ['gatechain', 'gate chain'],
    'venice-token': ['venice ai', 'venice_ai'],
    'flare-networks': ['flare'],
    'fabric-foundation': ['fabric'],
    'theuselesscoin': ['uselesscoin'],
}

_TOKEN_RE = re.compile(r'[A-Za-z0-9]+')
_ASCII_ONLY_RE = re.compile(r'^[a-z0-9 ]+$')
_SIGNAL_SEPARATOR_RE = re.compile(r'[^a-z0-9]+')
_MIN_NUMERIC_CMC_ID_SIGNAL_LENGTH = 6
SLUG_CONTENT_GUARD_EXCLUDED_DETECTED_SLUGS = {
    'ethereum-name-service',
}
CANONICAL_SLUG_TIEBREAKERS = {
    'hedera-hashgraph',
    'usdg',
}


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
    for key in ('slug', 'name', 'symbol', 'coingecko_id'):
        v = str(project.get(key) or '').strip().lower()
        if v:
            sigs.append(v)
    cmc_id = str(project.get('cmc_id') or '').strip().lower()
    if cmc_id and (
        not cmc_id.isdigit() or len(cmc_id) >= _MIN_NUMERIC_CMC_ID_SIGNAL_LENGTH
    ):
        sigs.append(cmc_id)
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
    best: Optional[Tuple[Tuple[int, int, int], Dict[str, str]]] = None
    for proj in projects:
        score = 0
        for sig in _project_signal(proj):
            score = max(score, _score_signal_in_text(sig, t, normalized_text, tokens))
        if score:
            status = str(proj.get('status') or '').lower()
            active_rank = 1 if status != 'archived' else 0
            canonical_rank = 1 if (proj.get('slug') or '').lower() in CANONICAL_SLUG_TIEBREAKERS else 0
            rank = (score, active_rank, canonical_rank)
            if best is None or rank > best[0]:
                best = (rank, proj)
    return best[1] if best else None


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
    if not has_interpretable_text_layer and expected_score >= 16:
        # Raster slide OCR can produce high-scoring false positives from noisy
        # letters. If the filename-resolved project is also visible in the body,
        # require a wider gap before blocking the publish.
        min_score_margin = 24
    expected_slug = (resolved_project.get('slug') or '').lower()
    best_other: Optional[Tuple[int, Dict[str, str]]] = None
    for proj in projects:
        candidate_slug = (proj.get('slug') or '').lower()
        if candidate_slug == expected_slug:
            continue
        if candidate_slug in SLUG_CONTENT_GUARD_EXCLUDED_DETECTED_SLUGS:
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
