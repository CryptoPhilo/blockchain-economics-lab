"""
On-Chain Data Collector
Combines data from:
- Etherscan API (token info, holder data)
- DeFiLlama API (protocol TVL)
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_collector import BaseCollector


class CollectorOnchain(BaseCollector):
    """Collector for on-chain data with Etherscan (primary) + Blockscout (fallback), and DeFiLlama."""

    ETHERSCAN_BASE_URL = 'https://api.etherscan.io/api'
    BLOCKSCOUT_BASE_URL = 'https://eth.blockscout.com/api/v2'
    DEFILLLAMA_BASE_URL = 'https://api.llama.fi'

    # Known exchange addresses for whale tracking
    EXCHANGE_ADDRESSES = {
        'binance_hot_1': '0x1111111254fb6c44bac0bed2854e76f90643097d',
        'coinbase': '0x71c7656ec7ab88b098defb751b7401b5f6d8976f',
        'kraken': '0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0',
        'binance_hot_2': '0x8fa3b4570b4c96f8036c13d06d2e7e38e7e07e7d',
        'huobi': '0xab5c66542510ce61583fac1731bb3d37e0c6f7a2',
        'okex': '0x6cc5f688a315f3dc28a7781717a9a798a59fda7b',
        'gate': '0x7f101fe45e6649a6ad0ea1b8b93674e169222cfe',
        'gemini': '0xd24400ae8bfeba18d7e02b0ecffe87b68e330fee',
    }

    def fetch_token_info(
        self,
        contract_address: str,
        chain: str = 'ethereum',
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch token information with automatic fallback.
        Primary: Etherscan → Fallback: Blockscout
        """
        if not contract_address.startswith('0x'):
            contract_address = '0x' + contract_address
        addr = contract_address.lower()

        cache_key = f'token_info_{addr}'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        result = self._try_with_fallback(
            primary_fn=lambda: self._fetch_token_etherscan(addr),
            fallback_fn=lambda: self._fetch_token_blockscout(addr),
            metric_name='token_info',
            primary_label='Etherscan',
            fallback_label='Blockscout',
        )
        if result:
            self._cache_set(cache_key, result, ttl=86400)
        return result

    def _fetch_token_etherscan(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Primary: Etherscan tokeninfo"""
        params = {
            'module': 'token',
            'action': 'tokeninfo',
            'contractaddress': contract_address,
        }
        data = self._request(self.ETHERSCAN_BASE_URL, params=params)
        if not data or not isinstance(data, dict):
            return None
        token_data = data if isinstance(data, dict) else data.get('result', {})
        return {
            'name': token_data.get('name'),
            'symbol': token_data.get('symbol'),
            'decimals': token_data.get('decimals'),
            'total_supply': token_data.get('totalSupply'),
            'website': token_data.get('website'),
            'description': token_data.get('description'),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'Etherscan',
        }

    def _fetch_token_blockscout(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Fallback: Blockscout /tokens/{address}"""
        time.sleep(0.5)
        url = f'{self.BLOCKSCOUT_BASE_URL}/tokens/{contract_address}'
        data = self._request(url)
        if not data or not isinstance(data, dict):
            return None
        return {
            'name': data.get('name'),
            'symbol': data.get('symbol'),
            'decimals': data.get('decimals'),
            'total_supply': data.get('total_supply'),
            'website': None,  # Blockscout doesn't provide website
            'description': None,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'Blockscout (fallback)',
        }

    def fetch_top_holders(
        self,
        contract_address: str,
        chain: str = 'ethereum',
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch top token holders with automatic fallback.
        Primary: Etherscan → Fallback: Blockscout
        """
        if not contract_address.startswith('0x'):
            contract_address = '0x' + contract_address
        addr = contract_address.lower()

        cache_key = f'token_holders_{addr}'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        result = self._try_with_fallback(
            primary_fn=lambda: self._fetch_holders_etherscan(addr),
            fallback_fn=lambda: self._fetch_holders_blockscout(addr),
            metric_name='top_holders',
            primary_label='Etherscan',
            fallback_label='Blockscout',
        )
        if result:
            self._cache_set(cache_key, result, ttl=86400)
        return result

    def _fetch_holders_etherscan(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Primary: Etherscan tokenholderlist"""
        params = {
            'module': 'token',
            'action': 'tokenholderlist',
            'contractaddress': contract_address,
            'page': 1,
            'offset': 20,
        }
        data = self._request(self.ETHERSCAN_BASE_URL, params=params)

        if data and isinstance(data, dict):
            if data.get('message') == 'Max rate limit reached':
                return None  # Let fallback handle it

        if not data or not isinstance(data, (dict, list)):
            return None

        holders_raw = data if isinstance(data, list) else data.get('result', [])
        if not holders_raw or (isinstance(holders_raw, str)):
            return None

        holders = []
        for holder in holders_raw[:20]:
            if isinstance(holder, dict):
                holders.append({
                    'address': holder.get('address'),
                    'quantity': holder.get('quantity'),
                    'percentage': holder.get('percentage'),
                })
        return {
            'holders': holders,
            'total_holders': len(holders),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'Etherscan',
        }

    def _fetch_holders_blockscout(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """Fallback: Blockscout /tokens/{address}/holders"""
        time.sleep(0.5)
        url = f'{self.BLOCKSCOUT_BASE_URL}/tokens/{contract_address}/holders'
        data = self._request(url)
        if not data or not isinstance(data, dict):
            return None

        items = data.get('items', [])
        holders = []
        for item in items[:20]:
            if isinstance(item, dict):
                addr_info = item.get('address', {})
                holders.append({
                    'address': addr_info.get('hash') if isinstance(addr_info, dict) else None,
                    'quantity': item.get('value'),
                    'percentage': None,  # Blockscout may not provide percentage directly
                })
        return {
            'holders': holders,
            'total_holders': len(holders),
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'Blockscout (fallback)',
        }

    def fetch_protocol_tvl(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Fetch protocol TVL (Total Value Locked) from DeFiLlama.

        Args:
            slug: Protocol slug (e.g., 'uniswap', 'aave', 'lido')

        Returns:
            Dict with keys:
            - name
            - tvl (current TVL in USD)
            - chain_tvls (TVL by chain)
            - tvl_change_24h
            - tvl_change_7d
            - last_updated
            - source
            Or None on failure
        """
        cache_key = f'defilllama_tvl_{slug}'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            time.sleep(0.5)  # Rate limit
            url = f'{self.DEFILLLAMA_BASE_URL}/protocol/{slug}'

            data = self._request(url)
            if not data:
                return None

            # Extract current TVL from chainTvls if tvl is a list
            tvl_value = data.get('tvl')
            if isinstance(tvl_value, list) and tvl_value:
                # If tvl is historical data, get the latest value
                tvl_value = tvl_value[-1].get('totalLiquidityUSD', tvl_value[-1]) if isinstance(tvl_value[-1], dict) else None

            # Also try to get current TVL from chainTvls
            if not tvl_value:
                chain_tvls = data.get('chainTvls', {})
                if isinstance(chain_tvls, dict):
                    tvl_value = sum(
                        v if isinstance(v, (int, float)) else 0
                        for v in chain_tvls.values()
                    ) or None

            result = {
                'name': data.get('name'),
                'tvl': tvl_value,
                'chain_tvls': data.get('chainTvls', {}),
                'tvl_change_24h': data.get('change_1d'),
                'tvl_change_7d': data.get('change_7d'),
                'last_updated': datetime.utcnow().isoformat(),
                'source': 'DeFiLlama',
            }

            self._cache_set(cache_key, result, ttl=3600)
            return result

        except Exception:
            return None

    def fetch_protocol_list(self) -> Optional[Dict[str, Any]]:
        """
        Fetch list of all protocols from DeFiLlama for slug lookup.

        Returns:
            Dict with keys:
            - protocols (list of dicts with name, slug, tvl)
            - total_count
            - last_updated
            - source
            Or None on failure
        """
        cache_key = 'defilllama_protocols_list'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            url = f'{self.DEFILLLAMA_BASE_URL}/protocols'

            data = self._request(url)
            if not data or not isinstance(data, list):
                return None

            protocols = []
            for protocol in data[:100]:  # Top 100
                if isinstance(protocol, dict):
                    protocols.append({
                        'name': protocol.get('name'),
                        'slug': protocol.get('slug'),
                        'tvl': protocol.get('tvl'),
                    })

            result = {
                'protocols': protocols,
                'total_count': len(protocols),
                'last_updated': datetime.utcnow().isoformat(),
                'source': 'DeFiLlama',
            }

            self._cache_set(cache_key, result, ttl=3600)
            return result

        except Exception:
            return None


if __name__ == '__main__':
    print("Testing CollectorOnchain...")
    collector = CollectorOnchain()

    # Test token info
    print("\n1. Fetching Uniswap token info...")
    token_info = collector.fetch_token_info('0x1f9840a85d5af5bf1d1762f925bdaddc4201f984')
    if token_info:
        print(f"   Name: {token_info.get('name')}")
        print(f"   Symbol: {token_info.get('symbol')}")
        print(f"   Decimals: {token_info.get('decimals')}")
        print(f"   Source: {token_info.get('source')}")
    else:
        print("   Failed to fetch token info")

    # Test top holders (may require API key)
    print("\n2. Fetching top holders...")
    holders = collector.fetch_top_holders('0x1f9840a85d5af5bf1d1762f925bdaddc4201f984')
    if holders:
        if holders.get('requires_api_key_warning'):
            print(f"   Note: {holders.get('error')}")
        else:
            print(f"   Total holders found: {holders.get('total_holders')}")
            if holders.get('holders'):
                print(f"   Top holder: {holders['holders'][0]}")
    else:
        print("   Failed to fetch holders")

    # Test protocol TVL
    print("\n3. Fetching Uniswap TVL...")
    tvl = collector.fetch_protocol_tvl('uniswap')
    if tvl:
        print(f"   Name: {tvl.get('name')}")
        tvl_value = tvl.get('tvl')
        if isinstance(tvl_value, (int, float)):
            print(f"   TVL: ${tvl_value:,.0f}")
        else:
            print(f"   TVL: {tvl_value}")
        print(f"   24h change: {tvl.get('tvl_change_24h')}%")
    else:
        print("   Failed to fetch TVL")

    # Test protocol list
    print("\n4. Fetching protocol list...")
    protocols = collector.fetch_protocol_list()
    if protocols:
        print(f"   Total protocols: {protocols.get('total_count')}")
        if protocols.get('protocols'):
            print(f"   First protocol: {protocols['protocols'][0]}")
    else:
        print("   Failed to fetch protocol list")

    print("\nCollectorOnchain test complete!")
