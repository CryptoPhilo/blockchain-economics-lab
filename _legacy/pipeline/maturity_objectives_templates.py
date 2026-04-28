"""
Project-Category-Specific Maturity Objective Templates

Instead of using 5 universal objectives for every project, this module provides
category-specific objective frameworks derived from what matters most for each
type of blockchain project.

CoinGecko categories are mapped to template keys, and each template defines:
  - Strategic objectives with tailored weights
  - KPIs relevant to that project type
  - On-Chain/Off-Chain ratio expectations
  - Achievement calculation hints

Usage:
    from maturity_objectives_templates import get_objectives_for_project
    objectives = get_objectives_for_project(coingecko_categories, fallback='general')
"""

from typing import Dict, List, Any, Optional

# ─────────────────────────────────────────────────────────────────────
# Category-to-template mapping
# ─────────────────────────────────────────────────────────────────────

# Maps CoinGecko category slugs → template key
CATEGORY_MAP: Dict[str, str] = {
    # Layer 1 / Layer 2
    'layer-1':                  'infrastructure',
    'layer-2':                  'infrastructure',
    'ethereum-ecosystem':       'infrastructure',
    'solana-ecosystem':         'infrastructure',
    'polygon-ecosystem':        'infrastructure',
    'avalanche-ecosystem':      'infrastructure',
    'cosmos-ecosystem':         'infrastructure',
    'arbitrum-ecosystem':       'infrastructure',
    'optimism-ecosystem':       'infrastructure',
    'zksync-ecosystem':         'infrastructure',
    'base-ecosystem':           'infrastructure',

    # DeFi
    'decentralized-finance-defi': 'defi',
    'decentralized-exchange':     'defi',
    'lending-borrowing':          'defi',
    'yield-farming':              'defi',
    'yield-aggregator':           'defi',
    'liquid-staking':             'defi',
    'derivatives':                'defi',
    'insurance':                  'defi',
    'stablecoins':                'defi',
    'automated-market-maker-amm': 'defi',
    'liquid-staking-derivatives': 'defi',
    'restaking':                  'defi',
    'real-world-assets-rwa':      'defi',

    # Gaming / Metaverse
    'gaming':                     'gaming',
    'play-to-earn':               'gaming',
    'metaverse':                  'gaming',
    'move-to-earn':               'gaming',
    'virtual-reality':            'gaming',
    'non-fungible-tokens-nft':    'nft',

    # AI / Data
    'artificial-intelligence':    'ai_blockchain',
    'big-data':                   'ai_blockchain',
    'machine-learning':           'ai_blockchain',
    'oracle':                     'ai_blockchain',
    'decentralized-science-desci':'ai_blockchain',

    # Social / Community
    'social-money':               'social',
    'fan-token':                  'social',
    'socialfi':                   'social',
    'decentralized-social-media': 'social',

    # Infrastructure / Middleware
    'interoperability':           'middleware',
    'cross-chain':                'middleware',
    'bridge':                     'middleware',
    'storage':                    'middleware',
    'privacy-coins':              'middleware',
    'zero-knowledge-zk':          'middleware',
    'data-availability':          'middleware',

    # Governance / DAO
    'governance':                 'dao',
    'decentralized-autonomous-organization': 'dao',

    # Meme / Speculative
    'meme-token':                 'meme',
    'dog-themed-coins':           'meme',
    'cat-themed-coins':           'meme',
    'political-memes':            'meme',
}


# ─────────────────────────────────────────────────────────────────────
# Objective Templates by category
# ─────────────────────────────────────────────────────────────────────

