"""Tests for watch_slides publish guard against slug/content mismatch (BCE-1699)."""

import importlib.util
from pathlib import Path
import tempfile

import pytest


@pytest.fixture(scope='module')
def ws():
    spec = importlib.util.spec_from_file_location(
        'watch_slides', Path(__file__).with_name('watch_slides.py')
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def projects():
    return [
        {'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
        {'slug': 'bittensor', 'name': 'Bittensor', 'symbol': 'TAO'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]


@pytest.fixture
def bitcoin_body():
    return (
        '비트코인(Bitcoin)은 2008년 글로벌 금융위기의 산물로, 사토시 나카모토가 제안한 '
        '세계 최초의 P2P 전자 현금 시스템이다. BTC는 21,000,000개로 공급량이 제한된다. '
    ) * 3


@pytest.fixture
def bittensor_body():
    return (
        '비텐서(Bittensor)는 인공지능(AI)과 기계 학습(ML) 모델의 개발, 공유 및 평가를 위한 '
        '오픈 소스 프로토콜이자 탈중앙화된 네트워크이다. TAO 토큰은 Bittensor 네트워크의 '
        '기축 통화로 사용된다. '
    ) * 3


def test_flags_bittensor_body_under_bitcoin_filename(ws, projects, bittensor_body):
    proj_bitcoin = projects[0]
    mismatch = ws._detect_slug_content_mismatch(proj_bitcoin, bittensor_body, '', projects)
    assert mismatch is not None
    assert mismatch['expected_slug'] == 'bitcoin'
    assert mismatch['detected_slug'] == 'bittensor'
    assert mismatch['detected_score'] > mismatch['expected_score']


def test_passes_matching_content(ws, projects, bitcoin_body):
    proj_bitcoin = projects[0]
    assert ws._detect_slug_content_mismatch(proj_bitcoin, bitcoin_body, '', projects) is None


def test_skips_empty_body_raster_pdf(ws, projects):
    proj_bitcoin = projects[0]
    assert ws._detect_slug_content_mismatch(proj_bitcoin, '', '', projects) is None


def test_passes_when_resolved_slug_matches_strongest_signal(ws, projects, bittensor_body):
    proj_bittensor = projects[1]
    assert ws._detect_slug_content_mismatch(proj_bittensor, bittensor_body, '', projects) is None


def test_short_body_below_threshold_is_skipped(ws, projects):
    proj_bitcoin = projects[0]
    short_bittensor = '비텐서 Bittensor TAO'
    assert ws._detect_slug_content_mismatch(proj_bitcoin, short_bittensor, '', projects) is None


def test_blocks_chinese_body_resolved_as_japanese(ws):
    body = (
        '本报告分析稳定币流动性、链上结算网络、交易所储备以及美元流动性传导机制。'
        '报告指出资金费率、现货深度与跨境支付需求共同影响市场结构。'
    ) * 3

    mismatch = ws._detect_language_content_mismatch('ja', body, '')

    assert mismatch == {
        'resolved_lang': 'ja',
        'detected_lang': 'zh',
        'source': 'text',
    }


def test_allows_japanese_body_resolved_as_japanese(ws):
    body = (
        '本レポートはステーブルコイン流動性、オンチェーン決済ネットワーク、'
        '取引所準備金、およびドル流動性の伝達メカニズムを分析する。'
    ) * 3

    assert ws._detect_language_content_mismatch('ja', body, '') is None


def test_blocks_japanese_body_with_korean_cover_text(ws):
    body = (
        'USDC ハイブリッド経済OS\n'
        '스테이블코인 결제 네트워크 분석\n'
        '本レポートはオンチェーン決済、準備金、流動性伝達を分析する。'
    ) * 3

    mismatch = ws._detect_language_content_mismatch('ja', body, '')

    assert mismatch == {
        'resolved_lang': 'ja',
        'detected_lang': 'ko',
        'source': 'text',
        'reason': 'mixed_cjk_script',
    }


def test_allows_chinese_body_resolved_as_chinese(ws):
    body = (
        '本报告分析稳定币流动性、链上结算网络、交易所储备以及美元流动性传导机制。'
        '报告指出资金费率、现货深度与跨境支付需求共同影响市场结构。'
    ) * 3

    assert ws._detect_language_content_mismatch('zh', body, '') is None


def test_blocks_chinese_body_with_japanese_kana(ws):
    body = (
        '本报告分析稳定币流动性、链上结算网络。'
        'このページには日本語のタイトルが混入しています。'
    ) * 3

    mismatch = ws._detect_language_content_mismatch('zh', body, '')

    assert mismatch == {
        'resolved_lang': 'zh',
        'detected_lang': 'ja',
        'source': 'text',
        'reason': 'mixed_cjk_script',
    }


@pytest.mark.parametrize(
    ('filename', 'expected'),
    [
        ('Tether_Cryptoeconomic_Blueprint_cn2.pdf', 'zh'),
        ('TRON_Economic_Architecture_en.pdf', 'en'),
        ('Solana_Economic_Engine_jp.pdf', 'ja'),
        ('TRON_Economic_Blueprint_ko.pdf', 'ko'),
        ('XRPL_Cryptoeconomic_Blueprint.pdf', None),
    ],
)
def test_resolves_explicit_filename_language_hints(ws, filename, expected):
    assert ws._lang_from_filename(filename) == expected


def test_iter_targets_yields_root_and_subfolder_pdfs(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {'econ': 'root-econ'})
    pdfs_by_parent = {
        'root-econ': [{'id': 'root-slide', 'name': 'bitcoin-root.pdf', 'modifiedTime': 't0'}],
        'folder-bitcoin': [{'id': 'slide-pdf', 'name': 'bitcoin-slide.pdf', 'modifiedTime': 't1'}],
    }
    folders_by_parent = {
        'root-econ': [{'id': 'folder-bitcoin', 'name': 'bitcoin'}],
        'folder-bitcoin': [],
    }
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))

    targets = list(ws._iter_targets(object(), ['econ']))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [
        ('econ', 'root-slide'),
        ('econ', 'slide-pdf'),
    ]
    assert targets[0][1]['source_path'] == 'Slide/econ/bitcoin-root.pdf'
    assert targets[0][1]['parent_folder_id'] == 'root-econ'
    assert targets[0][1]['source_depth'] == 0
    assert targets[1][1]['source_path'] == 'Slide/econ/bitcoin/bitcoin-slide.pdf'
    assert targets[1][1]['parent_folder_id'] == 'folder-bitcoin'
    assert targets[1][1]['source_depth'] == 1


def test_iter_targets_recurses_nested_folders(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {'econ': 'root-econ'})
    pdfs_by_parent = {
        'folder-lang': [{'id': 'nested-slide', 'name': 'bitcoin-ko.pdf', 'modifiedTime': 't1'}],
    }
    folders_by_parent = {
        'root-econ': [{'id': 'folder-bitcoin', 'name': 'bitcoin'}],
        'folder-bitcoin': [{'id': 'folder-lang', 'name': 'ko'}],
        'folder-lang': [],
    }
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))

    targets = list(ws._iter_targets(object(), ['econ']))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [('econ', 'nested-slide')]
    assert targets[0][1]['source_path'] == 'Slide/econ/bitcoin/ko/bitcoin-ko.pdf'
    assert targets[0][1]['source_depth'] == 2


