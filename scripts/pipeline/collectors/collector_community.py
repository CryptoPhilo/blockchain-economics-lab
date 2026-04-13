"""
Community Maturity Data Collector

Collects community health metrics from multiple sources:
  1. CoinGecko community_data (twitter, reddit, telegram)
  2. CoinGecko developer_data (GitHub metrics)
  3. GitHub API (detailed repo-level metrics)

These metrics feed into the Community Maturity Score in the MAT report.

Usage:
    from collectors.collector_community import collect_community_data
    data = collect_community_data('bitcoin', github_repo='bitcoin/bitcoin')
"""

import time
import requests
from typing import Dict, Any, Optional, List

# Rate limiting
_last_cg_call = 0.0
_CG_COOLDOWN = 1.5  # CoinGecko rate limit spacing

_last_gh_call = 0.0
_GH_COOLDOWN = 0.8  # GitHub rate limit spacing

_last_cp_call = 0.0
_CP_COOLDOWN = 1.0  # CoinPaprika rate limit spacing


def _cg_get(url: str, params: dict = None, timeout: int = 15) -> Optional[dict]:
    """CoinGecko API GET with rate limiting."""
    global _last_cg_call
    elapsed = time.time() - _last_cg_call
    if elapsed < _CG_COOLDOWN:
        time.sleep(_CG_COOLDOWN - elapsed)
    _last_cg_call = time.time()

    try:
        r = requests.get(url, params=params, timeout=timeout,
                         headers={'Accept': 'application/json'})
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print(f"[collector_community] CoinGecko rate limited, waiting 60s...")
            time.sleep(60)
            return None
        else:
            print(f"[collector_community] CoinGecko {r.status_code}: {url}")
            return None
    except Exception as e:
        print(f"[collector_community] CoinGecko error: {e}")
        return None


def _gh_get(url: str, token: str = None, timeout: int = 15) -> Optional[Any]:
    """GitHub API GET with rate limiting."""
    global _last_gh_call
    elapsed = time.time() - _last_gh_call
    if elapsed < _GH_COOLDOWN:
        time.sleep(_GH_COOLDOWN - elapsed)
    _last_gh_call = time.time()

    headers = {'Accept': 'application/vnd.github.v3+json'}
    if token:
        headers['Authorization'] = f'token {token}'

    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 403:
            print(f"[collector_community] GitHub rate limited")
            return None
        else:
            print(f"[collector_community] GitHub {r.status_code}: {url}")
            return None
    except Exception as e:
        print(f"[collector_community] GitHub error: {e}")
        return None


