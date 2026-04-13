"""
Whale Tracking Collector
Monitors large token transfers and exchange flows.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_collector import BaseCollector


class CollectorWhale(BaseCollector):
    """Collector for whale activity and large transfers with Etherscan (primary) + Blockscout (fallback)."""

    ETHERSCAN_BASE_URL = 'https://api.etherscan.io/api'
    BLOCKSCOUT_BASE_URL = 'https://eth.blockscout.com/api/v2'

    # Known exchange addresses for flow classification
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

    def fetch_large_transfers(
        self,
        contract_address: str,
        min_value_usd: float = 100000,
        chain: str = 'ethereum',
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch recent large token transfers with automatic fallback.
        Primary: Etherscan → Fallback: Blockscout
        """
        if not contract_address.startswith('0x'):
            contract_address = '0x' + contract_address
        addr = contract_address.lower()

        cache_key = f'large_transfers_{addr}'
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        result = self._try_with_fallback(
            primary_fn=lambda: self._fetch_transfers_etherscan(addr, min_value_usd),
            fallback_fn=lambda: self._fetch_transfers_blockscout(addr, min_value_usd),
            metric_name='large_transfers',
            primary_label='Etherscan',
            fallback_label='Blockscout',
        )
        if result:
            self._cache_set(cache_key, result, ttl=600)
        return result

    def _fetch_transfers_etherscan(self, contract_address: str, min_value_usd: float) -> Optional[Dict[str, Any]]:
        """Primary: Etherscan tokentx"""
        params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': contract_address,
            'sort': 'desc',
            'page': 1,
            'offset': 50,
        }
        data = self._request(self.ETHERSCAN_BASE_URL, params=params)
        if not data:
            return None

        transfers_raw = data if isinstance(data, list) else data.get('result', [])
        if not transfers_raw or isinstance(transfers_raw, str):
            return None

        transfers = []
        for tx in transfers_raw[:50]:
            if isinstance(tx, dict):
                transfers.append({
                    'from': tx.get('from'),
                    'to': tx.get('to'),
                    'value': tx.get('value'),
                    'tokenDecimal': tx.get('tokenDecimal'),
                    'hash': tx.get('hash'),
                    'blockNumber': tx.get('blockNumber'),
                    'timeStamp': tx.get('timeStamp'),
                    'timestamp': datetime.fromtimestamp(
                        int(tx.get('timeStamp', 0))
                    ).isoformat() if tx.get('timeStamp') else None,
                })
        return {
            'transfers': transfers,
            'total_count': len(transfers),
            'min_value_filter_usd': min_value_usd,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'Etherscan',
        }

    def _fetch_transfers_blockscout(self, contract_address: str, min_value_usd: float) -> Optional[Dict[str, Any]]:
        """Fallback: Blockscout /tokens/{address}/transfers"""
        time.sleep(0.5)
        url = f'{self.BLOCKSCOUT_BASE_URL}/tokens/{contract_address}/transfers'
        data = self._request(url)
        if not data or not isinstance(data, dict):
            return None

        items = data.get('items', [])
        transfers = []
        for tx in items[:50]:
            if isinstance(tx, dict):
                total = tx.get('total', {})
                transfers.append({
                    'from': tx.get('from', {}).get('hash') if isinstance(tx.get('from'), dict) else tx.get('from'),
                    'to': tx.get('to', {}).get('hash') if isinstance(tx.get('to'), dict) else tx.get('to'),
                    'value': total.get('value') if isinstance(total, dict) else tx.get('value'),
                    'tokenDecimal': total.get('decimals') if isinstance(total, dict) else None,
                    'hash': tx.get('tx_hash'),
                    'blockNumber': tx.get('block_number'),
                    'timeStamp': None,
                    'timestamp': tx.get('timestamp'),
                })
        return {
            'transfers': transfers,
            'total_count': len(transfers),
            'min_value_filter_usd': min_value_usd,
            'last_updated': datetime.utcnow().isoformat(),
            'source': 'Blockscout (fallback)',
        }

    def estimate_exchange_flow(
        self,
        transfers: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Classify transfers as exchange inflow/outflow and calculate net flow.

        Args:
            transfers: List of transfer dicts from fetch_large_transfers

        Returns:
            Dict with keys:
            - exchange_inflow (sum of transfers to exchange addresses)
            - exchange_outflow (sum of transfers from exchange addresses)
            - net_flow (outflow - inflow, negative = more to exchanges)
            - top_transfers (list of largest transfers)
            - last_updated
            - source
            Or None on failure
        """
        try:
            if not transfers:
                return {
                    'exchange_inflow': 0,
                    'exchange_outflow': 0,
                    'net_flow': 0,
                    'top_transfers': [],
                    'last_updated': datetime.utcnow().isoformat(),
                    'source': 'Whale Tracker',
                }

            exchange_addresses_lower = {
                addr.lower(): name
                for name, addr in self.EXCHANGE_ADDRESSES.items()
            }

            exchange_inflow = 0
            exchange_outflow = 0
            top_transfers = []

            for tx in transfers:
                try:
                    value = int(tx.get('value', 0))
                    from_addr = tx.get('from', '').lower()
                    to_addr = tx.get('to', '').lower()

                    # Track if from or to known exchange
                    if from_addr in exchange_addresses_lower:
                        exchange_outflow += value
                    if to_addr in exchange_addresses_lower:
                        exchange_inflow += value

                    # Track top transfers
                    top_transfers.append({
                        'value': value,
                        'from': tx.get('from'),
                        'to': tx.get('to'),
                        'from_exchange': exchange_addresses_lower.get(from_addr),
                        'to_exchange': exchange_addresses_lower.get(to_addr),
                        'timestamp': tx.get('timestamp'),
                    })

                except (ValueError, TypeError):
                    continue

            # Sort by value and keep top 10
            top_transfers.sort(key=lambda x: x['value'], reverse=True)
            top_transfers = top_transfers[:10]

            net_flow = exchange_outflow - exchange_inflow

            result = {
                'exchange_inflow': exchange_inflow,
                'exchange_outflow': exchange_outflow,
                'net_flow': net_flow,
                'flow_ratio': (
                    exchange_outflow / exchange_inflow
                    if exchange_inflow > 0 else 0
                ),
                'top_transfers': top_transfers,
                'last_updated': datetime.utcnow().isoformat(),
                'source': 'Whale Tracker',
            }

            return result

        except Exception:
            return None


if __name__ == '__main__':
    print("Testing CollectorWhale with Uniswap (UNI)...")
    collector = CollectorWhale()

    # UNI contract address
    uni_contract = '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984'

    # Test large transfers
    print("\n1. Fetching large transfers...")
    transfers = collector.fetch_large_transfers(uni_contract, min_value_usd=100000)
    if transfers:
        print(f"   Total transfers found: {transfers.get('total_count')}")
        if transfers.get('transfers'):
            print(f"   Sample transfer:")
            sample = transfers['transfers'][0]
            print(f"     From: {sample.get('from')}")
            print(f"     To: {sample.get('to')}")
            print(f"     Value: {sample.get('value')}")
            print(f"     Time: {sample.get('timestamp')}")
    else:
        print("   Failed to fetch transfers")

    # Test exchange flow estimation
    if transfers and transfers.get('transfers'):
        print("\n2. Analyzing exchange flows...")
        flow = collector.estimate_exchange_flow(transfers.get('transfers', []))
        if flow:
            print(f"   Exchange inflow: {flow.get('exchange_inflow')}")
            print(f"   Exchange outflow: {flow.get('exchange_outflow')}")
            print(f"   Net flow: {flow.get('net_flow')}")
            print(f"   Flow ratio: {flow.get('flow_ratio'):.2f}")
            if flow.get('top_transfers'):
                print(f"   Top transfer value: {flow['top_transfers'][0].get('value')}")
        else:
            print("   Failed to analyze flows")

    print("\nCollectorWhale test complete!")
