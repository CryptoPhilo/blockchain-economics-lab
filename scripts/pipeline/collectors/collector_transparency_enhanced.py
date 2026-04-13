"""
Phase C Enhanced: Transparency Scanner + Existing Collectors Integration
=========================================================================
기존 3종 보고서 데이터 수집 파이프라인(exchange, onchain, fundamentals, whale)의
데이터를 투명성/성숙도 평가에 함께 활용하는 통합 스캐너.

collector_transparency.py (v2 웹사이트 크롤링)을 기반으로,
기존 collectors의 데이터를 보조 입력으로 받아 점수를 보강한다.

사용 방법:
    from collectors.collector_transparency_enhanced import EnhancedTransparencyScanner
    scanner = EnhancedTransparencyScanner()
    result = scanner.full_scan('ethereum')  # 웹크롤링 + 기존 collectors 통합
    result = scanner.quick_scan('ethereum', collected_data=existing_data)  # 기수집 데이터 활용
"""

import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .collector_transparency import CollectorTransparency
from .collector_exchange import CollectorExchange
from .collector_onchain import CollectorOnchain
from .collector_fundamentals import CollectorFundamentals
from .collector_whale import CollectorWhale


class EnhancedTransparencyScanner:
    """
    투명성 스캔 + 기존 데이터 수집 파이프라인 통합.

    2가지 모드:
    1. full_scan(): 웹크롤링 + 기존 collectors 전체 실행 (느림, 정밀)
    2. quick_scan(): 웹크롤링 + 이미 수집된 데이터 활용 (빠름, 일상 스캔)
    """

    def __init__(self):
        self.transparency_scanner = CollectorTransparency()
        self.exchange_collector = CollectorExchange()
        self.onchain_collector = CollectorOnchain()
        self.fundamentals_collector = CollectorFundamentals()
        self.whale_collector = CollectorWhale()

    def full_scan(
        self,
        slug: str,
        token_detail: Optional[Dict] = None,
        market_token: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        전체 스캔: 웹크롤링 + 기존 collectors 모두 실행.
        FULL/STANDARD 보고서 대상 프로젝트에 사용.
        소요: 토큰당 ~15-30초 (API rate limits 포함)
        """
        # Step 1: Base transparency scan (website crawling)
        result = self.transparency_scanner.scan(slug, token_detail, market_token)

        # Step 2: Collect additional data from existing pipelines
        symbol = (market_token or {}).get('symbol', slug)
        contract = result.get('contract_address')

        # Fundamentals: GitHub 정밀 데이터
        fundamentals = self._safe_collect_fundamentals(slug, contract)

        # On-chain: 홀더 분석, TVL
        onchain = self._safe_collect_onchain(slug, contract)

        # Exchange: 추가 시장 데이터
        exchange = self._safe_collect_exchange(slug, symbol)

        # Whale: 고래 활동
        whale = self._safe_collect_whale(slug, contract)

        # Step 3: Enhance scores with additional data
        self._enhance_code_score(result, fundamentals)
        self._enhance_distribution_score(result, onchain)
        self._enhance_audit_score(result, onchain, fundamentals)
        self._enhance_docs_score(result, fundamentals)

        # Step 4: Add maturity enhancement data
        result['enhanced_data'] = {
            'has_fundamentals': bool(fundamentals),
            'has_onchain': bool(onchain),
            'has_exchange': bool(exchange),
            'has_whale': bool(whale),
            'tvl': onchain.get('defi_tvl', {}).get('totalLiquidityUSD') if onchain else None,
            'holder_count': onchain.get('onchain_top_holders', {}).get('total_holders') if onchain else None,
            'top10_concentration': self._calc_top10_concentration(onchain),
            'github_stars': fundamentals.get('github_data', {}).get('stargazers_count') if fundamentals else None,
            'github_forks': fundamentals.get('github_data', {}).get('forks_count') if fundamentals else None,
            'github_language': fundamentals.get('github_data', {}).get('language') if fundamentals else None,
            'whale_net_flow': whale.get('whale_exchange_flow', {}).get('net_flow') if whale else None,
            'whale_activity_level': self._assess_whale_activity(whale),
            'exchange_data': exchange,
        }

        # Recalculate total score
        total = (result['team_score'] + result['code_score'] +
                result['distribution_score'] + result['audit_score'] +
                result['docs_score'])
        result['transparency_score'] = total
        result['transparency_label'] = CollectorTransparency._score_to_label(total)
        result['scan_mode'] = 'full'

        return result

    def quick_scan(
        self,
        slug: str,
        token_detail: Optional[Dict] = None,
        market_token: Optional[Dict] = None,
        collected_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        빠른 스캔: 웹크롤링 + 이미 수집된 데이터 활용.
        일일 파이프라인에서 대량 스캔 시 사용.
        collected_data가 있으면 추가 API 호출 없이 점수 보강.
        """
        # Step 1: Base transparency scan
        result = self.transparency_scanner.scan(slug, token_detail, market_token)

        # Step 2: Enhance with pre-collected data if available
        if collected_data:
            fundamentals = {
                'github_data': collected_data.get('github_data', {}),
                'project_links': collected_data.get('project_links', {}),
            }
            onchain = {
                'onchain_top_holders': collected_data.get('onchain_top_holders', {}),
                'defi_tvl': collected_data.get('defi_tvl', {}),
            }

            self._enhance_code_score(result, fundamentals)
            self._enhance_distribution_score(result, onchain)
            self._enhance_docs_score(result, fundamentals)

            result['enhanced_data'] = {
                'has_fundamentals': bool(fundamentals.get('github_data')),
                'has_onchain': bool(onchain.get('onchain_top_holders')),
                'tvl': onchain.get('defi_tvl', {}).get('totalLiquidityUSD'),
                'holder_count': onchain.get('onchain_top_holders', {}).get('total_holders'),
                'top10_concentration': self._calc_top10_concentration(onchain),
                'github_stars': fundamentals.get('github_data', {}).get('stargazers_count'),
            }

            # Recalculate total
            total = (result['team_score'] + result['code_score'] +
                    result['distribution_score'] + result['audit_score'] +
                    result['docs_score'])
            result['transparency_score'] = total
            result['transparency_label'] = CollectorTransparency._score_to_label(total)

        result['scan_mode'] = 'quick'
        return result

    # ═══════════════════════════════════════════════════════
    # SCORE ENHANCEMENT METHODS
    # ═══════════════════════════════════════════════════════

    def _enhance_code_score(self, result: Dict, fundamentals: Optional[Dict]):
        """GitHub 정밀 데이터로 code_score 보강."""
        if not fundamentals or result.get('code_score', 0) >= 6:
            return

        github_data = fundamentals.get('github_data', {})
        if not github_data:
            return

        stars = github_data.get('stargazers_count', 0) or 0
        forks = github_data.get('forks_count', 0) or 0
        open_issues = github_data.get('open_issues_count', 0) or 0
        pushed_at = github_data.get('pushed_at', '')
        topics = github_data.get('topics', [])

        # Strong evidence from GitHub API
        if stars >= 100 or forks >= 50:
            result['code_score'] = 6
            result['code_source'] = (result.get('code_source', '') or '') + '+fundamentals_github'
            result['code_opensource'] = True
            result['github_stars'] = max(result.get('github_stars', 0), stars)
        elif stars >= 10 or forks >= 5:
            result['code_score'] = max(result.get('code_score', 0), 3)
            result['code_source'] = (result.get('code_source', '') or '') + '+fundamentals_github'
            result['code_opensource'] = True

    def _enhance_distribution_score(self, result: Dict, onchain: Optional[Dict]):
        """On-chain 홀더 데이터로 distribution_score 보강."""
        if not onchain or result.get('distribution_score', 0) >= 6:
            return

        holders_data = onchain.get('onchain_top_holders', {})
        if not holders_data:
            return

        holders = holders_data.get('holders', [])
        total_holders = holders_data.get('total_holders', 0)

        if holders and len(holders) >= 10:
            result['distribution_score'] = 6
            result['distribution_source'] = (result.get('distribution_source', '') or '') + '+onchain_holders'
            result['token_distribution_public'] = True
            result['total_holders'] = total_holders

            # Calculate top 10 concentration
            if holders:
                total_pct = sum(h.get('percentage', 0) for h in holders[:10])
                result['top10_holder_pct'] = round(total_pct, 2)
        elif total_holders and total_holders > 0:
            result['distribution_score'] = max(result.get('distribution_score', 0), 3)
            result['distribution_source'] = (result.get('distribution_source', '') or '') + '+onchain_partial'
            result['token_distribution_public'] = True
            result['total_holders'] = total_holders

    def _enhance_audit_score(self, result: Dict, onchain: Optional[Dict],
                             fundamentals: Optional[Dict]):
        """추가 데이터 소스로 audit_score 보강."""
        if result.get('audit_score', 0) >= 6:
            return

        # Check if TVL is high (DeFi protocols with high TVL usually audited)
        if onchain:
            tvl = onchain.get('defi_tvl', {}).get('totalLiquidityUSD', 0) or 0
            if tvl >= 100_000_000 and result.get('audit_score', 0) < 3:
                # High TVL DeFi → likely audited (weak signal)
                result['audit_score'] = max(result.get('audit_score', 0), 3)
                result['audit_source'] = (result.get('audit_source', '') or '') + '+high_tvl_inference'

    def _enhance_docs_score(self, result: Dict, fundamentals: Optional[Dict]):
        """Project links에서 문서화 보강."""
        if not fundamentals or result.get('docs_score', 0) >= 6:
            return

        links = fundamentals.get('project_links', {})
        if not links:
            return

        # Whitepaper URL from fundamentals
        whitepaper = links.get('whitepaper')
        if whitepaper and not result.get('whitepaper_url'):
            result['whitepaper_url'] = whitepaper
            result['documentation_public'] = True
            result['docs_score'] = max(result.get('docs_score', 0), 3)
            result['docs_source'] = (result.get('docs_source', '') or '') + '+fundamentals_whitepaper'

        # Website URL
        website = links.get('website')
        if website and not result.get('website_url'):
            result['website_url'] = website

    # ═══════════════════════════════════════════════════════
    # SAFE COLLECTION WRAPPERS
    # ═══════════════════════════════════════════════════════

    def _safe_collect_fundamentals(self, slug: str, contract: Optional[str]) -> Optional[Dict]:
        """Collect fundamentals data safely."""
        try:
            result = self.fundamentals_collector.collect(slug)
            time.sleep(1)
            return result
        except Exception:
            return None

    def _safe_collect_onchain(self, slug: str, contract: Optional[str]) -> Optional[Dict]:
        """Collect on-chain data safely."""
        if not contract:
            return None
        try:
            result = self.onchain_collector.collect(contract, slug)
            time.sleep(0.5)
            return result
        except Exception:
            return None

    def _safe_collect_exchange(self, slug: str, symbol: str) -> Optional[Dict]:
        """Collect exchange data safely."""
        try:
            result = self.exchange_collector.collect(slug, symbol)
            time.sleep(1.5)
            return result
        except Exception:
            return None

    def _safe_collect_whale(self, slug: str, contract: Optional[str]) -> Optional[Dict]:
        """Collect whale data safely."""
        if not contract:
            return None
        try:
            result = self.whale_collector.collect(contract)
            time.sleep(0.5)
            return result
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════
    # UTILITY
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _calc_top10_concentration(onchain: Optional[Dict]) -> Optional[float]:
        """Calculate top 10 holder concentration percentage."""
        if not onchain:
            return None
        holders = onchain.get('onchain_top_holders', {}).get('holders', [])
        if not holders:
            return None
        return round(sum(h.get('percentage', 0) for h in holders[:10]), 2)

    @staticmethod
    def _assess_whale_activity(whale: Optional[Dict]) -> str:
        """Assess whale activity level."""
        if not whale:
            return 'unknown'
        flow = whale.get('whale_exchange_flow', {})
        if not flow:
            return 'unknown'
        net_flow = abs(flow.get('net_flow', 0) or 0)
        if net_flow > 1_000_000:
            return 'high'
        elif net_flow > 100_000:
            return 'moderate'
        else:
            return 'low'