def test_process_file_id_filter_skips_nonmatching_targets(ws, monkeypatch):
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: {})
    monkeypatch.setattr(ws, '_iter_targets', lambda _service, _types: [
        ('econ', {'id': 'skip-me', 'name': 'skip.pdf', 'modifiedTime': 't0'}),
    ])

    scanned, processed = ws.process(
        ['econ'],
        filter_slug=None,
        filter_file_ids={'target-only'},
        dry_run=True,
        force=True,
    )

    assert scanned == []
    assert processed == []


def test_parse_language_overrides(ws):
    assert ws._parse_language_overrides([
        'drive-file-1=zh',
        'drive-file-2=ja',
    ]) == {
        'drive-file-1': 'zh',
        'drive-file-2': 'ja',
    }


def test_parse_language_overrides_rejects_invalid_lang(ws):
    with pytest.raises(ValueError):
        ws._parse_language_overrides(['drive-file-1=jp'])


def _write_blank_pdf(width, height):
    import fitz

    handle = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    handle.close()
    doc = fitz.open()
    doc.new_page(width=width, height=height)
    doc.save(handle.name)
    doc.close()
    return Path(handle.name)


def test_pdf_page_profile_accepts_landscape_slide(ws):
    path = _write_blank_pdf(1376, 768)
    try:
        profile = ws._pdf_page_profile(str(path))
    finally:
        path.unlink(missing_ok=True)

    assert profile['is_landscape_slide'] is True
    assert profile['aspect_ratio'] > 1.7


def test_pdf_page_profile_rejects_portrait_report(ws):
    path = _write_blank_pdf(595, 842)
    try:
        profile = ws._pdf_page_profile(str(path))
    finally:
        path.unlink(missing_ok=True)

    assert profile['is_landscape_slide'] is False
    assert profile['aspect_ratio'] < 1.0


class _FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class _FakeProjectReportsTable:
    def __init__(self, row):
        self.row = row
        self.patch = None

    def select(self, *_args):
        return self

    def update(self, patch):
        self.patch = patch
        return self

    def eq(self, *_args):
        return self

    def single(self):
        return self

    def execute(self):
        if self.patch is not None:
            self.row.update(self.patch)
            return _FakeExecuteResult([self.row])
        return _FakeExecuteResult(self.row)


class _FakeSupabase:
    def __init__(self, row):
        self.project_reports = _FakeProjectReportsTable(row)

    def table(self, name):
        assert name == 'project_reports'
        return self.project_reports


def test_remove_slide_url_if_matches_only_removes_exact_legacy_url(ws):
    row = {
        'slide_html_urls_by_lang': {
            'ko': 'https://storage/legacy-root.html',
            'en': 'https://storage/current-en.html',
        }
    }
    sb = _FakeSupabase(row)

    removed = ws._remove_slide_url_if_matches(
        sb,
        'report-1',
        'ko',
        'https://storage/legacy-root.html',
    )

    assert removed is True
    assert row['slide_html_urls_by_lang'] == {'en': 'https://storage/current-en.html'}


def test_remove_slide_url_if_matches_keeps_newer_url(ws):
    row = {'slide_html_urls_by_lang': {'ko': 'https://storage/new-slide.html'}}
    sb = _FakeSupabase(row)

    removed = ws._remove_slide_url_if_matches(
        sb,
        'report-1',
        'ko',
        'https://storage/legacy-root.html',
    )

    assert removed is False
    assert row['slide_html_urls_by_lang'] == {'ko': 'https://storage/new-slide.html'}