OBJECTIVE_TEMPLATES: Dict[str, Dict[str, Any]] = {

    # ── Infrastructure (L1/L2) ──────────────────────────────────────
    'infrastructure': {
        'description': 'Layer 1/2 블록체인 인프라 프로젝트',
        'onchain_offchain_default': {'onchain_ratio': 80, 'offchain_ratio': 20},
        'objectives': [
            {
                'name': 'Network Performance & Scalability',
                'weight': 30,
                'description': 'TPS, block time, gas costs, finality guarantees',
                'kpis': ['tps', 'block_time', 'gas_cost_avg', 'finality_seconds'],
                'onchain_offchain': '80:20',
                'achievement_sources': ['l2beat_data', 'chain_stats', 'block_explorer'],
            },
            {
                'name': 'Ecosystem & Developer Adoption',
                'weight': 25,
                'description': 'Active dApps, developer count, smart contract deployments',
                'kpis': ['active_dapps', 'unique_deployers_30d', 'github_contributors', 'tvl'],
                'onchain_offchain': '50:50',
                'achievement_sources': ['dappradar', 'defillama', 'github_api'],
            },
            {
                'name': 'Decentralization & Security',
                'weight': 20,
                'description': 'Validator count, Nakamoto coefficient, audit status, uptime',
                'kpis': ['validator_count', 'nakamoto_coefficient', 'audit_count', 'uptime_pct'],
                'onchain_offchain': '90:10',
                'achievement_sources': ['chain_stats', 'audit_reports'],
            },
            {
                'name': 'Tokenomics & Economic Sustainability',
                'weight': 15,
                'description': 'Fee revenue, inflation rate, staking participation, treasury health',
                'kpis': ['protocol_revenue_30d', 'inflation_rate', 'staking_ratio', 'treasury_usd'],
                'onchain_offchain': '70:30',
                'achievement_sources': ['defillama_fees', 'token_terminal', 'chain_stats'],
            },
            {
                'name': 'Community & Governance Maturity',
                'weight': 10,
                'description': 'Community size, governance participation, social engagement',
                'kpis': ['community_score', 'governance_proposals', 'voter_participation',
                         'social_engagement_rate'],
                'onchain_offchain': '40:60',
                'achievement_sources': ['coingecko_community', 'snapshot_governance', 'social_apis'],
            },
        ],
    },

    # ── DeFi ────────────────────────────────────────────────────────
    'defi': {
        'description': 'DeFi 프로토콜 (DEX, Lending, Yield, Derivatives)',
        'onchain_offchain_default': {'onchain_ratio': 85, 'offchain_ratio': 15},
        'objectives': [
            {
                'name': 'Protocol Security & Smart Contract Quality',
                'weight': 30,
                'description': 'Audit coverage, bug bounty, incident history, code quality',
                'kpis': ['audit_count', 'bug_bounty_usd', 'exploit_history', 'code_coverage'],
                'onchain_offchain': '95:5',
                'achievement_sources': ['audit_reports', 'github_api', 'rekt_database'],
            },
            {
                'name': 'Liquidity & TVL Growth',
                'weight': 25,
                'description': 'Total value locked, liquidity depth, capital efficiency',
                'kpis': ['tvl_usd', 'tvl_growth_30d', 'capital_efficiency', 'unique_depositors'],
                'onchain_offchain': '90:10',
                'achievement_sources': ['defillama', 'chain_data'],
            },
            {
                'name': 'Protocol Revenue & Sustainability',
                'weight': 20,
                'description': 'Fee generation, revenue retention, treasury management',
                'kpis': ['protocol_fees_30d', 'protocol_revenue_30d', 'treasury_usd', 'runway_months'],
                'onchain_offchain': '80:20',
                'achievement_sources': ['defillama_fees', 'token_terminal'],
            },
            {
                'name': 'User Adoption & Market Position',
                'weight': 15,
                'description': 'Unique users, transaction count, market share within category',
                'kpis': ['unique_users_30d', 'tx_count_30d', 'market_share_pct', 'holder_count'],
                'onchain_offchain': '70:30',
                'achievement_sources': ['chain_data', 'dappradar', 'coingecko'],
            },
            {
                'name': 'Community & Governance',
                'weight': 10,
                'description': 'DAO governance health, community engagement, developer ecosystem',
                'kpis': ['community_score', 'governance_proposals', 'voter_participation',
                         'discord_active_members'],
                'onchain_offchain': '50:50',
                'achievement_sources': ['coingecko_community', 'snapshot_governance'],
            },
        ],
    },

    # ── Gaming / Metaverse ──────────────────────────────────────────
    'gaming': {
        'description': '블록체인 게임/메타버스 프로젝트',
        'onchain_offchain_default': {'onchain_ratio': 40, 'offchain_ratio': 60},
        'objectives': [
            {
                'name': 'Infrastructure & Scalability',
                'weight': 25,
                'description': 'TPS, gas sponsorship, EVM compatibility, network stability',
                'kpis': ['tps', 'gas_sponsorship', 'block_time', 'uptime_pct'],
                'onchain_offchain': '70:30',
                'achievement_sources': ['chain_stats', 'l2beat_data'],
            },
            {
                'name': 'Ecosystem Content & Partnerships',
                'weight': 30,
                'description': 'Game count, AAA partnerships, genre diversity, live launches',
                'kpis': ['total_games', 'aaa_partners', 'live_games', 'genre_count'],
                'onchain_offchain': '30:70',
                'achievement_sources': ['dappradar', 'ecosystem_collector', 'web_scraping'],
            },
            {
                'name': 'User Experience & Onboarding',
                'weight': 20,
                'description': 'Wallet creation, MAU/DAU, fiat onramp, seamless UX',
                'kpis': ['registered_users', 'mau', 'dau', 'fiat_onramp_available'],
                'onchain_offchain': '50:50',
                'achievement_sources': ['dappradar', 'chain_data', 'web_scraping'],
            },
            {
                'name': 'Tokenomics & Sustainability',
                'weight': 15,
                'description': 'Protocol fees, staking, revenue vs incentive balance',
                'kpis': ['protocol_revenue_30d', 'staking_ratio', 'incentive_spend', 'runway_months'],
                'onchain_offchain': '60:40',
                'achievement_sources': ['defillama_fees', 'token_terminal'],
            },
            {
                'name': 'Community & Social Engagement',
                'weight': 10,
                'description': 'Community size, social sentiment, content creator activity',
                'kpis': ['community_score', 'social_engagement_rate', 'twitter_followers',
                         'telegram_members'],
                'onchain_offchain': '20:80',
                'achievement_sources': ['coingecko_community', 'social_apis'],
            },
        ],
    },

    # ── AI + Blockchain ─────────────────────────────────────────────
    'ai_blockchain': {
        'description': 'AI/데이터/오라클 블록체인 프로젝트',
        'onchain_offchain_default': {'onchain_ratio': 35, 'offchain_ratio': 65},
        'objectives': [
            {
                'name': 'AI/Core Technology Execution',
                'weight': 35,
                'description': 'Model accuracy, inference speed, novel mechanisms, production deployment',
                'kpis': ['model_deployed', 'api_uptime', 'benchmark_score', 'unique_integrations'],
                'onchain_offchain': '30:70',
                'achievement_sources': ['github_api', 'web_scraping', 'api_health_checks'],
            },
            {
                'name': 'On-Chain Integration & Verifiability',
                'weight': 20,
                'description': 'Smart contract quality, on-chain proof mechanisms, audit status',
                'kpis': ['audit_count', 'onchain_proofs', 'contract_verified', 'tx_count_30d'],
                'onchain_offchain': '80:20',
                'achievement_sources': ['chain_data', 'audit_reports'],
            },
            {
                'name': 'Ecosystem & Developer Adoption',
                'weight': 20,
                'description': 'Third-party integrations, developer tools, API usage',
                'kpis': ['api_consumers', 'github_contributors', 'sdk_downloads', 'active_dapps'],
                'onchain_offchain': '40:60',
                'achievement_sources': ['github_api', 'npm_stats', 'dappradar'],
            },
            {
                'name': 'Token Economics & Sustainability',
                'weight': 15,
                'description': 'Token utility demand, protocol revenue, deflationary mechanisms',
                'kpis': ['protocol_revenue_30d', 'token_velocity', 'burn_rate', 'staking_ratio'],
                'onchain_offchain': '60:40',
                'achievement_sources': ['defillama_fees', 'chain_data'],
            },
            {
                'name': 'Community & Market Penetration',
                'weight': 10,
                'description': 'User growth, community engagement, social sentiment',
                'kpis': ['community_score', 'holder_count', 'social_engagement_rate',
                         'twitter_followers'],
                'onchain_offchain': '30:70',
                'achievement_sources': ['coingecko_community', 'social_apis'],
            },
        ],
    },

    # ── NFT / Marketplace ───────────────────────────────────────────
    'nft': {
        'description': 'NFT 마켓플레이스/컬렉션 프로젝트',
        'onchain_offchain_default': {'onchain_ratio': 60, 'offchain_ratio': 40},
        'objectives': [
            {
                'name': 'Marketplace Volume & Liquidity',
                'weight': 30,
                'description': 'Trading volume, unique traders, floor price stability',
                'kpis': ['nft_volume_30d', 'unique_traders', 'floor_price_stability', 'listings_count'],
                'onchain_offchain': '80:20',
                'achievement_sources': ['chain_data', 'nft_aggregators'],
            },
            {
                'name': 'Creator & Collection Ecosystem',
                'weight': 25,
                'description': 'Active creators, collection diversity, royalty enforcement',
                'kpis': ['active_collections', 'creator_count', 'royalty_revenue', 'genre_diversity'],
                'onchain_offchain': '50:50',
                'achievement_sources': ['chain_data', 'web_scraping'],
            },
            {
                'name': 'Technology & User Experience',
                'weight': 20,
                'description': 'Gas efficiency, minting UX, cross-chain support',
                'kpis': ['gas_per_mint', 'supported_chains', 'fiat_onramp', 'mobile_support'],
                'onchain_offchain': '60:40',
                'achievement_sources': ['chain_data', 'web_scraping'],
            },
            {
                'name': 'Community & Brand',
                'weight': 15,
                'description': 'Community size, social engagement, brand partnerships',
                'kpis': ['community_score', 'twitter_followers', 'discord_members',
                         'brand_partnerships'],
                'onchain_offchain': '20:80',
                'achievement_sources': ['coingecko_community', 'social_apis'],
            },
            {
                'name': 'Tokenomics & Governance',
                'weight': 10,
                'description': 'Token utility, governance participation, fee structure',
                'kpis': ['protocol_revenue_30d', 'governance_proposals', 'staking_ratio'],
                'onchain_offchain': '70:30',
                'achievement_sources': ['defillama_fees', 'snapshot_governance'],
            },
        ],
    },

    # ── Social / SocialFi ──────────────────────────────────────────
    'social': {
        'description': 'SocialFi/팬토큰/탈중앙 소셜 프로젝트',
        'onchain_offchain_default': {'onchain_ratio': 30, 'offchain_ratio': 70},
        'objectives': [
            {
                'name': 'User Adoption & Engagement',
                'weight': 35,
                'description': 'MAU/DAU, retention rate, content creation rate',
                'kpis': ['mau', 'dau', 'retention_30d', 'posts_per_day'],
                'onchain_offchain': '30:70',
                'achievement_sources': ['dappradar', 'web_scraping'],
            },
            {
                'name': 'Community & Social Health',
                'weight': 25,
                'description': 'Community growth, social sentiment, cross-platform presence',
                'kpis': ['community_score', 'social_engagement_rate', 'twitter_followers',
                         'telegram_members', 'reddit_active_48h'],
                'onchain_offchain': '20:80',
                'achievement_sources': ['coingecko_community', 'social_apis'],
            },
            {
                'name': 'Platform Technology',
                'weight': 20,
                'description': 'Content storage, identity, moderation, scalability',
                'kpis': ['tps', 'storage_solution', 'identity_system', 'audit_count'],
                'onchain_offchain': '50:50',
                'achievement_sources': ['github_api', 'chain_data'],
            },
            {
                'name': 'Monetization & Creator Economy',
                'weight': 10,
                'description': 'Creator earnings, tipping volume, ad revenue',
                'kpis': ['creator_revenue_30d', 'tip_volume', 'premium_subscriptions'],
                'onchain_offchain': '40:60',
                'achievement_sources': ['chain_data', 'web_scraping'],
            },
            {
                'name': 'Token Economics',
                'weight': 10,
                'description': 'Token utility, governance, staking',
                'kpis': ['protocol_revenue_30d', 'staking_ratio', 'token_velocity'],
                'onchain_offchain': '60:40',
                'achievement_sources': ['defillama_fees', 'chain_data'],
            },
        ],
    },

    # ── Middleware / Cross-chain / Privacy ───────────────────────────
    'middleware': {
        'description': '인터옵/브릿지/스토리지/프라이버시 미들웨어',
        'onchain_offchain_default': {'onchain_ratio': 70, 'offchain_ratio': 30},
        'objectives': [
            {
                'name': 'Core Protocol Functionality',
                'weight': 30,
                'description': 'Bridge volume, message relay, storage capacity, privacy guarantees',
                'kpis': ['bridge_volume_30d', 'supported_chains', 'message_count', 'uptime_pct'],
                'onchain_offchain': '80:20',
                'achievement_sources': ['chain_data', 'defillama'],
            },
            {
                'name': 'Security & Trust',
                'weight': 25,
                'description': 'Audit status, exploit history, insurance coverage',
                'kpis': ['audit_count', 'exploit_history', 'insurance_coverage', 'tvl_at_risk'],
                'onchain_offchain': '90:10',
                'achievement_sources': ['audit_reports', 'rekt_database'],
            },
            {
                'name': 'Integration & Adoption',
                'weight': 20,
                'description': 'Protocol integrations, unique users, transaction volume',
                'kpis': ['integrations_count', 'unique_users_30d', 'tx_count_30d'],
                'onchain_offchain': '60:40',
                'achievement_sources': ['chain_data', 'dappradar'],
            },
            {
                'name': 'Token Economics & Revenue',
                'weight': 15,
                'description': 'Fee revenue, relay costs, economic sustainability',
                'kpis': ['protocol_revenue_30d', 'fee_per_tx', 'treasury_usd'],
                'onchain_offchain': '70:30',
                'achievement_sources': ['defillama_fees', 'chain_data'],
            },
            {
                'name': 'Community & Governance',
                'weight': 10,
                'description': 'Community engagement, governance activity',
                'kpis': ['community_score', 'governance_proposals', 'github_contributors'],
                'onchain_offchain': '50:50',
                'achievement_sources': ['coingecko_community', 'snapshot_governance', 'github_api'],
            },
        ],
    },

    # ── DAO / Governance ────────────────────────────────────────────
    'dao': {
        'description': 'DAO/거버넌스 프로젝트',
        'onchain_offchain_default': {'onchain_ratio': 75, 'offchain_ratio': 25},
        'objectives': [
            {
                'name': 'Governance Participation & Health',
                'weight': 35,
                'description': 'Proposal frequency, voter turnout, delegation',
                'kpis': ['governance_proposals', 'voter_participation', 'delegation_rate',
                         'unique_voters'],
                'onchain_offchain': '80:20',
                'achievement_sources': ['snapshot_governance', 'chain_data'],
            },
            {
                'name': 'Treasury Management',
                'weight': 25,
                'description': 'Treasury size, diversification, spend efficiency',
                'kpis': ['treasury_usd', 'treasury_diversification', 'runway_months', 'grant_count'],
                'onchain_offchain': '90:10',
                'achievement_sources': ['chain_data', 'defillama'],
            },
            {
                'name': 'Community & Contributor Ecosystem',
                'weight': 20,
                'description': 'Active contributors, community size, social engagement',
                'kpis': ['community_score', 'active_contributors', 'discord_active_members',
                         'social_engagement_rate'],
                'onchain_offchain': '30:70',
                'achievement_sources': ['coingecko_community', 'social_apis', 'github_api'],
            },
            {
                'name': 'Protocol Performance',
                'weight': 10,
                'description': 'Underlying protocol metrics, revenue, TVL',
                'kpis': ['protocol_revenue_30d', 'tvl_usd', 'tx_count_30d'],
                'onchain_offchain': '80:20',
                'achievement_sources': ['defillama', 'chain_data'],
            },
            {
                'name': 'Token Distribution & Decentralization',
                'weight': 10,
                'description': 'Token holder distribution, whale concentration',
                'kpis': ['holder_count', 'gini_coefficient', 'top10_concentration'],
                'onchain_offchain': '95:5',
                'achievement_sources': ['chain_data', 'coingecko'],
            },
        ],
    },

    # ── Meme / Speculative ──────────────────────────────────────────
    'meme': {
        'description': '밈/투기성 토큰',
        'onchain_offchain_default': {'onchain_ratio': 50, 'offchain_ratio': 50},
        'objectives': [
            {
                'name': 'Community & Viral Growth',
                'weight': 35,
                'description': 'Community size, social engagement, viral momentum',
                'kpis': ['community_score', 'twitter_followers', 'social_engagement_rate',
                         'reddit_active_48h', 'telegram_members'],
                'onchain_offchain': '10:90',
                'achievement_sources': ['coingecko_community', 'social_apis'],
            },
            {
                'name': 'Market Liquidity & Trading Activity',
                'weight': 25,
                'description': 'Volume, exchange listings, liquidity depth',
                'kpis': ['daily_volume_usd', 'exchange_count', 'liquidity_depth', 'holder_count'],
                'onchain_offchain': '70:30',
                'achievement_sources': ['coingecko', 'chain_data'],
            },
            {
                'name': 'Token Distribution Health',
                'weight': 20,
                'description': 'Holder distribution, whale concentration, burn mechanics',
                'kpis': ['holder_count', 'top10_concentration', 'burned_supply_pct'],
                'onchain_offchain': '90:10',
                'achievement_sources': ['chain_data', 'coingecko'],
            },
            {
                'name': 'Ecosystem Utility Development',
                'weight': 10,
                'description': 'Any utility beyond speculation (DeFi integrations, payments, NFTs)',
                'kpis': ['dapp_integrations', 'payment_adoption', 'nft_collections'],
                'onchain_offchain': '60:40',
                'achievement_sources': ['chain_data', 'dappradar'],
            },
            {
                'name': 'Security & Transparency',
                'weight': 10,
                'description': 'Contract verification, renounced ownership, audit status',
                'kpis': ['contract_verified', 'ownership_renounced', 'audit_count',
                         'transparency_score'],
                'onchain_offchain': '90:10',
                'achievement_sources': ['chain_data', 'audit_reports'],
            },
        ],
    },

    # ── General / Fallback ──────────────────────────────────────────
    'general': {
        'description': '범용 블록체인 프로젝트 (카테고리 미분류)',
        'onchain_offchain_default': {'onchain_ratio': 50, 'offchain_ratio': 50},
        'objectives': [
            {
                'name': 'Technical Development & Execution',
                'weight': 25,
                'description': 'Code quality, deployment status, security audits',
                'kpis': ['github_commits_30d', 'audit_count', 'contract_verified', 'uptime_pct'],
                'onchain_offchain': '60:40',
                'achievement_sources': ['github_api', 'audit_reports', 'chain_data'],
            },
            {
                'name': 'Market Adoption & User Growth',
                'weight': 25,
                'description': 'Holder count, transaction volume, unique users',
                'kpis': ['holder_count', 'tx_count_30d', 'unique_users_30d', 'daily_volume_usd'],
                'onchain_offchain': '70:30',
                'achievement_sources': ['coingecko', 'chain_data'],
            },
            {
                'name': 'Ecosystem & Partnerships',
                'weight': 20,
                'description': 'Integrations, partnerships, developer ecosystem',
                'kpis': ['integrations_count', 'partnerships_count', 'github_contributors'],
                'onchain_offchain': '40:60',
                'achievement_sources': ['web_scraping', 'github_api'],
            },
            {
                'name': 'Community & Social Health',
                'weight': 15,
                'description': 'Community size, engagement rate, multi-platform presence',
                'kpis': ['community_score', 'social_engagement_rate', 'twitter_followers',
                         'telegram_members', 'reddit_active_48h'],
                'onchain_offchain': '20:80',
                'achievement_sources': ['coingecko_community', 'social_apis'],
            },
            {
                'name': 'Token Economics & Sustainability',
                'weight': 15,
                'description': 'Protocol revenue, token utility, supply management',
                'kpis': ['protocol_revenue_30d', 'staking_ratio', 'inflation_rate', 'treasury_usd'],
                'onchain_offchain': '70:30',
                'achievement_sources': ['defillama_fees', 'chain_data'],
            },
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────
# Community Maturity Scoring Framework
# ─────────────────────────────────────────────────────────────────────

COMMUNITY_SCORING = {
    'metrics': {
        # Metric name → {weight, thresholds for scoring 0-100}
        'twitter_followers': {
            'weight': 15,
            'tiers': [
                (1_000_000, 100), (500_000, 90), (100_000, 75),
                (50_000, 60), (10_000, 40), (5_000, 25), (1_000, 10), (0, 0),
            ],
        },
        'reddit_subscribers': {
            'weight': 10,
            'tiers': [
                (500_000, 100), (100_000, 85), (50_000, 70),
                (10_000, 50), (5_000, 30), (1_000, 15), (0, 0),
            ],
        },
        'reddit_active_48h': {
            'weight': 15,
            'tiers': [
                (10_000, 100), (5_000, 85), (1_000, 70),
                (500, 55), (100, 35), (50, 20), (0, 0),
            ],
        },
        'telegram_members': {
            'weight': 10,
            'tiers': [
                (500_000, 100), (100_000, 85), (50_000, 70),
                (10_000, 50), (5_000, 30), (1_000, 15), (0, 0),
            ],
        },
        'github_contributors': {
            'weight': 15,
            'tiers': [
                (500, 100), (200, 90), (100, 75),
                (50, 60), (20, 40), (10, 25), (5, 10), (0, 0),
            ],
        },
        'github_commits_30d': {
            'weight': 15,
            'tiers': [
                (500, 100), (200, 85), (100, 70),
                (50, 55), (20, 35), (10, 20), (0, 0),
            ],
        },
        'social_engagement_rate': {
            'weight': 10,
            'tiers': [
                (5.0, 100), (3.0, 85), (1.5, 70),
                (0.5, 50), (0.2, 30), (0.05, 15), (0, 0),
            ],
        },
        'multi_platform_presence': {
            'weight': 10,
            'tiers': [
                (6, 100), (5, 85), (4, 70),
                (3, 50), (2, 30), (1, 15), (0, 0),
            ],
        },
    },
    'maturity_labels': {
        (80, 100): 'Thriving Community',
        (60, 79):  'Healthy Community',
        (40, 59):  'Developing Community',
        (20, 39):  'Early Community',
        (0, 19):   'Minimal Community',
    },
}


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def resolve_template_key(categories: List[str]) -> str:
    """
    Resolve CoinGecko category list to the best-matching template key.
    Uses priority scoring when multiple categories match different templates.
    """
    if not categories:
        return 'general'

    # Count matches per template key
    scores: Dict[str, int] = {}
    for cat in categories:
        cat_lower = cat.lower().replace(' ', '-')
        key = CATEGORY_MAP.get(cat_lower)
        if key:
            scores[key] = scores.get(key, 0) + 1

    if not scores:
        return 'general'

    # Return template with most category matches
    return max(scores, key=scores.get)


def get_objectives_for_project(
    categories: List[str] = None,
    template_key: str = None,
) -> Dict[str, Any]:
    """
    Get the appropriate objective template for a project.

    Args:
        categories: CoinGecko category list
        template_key: Override with specific template key

    Returns:
        Template dict with 'objectives', 'description', 'onchain_offchain_default'
    """
    if template_key and template_key in OBJECTIVE_TEMPLATES:
        key = template_key
    elif categories:
        key = resolve_template_key(categories)
    else:
        key = 'general'

    template = OBJECTIVE_TEMPLATES[key].copy()
    template['template_key'] = key
    return template


def compute_community_score(community_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute community maturity score from available metrics.

    Args:
        community_data: Dict with keys matching COMMUNITY_SCORING metrics

    Returns:
        Dict with overall_score (0-100), label, breakdown per metric
    """
    scoring = COMMUNITY_SCORING['metrics']
    breakdown = {}
    total_weighted = 0.0
    total_weight = 0.0

    for metric_name, config in scoring.items():
        raw_value = community_data.get(metric_name)
        if raw_value is None:
            continue

        try:
            val = float(raw_value)
        except (ValueError, TypeError):
            continue

        # Score from tiers
        score = 0
        for threshold, tier_score in config['tiers']:
            if val >= threshold:
                score = tier_score
                break

        weight = config['weight']
        total_weighted += score * weight
        total_weight += weight

        breakdown[metric_name] = {
            'raw_value': val,
            'score': score,
            'weight': weight,
        }

    overall = round(total_weighted / total_weight, 1) if total_weight > 0 else 0

    # Determine label
    label = 'Minimal Community'
    for (low, high), lbl in COMMUNITY_SCORING['maturity_labels'].items():
        if low <= overall <= high:
            label = lbl
            break

    return {
        'overall_score': overall,
        'label': label,
        'label_ko': _label_ko(label),
        'breakdown': breakdown,
        'metrics_available': len(breakdown),
        'metrics_total': len(scoring),
    }


def _label_ko(label: str) -> str:
    """Korean translation of community maturity label."""
    mapping = {
        'Thriving Community': '번성 커뮤니티',
        'Healthy Community': '건강한 커뮤니티',
        'Developing Community': '성장 중 커뮤니티',
        'Early Community': '초기 커뮤니티',
        'Minimal Community': '최소 커뮤니티',
    }
    return mapping.get(label, label)
