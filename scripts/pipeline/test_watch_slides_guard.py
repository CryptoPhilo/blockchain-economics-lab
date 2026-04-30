"""Tests for watch_slides publish guard against slug/content mismatch (BCE-1699)."""

import importlib.util
from pathlib import Path

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
