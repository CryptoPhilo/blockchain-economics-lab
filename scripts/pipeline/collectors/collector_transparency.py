"""
Phase C: Transparency Scanner v2 — Website Crawling Based
==========================================================
새로운 접근: CoinGecko에서 프로젝트 웹사이트 URL을 확인하고,
실제 웹사이트에 접속하여 투명성 정보를 수집한다.

5개 투명성 기준 (각 6점, 최대 30점):
  1. Team Public — 팀/창업자 정보 공개 여부 (웹사이트 + CoinGecko)
  2. Code Open Source — 오픈소스 코드 존재 (GitHub + CoinGecko dev_data)
  3. Token Distribution Public — 토큰 분배 정보 공개 (웹사이트 + 익스플로러)
  4. Audit Completed — 보안 감사 완료 여부 (웹사이트 + CoinGecko)
  5. Documentation/Contract — 문서화 수준 + 컨트랙트 검증 (웹사이트 + 익스플로러)

부분 점수 지원: 0 / 3 / 6 (약한 증거 = 3점, 강한 증거 = 6점)

Usage:
    from collectors.collector_transparency import CollectorTransparency
    ct = CollectorTransparency()
    result = ct.scan('uniswap')
"""

import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base_collector import BaseCollector

# Known audit providers (lowercase for matching)
KNOWN_AUDITORS = [
    'certik', 'hacken', 'trail of bits', 'trailofbits', 'openzeppelin',
    'consensys diligence', 'peckshield', 'slowmist', 'quantstamp',
    'chainsecurity', 'halborn', 'solidproof', 'cyberscope', 'techrate',
    'interfi', 'rugdoc', 'paladin', 'sherlock', 'code4rena', 'spearbit',
    'mixbytes', 'zellic', 'omniscia', 'hexens', 'immunefi',
]

# Known team/leadership keywords
TEAM_KEYWORDS_STRONG = [
    'founder', 'co-founder', 'ceo', 'cto', 'coo', 'cfo',
    'chief executive', 'chief technology', 'chief operating',
    'created by', 'founded by', 'built by',
]
TEAM_KEYWORDS_MODERATE = [
    'team', 'about us', 'our team', 'leadership', 'core team',
    'contributors', 'developers', 'advisors', 'advisory board',
]

# Explorer APIs by chain
EXPLORER_APIS = {
    'ethereum': {
        'base': 'https://api.etherscan.io/api',
        'key_env': 'ETHERSCAN_API_KEY',
    },
    'binance-smart-chain': {
        'base': 'https://api.bscscan.com/api',
        'key_env': 'BSCSCAN_API_KEY',
    },
    'polygon-pos': {
        'base': 'https://api.polygonscan.com/api',
        'key_env': 'POLYGONSCAN_API_KEY',
    },
    'arbitrum-one': {
        'base': 'https://api.arbiscan.io/api',
        'key_env': 'ARBISCAN_API_KEY',
    },
}

# Subpages to try crawling for additional info
SUBPAGES_TEAM = ['/about', '/team', '/about-us', '/our-team', '/about/team']
SUBPAGES_AUDIT = ['/security', '/audit', '/audits', '/security-audits']
SUBPAGES_DOCS = ['/docs', '/documentation', '/whitepaper', '/developers']
SUBPAGES_TOKENOMICS = ['/tokenomics', '/token', '/economics']


