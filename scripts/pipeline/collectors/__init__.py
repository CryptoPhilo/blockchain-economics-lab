"""
BCE Lab Data Collectors
Stage 0 - Data Collection Layer

This package contains specialized collectors for:
- Exchange data (CoinGecko)
- On-chain data (Etherscan, DeFiLlama)
- Macro market data (Fear & Greed, global data)
- Whale tracking (large transfers)
- Fundamental data (GitHub, project links)
- Token list (Universal Coverage Phase A)
- Transparency scan (Universal Coverage Phase C)
"""

from .base_collector import BaseCollector
from .collector_exchange import CollectorExchange
from .collector_onchain import CollectorOnchain
from .collector_macro import CollectorMacro
from .collector_whale import CollectorWhale
from .collector_fundamentals import CollectorFundamentals
from .collector_tokenlist import CollectorTokenList
from .collector_transparency import CollectorTransparency
from .collector_transparency_enhanced import EnhancedTransparencyScanner
from .warehouse import Warehouse, get_warehouse
from .collect_all import collect_all_data

__all__ = [
    'BaseCollector',
    'CollectorExchange',
    'CollectorOnchain',
    'CollectorMacro',
    'CollectorWhale',
    'CollectorFundamentals',
    'CollectorTokenList',
    'CollectorTransparency',
    'EnhancedTransparencyScanner',
    'Warehouse',
    'get_warehouse',
    'collect_all_data',
]

__version__ = '0.3.0'
