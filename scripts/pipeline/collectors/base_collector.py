"""
Base Collector Class
Provides common functionality for all data collectors:
- HTTP requests with retry and exponential backoff
- File-based JSON caching
- Graceful error handling
- Fallback/redundancy support for data source failover
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests


class BaseCollector:
    """Base class for all data collectors with HTTP, caching, and fallback utilities."""

    CACHE_DIR = Path(__file__).parent / '.cache'
    DEFAULT_TIMEOUT = 10
    DEFAULT_TTL = 3600  # 1 hour in seconds

    def __init__(self):
        """Initialize collector and ensure cache directory exists."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'BCE-Lab-Collector/1.0 (+https://blockchain-econ.org)'
        })
        # Track which sources were used (primary vs fallback)
        self._source_log: List[Dict[str, str]] = []

    def _request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        Perform HTTP GET request with retry logic and exponential backoff.

        Args:
            url: The URL to request
            params: Query parameters
            timeout: Request timeout in seconds
            max_retries: Number of retry attempts

        Returns:
            Parsed JSON response as dict, or None on failure
        """
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    time.sleep(wait_time)
                    continue
                return None

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                # 429 Too Many Requests: wait longer and retry
                if status == 429:
                    wait_time = min(30, 5 * (attempt + 1))  # 5s, 10s, 15s
                    print(f"    [Rate limit 429] Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    if attempt < max_retries - 1:
                        continue
                    return None
                # Don't retry on other 4xx errors (client errors)
                if 400 <= status < 500:
                    return None
                # Retry on 5xx errors
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                return None

            except (requests.exceptions.RequestException, json.JSONDecodeError):
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                return None

            except Exception:
                # Unexpected error, don't retry
                return None

        return None

    def _cache_key(self, key: str) -> str:
        """Generate cache file path from key."""
        # Sanitize key for filesystem
        safe_key = key.replace('/', '_').replace(':', '_').replace('?', '_')
        return str(self.CACHE_DIR / f'{safe_key}.json')

    def _cache_get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve data from file-based cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached data dict, or None if not found or expired
        """
        cache_path = self._cache_key(key)

        try:
            if not os.path.exists(cache_path):
                return None

            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check if expired
            if 'expires_at' in cache_data:
                if datetime.fromisoformat(cache_data['expires_at']) < datetime.utcnow():
                    os.remove(cache_path)
                    return None

            return cache_data.get('data')

        except Exception:
            return None

    def _cache_set(
        self,
        key: str,
        data: Dict[str, Any],
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """
        Store data in file-based cache with TTL.

        Args:
            key: Cache key
            data: Data to cache
            ttl: Time-to-live in seconds

        Returns:
            True if successful, False otherwise
        """
        cache_path = self._cache_key(key)

        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            cache_data = {
                'data': data,
                'expires_at': expires_at.isoformat(),
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)

            return True

        except Exception:
            return False


    def _try_with_fallback(
        self,
        primary_fn: Callable[[], Optional[Dict[str, Any]]],
        fallback_fn: Callable[[], Optional[Dict[str, Any]]],
        metric_name: str,
        primary_label: str = 'primary',
        fallback_label: str = 'fallback',
    ) -> Optional[Dict[str, Any]]:
        """
        Execute primary function, falling back to secondary on failure.

        Args:
            primary_fn: Primary data source callable (returns dict or None)
            fallback_fn: Fallback data source callable
            metric_name: Human-readable metric name for logging
            primary_label: Label for primary source
            fallback_label: Label for fallback source

        Returns:
            Data dict from whichever source succeeded, or None if both fail
        """
        # Try primary
        try:
            result = primary_fn()
            if result is not None:
                self._source_log.append({
                    'metric': metric_name,
                    'source': primary_label,
                    'status': 'ok',
                    'timestamp': datetime.utcnow().isoformat(),
                })
                return result
        except Exception:
            pass

        # Primary failed — try fallback
        print(f"    ⚠ {metric_name}: primary ({primary_label}) failed, trying fallback ({fallback_label})...")
        try:
            result = fallback_fn()
            if result is not None:
                self._source_log.append({
                    'metric': metric_name,
                    'source': fallback_label,
                    'status': 'fallback',
                    'timestamp': datetime.utcnow().isoformat(),
                })
                if isinstance(result, dict):
                    result['_fallback'] = True
                    result['_primary_source'] = primary_label
                    result['_fallback_source'] = fallback_label
                return result
        except Exception:
            pass

        # Both failed
        self._source_log.append({
            'metric': metric_name,
            'source': 'none',
            'status': 'failed',
            'timestamp': datetime.utcnow().isoformat(),
        })
        print(f"    ✗ {metric_name}: both sources failed")
        return None

    def get_source_log(self) -> List[Dict[str, str]]:
        """Return log of which data sources were used."""
        return list(self._source_log)


if __name__ == '__main__':
    # Test basic collector functionality
    print("Testing BaseCollector...")
    collector = BaseCollector()

    # Test cache operations
    test_data = {'test': 'value', 'number': 42}
    collector._cache_set('test_key', test_data, ttl=3600)
    retrieved = collector._cache_get('test_key')
    print(f"Cache test: {retrieved == test_data}")

    # Test fallback mechanism
    def primary_fail():
        return None
    def fallback_ok():
        return {'data': 'from_fallback', 'source': 'test_fallback'}
    result = collector._try_with_fallback(primary_fail, fallback_ok, 'test_metric', 'primary', 'fallback')
    print(f"Fallback test: {result is not None and result.get('_fallback') == True}")
    print(f"Source log: {collector.get_source_log()}")

    print("BaseCollector initialized successfully")