class CollectorTransparency(BaseCollector):
    """
    v2: 웹사이트 크롤링 기반 투명성 스캐너.
    CoinGecko → 웹사이트 URL → 웹사이트 크롤링 → 투명성 점수 산출.
    """

    COINGECKO_BASE = 'https://api.coingecko.com/api/v3'
    GITHUB_API = 'https://api.github.com'

    def __init__(self):
        super().__init__()
        self._github_token = os.environ.get('GITHUB_TOKEN', '')
        # Separate session for HTML fetching (different headers)
        self._web_session = requests.Session()
        self._web_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; BCELab/2.0; +https://blockchain-econ.org)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    # ═══════════════════════════════════════════════════════
    # MAIN SCAN METHOD
    # ═══════════════════════════════════════════════════════

    def scan(
        self,
        slug: str,
        token_detail: Optional[Dict] = None,
        market_token: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Run full transparency scan for a single project.

        Flow:
        1. CoinGecko coin detail 조회 → 웹사이트 URL, GitHub URL, 기본 정보 확보
        2. 프로젝트 웹사이트 메인 페이지 크롤링
        3. 관련 서브페이지 크롤링 (team, audit, docs, tokenomics)
        4. 5개 기준별 점수 산출
        5. 총점 + 라벨 반환
        """
        result = {
            'slug': slug,
            # Criterion 1: Team
            'team_public': False,
            'team_score': 0,
            'team_info_source': None,
            'team_members_found': [],
            # Criterion 2: Code
            'code_opensource': False,
            'code_score': 0,
            'github_org': None,
            'github_repo_count': 0,
            'github_stars': 0,
            'github_contributors': 0,
            'github_last_commit': None,
            'code_source': None,
            # Criterion 3: Token Distribution
            'token_distribution_public': False,
            'distribution_score': 0,
            'top10_holder_pct': None,
            'total_holders': None,
            'distribution_source': None,
            # Criterion 4: Audit
            'audit_completed': False,
            'audit_score': 0,
            'audit_provider': None,
            'audit_url': None,
            'audit_source': None,
            # Criterion 5: Documentation/Contract
            'documentation_public': False,
            'docs_score': 0,
            'whitepaper_url': None,
            'docs_url': None,
            'contract_verified': False,
            'contract_address': None,
            'docs_source': None,
            # Metadata
            'website_url': None,
            'website_accessible': False,
            'pages_crawled': 0,
            'transparency_score': 0,
            'transparency_label': 'OPAQUE',
            'scanned_at': datetime.utcnow().isoformat() + 'Z',
        }

        # ── Step 1: CoinGecko coin detail ──
        if not token_detail:
            token_detail = self._fetch_token_detail(slug)
            time.sleep(1.5)  # CoinGecko rate limit

        if not token_detail:
            result['transparency_label'] = 'OPAQUE'
            return result

        # Extract URLs and metadata
        links = token_detail.get('links', {})
        homepage_url = links.get('homepage')
        github_urls = links.get('github', [])
        whitepaper_url = links.get('whitepaper')
        platforms = token_detail.get('platforms', {})
        dev_data = token_detail.get('developer_data', {})
        community_data = token_detail.get('community_data', {})
        description = token_detail.get('description', '')

        result['website_url'] = homepage_url
        if whitepaper_url:
            result['whitepaper_url'] = whitepaper_url

        # Extract contract info
        contract_address, chain = self._extract_primary_contract(platforms)
        result['contract_address'] = contract_address

        # ── Step 2: Crawl main website ──
        main_page_text = ''
        main_page_links = []
        if homepage_url and self._is_valid_url(homepage_url):
            main_page_text, main_page_links = self._crawl_page(homepage_url)
            if main_page_text:
                result['website_accessible'] = True
                result['pages_crawled'] += 1
            time.sleep(0.5)

        # ── Step 3: Crawl subpages ──
        subpage_texts = {}  # category -> concatenated text

        if homepage_url and result['website_accessible']:
            # Team pages
            team_text = self._crawl_subpages(homepage_url, SUBPAGES_TEAM, main_page_links)
            if team_text:
                subpage_texts['team'] = team_text
                result['pages_crawled'] += 1

            # Audit pages
            audit_text = self._crawl_subpages(homepage_url, SUBPAGES_AUDIT, main_page_links)
            if audit_text:
                subpage_texts['audit'] = audit_text
                result['pages_crawled'] += 1

            # Docs pages
            docs_text = self._crawl_subpages(homepage_url, SUBPAGES_DOCS, main_page_links)
            if docs_text:
                subpage_texts['docs'] = docs_text
                result['pages_crawled'] += 1

            # Tokenomics pages
            tokenomics_text = self._crawl_subpages(homepage_url, SUBPAGES_TOKENOMICS, main_page_links)
            if tokenomics_text:
                subpage_texts['tokenomics'] = tokenomics_text
                result['pages_crawled'] += 1

        # Combine all text for full analysis
        all_website_text = (main_page_text + ' ' +
                           ' '.join(subpage_texts.values())).lower()

        # ── Step 4: Score each criterion ──

        # Criterion 1: Team Public (0/3/6)
        self._score_team(result, all_website_text, subpage_texts.get('team', ''),
                        description, dev_data, community_data)

        # Criterion 2: Code Open Source (0/3/6)
        self._score_code(result, all_website_text, github_urls, dev_data)

        # Criterion 3: Token Distribution Public (0/3/6)
        self._score_distribution(result, all_website_text,
                                subpage_texts.get('tokenomics', ''),
                                contract_address, chain)

        # Criterion 4: Audit (0/3/6)
        self._score_audit(result, all_website_text,
                         subpage_texts.get('audit', ''), description)

        # Criterion 5: Documentation + Contract (0/3/6)
        self._score_docs(result, all_website_text,
                        subpage_texts.get('docs', ''),
                        whitepaper_url, contract_address, chain, main_page_links)

        # ── Step 5: Calculate total score ──
        total = (result['team_score'] + result['code_score'] +
                result['distribution_score'] + result['audit_score'] +
                result['docs_score'])
        result['transparency_score'] = total
        result['transparency_label'] = self._score_to_label(total)

        return result

    # ═══════════════════════════════════════════════════════
    # WEBSITE CRAWLING
    # ═══════════════════════════════════════════════════════

    def _crawl_page(self, url: str, timeout: int = 10) -> Tuple[str, List[str]]:
        """
        Fetch and parse a web page.

        Returns:
            (page_text, list_of_link_urls) — text content + all links found
        """
        try:
            resp = self._web_session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code != 200:
                return '', []

            content_type = resp.headers.get('content-type', '')
            if 'html' not in content_type and 'text' not in content_type:
                return '', []

            soup = BeautifulSoup(resp.text, 'lxml')

            # Remove script/style/nav elements
            for tag in soup(['script', 'style', 'noscript', 'iframe']):
                tag.decompose()

            # Extract text
            text = soup.get_text(separator=' ', strip=True)
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            # Limit length to prevent memory issues
            text = text[:50000]

            # Extract all links
            links = []
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                # Resolve relative URLs
                full_url = urljoin(url, href)
                links.append(full_url)

            return text, links

        except Exception:
            return '', []

    def _crawl_subpages(
        self,
        base_url: str,
        subpaths: List[str],
        main_page_links: List[str],
    ) -> str:
        """
        Try to find and crawl relevant subpages.

        Strategy:
        1. Check if any main_page_links match the subpath patterns
        2. If not found, try constructing URLs from base_url + subpath
        3. Return concatenated text from first successful crawl
        """
        parsed_base = urlparse(base_url)
        base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

        # Strategy 1: Search main page links for relevant subpages
        for link in main_page_links:
            link_lower = link.lower()
            for subpath in subpaths:
                keyword = subpath.strip('/')
                if keyword in link_lower and link_lower.startswith(('http://', 'https://')):
                    # Found a relevant link, crawl it
                    text, _ = self._crawl_page(link, timeout=8)
                    if text and len(text) > 100:
                        time.sleep(0.3)
                        return text

        # Strategy 2: Try direct subpath construction
        for subpath in subpaths[:3]:  # Limit attempts
            url = base_domain + subpath
            text, _ = self._crawl_page(url, timeout=8)
            if text and len(text) > 100:
                time.sleep(0.3)
                return text
            time.sleep(0.3)

        return ''

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and crawlable."""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            if not parsed.netloc:
                return False
            # Skip social media, marketplaces
            skip_domains = ['twitter.com', 'x.com', 'discord.com', 'discord.gg',
                          't.me', 'telegram.me', 'reddit.com', 'medium.com',
                          'facebook.com', 'youtube.com', 'github.com',
                          'coingecko.com', 'coinmarketcap.com']
            if any(d in parsed.netloc.lower() for d in skip_domains):
                return False
            return True
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════
    # CRITERION 1: TEAM PUBLIC (0/3/6)
    # ═══════════════════════════════════════════════════════

    def _score_team(
        self,
        result: Dict,
        all_text: str,
        team_page_text: str,
        cg_description: str,
        dev_data: Dict,
        community_data: Dict,
    ):
        """
        Score team transparency.
        6 pts: Named team members found (founder names, LinkedIn profiles, photos)
        3 pts: Generic team mention or strong social/dev presence
        0 pts: No team information found
        """
        score = 0
        source = None
        members = []

        # ── Website analysis ──
        # Check for named team members on dedicated team page
        if team_page_text:
            team_lower = team_page_text.lower()
            # Strong: Named roles on team page
            named_roles = re.findall(
                r'(?:ceo|cto|coo|cfo|founder|co-founder|chief)\s*[:\-–]?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
                team_page_text,
                re.IGNORECASE
            )
            if named_roles:
                score = 6
                source = 'website_team_page_named'
                members = named_roles[:10]
            elif any(kw in team_lower for kw in TEAM_KEYWORDS_STRONG):
                score = 6
                source = 'website_team_page'
            elif any(kw in team_lower for kw in TEAM_KEYWORDS_MODERATE):
                score = 3
                source = 'website_team_page_generic'

        # Check main website text if no team page found
        if score < 6 and all_text:
            # LinkedIn profiles indicate real team
            linkedin_count = all_text.count('linkedin.com')
            if linkedin_count >= 2:
                score = max(score, 6)
                source = source or 'website_linkedin_profiles'
            elif linkedin_count >= 1:
                score = max(score, 3)
                source = source or 'website_linkedin_profile'

            # Named founders/leadership on main page
            if score < 6:
                for kw in TEAM_KEYWORDS_STRONG:
                    if kw in all_text:
                        score = max(score, 6)
                        source = source or 'website_main_page_named'
                        break

            if score < 3:
                for kw in TEAM_KEYWORDS_MODERATE:
                    if kw in all_text:
                        score = max(score, 3)
                        source = source or 'website_main_page_generic'
                        break

        # ── CoinGecko description fallback ──
        if score < 6 and cg_description:
            desc_lower = cg_description.lower()
            for kw in TEAM_KEYWORDS_STRONG:
                if kw in desc_lower:
                    score = max(score, 6)
                    source = source or 'coingecko_description'
                    break
            if score < 3:
                for kw in TEAM_KEYWORDS_MODERATE:
                    if kw in desc_lower:
                        score = max(score, 3)
                        source = source or 'coingecko_description_generic'
                        break

        # ── Developer/Community data fallback ──
        if score < 3:
            contributors = dev_data.get('contributors', 0) or 0
            twitter_followers = community_data.get('twitter_followers', 0) or 0
            if contributors >= 10 and twitter_followers >= 10000:
                score = 3
                source = 'dev_community_activity'
            elif twitter_followers >= 50000:
                score = 3
                source = 'strong_social_presence'

        result['team_public'] = score > 0
        result['team_score'] = score
        result['team_info_source'] = source
        result['team_members_found'] = members

    # ═══════════════════════════════════════════════════════
    # CRITERION 2: CODE OPEN SOURCE (0/3/6)
    # ═══════════════════════════════════════════════════════

    def _score_code(
        self,
        result: Dict,
        all_text: str,
        github_urls: List[str],
        dev_data: Dict,
    ):
        """
        Score code openness.
        6 pts: Active GitHub repos with recent commits + stars
        3 pts: GitHub exists but minimal activity, or only CoinGecko dev_data
        0 pts: No code evidence
        """
        score = 0
        source = None

        # ── CoinGecko developer_data (always available, no API key needed) ──
        stars = dev_data.get('stars', 0) or 0
        forks = dev_data.get('forks', 0) or 0
        subscribers = dev_data.get('subscribers', 0) or 0
        commit_4w = dev_data.get('commit_count_4_weeks', 0) or 0
        contributors = dev_data.get('contributors', 0) or 0
        pr_merged = dev_data.get('pull_requests_merged', 0) or 0
        total_issues = dev_data.get('total_issues', 0) or 0

        # Strong evidence: active development
        if (stars >= 100 and commit_4w >= 10 and contributors >= 5) or \
           (forks >= 50 and pr_merged >= 50) or \
           (stars >= 500):
            score = 6
            source = 'coingecko_devdata_strong'
            result['github_stars'] = stars
            result['github_contributors'] = contributors
        # Moderate evidence
        elif (stars >= 10 or forks >= 5) and (commit_4w >= 1 or contributors >= 2):
            score = 3
            source = 'coingecko_devdata_moderate'
            result['github_stars'] = stars
            result['github_contributors'] = contributors
        # Minimal: has some dev data
        elif stars > 0 or forks > 0 or total_issues > 0 or commit_4w > 0:
            score = 3
            source = 'coingecko_devdata_minimal'

        # ── GitHub API check (if score < 6 and URLs available) ──
        if score < 6 and github_urls and self._github_token:
            for url in github_urls[:2]:
                org_or_repo = self._parse_github_url(url)
                if not org_or_repo:
                    continue

                headers = {'Authorization': f'token {self._github_token}'} if self._github_token else {}
                try:
                    resp = self.session.get(
                        f'{self.GITHUB_API}/repos/{org_or_repo}',
                        headers=headers,
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        repo = resp.json()
                        result['github_org'] = org_or_repo
                        result['github_stars'] = repo.get('stargazers_count', 0)
                        result['github_last_commit'] = repo.get('pushed_at')
                        result['github_repo_count'] = 1

                        if repo.get('stargazers_count', 0) >= 50:
                            score = 6
                            source = 'github_api_active'
                        else:
                            score = max(score, 3)
                            source = source or 'github_api_exists'
                        break
                except Exception:
                    pass
                time.sleep(0.5)

        # ── Website check: GitHub link found on website ──
        if score < 3:
            if 'github.com' in all_text:
                score = 3
                source = 'website_github_link'
            elif github_urls:
                score = 3
                source = 'coingecko_github_url'
                result['github_org'] = self._parse_github_url(github_urls[0])

        result['code_opensource'] = score > 0
        result['code_score'] = score
        result['code_source'] = source

    # ═══════════════════════════════════════════════════════
    # CRITERION 3: TOKEN DISTRIBUTION PUBLIC (0/3/6)
    # ═══════════════════════════════════════════════════════

    def _score_distribution(
        self,
        result: Dict,
        all_text: str,
        tokenomics_text: str,
        contract_address: Optional[str],
        chain: Optional[str],
    ):
        """
        Score token distribution transparency.
        6 pts: Detailed tokenomics on website + on-chain verifiable
        3 pts: Basic tokenomics info or holder data available
        0 pts: No distribution info
        """
        score = 0
        source = None

        # ── Website tokenomics analysis ──
        combined_text = (all_text + ' ' + tokenomics_text).lower()

        # Strong: detailed tokenomics page
        tokenomics_strong = [
            'token distribution', 'token allocation', 'vesting schedule',
            'circulating supply', 'total supply', 'token economics',
            'tokenomics', 'emission schedule', 'unlock schedule',
        ]
        tokenomics_moderate = [
            'supply', 'allocation', 'distribution', 'staking',
            'burned', 'deflationary', 'inflationary',
        ]

        strong_matches = sum(1 for kw in tokenomics_strong if kw in combined_text)
        moderate_matches = sum(1 for kw in tokenomics_moderate if kw in combined_text)

        if strong_matches >= 3:
            score = 6
            source = 'website_tokenomics_detailed'
        elif strong_matches >= 1 or tokenomics_text:
            score = 3
            source = 'website_tokenomics_basic'
        elif moderate_matches >= 3:
            score = 3
            source = 'website_supply_info'

        # ── On-chain verification (Etherscan) ──
        if contract_address and chain and score < 6:
            explorer = EXPLORER_APIS.get(chain)
            if explorer:
                api_key = os.environ.get(explorer['key_env'], '')
                try:
                    data = self._request(
                        explorer['base'],
                        params={
                            'module': 'token',
                            'action': 'tokeninfo',
                            'contractaddress': contract_address,
                            'apikey': api_key,
                        },
                        timeout=10,
                    )
                    if data and data.get('status') == '1':
                        token_info = data.get('result', [{}])
                        if isinstance(token_info, list) and token_info:
                            token_info = token_info[0]
                        if isinstance(token_info, dict):
                            holder_str = token_info.get('holdersCount', '0')
                            try:
                                holders = int(str(holder_str).replace(',', ''))
                                if holders > 0:
                                    result['total_holders'] = holders
                                    result['token_distribution_public'] = True
                                    score = max(score, 6) if holders >= 1000 else max(score, 3)
                                    source = source or 'etherscan_holders'
                            except (ValueError, TypeError):
                                pass
                except Exception:
                    pass
                time.sleep(0.3)

        result['token_distribution_public'] = score > 0
        result['distribution_score'] = score
        result['distribution_source'] = source

    # ═══════════════════════════════════════════════════════
    # CRITERION 4: AUDIT COMPLETED (0/3/6)
    # ═══════════════════════════════════════════════════════

    def _score_audit(
        self,
        result: Dict,
        all_text: str,
        audit_page_text: str,
        cg_description: str,
    ):
        """
        Score audit transparency.
        6 pts: Named auditor found + audit report link
        3 pts: Audit mentioned but no specific provider or link
        0 pts: No audit evidence
        """
        score = 0
        source = None
        provider = None
        audit_url = None

        combined_text = (all_text + ' ' + audit_page_text + ' ' +
                        (cg_description or '')).lower()

        # ── Check for named auditors ──
        for auditor in KNOWN_AUDITORS:
            if auditor in combined_text:
                score = 6
                provider = auditor.title()
                source = 'named_auditor_found'
                break

        # ── Check for audit report links ──
        if score < 6:
            audit_link_patterns = [
                r'audit[\s\-_]*report',
                r'security[\s\-_]*audit',
                r'smart[\s\-_]*contract[\s\-_]*audit',
                r'certificate.*audit',
            ]
            for pattern in audit_link_patterns:
                if re.search(pattern, combined_text):
                    if score < 6 and provider:
                        score = 6
                    else:
                        score = max(score, 3)
                    source = source or 'audit_report_mentioned'
                    break

        # ── Check for generic audit mentions ──
        if score < 3:
            audit_keywords = ['audited', 'audit completed', 'security review',
                            'code review', 'peer reviewed', 'formally verified',
                            'bug bounty', 'immunefi']
            for kw in audit_keywords:
                if kw in combined_text:
                    score = 3
                    source = 'audit_mentioned_generic'
                    break

        # ── Check for bug bounty programs (partial credit) ──
        if score < 3:
            if 'bug bounty' in combined_text or 'immunefi' in combined_text:
                score = 3
                source = 'bug_bounty_program'

        result['audit_completed'] = score > 0
        result['audit_score'] = score
        result['audit_provider'] = provider
        result['audit_source'] = source

    # ═══════════════════════════════════════════════════════
    # CRITERION 5: DOCUMENTATION + CONTRACT (0/3/6)
    # ═══════════════════════════════════════════════════════

    def _score_docs(
        self,
        result: Dict,
        all_text: str,
        docs_page_text: str,
        whitepaper_url: Optional[str],
        contract_address: Optional[str],
        chain: Optional[str],
        main_page_links: List[str],
    ):
        """
        Score documentation + contract verification.
        6 pts: Whitepaper/docs + verified contract
        3 pts: Either docs or verified contract
        0 pts: Neither
        """
        has_docs = False
        has_contract = False
        source_parts = []

        # ── Documentation check ──
        # Whitepaper from CoinGecko
        if whitepaper_url:
            has_docs = True
            result['whitepaper_url'] = whitepaper_url
            source_parts.append('whitepaper_url')

        # Docs page found
        if docs_page_text and len(docs_page_text) > 200:
            has_docs = True
            source_parts.append('docs_page')

        # Documentation links on website
        if not has_docs:
            docs_indicators = ['documentation', 'whitepaper', 'litepaper',
                             'technical paper', 'yellow paper', 'gitbook',
                             'docs.', 'wiki', 'developer docs']
            combined = (all_text or '').lower()
            for indicator in docs_indicators:
                if indicator in combined:
                    has_docs = True
                    source_parts.append('website_docs_link')
                    break

        # Check main page links for docs
        if not has_docs and main_page_links:
            for link in main_page_links:
                link_lower = link.lower()
                if any(kw in link_lower for kw in ['docs.', 'documentation',
                       'whitepaper', 'gitbook', '/docs']):
                    has_docs = True
                    result['docs_url'] = link
                    source_parts.append('website_docs_link_href')
                    break

        # ── Contract verification check ──
        if contract_address and chain:
            explorer = EXPLORER_APIS.get(chain)
            if explorer:
                api_key = os.environ.get(explorer['key_env'], '')
                try:
                    data = self._request(
                        explorer['base'],
                        params={
                            'module': 'contract',
                            'action': 'getabi',
                            'address': contract_address,
                            'apikey': api_key,
                        },
                        timeout=10,
                    )
                    if data and data.get('status') == '1':
                        abi = data.get('result', '')
                        if abi and abi != 'Contract source code not verified':
                            has_contract = True
                            result['contract_verified'] = True
                            source_parts.append('contract_verified')
                except Exception:
                    pass
                time.sleep(0.3)

        # ── Score ──
        if has_docs and has_contract:
            score = 6
        elif has_docs or has_contract:
            score = 3
        else:
            score = 0

        result['documentation_public'] = has_docs
        result['docs_score'] = score
        result['docs_source'] = '+'.join(source_parts) if source_parts else None

    # ═══════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════

    def _fetch_token_detail(self, slug: str) -> Optional[Dict]:
        """Fetch CoinGecko coin detail."""
        cached = self._cache_get(f'transparency_detail_{slug}')
        if cached:
            return cached

        data = self._request(
            f'{self.COINGECKO_BASE}/coins/{slug}',
            params={
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'false',
                'community_data': 'true',
                'developer_data': 'true',
            },
            timeout=15,
        )

        if data:
            detail = {
                'id': data.get('id'),
                'symbol': data.get('symbol'),
                'name': data.get('name'),
                'description': (data.get('description', {}).get('en', '') or '')[:2000],
                'genesis_date': data.get('genesis_date'),
                'categories': data.get('categories', []),
                'links': {
                    'homepage': (data.get('links', {}).get('homepage', []) or [None])[0],
                    'github': data.get('links', {}).get('repos_url', {}).get('github', []),
                    'twitter': data.get('links', {}).get('twitter_screen_name'),
                    'whitepaper': data.get('links', {}).get('whitepaper'),
                },
                'platforms': data.get('platforms', {}),
                'developer_data': data.get('developer_data', {}),
                'community_data': data.get('community_data', {}),
            }
            self._cache_set(f'transparency_detail_{slug}', detail, ttl=86400)
            return detail

        return None

    def _extract_primary_contract(self, platforms: Dict) -> Tuple[Optional[str], Optional[str]]:
        """Extract primary contract address and chain from CoinGecko platforms."""
        priority = ['ethereum', 'binance-smart-chain', 'polygon-pos', 'arbitrum-one']
        for chain in priority:
            addr = platforms.get(chain)
            if addr and len(addr) > 10:
                return addr, chain
        for chain, addr in platforms.items():
            if addr and len(addr) > 10:
                return addr, chain
        return None, None

    def _parse_github_url(self, url: str) -> Optional[str]:
        """Extract org/repo path from GitHub URL."""
        if not url:
            return None
        match = re.search(r'github\.com/([^/\s?#]+(?:/[^/\s?#]+)?)', url)
        if match:
            return match.group(1).rstrip('/')
        return None

    @staticmethod
    def _score_to_label(score: int) -> str:
        """Map transparency score (0-30) to label."""
        if score >= 26:
            return 'OPEN'
        elif score >= 19:
            return 'MOSTLY'
        elif score >= 13:
            return 'PARTIAL'
        elif score >= 7:
            return 'LIMITED'
        else:
            return 'OPAQUE'


if __name__ == '__main__':
    ct = CollectorTransparency()

    test_slugs = ['ethereum', 'bitcoin', 'uniswap', 'solana']
    for slug in test_slugs:
        print(f"\n{'='*50}")
        print(f"Scanning {slug}...")
        result = ct.scan(slug)

        print(f"\nResults for {slug}:")
        print(f"  Website: {result['website_url']} (accessible: {result['website_accessible']})")
        print(f"  Pages crawled: {result['pages_crawled']}")
        print(f"  ────────────────────────────")
        print(f"  Team:         {result['team_score']}/6 ({result['team_info_source']})")
        print(f"  Code:         {result['code_score']}/6 ({result['code_source']})")
        print(f"  Distribution: {result['distribution_score']}/6 ({result['distribution_source']})")
        print(f"  Audit:        {result['audit_score']}/6 ({result['audit_source']})")
        print(f"  Docs:         {result['docs_score']}/6 ({result['docs_source']})")
        print(f"  ────────────────────────────")
        print(f"  Score: {result['transparency_score']}/30")
        print(f"  Label: {result['transparency_label']}")

        time.sleep(3)  # Rate limit between tokens