def _cp_get(url: str, params: dict = None, timeout: int = 15) -> Optional[dict]:
    """CoinPaprika API GET with rate limiting."""
    global _last_cp_call
    elapsed = time.time() - _last_cp_call
    if elapsed < _CP_COOLDOWN:
        time.sleep(_CP_COOLDOWN - elapsed)
    _last_cp_call = time.time()

    try:
        r = requests.get(url, params=params, timeout=timeout,
                         headers={'Accept': 'application/json'})
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            print(f"[collector_community] CoinPaprika rate limited, waiting 30s...")
            time.sleep(30)
            return None
        else:
            print(f"[collector_community] CoinPaprika {r.status_code}: {url}")
            return None
    except Exception as e:
        print(f"[collector_community] CoinPaprika error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────
# CoinGecko Community + Developer data
# ─────────────────────────────────────────────────────────────────────

def collect_coingecko_community(coingecko_id: str) -> Dict[str, Any]:
    """
    Extract community and developer metrics from CoinGecko /coins/{id}.

    Returns dict with standardized keys:
      - twitter_followers
      - reddit_subscribers
      - reddit_active_48h
      - reddit_avg_posts_48h
      - reddit_avg_comments_48h
      - telegram_members
      - facebook_likes
      - github_forks
      - github_stars
      - github_subscribers (watchers)
      - github_total_issues
      - github_closed_issues
      - github_pull_requests_merged
      - github_contributors
      - github_commits_4w (commit_count_4_weeks)
      - github_additions_4w
      - github_deletions_4w
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
    params = {
        'localization': 'false',
        'tickers': 'false',
        'market_data': 'false',
        'community_data': 'true',
        'developer_data': 'true',
        'sparkline': 'false',
    }

    data = _cg_get(url, params)
    if not data:
        return {'source': 'coingecko', 'error': 'Failed to fetch'}

    result = {'source': 'coingecko', 'coingecko_id': coingecko_id}

    # Community data
    community = data.get('community_data', {}) or {}
    result['twitter_followers'] = community.get('twitter_followers')
    result['reddit_subscribers'] = community.get('reddit_subscribers')
    result['reddit_active_48h'] = community.get('reddit_accounts_active_48h')
    result['reddit_avg_posts_48h'] = community.get('reddit_average_posts_48h')
    result['reddit_avg_comments_48h'] = community.get('reddit_average_comments_48h')
    result['telegram_members'] = community.get('telegram_channel_user_count')
    result['facebook_likes'] = community.get('facebook_likes')

    # Developer data
    developer = data.get('developer_data', {}) or {}
    result['github_forks'] = developer.get('forks')
    result['github_stars'] = developer.get('stars')
    result['github_subscribers'] = developer.get('subscribers')
    result['github_total_issues'] = developer.get('total_issues')
    result['github_closed_issues'] = developer.get('closed_issues')
    result['github_pull_requests_merged'] = developer.get('pull_requests_merged')
    result['github_contributors'] = developer.get('pull_request_contributors')
    result['github_commits_4w'] = developer.get('commit_count_4_weeks')
    code_changes = developer.get('code_additions_deletions_4_weeks', {}) or {}
    result['github_additions_4w'] = code_changes.get('additions')
    result['github_deletions_4w'] = code_changes.get('deletions')

    # Also capture CoinGecko categories for template matching
    result['categories'] = data.get('categories', [])

    # Links for reference
    links = data.get('links', {}) or {}
    result['homepage'] = (links.get('homepage', [None]) or [None])[0]
    result['twitter_handle'] = links.get('twitter_screen_name', '')
    result['telegram_id'] = links.get('telegram_channel_identifier', '')
    result['subreddit_url'] = links.get('subreddit_url', '')
    repos = links.get('repos_url', {}) or {}
    github_urls = repos.get('github', [])
    result['github_repos'] = [u for u in github_urls if u] if github_urls else []

    return result


# ─────────────────────────────────────────────────────────────────────
# CoinPaprika Community data (fallback)
# ─────────────────────────────────────────────────────────────────────

def _find_coinpaprika_id(coingecko_id: str) -> Optional[str]:
    """Search CoinPaprika for matching coin ID."""
    url = "https://api.coinpaprika.com/v1/search"
    data = _cp_get(url, params={'q': coingecko_id, 'limit': 3})
    if data and data.get('currencies'):
        return data['currencies'][0].get('id')
    return None


def collect_coinpaprika_community(coingecko_id: str) -> Dict[str, Any]:
    """
    Fallback: Extract community metrics from CoinPaprika /coins/{id}.

    CoinPaprika provides: twitter followers, reddit subscribers, GitHub repo links.
    Missing compared to CoinGecko: reddit active 48h, telegram members, developer_data details.
    """
    paprika_id = _find_coinpaprika_id(coingecko_id)
    if not paprika_id:
        return {'source': 'coinpaprika', 'error': 'Coin not found'}

    url = f"https://api.coinpaprika.com/v1/coins/{paprika_id}"
    data = _cp_get(url)
    if not data:
        return {'source': 'coinpaprika', 'error': 'Failed to fetch'}

    result = {'source': 'coinpaprika (fallback)', 'coingecko_id': coingecko_id}

    # Extract links_extended for social data
    links_ext = data.get('links_extended', [])
    twitter_followers = 0
    reddit_subscribers = 0
    github_repos = []

    for link in links_ext:
        url_val = link.get('url', '')
        stats = link.get('stats', {})
        link_type = link.get('type', '')

        if 'twitter.com' in url_val:
            twitter_followers = stats.get('followers', 0) or 0
        elif 'reddit.com' in url_val:
            reddit_subscribers = stats.get('subscribers', 0) or 0
        elif link_type == 'source_code' and 'github.com' in url_val:
            github_repos.append(url_val)
            # CoinPaprika may have stars/contributors in stats
            if stats.get('stars'):
                result['github_stars'] = stats['stars']
            if stats.get('contributors'):
                result['github_contributors'] = stats['contributors']

    result['twitter_followers'] = twitter_followers
    result['reddit_subscribers'] = reddit_subscribers
    result['reddit_active_48h'] = 0  # Not available in CoinPaprika
    result['reddit_avg_posts_48h'] = 0
    result['reddit_avg_comments_48h'] = 0
    result['telegram_members'] = 0  # Not directly available
    result['facebook_likes'] = 0
    result['github_repos'] = github_repos
    result['github_forks'] = result.get('github_forks', 0)
    result.setdefault('github_stars', 0)
    result['github_subscribers'] = 0
    result['github_total_issues'] = 0
    result['github_closed_issues'] = 0
    result['github_pull_requests_merged'] = 0
    result.setdefault('github_contributors', 0)
    result['github_commits_4w'] = 0  # Not available
    result['github_additions_4w'] = 0
    result['github_deletions_4w'] = 0
    result['categories'] = data.get('tags', [])

    # Links for reference
    links = data.get('links', {}) or {}
    website = links.get('website', [])
    result['homepage'] = website[0] if isinstance(website, list) and website else None
    result['twitter_handle'] = ''
    result['telegram_id'] = ''
    result['subreddit_url'] = ''

    for link in links_ext:
        url_val = link.get('url', '')
        if 'twitter.com' in url_val:
            # Extract handle from URL
            parts = url_val.rstrip('/').split('/')
            result['twitter_handle'] = parts[-1] if parts else ''
        elif 'reddit.com/r/' in url_val:
            result['subreddit_url'] = url_val
        elif 't.me/' in url_val or 'telegram' in url_val.lower():
            result['telegram_id'] = url_val.rstrip('/').split('/')[-1]

    return result


# ─────────────────────────────────────────────────────────────────────
# GitHub detailed metrics (optional, enhances CoinGecko data)
# ─────────────────────────────────────────────────────────────────────

def collect_github_details(repo_slug: str, token: str = None) -> Dict[str, Any]:
    """
    Collect detailed GitHub repo metrics.

    Args:
        repo_slug: 'owner/repo' format
        token: Optional GitHub personal access token

    Returns dict with:
      - stars, forks, watchers, open_issues
      - contributors_count
      - commit_activity_52w (weekly commit counts)
      - recent_releases (last 5)
      - languages
      - license
      - created_at, last_push
    """
    base = f"https://api.github.com/repos/{repo_slug}"
    result = {'source': 'github', 'repo': repo_slug}

    # Basic repo info
    repo = _gh_get(base, token)
    if not repo:
        return {'source': 'github', 'repo': repo_slug, 'error': 'Failed to fetch'}

    result['stars'] = repo.get('stargazers_count', 0)
    result['forks'] = repo.get('forks_count', 0)
    result['watchers'] = repo.get('subscribers_count', 0)
    result['open_issues'] = repo.get('open_issues_count', 0)
    result['language'] = repo.get('language', '')
    result['license'] = (repo.get('license') or {}).get('spdx_id', 'Unknown')
    result['created_at'] = repo.get('created_at', '')
    result['last_push'] = repo.get('pushed_at', '')
    result['description'] = repo.get('description', '')
    result['archived'] = repo.get('archived', False)

    # Contributors count (use per_page=1 and parse Link header)
    contrib_resp = _gh_get(f"{base}/contributors?per_page=1&anon=true", token)
    if isinstance(contrib_resp, list):
        # Try to get total from Link header — simplified: just count first page
        result['contributors_count'] = 1  # will be updated below if possible
    else:
        result['contributors_count'] = 0

    # Get actual contributor count by pagination
    try:
        r = requests.get(f"{base}/contributors?per_page=1&anon=true",
                         headers={'Accept': 'application/vnd.github.v3+json',
                                  **(({'Authorization': f'token {token}'}) if token else {})},
                         timeout=10)
        if r.status_code == 200 and 'Link' in r.headers:
            # Parse last page number from Link header
            links = r.headers['Link']
            for part in links.split(','):
                if 'rel="last"' in part:
                    import re
                    match = re.search(r'page=(\d+)', part)
                    if match:
                        result['contributors_count'] = int(match.group(1))
    except Exception:
        pass

    # Commit activity (52 weeks)
    activity = _gh_get(f"{base}/stats/commit_activity", token)
    if isinstance(activity, list) and len(activity) > 0:
        weekly_totals = [w.get('total', 0) for w in activity]
        result['commit_activity_52w'] = weekly_totals
        result['commits_last_4w'] = sum(weekly_totals[-4:])
        result['commits_last_12w'] = sum(weekly_totals[-12:])
        result['commits_total_52w'] = sum(weekly_totals)
        # Compute commit trend (last 4w vs prev 4w)
        recent = sum(weekly_totals[-4:])
        prev = sum(weekly_totals[-8:-4])
        if prev > 0:
            result['commit_trend_pct'] = round((recent - prev) / prev * 100, 1)
        else:
            result['commit_trend_pct'] = 100.0 if recent > 0 else 0.0

    # Recent releases
    releases = _gh_get(f"{base}/releases?per_page=5", token)
    if isinstance(releases, list):
        result['recent_releases'] = [
            {
                'tag': r.get('tag_name', ''),
                'name': r.get('name', ''),
                'published_at': r.get('published_at', ''),
                'prerelease': r.get('prerelease', False),
            }
            for r in releases[:5]
        ]
        result['release_count_recent'] = len(releases)

    return result


# ─────────────────────────────────────────────────────────────────────
# Unified collection
# ─────────────────────────────────────────────────────────────────────

def collect_community_data(
    coingecko_id: str,
    github_repo: str = None,
    github_token: str = None,
) -> Dict[str, Any]:
    """
    Collect all community maturity data for a project.

    Merges CoinGecko community/developer data with optional GitHub detailed metrics.

    Returns unified dict ready for compute_community_score().
    """
    result = {
        'coingecko_id': coingecko_id,
        'collected_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }

    # 1. CoinGecko community + developer data (primary)
    cg_data = collect_coingecko_community(coingecko_id)
    if 'error' not in cg_data:
        source_data = cg_data
        result['_community_source'] = 'CoinGecko'
    else:
        # Fallback: CoinPaprika
        print(f"    ⚠ community_data: CoinGecko failed, trying CoinPaprika fallback...")
        cp_data = collect_coinpaprika_community(coingecko_id)
        if 'error' not in cp_data:
            source_data = cp_data
            result['_community_source'] = 'CoinPaprika (fallback)'
        else:
            source_data = None
            result['_community_source'] = 'none (both failed)'
            result['coingecko_error'] = cg_data.get('error')
            result['coinpaprika_error'] = cp_data.get('error')

    if source_data and 'error' not in source_data:
        result.update({
            # Social metrics
            'twitter_followers': source_data.get('twitter_followers') or 0,
            'reddit_subscribers': source_data.get('reddit_subscribers') or 0,
            'reddit_active_48h': source_data.get('reddit_active_48h') or 0,
            'reddit_avg_posts_48h': source_data.get('reddit_avg_posts_48h') or 0,
            'reddit_avg_comments_48h': source_data.get('reddit_avg_comments_48h') or 0,
            'telegram_members': source_data.get('telegram_members') or 0,
            'facebook_likes': source_data.get('facebook_likes') or 0,

            # Developer metrics
            'github_forks': source_data.get('github_forks') or 0,
            'github_stars': source_data.get('github_stars') or 0,
            'github_contributors': source_data.get('github_contributors') or 0,
            'github_commits_30d': source_data.get('github_commits_4w') or 0,
            'github_total_issues': source_data.get('github_total_issues') or 0,
            'github_closed_issues': source_data.get('github_closed_issues') or 0,
            'github_prs_merged': source_data.get('github_pull_requests_merged') or 0,
            'github_additions_4w': source_data.get('github_additions_4w') or 0,
            'github_deletions_4w': source_data.get('github_deletions_4w') or 0,

            # Metadata
            'categories': source_data.get('categories', []),
            'github_repos': source_data.get('github_repos', []),
            'twitter_handle': source_data.get('twitter_handle', ''),
            'telegram_id': source_data.get('telegram_id', ''),
            'subreddit_url': source_data.get('subreddit_url', ''),
        })

    # Compute multi-platform presence count
    platforms = 0
    if result.get('twitter_followers', 0) > 0: platforms += 1
    if result.get('reddit_subscribers', 0) > 0: platforms += 1
    if result.get('telegram_members', 0) > 0: platforms += 1
    if result.get('facebook_likes', 0) > 0: platforms += 1
    if result.get('github_stars', 0) > 0: platforms += 1
    if result.get('subreddit_url'): platforms += 1  # has subreddit
    result['multi_platform_presence'] = platforms

    # Compute social engagement rate (simplified: reddit activity / subscribers)
    subs = result.get('reddit_subscribers', 0)
    active = result.get('reddit_active_48h', 0)
    if subs > 0 and active > 0:
        result['social_engagement_rate'] = round((active / subs) * 100, 2)
    else:
        result['social_engagement_rate'] = 0

    # 2. GitHub detailed metrics (optional, enhances CoinGecko data)
    gh_repo = github_repo
    if not gh_repo and result.get('github_repos'):
        # Auto-detect from CoinGecko github repos
        for url in result['github_repos']:
            # Extract owner/repo from GitHub URL
            if 'github.com/' in url:
                parts = url.rstrip('/').split('github.com/')[-1].split('/')
                if len(parts) >= 2:
                    gh_repo = f"{parts[0]}/{parts[1]}"
                    break

    if gh_repo:
        gh_data = collect_github_details(gh_repo, github_token)
        if 'error' not in gh_data:
            # Override CoinGecko data with more accurate GitHub data
            result['github_repo_primary'] = gh_repo
            if gh_data.get('contributors_count', 0) > 0:
                result['github_contributors'] = gh_data['contributors_count']
            if gh_data.get('commits_last_4w', 0) > 0:
                result['github_commits_30d'] = gh_data['commits_last_4w']
            result['github_commits_12w'] = gh_data.get('commits_last_12w', 0)
            result['github_commits_52w'] = gh_data.get('commits_total_52w', 0)
            result['github_commit_trend_pct'] = gh_data.get('commit_trend_pct', 0)
            result['github_license'] = gh_data.get('license', 'Unknown')
            result['github_created_at'] = gh_data.get('created_at', '')
            result['github_last_push'] = gh_data.get('last_push', '')
            result['github_archived'] = gh_data.get('archived', False)
            result['github_recent_releases'] = gh_data.get('recent_releases', [])
            result['github_open_issues'] = gh_data.get('open_issues', 0)
        else:
            result['github_error'] = gh_data.get('error')

    return result


def health_check() -> Dict[str, Any]:
    """Test collector health (including fallback sources)."""
    try:
        data = _cg_get("https://api.coingecko.com/api/v3/ping")
        cg_ok = data is not None and 'gecko_says' in (data or {})
    except Exception:
        cg_ok = False

    try:
        gh = _gh_get("https://api.github.com/rate_limit")
        gh_ok = gh is not None
        gh_remaining = (gh or {}).get('rate', {}).get('remaining', 0) if gh else 0
    except Exception:
        gh_ok = False
        gh_remaining = 0

    try:
        cp = _cp_get("https://api.coinpaprika.com/v1/global")
        cp_ok = cp is not None
    except Exception:
        cp_ok = False

    return {
        'collector': 'community',
        'coingecko_available': cg_ok,
        'coinpaprika_available': cp_ok,
        'github_available': gh_ok,
        'github_rate_remaining': gh_remaining,
    }
