"""Tests for watch_slides publish guard against slug/content mismatch (BCE-1699)."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys

import pytest


@pytest.fixture(scope='module')
def ws():
    spec = importlib.util.spec_from_file_location(
        'watch_slides', Path(__file__).with_name('watch_slides.py')
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pipeline_module(module_name):
    spec = importlib.util.spec_from_file_location(
        module_name, Path(__file__).with_name(f'{module_name}.py')
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def matching_helpers():
    return _load_pipeline_module('watch_slides_matching')


@pytest.fixture(scope='module')
def inspection_helpers():
    return _load_pipeline_module('watch_slides_inspection')


@pytest.fixture(scope='module')
def telemetry_helpers():
    return _load_pipeline_module('watch_slides_telemetry')


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


@pytest.fixture
def ripple_body():
    return (
        'XRP Ledger (XRPL) is a public blockchain for fast settlement, tokenization, '
        'and low-cost value movement. XRP is the native asset used for fees, account '
        'reserves, and bridge liquidity across the network. '
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


@pytest.mark.parametrize('alias', ['빗텐서', '비텐서'])
def test_bittensor_korean_alias_resolves_from_slide_filename(ws, alias):
    projects = [
        {
            'slug': 'bittensor',
            'name': 'Bittensor',
            'symbol': 'TAO',
            'aliases': ['빗텐서', '비텐서', '타오', 'tao'],
        },
        {'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
    ]

    project, source = ws._resolve_slug(
        f'{alias}_Cryptoeconomic_Blueprint_ko.pdf',
        '',
        '',
        projects,
    )

    assert project['slug'] == 'bittensor'
    assert source == 'filename'


def test_short_body_below_threshold_is_skipped(ws, projects):
    proj_bitcoin = projects[0]
    short_bittensor = '비텐서 Bittensor TAO'
    assert ws._detect_slug_content_mismatch(proj_bitcoin, short_bittensor, '', projects) is None


@pytest.mark.parametrize('lang_token', ['en', 'ja', 'ko', 'zh'])
def test_explicit_xrpl_alias_resolves_to_ripple_for_supported_locales(ws, lang_token):
    projects = [
        {'slug': 'ripple', 'name': 'Ripple', 'symbol': 'XRP'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]

    project, source = ws._resolve_slug(
        f'XRPL_Cryptoeconomic_Blueprint_{lang_token}.pdf',
        '',
        '',
        projects,
    )

    assert project['slug'] == 'ripple'
    assert source == 'filename'


def test_xrpl_alias_passes_content_guard_for_ripple_body(ws, ripple_body):
    projects = [
        {'slug': 'ripple', 'name': 'Ripple', 'symbol': 'XRP'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]
    project, _source = ws._resolve_slug(
        'XRPL_Cryptoeconomic_Blueprint_en.pdf',
        ripple_body,
        '',
        projects,
    )

    assert project['slug'] == 'ripple'
    assert ws._detect_slug_content_mismatch(project, ripple_body, '', projects) is None


def test_xrpl_alias_still_blocks_wrong_project_body(ws):
    projects = [
        {'slug': 'ripple', 'name': 'Ripple', 'symbol': 'XRP'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]
    ethereum_body = (
        'Ethereum is a smart contract platform. ETH powers the Ethereum network, '
        'EVM execution, decentralized applications, and programmable settlement. '
    ) * 4
    project, _source = ws._resolve_slug(
        'XRPL_Cryptoeconomic_Blueprint_en.pdf',
        ethereum_body,
        '',
        projects,
    )

    mismatch = ws._detect_slug_content_mismatch(project, ethereum_body, '', projects)

    assert project['slug'] == 'ripple'
    assert mismatch['expected_slug'] == 'ripple'
    assert mismatch['detected_slug'] == 'ethereum'


def test_filename_slug_with_ocr_only_generic_project_signal_does_not_block(ws):
    projects = [
        {'slug': 'okx', 'name': 'OKX', 'symbol': 'OKB'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]
    project, source = ws._resolve_slug(
        'X_Layer_Economic_Blueprint_cn.pdf',
        '',
        '',
        projects,
    )
    noisy_ocr = (
        'Ethereum market structure settlement liquidity validators gas staking '
        'generic blockchain ecosystem smart contracts. '
    ) * 4

    mismatch = ws._detect_slug_content_mismatch(project, '', noisy_ocr, projects)

    assert project['slug'] == 'okx'
    assert source == 'filename'
    assert mismatch is None


@pytest.mark.parametrize(
    'filename',
    [
        'WLFI_ECON_ko.pdf',
        'WLF_Intelligence_Briefing_en.pdf',
        'WLF_Economic_Architecture_cn.pdf',
    ],
)
def test_wlf_filename_aliases_resolve_to_world_liberty_financial(ws, filename):
    projects = [
        {'slug': 'world-liberty-financial', 'name': 'World Liberty Financial', 'symbol': 'WLFI'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]

    project, source = ws._resolve_slug(filename, '', '', projects)

    assert project['slug'] == 'world-liberty-financial'
    assert source == 'filename'


def test_wlf_token_alone_is_not_a_world_liberty_financial_alias(ws):
    projects = [
        {'slug': 'world-liberty-financial', 'name': 'World Liberty Financial', 'symbol': 'WLFI'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]

    project, source = ws._resolve_slug('WLF_Market_Update_en.pdf', '', '', projects)

    assert project is None
    assert source == 'none'


@pytest.mark.parametrize(
    'filename',
    [
        'X_Layer_Economic_Blueprint_cn.pdf',
        'X_Layer_Money_Chain_Analysis_ko.pdf',
        'X_Layer_Economic_Blueprint_en.pdf',
        'X_Layer_Economic_Analysis_jp.pdf',
    ],
)
def test_x_layer_filename_aliases_resolve_to_okx(ws, filename):
    projects = [
        {'slug': 'okx', 'name': 'OKX', 'symbol': 'OKB'},
        {'slug': 'ripple', 'name': 'Ripple', 'symbol': 'XRP'},
    ]

    project, source = ws._resolve_slug(filename, '', '', projects)

    assert project['slug'] == 'okx'
    assert source == 'filename'


def test_x_layer_phrase_alone_is_not_an_okx_alias(ws):
    projects = [
        {'slug': 'okx', 'name': 'OKX', 'symbol': 'OKB'},
        {'slug': 'ripple', 'name': 'Ripple', 'symbol': 'XRP'},
    ]

    project, source = ws._resolve_slug('X_Layer_Validator_Update_en.pdf', '', '', projects)

    assert project is None
    assert source == 'none'


def test_programmable_trust_blueprint_filename_resolves_to_ethereum(ws):
    projects = [
        {'slug': 'ripple', 'name': 'Ripple', 'symbol': 'XRP'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]

    project, source = ws._resolve_slug('Programmable_Trust_Blueprint_ko.pdf', '', '', projects)

    assert project['slug'] == 'ethereum'
    assert source == 'filename'


def test_programmable_trust_is_not_an_ethereum_alias(ws):
    projects = [
        {'slug': 'ripple', 'name': 'Ripple', 'symbol': 'XRP'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
    ]

    project, source = ws._resolve_slug(
        'Programmable_Trust_Cryptoeconomic_Blueprint_en.pdf',
        '',
        '',
        projects,
    )

    assert project is None
    assert source == 'none'


def test_filename_separator_normalization_resolves_tether_gold(ws):
    projects = [
        {'slug': 'tether-gold', 'name': 'Tether Gold', 'symbol': 'XAUT'},
        {'slug': 'tether', 'name': 'Tether', 'symbol': 'USDT'},
    ]

    project, source = ws._resolve_slug(
        'Tether_Gold_Cryptoeconomics_cn.pdf',
        '',
        '',
        projects,
    )

    assert project['slug'] == 'tether-gold'
    assert source == 'filename'


@pytest.mark.parametrize(
    ('slug', 'name', 'symbol', 'filename'),
    [
        ('bitcoin-cash', 'Bitcoin Cash', 'BCH', 'BCH_Cryptoeconomic_Blueprint_en.pdf'),
        ('cardano', 'Cardano', 'ADA', 'ADA_Economic_Architecture_en.pdf'),
        ('tether-gold', 'Tether Gold', 'XAUT', 'XAUT_Cryptoeconomics_en.pdf'),
        ('global-dollar', 'Global Dollar', 'USDG', 'USDG_Cryptoeconomic_Blueprint_en.pdf'),
        ('mantle', 'Mantle', 'MNT', 'MNT_Cryptoeconomic_Blueprint_en.pdf'),
        ('uniswap', 'Uniswap', 'UNI', 'UNI_Cryptoeconomic_Blueprint_en.pdf'),
        ('polkadot', 'Polkadot', 'DOT', 'DOT_Cryptoeconomic_Blueprint_en.pdf'),
        ('pi-network', 'Pi Network', 'PI', 'PI_Cryptoeconomic_Blueprint_en.pdf'),
    ],
)
def test_recovery_target_aliases_resolve_from_slide_filename(ws, slug, name, symbol, filename):
    projects = [
        {'slug': slug, 'name': name, 'symbol': symbol},
        {'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
    ]

    project, source = ws._resolve_slug(filename, '', '', projects)

    assert project['slug'] == slug
    assert source == 'filename'


@pytest.mark.parametrize(
    ('slug', 'name', 'symbol', 'filename'),
    [
        ('cosmos-hub', 'Cosmos Hub', 'ATOM', 'cosmos_MAT_ko.pdf'),
        ('worldcoin', 'Worldcoin', 'WLD', 'World_MAT_en.pdf'),
    ],
)
def test_mat_short_filenames_resolve_to_canonical_projects(ws, slug, name, symbol, filename):
    projects = [
        {'slug': slug, 'name': name, 'symbol': symbol},
        {'slug': 'world-liberty-financial', 'name': 'World Liberty Financial', 'symbol': 'WLFI'},
    ]

    project, source = ws._resolve_slug(filename, '', '', projects)

    assert project['slug'] == slug
    assert source == 'filename'


def test_immutable_short_filename_resolves_to_immutable_x(ws):
    projects = [
        {'slug': 'immutable-x', 'name': 'Immutable X', 'symbol': 'IMX'},
        {'slug': 'ainft', 'name': 'AINFT', 'symbol': 'NFT'},
    ]

    project, source = ws._resolve_slug('immutable_MAT_ko.pdf', '', '', projects)

    assert project['slug'] == 'immutable-x'
    assert source == 'filename'


@pytest.mark.parametrize(
    ('slug', 'name', 'symbol', 'filename'),
    [
        ('artificial-superintelligence-alliance', 'Artificial Superintelligence Alliance', 'FET', 'ASI_ECON_ko.pdf'),
        ('pyth-network', 'Pyth Network', 'PYTH', 'pyth_network_MAT_ko.pdf'),
        ('lido-dao', 'Lido Finance', 'LDO', 'Lido_MAT_en.pdf'),
        ('aerodrome-finance', 'Aerodrome Finance', 'AERO', 'Aerodrome_MAT_ko.pdf'),
        ('bittorrent', 'BitTorrent', 'BTT', 'BTTC_MAT_ko.pdf'),
        ('virtuals-protocol', 'Virtuals Protocol', 'VIRTUAL', 'Virtuals_ECON_ko.pdf'),
        ('zebec-network', 'Zebec Network', 'ZBCN', 'zebec_MAT_ko.pdf'),
        ('ethereum-name-service', 'Ethereum Name Service', 'ENS', 'ENS_MAT_ko.pdf'),
        ('story-protocol', 'Story Protocol', 'IP', 'story_ECON_ko.pdf'),
        ('convex-finance', 'Convex Finance', 'CVX', 'convex_MAT_en.pdf'),
        ('deepbook-protocol', 'DeepBook Protocol', 'DEEP', 'DeepBook_MAT_jp.pdf'),
        ('golem-network-tokens', 'Golem Network Tokens', 'GNT', 'golem_network_ECON_cn.pdf'),
        ('mx-token', 'MX Token', 'MX', 'MEXC_ECON_en.pdf'),
        ('1inch', '1inch', '1INCH', '1inch_ECON_ko.pdf'),
        ('instadapp', 'Fluid', 'FLUID', 'fluid_ECON_en.pdf'),
        ('instadapp', 'Fluid', 'FLUID', 'Fluid_MAT_jp.pdf'),
        ('vision', 'Vision', 'VSN', 'VSN_ECON_cn.pdf'),
        ('vision', 'Vision', 'VSN', 'vision_token_MAT_ko.pdf'),
        ('newton', 'Newton', 'N', 'NEWT_MAT_en.pdf'),
        ('reserve-rights', 'Reserve Rights', 'RSR', 'Reserve_Protocol_ECON_ko.pdf'),
        ('reserve-rights', 'Reserve Rights', 'RSR', 'Reserve_Rights_MAT_en.pdf'),
        ('synthetix', 'Synthetix', 'SNX', 'synthetix_ECON_ko.pdf'),
        ('synthetix', 'Synthetix', 'SNX', 'SNX_MAT_en.pdf'),
        ('starknet', 'Starknet', 'STRK', 'Starknet_ECON_ko.pdf'),
        ('starknet', 'Starknet', 'STRK', 'STRK_MAT_en.pdf'),
        ('binancecoin', 'BNB', 'BNB', 'BNB_ECON_ko.pdf'),
        ('binancecoin', 'BNB', 'BNB', 'BNB_Chain_MAT_en.pdf'),
        ('the-open-network', 'Toncoin', 'TON', 'TON_ECON_ko.pdf'),
        ('the-open-network', 'Toncoin', 'TON', 'Toncoin_MAT_en.pdf'),
        ('hedera-hashgraph', 'Hedera', 'HBAR', 'Hedera_ECON_ko.pdf'),
        ('hedera-hashgraph', 'Hedera', 'HBAR', 'HBAR_MAT_en.pdf'),
        ('flare-networks', 'Flare', 'FLR', 'Flare_ECON_ko.pdf'),
        ('flare-networks', 'Flare', 'FLR', 'Flare_Network_MAT_en.pdf'),
        ('pi-network', 'Pi', 'PI', 'PI_ECON_ko.pdf'),
        ('pi-network', 'Pi', 'PI', 'Pi_Network_MAT_en.pdf'),
        ('worldcoin', 'Worldcoin', 'WLD', 'Worldcoin_org_ECON_ko.pdf'),
        ('worldcoin', 'Worldcoin', 'WLD', 'WLD_MAT_en.pdf'),
        ('gate', 'GateToken', 'GT', 'GateToken_ECON_ko.pdf'),
        ('gate', 'GateToken', 'GT', 'Gate_Chain_MAT_en.pdf'),
        ('usd1', 'World Liberty Financial USD', 'USD1', 'USD1_ECON_ko.pdf'),
        ('usd1', 'World Liberty Financial USD', 'USD1', 'World_Liberty_Financial_USD_MAT_en.pdf'),
        ('dai', 'Dai', 'DAI', 'DAI_ECON_ko.pdf'),
        ('dai', 'Dai', 'DAI', 'Dai_MAT_en.pdf'),
        ('wemix', 'WEMIX', 'WEMIX', 'WEMIX_ECON_cn.pdf'),
        ('usd-ai', 'USD.AI', 'CHIP', 'USD_AI_ECON_ko.pdf'),
        ('usd-ai', 'USD.AI', 'CHIP', 'CHIP_MAT_en.pdf'),
        ('ab-chain', 'AB Chain', 'AB', 'AB_Chain_ECON_ko.pdf'),
        ('ab-chain', 'AB Chain', 'AB', 'AB_MAT_en.pdf'),
        ('maplestory-universe', 'NEXPACE', 'NXPC', 'MapleStory_Universe_ECON_ko.pdf'),
        ('maplestory-universe', 'NEXPACE', 'NXPC', 'MapleStory_Universe_MSU_MAT_en.pdf'),
        ('maplestory-universe', 'NEXPACE', 'NXPC', 'NXPC_ECON_cn.pdf'),
        ('river', 'River', 'RIVER', 'River_ECON_ko.pdf'),
        ('river', 'River', 'RIVER', 'River_Protocol_ECON_jp.pdf'),
        ('river-protocol', 'River Protocol', 'RVR', 'RVR_MAT_cn.pdf'),
    ],
)
def test_operational_short_filename_aliases_resolve_to_canonical_projects(ws, slug, name, symbol, filename):
    projects = [
        {'slug': slug, 'name': name, 'symbol': symbol},
        {'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
    ]

    project, source = ws._resolve_slug(filename, '', '', projects)

    assert project['slug'] == slug
    assert source == 'filename'


def test_ens_localized_body_does_not_get_blocked_by_comparison_project_mentions(ws):
    projects = [
        {'slug': 'ethereum-name-service', 'name': 'Ethereum Name Service', 'symbol': 'ENS'},
        {'slug': 'trust-wallet', 'name': 'Trust Wallet', 'symbol': 'TWT'},
    ]
    project, source = ws._resolve_slug('ENS_ECON_ko.pdf', '', '', projects)
    body = (
        'ENS 이더리움 네임 서비스는 지갑 주소를 사람이 읽을 수 있는 이름으로 연결하는 '
        '네임 레이어다. 본문은 Trust Wallet 같은 지갑 앱과의 통합 가능성을 비교하지만, '
        '분석 대상은 ENS 거버넌스와 도메인 수요, ENS 토큰 경제다. '
    ) * 4

    assert project['slug'] == 'ethereum-name-service'
    assert source == 'filename'
    assert ws._detect_slug_content_mismatch(project, body, '', projects) is None


def test_unresolved_explicit_report_filename_does_not_fall_through_to_ocr(ws):
    projects = [
        {'slug': 'ainft', 'name': 'AINFT', 'symbol': 'NFT'},
        {'slug': 'gensyn', 'name': 'Gensyn', 'symbol': 'GENSYN'},
    ]

    project, source = ws._resolve_slug(
        'immutable_MAT_ko.pdf',
        '',
        'AINFT NFT decentralized intelligence network Gensyn compute marketplace',
        projects,
    )

    assert project is None
    assert source == 'filename_unresolved'


@pytest.mark.parametrize(
    'filename',
    [
        'SirenAI_ECON_cn.pdf',
        'SirenAI_ECON_jp.pdf',
        'SirenAI_ECON_ko.pdf',
        'SirenAI_ECON_en.pdf',
    ],
)
def test_sirenai_econ_filenames_resolve_to_active_siren_slug(ws, filename):
    projects = [
        {'slug': 'siren', 'name': 'Siren', 'symbol': 'SIREN', 'status': 'active'},
        {'slug': 'siren-bsc', 'name': 'siren', 'symbol': 'SIREN', 'status': 'monitoring_only'},
    ]

    project, source = ws._resolve_slug(filename, '', '', projects)

    assert project['slug'] == 'siren'
    assert source == 'filename'


def test_kcs_filename_resolves_to_kucoin_without_gnosis_substring_collision(ws):
    projects = [
        {'slug': 'kucoin', 'name': 'KuCoin', 'symbol': 'KCS'},
        {'slug': 'gnosis', 'name': 'Gnosis', 'symbol': 'GNO'},
    ]

    project, source = ws._resolve_slug(
        'KCS_System_Diagnosis_cn.pdf',
        '',
        '',
        projects,
    )

    assert project['slug'] == 'kucoin'
    assert source == 'filename'


def test_ascii_signal_does_not_match_inside_larger_filename_token(ws):
    projects = [
        {'slug': 'gnosis', 'name': 'Gnosis', 'symbol': 'GNO'},
    ]

    project, source = ws._resolve_slug(
        'KCS_System_Diagnosis_cn.pdf',
        '',
        '',
        projects,
    )

    assert project is None
    assert source == 'none'


def test_matching_helper_keeps_ascii_signal_token_boundaries(matching_helpers):
    projects = [
        {'slug': 'gnosis', 'name': 'Gnosis', 'symbol': 'GNO'},
    ]

    project, source = matching_helpers._resolve_slug(
        'KCS_System_Diagnosis_cn.pdf',
        '',
        '',
        projects,
    )

    assert project is None
    assert source == 'none'


def test_non_ascii_substring_alias_matching_is_preserved(ws):
    projects = [
        {'slug': 'bittensor', 'name': 'Bittensor', 'symbol': 'TAO', 'aliases': ['비텐서']},
        {'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
    ]

    project, source = ws._resolve_slug(
        '비텐서경제진단_ko.pdf',
        '',
        '',
        projects,
    )

    assert project['slug'] == 'bittensor'
    assert source == 'filename'


def test_filename_language_resolution_ignores_noisy_ocr_script_mismatch(ws):
    mismatch = ws._detect_language_content_mismatch(
        'ko',
        'NotebookLM export metadata ' * 20,
        'これはOCRが誤認した日本語テキストです' * 5,
        'filename',
    )

    assert mismatch is None


def test_inspection_helper_prefers_filename_language_over_metadata(inspection_helpers):
    lang, source = inspection_helpers._resolve_lang(
        'Project_Market_Map_ko.pdf',
        {'title': 'English market map'},
        'English market map ' * 5,
        '',
    )

    assert lang == 'ko'
    assert source == 'filename'


def test_telemetry_helper_classifies_blocked_counts(telemetry_helpers):
    metrics = {
        'scanned': 2,
        'processed': 1,
        'published': 0,
        'review_ready': 0,
        'unresolved': 1,
        'failed': 0,
        'blocked': 1,
    }

    assert telemetry_helpers._paperclip_status_for_counts(metrics) == 'waiting_manual'


def test_blocked_manifest_diagnostic_honors_backoff(ws):
    now = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    diag = ws._blocked_manifest_diagnostic(
        {
            'status': 'unresolved',
            'updated_at': '2026-05-12T10:30:00Z',
        },
        now=now,
        recheck_after_minutes=120,
    )

    assert diag == {
        'should_recheck': False,
        'status': 'unresolved',
        'updated_at': '2026-05-12T10:30:00+00:00',
        'age_minutes': 90,
        'recheck_after_minutes': 120,
        'reason': 'within_backoff',
    }


def test_blocked_manifest_diagnostic_rechecks_after_threshold(ws):
    now = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)
    diag = ws._blocked_manifest_diagnostic(
        {
            'status': 'language_mismatch',
            'updated_at': '2026-05-12T09:30:00Z',
        },
        now=now,
        recheck_after_minutes=120,
    )

    assert diag['should_recheck'] is True
    assert diag['age_minutes'] == 150
    assert diag['reason'] == 'age_exceeded_threshold'


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self

    def in_(self, field, values):
        self.rows = [row for row in self.rows if row.get(field) in values]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(list(self.tables[name]))


def test_active_project_backlog_guard_flags_projects_without_slide_state(ws):
    sb = FakeSupabase({
        "tracked_projects": [
            {
                "id": "p-shib",
                "slug": "shiba-inu",
                "name": "Shiba Inu",
                "symbol": "SHIB",
                "status": "active",
                "last_econ_report_at": None,
                "last_maturity_report_at": None,
                "last_forensic_report_at": None,
                "next_econ_due_at": None,
                "next_maturity_due_at": None,
            },
            {
                "id": "p-btc",
                "slug": "bitcoin",
                "name": "Bitcoin",
                "symbol": "BTC",
                "status": "active",
                "last_econ_report_at": "2026-05-01T00:00:00Z",
                "last_maturity_report_at": None,
                "last_forensic_report_at": None,
                "next_econ_due_at": None,
                "next_maturity_due_at": None,
            },
        ],
        "project_reports": [],
    })

    missing = ws.find_active_projects_missing_report_backlog(sb)

    assert [project["slug"] for project in missing] == ["bitcoin", "shiba-inu"]


def test_active_project_backlog_guard_flags_pdf_only_legacy_reports(ws):
    sb = FakeSupabase({
        "tracked_projects": [
            {
                "id": "p-shib",
                "slug": "shiba-inu",
                "name": "Shiba Inu",
                "symbol": "SHIB",
                "status": "active",
                "last_econ_report_at": None,
                "last_maturity_report_at": None,
                "last_forensic_report_at": None,
                "next_econ_due_at": None,
                "next_maturity_due_at": None,
            },
        ],
        "project_reports": [{
            "project_id": "p-shib",
            "gdrive_urls_by_lang": {"en": {"url": "https://drive.example/report.pdf"}},
            "slide_html_urls_by_lang": None,
        }],
    })

    missing = ws.find_active_projects_missing_report_backlog(sb)

    assert [project["slug"] for project in missing] == ["shiba-inu"]
    assert missing[0]["status"] == "missing_slide_html"
    assert missing[0]["reason"] == "legacy_pdf_only_no_slide_html"


@pytest.mark.parametrize(
    ('project', 'report_row'),
    [
        (
            {'id': 'p-aave', 'slug': 'aave', 'name': 'Aave', 'symbol': 'AAVE'},
            {
                'project_id': 'p-aave',
                'gdrive_urls_by_lang': {
                    'en': {'url': 'https://drive.google.com/file/d/aave-pdf/view'},
                },
                'slide_html_urls_by_lang': None,
            },
        ),
        (
            {'id': 'p-usdd', 'slug': 'usdd', 'name': 'USDD', 'symbol': 'USDD'},
            {
                'project_id': 'p-usdd',
                'file_url': 'https://drive.google.com/file/d/usdd-pdf/view',
                'slide_html_urls_by_lang': {},
            },
        ),
        (
            {
                'id': 'p-bitget-token',
                'slug': 'bitget-token',
                'name': 'Bitget Token',
                'symbol': 'BGB',
            },
            {
                'project_id': 'p-bitget-token',
                'gdrive_url': 'https://drive.google.com/file/d/bgb-pdf/view',
                'slide_html_urls_by_lang': {'en': ''},
            },
        ),
    ],
)
def test_active_project_backlog_guard_marks_legacy_pdf_only_no_slide_html(ws, project, report_row):
    tracked_project = {
        **project,
        "status": "active",
        "last_econ_report_at": "2026-05-01T00:00:00Z",
        "last_maturity_report_at": None,
        "last_forensic_report_at": None,
        "next_econ_due_at": None,
        "next_maturity_due_at": None,
    }
    sb = FakeSupabase({
        "tracked_projects": [tracked_project],
        "project_reports": [report_row],
    })

    missing = ws.find_active_projects_missing_report_backlog(sb)

    assert [project["slug"] for project in missing] == [tracked_project["slug"]]
    assert missing[0]["id"] == tracked_project["id"]
    assert missing[0]["name"] == tracked_project["name"]
    assert missing[0]["symbol"] == tracked_project["symbol"]
    assert missing[0]["status"] == "missing_slide_html"
    assert missing[0]["reason"] == "legacy_pdf_only_no_slide_html"


def test_active_project_backlog_guard_ignores_projects_with_slide_html(ws):
    sb = FakeSupabase({
        "tracked_projects": [
            {
                "id": "p-shib",
                "slug": "shiba-inu",
                "name": "Shiba Inu",
                "symbol": "SHIB",
                "status": "active",
                "last_econ_report_at": None,
                "last_maturity_report_at": None,
                "last_forensic_report_at": None,
                "next_econ_due_at": None,
                "next_maturity_due_at": None,
            },
        ],
        "project_reports": [{
            "project_id": "p-shib",
            "gdrive_urls_by_lang": {"en": {"url": "https://drive.example/report.pdf"}},
            "slide_html_urls_by_lang": {"en": "https://storage.example/slides/econ/shiba-inu/en.html"},
        }],
    })

    missing = ws.find_active_projects_missing_report_backlog(sb)

    assert missing == []


def test_active_project_backlog_guard_ignores_duplicate_symbol_with_report_state(ws):
    sb = FakeSupabase({
        "tracked_projects": [
            {
                "id": "p-usdg",
                "slug": "usdg",
                "name": "USDG",
                "symbol": "USDG",
                "status": "active",
                "last_econ_report_at": "2026-04-25T14:39:31Z",
                "last_maturity_report_at": None,
                "last_forensic_report_at": None,
                "next_econ_due_at": None,
                "next_maturity_due_at": None,
            },
            {
                "id": "p-global-dollar",
                "slug": "global-dollar",
                "name": "Global Dollar",
                "symbol": "USDG",
                "status": "active",
                "last_econ_report_at": None,
                "last_maturity_report_at": None,
                "last_forensic_report_at": None,
                "next_econ_due_at": None,
                "next_maturity_due_at": None,
            },
        ],
        "project_reports": [{
            "project_id": "p-usdg",
            "slide_html_urls_by_lang": {"en": "https://storage.example/slides/econ/usdg/en.html"},
        }],
    })

    missing = ws.find_active_projects_missing_report_backlog(sb)

    assert missing == []


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


def test_allows_english_body_with_noisy_cjk_ocr(ws):
    pdf_text = (
        'Litecoin is a peer-to-peer digital currency optimized for fast settlement, '
        'low transaction fees, merged mining incentives, and digital silver positioning. '
    ) * 3
    noisy_ocr = 'ライトコイン 市場 流動性 供給 発行 交易 网络 结算'

    assert ws._detect_language_content_mismatch('en', pdf_text, noisy_ocr) is None


def test_allows_chinese_body_with_small_kana_ocr_noise(ws):
    body = (
        '莱特币是一种点对点数字货币，强调快速结算、低手续费、固定供应、'
        '工作量证明安全预算、矿工激励、支付网络流动性以及数字白银叙事。'
    ) * 4
    noisy_ocr = body + ' の は スライド'

    assert ws._detect_language_content_mismatch('zh', body, noisy_ocr) is None


def test_filename_lang_with_ocr_only_japanese_noise_does_not_block(ws):
    noisy_ocr = (
        'ライトコイン 市場 流動性 供給 発行 取引 ネットワーク 決済 '
        'このスライドはOCRノイズを含みます。'
    ) * 4

    assert ws._detect_language_content_mismatch('ko', '', noisy_ocr, 'filename') is None


def test_filename_lang_still_blocks_text_layer_cjk_mismatch(ws):
    body = (
        'このレポートは市場流動性、オンチェーン決済、バリデータ収益、'
        'ステーキング構造、およびネットワーク利用を分析する。'
    ) * 3

    mismatch = ws._detect_language_content_mismatch('ko', body, '', 'filename')

    assert mismatch == {
        'resolved_lang': 'ko',
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


def test_list_pdfs_direct_accepts_pdf_extension_with_stale_mime(ws):
    class _ListCall:
        def __init__(self, service):
            self.service = service

        def execute(self):
            return {
                'files': [
                    {
                        'id': 'ethgas-ko',
                        'name': 'ETHGas_GWEI_ECON_ko.pdf',
                        'mimeType': 'application/octet-stream',
                        'modifiedTime': 't1',
                    },
                    {
                        'id': 'notes',
                        'name': 'ETHGas_GWEI_ECON_ko.txt',
                        'mimeType': 'text/plain',
                        'modifiedTime': 't2',
                    },
                ]
            }

    class _Files:
        def __init__(self):
            self.queries = []
            self.calls = []

        def list(self, **kwargs):
            self.calls.append(kwargs)
            self.queries.append(kwargs['q'])
            return _ListCall(self)

    class _Service:
        def __init__(self):
            self._files = _Files()

        def files(self):
            return self._files

    service = _Service()

    files = ws._list_pdfs_direct(service, 'root-econ')

    assert [file_info['id'] for file_info in files] == ['ethgas-ko']
    assert "mimeType != 'application/vnd.google-apps.folder'" in service._files.queries[0]
    assert service._files.calls[0]['corpora'] == 'allDrives'


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


def test_iter_targets_uses_drive_name_search_for_slug_when_root_listing_misses(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {'econ': 'root-econ'})
    projects = [{'slug': 'ethgas', 'name': 'ETHGas', 'symbol': 'GWEI'}]
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: [])
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: [])

    searched_terms = []

    def _fake_search(_service, terms, _modified_since=None):
        searched_terms.extend(sorted(terms))
        return [{
            'id': 'ethgas-econ-ko',
            'name': 'ETHGas_GWEI_ECON_ko.pdf',
            'mimeType': 'application/pdf',
            'modifiedTime': 't1',
        }]

    monkeypatch.setattr(ws, '_search_pdfs_by_name', _fake_search)

    targets = list(ws._iter_targets(object(), ['econ'], filter_slug='ethgas', projects=projects))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [('econ', 'ethgas-econ-ko')]
    assert targets[0][1]['source_path'] == 'Drive/search/econ/ETHGas_GWEI_ECON_ko.pdf'
    assert targets[0][1]['drive_search_fallback'] is True
    assert targets[0][1]['expected_slide_parent_id'] == 'root-econ'
    assert 'ETHGas' in searched_terms
    assert 'GWEI' in searched_terms


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


def test_iter_targets_routes_misfiled_forensic_pdf_by_filename(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {
        'econ': 'root-econ',
        'mat': 'root-mat',
        'for': 'root-for',
    })
    pdfs_by_parent = {
        'root-mat': [{
            'id': 'ton-forensic-en',
            'name': 'TON_Forensic_Market_Report_en.pdf',
            'modifiedTime': 't-ton',
        }],
    }
    folders_by_parent = {
        'root-econ': [],
        'root-mat': [],
        'root-for': [],
    }
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))

    targets = list(ws._iter_targets(object(), ['for']))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [('for', 'ton-forensic-en')]
    assert targets[0][1]['source_path'] == 'Slide/mat/TON_Forensic_Market_Report_en.pdf'
    assert targets[0][1]['parent_folder_id'] == 'root-mat'


def test_iter_targets_does_not_recurse_unrequested_slide_roots(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {
        'econ': 'root-econ',
        'mat': 'root-mat',
        'for': 'root-for',
    })
    pdfs_by_parent = {
        'root-mat': [{
            'id': 'ton-forensic-en',
            'name': 'TON_Forensic_Market_Report_en.pdf',
            'modifiedTime': 't-ton',
        }],
        'folder-mat-heavy': [{
            'id': 'should-not-scan',
            'name': 'Other_Forensic_Report_en.pdf',
            'modifiedTime': 't-other',
        }],
        'root-for': [],
    }
    folders_by_parent = {
        'root-for': [],
        'root-mat': [{'id': 'folder-mat-heavy', 'name': 'large-mat-folder'}],
    }
    child_calls = []

    def fake_list_child_folders(_service, parent_id):
        child_calls.append(parent_id)
        return folders_by_parent.get(parent_id, [])

    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_child_folders', fake_list_child_folders)

    targets = list(ws._iter_targets(object(), ['for']))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [('for', 'ton-forensic-en')]
    assert 'root-for' in child_calls
    assert 'root-mat' not in child_calls
    assert 'folder-mat-heavy' not in child_calls


class MutableFakeQuery:
    def __init__(self, table_rows):
        self.table_rows = table_rows
        self.rows = list(table_rows)
        self.update_payload = None
        self.upsert_row = None
        self.conflict_cols = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.rows = [row for row in self.rows if row.get(field) == value]
        return self

    def in_(self, field, values):
        self.rows = [row for row in self.rows if row.get(field) in values]
        return self

    def order(self, field, desc=False):
        self.rows = sorted(
            self.rows,
            key=lambda row: (row.get(field) is not None, row.get(field)),
            reverse=desc,
        )
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def single(self):
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def upsert(self, row, on_conflict=None):
        self.upsert_row = row
        self.conflict_cols = [col.strip() for col in (on_conflict or '').split(',') if col.strip()]
        return self

    def execute(self):
        if self.update_payload is not None:
            selected_ids = {id(row) for row in self.rows}
            for row in self.table_rows:
                if id(row) in selected_ids:
                    row.update(self.update_payload)
            return SimpleNamespace(data=[row for row in self.table_rows if id(row) in selected_ids])

        if self.upsert_row is not None:
            match = None
            if self.conflict_cols:
                for row in self.table_rows:
                    if all(row.get(col) == self.upsert_row.get(col) for col in self.conflict_cols):
                        match = row
                        break
            if match is None:
                match = {'id': f"r{len(self.table_rows) + 1}"}
                self.table_rows.append(match)
            match.update(self.upsert_row)
            return SimpleNamespace(data=[match])

        return SimpleNamespace(data=list(self.rows))


class MutableFakeSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return MutableFakeQuery(self.tables[name])


def test_ensure_runtime_project_seed_appends_known_slug_in_dry_run(ws):
    projects = [{'id': 'p-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'}]

    updated = ws._ensure_runtime_project_seed(
        object(),
        projects,
        'instadapp',
        dry_run=True,
    )

    assert [project['slug'] for project in updated] == ['bitcoin', 'instadapp']
    instadapp = updated[-1]
    assert instadapp['id'] == 'dry-run-instadapp'
    assert instadapp['name'] == 'Fluid'
    assert 'fluid' in instadapp['aliases']

    updated = ws._ensure_runtime_project_seed(
        object(),
        projects,
        'maplestory-universe',
        dry_run=True,
    )
    nexpace = updated[-1]
    assert nexpace['id'] == 'dry-run-maplestory-universe'
    assert nexpace['name'] == 'NEXPACE'
    assert nexpace['symbol'] == 'NXPC'
    assert 'msu' in nexpace['aliases']


def test_ensure_runtime_project_seed_upserts_known_slug_for_publish(ws):
    sb = MutableFakeSupabase({'tracked_projects': []})

    updated = ws._ensure_runtime_project_seed(
        sb,
        [],
        '1inch',
        dry_run=False,
    )

    assert len(updated) == 1
    assert updated[0]['id'] == 'r1'
    assert updated[0]['slug'] == '1inch'
    assert updated[0]['symbol'] == '1INCH'
    assert '1inch network' in updated[0]['aliases']
    assert sb.tables['tracked_projects'][0]['discovery_source'] == 'slide-runtime-report-gap-repair'


def test_report_source_identity_reuses_existing_drive_source(ws):
    project = {'id': 'p-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin'}
    source_patch = ws._report_source_patch(
        project=project,
        db_type='econ',
        lang='ko',
        pdf_file_id='drive-1',
        pdf_modified_time='2026-05-15T00:00:00Z',
        pdf_size='1234',
        pdf_name='bitcoin_ECON_ko.pdf',
    )
    sb = MutableFakeSupabase({
        'project_reports': [{
            'id': 'r-existing',
            'project_id': 'p-bitcoin',
            'report_type': 'econ',
            'language': 'ko',
            'version': 2,
            'status': 'published',
            'is_latest': True,
            'source_identity': source_patch['source_identity'],
            'source_file_id': 'drive-1',
        }],
    })

    report_id, version, status, previous_report_id, existing_source = ws._resolve_report_version_target(
        sb,
        project=project,
        db_type='econ',
        lang='ko',
        source_patch=source_patch,
    )

    assert report_id == 'r-existing'
    assert version == 2
    assert status == 'published'
    assert previous_report_id is None
    assert existing_source is True


def test_report_source_identity_allocates_next_version_for_new_drive_pdf(ws):
    project = {'id': 'p-bitcoin', 'slug': 'bitcoin'}
    source_patch = ws._report_source_patch(
        project=project,
        db_type='econ',
        lang='ko',
        pdf_file_id='drive-new',
        pdf_modified_time='2026-05-15T00:05:00Z',
        pdf_size='2234',
        pdf_name='bitcoin_ECON_ko_v3.pdf',
    )
    sb = MutableFakeSupabase({
        'project_reports': [{
            'id': 'r-latest',
            'project_id': 'p-bitcoin',
            'report_type': 'econ',
            'language': 'ko',
            'version': 2,
            'status': 'published',
            'is_latest': True,
            'updated_at': '2026-05-14T00:00:00Z',
            'source_identity': 'old-source',
            'source_file_id': 'drive-old',
        }],
    })

    report_id, version, status, previous_report_id, existing_source = ws._resolve_report_version_target(
        sb,
        project=project,
        db_type='econ',
        lang='ko',
        source_patch=source_patch,
    )

    assert report_id is None
    assert version == 3
    assert status == 'published'
    assert previous_report_id == 'r-latest'
    assert existing_source is False


def test_create_report_row_for_slide_moves_latest_pointer_and_stores_source(ws):
    project = {'id': 'p-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin'}
    source_patch = ws._report_source_patch(
        project=project,
        db_type='econ',
        lang='ko',
        pdf_file_id='drive-new',
        pdf_modified_time='2026-05-15T00:05:00Z',
        pdf_size='2234',
        pdf_name='bitcoin_ECON_ko_v3.pdf',
    )
    rows = [{
        'id': 'r-latest',
        'project_id': 'p-bitcoin',
        'report_type': 'econ',
        'language': 'ko',
        'version': 2,
        'status': 'published',
        'is_latest': True,
    }]
    sb = MutableFakeSupabase({
        'project_reports': rows,
        'tracked_projects': [{'id': 'p-bitcoin'}],
    })

    report_id, version = ws._create_report_row_for_slide(
        sb,
        project_id='p-bitcoin',
        db_type='econ',
        slug='bitcoin',
        lang='ko',
        pdf_file_id='drive-new',
        pdf_name='bitcoin_ECON_ko_v3.pdf',
        public_url='https://storage.example/econ/bitcoin/latest/ko.html',
        version=3,
        project_name=project['name'],
        source_patch=source_patch,
        previous_report_id='r-latest',
    )

    assert report_id == 'r2'
    assert version == 3
    assert rows[0]['is_latest'] is False
    assert rows[1]['is_latest'] is True
    assert rows[1]['previous_report_id'] == 'r-latest'
    assert rows[1]['source_identity'] == source_patch['source_identity']
    assert rows[1]['source_file_id'] == 'drive-new'
    assert rows[1]['title_ko'] == 'Bitcoin'


def test_report_source_identity_migration_backfill_prefers_version_before_timestamp():
    migration_sql = (
        Path(__file__).parents[2]
        / 'supabase'
        / 'migrations'
        / '20260515_add_report_source_identity_and_latest_contract.sql'
    ).read_text()

    order_start = migration_sql.index('ORDER BY')
    order_end = migration_sql.index(') AS rn', order_start)
    order_clause = migration_sql[order_start:order_end]

    assert order_clause.index('version DESC') < order_clause.index(
        'COALESCE(published_at, updated_at, created_at) DESC NULLS LAST'
    )

    rows = [
        {
            'id': 'v1-later-timestamp',
            'status': 'published',
            'version': 1,
            'published_at': '2026-05-15T12:00:00Z',
            'updated_at': '2026-05-15T12:00:00Z',
            'created_at': '2026-05-15T12:00:00Z',
        },
        {
            'id': 'v2-older-timestamp',
            'status': 'published',
            'version': 2,
            'published_at': '2026-05-14T12:00:00Z',
            'updated_at': '2026-05-14T12:00:00Z',
            'created_at': '2026-05-14T12:00:00Z',
        },
    ]

    def migration_rank_key(row):
        visible_rank = 0 if row['status'] in {'published', 'approved', 'in_review', 'coming_soon'} else 1
        timestamp = row.get('published_at') or row.get('updated_at') or row.get('created_at') or ''
        return (visible_rank, -row['version'], timestamp, row['id'])

    latest = sorted(rows, key=migration_rank_key)[0]

    assert latest['id'] == 'v2-older-timestamp'


def test_iter_targets_slug_filter_prunes_nonmatching_folders_and_pdfs(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {'econ': 'root-econ'})
    pdfs_by_parent = {
        'root-econ': [
            {'id': 'near-root', 'name': 'NEAR_Cryptoeconomic_Blueprint_en.pdf', 'modifiedTime': 't-near'},
            {'id': 'okx-root', 'name': 'OKX_Cryptoeconomic_Blueprint_en.pdf', 'modifiedTime': 't-okx'},
            {'id': 'bitcoin-cash-root', 'name': 'Bitcoin_Cash_Cryptoeconomic_Blueprint_en.pdf', 'modifiedTime': 't-bch'},
        ],
        'folder-near': [{'id': 'near-child', 'name': 'near_econ_v1_ko.pdf', 'modifiedTime': 't-near-ko'}],
        'folder-okx': [{'id': 'okx-child', 'name': 'okx_econ_v1_ko.pdf', 'modifiedTime': 't-okx-ko'}],
        'folder-bitcoin-cash': [{'id': 'bitcoin-cash-child', 'name': 'bitcoin-cash_econ_v1_ko.pdf', 'modifiedTime': 't-bch-ko'}],
    }
    folders_by_parent = {
        'root-econ': [
            {'id': 'folder-near', 'name': 'near'},
            {'id': 'folder-okx', 'name': 'okx'},
            {'id': 'folder-bitcoin-cash', 'name': 'bitcoin-cash'},
        ],
        'folder-near': [],
    }
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))

    targets = list(ws._iter_targets(
        object(),
        ['econ'],
        filter_slug='near',
        projects=[
            {'slug': 'near', 'name': 'NEAR Protocol', 'symbol': 'NEAR'},
            {'slug': 'bitcoin-cash', 'name': 'Bitcoin Cash', 'symbol': 'BCH'},
        ],
    ))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [
        ('econ', 'near-root'),
        ('econ', 'near-child'),
    ]


def test_iter_targets_slug_filter_scans_requested_root_container_folders(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {'econ': 'root-econ'})
    pdfs_by_parent = {
        'root-econ': [],
        'folder-batch': [
            {'id': 'wlfi-child', 'name': 'WLFI_ECON_ko.pdf', 'modifiedTime': 't-wlfi-ko'},
            {'id': 'okx-child', 'name': 'OKX_ECON_ko.pdf', 'modifiedTime': 't-okx-ko'},
        ],
    }
    folders_by_parent = {
        'root-econ': [{'id': 'folder-batch', 'name': 'batch-2026-05-14'}],
        'folder-batch': [],
    }
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))

    targets = list(ws._iter_targets(
        object(),
        ['econ'],
        filter_slug='world-liberty-financial',
        projects=[
            {'slug': 'world-liberty-financial', 'name': 'World Liberty Financial', 'symbol': 'WLFI'},
            {'slug': 'okx', 'name': 'OKX', 'symbol': 'OKB'},
        ],
    ))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [
        ('econ', 'wlfi-child'),
    ]


def test_iter_targets_slug_filter_does_not_substring_match_other_projects(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {'econ': 'root-econ'})
    pdfs_by_parent = {
        'root-econ': [
            {'id': 'bitcoin-root', 'name': 'Bitcoin_Cryptoeconomic_Blueprint_en.pdf', 'modifiedTime': 't-btc'},
            {'id': 'bitcoin-cash-root', 'name': 'Bitcoin_Cash_Cryptoeconomic_Blueprint_en.pdf', 'modifiedTime': 't-bch'},
            {'id': 'ethena-root', 'name': 'Ethena_Economic_Blueprint_en.pdf', 'modifiedTime': 't-ena'},
            {'id': 'tether-root', 'name': 'Tether_Cryptoeconomic_Blueprint_en.pdf', 'modifiedTime': 't-usdt'},
        ],
        'folder-bitcoin': [{'id': 'bitcoin-child', 'name': 'bitcoin_econ_v1_ko.pdf', 'modifiedTime': 't-btc-ko'}],
        'folder-bitcoin-cash': [{'id': 'bitcoin-cash-child', 'name': 'bitcoin-cash_econ_v1_ko.pdf', 'modifiedTime': 't-bch-ko'}],
    }
    folders_by_parent = {
        'root-econ': [
            {'id': 'folder-bitcoin', 'name': 'bitcoin'},
            {'id': 'folder-bitcoin-cash', 'name': 'bitcoin-cash'},
        ],
        'folder-bitcoin': [],
    }
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))

    projects = [
        {'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
        {'slug': 'bitcoin-cash', 'name': 'Bitcoin Cash', 'symbol': 'BCH'},
        {'slug': 'ethereum', 'name': 'Ethereum', 'symbol': 'ETH'},
        {'slug': 'ethena', 'name': 'Ethena', 'symbol': 'ENA'},
        {'slug': 'tether', 'name': 'Tether', 'symbol': 'USDT'},
    ]

    bitcoin_targets = list(ws._iter_targets(
        object(),
        ['econ'],
        filter_slug='bitcoin',
        projects=projects,
    ))

    ethereum_targets = list(ws._iter_targets(
        object(),
        ['econ'],
        filter_slug='ethereum',
        projects=projects,
    ))

    assert [(rtype, pdf['id']) for rtype, pdf in bitcoin_targets] == [
        ('econ', 'bitcoin-root'),
        ('econ', 'bitcoin-child'),
    ]
    assert ethereum_targets == []


def test_iter_targets_keeps_root_type_when_filename_has_no_type_token(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {
        'econ': 'root-econ',
        'mat': 'root-mat',
        'for': 'root-for',
    })
    pdfs_by_parent = {
        'root-mat': [{
            'id': 'ton-generic',
            'name': 'TON_Market_Report_en.pdf',
            'modifiedTime': 't-ton',
        }],
    }
    folders_by_parent = {
        'root-econ': [],
        'root-mat': [],
        'root-for': [],
    }
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))

    assert list(ws._iter_targets(object(), ['for'])) == []
    assert [(rtype, pdf['id']) for rtype, pdf in ws._iter_targets(object(), ['mat'])] == [
        ('mat', 'ton-generic'),
    ]


def test_iter_targets_excludes_legacy_report_pdfs_by_default(ws, monkeypatch):
    monkeypatch.setattr(ws, 'TYPE_FOLDER_IDS', {'econ': 'slide-econ'})
    monkeypatch.setattr(ws, '_legacy_reports_root_folders', lambda _service: [
        {'id': 'legacy-root', 'name': 'BCE Lab Reports'},
    ])
    folders_by_parent = {
        'slide-econ': [],
        'legacy-root': [
            {'id': 'folder-bch', 'name': 'bitcoin-cash'},
            {'id': 'folder-cardano', 'name': 'cardano'},
            {'id': 'folder-pi', 'name': 'pi-network'},
        ],
        'folder-bch': [{'id': 'folder-bch-econ', 'name': 'econ'}],
        'folder-cardano': [{'id': 'folder-cardano-econ', 'name': 'econ'}],
        'folder-pi': [{'id': 'folder-pi-econ', 'name': 'econ'}],
    }
    pdfs_by_parent = {
        'slide-econ': [],
        'folder-bch-econ': [{
            'id': 'drive-bch-en',
            'name': 'bitcoin-cash_econ_v1_en.pdf',
            'modifiedTime': 't-bch',
        }],
        'folder-cardano-econ': [{
            'id': 'drive-cardano-en',
            'name': 'cardano_econ_v1_en.pdf',
            'modifiedTime': 't-cardano',
        }],
        'folder-pi-econ': [{
            'id': 'drive-pi-en',
            'name': 'pi-network_econ_v1_en.pdf',
            'modifiedTime': 't-pi',
        }],
    }
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))

    assert list(ws._iter_targets(object(), ['econ'])) == []


def test_iter_legacy_report_targets_respects_slug_filter(ws, monkeypatch):
    monkeypatch.setattr(ws, '_legacy_reports_root_folders', lambda _service: [
        {'id': 'legacy-root', 'name': 'BCE Lab Reports'},
    ])
    folders_by_parent = {
        'legacy-root': [
            {'id': 'folder-bch', 'name': 'bitcoin-cash'},
            {'id': 'folder-cardano', 'name': 'cardano'},
            {'id': 'folder-pi', 'name': 'pi-network'},
        ],
        'folder-bch': [{'id': 'folder-bch-econ', 'name': 'econ'}],
        'folder-cardano': [{'id': 'folder-cardano-econ', 'name': 'econ'}],
        'folder-pi': [{'id': 'folder-pi-econ', 'name': 'econ'}],
    }
    pdfs_by_parent = {
        'folder-bch-econ': [{
            'id': 'drive-bch-en',
            'name': 'bitcoin-cash_econ_v1_en.pdf',
            'modifiedTime': 't-bch',
        }],
        'folder-cardano-econ': [{
            'id': 'drive-cardano-en',
            'name': 'cardano_econ_v1_en.pdf',
            'modifiedTime': 't-cardano',
        }],
        'folder-pi-econ': [{
            'id': 'drive-pi-en',
            'name': 'pi-network_econ_v1_en.pdf',
            'modifiedTime': 't-pi',
        }],
    }
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))

    targets = list(ws._iter_legacy_report_targets(object(), ['econ'], filter_slug='cardano'))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [
        ('econ', 'drive-cardano-en'),
    ]
    assert [pdf['source_path'] for _rtype, pdf in targets] == [
        'BCE Lab Reports/cardano/econ/cardano_econ_v1_en.pdf',
    ]
    assert {pdf['source_kind'] for _rtype, pdf in targets} == {'legacy_report'}
    assert [pdf['legacy_slug_hint'] for _rtype, pdf in targets] == ['cardano']


def test_iter_legacy_report_targets_can_scan_all_slugs_when_called_explicitly(ws, monkeypatch):
    monkeypatch.setattr(ws, '_legacy_reports_root_folders', lambda _service: [
        {'id': 'legacy-root', 'name': 'BCE Lab Reports'},
    ])
    folders_by_parent = {
        'legacy-root': [
            {'id': 'folder-bch', 'name': 'bitcoin-cash'},
            {'id': 'folder-cardano', 'name': 'cardano'},
            {'id': 'folder-pi', 'name': 'pi-network'},
        ],
        'folder-bch': [{'id': 'folder-bch-econ', 'name': 'econ'}],
        'folder-cardano': [{'id': 'folder-cardano-econ', 'name': 'econ'}],
        'folder-pi': [{'id': 'folder-pi-econ', 'name': 'econ'}],
    }
    pdfs_by_parent = {
        'folder-bch-econ': [{
            'id': 'drive-bch-en',
            'name': 'bitcoin-cash_econ_v1_en.pdf',
            'modifiedTime': 't-bch',
        }],
        'folder-cardano-econ': [{
            'id': 'drive-cardano-en',
            'name': 'cardano_econ_v1_en.pdf',
            'modifiedTime': 't-cardano',
        }],
        'folder-pi-econ': [{
            'id': 'drive-pi-en',
            'name': 'pi-network_econ_v1_en.pdf',
            'modifiedTime': 't-pi',
        }],
    }
    monkeypatch.setattr(ws, '_list_child_folders', lambda _service, parent_id: folders_by_parent.get(parent_id, []))
    monkeypatch.setattr(ws, '_list_pdfs_direct', lambda _service, parent_id: pdfs_by_parent.get(parent_id, []))

    targets = list(ws._iter_legacy_report_targets(object(), ['econ']))

    assert [(rtype, pdf['id']) for rtype, pdf in targets] == [
        ('econ', 'drive-bch-en'),
        ('econ', 'drive-cardano-en'),
        ('econ', 'drive-pi-en'),
    ]
    assert [pdf['source_path'] for _rtype, pdf in targets] == [
        'BCE Lab Reports/bitcoin-cash/econ/bitcoin-cash_econ_v1_en.pdf',
        'BCE Lab Reports/cardano/econ/cardano_econ_v1_en.pdf',
        'BCE Lab Reports/pi-network/econ/pi-network_econ_v1_en.pdf',
    ]
    assert {pdf['source_kind'] for _rtype, pdf in targets} == {'legacy_report'}
    assert [pdf['legacy_slug_hint'] for _rtype, pdf in targets] == [
        'bitcoin-cash',
        'cardano',
        'pi-network',
    ]


def test_process_rejects_file_id_filter(ws, monkeypatch):
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: {})

    with pytest.raises(ValueError, match='--file-id targets are disabled'):
        ws.process(
            ['econ'],
            filter_slug=None,
            filter_file_ids={'target-only'},
            dry_run=True,
            force=True,
        )


class _FakeDriveGet:
    def __init__(self, metadata):
        self.metadata = metadata

    def execute(self):
        return self.metadata


class _FakeDriveFiles:
    def __init__(self, metadata_by_id):
        self.metadata_by_id = metadata_by_id

    def get(self, fileId, **_kwargs):
        if fileId not in self.metadata_by_id:
            raise KeyError(fileId)
        return _FakeDriveGet(self.metadata_by_id[fileId])


class _FakeDriveService:
    def __init__(self, metadata_by_id):
        self.metadata_by_id = metadata_by_id

    def files(self):
        return _FakeDriveFiles(self.metadata_by_id)


def test_parse_source_draft_name_extracts_slug_type_version_lang(ws):
    parsed = ws._parse_source_draft_name('okx_econ_v1_en.md', {'econ'})

    assert parsed == {
        'slug': 'okx',
        'rtype': 'econ',
        'version': 1,
        'lang': 'en',
    }


def test_source_slide_diagnostics_flags_source_without_publishable_slide(ws):
    source_records = [
        {
            'id': 'source-okx-en',
            'slug': 'okx',
            'rtype': 'econ',
            'lang': 'en',
            'source_path': 'BCE Research Source Drafts/okx_econ_v1_en.md',
        },
        {
            'id': 'source-near-en',
            'slug': 'near',
            'rtype': 'econ',
            'lang': 'en',
            'source_path': 'BCE Research Source Drafts/near_econ_v1_en.md',
        },
    ]
    scanned = [
        {
            'rtype': 'econ',
            'slug': 'near',
            'status': 'unchanged',
        },
    ]

    diagnostics = ws.build_source_slide_diagnostics(source_records, scanned, [])

    assert diagnostics == [{
        'rtype': 'econ',
        'slug': 'okx',
        'lang': 'en',
        'status': 'source_waiting_for_slide_pdf',
        'source_path': 'BCE Research Source Drafts/okx_econ_v1_en.md',
        'source_file_id': 'source-okx-en',
        'message': 'source draft exists but no publishable active Slide PDF was found',
    }]


def test_validates_sudden_mover_handoff_contract_for_same_slug_type_and_lang(ws):
    contract = {
        'registration': {
            'tables': {
                'project_reports': {
                    'report_type': 'forensic',
                },
            },
        },
        'human_source_request': {
            'draft_name': 'solana_for_v1_en.md',
            'required_slug': 'solana',
            'required_rtype': 'for',
            'required_report_type': 'forensic',
            'required_lang': 'en',
        },
        'slide_intake': {
            'args': ['--type', 'for', '--slug', 'solana'],
            'expected_db_report_type': 'forensic',
            'expected_source_draft_name': 'solana_for_v1_en.md',
        },
    }

    assert ws.validate_source_slide_handoff_contract(contract) == {
        'status': 'ok',
        'source_draft': {
            'slug': 'solana',
            'rtype': 'for',
            'version': 1,
            'lang': 'en',
        },
        'db_report_type': 'forensic',
        'watcher_args': ['--type', 'for', '--slug', 'solana'],
    }


def test_handoff_contract_guard_rejects_slug_mismatch(ws):
    contract = {
        'registration': {
            'tables': {
                'project_reports': {
                    'report_type': 'forensic',
                },
            },
        },
        'human_source_request': {
            'draft_name': 'solana_for_v1_en.md',
            'required_slug': 'near',
            'required_rtype': 'for',
            'required_report_type': 'forensic',
            'required_lang': 'en',
        },
        'slide_intake': {
            'args': ['--type', 'for', '--slug', 'near'],
            'expected_db_report_type': 'forensic',
        },
    }

    result = ws.validate_source_slide_handoff_contract(contract)

    assert result['status'] == 'failed'
    assert result['code'] == 'handoff_contract_mismatch'
    assert {'field': 'slug', 'draft': 'solana', 'expected': 'near'} in result['mismatches']
    assert {'field': 'watcher_args.slug', 'draft': 'solana', 'expected': 'near'} in result['mismatches']


def test_legacy_report_portrait_pdf_records_slug_hint_and_skip(ws, monkeypatch):
    saved = []

    monkeypatch.setitem(
        sys.modules,
        'supabase_storage',
        SimpleNamespace(
            ensure_bucket=lambda *_args, **_kwargs: None,
            get_supabase_storage_client=lambda: object(),
        ),
    )
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: {})
    monkeypatch.setattr(ws, '_save_manifest', lambda data: saved.append({k: dict(v) for k, v in data.items()}))
    monkeypatch.setattr(ws, '_load_tracked_projects', lambda _sb: [
        {'id': 'project-cardano', 'slug': 'cardano', 'name': 'Cardano', 'symbol': 'ADA'},
    ])
    monkeypatch.setattr(ws, '_iter_targets', lambda _service, _types, **_kwargs: [
        ('econ', {
            'id': 'drive-cardano-en',
            'name': 'cardano_econ_v1_en.pdf',
            'modifiedTime': 't-cardano',
            'parent_folder_id': 'folder-cardano-econ',
            'parent_folder_name': 'econ',
            'source_path': 'BCE Lab Reports/cardano/econ/cardano_econ_v1_en.pdf',
            'source_depth': 2,
            'source_kind': 'legacy_report',
            'legacy_slug_hint': 'cardano',
        }),
    ])
    monkeypatch.setattr(ws, '_download_file', lambda *_args: None)
    monkeypatch.setattr(ws, '_pdf_page_profile', lambda _path: {
        'page_count': 25,
        'width': 595,
        'height': 842,
        'aspect_ratio': 0.707,
        'is_landscape_slide': False,
    })

    scanned, processed = ws.process(
        ['econ'],
        filter_slug='cardano',
        dry_run=False,
        force=False,
    )

    assert processed == []
    assert scanned == [{
        'rtype': 'econ',
        'slug': 'cardano',
        'lang': None,
        'status': 'no_active_slide_pdf_for_slug',
        'error': 'active_slide_pdf_missing',
        'source_path': 'Slide/econ',
        'source_kind': 'active_slide_diagnostic',
    }, {
        'rtype': 'econ',
        'file_id': 'drive-cardano-en',
        'name': 'cardano_econ_v1_en.pdf',
        'modifiedTime': 't-cardano',
        'size': None,
        'parent_folder_id': 'folder-cardano-econ',
        'parent_folder_name': 'econ',
        'source_path': 'BCE Lab Reports/cardano/econ/cardano_econ_v1_en.pdf',
        'source_depth': 2,
        'source_kind': 'legacy_report',
        'legacy_slug_hint': 'cardano',
        'slug': 'cardano',
        'lang': 'en',
        'status': 'skipped_legacy_portrait_pdf',
    }]
    assert saved[-1]['drive-cardano-en']['status'] == 'skipped_legacy_portrait_pdf'
    assert saved[-1]['drive-cardano-en']['slug'] == 'cardano'
    assert saved[-1]['drive-cardano-en']['lang'] == 'en'
    assert saved[-1]['drive-cardano-en']['source_path'] == (
        'BCE Lab Reports/cardano/econ/cardano_econ_v1_en.pdf'
    )


def test_unchanged_published_with_verified_landscape_profile_skips_download(ws, monkeypatch):
    manifest = {
        'file-en': {
            'status': 'published',
            'modifiedTime': 't0',
            'slug': 'bitcoin',
            'lang': 'en',
            'lang_source': 'filename',
            'report_id': 'report-1',
            'public_url': 'https://storage/slide.html',
            'page_profile': {
                'page_count': 12,
                'width': 1376,
                'height': 768,
                'aspect_ratio': 1.791,
                'is_landscape_slide': True,
            },
        },
    }
    saved = []
    prune_calls = []

    monkeypatch.setitem(
        sys.modules,
        'supabase_storage',
        SimpleNamespace(
            ensure_bucket=lambda *_args, **_kwargs: None,
            get_supabase_storage_client=lambda: object(),
        ),
    )
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: manifest)
    monkeypatch.setattr(ws, '_save_manifest', lambda data: saved.append({k: dict(v) for k, v in data.items()}))
    monkeypatch.setattr(ws, '_load_tracked_projects', lambda _sb: [
        {'id': 'project-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
    ])
    monkeypatch.setattr(ws, '_iter_targets', lambda _service, _types, **_kwargs: [
        ('econ', {'id': 'file-en', 'name': 'Bitcoin_Cryptoeconomic_Blueprint_en.pdf', 'modifiedTime': 't0'}),
    ])
    monkeypatch.setattr(ws, '_download_file', lambda *_args: pytest.fail('unchanged verified landscape should not download'))
    monkeypatch.setattr(ws, '_merge_slide_url', lambda *_args: None)
    monkeypatch.setattr(ws, '_prune_stale_languages_for_pair', lambda *_args, **kwargs: prune_calls.append(kwargs) or [])

    scanned, processed = ws.process(
        ['econ'],
        filter_slug='bitcoin',
        dry_run=False,
        force=False,
    )

    assert processed == []
    assert scanned[-1]['status'] == 'unchanged'
    assert saved[-1]['file-en']['page_profile']['is_landscape_slide'] is True
    assert prune_calls[0]['current_langs'] == {'en'}


def test_unchanged_published_missing_public_url_reprocesses_slide(ws, monkeypatch):
    manifest = {
        'file-en': {
            'status': 'published',
            'modifiedTime': 't0',
            'slug': 'bitcoin',
            'lang': 'en',
            'lang_source': 'filename',
            'report_id': 'report-1',
            'page_profile': {
                'page_count': 12,
                'width': 1376,
                'height': 768,
                'aspect_ratio': 1.791,
                'is_landscape_slide': True,
            },
        },
    }
    saved = []
    downloaded = []
    merged = []
    pruned = []

    monkeypatch.setitem(
        sys.modules,
        'supabase_storage',
        SimpleNamespace(
            ensure_bucket=lambda *_args, **_kwargs: None,
            get_supabase_storage_client=lambda: object(),
        ),
    )
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: manifest)
    monkeypatch.setattr(ws, '_save_manifest', lambda data: saved.append({k: dict(v) for k, v in data.items()}))
    monkeypatch.setattr(ws, '_load_tracked_projects', lambda _sb: [
        {'id': 'project-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
    ])
    monkeypatch.setattr(ws, '_iter_targets', lambda _service, _types, **_kwargs: [
        ('econ', {'id': 'file-en', 'name': 'Bitcoin_Cryptoeconomic_Blueprint_en.pdf', 'modifiedTime': 't0'}),
    ])
    monkeypatch.setattr(ws, '_download_file', lambda *_args: downloaded.append(True))
    monkeypatch.setattr(ws, '_pdf_page_profile', lambda _path: {
        'page_count': 12,
        'width': 1376,
        'height': 768,
        'aspect_ratio': 1.791,
        'is_landscape_slide': True,
    })
    monkeypatch.setattr(ws, '_extract_pdf_meta_and_text', lambda _path: ({}, 'Bitcoin BTC settlement network ' * 20))
    monkeypatch.setattr(ws, '_resolve_slug', lambda *_args: (
        {'id': 'project-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
        'filename',
    ))
    monkeypatch.setattr(ws, '_resolve_lang', lambda *_args: ('en', 'filename'))
    monkeypatch.setattr(
        ws,
        '_find_report_for_lang',
        lambda *_args: ('report-1', 1, ws.PUBLICATION_APPROVED_STATUS),
    )
    monkeypatch.setattr(ws, '_find_analysis_source_for_slide', lambda *_args, **_kwargs: object())
    monkeypatch.setattr(ws, '_generate_summary_after_slide_publish', lambda *_args, **_kwargs: True)
    monkeypatch.setattr(ws, '_convert_and_upload', lambda *_args, **_kwargs: {
        'latest_url': 'https://storage/econ/bitcoin/latest/en.html',
        'versioned_url': 'https://storage/econ/bitcoin/1/en.html',
    })
    monkeypatch.setattr(
        ws,
        '_merge_slide_url',
        lambda _sb, report_id, lang, public_url, **kwargs: merged.append(
            (report_id, lang, public_url, kwargs.get('status'))
        ),
    )
    monkeypatch.setattr(ws, '_prune_stale_languages_for_pair', lambda *_args, **kwargs: pruned.append(kwargs) or [])

    scanned, processed = ws.process(
        ['econ'],
        filter_slug='bitcoin',
        dry_run=False,
        force=False,
    )

    assert downloaded == [True]
    assert scanned[-1].get('status') != 'unchanged'
    assert processed[-1]['status'] == 'published'
    assert processed[-1]['public_url'] == 'https://storage/econ/bitcoin/latest/en.html'
    assert merged == [('report-1', 'en', 'https://storage/econ/bitcoin/latest/en.html', ws.PUBLICATION_PUBLISHED_STATUS)]
    assert saved[-1]['file-en']['public_url'] == 'https://storage/econ/bitcoin/latest/en.html'
    assert pruned[0]['current_langs'] == {'en'}


def test_unchanged_manifest_repair_creates_missing_report_shell(ws, monkeypatch):
    calls = []
    monkeypatch.setattr(ws, '_find_report_for_lang', lambda *_args: (None, None, None))

    def fake_create(_sb, **kwargs):
        calls.append(kwargs)
        return 'report-created', kwargs['version'] or 1

    monkeypatch.setattr(ws, '_create_report_row_for_slide', fake_create)

    report_id, version, status = ws._repair_unchanged_manifest_publication(
        object(),
        rtype='econ',
        project={'id': 'project-bitcoin', 'slug': 'bitcoin'},
        slug='bitcoin',
        lang='en',
        public_url='https://storage/econ/bitcoin/latest/en.html',
        pdf_file_id='drive-file-id',
        pdf_name='Bitcoin_Cryptoeconomic_Blueprint_en.pdf',
        version=None,
    )

    assert report_id == 'report-created'
    assert version == 1
    assert status == 'published_created'
    assert calls[0]['project_id'] == 'project-bitcoin'
    assert calls[0]['db_type'] == 'econ'
    assert calls[0]['public_url'] == 'https://storage/econ/bitcoin/latest/en.html'
    assert calls[0]['status'] == ws.PUBLICATION_PUBLISHED_STATUS


def test_file_id_filtered_unchanged_run_is_rejected(ws, monkeypatch):
    manifest = {
        'file-en': {
            'status': 'published',
            'modifiedTime': 't0',
            'slug': 'tether',
            'lang': 'en',
            'lang_source': 'filename',
            'report_id': 'report-1',
            'public_url': 'https://storage/slide.html',
            'page_profile': {
                'page_count': 12,
                'width': 1376,
                'height': 768,
                'aspect_ratio': 1.791,
                'is_landscape_slide': True,
            },
        },
    }

    monkeypatch.setitem(
        sys.modules,
        'supabase_storage',
        SimpleNamespace(
            ensure_bucket=lambda *_args, **_kwargs: None,
            get_supabase_storage_client=lambda: object(),
        ),
    )
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: manifest)
    monkeypatch.setattr(ws, '_save_manifest', lambda _data: None)
    monkeypatch.setattr(ws, '_load_tracked_projects', lambda _sb: [
        {'id': 'project-tether', 'slug': 'tether', 'name': 'Tether', 'symbol': 'USDT'},
    ])
    with pytest.raises(ValueError, match='--file-id targets are disabled'):
        ws.process(
            ['econ'],
            filter_slug='tether',
            filter_file_ids={'file-en'},
            dry_run=False,
            force=False,
        )


def test_unresolved_stale_file_clears_previous_publication_metadata(ws, monkeypatch):
    manifest = {
        'file-zh': {
            'status': 'published',
            'modifiedTime': 'old',
            'slug': 'ripple',
            'lang': 'en',
            'report_id': 'report-ripple',
            'public_url': 'https://storage/econ/ripple/latest/en.html',
            'versioned_url': 'https://storage/econ/ripple/1/en.html',
            'version': 1,
        },
    }
    saved = []

    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: manifest)
    monkeypatch.setattr(ws, '_save_manifest', lambda data: saved.append({k: dict(v) for k, v in data.items()}))
    monkeypatch.setattr(ws, '_iter_targets', lambda _service, _types, **_kwargs: [
        ('econ', {'id': 'file-zh', 'name': 'XRPL_Cryptoeconomic_Blueprint_cn.pdf', 'modifiedTime': 'new'}),
    ])
    monkeypatch.setattr(ws, '_download_file', lambda *_args: None)
    monkeypatch.setattr(ws, '_pdf_page_profile', lambda _path: {
        'page_count': 12,
        'width': 1376,
        'height': 768,
        'aspect_ratio': 1.791,
        'is_landscape_slide': True,
    })
    monkeypatch.setattr(ws, '_extract_pdf_meta_and_text', lambda _path: ({}, ''))
    monkeypatch.setattr(ws, '_resolve_slug', lambda *_args: (None, 'none'))
    monkeypatch.setattr(ws, '_resolve_lang', lambda *_args: ('zh', 'filename'))

    _scanned, processed = ws.process(
        ['econ'],
        filter_slug=None,
        dry_run=True,
        force=True,
    )

    assert processed[0]['status'] == 'unresolved'
    assert saved[-1]['file-zh']['status'] == 'unresolved'
    assert saved[-1]['file-zh']['public_url'] is None
    assert saved[-1]['file-zh']['versioned_url'] is None
    assert saved[-1]['file-zh']['report_id'] is None
    assert saved[-1]['file-zh']['version'] is None


def test_unchanged_published_missing_page_profile_rechecks_and_cleans_portrait(ws, monkeypatch):
    manifest = {
        'file-en': {
            'status': 'published',
            'modifiedTime': 't0',
            'slug': 'tether',
            'lang': 'en',
            'lang_source': 'filename',
            'report_id': 'report-tether',
            'public_url': 'https://storage/econ/tether/latest/en.html',
        },
    }
    saved = []
    removed = []

    monkeypatch.setitem(
        sys.modules,
        'supabase_storage',
        SimpleNamespace(
            ensure_bucket=lambda *_args, **_kwargs: None,
            get_supabase_storage_client=lambda: object(),
        ),
    )
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: manifest)
    monkeypatch.setattr(ws, '_save_manifest', lambda data: saved.append({k: dict(v) for k, v in data.items()}))
    monkeypatch.setattr(ws, '_load_tracked_projects', lambda _sb: [
        {'id': 'project-tether', 'slug': 'tether', 'name': 'Tether', 'symbol': 'USDT'},
    ])
    monkeypatch.setattr(ws, '_iter_targets', lambda _service, _types, **_kwargs: [
        ('econ', {'id': 'file-en', 'name': 'Tether_Cryptoeconomic_Blueprint_cn2.pdf', 'modifiedTime': 't0'}),
    ])

    def fake_download(_service, _file_id, dest_path):
        import fitz

        doc = fitz.open()
        doc.new_page(width=595, height=842)
        doc.save(dest_path)
        doc.close()

    def fake_remove(_sb, report_id, lang, public_url):
        removed.append((report_id, lang, public_url))
        return True

    monkeypatch.setattr(ws, '_download_file', fake_download)
    monkeypatch.setattr(ws, '_remove_slide_url_if_matches', fake_remove)

    scanned, processed = ws.process(
        ['econ'],
        filter_slug='tether',
        dry_run=False,
        force=False,
    )

    assert processed == []
    assert scanned == [{
        'rtype': 'econ',
        'file_id': 'file-en',
        'name': 'Tether_Cryptoeconomic_Blueprint_cn2.pdf',
        'modifiedTime': 't0',
        'size': None,
        'parent_folder_id': None,
        'parent_folder_name': None,
        'source_path': None,
        'source_depth': None,
        'slug': 'tether',
        'lang': 'en',
        'status': 'skipped_legacy_portrait_pdf',
    }]
    assert removed == [('report-tether', 'en', 'https://storage/econ/tether/latest/en.html')]
    assert saved[-1]['file-en']['status'] == 'skipped_legacy_portrait_pdf'
    assert saved[-1]['file-en']['page_profile']['is_landscape_slide'] is False
    assert saved[-1]['file-en']['stale_url_removed'] is True


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


class _FakeProjectReportsPruneTable:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}
        self.patch = None

    def select(self, *_args):
        return self

    def update(self, patch):
        self.patch = patch
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def execute(self):
        matched = [
            row for row in self.rows
            if all(row.get(key) == value for key, value in self.filters.items())
        ]
        if self.patch is not None:
            for row in matched:
                row.update(self.patch)
            return _FakeExecuteResult(matched)
        return _FakeExecuteResult(matched)


class _FakePruneSupabase:
    def __init__(self, rows):
        self.project_reports = _FakeProjectReportsPruneTable(rows)

    def table(self, name):
        assert name == 'project_reports'
        return self.project_reports


class _FakeStorageBucket:
    def __init__(self):
        self.removed = []

    def remove(self, keys):
        self.removed.extend(keys)
        return None


class _FakeStorageRoot:
    def __init__(self):
        self.bucket = _FakeStorageBucket()

    def from_(self, bucket_name):
        assert bucket_name == 'slides'
        return self.bucket


class _FakeStorageClient:
    def __init__(self):
        self.storage = _FakeStorageRoot()


class _FakeReconcileExecuteResult:
    def __init__(self, data):
        self.data = data


class _FakeReconcileTable:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}
        self.patch = None
        self.range_bounds = None
        self.upsert_payload = None
        self.on_conflict = None

    def select(self, *_args):
        return self

    def upsert(self, payload, on_conflict=None):
        self.upsert_payload = payload
        self.on_conflict = on_conflict
        return self

    def range(self, start, end):
        self.range_bounds = (start, end)
        return self

    def update(self, patch):
        self.patch = patch
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def execute(self):
        if self.upsert_payload is not None:
            row = {**self.upsert_payload, 'id': f"created-{len(self.rows) + 1}"}
            self.rows.append(row)
            return _FakeReconcileExecuteResult([row])
        matched = [
            row for row in self.rows
            if all(row.get(key) == value for key, value in self.filters.items())
        ]
        if self.patch is not None:
            for row in matched:
                row.update(self.patch)
            return _FakeReconcileExecuteResult(matched)
        if self.range_bounds:
            start, end = self.range_bounds
            matched = matched[start:end + 1]
        return _FakeReconcileExecuteResult(matched)


class _FakeReconcileSupabase:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        assert name in self.tables
        return _FakeReconcileTable(self.tables[name])


class _FakeMergeTable:
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
        return _FakeExecuteResult(self.row)


class _FakeMergeSupabase:
    def __init__(self, report_row, project_row):
        self.project_reports = _FakeMergeTable(report_row)
        self.tracked_projects = _FakeMergeTable(project_row)

    def table(self, name):
        if name == 'project_reports':
            return self.project_reports
        if name == 'tracked_projects':
            return self.tracked_projects
        raise AssertionError(f'unexpected table {name}')


class _FakeCreateReportTable:
    def __init__(self, row_id='report-created'):
        self.row_id = row_id
        self.upsert_payload = None

    def upsert(self, payload, on_conflict=None):
        self.upsert_payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        return _FakeExecuteResult([{**self.upsert_payload, 'id': self.row_id}])


class _FakeCreateTrackedProjectsTable:
    def __init__(self):
        self.patch = None
        self.filters = []

    def update(self, patch):
        self.patch = patch
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def execute(self):
        return _FakeExecuteResult([self.patch or {}])


class _FakeCreateReportSupabase:
    def __init__(self):
        self.project_reports = _FakeCreateReportTable()
        self.tracked_projects = _FakeCreateTrackedProjectsTable()

    def table(self, name):
        if name == 'project_reports':
            return self.project_reports
        if name == 'tracked_projects':
            return self.tracked_projects
        raise AssertionError(f'unexpected table {name}')


def test_create_report_row_for_slide_upserts_missing_report_shell(ws):
    sb = _FakeCreateReportSupabase()

    report_id, version = ws._create_report_row_for_slide(
        sb,
        project_id='project-shib',
        db_type='econ',
        slug='shiba-inu',
        lang='ko',
        pdf_file_id='drive-pdf-id',
        pdf_name='Shiba_Inu_Cryptoeconomic_Analysis_ko.pdf',
        public_url='https://storage/slides/econ/shiba-inu/latest/ko.html',
        version=None,
        project_name='Shiba Inu',
    )

    payload = sb.project_reports.upsert_payload
    assert report_id == 'report-created'
    assert version == 1
    assert sb.project_reports.on_conflict == 'project_id,report_type,version,language'
    assert payload['project_id'] == 'project-shib'
    assert payload['report_type'] == 'econ'
    assert payload['language'] == 'ko'
    assert payload['status'] == ws.PUBLICATION_PUBLISHED_STATUS
    assert payload['review_at'] is None
    assert payload['published_at']
    assert payload['gdrive_file_id'] == 'drive-pdf-id'
    assert payload['gdrive_urls_by_lang'] == {
        'ko': 'https://drive.google.com/file/d/drive-pdf-id/view?usp=drivesdk',
    }
    assert payload['slide_html_urls_by_lang'] == {
        'ko': 'https://storage/slides/econ/shiba-inu/latest/ko.html',
    }
    assert payload['cover_image_urls_by_lang'] == {}
    assert payload['card_data']['slug'] == 'shiba-inu'
    assert payload['title_ko'] == 'Shiba Inu'
    assert sb.tracked_projects.patch is not None


def test_merge_slide_url_updates_publish_metadata_and_project_timestamp(ws):
    report = {
        'project_id': 'project-avalanche',
        'report_type': 'econ',
        'slide_html_urls_by_lang': {'ko': 'https://storage/old-ko.html'},
        'cover_image_urls_by_lang': {'ko': 'https://storage/old-ko-cover.png'},
        'card_data': {'summary': 'Avalanche summary', 'generated_at': '2026-04-16T00:00:00Z'},
        'published_at': '2026-04-16T12:29:22Z',
    }
    project = {
        'id': 'project-avalanche',
        'last_econ_report_at': '2026-04-13T11:32:40Z',
    }
    sb = _FakeMergeSupabase(report, project)
    publish_ts = '2026-05-02T09:06:00+00:00'

    ws._merge_slide_url(
        sb,
        'report-avalanche',
        'en',
        'https://storage/econ/avalanche-2/latest/en.html',
        status=ws.PUBLICATION_PUBLISHED_STATUS,
        cover_url='https://storage/econ/avalanche-2/latest/en-cover.png',
        published_at=publish_ts,
    )

    assert report['slide_html_urls_by_lang']['en'] == 'https://storage/econ/avalanche-2/latest/en.html'
    assert report['cover_image_urls_by_lang']['ko'] == 'https://storage/old-ko-cover.png'
    assert report['cover_image_urls_by_lang']['en'] == 'https://storage/econ/avalanche-2/latest/en-cover.png'
    assert report['published_at'] == publish_ts
    assert report['updated_at'] == publish_ts
    assert report['card_data']['generated_at'] == publish_ts
    assert report['card_data']['summary'] == 'Avalanche summary'
    assert project['last_econ_report_at'] == publish_ts
    assert project['updated_at'] == publish_ts


def test_extract_maturity_score_from_analysis_markdown(ws):
    text = """
    # Hyperliquid MAT

    **Maturity Score: 85.0 | Stage: ESTABLISHED**
    """

    assert ws._extract_maturity_score_from_text(text) == 85.0
    assert ws._extract_maturity_stage_from_text(text, 85.0) == 'established'


def test_extract_maturity_score_from_korean_summary_forms(ws):
    assert ws._extract_maturity_score_from_text('종합 점수 82.6% 기준 Aave는 성숙 서사 구간이다.') == 82.6
    assert ws._extract_maturity_score_from_text('**최종 판정:** 전개 서사 단계, 종합 성숙도 57.4 / 100') == 57.4


def test_persist_maturity_score_from_source_updates_tracked_project(ws):
    class Source:
        name = 'hyperliquid_mat_v1_en.md'
        text = '**Overall Maturity Score: 85.0**\n\nStage: Established\n'

    report = {'project_id': 'project-hype', 'report_type': 'maturity'}
    project = {'id': 'project-hype', 'slug': 'hyperliquid'}
    sb = _FakeMergeSupabase(report, project)

    persisted = ws._persist_maturity_score_from_source(
        sb,
        project=project,
        source=Source(),
    )

    assert persisted is True
    assert project['maturity_score'] == 85.0
    assert project['maturity_stage'] == 'established'
    assert project['updated_at']


def test_summary_generation_overwrites_stale_cross_project_card_identity(ws, monkeypatch):
    class Source:
        name = 'ethereum_mat_v4_ko.md'
        drive_file_id = 'source-ethereum'
        report_type = 'mat'
        db_report_type = 'maturity'
        version = 4
        lang = 'ko'
        modified_time = '2026-05-25T00:00:00Z'
        text = '# Ethereum MAT\n\nEthereum maturity summary.'

    def fake_patch(source, translate=True):
        assert source.name == 'ethereum_mat_v4_ko.md'
        return {
            'card_summary_ko': 'Ethereum summary text',
            'card_data': {
                'summary': 'Ethereum summary text',
                'source_md': {
                    'name': source.name,
                    'slug': 'lido-dao',
                    'report_type': 'mat',
                    'version': 3,
                    'language': 'ko',
                    'drive_file_id': source.drive_file_id,
                },
            },
        }

    monkeypatch.setitem(
        sys.modules,
        'marketing_content_pipeline',
        type('FakeMarketingModule', (), {
            'build_project_report_patch_from_drive_source': staticmethod(fake_patch),
        }),
    )
    report = {
        'project_id': 'project-ethereum',
        'report_type': 'maturity',
        'card_data': {
            'slug': 'lido-dao',
            'source_md': {'slug': 'lido-dao'},
        },
    }
    project = {
        'id': 'project-ethereum',
        'slug': 'ethereum',
        'name': 'Ethereum',
    }
    sb = _FakeMergeSupabase(report, project)

    generated = ws._generate_summary_after_slide_publish(
        sb,
        None,
        project=project,
        rtype='mat',
        report_id='report-ethereum-mat',
        version=4,
        source=Source(),
    )

    assert generated is True
    assert report['title_ko'] == 'Ethereum'
    assert report['card_summary_ko'] == 'Ethereum summary text'
    assert report['card_data']['slug'] == 'ethereum'
    assert report['card_data']['report_type'] == 'maturity'
    assert report['card_data']['source_md']['slug'] == 'ethereum'
    assert report['card_data']['source_md']['version'] == 4


def test_prune_stale_languages_removes_db_json_and_latest_storage(ws):
    rows = [{
        'id': 'report-1',
        'project_id': 'project-bitcoin',
        'report_type': 'econ',
        'gdrive_urls_by_lang': {
            'ko': 'drive-ko',
            'en': 'drive-en',
            'ja': 'drive-ja',
            'zh': 'drive-zh',
            'de': 'drive-de',
            'es': 'drive-es',
            'fr': 'drive-fr',
        },
        'slide_html_urls_by_lang': {
            'ko': 'slide-ko',
            'en': 'slide-en',
            'ja': 'slide-ja',
            'zh': 'slide-zh',
            'de': 'slide-de',
            'es': 'slide-es',
            'fr': 'slide-fr',
        },
    }]
    storage = _FakeStorageClient()

    results = ws._prune_stale_languages_for_pair(
        _FakePruneSupabase(rows),
        storage,
        rtype='econ',
        slug='bitcoin',
        project_id='project-bitcoin',
        current_langs={'ko', 'en', 'ja', 'zh'},
        dry_run=False,
    )

    assert rows[0]['gdrive_urls_by_lang'] == {
        'ko': 'drive-ko',
        'en': 'drive-en',
        'ja': 'drive-ja',
        'zh': 'drive-zh',
    }
    assert rows[0]['slide_html_urls_by_lang'] == {
        'ko': 'slide-ko',
        'en': 'slide-en',
        'ja': 'slide-ja',
        'zh': 'slide-zh',
    }
    assert storage.storage.bucket.removed == [
        'econ/bitcoin/latest/de.html',
        'econ/bitcoin/latest/es.html',
        'econ/bitcoin/latest/fr.html',
    ]
    assert {result['status'] for result in results} == {
        'pruned_stale_languages',
        'pruned_stale_storage',
    }


def test_prune_stale_languages_dry_run_does_not_mutate_db_or_storage(ws):
    rows = [{
        'id': 'report-1',
        'project_id': 'project-bitcoin',
        'report_type': 'econ',
        'gdrive_urls_by_lang': {'ko': 'drive-ko', 'de': 'drive-de'},
        'slide_html_urls_by_lang': {'ko': 'slide-ko', 'de': 'slide-de'},
    }]
    storage = _FakeStorageClient()

    results = ws._prune_stale_languages_for_pair(
        _FakePruneSupabase(rows),
        storage,
        rtype='econ',
        slug='bitcoin',
        project_id='project-bitcoin',
        current_langs={'ko'},
        dry_run=True,
    )

    assert rows[0]['gdrive_urls_by_lang'] == {'ko': 'drive-ko', 'de': 'drive-de'}
    assert rows[0]['slide_html_urls_by_lang'] == {'ko': 'slide-ko', 'de': 'slide-de'}
    assert storage.storage.bucket.removed == []
    assert {result['status'] for result in results} == {
        'dry_run_prune',
        'dry_run_prune_storage',
    }


def test_prune_stale_languages_skips_empty_current_language_set(ws):
    rows = [{
        'id': 'report-1',
        'project_id': 'project-bitcoin',
        'report_type': 'econ',
        'gdrive_urls_by_lang': {'de': 'drive-de'},
        'slide_html_urls_by_lang': {'de': 'slide-de'},
    }]
    storage = _FakeStorageClient()

    results = ws._prune_stale_languages_for_pair(
        _FakePruneSupabase(rows),
        storage,
        rtype='econ',
        slug='bitcoin',
        project_id='project-bitcoin',
        current_langs=set(),
        dry_run=False,
    )

    assert rows[0]['gdrive_urls_by_lang'] == {'de': 'drive-de'}
    assert rows[0]['slide_html_urls_by_lang'] == {'de': 'slide-de'}
    assert storage.storage.bucket.removed == []
    assert results == [{
        'rtype': 'econ',
        'slug': 'bitcoin',
        'lang': None,
        'status': 'prune_skipped_no_publishable_pdf',
        'error': 'no current publishable PDFs',
    }]


def test_db_reconcile_cancels_visible_rows_absent_from_active_drive(ws, monkeypatch):
    projects = [
        {'id': 'project-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
        {'id': 'project-polygon', 'slug': 'matic-network', 'name': 'Polygon', 'symbol': 'MATIC'},
    ]
    tables = {
        'project_reports': [
            {
                'id': 'report-bitcoin-en',
                'project_id': 'project-bitcoin',
                'report_type': 'econ',
                'language': 'en',
                'status': 'published',
                'published_at': '2026-05-01T00:00:00Z',
                'updated_at': '2026-05-01T00:00:00Z',
                'created_at': '2026-05-01T00:00:00Z',
                'slide_html_urls_by_lang': {'en': 'https://storage/econ/bitcoin/latest/en.html'},
            },
            {
                'id': 'report-polygon-en',
                'project_id': 'project-polygon',
                'report_type': 'econ',
                'language': 'en',
                'status': 'published',
                'published_at': '2026-04-01T00:00:00Z',
                'updated_at': '2026-04-01T00:00:00Z',
                'created_at': '2026-04-01T00:00:00Z',
                'slide_html_urls_by_lang': {'en': 'https://storage/econ/matic-network/latest/en.html'},
            },
        ],
        'tracked_projects': [
            {
                'id': 'project-bitcoin',
                'slug': 'bitcoin',
                'last_econ_report_at': '2026-04-30T00:00:00Z',
                'last_maturity_report_at': None,
                'last_forensic_report_at': None,
            },
            {
                'id': 'project-polygon',
                'slug': 'matic-network',
                'last_econ_report_at': '2026-04-01T00:00:00Z',
                'last_maturity_report_at': None,
                'last_forensic_report_at': None,
            },
        ],
    }
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [
        ('econ', {'name': 'Bitcoin_Cryptoeconomic_Blueprint_en.pdf', 'source_path': 'Slide/econ'}),
    ])

    results = ws._reconcile_visible_reports_with_drive(
        _FakeReconcileSupabase(tables),
        object(),
        types=['econ'],
        projects=projects,
        dry_run=False,
    )

    assert tables['project_reports'][0]['status'] == 'published'
    assert tables['project_reports'][1]['status'] == 'cancelled'
    assert tables['tracked_projects'][0]['last_econ_report_at'] == '2026-05-01T00:00:00Z'
    assert tables['tracked_projects'][1]['last_econ_report_at'] is None
    assert {row['status'] for row in results} == {
        'db_reconcile_cancelled',
        'db_reconcile_timestamp_synced',
        'db_reconcile_timestamp_cleared',
    }


def test_db_reconcile_dry_run_does_not_mutate_rows(ws, monkeypatch):
    projects = [
        {'id': 'project-polygon', 'slug': 'matic-network', 'name': 'Polygon', 'symbol': 'MATIC'},
    ]
    tables = {
        'project_reports': [{
            'id': 'report-polygon-en',
            'project_id': 'project-polygon',
            'report_type': 'econ',
            'language': 'en',
            'status': 'published',
            'published_at': '2026-04-01T00:00:00Z',
            'updated_at': '2026-04-01T00:00:00Z',
            'created_at': '2026-04-01T00:00:00Z',
            'slide_html_urls_by_lang': {'en': 'https://storage/econ/matic-network/latest/en.html'},
        }],
        'tracked_projects': [{
            'id': 'project-polygon',
            'slug': 'matic-network',
            'last_econ_report_at': '2026-04-01T00:00:00Z',
            'last_maturity_report_at': None,
            'last_forensic_report_at': None,
        }],
    }
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [])

    results = ws._reconcile_visible_reports_with_drive(
        _FakeReconcileSupabase(tables),
        object(),
        types=['econ'],
        projects=projects,
        dry_run=True,
    )

    assert tables['project_reports'][0]['status'] == 'published'
    assert tables['tracked_projects'][0]['last_econ_report_at'] == '2026-04-01T00:00:00Z'
    assert {row['status'] for row in results} == {
        'dry_run_db_reconcile_cancel',
        'dry_run_db_reconcile_timestamp_clear',
    }


def test_db_reconcile_for_rows_without_active_slide_pdf_are_classified_as_missing_active_slide_pdf(ws, monkeypatch):
    projects = [
        {'id': 'project-ton', 'slug': 'ton', 'name': 'TON', 'symbol': 'TON'},
    ]
    tables = {
        'project_reports': [{
            'id': 'report-ton-en',
            'project_id': 'project-ton',
            'report_type': 'forensic',
            'language': 'en',
            'status': 'published',
            'published_at': '2026-05-01T00:00:00Z',
            'updated_at': '2026-05-01T00:00:00Z',
            'created_at': '2026-05-01T00:00:00Z',
            'slide_html_urls_by_lang': {'en': 'https://storage/for/ton/latest/en.html'},
        }],
        'tracked_projects': [{
            'id': 'project-ton',
            'slug': 'ton',
            'last_econ_report_at': None,
            'last_maturity_report_at': None,
            'last_forensic_report_at': None,
        }],
    }
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [])

    results = ws._reconcile_visible_reports_with_drive(
        _FakeReconcileSupabase(tables),
        object(),
        types=['for'],
        projects=projects,
        dry_run=False,
    )

    assert tables['project_reports'][0]['status'] == 'cancelled'
    assert tables['tracked_projects'][0]['last_forensic_report_at'] is None
    assert {row['status'] for row in results} == {
        'db_reconcile_cancelled_missing_active_slide_pdf',
    }


def test_db_reconcile_keeps_for_coming_soon_placeholder_without_active_slide_pdf(ws, monkeypatch):
    projects = [
        {'id': 'project-aztec', 'slug': 'aztec', 'name': 'Aztec', 'symbol': 'AZTEC'},
    ]
    tables = {
        'project_reports': [{
            'id': 'report-aztec-en',
            'project_id': 'project-aztec',
            'report_type': 'forensic',
            'language': 'en',
            'status': 'coming_soon',
            'published_at': None,
            'updated_at': '2026-05-13T00:00:00Z',
            'created_at': '2026-05-13T00:00:00Z',
            'gdrive_urls_by_lang': None,
            'gdrive_url': None,
            'file_urls_by_lang': None,
            'file_url': None,
            'gdrive_file_id': None,
            'slide_html_urls_by_lang': None,
        }],
        'tracked_projects': [{
            'id': 'project-aztec',
            'slug': 'aztec',
            'last_econ_report_at': None,
            'last_maturity_report_at': None,
            'last_forensic_report_at': None,
        }],
    }
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [])

    results = ws._reconcile_visible_reports_with_drive(
        _FakeReconcileSupabase(tables),
        object(),
        types=['for'],
        projects=projects,
        dry_run=False,
    )

    assert tables['project_reports'][0]['status'] == 'coming_soon'
    assert tables['tracked_projects'][0]['last_forensic_report_at'] is None
    assert {row['status'] for row in results} == {
        'db_reconcile_for_placeholder_without_active_slide_pdf',
    }


def test_db_reconcile_resolves_compact_drive_filename_slug(ws, monkeypatch):
    projects = [
        {'id': 'project-pump', 'slug': 'pump-fun', 'name': 'Pump.fun', 'symbol': 'PUMP'},
    ]
    tables = {
        'project_reports': [{
            'id': 'report-pump-en',
            'project_id': 'project-pump',
            'report_type': 'maturity',
            'language': 'en',
            'status': 'published',
            'published_at': '2026-05-01T00:00:00Z',
            'updated_at': '2026-05-01T00:00:00Z',
            'created_at': '2026-05-01T00:00:00Z',
            'slide_html_urls_by_lang': {'en': 'https://storage/mat/pump-fun/latest/en.html'},
        }],
        'tracked_projects': [{
            'id': 'project-pump',
            'slug': 'pump-fun',
            'last_econ_report_at': None,
            'last_maturity_report_at': '2026-05-01T00:00:00Z',
            'last_forensic_report_at': None,
        }],
    }
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [
        ('mat', {'name': 'pumpfun_MAT_en.pdf', 'source_path': 'Slide/mat/pumpfun_MAT_en.pdf'}),
    ])

    results = ws._reconcile_visible_reports_with_drive(
        _FakeReconcileSupabase(tables),
        object(),
        types=['mat'],
        projects=projects,
        dry_run=False,
    )

    assert tables['project_reports'][0]['status'] == 'published'
    assert results == [{
        'rtype': None,
        'slug': None,
        'lang': None,
        'status': 'db_reconcile_ok',
        'error': 'visible DB report availability already matches active Drive Slide folders',
    }]


@pytest.mark.parametrize(
    ('slug', 'name', 'symbol', 'filename'),
    [
        ('convex-finance', 'Convex Finance', 'CVX', 'convex_MAT_ko.pdf'),
        ('golem-network-tokens', 'Golem Network Tokens', 'GNT', 'golem_network_ECON_en.pdf'),
        ('mx-token', 'MX Token', 'MX', 'MEXC_MAT_jp.pdf'),
        ('ethgas', 'ETHGas', 'GWEI', 'ETHGas_ECON_ko.pdf'),
        ('ethgas', 'ETHGas', 'GWEI', 'GWEI_MAT_en.pdf'),
    ],
)
def test_db_reconcile_resolves_short_drive_filename_aliases(ws, monkeypatch, slug, name, symbol, filename):
    projects = [
        {'id': f'project-{slug}', 'slug': slug, 'name': name, 'symbol': symbol},
        {'id': 'project-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
    ]
    rtype = 'mat' if '_MAT_' in filename else 'econ'
    db_type = ws.DB_REPORT_TYPE[rtype]
    tables = {
        'project_reports': [],
        'tracked_projects': [{
            'id': f'project-{slug}',
            'slug': slug,
            'last_econ_report_at': None,
            'last_maturity_report_at': None,
            'last_forensic_report_at': None,
        }],
    }
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [
        (rtype, {
            'id': f'drive-{slug}',
            'name': filename,
            'source_path': f'Slide/{rtype}/{filename}',
        }),
    ])

    results = ws._reconcile_visible_reports_with_drive(
        _FakeReconcileSupabase(tables),
        object(),
        types=[rtype],
        projects=projects,
        dry_run=False,
    )

    assert tables['project_reports'][0]['project_id'] == f'project-{slug}'
    assert tables['project_reports'][0]['report_type'] == db_type
    assert tables['project_reports'][0]['status'] == ws.PUBLICATION_PUBLISHED_STATUS
    assert any(result['status'] == 'db_reconcile_materialized' for result in results)


def test_db_reconcile_materializes_active_drive_pdf_only_report_row(ws, monkeypatch):
    projects = [
        {'id': 'project-pump', 'slug': 'pump-fun', 'name': 'Pump.fun', 'symbol': 'PUMP'},
    ]
    tables = {
        'project_reports': [],
        'tracked_projects': [{
            'id': 'project-pump',
            'slug': 'pump-fun',
            'last_econ_report_at': None,
            'last_maturity_report_at': None,
            'last_forensic_report_at': None,
        }],
    }
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [
        ('econ', {
            'id': 'drive-pump-cn',
            'name': 'Pump.fun_Cryptoeconomic_Blueprint_cn.pdf',
            'source_path': 'Slide/econ/Pump.fun_Cryptoeconomic_Blueprint_cn.pdf',
        }),
    ])

    results = ws._reconcile_visible_reports_with_drive(
        _FakeReconcileSupabase(tables),
        object(),
        types=['econ'],
        projects=projects,
        dry_run=False,
    )

    assert tables['project_reports'][0]['project_id'] == 'project-pump'
    assert tables['project_reports'][0]['report_type'] == 'econ'
    assert tables['project_reports'][0]['language'] == 'zh'
    assert tables['project_reports'][0]['status'] == ws.PUBLICATION_PUBLISHED_STATUS
    assert tables['project_reports'][0]['published_at'] is not None
    assert tables['project_reports'][0]['gdrive_file_id'] == 'drive-pump-cn'
    assert tables['project_reports'][0]['gdrive_urls_by_lang'] == {
        'zh': 'https://drive.google.com/file/d/drive-pump-cn/view?usp=drivesdk',
    }
    assert tables['project_reports'][0]['slide_html_urls_by_lang'] == {}
    assert tables['tracked_projects'][0]['last_econ_report_at'] is not None
    assert any(result['status'] == 'db_reconcile_materialized' for result in results)
    assert any(result['status'] == 'db_reconcile_timestamp_synced' for result in results)


def test_db_reconcile_dry_run_materialization_does_not_mutate_rows(ws, monkeypatch):
    projects = [
        {'id': 'project-pump', 'slug': 'pump-fun', 'name': 'Pump.fun', 'symbol': 'PUMP'},
    ]
    tables = {
        'project_reports': [],
        'tracked_projects': [{
            'id': 'project-pump',
            'slug': 'pump-fun',
            'last_econ_report_at': None,
            'last_maturity_report_at': None,
            'last_forensic_report_at': None,
        }],
    }
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [
        ('econ', {
            'id': 'drive-pump-cn',
            'name': 'Pump.fun_Cryptoeconomic_Blueprint_cn.pdf',
            'source_path': 'Slide/econ/Pump.fun_Cryptoeconomic_Blueprint_cn.pdf',
        }),
    ])

    results = ws._reconcile_visible_reports_with_drive(
        _FakeReconcileSupabase(tables),
        object(),
        types=['econ'],
        projects=projects,
        dry_run=True,
    )

    assert tables['project_reports'] == []
    assert any(result['status'] == 'dry_run_db_reconcile_materialize' for result in results)


def test_run_db_reconcile_only_skips_slide_conversion_and_materializes_rows(ws, monkeypatch):
    projects = [
        {'id': 'project-story', 'slug': 'story-protocol', 'name': 'Story Protocol', 'symbol': 'IP'},
    ]
    tables = {
        'project_reports': [],
        'tracked_projects': [{
            'id': 'project-story',
            'slug': 'story-protocol',
            'last_econ_report_at': None,
            'last_maturity_report_at': None,
            'last_forensic_report_at': None,
        }],
    }
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_tracked_projects', lambda _sb: projects)
    monkeypatch.setitem(sys.modules, 'supabase_storage', SimpleNamespace(
        get_supabase_storage_client=lambda: _FakeReconcileSupabase(tables),
    ))
    monkeypatch.setattr(ws, '_iter_active_slide_targets', lambda *_args, **_kwargs: [
        ('econ', {
            'id': 'drive-story-en',
            'name': 'Story Protocol_Cryptoeconomic_Blueprint_en.pdf',
            'source_path': 'Slide/econ/Story Protocol_Cryptoeconomic_Blueprint_en.pdf',
        }),
    ])

    results = ws.run_db_reconcile_only(['econ'], dry_run=False)

    assert tables['project_reports'][0]['project_id'] == 'project-story'
    assert tables['project_reports'][0]['report_type'] == 'econ'
    assert tables['project_reports'][0]['language'] == 'en'
    assert tables['project_reports'][0]['status'] == ws.PUBLICATION_PUBLISHED_STATUS
    assert tables['project_reports'][0]['gdrive_file_id'] == 'drive-story-en'
    assert any(result['status'] == 'db_reconcile_materialized' for result in results)


def test_write_run_log_handles_prune_records_without_name(ws, monkeypatch, tmp_path):
    monkeypatch.setattr(ws, 'LOG_DIR', tmp_path)

    log_path = ws.write_run_log(
        '2026-05-01 00:00:00 UTC',
        ['econ'],
        [{
            'rtype': 'econ',
            'name': 'Bitcoin_Cryptoeconomic_Blueprint.pdf',
            'modifiedTime': 't0',
            'slug': 'bitcoin',
            'lang': 'en',
        }],
        [{
            'rtype': 'econ',
            'slug': 'bitcoin',
            'lang': None,
            'status': 'dry_run_prune',
            'current_langs': ['en', 'ja', 'ko', 'zh'],
            'stale_langs': ['de'],
        }],
    )

    text = Path(log_path).read_text(encoding='utf-8')
    assert '- [dry_run_prune] `econ/bitcoin`' in text


def test_unchanged_manifest_override_preserves_manual_verified_lang(ws, monkeypatch):
    manifest = {
        'file-zh': {
            'status': 'published',
            'modifiedTime': 't0',
            'slug': 'bitcoin',
            'lang': 'zh',
            'lang_source': 'ocr_langdetect',
            'rtype': 'econ',
            'name': 'Bitcoin_Crypto-Economy_Architecture.pdf',
            'report_id': 'report-bitcoin',
            'public_url': 'https://storage/econ/bitcoin/latest/zh.html',
            'page_profile': {
                'page_count': 12,
                'width': 1376,
                'height': 768,
                'aspect_ratio': 1.791,
                'is_landscape_slide': True,
            },
        }
    }
    saved = []
    prune_calls = []

    monkeypatch.setitem(
        sys.modules,
        'supabase_storage',
        SimpleNamespace(
            ensure_bucket=lambda *_args, **_kwargs: None,
            get_supabase_storage_client=lambda: object(),
        ),
    )
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: manifest)
    monkeypatch.setattr(ws, '_save_manifest', lambda data: saved.append({k: dict(v) for k, v in data.items()}))
    monkeypatch.setattr(ws, '_load_tracked_projects', lambda _sb: [
        {'id': 'project-bitcoin', 'slug': 'bitcoin', 'name': 'Bitcoin', 'symbol': 'BTC'},
    ])
    monkeypatch.setattr(ws, '_iter_targets', lambda _service, _types, **_kwargs: [
        ('econ', {
            'id': 'file-zh',
            'name': 'Bitcoin_Crypto-Economy_Architecture.pdf',
            'modifiedTime': 't0',
        }),
    ])

    def fake_prune(_sb, _storage_client, **kwargs):
        prune_calls.append(kwargs)
        return []

    monkeypatch.setattr(ws, '_prune_stale_languages_for_pair', fake_prune)

    scanned, processed = ws.process(
        ['econ'],
        filter_slug='bitcoin',
        dry_run=False,
        force=False,
        language_overrides={'file-zh': 'zh'},
    )

    assert processed == []
    assert scanned == [{
        'rtype': 'econ',
        'file_id': 'file-zh',
        'name': 'Bitcoin_Crypto-Economy_Architecture.pdf',
        'modifiedTime': 't0',
        'size': None,
        'parent_folder_id': None,
        'parent_folder_name': None,
        'source_path': None,
        'source_depth': None,
        'slug': 'bitcoin',
        'lang': 'zh',
        'status': 'unchanged',
    }]
    assert saved[-1]['file-zh']['lang'] == 'zh'
    assert saved[-1]['file-zh']['lang_source'] == 'manual_verified'
    assert prune_calls[0]['current_langs'] == {'zh'}


def test_ocr_returns_empty_when_tesseract_binary_missing(ws, monkeypatch):
    monkeypatch.setattr(ws.shutil, 'which', lambda _name: None)
    monkeypatch.setattr(ws, '_TESSERACT_AVAILABLE', None)

    assert ws._ocr_first_page_text('/tmp/does-not-need-to-exist.pdf') == ''
    assert ws._TESSERACT_AVAILABLE is False


def test_processing_manifest_diagnostic_marks_old_entry_stale(ws):
    now = datetime(2026, 5, 7, 4, 0, tzinfo=timezone.utc)
    diag = ws._processing_manifest_diagnostic(
        {
            'status': 'processing',
            'started_at': (now - timedelta(minutes=31)).isoformat(),
        },
        now=now,
        stale_after_minutes=30,
    )

    assert diag['is_stale'] is True
    assert diag['age_minutes'] == 31
    assert diag['reason'] == 'age_exceeded_threshold'


def test_processing_manifest_diagnostic_keeps_recent_entry_active(ws):
    now = datetime(2026, 5, 7, 4, 0, tzinfo=timezone.utc)
    diag = ws._processing_manifest_diagnostic(
        {
            'status': 'processing',
            'started_at': (now - timedelta(minutes=29)).isoformat(),
        },
        now=now,
        stale_after_minutes=30,
    )

    assert diag['is_stale'] is False
    assert diag['age_minutes'] == 29
    assert diag['reason'] == 'within_threshold'


def test_process_skips_recent_processing_manifest_entry(ws, monkeypatch):
    now = datetime.now(timezone.utc)
    manifest = {
        'file-processing': {
            'status': 'processing',
            'started_at': (now - timedelta(minutes=5)).isoformat(),
            'modifiedTime': 't0',
            'slug': 'bitcoin',
            'lang': 'en',
        }
    }

    monkeypatch.setitem(
        sys.modules,
        'supabase_storage',
        SimpleNamespace(get_supabase_storage_client=lambda: object()),
    )
    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: manifest)
    monkeypatch.setattr(ws, '_load_tracked_projects', lambda _sb: [])
    monkeypatch.setattr(ws, '_iter_targets', lambda _service, _types, **_kwargs: [
        ('mat', {
            'id': 'file-processing',
            'name': 'Bitcoin_Maturity_en.pdf',
            'modifiedTime': 't0',
        }),
    ])

    scanned, processed = ws.process(['mat'], filter_slug=None, dry_run=True, force=False)

    assert processed == []
    assert scanned[0]['status'] == 'processing_in_progress'
    assert scanned[0]['slug'] == 'bitcoin'
    assert scanned[0]['lang'] == 'en'
    assert scanned[0]['processing_age_minutes'] < ws.STALE_PROCESSING_AFTER_MINUTES


def test_write_run_log_surfaces_stale_processing_recovery(ws, monkeypatch, tmp_path):
    monkeypatch.setattr(ws, 'LOG_DIR', tmp_path)

    log_path = ws.write_run_log(
        '2026-05-07 04:00:00 UTC',
        ['mat'],
        scanned=[],
        processed=[{
            'rtype': 'mat',
            'slug': 'ethereum',
            'lang': 'ko',
            'name': 'Ethereum_Value_Capture_Paradox_ko.pdf',
            'status': 'published',
            'stale_processing': {
                'started_at': '2026-05-06T10:18:31+00:00',
                'age_minutes': 1061,
                'stale_after_minutes': 30,
            },
        }],
    )

    body = Path(log_path).read_text(encoding='utf-8')
    assert '- Stale processing recovered: 1' in body
    assert '## Processing Manifest Health' in body
    assert '[stale_processing_reprocessed]' in body


def test_build_paperclip_run_payload_has_expected_metadata(ws, monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_ID', '12345')
    monkeypatch.setenv('GITHUB_SHA', 'abc123')

    payload = ws.build_paperclip_run_payload(
        rtype='econ',
        scan_time='2026-05-10 12:00:00 UTC',
        dry_run=True,
        force=False,
        slug='bitcoin',
    )

    assert payload['pipeline_name'] == 'slide-pipeline'
    assert payload['paperclip_pipeline_name'] == 'ECON Report Publishing'
    assert payload['report_type'] == 'econ'
    assert payload['status'] == 'processing'
    assert payload['trigger_type'] == 'manual'
    assert payload['project_slug'] == 'bitcoin'
    assert payload['dry_run'] is True
    assert payload['force'] is False
    assert payload['metadata']['reportType'] == 'econ'
    assert payload['metadata']['scanTime'] == '2026-05-10 12:00:00 UTC'
    assert payload['metadata']['dryRun'] is True
    assert payload['metadata']['force'] is False
    assert payload['metadata']['slug'] == 'bitcoin'
    assert payload['github_run_id'] == '12345'
    assert payload['github_sha'] == 'abc123'


def test_build_paperclip_run_payload_uses_schedule_trigger_in_github_actions(ws, monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')

    payload = ws.build_paperclip_run_payload(
        rtype='mat',
        scan_time='2026-05-10 12:00:00 UTC',
        dry_run=False,
        force=False,
        slug=None,
    )

    assert payload['trigger_type'] == 'schedule'


def test_paperclip_counts_and_event_payload_include_required_metrics(ws):
    scanned = [
        {'rtype': 'econ', 'status': 'unchanged'},
        {'rtype': 'econ', 'status': 'target'},
        {'rtype': 'mat', 'status': 'target'},
    ]
    processed = [
        {'rtype': 'econ', 'status': 'published'},
        {'rtype': 'econ', 'status': 'unresolved'},
        {'rtype': 'econ', 'status': 'failed'},
        {'rtype': 'mat', 'status': 'published'},
    ]

    metrics = ws._paperclip_counts_for_type('econ', scanned, processed)
    status = ws._paperclip_status_for_counts(metrics)
    payload = ws.build_paperclip_event_payload(
        pipeline_run_id='run-1',
        rtype='econ',
        status=status,
        metrics=metrics,
        log_path='logs/slide_pipeline/20260510_120000.md',
        warnings=['POST /pipelines/x/events failed'],
    )

    assert metrics == {
        'scanned': 2,
        'processed': 3,
        'published': 1,
        'unresolved': 1,
        'failed': 1,
        'blocked': 1,
    }
    assert status == 'failed'
    assert payload['pipeline_run_id'] == 'run-1'
    assert payload['severity'] == 'error'
    assert payload['pipeline_name'] == 'slide-pipeline'
    assert payload['details']['metrics']['published'] == 1
    assert payload['details']['logArtifactPath'] == 'logs/slide_pipeline/20260510_120000.md'


def test_write_run_log_includes_paperclip_telemetry_warnings(ws, monkeypatch, tmp_path):
    monkeypatch.setattr(ws, 'LOG_DIR', tmp_path)

    log_path = ws.write_run_log(
        '2026-05-10 12:00:00 UTC',
        ['econ'],
        scanned=[],
        processed=[],
        telemetry_warnings=['POST /pipelines/run failed: timeout'],
    )

    body = Path(log_path).read_text(encoding='utf-8')
    assert '## Remote Pipeline State' in body
    assert '- Warnings: 1' in body
    assert 'POST /pipelines/run failed: timeout' in body


def test_paperclip_telemetry_start_and_complete_builds_expected_calls(ws, monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://state-store.test')
    monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'token')

    calls = []

    def fake_request(self, method, table, payload=None, query=''):
        calls.append((method, table, payload, query))
        if method == 'POST' and table == 'pipeline_runs':
            return [{'id': 'run-econ'}]
        return {'ok': True}

    monkeypatch.setattr(ws.PaperclipTelemetry, 'request', fake_request)
    telemetry = ws.PaperclipTelemetry()

    telemetry.start_runs(
        ['econ'],
        scan_time='2026-05-10 12:00:00 UTC',
        dry_run=False,
        force=True,
        slug=None,
    )
    telemetry.complete_runs(
        ['econ'],
        scanned=[
            {'rtype': 'econ', 'status': 'target'},
            {'rtype': 'econ', 'status': 'unchanged'},
        ],
        processed=[
            {'rtype': 'econ', 'status': 'published'},
            {'rtype': 'econ', 'status': 'unresolved'},
        ],
        log_path='logs/slide_pipeline/20260510_120000.md',
    )

    assert calls[0][0:2] == ('POST', 'pipeline_runs')
    assert calls[0][2]['metadata']['reportType'] == 'econ'
    assert calls[0][2]['pipeline_name'] == 'slide-pipeline'
    assert calls[0][2]['paperclip_pipeline_name'] == 'ECON Report Publishing'

    node_run_calls = [call for call in calls if call[1] == 'pipeline_node_runs']
    assert len(node_run_calls) == len(ws.PAPERCLIP_NODE_STAGES)
    assert node_run_calls[0][2]['pipeline_run_id'] == 'run-econ'
    assert node_run_calls[0][2]['node_key'] == 'source_collection'
    assert node_run_calls[0][2]['status'] == 'waiting_manual'
    assert node_run_calls[0][2]['metrics']['scanned'] == 2
    assert node_run_calls[0][2]['metrics']['published'] == 1
    assert node_run_calls[0][2]['metrics']['unresolved'] == 1

    event_call = next(call for call in calls if call[1] == 'pipeline_events')
    assert event_call[2]['event_type'] == 'slide_watcher.completed'
    assert event_call[2]['severity'] == 'warning'
    assert event_call[2]['details']['logArtifactPath'] == 'logs/slide_pipeline/20260510_120000.md'

    patch_call = next(call for call in calls if call[0] == 'PATCH')
    assert patch_call[1] == 'pipeline_runs'
    assert patch_call[2]['status'] == 'waiting_manual'
    assert patch_call[2]['languages_completed']['published'] == 1
    assert patch_call[2]['artifact_path'] == 'logs/slide_pipeline/20260510_120000.md'
    assert patch_call[2]['metadata']['source'] == 'watch_slides.py'
    assert patch_call[3] == '?id=eq.run-econ'


def test_paperclip_telemetry_disabled_warns_without_raising(ws, monkeypatch):
    monkeypatch.delenv('SUPABASE_URL', raising=False)
    monkeypatch.delenv('NEXT_PUBLIC_SUPABASE_URL', raising=False)
    monkeypatch.delenv('SUPABASE_SERVICE_KEY', raising=False)
    monkeypatch.delenv('SUPABASE_SERVICE_ROLE_KEY', raising=False)
    monkeypatch.delenv('NEXT_PUBLIC_SUPABASE_ANON_KEY', raising=False)

    telemetry = ws.PaperclipTelemetry()

    telemetry.start_runs(
        ['econ'],
        scan_time='2026-05-10 12:00:00 UTC',
        dry_run=True,
        force=False,
        slug='bitcoin',
    )
    telemetry.complete_runs(['econ'], scanned=[], processed=[], log_path=None)

    assert telemetry.run_ids == {}
    assert telemetry.warnings == [
        'disabled; set SUPABASE_URL and SUPABASE_SERVICE_KEY to publish pipeline state'
    ]


def test_process_stops_at_target_budget(ws, monkeypatch):
    targets = [
        {'id': 'file-1', 'name': 'Bitcoin_ECON_en.pdf', 'modifiedTime': '2026-05-28T00:00:00Z'},
        {'id': 'file-2', 'name': 'Bitcoin_ECON_ko.pdf', 'modifiedTime': '2026-05-28T00:00:00Z'},
        {'id': 'file-3', 'name': 'Bitcoin_ECON_ja.pdf', 'modifiedTime': '2026-05-28T00:00:00Z'},
    ]
    manifest = {
        target['id']: {
            'status': 'published',
            'modifiedTime': target['modifiedTime'],
            'slug': 'bitcoin',
            'lang': target['name'].split('_')[-1].split('.')[0],
            'lang_source': 'filename',
            'page_profile': {'is_landscape_slide': True},
        }
        for target in targets
    }

    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: manifest)
    monkeypatch.setattr(ws, '_iter_targets', lambda *args, **kwargs: iter(('econ', target) for target in targets))
    monkeypatch.setattr(ws, '_save_manifest', lambda _manifest: None)

    scanned, processed = ws.process(
        ['econ'],
        filter_slug=None,
        dry_run=True,
        force=False,
        max_targets=2,
    )

    assert scanned[-1]['status'] == 'target_budget_exhausted'
    assert scanned[-1]['targets_seen'] == 2
    assert all(row.get('file_id') != 'file-3' for row in scanned + processed)


def test_process_stops_at_runtime_budget(ws, monkeypatch):
    targets = [
        {'id': 'file-1', 'name': 'Bitcoin_ECON_en.pdf', 'modifiedTime': '2026-05-28T00:00:00Z'},
    ]

    monkeypatch.setattr(ws, '_get_drive_service', lambda: object())
    monkeypatch.setattr(ws, '_load_manifest', lambda: {})
    monkeypatch.setattr(ws, '_iter_targets', lambda *args, **kwargs: iter(('econ', target) for target in targets))

    scanned, processed = ws.process(
        ['econ'],
        filter_slug=None,
        dry_run=True,
        force=False,
        deadline_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    assert processed == []
    assert scanned == [{
        'rtype': 'econ',
        'slug': None,
        'lang': None,
        'status': 'run_budget_exhausted',
        'error': scanned[0]['error'],
        'targets_seen': 0,
    }]
