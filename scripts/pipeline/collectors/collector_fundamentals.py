"""
Fundamentals Data Collector
Collects GitHub statistics and project links from CoinGecko.
"""

import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_collector import BaseCollector


class CollectorFundamentals(BaseCollector):
    """Collector for fundamental project data with CoinGecko (primary) + CoinPaprika (fallback)."""

    GITHUB_BASE_URL = 'https://api.github.com'
    COINGECKO_BASE_URL = 'https://api.coingecko.com/api/v3'
    COINPAPRIKA_BASE_URL = 'https://api.coinpaprika.com/v1'
    RATE_LIMIT_SLEEP = 0.5

    def fetch_github_info(self, org_or_repo: str) -> Optional[Dict[str, Any]]:
        """
        Fetch GitHub repository information.

        Args:
            org_or_repo: Organization/repo path (e.g., 'uniswap/v3-core' or 'uniswap')

        Returns:
            Dict with keys:
            - name
            - full_name
            - description
            - url
            - stars
            - forks
            - open_issues
            - language
            - last_push_date
            - is_fork
            - topics
            - last_updated
            - source
            Or None on failure
        """
        cache_key = f'github_info_{org_or_repo.lower()}'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            time.sleep(self.RATE_LIMIT_SLEEP)

            # Try as repo first (org/repo), then as org
            if '/' in org_or_repo:
                url = f'{self.GITHUB_BASE_URL}/repos/{org_or_repo}'
            else:
                url = f'{self.GITHUB_BASE_URL}/orgs/{org_or_repo}'

            data = self._request(url)
            if not data:
                return None

            # For organization, try to get most starred repo
            if 'repos_url' in data:
                # This is an org, not a repo
                return {
                    'type': 'organization',
                    'name': data.get('login'),
                    'public_repos': data.get('public_repos'),
                    'followers': data.get('followers'),
                    'public_gists': data.get('public_gists'),
                    'last_updated': datetime.utcnow().isoformat(),
                    'source': 'GitHub',
                }

            # This is a repo
            result = {
                'name': data.get('name'),
                'full_name': data.get('full_name'),
                'description': data.get('description'),
                'url': data.get('html_url'),
                'stars': data.get('stargazers_count'),
                'forks': data.get('forks_count'),
                'open_issues': data.get('open_issues_count'),
                'language': data.get('language'),
                'last_push_date': data.get('pushed_at'),
                'is_fork': data.get('fork'),
                'topics': data.get('topics', []),
                'last_updated': datetime.utcnow().isoformat(),
                'source': 'GitHub',
            }

            self._cache_set(cache_key, result, ttl=86400)  # 24h cache
            return result

        except Exception:
            return None

    def fetch_project_links(self, coingecko_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch project links and metadata with automatic fallback.
        Primary: CoinGecko → Fallback: CoinPaprika
        """
        cache_key = f'project_links_{coingecko_id}'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        result = self._try_with_fallback(
            primary_fn=lambda: self._fetch_links_coingecko(coingecko_id),
            fallback_fn=lambda: self._fetch_links_coinpaprika(coingecko_id),
            metric_name='project_links',
            primary_label='CoinGecko',
            fallback_label='CoinPaprika',
        )
        if result:
            self._cache_set(cache_key, result, ttl=86400)
        return result

    def _fetch_links_coingecko(self, coingecko_id: str) -> Optional[Dict[str, Any]]:
        """Primary: CoinGecko /coins/{id}"""
        time.sleep(self.RATE_LIMIT_SLEEP)
        url = f'{self.COINGECKO_BASE_URL}/coins/{coingecko_id}'
        data = self._request(url)
        if not data:
            return None

        links = data.get('links', {})
        github_url = links.get('repos_url', {}).get('github', [None])[0]
        github_org = None
        if github_url:
            match = re.search(r'github\.com/([^/]+)', github_url)
            if match:
                github_org = match.group(1)

        return {
            'name': data.get('name'),
            'symbol': data.get('symbol', '').upper(),
            'website': links.get('homepage', [None])[0],
            'whitepaper_url': links.get('whitepaper'),
            'github': github_url,
            'twitter': links.get('twitter_screen_name'),
            'discord': links.get('chat_url', [None])[0],
            'telegram': links.get('telegram_channel_identifier'),
            'reddit': links.get('subreddit_url'),
            'medium': links.get('official_forum_url'),
            'github_org': github_org,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinGecko',
        }

    def _fetch_links_coinpaprika(self, coingecko_id: str) -> Optional[Dict[str, Any]]:
        """
        Fallback: CoinPaprika /coins/{id}.
        CoinPaprika IDs typically use format like 'uni-uniswap', 'btc-bitcoin'.
        We try the coingecko_id directly and also search.
        """
        time.sleep(0.5)
        # CoinPaprika search to find the coin
        search_url = f'{self.COINPAPRIKA_BASE_URL}/search'
        search_data = self._request(search_url, params={'q': coingecko_id, 'limit': 1})
        paprika_id = None
        if search_data and search_data.get('currencies'):
            paprika_id = search_data['currencies'][0].get('id')

        if not paprika_id:
            return None

        url = f'{self.COINPAPRIKA_BASE_URL}/coins/{paprika_id}'
        data = self._request(url)
        if not data:
            return None

        links_data = data.get('links', {})
        links_ext = data.get('links_extended', [])

        # Extract specific links from links_extended
        github_url = None
        discord_url = None
        medium_url = None
        for link in links_ext:
            link_type = link.get('type', '')
            link_url = link.get('url', '')
            if link_type == 'source_code' and 'github' in link_url:
                github_url = link_url
            elif link_type == 'chat' and 'discord' in link_url:
                discord_url = link_url
            elif link_type == 'blog' and 'medium' in link_url:
                medium_url = link_url

        github_org = None
        if github_url:
            match = re.search(r'github\.com/([^/]+)', github_url)
            if match:
                github_org = match.group(1)

        return {
            'name': data.get('name'),
            'symbol': (data.get('symbol') or '').upper(),
            'website': links_data.get('website', [None])[0] if isinstance(links_data.get('website'), list) else links_data.get('website'),
            'whitepaper_url': data.get('whitepaper', {}).get('link') if isinstance(data.get('whitepaper'), dict) else None,
            'github': github_url,
            'twitter': data.get('links', {}).get('twitter', [None])[0] if isinstance(data.get('links', {}).get('twitter'), list) else None,
            'discord': discord_url,
            'telegram': None,
            'reddit': links_data.get('reddit', [None])[0] if isinstance(links_data.get('reddit'), list) else links_data.get('reddit'),
            'medium': medium_url,
            'github_org': github_org,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'CoinPaprika (fallback)',
        }

    def fetch_combined_fundamentals(
        self,
        coingecko_id: str,
        github_org: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch both CoinGecko links and GitHub data for a project.

        Args:
            coingecko_id: CoinGecko ID
            github_org: Optional GitHub org/repo to fetch (if not in CoinGecko data)

        Returns:
            Combined dict with all data from both sources
        """
        try:
            # Get links from CoinGecko
            links = self.fetch_project_links(coingecko_id)
            if not links:
                return None

            # Determine GitHub org to fetch
            github_to_fetch = github_org or links.get('github_org')
            github_data = None

            if github_to_fetch:
                github_data = self.fetch_github_info(github_to_fetch)

            result = {
                'coingecko_id': coingecko_id,
                'name': links.get('name'),
                'symbol': links.get('symbol'),
                'links': links,
                'github': github_data,
                'last_updated': datetime.utcnow().isoformat(),
                'source': 'CoinGecko + GitHub',
            }

            return result

        except Exception:
            return None


if __name__ == '__main__':
    print("Testing CollectorFundamentals with Uniswap...")
    collector = CollectorFundamentals()

    # Test project links
    print("\n1. Fetching Uniswap project links from CoinGecko...")
    links = collector.fetch_project_links('uniswap')
    if links:
        print(f"   Name: {links.get('name')}")
        print(f"   Symbol: {links.get('symbol')}")
        print(f"   Website: {links.get('website')}")
        print(f"   GitHub: {links.get('github')}")
        print(f"   GitHub org: {links.get('github_org')}")
        print(f"   Twitter: {links.get('twitter')}")
        print(f"   Discord: {links.get('discord')}")
    else:
        print("   Failed to fetch project links")

    # Test GitHub info
    print("\n2. Fetching Uniswap GitHub info...")
    github = collector.fetch_github_info('uniswap')
    if github:
        if github.get('type') == 'organization':
            print(f"   Type: Organization")
            print(f"   Name: {github.get('name')}")
            print(f"   Public repos: {github.get('public_repos')}")
            print(f"   Followers: {github.get('followers')}")
        else:
            print(f"   Name: {github.get('full_name')}")
            print(f"   Stars: {github.get('stars')}")
            print(f"   Forks: {github.get('forks')}")
            print(f"   Language: {github.get('language')}")
            print(f"   Last push: {github.get('last_push_date')}")
    else:
        print("   Failed to fetch GitHub info")

    # Test combined fundamentals
    print("\n3. Fetching combined fundamentals...")
    combined = collector.fetch_combined_fundamentals('uniswap')
    if combined:
        print(f"   Project: {combined.get('name')} ({combined.get('symbol')})")
        print(f"   Has links data: {combined.get('links') is not None}")
        print(f"   Has GitHub data: {combined.get('github') is not None}")
        print(f"   Source: {combined.get('source')}")
    else:
        print("   Failed to fetch combined fundamentals")

    print("\nCollectorFundamentals test complete!")
