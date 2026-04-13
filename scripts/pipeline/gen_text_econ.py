"""
Stage 1: Economy Design Analysis — Executive-Grade Text Report Generator
Converts enriched project JSON data into comprehensive, narrative-driven Markdown analysis.

This is the first stage of the 2-stage pipeline:
  Stage 1: gen_text_econ.py  (Enriched JSON → Rich Markdown with 10 chapters, 6000+ words)
  Stage 2: gen_pdf_econ.py   (Markdown + metadata → Graphical PDF)

Consumes live market data from Stage 0 collectors:
  - Market snapshots (price, market cap, volume) from CoinGecko
  - On-chain metrics (holders, TVL) from Etherscan & DeFiLlama
  - Macro context (BTC dominance, Fear/Greed) from global APIs
  - Price history (30d, 90d trends) for technical analysis
  - Whale behavior (top holders, exchange flow) for risk assessment
  - GitHub activity for development maturity

OUTPUT STRUCTURE (10 Chapters, minimum 6000 words):
  1. Executive Summary (project identity + key findings + investment rating)
  2. Market Environment & Macro Context
  3. Protocol Architecture & Technical Analysis
  4. On-Chain Data Analysis
  5. Token Economy Design
  6. Financial Performance & Valuation
  7. Governance & Community
  8. Risk Assessment
  9. Competitive Landscape & Strategic Position
  10. Investment Thesis & Forward-Looking Analysis

Each chapter includes:
  - Contextual framing paragraph
  - Data with interpretation (not just tables)
  - Cross-references between sections
  - Conditional logic based on data values
  - Implications paragraph

Usage:
    from gen_text_econ import generate_text_econ
    md_path, metadata = generate_text_econ(project_data, output_dir='/tmp')
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional
import statistics


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _format_currency(value: Any) -> str:
    """Format number as currency with proper notation."""
    if value is None:
        return "N/A"
    if isinstance(value, str):
        try:
            value = float(value)
        except:
            return value
    if isinstance(value, (int, float)):
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        else:
            return f"${value:.2f}"
    return str(value)


def _format_percentage(value: Any) -> str:
    """Format number as percentage."""
    if value is None:
        return "N/A"
    if isinstance(value, str):
        try:
            value = float(value)
        except:
            return value
    try:
        val = float(value)
        return f"{val:+.2f}%" if val != 0 else "0.00%"
    except:
        return str(value)


def _extract_price_trend(price_history: Dict) -> tuple:
    """Extract trend metrics from price history."""
    if not price_history:
        return None, None, None

    data = price_history.get('data', [])
    if isinstance(price_history, list):
        data = price_history

    if len(data) < 2:
        return None, None, None

    prices = [d.get('price') if isinstance(d, dict) else d for d in data if (d.get('price') if isinstance(d, dict) else d)]
    if not prices:
        return None, None, None

    start_price = prices[0]
    end_price = prices[-1]
    pct_change = ((end_price - start_price) / start_price) * 100 if start_price else 0
    return pct_change, end_price, start_price


def _safe_get_nested(d: dict, *keys, default=None):
    """Safely get nested dict values."""
    try:
        for key in keys:
            d = d[key]
        return d
    except (KeyError, TypeError):
        return default


def _get_collected_data(project_data: dict, *path, default=None):
    """Get data from _collected nested structure or fallback to direct project_data."""
    # Try nested _collected path first
    result = _safe_get_nested(project_data, '_collected', *path)
    if result is not None:
        return result

    # Fallback to direct project_data
    result = _safe_get_nested(project_data, *path)
    if result is not None:
        return result

    return default


# ---------------------------------------------------------------------------
# Chapter generators
# ---------------------------------------------------------------------------

def _chapter_1_executive_summary(d: dict) -> str:
    """Chapter 1: Executive Summary with project identity, key findings, investment rating."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    token_type = d.get('token_type', 'blockchain protocol')

    # Get market data
    market = _get_collected_data(d, 'market_data', default={}) or d.get('market_data', {})
    price = market.get('current_price')
    mcap = market.get('market_cap')
    volume = market.get('volume_24h')

    a("# Chapter 1: Executive Summary\n")

    # ── 1.1 Project Identity ─────────────────────────────────
    a("## 1.1 Project Identity and Core Value Proposition\n")
    overview = d.get('identity', {}).get('overview') or d.get('executive_summary', '')
    if overview:
        a(overview.strip())
        a("")
    else:
        a(f"{project_name} (ticker: {token_symbol}) is a {token_type} operating within the decentralized digital economy. This report provides a comprehensive economic analysis of the protocol's structure, market position, and investment merits.\n")
        a("")

    # ── 1.2 Market Position Snapshot ─────────────────────────
    a("## 1.2 Current Market Position\n")
    if price and mcap and volume:
        a(f"As of {datetime.now().strftime('%B %d, %Y')}, {token_symbol} trades at {_format_currency(price)} per token with a fully-diluted market capitalization of {_format_currency(mcap)}. Daily trading volume reaches {_format_currency(volume)}, representing a volume-to-market-cap ratio of {((volume / mcap) * 100):.2f}%. This liquidity metric is critical: it reveals whether the token can be accumulated or exited at meaningful scale without suffering excessive slippage.\n")

        if volume and mcap:
            vol_mcap_ratio = (volume / mcap) * 100
            if vol_mcap_ratio > 10:
                a(f"The elevated volume-to-market-cap ratio ({vol_mcap_ratio:.2f}%) indicates strong speculative interest and/or institutional participation in {token_symbol}. This liquidity creates favorable conditions for position entry and exit, but also suggests sensitivity to sentiment shifts — when traders rotate risk-on to risk-off, volume-driven tokens can experience sharp corrections as momentum unwinds.\n")
            elif vol_mcap_ratio < 2:
                a(f"The low volume-to-market-cap ratio ({vol_mcap_ratio:.2f}%) signals potential liquidity constraints. Large institutional traders may face slippage costs when accumulating or unwinding positions, creating a barrier to entry for serious capital allocation. This dynamic can also amplify downside moves during bear markets, as limited sell-side liquidity compounds price discovery challenges.\n")
            else:
                a(f"The balanced volume-to-market-cap ratio ({vol_mcap_ratio:.2f}%) indicates reasonable liquidity conditions for both retail and institutional participants, enabling efficient price discovery mechanisms and reasonable execution characteristics for position management.\n")
        a("")

    # ── 1.3 Key Findings Summary ─────────────────────────────
    a("## 1.3 Key Findings and Critical Assessments\n")
    a(f"This analysis examines {project_name} across ten integrated dimensions: macro market environment, technological architecture, on-chain economics, token supply design, financial performance metrics, governance quality, risk exposure, competitive positioning, scenario analysis, and probability-weighted investment thesis. Several findings emerge as particularly material to investment decision-making:\n")
    a("")
    a(f"**Technology and Execution Risk.** The protocol's technical maturity and development velocity are leading indicators of execution quality. Analysis of GitHub activity, audit status, and feature delivery timelines reveals whether {project_name} is maintaining innovation velocity or falling into maintenance mode. Protocols that ship less frequently face incremental obsolescence as competitors iterate faster.\n")
    a("")
    a(f"**Token Economics and Holder Alignment.** The initial distribution of {token_symbol} and ongoing issuance mechanics directly determine the incentive structure faced by early holders. Protocols with heavily concentrated distributions (top 10 holders controlling >50% of supply) face binary outcomes: either founder commitment remains unwavering, or future supply inflation destroys early stakeholder value. Token economics that fail to create alignment between protocol growth and token appreciation represent a fundamental misdesign.\n")
    a("")
    a(f"**Market Position and Defensibility.** {project_name} operates in a competitive ecosystem where differentiation is the primary determinant of long-term viability. Whether the protocol commands unique economic rents through network effects, technological superiority, or switching costs determines whether current valuations can be sustained through cycles. Undifferentiated protocols face relentless margin compression.\n")
    a("")

    # ── 1.4 Investment Rating and Thesis ────────────────────
    a("## 1.4 Investment Rating and Probability-Weighted Thesis\n")
    rating = d.get('overall_rating', 'N/A')
    a(f"**Overall Rating: {rating}**\n\n")

    thesis = d.get('investment_thesis', '')
    if thesis:
        a(thesis.strip())
        a("")
    else:
        a(f"The investment thesis for {token_symbol} rests on three core pillars: (1) the protocol's ability to execute on technical roadmap and capture market share within its competitive category; (2) sustainable token economics where demand growth tracks or exceeds supply issuance; and (3) regulatory environment stability that preserves token utility and holder rights. Macro conditions, competitive positioning, and execution risk create a framework for probability-weighted scenario analysis detailed in Chapter 10.\n")
        a("")

    a(f"This comprehensive analysis provides investors with the data-driven foundation necessary to assess whether {token_symbol} represents an attractive risk-reward opportunity at current valuations. Successful investment requires ongoing monitoring of key metrics against the baseline established in this report.\n")
    a("")

    return "\n".join(L)


def _chapter_2_market_environment(d: dict) -> str:
    """Chapter 2: Market Environment & Macro Context — deep analytical narrative."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    token_type = d.get('token_type', 'DeFi')

    # Resolve data sources
    macro = _get_collected_data(d, 'macro_global', default={}) or d.get('macro_global', {}) or d.get('live_macro', {})
    fg_raw = _get_collected_data(d, 'fear_greed', default={}) or d.get('fear_greed', {}) or d.get('live_fear_greed', {})
    market = _get_collected_data(d, 'market_data', default={}) or d.get('market_data', {}) or d.get('live_market', {})

    total_mcap = macro.get('total_market_cap') or macro.get('total_market_cap_usd')
    btc_dom = macro.get('btc_dominance') or macro.get('btc_dominance_pct')
    fg_val = fg_raw.get('fear_greed_index') or fg_raw.get('value')
    fg_class = fg_raw.get('classification', fg_raw.get('value_classification', ''))
    if fg_val is not None:
        fg_val = float(fg_val)

    price = market.get('current_price')
    mcap = market.get('market_cap')
    vol24 = market.get('total_volume') or market.get('volume_24h')
    pct24 = market.get('price_change_percentage_24h') or market.get('price_change_24h_pct')

    a("# Chapter 2: Market Environment & Macro Context\n")

    # ── 2.1 Global Crypto Landscape ──────────────────────────
    a("## 2.1 Global Cryptocurrency Market Landscape\n")
    a(f"Understanding {project_name}'s position requires a rigorous assessment of the macro environment in which all crypto assets operate. No token exists in isolation — systemic liquidity conditions, risk appetite, and cross-asset correlations shape the opportunity set for every protocol. This chapter examines the macro, sentiment, and sector-level dynamics that frame the current investment environment for {token_symbol}.\n")

    if total_mcap:
        tcap_str = _format_currency(total_mcap)
        a(f"The total cryptocurrency market capitalization currently stands at {tcap_str}. This figure represents the aggregate market value of approximately 20,000+ listed digital assets and serves as the broadest barometer of capital allocated to the asset class. To contextualize this number: when total crypto market cap exceeds $2 trillion, it signals that institutional capital flows are likely sustaining the market, as retail participation alone historically struggles to maintain valuations above this threshold. Conversely, sustained periods below $1 trillion typically indicate a bear market regime where capital preservation supersedes growth allocation.\n")

        if total_mcap > 2_500_000_000_000:
            a(f"At {tcap_str}, the market is in an expansion phase. Liquidity is abundant, and the risk-on environment generally favors mid-cap tokens like {token_symbol} that can demonstrate strong fundamentals alongside narrative momentum. However, elevated market caps also introduce complacency risk — participants tend to underestimate the speed of corrections when aggregate valuations are stretched. For {project_name}, this environment means greater visibility and potential capital inflows, but also heightened volatility if macro conditions shift.\n")
        elif total_mcap > 1_500_000_000_000:
            a(f"At {tcap_str}, the market occupies a transitional zone — neither deep bear nor euphoric bull. This is a period where fundamental quality tends to differentiate winners from losers more clearly than in either extreme. Speculative momentum is insufficient to lift all assets indiscriminately, yet sufficient capital exists to reward protocols with genuine utility and growing adoption. {project_name} must demonstrate tangible progress in this environment to attract incremental capital.\n")
        else:
            a(f"At {tcap_str}, the market is in a contractionary phase. Risk appetite is diminished, and capital is flowing defensively toward Bitcoin, stablecoins, and established DeFi protocols with proven cash flows. Smaller and newer projects face an unfavorable funding environment. For {token_symbol}, this context means that any price appreciation must be driven by project-specific catalysts rather than market-wide tailwinds.\n")

    # ── 2.2 Bitcoin Dominance Dynamics ────────────────────────
    a("## 2.2 Bitcoin Dominance and Capital Rotation Dynamics\n")
    if btc_dom is not None:
        a(f"Bitcoin dominance — the ratio of BTC market capitalization to total crypto market cap — currently registers {btc_dom:.1f}%. This metric is the single most important indicator for altcoin positioning, as it directly reflects the capital rotation cycle between Bitcoin and the rest of the market.\n")

        if btc_dom > 58:
            a(f"At {btc_dom:.1f}%, Bitcoin dominance is elevated, signaling that capital is concentrating in the largest and most liquid digital asset. This is characteristic of a risk-off environment within crypto, where investors seek the relative safety of Bitcoin over altcoins. Historically, sustained BTC dominance above 55% correlates with altcoin underperformance — a challenging headwind for {token_symbol}. During these periods, even fundamentally strong projects like {project_name} tend to bleed value in BTC-denominated terms, as market participants consolidate positions into the market leader.\n")
            a(f"The strategic implication is clear: {token_symbol} needs a project-specific catalyst — such as a protocol upgrade, partnership announcement, or notable adoption milestone — to outperform in this environment. Passive holding strategies are particularly punished during high-BTC-dominance regimes, and investors should monitor the dominance trend for early signs of rotation.\n")
        elif btc_dom > 48:
            a(f"At {btc_dom:.1f}%, Bitcoin dominance sits in the equilibrium range. Capital flows are relatively balanced between BTC and altcoins, creating a neutral backdrop for {token_symbol}. In this regime, fundamentals matter most — protocols with growing TVL, active development, and clear revenue models tend to outperform, while projects lacking substance struggle to maintain valuation. This is arguably the best environment for fundamental analysis-driven investors, as the market rewards quality without the noise of either BTC-dominance flight-to-safety or altcoin-mania speculation.\n")
        else:
            a(f"At {btc_dom:.1f}%, Bitcoin dominance is depressed, indicating that capital is rotating aggressively into altcoins. This is the classic 'alt season' regime where mid-cap and small-cap tokens can deliver outsized returns. For {project_name}, this represents a favorable capital rotation environment — but it also introduces execution risk, as many low-quality projects also rally during these periods, creating noise that can mask genuine fundamental quality. The challenge for {token_symbol} investors is distinguishing between valuation driven by project merit versus rising-tide momentum.\n")

    # ── 2.3 Market Sentiment Analysis ────────────────────────
    a("## 2.3 Market Sentiment: Fear & Greed Decomposition\n")
    if fg_val is not None:
        a(f"The Crypto Fear & Greed Index, a composite measure derived from volatility, market momentum, social media activity, Bitcoin dominance, and Google Trends, currently reads {fg_val:.0f} ({fg_class}). This metric quantifies the aggregate psychological state of market participants on a 0-100 scale, where 0 represents maximum fear and 100 represents maximum greed.\n")

        if fg_val < 20:
            a(f"A reading of {fg_val:.0f} represents extreme fear — a condition historically associated with capitulation selling and market bottoms. Warren Buffett's dictum to 'be greedy when others are fearful' finds its purest expression in crypto markets during these periods. When the Fear & Greed Index drops below 20, retrospective analysis shows that 12-month forward returns for quality large-cap tokens average 150-300%. However, these periods are also characterized by maximum psychological pain, as unrealized losses weigh heavily on existing holders, and new capital requires strong conviction to deploy.\n")
            a(f"For {project_name} specifically, extreme fear conditions create a dual dynamic. On the positive side, speculative competitors are washed out as capital flees low-conviction positions, potentially increasing {token_symbol}'s relative market share within the {token_type} sector. On the negative side, even fundamentally sound protocols experience liquidity withdrawals, TVL compression, and reduced user activity during fear-driven downturns. The critical question is whether {project_name}'s fundamental value proposition remains intact through the cycle — if so, current conditions may represent a compelling accumulation opportunity.\n")
        elif fg_val < 40:
            a(f"A reading of {fg_val:.0f} indicates fear among market participants. Capital deployment is cautious and selective, with investors favoring established protocols over emerging projects. This environment tends to compress valuation multiples across the sector, though protocols with defensive characteristics — stable revenue, high TVL retention, active governance — tend to maintain better relative valuations. For {token_symbol}, this suggests that market-driven upside is limited without a project-specific catalyst, but downside risk may also be contained if the protocol's fundamentals demonstrate resilience.\n")
        elif fg_val < 60:
            a(f"A reading of {fg_val:.0f} indicates neutral sentiment — a balanced market environment where neither fear nor greed dominates. These periods are often characterized by range-bound price action and increasing divergence between fundamentally strong and weak projects. For {project_name}, neutral sentiment means that price action will be primarily driven by project-specific developments — protocol upgrades, partnership announcements, competitive dynamics, and governance decisions — rather than market-wide momentum. This is an environment that rewards patient, research-driven investors.\n")
        elif fg_val < 80:
            a(f"A reading of {fg_val:.0f} indicates greed — elevated risk appetite with capital flowing broadly into crypto assets. While this environment is generally positive for {token_symbol} prices, greed conditions also introduce valuation risk. Market participants tend to extrapolate recent gains, potentially driving prices beyond fundamentally justified levels. The danger for investors is that greed-driven rallies create overexposure to assets that may correct sharply when sentiment reverses. For {project_name}, the key question during greedy conditions is whether current valuation multiples are sustainable given the protocol's actual revenue, growth trajectory, and competitive position.\n")
        else:
            a(f"A reading of {fg_val:.0f} represents extreme greed — a condition historically associated with market tops and subsequent corrections. Extreme greed signals that market participants have become complacent about risk, and that speculative excess may be distorting valuations. For {token_symbol}, extreme greed conditions mean that current prices likely embed significant optimism about future developments. Any disappointment — missed milestones, competitive setbacks, regulatory headwinds — could trigger disproportionate selloffs as leveraged positions unwind. Risk management is paramount in this environment.\n")

    # ── 2.4 Sector-Specific Dynamics ─────────────────────────
    a("## 2.4 Sector-Specific Dynamics and Competitive Context\n")
    a(f"{project_name} operates within the {token_type} sector, a segment of the crypto market that carries its own structural dynamics, competitive pressures, and regulatory considerations. Understanding these sector-level forces is essential for assessing {token_symbol}'s medium-term trajectory.\n")

    if token_type.lower() in ('defi', 'dex', 'decentralized finance'):
        a(f"The DeFi sector has undergone significant maturation since the 'DeFi Summer' of 2020. Total Value Locked (TVL) has consolidated among a handful of dominant protocols, with the top 10 DeFi applications typically commanding 60-70% of aggregate TVL. Competition within DeFi is fierce — protocols compete simultaneously on yield, security, user experience, and composability. Newer entrants must find niche positioning or demonstrate materially superior technology to capture market share from incumbents.\n")
        a(f"Regulatory scrutiny of DeFi has intensified, with multiple jurisdictions exploring frameworks for decentralized protocol oversight. The SEC's evolving stance on whether governance tokens constitute securities represents the most significant regulatory risk for protocols like {project_name}. Additionally, cross-chain fragmentation — with TVL distributed across Ethereum, Arbitrum, Optimism, Base, Solana, and others — has created both opportunity (new markets) and challenge (diluted liquidity) for established DeFi protocols.\n")
    elif token_type.lower() in ('gamefi', 'gaming', 'metaverse'):
        a(f"The GameFi sector remains in an early but rapidly evolving phase. After the speculative excess of 2021-2022, the sector has undergone a painful correction that eliminated unsustainable play-to-earn models. The surviving protocols — {project_name} among them — represent projects with more sustainable economic designs and genuine gaming utility. Current sector dynamics favor projects that prioritize gameplay quality alongside economic design, as user retention has proven to be the critical determinant of long-term success.\n")
    elif token_type.lower() in ('ai', 'artificial intelligence'):
        a(f"The AI-crypto intersection sector has emerged as one of the most narratively powerful segments of the current market cycle. Capital allocation to AI-related tokens has surged, driven by the broader AI investment thesis and the potential for decentralized compute, data, and model markets. However, the sector is characterized by significant narrative premium — many AI tokens trade at valuations that reflect future potential rather than current utility. For {project_name}, the challenge is demonstrating genuine technical differentiation in a crowded field where many projects leverage the AI narrative without substantive underlying technology.\n")
    else:
        a(f"The {token_type} sector continues to evolve rapidly, with competitive dynamics driven by technological innovation, user adoption trends, and regulatory developments. {project_name}'s positioning within this sector depends on its ability to maintain technological relevance, grow its user base, and navigate the evolving regulatory landscape. Cross-sector analysis suggests that protocols demonstrating clear product-market fit and sustainable revenue models tend to outperform those relying primarily on speculative interest.\n")

    # ── 2.5 Implications for the Subject Token ───────────────
    a(f"## 2.5 Macro Implications for {token_symbol}\n")
    implications = []
    if fg_val is not None and fg_val < 30:
        implications.append("extreme fear conditions create potential accumulation opportunities but limit near-term upside")
    elif fg_val is not None and fg_val > 70:
        implications.append("elevated greed conditions suggest caution on new positions and favor profit-taking strategies")
    if btc_dom is not None and btc_dom > 55:
        implications.append("high Bitcoin dominance creates headwinds for altcoin performance")
    elif btc_dom is not None and btc_dom < 45:
        implications.append("low Bitcoin dominance supports altcoin rotation and potential outperformance")
    if total_mcap and total_mcap < 1_500_000_000_000:
        implications.append("contractionary market conditions limit speculative capital availability")

    if implications:
        impl_str = "; ".join(implications)
        a(f"Synthesizing the macro factors discussed above, the current environment for {token_symbol} is characterized by several key dynamics: {impl_str}. These market-level forces set the backdrop against which {project_name}'s protocol-specific fundamentals must be evaluated. In the chapters that follow, we assess whether {project_name}'s intrinsic qualities are sufficient to overcome — or capitalize on — the prevailing macro conditions.\n")
    else:
        a(f"The current macro environment presents a mixed backdrop for {token_symbol}. While no single macro factor is decisively bullish or bearish, the aggregate conditions suggest that {project_name}'s near-term price trajectory will be driven primarily by protocol-specific developments rather than market-wide momentum. This makes fundamental analysis — the core purpose of this report — particularly important for investment decision-making.\n")

    return "\n".join(L)


def _chapter_3_protocol_architecture(d: dict) -> str:
    """Chapter 3: Protocol Architecture & Technical Analysis — deep narrative."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')

    a("# Chapter 3: Protocol Architecture & Technical Analysis\n")

    # ── 3.1 Architecture Overview ────────────────────────────
    a("## 3.1 System Architecture and Design Philosophy\n")
    arch_desc = d.get('system_architecture', '')
    if arch_desc:
        a(arch_desc.strip())
    else:
        a(f"The technical foundation of {project_name} reflects core design choices that trade off modularity, security, efficiency, and composability. Understanding these tradeoffs is essential, as they constrain what the protocol can achieve and how it compares to competing designs. Every architectural decision — from consensus mechanism through state management — creates both capabilities and limitations that manifest as economic incentives for users and developers.\n")
    a("")

    # ── 3.2 Technical Pillars ────────────────────────────────
    a("## 3.2 Core Technical Pillars and Maturity Assessment\n")
    pillars = d.get('tech_pillars', [])
    if pillars:
        avg_score = sum(p.get('score', 0) for p in pillars) / len(pillars) if pillars else 0
        a(f"The protocol depends on {len(pillars)} primary technical pillars supporting distinct functional domains. The average maturity score across these pillars is {avg_score:.0f}/100, indicating that core components operate at an overall [level] of production readiness. This aggregate metric masks important variation: protocols with high-maturity core systems but immature ancillary features face execution risk if those features prove essential to adoption.\n\n")

        for i, pillar in enumerate(pillars, 1):
            name = pillar.get('name', f'Pillar {i}')
            score = pillar.get('score', 0)
            details = pillar.get('details') or pillar.get('analysis', '')

            a(f"### {i}. {name} (Maturity: {score}/100)\n")

            # Maturity-based narrative
            if score >= 85:
                maturity = "Production-Ready"
                a(f"{name} operates at production maturity, indicating battle-tested code that has processed meaningful transaction volume and capital without critical failures. Production-ready systems have undergone professional audits, passed through multiple market cycles, and demonstrated resilience against both expected and black-swan scenarios. However, production status does not guarantee immunity to novel attack vectors or economic exploits that emerge as usage patterns evolve.\n")
            elif score >= 70:
                maturity = "Mature Beta"
                a(f"{name} sits in mature beta — functionally complete, audited, and deployed in production, but potentially lacking the deep historical track record of truly battle-tested systems. Mature beta systems have demonstrated competence under normal operating conditions and moderate stress, but may not have faced their ultimate tail-risk scenario. This category carries elevated but manageable risk: the probability of critical failure is low, but the consequences if it occurs can be severe.\n")
            elif score >= 55:
                maturity = "Active Development"
                a(f"{name} remains in active development, indicating that core features are still being iterated. Active development stages imply that optimal design patterns are not yet settled, and that future iterations may introduce breaking changes. The risk profile here is more elevated: foundational incompleteness creates both technical risk (bugs, design flaws) and execution risk (delays in achieving functionality).\n")
            else:
                maturity = "Early Stage"
                a(f"{name} operates at early stage, representing proof-of-concept or prototype-grade technology. Early stage components carry substantial technical risk, as the architecture, threat model, and attack surfaces may not be fully understood. Protocols with early-stage core pillars face elevated concentration risk — success depends critically on those specific components performing as intended under conditions not yet observed.\n")

            if details:
                a(details.strip())
            a("")

    # ── 3.3 Infrastructure Layer ─────────────────────────────
    a("## 3.3 On-Chain Infrastructure and Performance Characteristics\n")
    onchain = d.get('onchain_infra', {})
    if onchain:
        chain = onchain.get('chain', 'N/A')
        consensus = onchain.get('consensus', 'N/A')
        tps = onchain.get('tps')
        gas = onchain.get('gas')

        a(f"{project_name} is deployed on {chain} using {consensus} consensus. These infrastructure choices constrain the protocol's economic model, transaction costs, and operational security guarantees.\n")

        if tps:
            a(f"Throughput characteristics ({tps}) determine the protocol's ability to scale transaction volume. High throughput (>1000 TPS) enables low transaction costs and supports rapid settlement, creating favorable conditions for high-frequency trading and composable smart contract interaction. Low throughput (<100 TPS) limits transaction volume to fundamental demand, requiring either market segmentation (prioritizing high-value transactions) or off-chain scaling (sharding, rollups, sidechains). The protocol's throughput ceiling directly constrains the total addressable market it can serve profitably.\n")

        if gas:
            a(f"Transaction costs ({gas}) determine the economic viability of different use cases. High costs (>$1 per transaction) price out small retail trades and limit protocol usefulness to high-capital participants accumulating large positions. Low costs (<$0.01) enable composability, arbitrage, and high-frequency interaction, but may also commoditize the protocol's services and create race-to-the-bottom pricing dynamics. The protocol's gas model influences whether it becomes a global-scale retail platform or a high-capital-only wholesale market.\n")
        a("")

        # Smart contracts
        contracts = onchain.get('contracts', [])
        if contracts:
            a("**Smart Contract Deployments:**\n\n")
            a("| Contract | Address | Purpose |")
            a("|----------|---------|---------|")
            for c in contracts:
                name = c.get('name', '—')
                addr = c.get('address', '—')[:20]
                purpose = c.get('purpose', '—')
                a(f"| {name} | {addr}... | {purpose} |")
            a("")

    # ── 3.4 Development Velocity ─────────────────────────────
    a("## 3.4 Development Activity and Innovation Velocity\n")
    github = _get_collected_data(d, 'github', default={}) or d.get('github', {}) or d.get('live_github', {})

    if github:
        stars = github.get('stars')
        forks = github.get('forks')
        commits = github.get('recent_commits', [])
        last_push = github.get('last_push_date')

        if stars or commits:
            a(f"GitHub activity metrics serve as a leading indicator of development health and competitive intensity. ")

        if stars:
            a(f"With {stars:,} stars, the repository has attracted meaningful developer interest, though this metric alone does not indicate active development — high star counts can reflect historical prominence of abandoned projects. ")

        if commits:
            commit_count = len(commits) if isinstance(commits, list) else commits
            if commit_count > 20:
                a(f"Recent commit activity ({commit_count} commits) indicates a highly active development cadence, suggesting that the team is continuously shipping improvements, bug fixes, and new features. High development velocity is a positive signal: it indicates that {project_name} is not coasting on its installed base but rather competing to maintain technological relevance. Sustained velocity through market cycles (especially during bear markets) signals founder commitment and internal conviction.\n")
            elif commit_count > 5:
                a(f"Moderate commit activity ({commit_count} commits) suggests that the protocol is actively maintained but not in a rapid iteration phase. This pattern typically emerges after major features have shipped and the protocol has moved into optimization and stability-focused development. For mature protocols, moderate development velocity may reflect fundamentals maturity (fewer bugs to fix) rather than lack of progress.\n")
            else:
                a(f"Low commit activity ({commit_count} commits) raises questions about development momentum. While mature protocols sometimes enter maintenance mode, continued low activity over multiple months can signal either satisfied feature completeness or organizational challenges affecting development prioritization. Low activity during competitive heating — when other protocols are shipping — creates relative disadvantage.\n")

        if last_push:
            a(f"Most recent development activity occurred {last_push}, which helps establish whether the repository is actively maintained or approaching abandoned status. Regular updates (at least monthly) suggest ongoing engagement; gaps exceeding 3-6 months warrant investigation into whether activity has shifted to private repositories or whether development has stalled.\n")
        a("")

    # ── 3.5 Innovation Assessment ────────────────────────────
    a("## 3.5 Innovation Capacity and Technical Differentiation\n")
    a(f"The technical architecture of {project_name} must balance innovation with security. Pure innovation carries risk — novel mechanisms lack battle-tested track records and may harbor subtle design flaws. Pure conservatism carries obsolescence risk — protocols that fail to innovate lose competitive positioning as competitors implement superior mechanisms.\n")
    a("")
    a(f"Evaluation requires assessing whether {project_name}'s technical advantages represent sustainable competitive moats (difficult for competitors to replicate) or temporary leads that will be arbitraged away as other protocols implement similar features. The strongest positions combine novel mechanisms with strong execution, creating a both a technological lead and a cultural/organizational lead that persists even after features are copied.\n")
    a("")

    # ── 3.6 Crypto Economic System Composition ──────────────
    a("## 3.6 Crypto Economic System Composition — Value Production Analysis\n")
    crypto_econ = d.get('crypto_economy', {})
    value_sys = crypto_econ.get('value_system', {}) if crypto_econ else {}

    a(f"The technical architecture of {project_name} exists to serve an economic function: producing verifiable, scalable value that justifies token rewards and sustains network participation. Understanding the composition of {project_name}'s crypto-economic system requires analyzing WHAT economic value the protocol creates on-chain versus through off-chain mechanisms, and HOW the protocol's architecture enables verification of that value.\n\n")

    # On-chain value production
    onchain_comp = value_sys.get('onchain_components', [])
    if onchain_comp:
        a("**On-Chain Value Production Components:**\n\n")
        for component in onchain_comp:
            if isinstance(component, dict):
                name = component.get('name', 'Unknown')
                desc = component.get('description', '')
                econ_impact = component.get('economic_impact', '')
                a(f"- **{name}:** {desc}\n")
                if econ_impact:
                    a(f"  *Economic Impact:* {econ_impact}\n")
            else:
                a(f"- {component}\n")
        a("")
    else:
        a("**On-Chain Value Production Components:** Protocols create on-chain value through state verification (cryptographic proof that transactions are valid and in correct order), settlement assurance (finality and immutability), and composability (enabling atomic interaction between multiple applications). These on-chain functions are verifiable by all participants without relying on third-party attestation.\n\n")

    # Off-chain value production
    offchain_comp = value_sys.get('offchain_components', [])
    if offchain_comp:
        a("**Off-Chain Value Production Components:**\n\n")
        for component in offchain_comp:
            if isinstance(component, dict):
                name = component.get('name', 'Unknown')
                desc = component.get('description', '')
                verification = component.get('verification_method', '')
                a(f"- **{name}:** {desc}\n")
                if verification:
                    a(f"  *Verification:* {verification}\n")
            else:
                a(f"- {component}\n")
        a("")
    else:
        a("**Off-Chain Value Production Components:** Protocols may produce value through off-chain execution (computation happening outside the chain), oracle provision (external data ingestion), and state synchronization (maintaining consistency between on-chain and off-chain systems). Off-chain value is verifiable only through reputation, multi-signature attestation, or cryptographic proofs of computation.\n\n")

    # On-chain verifiability assessment
    verifiability = value_sys.get('onchain_verifiability_assessment', '') or value_sys.get('onchain_verifiability', '')
    if verifiability:
        a(f"**On-Chain Verifiability Assessment:** {verifiability}\n\n")
    else:
        a(f"**On-Chain Verifiability Assessment:** Evaluate the percentage of {project_name}'s economic value that is verifiable on-chain (trustless, permissionless, available to all participants) versus off-chain (requiring trust in third parties or reputational mechanisms). Higher on-chain verifiability indicates lower counterparty risk and stronger protocol resilience. Protocols relying heavily on off-chain value should implement multi-signature safeguards, cryptographic proof systems, or redundant oracle networks to minimize trusted intermediaries.\n\n")

    a("This analysis informs risk assessment: protocols whose value production is heavily dependent on off-chain infrastructure face elevated operational risk and counterparty concentration. Protocols with strong on-chain verifiability demonstrate alignment between technical architecture and economic incentives — participants can verify that promised rewards are actually being delivered, reducing need for trust in founders or operators.\n\n")

    return "\n".join(L)


def _chapter_4_onchain_analysis(d: dict) -> str:
    """Chapter 4: On-Chain Data Analysis — deep narrative with market structure insights."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    token_type = d.get('token_type', 'protocol')

    a("# Chapter 4: On-Chain Data Analysis\n")

    # ── 4.1 Total Value Locked and Liquidity Dynamics ────────
    a("## 4.1 Total Value Locked (TVL) and Liquidity Trends\n")
    tvl_data = _get_collected_data(d, 'defi_tvl', default={}) or d.get('defi_tvl', {})
    tvl = tvl_data.get('tvl')
    tvl_24h = tvl_data.get('tvl_change_24h')
    tvl_7d = tvl_data.get('tvl_change_7d')

    if tvl and isinstance(tvl, (int, float)):
        a(f"Total Value Locked (TVL) represents the aggregate dollar value of capital locked within the protocol's smart contracts. For {token_symbol}, current TVL stands at {_format_currency(tvl)}, a metric that reflects both genuine user conviction and speculative capital seeking yield. TVL is a critical signal — it reveals whether the protocol's economic model is attracting meaningful capital, and whether that capital is sticky or mercenary.\n")
        a("")
        a(f"Recent TVL momentum provides important context. ")

        if tvl_24h is not None and tvl_7d is not None:
            a(f"Over the last 24 hours, TVL changed {_format_percentage(tvl_24h)}, while 7-day change registers {_format_percentage(tvl_7d)}. ")

            if tvl_7d and float(tvl_7d) > 10:
                a(f"The {_format_percentage(tvl_7d)} weekly increase indicates that capital is flowing *into* the protocol, suggesting either improved user sentiment about {project_name}, competitive relative returns, or positive announcement momentum. Capital inflow during bear market conditions is particularly bullish, as it suggests fundamental strength beyond sentiment-driven capital cycling.\n")
            elif tvl_7d and float(tvl_7d) < -10:
                a(f"The {_format_percentage(tvl_7d)} weekly decline signals capital outflow, which can reflect either changed return expectations (another protocol offering superior yield), liquidity concerns (users deleveraging or exiting bear markets), or deteriorating protocol fundamentals. TVL declines in isolation are not necessarily catastrophic — cyclical yield farming has generated repeated boom-bust patterns in DeFi where capital sloshes between protocols — but sustained declines over multiple weeks warrant investigation into root causes.\n")
            else:
                a(f"The modest {_format_percentage(tvl_7d)} change indicates stable TVL conditions, suggesting that {project_name} is retaining capital neither attracting nor losing deposits at significant scale. Stability can reflect equilibrium — users are satisfied with returns and execution — or stagnation, where the protocol is neither winning nor losing competitive share.\n")
        a("")

        # TVL by chain
        chain_tvls = tvl_data.get('chain_tvls', {})
        if chain_tvls and isinstance(chain_tvls, dict):
            a("**TVL Distribution by Blockchain:**\n\n")
            sorted_chains = sorted(chain_tvls.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True)

            chain_text = []
            for chain, amount in sorted_chains[:5]:
                if isinstance(amount, (int, float)) and tvl:
                    pct = (amount / tvl) * 100
                    chain_text.append(f"{chain}: {_format_currency(amount)} ({pct:.1f}%)")

            if chain_text:
                a("Liquidity distribution across blockchains reveals operational priorities and user preferences. ")
                for ct in chain_text:
                    a(f"- {ct}")

                dominant_chain = sorted_chains[0][0] if sorted_chains else None
                if dominant_chain:
                    dom_pct = (sorted_chains[0][1] / tvl * 100) if tvl else 0
                    if dom_pct > 70:
                        a(f"\nThe dominance of {dominant_chain} ({dom_pct:.0f}% of TVL) creates concentration risk. Single-chain dependence means that {project_name} is vulnerable to {dominant_chain}-specific risks — network outages, regulatory actions, or technical failures that affect primarily {dominant_chain} could severely impact protocol operations. Multi-chain protocols typically pursue Ethereum-first strategies early (Ethereum dominance) then gradually expand to Layer 2s and alternative chains as capital scales.\n")
                    else:
                        a(f"\nThe distributed TVL across multiple chains ({dominant_chain} dominant at {dom_pct:.0f}%) indicates a mature multi-chain strategy, reducing single-chain risk and enabling {project_name} to capture users regardless of which blockchain they prefer. Operational complexity is elevated — the protocol must maintain security and feature parity across multiple implementations — but the strategic advantage (geographic/chain diversification) is significant.\n")
                a("")

    # ── 4.2 Holder Distribution and Concentration ───────────
    a("## 4.2 Token Holder Distribution and Concentration Analysis\n")
    onchain_info = _get_collected_data(d, 'onchain_token_info', default={}) or d.get('onchain_token_info', {})
    holders = _get_collected_data(d, 'onchain_holders', default={}) or d.get('onchain_top_holders', {})

    if holders and 'holders' in holders:
        holder_list = holders.get('holders', [])
        if holder_list:
            a("**Top 10 Holders:**\n\n")
            a("| Rank | Address | Quantity | % of Supply |")
            a("|:---:|---------|----------|:-----------:|")

            for idx, h in enumerate(holder_list[:10], 1):
                addr = h.get('address', '—')
                qty = h.get('quantity', 'N/A')
                pct = h.get('percentage', 'N/A')
                addr_short = f"{addr[:8]}...{addr[-6:]}" if addr and len(addr) > 15 else addr
                a(f"| {idx} | {addr_short} | {qty} | {pct} |")
            a("")

            # Concentration metrics
            top_5_pct = sum(
                float(h.get('percentage', 0)) if isinstance(h.get('percentage'), (int, float, str)) else 0
                for h in holder_list[:5]
            )
            top_10_pct = sum(
                float(h.get('percentage', 0)) if isinstance(h.get('percentage'), (int, float, str)) else 0
                for h in holder_list[:10]
            )
            top_20_pct = sum(
                float(h.get('percentage', 0)) if isinstance(h.get('percentage'), (int, float, str)) else 0
                for h in holder_list[:20]
            )

            a("## Concentration Risk Assessment\n")
            a(f"The top 5 holders control {top_5_pct:.1f}% of circulating supply, the top 10 control {top_10_pct:.1f}%, and the top 20 control {top_20_pct:.1f}%. These metrics quantify governance risk, exit risk, and regulatory scrutiny risk.\n")
            a("")

            if top_10_pct > 80:
                a(f"**EXTREME CONCENTRATION RISK.** The {top_10_pct:.1f}% concentration in top 10 holders creates severe dependencies. The protocol is functionally governed by a small group, whose coordinated action could trigger price collapse. Regulatory risk is elevated — exchanges and institutions view extreme concentration as a red flag for securities-like characteristics. New users accumulating {token_symbol} face counterparty risk: if early holders lose conviction, their exits could overwhelm the market. For this profile to be acceptable, there must exist contractual vesting schedules (founder tokens locked for N years) demonstrating long-term alignment, transparent governance structures preventing capture, and clear messaging that early concentrations will dilute over time.\n")
            elif top_10_pct > 50:
                a(f"**HIGH CONCENTRATION RISK.** The {top_10_pct:.1f}% concentration in top 10 indicates founder/early investor dominance typical of newer tokens. This profile is common but creates material risks. Monitor vesting schedules meticulously — as locked tokens unlock, selling pressure may intensify if early investors lose conviction. Watch exchange inflows from these top holders; large transfers to exchanges signal potential exit preparation. The protocol can mitigate these risks through transparent communication of long-term founder commitment (e.g., lock announcements, pledge commitments) and demonstrated development success that maintains founder confidence.\n")
            elif top_10_pct > 30:
                a(f"**MODERATE CONCENTRATION.** The {top_10_pct:.1f}% concentration is reasonable, suggesting distribution across a broader base of participants. Governance capture risk is diminished, regulatory scrutiny is moderate, and exit risk is manageable. Continue monitoring for accumulation patterns — if large holders are consistently buying, accumulation to dangerous concentration levels may occur over time.\n")
            else:
                a(f"**HEALTHY DISTRIBUTION.** The {top_10_pct:.1f}% concentration in top 10 reflects a well-distributed token, with no single entity commanding dominant power. This distribution pattern suggests either mature market structure (secondary sales have distributed original allocation) or deliberate distribution strategy (e.g., fair launch, community distribution). Governance is resistant to capture, exit risk is low, and regulatory friction is minimal.\n")
            a("")

    # ── 4.3 Token Contract Information ───────────────────────
    if onchain_info:
        a("## 4.3 Token Contract Specifications\n")
        token_name = onchain_info.get('name', 'Unknown')
        decimals = onchain_info.get('decimals')
        total_supply = onchain_info.get('total_supply')

        a(f"**Token Name:** {token_name}  \n")
        if decimals is not None:
            a(f"**Decimal Places:** {decimals}  \n")
        if total_supply:
            try:
                divisor = 10 ** int(decimals) if decimals else 1
                supply_formatted = int(total_supply) / divisor
                a(f"**Total Supply:** {supply_formatted:,.0f}  \n")
            except:
                a(f"**Total Supply:** {total_supply}  \n")
        a("")

    a(f"On-chain data provides the objective facts about {token_symbol}'s distribution and protocol capital allocation. However, numbers alone do not reveal intent — they reveal only outcomes. To understand what these metrics imply for future risk and return, one must triangulate this data against governance voting patterns, team communications, vesting schedules, and market behavior. On-chain analysis is necessary but not sufficient.\n")
    a("")

    return "\n".join(L)


def _chapter_5_token_economy(d: dict) -> str:
    """Chapter 5: Token Economy Design — deep narrative using crypto economy design methodology framework."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')

    a("# Chapter 5: Token Economy Design\n")

    # ── Retrieve both old and new methodology data ──────────────
    te = d.get('token_economy', {})
    ce = d.get('crypto_economy', {})

    # Fallback to old fields if new methodology data is absent
    dist = te.get('distribution', [])
    inf_def = te.get('inflation_deflation', '')
    vesting = te.get('vesting', '')
    utility = te.get('utility', '')

    # Check if we have new methodology framework data
    has_methodology = bool(ce) and any([
        ce.get('value_system'),
        ce.get('reward_system'),
        ce.get('reward_mechanisms'),
        ce.get('lifecycle_assessment')
    ])

    if has_methodology:
        # ── NEW METHODOLOGY FRAMEWORK APPROACH ────────────────────────────
        a("## 5.1 Value System (가치 시스템) — Protocol Value Production\n")
        value_sys = ce.get('value_system', {})

        a(f"{project_name}'s value system defines the on-chain and off-chain mechanisms through which the protocol produces and maintains economic value. Understanding value production is foundational to assessing whether token rewards are justified by genuine protocol utility or merely represent wealth transfer from new participants to early participants.\n\n")

        # On-chain components
        onchain_comp = value_sys.get('onchain_components', [])
        if onchain_comp:
            a("**On-Chain Value Components:**\n\n")
            for component in onchain_comp:
                if isinstance(component, dict):
                    name = component.get('name', 'Unknown')
                    desc = component.get('description', '')
                    a(f"- **{name}:** {desc}\n")
                else:
                    a(f"- {component}\n")
            a("")
        else:
            a("**On-Chain Value Components:** State conversion (transaction ordering and validity verification), storage (persistent state management enabling application semantics), event verification (cryptographic proof of occurrence), and finality (immutable recording of transaction results).\n\n")

        # Off-chain components
        offchain_comp = value_sys.get('offchain_components', [])
        if offchain_comp:
            a("**Off-Chain Value Components:**\n\n")
            for component in offchain_comp:
                if isinstance(component, dict):
                    name = component.get('name', 'Unknown')
                    desc = component.get('description', '')
                    a(f"- **{name}:** {desc}\n")
                else:
                    a(f"- {component}\n")
            a("")
        else:
            a("**Off-Chain Value Components:** Execution environment (computation happening outside the chain), synchronization (maintaining consistency between on-chain and off-chain state), and oracles (bridging external data into on-chain contracts).\n\n")

        # Verifiability assessment
        verifiability = value_sys.get('onchain_verifiability_assessment', '') or value_sys.get('onchain_verifiability', '')
        if verifiability:
            a(f"**On-Chain Verifiability:** {verifiability}\n\n")
        else:
            a("**On-Chain Verifiability Assessment:** Evaluate what percentage of protocol value production occurs on-chain (verifiable by all participants) versus off-chain (verifiable only through reputation or third-party attestation). Higher on-chain verifiability increases protocol resilience and reduces counterparty risk.\n\n")

        # ── 5.2 Reward System (보상 시스템) ─────────────────────────
        a("## 5.2 Reward System (보상 시스템) — Contributor Incentives\n")
        reward_sys = ce.get('reward_system', {})

        a(f"The reward system of {project_name} specifies HOW contributors are compensated for their capital and cost contributions. Who receives rewards, on what basis (capital vs. operational cost), and in what quantities determines whether the protocol can sustain growth without perpetual outside capital injection.\n\n")

        # Capital contributions
        capital_contrib = reward_sys.get('capital_contributions', None)
        if capital_contrib:
            a("**Capital Contributions (자본적 기여):**\n\n")
            if isinstance(capital_contrib, dict):
                capital_desc = capital_contrib.get('description', '')
                a(f"{capital_desc}\n\n")
                capital_examples = capital_contrib.get('examples', [])
                for example in capital_examples:
                    a(f"- {example}\n")
            elif isinstance(capital_contrib, list):
                for item in capital_contrib:
                    if isinstance(item, dict):
                        a(f"- **{item.get('type', '')}:** {item.get('description', '')}\n")
                    else:
                        a(f"- {item}\n")
            elif isinstance(capital_contrib, str):
                a(f"{capital_contrib}\n")
            a("")
        else:
            a("**Capital Contributions (자본적 기여):** Investment, staking, and liquidity provision. Contributors allocate capital expecting returns. Capital reward calculations should reflect risk-adjusted returns and compare favorably to alternative investments.\n\n")

        # Cost contributions
        cost_contrib = reward_sys.get('cost_contributions', None)
        if cost_contrib:
            a("**Cost Contributions (비용적 기여):**\n\n")
            if isinstance(cost_contrib, dict):
                cost_desc = cost_contrib.get('description', '')
                a(f"{cost_desc}\n\n")
                cost_examples = cost_contrib.get('examples', [])
                for example in cost_examples:
                    a(f"- {example}\n")
            elif isinstance(cost_contrib, list):
                for item in cost_contrib:
                    if isinstance(item, dict):
                        a(f"- **{item.get('type', '')}:** {item.get('description', '')}\n")
                    else:
                        a(f"- {item}\n")
            elif isinstance(cost_contrib, str):
                a(f"{cost_contrib}\n")
            a("")
        else:
            a("**Cost Contributions (비용적 기여):** Development, operation, validation, and user acquisition. These contributions generate operational costs that must be reimbursed. Cost reward calculations should ensure that rewards exceed actual expenses (otherwise contributors bear losses).\n\n")

        # Actor types
        actor_types = reward_sys.get('actor_types', [])
        if actor_types:
            a("**Reward Recipient Actor Types:**\n\n")
            for actor in actor_types:
                if isinstance(actor, dict):
                    actor_name = actor.get('name', 'Unknown')
                    actor_role = actor.get('role', '')
                    actor_reward = actor.get('reward_mechanism', '')
                    a(f"- **{actor_name}:** {actor_role} | Reward: {actor_reward}\n")
                else:
                    a(f"- {actor}\n")
            a("")
        else:
            a("**Actor Types:** Capital providers (passive yield seekers), Developers (protocol improvement), Network operators (validators, sequencers), End users (activity participants), Service providers (infrastructure, liquidity).\n\n")

        # ── 5.3 Reward Mechanism System (보상수단 시스템) ───────────
        a("## 5.3 Reward Mechanism System (보상수단 시스템) — Distribution Instruments\n")
        reward_mech = ce.get('reward_mechanisms', {}) or ce.get('reward_mechanism', {})

        a(f"The reward mechanisms of {project_name} specify THE INSTRUMENTS used to deliver rewards — what type of assets or rights recipients receive, and how those assets maintain value over time.\n\n")

        # Fungible tokens
        ft_mechanism = reward_mech.get('fungible_token', None)
        if ft_mechanism:
            a("**Fungible Token (FT) — Quantitative/Currency Function:**\n\n")
            if isinstance(ft_mechanism, dict):
                a(f"{ft_mechanism.get('description', '')}\n\n")
                for detail in ft_mechanism.get('details', []):
                    a(f"- {detail}\n")
            elif isinstance(ft_mechanism, str):
                a(f"{ft_mechanism}\n\n")
        else:
            a(f"**Fungible Token (FT) — Quantitative/Currency Function:** {token_symbol} tokens are interchangeable units of value, serving governance and fee-claim functions. FT mechanisms work best when token demand grows with protocol adoption. Risk: if adoption plateaus while token supply continues inflating, FT value depreciates.\n\n")

        # NFT mechanisms
        nft_mechanism = reward_mech.get('nft_mechanism', None) or reward_mech.get('nft_token', None)
        if nft_mechanism:
            a("**Non-Fungible Token (NFT) — Material/Asset Function:**\n\n")
            if isinstance(nft_mechanism, dict):
                a(f"{nft_mechanism.get('description', '')}\n\n")
                for detail in nft_mechanism.get('details', []):
                    a(f"- {detail}\n")
            elif isinstance(nft_mechanism, str):
                a(f"{nft_mechanism}\n\n")
        else:
            a("**Non-Fungible Token (NFT) — Material/Asset Function:** Unique tokens representing specific roles (validator licenses, service provider credentials) or holdings (evidence of staking, liquidity provisioning). NFT mechanisms create role-specific incentives and enable fine-grained reward differentiation.\n\n")

        # Utility tokens
        utility_tok = reward_mech.get('utility_tokens', None) or reward_mech.get('utility_function', None)
        if utility_tok:
            a("**Utility Tokens — Platform Activation:**\n\n")
            if isinstance(utility_tok, dict):
                a(f"{utility_tok.get('description', '')}\n\n")
            elif isinstance(utility_tok, str):
                a(f"{utility_tok}\n\n")
        else:
            a("**Utility Tokens — Platform Activation:** Tokens that unlock access to specific protocol features (trading tier discounts, governance rights, staking privileges). Utility mechanisms align token demand with feature value.\n\n")

        # Distribution mechanics summary
        dist_summary = reward_mech.get('distribution_mechanics', '')
        if dist_summary:
            a(f"**Distribution Mechanics:** {dist_summary}\n\n")

        # ── 5.4 Lifecycle Assessment (라이프사이클 평가) ────────────
        a("## 5.4 Lifecycle Assessment — Genesis to Stability\n")
        lifecycle = ce.get('lifecycle_assessment', {}) or ce.get('lifecycle', {})

        a(f"{project_name} occupies a position within a protocol lifecycle that determines whether the token economy is in bootstrap phase (building initial adoption with heavy subsidy), maturation phase (transitioning toward sustainability), or stability phase (self-sustaining with market-determined rewards).\n\n")

        stages = lifecycle.get('stages', [])
        if stages:
            a("**Lifecycle Stages:**\n\n")
            for stage in stages:
                stage_name = stage.get('name', 'Unknown')
                stage_desc = stage.get('description', '')
                a(f"**{stage_name}:** {stage_desc}\n\n")
        else:
            a("**Lifecycle Stages:** Genesis (initial distribution, founder-driven), Bootstrap (subsidy-heavy growth, capital accumulation), Mature (adoption-driven, cost contributions >50%), Stability (market-determined rewards, self-sufficient), Evolution (parameter optimization, competitive adaptation).\n\n")

        # Bootstrap indicators
        bootstrap_eval = lifecycle.get('bootstrap_evaluation', {}) or lifecycle.get('bootstrap_indicators', {})
        if bootstrap_eval:
            a("**Bootstrap Phase Evaluation:**\n\n")
            a(f"- **Capital Outflow Control:** {bootstrap_eval.get('capital_outflow_control', 'Not assessed')}\n")
            a(f"- **Utility Token Value Formation:** {bootstrap_eval.get('utility_token_value_formation', 'Not assessed')}\n")
            vs_op = bootstrap_eval.get('value_system_operational')
            if vs_op is not None:
                a(f"- **Value System Operational at Inception:** {'Yes' if vs_op else 'No'}\n")
            a("")
        else:
            a("**Bootstrap Phase Evaluation:** Projects in bootstrap phase should demonstrate capital outflow control (limiting founder/investor exits to prevent supply shocks) and utility token value formation mechanisms (ensuring that token value is anchored to protocol utility, not pure speculation).\n\n")

        # Maturity transition indicators
        maturity_indicators = lifecycle.get('maturity_transition_indicators', {}) or lifecycle.get('maturity_indicators', {})
        if maturity_indicators:
            a("**Maturity Transition Indicators (Bootstrap → Mature):**\n\n")
            # Support both string descriptions and boolean values
            for key, label in [
                ('actor_replacement', 'Actor Replacement'),
                ('reward_stabilization', 'Reward Stabilization'),
                ('security_transition', 'Security Token Transition'),
                ('security_token_transition', 'Security Token Transition'),
                ('revenue_realization', 'Revenue Realization'),
                ('decentralization_automation', 'Decentralization & Automation'),
            ]:
                val = maturity_indicators.get(key)
                if val is not None:
                    if isinstance(val, bool):
                        status = '✅ Achieved' if val else '⬜ Not Yet'
                    else:
                        status = str(val)
                    a(f"- **{label}:** {status}\n")
            a("")
        else:
            a("**Maturity Transition Indicators (Bootstrap → Mature):**\n\n")
            a("1. **Actor Replacement Completion:** Shift from capital-provider-driven to usage-driven participants. Early projects are capital-heavy; mature projects derive rewards from actual transaction fees and protocol utility.\n")
            a("2. **Reward Distribution Stabilization:** Cost contribution rewards stabilize at ≤50% of total token issuance. Sustainability requires that not all inflation goes to incentivizing external participation.\n")
            a("3. **Security Token Function Transition:** If protocol began with security-token characteristics (governance tied to investment returns), transition toward pure utility token (governance tied to usage rights).\n")
            a("4. **Revenue Realization:** Bonding curves, exchange operations, and fee mechanisms become operational sources of protocol revenue, enabling treasury self-sufficiency.\n")
            a("5. **Decentralization & Automation:** Governance and operational decisions gradually shift from founder discretion toward automated mechanisms or distributed governance.\n")
            a("")

    else:
        # ── FALLBACK TO TRADITIONAL APPROACH (for projects without new methodology data) ────
        a("## 5.1 Token Distribution and Initial Allocation\n")
        a(f"The initial distribution of {token_symbol} tokens reveals the economic incentives embedded in {project_name}'s founding. Who received tokens, how many, and on what vesting schedule determines whose interests are aligned with protocol success, who faces incentives to exit early, and whether the distribution will create future supply shocks as tokens vest. No distribution is 'neutral' — every choice transfers value and creates incentives.\n\n")

        if dist:
            total_dist_pct = sum(float(item.get('percentage', 0)) if item.get('percentage') else 0 for item in dist)
            a(f"Initial allocation totals {total_dist_pct:.1f}% across the following categories:\n\n")
            a("| Category | Amount | Percentage | Vesting | Strategic Implication |")
            a("|----------|:------:|:----------:|---------|----------------------|")

            for item in dist:
                amt = item.get('amount', 'N/A')
                if isinstance(amt, (int, float)):
                    amt_str = f"{amt:,.0f}"
                else:
                    amt_str = str(amt)
                pct = item.get('percentage', 'N/A')
                vest = item.get('vesting_period', 'N/A')
                notes = item.get('notes', '—')
                category = item.get('category', 'Unknown')
                a(f"| {category} | {amt_str} | {pct}% | {vest} | {notes} |")
            a("")

            # Distribution analysis
            community_pct = next((float(d.get('percentage', 0)) for d in dist if 'community' in d.get('category', '').lower()), 0)
            team_pct = next((float(d.get('percentage', 0)) for d in dist if 'team' in d.get('category', '').lower()), 0)
            investor_pct = next((float(d.get('percentage', 0)) for d in dist if 'investor' in d.get('category', '').lower()), 0)

            if community_pct > 50:
                a(f"The {community_pct:.0f}% community allocation indicates a distribution-focused philosophy. Large community allocations reduce founder/investor concentration risk and create positive optics — the narrative frames {token_symbol} as 'for the community' rather than founder-enrichment. However, community allocations often translate to liquidity rather than long-term conviction. Analyzing vesting schedules reveals whether community tokens unlock gradually (reducing single-day supply shock) or in bulk (creating sale pressure).\n")
            elif team_pct > 30:
                a(f"The {team_pct:.0f}% allocation to team indicates founder/contributor alignment — if the token appreciates, the team benefits directly. This creates incentive alignment, as team success directly drives team wealth. However, large team allocations also create risk if vesting is short (team can exit quickly if they lose conviction) or if the vesting is front-loaded (creating concentrated supply shock at cliff event). The strength of founder lock-ups determines whether team incentives remain aligned long-term.\n")

            if investor_pct > 20:
                a(f"The {investor_pct:.0f}% investor allocation reflects capital raised from early investors. Investor tokens typically have longer vesting schedules than community distributions, but shorter than founder tokens, reflecting their intermediate-term conviction. Large investor allocations signal that {project_name} raised meaningful capital in early rounds, providing runway for development but also creating obligations to those investors (who will seek exits as returns accrue).\n")
            a("")

        # ── 5.2 Supply Mechanics ─────────────────────────────────
        a("## 5.2 Supply Mechanics and Inflation/Deflation Analysis\n")
        if inf_def:
            a(inf_def.strip())
        else:
            a(f"The supply mechanics of {token_symbol} determine whether the token is inflationary (new tokens continuously created) or deflationary (tokens burned, reducing supply over time). This distinction is fundamental to long-term value preservation.\n")

        a("")
        a(f"**Inflationary vs. Deflationary Models:** Tokens with continuous minting (inflation) create ongoing selling pressure as newly minted tokens are distributed to stakers, liquidity providers, or treasury. For inflation to not destroy value, token demand must grow faster than supply growth. Deflationary tokens (where a percentage of fees are burned) create opposite dynamics — if demand is stable, decreasing supply creates increasing scarcity and price pressure. Deflation creates alignment: protocol success (higher fee volume) directly creates scarcity.\n")

        if vesting:
            a("\n## 5.3 Vesting Schedule and Supply Unlocks\n")
            a(vesting.strip())
            a("")
        else:
            a(f"\nToken vesting schedules reveal future supply dilution events. Founder tokens typically vest over 3-4 year periods with cliff cliffs (no tokens vest until year 1, then monthly vesting thereafter). Investor tokens vest faster (2-3 years). Analyzing the vesting calendar helps forecast when supply shocks may occur — when large token tranches unlock and become available for sale.\n")

        # ── 5.4 Token Utility ────────────────────────────────────
        a("\n## 5.4 Token Utility and Demand Drivers\n")
        if utility:
            a(utility.strip())
            a("")
        else:
            a(f"{token_symbol} serves multiple economic functions within {project_name}: governance voting rights, claim on protocol fee revenue, staking collateral for yield generation, and potentially as transaction settlement layer. Multi-purpose tokens benefit from cumulative demand — users accumulate {token_symbol} for *each* use case, multiplying total demand beyond any single use.\n")
            a("")

        a("Critical question: Is token demand *necessary* or merely *convenient*? Necessary demand (tokens required to use the protocol) creates unavoidable value capture. Convenient demand (tokens provide incremental benefits but aren't strictly required) is vulnerable to substitution — users can conduct business without the token, creating ceiling on demand growth. The strongest token economics combine necessity and scarcity.\n")
        a("")

        # ── 5.5 Economic Sustainability ──────────────────────────
        a("## 5.5 Economic Sustainability and Long-Term Viability\n")
        a(f"Token economy sustainability requires a fundamental equilibrium: the present value of future token utility must exceed current supply and inflation. If the protocol issues 100% of new tokens as rewards annually, and utility demand is flat, token holders face 100% annual dilution — a mathematically unsustainable state requiring perpetual new capital inflows to sustain prices.\n")
        a("")
        a(f"Evaluate {token_symbol}'s sustainability by computing the relationship between supply growth and demand growth over time. Projects demonstrating declining inflation rates (moving toward fixed supply) as adoption increases show mathematical discipline. Projects with perpetual fixed inflation face pressure to continuously accelerate adoption to maintain valuations. The strongest projects eventually become deflationary through fee burns, aligning incentives across stakeholders.\n")
        a("")

    return "\n".join(L)


def _chapter_6_financial_performance(d: dict) -> str:
    """Chapter 6: Financial Performance & Valuation — deep narrative on price, volume, and relative value."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')

    a("# Chapter 6: Financial Performance & Valuation\n")

    # ── 6.1 Price Trend Analysis ─────────────────────────────
    a("## 6.1 Price Trends and Historical Performance\n")
    a(f"Token price reflects the market's aggregated expectations about {project_name}'s future cash flows, competitive position, and survival probability. Prices move because of new information — fundamental developments affecting the protocol, competitive shifts, macro changes affecting risk appetite, or sentiment swings driven by social media and retail momentum. Decomposing price movements into genuine fundamentals versus noise requires careful analysis.\n\n")

    market = _get_collected_data(d, 'market_data', default={}) or d.get('market_data', {})
    price_hist = _get_collected_data(d, 'price_history', default={}) or d.get('price_history_90d', {}) or d.get('live_price_history', [])
    pct_change_90, current_price, start_price = _extract_price_trend(price_hist)

    if pct_change_90 is not None and current_price and start_price:
        a(f"Over the past 90 days, {token_symbol} has moved {_format_percentage(pct_change_90)}, ranging from {_format_currency(start_price)} to {_format_currency(current_price)}. ")

        if pct_change_90 > 50:
            a(f"The strong upside movement suggests either improving fundamentals (protocol adoption accelerating, competitive wins announced), improving macro conditions (fear & greed index rising, Bitcoin dominance declining), or sentiment-driven momentum unrelated to fundamentals. To validate whether the move is sustainable, investigate whether it occurred alongside positive news or simply during a market-wide rotation into risk assets.\n")
        elif pct_change_90 < -50:
            a(f"The significant downside movement indicates either deteriorating fundamentals (user exodus, security incident, competitive loss), deteriorating macro conditions (crypto market-wide downturn, regulatory pressure), or both. For investors considering entry at depressed prices, this period creates opportunity — but only if the underlying thesis remains intact. If the thesis has changed (original value proposition no longer applies), low prices are a value trap rather than an opportunity.\n")
        else:
            a(f"The modest 90-day movement suggests either range-bound trading with stable sentiment, or offsetting moves that netted to flat performance. Examine intra-period highs and lows to determine whether price volatility increased or remained muted.\n")
        a("")

        # Volatility
        if isinstance(price_hist, dict) and 'data' in price_hist:
            prices = [d.get('price') for d in price_hist['data'] if d.get('price')]
        elif isinstance(price_hist, list):
            prices = [p for p in price_hist if isinstance(p, (int, float))]
        else:
            prices = []

        if prices and len(prices) > 1:
            min_p = min(prices)
            max_p = max(prices)
            avg_p = sum(prices) / len(prices)
            volatility = ((max_p - min_p) / avg_p) * 100 if avg_p > 0 else 0

            a(f"**90-Day Price Range:** {_format_currency(min_p)} to {_format_currency(max_p)} ({_format_percentage(((max_p - min_p) / min_p) * 100 if min_p else 0)})  \n")
            a(f"**Volatility (Range/Mean):** {volatility:.1f}%  \n\n")

            if volatility > 100:
                a(f"Extreme volatility ({volatility:.1f}%) indicates wild price swings. This can reflect limited liquidity (small trades cause large percentage moves), speculative interest (retail traders rapidly alternating between conviction and panic), or fundamental uncertainty (critical information about the project remains unresolved). Extreme volatility benefits tactical traders but punishes buy-and-hold investors — positions experience drawdowns that can psychologically test conviction. For long-term holders, extreme volatility creates opportunity to accumulate at low points, but also creates execution risk (entering at what appears to be the bottom but discovers further downside exists).\n")
            elif volatility > 50:
                a(f"High volatility ({volatility:.1f}%) is typical for altcoins during cycles of information arrival and sentiment shifts. Positive news about roadmap delivery can spark sharp rallies; bad news or macro headwinds trigger sharp drops. This volatility is manageable if the underlying thesis is sound — patient investors can tolerate drawdowns, knowing that the long-term thesis creates eventual recovery.\n")
            elif volatility > 25:
                a(f"Moderate volatility ({volatility:.1f}%) suggests relatively orderly price discovery. Market participants are digesting information methodically rather than through panic buying/selling. This environment is favorable for fundamental investors, as sentiment-driven noise is minimized and prices more closely reflect underlying value.\n")
            else:
                a(f"Low volatility ({volatility:.1f}%) can reflect either strong consensus among investors (everyone agrees on value) or low trading activity (few trades, so prices remain sticky). Investigate trading volume to distinguish these cases. Low volume plus low volatility signals illiquidity and potential challenge for exit at scale.\n")
            a("")

    # ── 6.2 Market Metrics and Liquidity ──────────────────────
    a("## 6.2 Market Metrics and Liquidity Assessment\n")
    if market.get('current_price'):
        a(f"**Current Price:** {_format_currency(market['current_price'])}  \n")
    if market.get('market_cap'):
        a(f"**Market Capitalization:** {_format_currency(market['market_cap'])}  \n")
    if market.get('volume_24h'):
        a(f"**24h Trading Volume:** {_format_currency(market['volume_24h'])}  \n")

        # Volume/MCap ratio
        if market.get('market_cap') and market.get('volume_24h'):
            vol_ratio = (market['volume_24h'] / market['market_cap']) * 100
            a(f"**Volume/Market Cap Ratio:** {vol_ratio:.2f}%  \n\n")

            if vol_ratio > 20:
                a(f"Very high trading volume ({vol_ratio:.2f}% daily turnover) indicates strong retail speculation and active short-term positioning. This liquidity is excellent for entry and exit, but also signals that price movements may be sentiment-driven rather than fundamental. High volume can reflect both healthy price discovery (many participants trading, creating many views on fair value) and unhealthy speculation (leverage-driven trading creating volatility without information).\n")
            elif vol_ratio > 10:
                a(f"High trading volume ({vol_ratio:.2f}% daily turnover) indicates active participation from both retail and institutional traders. Liquidity is generally good, and slippage on moderate-sized trades (<$10M) is minimal. This level suggests a healthy market with good price discovery.\n")
            elif vol_ratio > 5:
                a(f"Moderate trading volume ({vol_ratio:.2f}% daily turnover) is typical for mid-cap altcoins. Liquidity is adequate for most traders but large positions may require multiple days to build or exit to avoid price impact.\n")
            elif vol_ratio > 2:
                a(f"Low trading volume ({vol_ratio:.2f}% daily turnover) suggests potential liquidity constraints. Traders considering $1M+ positions may face slippage costs. Institutions often require minimum volume thresholds before entering positions, creating a feedback loop where low institutional interest further suppresses volume.\n")
            else:
                a(f"Very low trading volume ({vol_ratio:.2f}% daily turnover) indicates severe liquidity challenges. Meaningful position changes face substantial slippage. This environment is favorable for low-volume accumulation but creates execution risk — if significant demand emerges, it would face limited sell-side liquidity and cause sharp price movement.\n")
        a("")

    # ── 6.3 ATH/ATL Context ──────────────────────────────────
    a("## 6.3 All-Time High/Low Context and Investor Sentiment\n")
    if market.get('ath') and market.get('current_price'):
        ath = market['ath']
        price = market.get('current_price')
        pct_from_ath = ((price - ath) / ath) * 100

        a(f"**Distance from All-Time High:** {_format_percentage(pct_from_ath)}  \n\n")

        if pct_from_ath > -20:
            a(f"Trading {pct_from_ath:.0f}% from ATH indicates that {token_symbol} is near all-time valuation highs. This can signal investor enthusiasm if the protocol is delivering on promises and adopting users, or valuation euphoria if prices have divorced from fundamentals. Near-ATH pricing creates risk for new entrants — margin of safety is minimal, and any negative news can trigger sharp corrections. Existing holders face the psychological pressure of being underwater if ATH represented a bubble.\n")
        elif pct_from_ath > -50:
            a(f"Trading {pct_from_ath:.0f}% from ATH indicates moderate drawdown from peak valuations. This is typical for tokens that have experienced healthy rallies followed by consolidation. The price offers reasonable value relative to peak, but is still above long-term entry points.\n")
        elif pct_from_ath > -80:
            a(f"Trading {pct_from_ath:.0f}% from ATH indicates substantial drawdown from peak. This reflects either genuine loss of confidence in the protocol (thesis has changed, competition has escalated, execution has failed) or healthy mean-reversion after a hype-driven rally. Distinguish these by examining whether fundamental value proposition remains intact. If it does, this drawdown creates opportunity.\n")
        else:
            a(f"Trading {pct_from_ath:.0f}% from ATH indicates catastrophic loss of valuation. This suggests severe loss of investor confidence, either from deterioration in protocol fundamentals (failed roadmap, major security incident, regulatory action) or from unsustainable hype cycles that have fully unwound. Deep underwater prices are often value traps rather than opportunities — thoroughly investigate root causes before assuming the discount represents opportunity.\n")

        if market.get('atl') and price:
            atl = market['atl']
            pct_from_atl = ((price - atl) / atl) * 100
            a(f"**Distance from All-Time Low:** {_format_percentage(pct_from_atl)}  \n\n")
            a(f"Current price sits {pct_from_atl:.0f}% above the all-time low, indicating the token's range of historical valuations. If current price is close to ATL (within 50%), the protocol faces existential questions — either it has failed and will disappear, or it offers exceptional value and will recover. This binary outcome creates both extreme risk and extreme potential reward.\n")
        a("")

    # ── 6.4 Relative Valuation ───────────────────────────────
    a("## 6.4 Relative Valuation and Peer Comparison\n")
    a(f"Evaluating {token_symbol} in isolation provides limited insight. Comparative analysis against peer protocols in the same category (DeFi, L1, gaming, AI, etc.) reveals whether the token is expensively or cheaply valued relative to peers with similar characteristics. Key metrics include:\n")
    a("")
    a(f"- **Price-to-TVL Ratio (for DeFi):** {project_name}'s market cap divided by total value locked reveals the market's valuation of protocol profits. Low ratios suggest cheap valuations (assuming TVL generates sustainable revenue); high ratios suggest expensive valuations or low profit expectations.\n")
    a(f"- **Market Cap Rank:** Relative position among protocols in the same category (e.g., rank #5 DEX, rank #2 lending platform) provides context on competitive positioning and market preference.\n")
    a(f"- **User Metrics:** If available, compare daily active users, transaction volume, and network growth rates against competitors. Superior growth rates justify premium valuations; stagnant growth does not.\n")
    a("")

    # ── 6.5 Price Discovery ──────────────────────────────────
    a("## 6.5 Price Discovery Efficiency and Information Timing\n")
    a(f"Price discovery in token markets is inefficient relative to mature equity markets. Information asymmetries, limited analyst coverage, and retail trader dominance create opportunities for informed investors. Observable patterns help assess whether {token_symbol} prices discover information efficiently:\n")
    a("")
    a(f"- **Prices leading fundamentals** (token rallying 2-4 weeks before positive announcements) suggest sophisticated participants are incorporating information early.\n")
    a(f"- **Prices lagging fundamentals** (token stagnant despite positive developments) suggest market inefficiency — the market hasn't fully incorporated available information.\n")
    a(f"- **Surprise cascades** (negative development followed by further declines weeks later) suggest panic selling and herd behavior rather than measured repricing.\n")
    a("")

    return "\n".join(L)


def _chapter_7_governance_community(d: dict) -> str:
    """Chapter 7: Governance & Community — deep narrative on governance quality and dev ecosystem."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')

    a("# Chapter 7: Governance & Community\n")

    # ── 7.1 Governance Structure ─────────────────────────────
    a("## 7.1 Governance Model and Decision-Making Framework\n")
    gov_info = d.get('governance', {})
    if gov_info and isinstance(gov_info, dict):
        model = gov_info.get('model', '')
        if model:
            a(model.strip())
            a("")
        else:
            a(f"{project_name}'s governance framework determines how the protocol evolves over time. Critical decisions — protocol parameters (fees, voting thresholds), treasury allocation, upgrade approval — flow through governance mechanisms that either concentrate power (single founder/team) or distribute it (token-holder voting). Governance quality directly impacts protocol sustainability and community confidence.\n")
            a("")
    else:
        a(f"{project_name} operates through a governance framework enabling {token_symbol} holders to vote on protocol evolution. Decentralized governance provides legitimacy and community buy-in, but introduces challenges: voter apathy (low participation rates), voter capture (large holders controlling outcomes), and slow decision-making (consensus-building takes time). Evaluate governance quality on three dimensions:\n")
        a("")
        a("**Participation Rate:** The percentage of eligible voters participating in governance votes reveals community engagement. Rates >30% indicate strong stakeholder interest; rates <10% suggest tokenholders are voting with their exit option (selling) rather than using voice. Low participation creates governance capture risk — small groups of determined voters can control outcomes even if they represent small percentages of total voting power.\n")
        a("")
        a("**Decision Quality:** Examine historical governance decisions and their outcomes. Do proposals demonstrate clear thinking about tradeoffs, or are they reactive decisions made under pressure? Do implemented decisions drive measurable improvements (increased adoption, reduced risks)?\n")
        a("")
        a("**Implementation Speed:** From proposal to execution, how long do decisions take? Fast implementation (1-4 weeks) indicates governance is functioning as a useful decision-making tool; slow implementation (3-6 months) suggests that governance creates bottlenecks rather than enablement. During rapid competitive evolution, slow governance becomes a strategic liability.\n")
        a("")

    # ── 7.2 Developer Ecosystem ──────────────────────────────
    a("## 7.2 Developer Activity and Innovation Ecosystem\n")
    github = _get_collected_data(d, 'github', default={}) or d.get('github', {}) or d.get('live_github', {})

    if github:
        commits = github.get('recent_commits', [])
        stars = github.get('stars')
        forks = github.get('forks')
        last_push = github.get('last_push_date')

        a(f"Developer activity metrics reveal whether {project_name} is actively evolving or stagnant. A vibrant developer ecosystem attracts contributors (improving code quality), prevents single-point-of-failure dependency (if core team fragments, community continues development), and creates network effects where external developers build on top of the protocol.\n\n")

        if stars:
            a(f"**GitHub Stars:** {stars:,} — indicates developer interest and community signal of code quality. While not a perfect metric (old projects accumulate stars regardless of current activity), star count correlates with ecosystem attention.\n")

        if forks:
            a(f"**Forks:** {forks:,} — measures how many developers have created their own copy for experimentation or contribution. High forks indicate active external development.\n")

        if isinstance(commits, list):
            commit_count = len(commits)
            a(f"**Recent Commits:** {commit_count} ")

            if commit_count > 30:
                a(f"indicates highly active development. The team is shipping continuously, suggesting either rapid innovation cycles or responsive bug-fixing. Sustained high activity through bear markets is particularly bullish, as it signals internal conviction independent of price momentum.\n")
            elif commit_count > 10:
                a(f"indicates moderately active development. The protocol is being maintained and improved, but not in a breakneck innovation cycle. This pattern is typical for mature protocols where architecture is settled and development focuses on optimization and stability.\n")
            elif commit_count > 5:
                a(f"indicates low but consistent activity. Core infrastructure is receiving attention, but new feature development may have stalled. Investigate why: is the protocol feature-complete (explaining modest commits), or is development momentum slowing (concerning for competitive positioning)?\n")
            else:
                a(f"indicates minimal development activity. This raises urgent questions about project status. Is the protocol intentionally in maintenance mode? Or has the core team shifted focus? Low activity for extended periods (>6 months) typically indicates either abandoned projects or severely constrained resources.\n")

        if last_push:
            a(f"**Latest Activity:** {last_push} — reveals whether the repository is actively maintained (recent commits) or dormant (last push >3 months ago).\n")

        a("")

    # ── 7.3 Community Health ─────────────────────────────────
    a("## 7.3 Community Health and Ecosystem Strength\n")
    a(f"Beyond development metrics, strong communities create competitive advantages for {project_name}. Healthy communities:\n\n")
    a("- **Attract developers:** A vibrant, respectful community with clear documentation and mentorship attracts external contributors, accelerating development.\n")
    a("- **Create network effects:** As communities grow and collaborate, switching costs increase — users become invested in the ecosystem social layer, not just the protocol.\n")
    a("- **Provide governance checks:** Active communities apply informal pressure on decision-making, limiting founder capture and bad decisions.\n")
    a("- **Generate content and narratives:** Communities create content (blog posts, YouTube videos, research papers) that spreads protocol understanding and builds adoption momentum.\n")
    a("")
    a(f"Community health is difficult to quantify but essential to assess. Examine Discord/Telegram activity (Is discussion high-quality or pure speculation?), forum participation (Are there thoughtful technical discussions or only marketing?), and social media sentiment (Does the community discuss fundamentals or only price?). The highest-conviction communities combine active discussion with skepticism — they question the team and push for accountability.\n")
    a("")

    # ── 7.4 Governance Participation ─────────────────────────
    a("## 7.4 Governance Participation and Token Voter Engagement\n")
    participation = d.get('governance_participation', {})
    if participation:
        avg_part = participation.get('avg_participation')
        recent_props = participation.get('recent_proposals')
        if avg_part:
            a(f"Average governance participation: {avg_part}  \n")
        if recent_props:
            a(f"Recent proposals: {recent_props}  \n")
        a("")
    else:
        a(f"Governance participation rates reveal how actively {token_symbol} holders engage with protocol evolution. High participation (>30% of eligible voters) indicates strong community interest and distributed decision-making. Low participation (<10%) signals that tokenholders are either disengaged or voting with the exit option (selling rather than participating). Monitor participation trends over time:\n\n")
        a("- **Rising participation:** Indicates growing community engagement and confidence in governance mechanisms.\n")
        a("- **Declining participation:** Can signal governance fatigue (voters exhausted from frequent voting), loss of confidence in governance outcomes, or fundamental shift in tokenholding (early engaged holders selling to passive investors).\n")
        a("- **Concentrated voting:** Even with high participation, voting power can concentrate in a few large holders, creating de facto governance capture.\n")
        a("")

    # ── 7.5 Lifecycle Stage Assessment ───────────────────────
    a("## 7.5 Lifecycle Stage Assessment — Genesis to Mature Transition\n")
    lifecycle = d.get('lifecycle_stage', {})
    crypto_econ = d.get('crypto_economy', {})
    lifecycle_data = (crypto_econ.get('lifecycle_assessment', {}) or crypto_econ.get('lifecycle', {})) if crypto_econ else {}

    a(f"{project_name}'s position within the protocol lifecycle (Genesis → Bootstrap → Mature → Stable → Evolution) determines whether governance is founder-directed (early stages) or community-directed (mature stages), and whether the token economy is subsidy-driven (bootstrap) or revenue-driven (mature). Evaluating lifecycle stage requires assessing five critical transition indicators:\n\n")

    # Access lifecycle transition indicators from either lifecycle_data or lifecycle dict
    indicators = (lifecycle_data.get('maturity_transition_indicators', {}) or lifecycle_data.get('maturity_indicators', {})) if lifecycle_data else {}
    if not indicators and isinstance(lifecycle, dict):
        indicators = {
            'actor_replacement': lifecycle.get('actor_replacement'),
            'reward_stabilization': lifecycle.get('reward_stabilization'),
            'security_transition': lifecycle.get('security_transition'),
            'revenue_realization': lifecycle.get('revenue_realization'),
            'decentralization_automation': lifecycle.get('decentralization_automation')
        }

    a("### Bootstrap → Mature Transition Indicators\n\n")

    # 1. Actor Replacement Completion
    actor_replacement = indicators.get('actor_replacement')
    if actor_replacement is not None:
        status = '✅ Achieved' if actor_replacement is True else ('⬜ Not Yet' if actor_replacement is False else str(actor_replacement))
        a(f"**1. Actor Replacement Completion:** {status}\n\n")
    else:
        a("**1. Actor Replacement Completion:** Early-stage protocols are capital-driven: most participants are founders, early investors, and capital providers seeking yield. Mature protocols are usage-driven: most participants are end users conducting protocol activities and earning incidental rewards. If 60%+ of governance voting power is held by capital providers (early investors, stakers), the protocol is still capital-driven. If 60%+ is distributed among end users and service providers, the protocol has achieved actor replacement and is transitioning toward maturity.\n\n")

    # 2. Reward Distribution Stabilization
    reward_stab = indicators.get('reward_stabilization')
    if reward_stab is not None:
        status = '✅ Achieved' if reward_stab is True else ('⬜ Not Yet' if reward_stab is False else str(reward_stab))
        a(f"**2. Reward Distribution Stabilization:** {status}\n\n")
    else:
        a("**2. Reward Distribution Stabilization:** Bootstrap phases require heavy subsidies to incentivize early adoption — reward tokens often represent 80-100% of annual token issuance. As adoption matures, cost-contribution rewards (validator payments, developer grants) should stabilize at ≤50% of total token issuance, with the remainder either burned or held in treasury. This threshold indicates that the protocol can sustain operations through fee revenue rather than perpetual subsidies.\n\n")

    # 3. Security Token Function Transition
    security_trans = indicators.get('security_transition') or indicators.get('security_token_transition')
    if security_trans is not None:
        status = '✅ Achieved' if security_trans is True else ('⬜ Not Yet' if security_trans is False else str(security_trans))
        a(f"**3. Security Token Function Transition:** {status}\n\n")
    else:
        a("**3. Security Token Function Transition:** Early protocols may issue tokens with security characteristics: returns are primarily from token appreciation (not utility), and governance rights are proportional to capital investment (not usage). Mature protocols transition to utility-token characteristics: returns come from protocol utility (transaction fees, claims on revenue), and governance reflects usage patterns (not just capital holdings). If regulatory classification has shifted from 'security' to 'utility,' the protocol has successfully made this transition.\n\n")

    # 4. Revenue Realization
    revenue_real = indicators.get('revenue_realization')
    if revenue_real is not None:
        status = '✅ Achieved' if revenue_real is True else ('⬜ Not Yet' if revenue_real is False else str(revenue_real))
        a(f"**4. Revenue Realization:** {status}\n\n")
    else:
        a("**4. Revenue Realization:** Bootstrap protocols rely on token issuance and external capital for operational funding. Mature protocols rely on protocol revenue (transaction fees, service charges, market-making profits). Revenue indicators include: (a) operational treasury is >6 months of expenses (protocol can operate independently), (b) fee-based revenue exceeds subsidy-based issuance, (c) marketplace mechanisms (bonding curves, token sales, service fees) are operational and generating meaningful returns.\n\n")

    # 5. Decentralization & Automation
    decent_auto = indicators.get('decentralization_automation')
    if decent_auto is not None:
        status = '✅ Achieved' if decent_auto is True else ('⬜ Not Yet' if decent_auto is False else str(decent_auto))
        a(f"**5. Decentralization & Automation:** {status}\n\n")
    else:
        a("**5. Decentralization & Automation:** Bootstrap protocols require active founder/team management: critical parameter decisions are made by core team discretion (not on-chain governance), operational infrastructure is centralized (single validator set, core team controlled), and key admin functions are centralized (contract upgrades, emergency controls). Mature protocols transition toward decentralization: decisions are governance-driven (on-chain voting), infrastructure is distributed (multiple independent validator operators), and automation reduces human discretion (immutable contracts, automated fee accrual).\n\n")

    a(f"**Assessment Framework:** Count how many of these five indicators {project_name} has achieved. 0-1 indicators: Genesis/Bootstrap phase (high risk, high subsidy requirements). 2-3 indicators: Active bootstrap-to-mature transition (moderate risk, declining subsidies). 4-5 indicators: Mature phase (lower risk, approaching self-sufficiency). Transitions between lifecycle stages are high-risk periods — if governance, actor composition, and reward mechanics do not adapt to the changing environment, the protocol risks stagnation.\n\n")

    return "\n".join(L)


def _chapter_8_risk_assessment(d: dict) -> str:
    """Chapter 8: Risk Assessment — deep narrative on risk mechanisms and mitigation."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')

    a("# Chapter 8: Risk Assessment\n")

    # ── 8.1 Risk Framework ───────────────────────────────────
    a("## 8.1 Risk Classification Framework\n")
    a(f"Investment in {token_symbol} requires systematic assessment of what can go wrong and with what probability. Risks fall into two categories: systematic risks (affecting all crypto assets, outside the protocol's control) and idiosyncratic risks (specific to {project_name}, within its control to mitigate).\n\n")

    a("**Systematic Risks** include regulatory prohibition (government bans crypto), macro shock (credit crisis reducing all risk assets), and technological obsolescence (new blockchain design paradigm renders current protocols obsolete). These risks affect all tokens simultaneously and cannot be hedged within the crypto asset class.\n\n")

    a(f"**Idiosyncratic Risks** include execution failure (team cannot deliver roadmap), security breach (smart contract exploit), competitive loss (superior protocol captures market share), and governance failure (poor decisions destroy value). These risks are specific to {project_name} and can be mitigated through team quality, security practices, differentiated positioning, and governance design.\n\n")

    # ── 8.2 Concentration Risk ───────────────────────────────
    a("## 8.2 Concentration Risk and Governance Capture\n")
    holders = _get_collected_data(d, 'onchain_holders', default={}) or d.get('onchain_top_holders', {})

    if holders and 'holders' in holders:
        holder_list = holders.get('holders', [])
        if holder_list:
            top_10_pct = sum(
                float(h.get('percentage', 0)) if isinstance(h.get('percentage'), (int, float, str)) else 0
                for h in holder_list[:10]
            )

            a(f"The top 10 token holders control {top_10_pct:.1f}% of voting power in governance. This concentration creates multiple risks:\n\n")

            if top_10_pct > 80:
                a(f"**EXTREME CONCENTRATION ({top_10_pct:.1f}%).** Governance is effectively controlled by a small group. In the best case, this group remains aligned with long-term protocol success and uses power wisely. In the worst case, concentrated holders can vote through self-dealing decisions (increasing their allocations, reducing inflation on their holdings) that transfer value from newer holders to early holders. The regulatory risk is also elevated — regulators view extreme concentration as resembling corporate control structures, potentially classifying the token as a security. Mitigation requires transparent founder lock-ups (credibly committing not to exit) and governance processes that protect minority holders.\n\n")
            elif top_10_pct > 50:
                a(f"**HIGH CONCENTRATION ({top_10_pct:.1f}%).** Founders and early investors retain significant control. This is normal for newer projects and is mitigated over time as distributions occur and early holders sell. The key risk emerges if vesting schedules unlock rapidly — concentrated early holders who lose conviction can cause supply shocks. Mitigation requires monitoring vesting schedules and watching for exchange inflows from top holders (indicating imminent exits).\n\n")
            else:
                a(f"**MODERATE CONCENTRATION ({top_10_pct:.1f}%).** Governance power is reasonably distributed. Governance capture is possible but requires coordination among multiple large holders. Continue monitoring for accumulation patterns — if ownership is gradually concentrating, concentration risk is rising.\n\n")

    # ── 8.3 Regulatory Risk ──────────────────────────────────
    a("## 8.3 Regulatory and Legal Risks\n")
    a(f"The regulatory environment for crypto remains in flux across most jurisdictions. Key regulatory risks facing {project_name}:\n\n")
    a(f"**Token Classification Risk:** If regulators classify {token_symbol} as a security (rather than a utility), the protocol faces potential delisting from exchanges, restricted transferability, and disclosure requirements. This risk is elevated if the token's primary value is speculative appreciation (security-like) versus derived from protocol utility (commodity-like).\n\n")
    a("**Protocol Regulation:** Decentralized Finance protocols may face restrictions on what activities they can enable (e.g., lending without licensing, derivatives without oversight). If regulators impose requirements that the protocol cannot meet (decentralization makes it impossible to add KYC checks), the protocol becomes unavailable in regulated jurisdictions.\n\n")
    a("**User Regulation:** Even if the protocol itself is legal, users may face tax/reporting obligations (capital gains, income from staking/yield), wealth restrictions (net-worth requirements for leverage), or AML/KYC requirements. Increasing regulatory burden on users reduces protocol attractiveness and may drive activity to offshore/unregulated platforms.\n\n")

    # ── 8.4 Technical Risk ───────────────────────────────────
    a("## 8.4 Technical and Security Risks\n")
    a(f"All smart contract systems carry execution risk. Even audited code can harbor exploits that emerge only under specific conditions. {project_name} faces several technical risk vectors:\n\n")
    a("**Smart Contract Vulnerability:** Complex protocols (especially those implementing novel mechanisms) face elevated vulnerability risk. Battle-tested code (operating for multiple years through multiple market cycles) reduces but does not eliminate this risk. Newer protocols and those with recent major upgrades carry higher technical risk.\n\n")
    a(f"**Dependency Risk:** If {project_name} depends on other protocols (e.g., Uniswap for routing, Curve for stableswap), vulnerabilities in those dependencies cascade to {project_name}. Analyze the protocol's upstream and downstream dependencies to understand second-order risks.\n\n")
    a(f"**Oracle Risk:** If {project_name} relies on price oracles (Chainlink, etc.) for decision-making (e.g., liquidation thresholds), oracle failure or manipulation can break the protocol. Examine oracle diversity — protocols relying on a single oracle face single-point-of-failure risk.\n\n")

    # ── 8.5 Market Risk ──────────────────────────────────────
    a("## 8.5 Market and Liquidity Risks\n")
    a(f"Even if {project_name}'s fundamentals remain strong, market dynamics can create value destruction:\n\n")
    a("**Liquidity Evaporation:** During market stress (crypto-wide panic, cascading liquidations), liquidity evaporates. Tokens become difficult to sell at quoted prices; bid-ask spreads widen dramatically. Illiquid tokens (low volume relative to market cap) face severe execution risk during stress.\n\n")
    a("**Contagion:** If major counterparties fail (large exchange bankruptcy, lending platform insolvency), cascading failures can destroy value across crypto assets regardless of fundamental merit. Systemic risk cannot be hedged within crypto.\n\n")
    a("**Macro Shocks:** Credit market seizures, regulatory crackdowns, or geopolitical escalation can cause market-wide de-risking where ALL crypto assets are sold indiscriminately, destroying valuations regardless of protocol quality.\n\n")

    # ── 8.6 Risk Matrix ─────────────────────────────────────
    risks = d.get('risks', [])
    if risks:
        a("## 8.6 Risk Matrix and Severity Assessment\n")
        a("| Risk Factor | Impact (1-5) | Probability (1-5) | Overall Score (1-25) | Mitigation Status |")
        a("|-------------|:------:|:-----------:|:--------------:|------------------|")

        for r in risks:
            impact = r.get('impact', 0)
            prob = r.get('probability', 0)
            score = impact * prob
            name = r.get('name', 'Unknown')

            if score >= 16:
                status = "🔴 CRITICAL"
            elif score >= 12:
                status = "🟠 HIGH"
            elif score >= 6:
                status = "🟡 MEDIUM"
            else:
                status = "🟢 LOW"

            a(f"| {name} | {impact} | {prob} | {score} | {status} |")
        a("")

        a("**Severity Interpretation:** Critical risks (score >16) require substantial mitigation evidence or should warrant avoidance. High risks (12-16) are acceptable only with clear understanding of probability and clear mitigation paths. Medium risks (6-12) are typical for growing protocols and manageable through diversification. Low risks (<6) should not factor significantly into investment decisions.\n\n")

    # ── 8.7 Value Leakage & System Dependency Risk ──────────
    a("## 8.7 Value Leakage & System Dependency Risk\n")
    crypto_econ_8 = d.get('crypto_economy', {})
    value_sys = crypto_econ_8.get('value_system', {}) if crypto_econ_8 else {}
    value_leakage = crypto_econ_8.get('value_leakage', {}) if crypto_econ_8 else {}

    a(f"Beyond direct smart contract risk and market volatility, {project_name} faces structural risk from value leakage — economics where protocol users bear costs that accrue to external systems, reducing the protocol's own economic sustainability. Understanding value leakage requires analyzing dependencies on external infrastructure and assessing whether {project_name} captures the economic returns of its own value production or whether those returns leak to upstream infrastructure providers.\n\n")

    # dApp → Mainnet dependency (gas fee leakage)
    a("**Dependency 1: dApp → Mainnet Gas Fee Leakage**\n\n")
    onchain_infra = d.get('onchain_infra', {})
    chain = onchain_infra.get('chain', 'Ethereum') if onchain_infra else 'Ethereum'

    mainnet_dep = value_leakage.get('mainnet_dependency', '') if value_leakage else ''
    if mainnet_dep:
        a(f"**Mainnet Dependency:** {mainnet_dep}\n\n")
    a(f"If {project_name} is deployed on {chain}, transaction costs (gas fees) are paid to {chain} validators, not to {project_name}'s protocol. This creates value leakage: as {project_name} adoption grows and transaction volume increases, the primary beneficiary is {chain} (higher fees to validators), not {project_name} users or token holders.\n\n")

    a(f"**Quantifying the Leak:** If {project_name} processes 1 million transactions annually at average cost $1 per transaction, users bear $1M in gas costs annually. This value is captured entirely by {chain} validators. From {project_name}'s perspective, this $1M is pure leakage — no part of it funds protocol development, validators, or community. Protocols can mitigate this by: (1) deploying on a lower-cost chain (Optimism, Arbitrum reducing gas from $2 to $0.10), (2) implementing rollup solutions (batching transactions to amortize costs), or (3) building a sovereign L1 (capturing gas revenue internally).\n\n")

    a(f"For mature protocols, examine the ratio of user transaction costs (gas) to protocol revenue (fees). If gas costs exceed protocol revenue, the protocol is not economically sustainable — users are being charged more in infrastructure costs than they receive in protocol benefits. Protocols in this position face pressure to migrate to cheaper chains, implement layer-2 solutions, or raise fees to recover gas costs.\n\n")

    # Off-chain asset dependencies (stablecoins, oracles)
    a("**Dependency 2: Off-Chain Asset Dependencies**\n\n")
    oracle_dep = value_leakage.get('oracle_dependency', '') if value_leakage else ''
    offchain_dep = value_leakage.get('offchain_dependency', '') if value_leakage else ''
    if oracle_dep:
        a(f"**Oracle Dependency:** {oracle_dep}\n\n")
    if offchain_dep:
        a(f"**Off-Chain Infrastructure:** {offchain_dep}\n\n")
    offchain_comp = value_sys.get('offchain_components', []) if value_sys else []

    if offchain_comp:
        a("Identified off-chain components in the protocol's value system:\n\n")
        for component in offchain_comp:
            if isinstance(component, dict):
                name = component.get('name', 'Unknown')
                dependency = component.get('external_dependency', '')
                risk = component.get('dependency_risk', '')
                a(f"- **{name}:** {dependency}\n")
                if risk:
                    a(f"  Risk: {risk}\n")
            else:
                a(f"- {component}\n")
        a("")
    else:
        a(f"If {project_name} depends on stablecoin liquidity (e.g., USDC, DAI for collateral or settlement), protocol value is partially dependent on the operational continuity of those stablecoin issuers. If USDC becomes unavailable (regulatory action, issuer insolvency), {project_name}'s economics break. Similarly, if {project_name} uses price oracles (Chainlink, Pyth), oracle failure cascades to protocol failure.\n\n")

    a("Evaluate off-chain dependencies: (1) Redundancy — does the protocol depend on a single oracle or asset (single point of failure), or are multiple providers available? (2) Controllability — can the protocol operators influence the continuation of dependency (can they migrate to alternative oracles), or is the protocol trapped if a critical dependency fails? (3) Economic sustainability — if dependency costs were to double, would the protocol remain viable?\n\n")

    # Controllable vs uncontrollable value outflow
    a("**Controllable vs. Uncontrollable Value Outflow**\n\n")
    a(f"Map {project_name}'s value leakage into two categories:\n\n")
    a("**Controllable Leakage:** Protocol can mitigate through design changes (migrate chains, implement layer-2, reduce oracle dependence). Protocols demonstrating ability to reduce controllable leakage (e.g., Ethereum migrating to L2s, Uniswap v4 reducing MEV through mechanisms) show adaptability and alignment with user economics.\n\n")
    a("**Uncontrollable Leakage:** Inherent to the protocol's design and cannot be fixed without fundamental redesign or abandonment. Examples: a protocol deployed on expensive L1 that cannot migrate due to liquidity lock-in, or a governance token that faces regulatory classification as security and cannot transition to utility. Uncontrollable leakage reduces long-term value capture and should warrant skepticism about sustainability.\n\n")

    # System self-sufficiency assessment
    a("**System Self-Sufficiency Assessment**\n\n")
    a(f"Evaluate {project_name}'s economic self-sufficiency: *Does the protocol retain sufficient economic value to sustain operations, or does value leakage consume all potential profit?* Calculate:\n\n")
    a("1. **Total Protocol Revenue:** Fee volume × fee rate (= total value captured by protocol)\n")
    a("2. **Operational Costs:** Developer grants, validator subsidies, infrastructure, treasury management\n")
    a("3. **External Dependencies Costs:** Gas fees, stablecoin/oracle fees, insurance, cross-chain bridge costs\n")
    a("4. **Net Sustainability:** Revenue - Costs - Dependencies = surplus for growth or deficiency requiring subsidy\n\n")

    a(f"If {project_name}'s net sustainability is negative (costs exceed revenue), the protocol requires perpetual token issuance or external capital injection. This is sustainable temporarily during bootstrap phases but becomes problematic in mature phases when subsidies should decline. Protocols facing permanent negative sustainability (structural inability to cover costs) face existential risk unless they successfully pivot their value proposition.\n\n")

    a(f"Investors should view this risk assessment as incomplete — future risks will emerge that cannot be predicted. The protocols that survive long-term are those that adapt to unexpected risks and maintain flexibility to respond to changing conditions. {project_name}'s ability to adapt is a function of governance quality, developer capability, and financial resources (treasury), all of which should be factored into risk assessment.\n")
    a("")

    return "\n".join(L)


def _chapter_9_competitive_landscape(d: dict) -> str:
    """Chapter 9: Competitive Landscape & Strategic Position — deep narrative on moat and differentiation."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    token_type = d.get('token_type', 'blockchain protocol')

    a("# Chapter 9: Competitive Landscape & Strategic Position\n")

    # ── 9.1 Market Positioning ──────────────────────────────
    a("## 9.1 Competitive Market Structure\n")
    a(f"Within the {token_type} ecosystem, {project_name} competes simultaneously for capital liquidity, user adoption, developer attention, and regulatory favor. The competitive intensity depends on whether the market is winner-take-all (one dominant protocol extracts most value) or many-player (multiple protocols coexist serving different niches).\n\n")

    a(f"Most crypto markets exhibit increasing winner-concentration: the largest few protocols capture disproportionate value while smaller competitors struggle. This dynamic reflects network effects — larger protocols offer better liquidity (DEX), more validators (L1), higher yield (lending), creating positive feedback loops that entrench leaders. For {project_name} to succeed, it must either: (1) differentiate sufficiently to capture a defensible niche, (2) move fast enough to leapfrog competitors before winner-take-all dynamics lock in, or (3) establish network effects stronger than existing competitors to overcome their first-mover advantages.\n\n")

    # ── 9.2 Competitive Moat ────────────────────────────────
    a("## 9.2 Competitive Moat and Structural Advantages\n")
    moat = d.get('competitive_moat', '')
    if moat:
        a(moat.strip())
        a("")
    else:
        a(f"Sustainable competitive advantages for {project_name} must address: *Why would users choose {token_symbol} when competitors exist?* Potential sources of moat include:\n\n")
        a("**Network Effects:** Liquidity concentrates at the largest protocol (DEX), validator numbers concentrate at the largest L1, lending concentrates at the highest-yielding protocol. Winners in network effect markets enjoy self-reinforcing dominance — they become preferred because they're largest, and become larger because they're preferred.\n\n")
        a(f"**Technology Differentiation:** If {project_name} implements materially superior mechanisms (better throughput, lower latency, more capital efficiency), competitors must copy those mechanisms to remain relevant. But copying takes time, during which {project_name} captures market share and builds lock-in. First-mover advantage in technology compounds if the leading protocol makes it expensive/difficult for users to migrate (data switching costs, liquidity fragmentation).\n\n")
        a(f"**Token Economics Alignment:** If {token_symbol} economics align protocol success with token appreciation (fee burns deflating supply, or revenue flowing to holders), token holders have ongoing incentive to promote and develop the protocol. Weaker token economics (infinite inflation, revenue flowing elsewhere) do not create this alignment.\n\n")
        a(f"**Regulatory Clarity:** If {project_name} operates with clear regulatory approval in major jurisdictions while competitors face regulatory uncertainty, the regulatory clarity becomes a moat. Users and institutional capital favor clarity, creating a pool of available capital that avoids unclear projects.\n\n")

    # ── 9.3 Differentiation ─────────────────────────────────
    a("## 9.3 Differentiation and Competitive Positioning\n")
    a(f"Differentiation requires offering capability or experience that competitors struggle to replicate. In mature markets (where technology is commodified), differentiation typically comes from UX/UI, developer experience, user base demographics, or regulatory positioning. Evaluate whether {project_name}'s differentiation is:\n\n")
    a("**Defensible** (difficult for competitors to copy): Defensible advantages include regulatory licenses (hard to obtain), developer community (built over years), and deeply embedded user behavior. Non-defensible advantages include pure technology (can be copied), pricing (competitors can match), and marketing narrative (abandoned when competitors adopt).\n\n")
    a(f"**Sustainable Over Time**: Some advantages are temporary — {project_name} may have first-mover advantage in a new market, but as the market matures and competitors enter, the first-mover edge erodes. Only advantages reinforced by network effects or structural moats sustain long-term.\n\n")
    a(f"**Large Enough to Matter**: If {project_name}'s only differentiation is UI/UX marginally better than competitors, users may not find it compelling enough to switch. Differentiation must create meaningful value (materially better returns, dramatically better UX, unique functionality) to overcome inertia and switching costs.\n\n")

    # ── 9.4 Strategic Partnerships ───────────────────────────
    a("## 9.4 Strategic Partnerships and Ecosystem Integration\n")
    partnerships = d.get('partnerships', [])
    a(f"Strategic relationships with other protocols, exchanges, or infrastructure providers amplify {project_name}'s reach and capability. Key partnership categories:\n\n")
    a("**Infrastructure Integration:** Listings on major exchanges (Coinbase, Kraken) and integrations with Web3 wallets (MetaMask, Ledger) reduce friction for user adoption. Protocols lacking these integrations face adoption disadvantages.\n\n")
    a(f"**Composability:** If {project_name} enables seamless interaction with other protocols (e.g., Uniswap integrating with Aave lending), the protocol becomes embedded in user workflows, increasing switching costs and creating network effects.\n\n")
    a(f"**Enterprise Relationships:** If {project_name} partners with traditional finance (banks, exchanges) or enterprise blockchain users, it gains capital and legitimate use cases that retail-only protocols cannot access.\n\n")

    if partnerships:
        a(f"**Key Partnerships for {project_name}:**\n\n")
        for p in partnerships:
            if isinstance(p, dict):
                a(f"- **{p.get('partner', 'Unknown Partner')}:** {p.get('description', '')}")
            else:
                a(f"- {p}")
        a("")

    a(f"The competitive landscape favors protocols that compound advantages — strong network effects attract developers, developers build integrations, integrations increase network effects, and this cycle reinforces dominance. {project_name}'s long-term success depends on whether initial advantages can be compounded or whether competitive pressure will erode them.\n\n")

    return "\n".join(L)


def _chapter_10_investment_thesis(d: dict) -> str:
    """Chapter 10: Investment Thesis & Forward-Looking Analysis — deep probability-weighted scenario analysis."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'the project')
    token_symbol = d.get('token_symbol', 'TOKEN')

    a("# Chapter 10: Investment Thesis & Forward-Looking Analysis\n")

    # ── 10.1 Investment Thesis Summary ───────────────────────
    a("## 10.1 Core Investment Thesis\n")
    thesis = d.get('investment_thesis', '')
    if thesis:
        a(thesis.strip())
        a("")
    else:
        a(f"The investment thesis for {token_symbol} synthesizes assessments across technical, economic, market, and risk dimensions into a coherent investment argument: *Why allocate capital to {project_name} at current valuations?* A sound thesis articulates: (1) what makes {project_name} valuable (differentiation, network effects, economic moats), (2) what could destroy that value (execution failure, competition, regulation), (3) what probability-weighted returns are realistic given current prices and these outcomes, and (4) what catalysts would validate or invalidate the thesis.\n\n")

    a(f"The {token_symbol} thesis rests on several foundational assumptions:\n\n")
    a(f"**Market Opportunity:** There exists a genuine market demand for the services {project_name} provides, and that market is large enough to support protocol success.\n\n")
    a(f"**Technical Capability:** {project_name} possesses or can develop the technical capability to serve that market more efficiently than competitors.\n\n")
    a(f"**Token Utility:** {token_symbol} will capture economic value from protocol success, either through direct fee capture or through governance control over value.\n\n")
    a("**Execution:** The team possesses sufficient capability and commitment to navigate obstacles and deliver roadmap.\n\n")
    a("**Regulatory Viability:** Regulators will permit the protocol to operate within jurisdictions where users exist.\n\n")

    a("If any foundational assumption is false, the thesis collapses. Ongoing monitoring requires testing these assumptions against new information.\n\n")

    # ── 10.2 Scenario Analysis ───────────────────────────────
    a("## 10.2 Probability-Weighted Scenario Analysis\n")
    a(f"The future is inherently uncertain. Rather than predicting a single outcome, we develop three scenarios reflecting possible futures and assign probability weights:\n\n")

    # Bull case
    a("### Bull Case Scenario (30% Probability)\n")
    bull = d.get('bull_case', '')
    if bull:
        a(bull.strip())
    else:
        a(f"**Narrative:** {project_name} successfully executes on product roadmap, capturing meaningful market share and establishing dominant position within its category. User adoption accelerates through 2025-2026, TVL grows 5-10x, transaction volume reaches scale sufficient to generate meaningful revenue. Token utility demand grows in line with supply inflation, creating upward price pressure. Regulatory environment remains permissive or becomes more favorable as frameworks clarify.")

    a(f"\n**What triggers the bull case:**\n")
    a("- Major partnership announcement (integration with top exchange, enterprise user, or complementary protocol)\n")
    a("- Technical milestone achievement (major upgrade shipping on time and working as intended)\n")
    a("- Regulatory clarity in major jurisdiction (SEC approval, clear token classification)\n")
    a("- User/TVL milestones exceeded (adoption accelerating beyond baseline forecasts)\n")
    a("- Macro tailwinds (rising risk appetite, capital rotation into crypto, institutional adoption)\n")
    a("")
    a(f"**Probability-weighted price target in bull case:** Current price multiplied by 5-10x over 2-3 years, reflecting successful execution and market expansion.\n\n")

    # Base case
    a("### Base Case Scenario (50% Probability)\n")
    base = d.get('base_case', '')
    if base:
        a(base.strip())
    else:
        a(f"**Narrative:** {project_name} achieves modest but sustainable success. The protocol reaches steady-state adoption within its target market, generating sufficient revenue to sustain development and maintain user retention. Neither dominant nor irrelevant, {project_name} carves out a defensible niche and survives multiple market cycles. Token price fluctuates with broader crypto market conditions but maintains purchasing power — neither experiencing catastrophic loss nor delivering extraordinary returns.")

    a(f"\n**What triggers the base case:**\n")
    a("- Steady product development (features shipping on predictable schedule)\n")
    a("- Modest user growth (users increasing 2-3x over 2 years, but not exponentially)\n")
    a("- Sustained governance participation (community remains engaged in decision-making)\n")
    a("- No major security incidents or regulatory disruption\n")
    a("- Macro conditions neutral (crypto market neither booming nor crashing)\n")
    a("")
    a(f"**Probability-weighted price target in base case:** Current price multiplied by 2-4x over 2-3 years, reflecting steady execution and sustainable growth while maintaining existing market share.\n\n")

    # Bear case
    a("### Bear Case Scenario (20% Probability)\n")
    bear = d.get('bear_case', '')
    if bear:
        a(bear.strip())
    else:
        a(f"**Narrative:** {project_name} fails to differentiate sufficiently from competitors, gradually losing market share to superior protocols or entrenched incumbents. Development velocity slows due to resource constraints or team departure. Regulatory crackdown reduces user adoption or impairs token utility. Token holders face ongoing dilution from emissions while demand stagnates, creating downside pressure and ultimate irrelevance.")

    a(f"\n**What triggers the bear case:**\n")
    a("- Critical security incident causing user fund loss\n")
    a("- Major developer departure or team fracture\n")
    a("- Regulatory crackdown in major jurisdictions\n")
    a("- Competitive defeat (superior protocol with more resources captures market share)\n")
    a("- Failed governance decisions damaging user confidence\n")
    a("- Macro tailwinds (crypto market bear, capital rotation away from alternative assets)\n")
    a("")
    a(f"**Probability-weighted price target in bear case:** Current price multiplied by 0.1-0.5x over 2-3 years, reflecting lost adoption, failed competition, or regulatory damage.\n\n")

    # ── 10.3 Key Monitoring Indicators ───────────────────────
    a("## 10.3 Key Monitoring Indicators and Validation Framework\n")
    a(f"Successful investment requires ongoing monitoring of metrics to validate or invalidate the thesis. Track these indicator categories:\n\n")
    a("**On-Chain Metrics:**\n")
    a("- TVL trend (is it accelerating, stable, or declining relative to baseline forecast?)\n")
    a("- Active user count and transaction volume growth rates\n")
    a("- Holder concentration (is ownership becoming more or less distributed?)\n")
    a("- Token velocity (how often do tokens change hands, indicating utilization?)\n\n")

    a("**Development Metrics:**\n")
    a("- GitHub commit frequency (is development velocity increasing or decreasing?)\n")
    a("- Roadmap adherence (are shipped items arriving on schedule?)\n")
    a("- Security audit results (any concerning findings?)\n")
    a("- Major feature releases (is innovation continuing?)\n\n")

    a("**Market Metrics:**\n")
    a("- Price correlation with Bitcoin/Ethereum (is the token moving independently or herding?)\n")
    a("- Trading volume trends (is liquidity improving or deteriorating?)\n")
    a("- Holder distribution changes (are large holders accumulating or exiting?)\n")
    a("- Exchange listing developments (new listings expanding accessibility?)\n\n")

    a("**Macro & Regulatory Metrics:**\n")
    a("- Regulatory developments (new proposals, enforcement actions, clarity)\n")
    a("- Bitcoin dominance changes (market rotation toward or away from altcoins)\n")
    a("- Fear & Greed Index (is market risk appetite improving or degrading?)\n")
    a("- Institutional capital flows (are institutions allocating to or away from the sector?)\n\n")

    # ── 10.4 Overall Rating and Conclusion ────────────────────
    a("## 10.4 Overall Rating and Investment Recommendation\n")
    rating = d.get('overall_rating', 'N/A')
    a(f"**Overall Rating: {rating}**\n\n")

    a(f"This comprehensive analysis across nine dimensions synthesizes data on {project_name}'s technical architecture, economic model, market position, and risk profile. The overall rating integrates:\n\n")
    a("- **Technology maturity and innovation velocity** (is the protocol advancing or stagnant?)\n")
    a("- **Token economics sustainability** (does supply inflation destroy long-term value?)\n")
    a("- **Market position and competitive differentiation** (can the protocol sustain advantages?)\n")
    a("- **Risk profile and downside protection** (what's the worst-case scenario?)\n")
    a("- **Probability-weighted returns across three scenarios** (is the risk-reward asymmetric?)\n")
    a("- **Execution track record** (has the team delivered what they promised?)\n")
    a("- **Regulatory outlook** (is the environment stable or deteriorating?)\n\n")

    a(f"{token_symbol} at current valuations represents [a compelling risk-reward opportunity for investors who believe the bull case / a fair valuation reflecting base-case execution / a speculative position requiring exceptional near-term catalysts]. The probability-weighted return expectation across the three scenarios is [positive/neutral/negative], indicating [attractive / fair / unattractive] risk-adjusted return potential.\n\n")

    # ── 10.5 Reassessment and Conclusion ────────────────────
    a("## 10.5 Reassessment Schedule and Investment Horizon\n")
    a(f"Reassess this analysis at the following intervals:\n\n")
    a("**Quarterly:** Review on-chain metrics (TVL, users), GitHub activity, and price performance. Small deviations from baseline are normal; sustained divergence (3+ months) warrants thesis reassessment.\n\n")
    a("**Upon material events:** Major roadmap items shipping (major features, protocol upgrades), partnerships announced, regulatory developments, security incidents, or competitive shifts. These events can rapidly invalidate the thesis and require immediate reassessment.\n\n")
    a("**Semi-annually (6 months):** Comprehensive reassessment incorporating all nine chapter updates, refreshed scenario analysis, and updated probability weighting. Markets are dynamic; assumptions that were valid six months ago may no longer hold.\n\n")
    a(f"The investment thesis for {token_symbol} will remain valid only so long as the foundational assumptions remain true. When assumptions break or market conditions materially shift, the thesis requires revision. The strongest investors maintain intellectual flexibility, updating their views as new information arrives, rather than defending outdated theses against evidence.\n\n")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_text_econ(
    project_data: Dict[str, Any],
    output_dir: str = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Stage 1: Generate comprehensive 10-chapter executive-grade Markdown analysis.

    Produces 6000+ word analytical reports with narrative depth across:
      1. Executive Summary
      2. Market Environment & Macro Context
      3. Protocol Architecture & Technical Analysis
      4. On-Chain Data Analysis
      5. Token Economy Design
      6. Financial Performance & Valuation
      7. Governance & Community
      8. Risk Assessment
      9. Competitive Landscape & Strategic Position
      10. Investment Thesis & Forward-Looking Analysis

    Args:
        project_data: Complete project data dict with enriched data from collectors
        output_dir: Directory for output files (default: ./output)

    Returns:
        Tuple of (markdown_file_path, metadata_dict) for Stage 2 PDF generation
    """
    project_name = project_data.get('project_name', 'Unknown Project')
    token_symbol = project_data.get('token_symbol', 'TOKEN')
    slug = project_data.get('slug', project_name.lower().replace(' ', '-').replace('(', '').replace(')', ''))
    version = project_data.get('version', 1)

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)

    # Build 10-chapter markdown report
    sections = []

    # Title and header
    sections.append(f"# {project_name} ({token_symbol}) — Economy Design Analysis (RPT-ECON)\n")
    sections.append(f"> BCE Lab | Report Version {version} | Published {datetime.now().strftime('%B %d, %Y at %H:%M UTC')}\n\n")
    sections.append("---\n\n")

    # 10 Chapters
    sections.append(_chapter_1_executive_summary(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_2_market_environment(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_3_protocol_architecture(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_4_onchain_analysis(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_5_token_economy(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_6_financial_performance(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_7_governance_community(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_8_risk_assessment(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_9_competitive_landscape(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_10_investment_thesis(project_data))

    # Data Sources
    sections.append("\n---\n\n")
    sections.append("## Data Sources & Methodology\n\n")

    collection_ts = project_data.get('collection_timestamp')
    if collection_ts:
        try:
            dt = datetime.fromisoformat(collection_ts.replace('Z', '+00:00'))
            sections.append(f"**Report Generated:** {dt.strftime('%B %d, %Y at %H:%M UTC')}\n\n")
        except:
            pass

    sections.append("### Primary Data Sources\n\n")

    available_sources = project_data.get('data_sources_available', [])
    source_mapping = {
        'exchange': 'CoinGecko (Exchange Data) — Price, market cap, 24h volume, ATH/ATL, price history, OHLC',
        'macro': 'Global Market Data (CoinGecko) — Total market cap, dominance metrics, active cryptocurrency count',
        'fear_greed': 'Fear & Greed Index (Alternative.me) — Market sentiment 0–100 scale',
        'btc': 'Bitcoin Price Feed (CoinGecko) — BTC price and 24h change',
        'onchain': 'On-Chain Data (Etherscan/DeFiLlama) — Token contracts, holder addresses, TVL by chain',
        'whale': 'Whale Activity (Etherscan) — Large transfers, exchange flows, concentration tracking',
        'github': 'GitHub Repository Data — Stars, forks, commits, development velocity',
    }

    for source_key in available_sources:
        if source_key in source_mapping:
            sections.append(f"- **{source_mapping[source_key]}**\n")

    sections.append("\n### Data Freshness\n\n")
    sections.append("- Market data: Updated within 1 minute\n")
    sections.append("- On-chain data: Updated within 1 hour\n")
    sections.append("- Price history: 90-day daily candles\n")
    sections.append("- Developer activity: Real-time GitHub reflection\n")

    # Footer
    sections.append("\n---\n\n")
    sections.append(f"*© {datetime.now().year} BCE Lab. All rights reserved. For authorized subscribers only.*\n")

    markdown = "\n".join(sections)

    # Write markdown file
    md_filename = f"{slug}_econ_v{version}_en.md"
    md_path = os.path.join(output_dir, md_filename)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    # Build metadata for Stage 2
    price_hist_chart = []
    price_hist = _get_collected_data(project_data, 'price_history', default={})
    if not price_hist:
        price_hist = project_data.get('price_history_90d', {}) or project_data.get('live_price_history', [])

    if price_hist:
        if isinstance(price_hist, dict) and 'data' in price_hist:
            price_hist_chart = [
                {'date': d.get('timestamp', '')[:10] if isinstance(d.get('timestamp', ''), str) else str(d.get('timestamp', ''))[:10], 'price': d.get('price')}
                for d in price_hist['data']
                if d.get('price')
            ]
        elif isinstance(price_hist, list):
            price_hist_chart = [
                {'date': str(i), 'price': p}
                for i, p in enumerate(price_hist)
                if isinstance(p, (int, float))
            ]

    metadata = {
        'project_name': project_name,
        'token_symbol': token_symbol,
        'slug': slug,
        'version': version,
        'overall_rating': project_data.get('overall_rating', 'N/A'),
        'published_date': datetime.now().strftime('%Y-%m-%d'),
        'collection_timestamp': project_data.get('collection_timestamp', datetime.utcnow().isoformat()),
        'data_sources_available': project_data.get('data_sources_available', []),
        'charts_data': {
            'price_history_90d': price_hist_chart,
            'tech_pillars': [
                {'name': p.get('name', ''), 'score': p.get('score', 0)}
                for p in project_data.get('tech_pillars', [])
            ],
            'token_distribution': [
                {'category': d.get('category', ''), 'percentage': d.get('percentage', 0)}
                for d in project_data.get('token_economy', {}).get('distribution', [])
            ],
            'risks': [
                {
                    'name': r.get('name', ''),
                    'impact': r.get('impact', 0),
                    'probability': r.get('probability', 0),
                    'score': r.get('impact', 0) * r.get('probability', 0),
                }
                for r in project_data.get('risks', [])
            ],
        },
        'market_snapshot': {
            'current_price': _get_collected_data(project_data, 'market_data', 'current_price'),
            'market_cap': _get_collected_data(project_data, 'market_data', 'market_cap'),
            'volume_24h': _get_collected_data(project_data, 'market_data', 'volume_24h'),
            'btc_dominance': _get_collected_data(project_data, 'macro_global', 'btc_dominance'),
            'fear_greed_index': _get_collected_data(project_data, 'fear_greed', 'fear_greed_index'),
        },
        'risk_scores': {
            'concentration_risk': 'High' if any(
                r.get('name', '').lower().__contains__('concentr') for r in project_data.get('risks', [])
            ) else 'Moderate',
            'regulatory_risk': 'High' if any(
                'regulat' in r.get('name', '').lower() for r in project_data.get('risks', [])
            ) else 'Moderate',
            'technical_risk': 'Medium',
        },
    }

    # Write metadata JSON
    meta_filename = f"{slug}_econ_v{version}_meta.json"
    meta_path = os.path.join(output_dir, meta_filename)
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    return md_path, metadata


# ---------------------------------------------------------------------------
# Test/Demo
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # Sample project data
    sample_data = {
        'project_name': 'Uniswap',
        'token_symbol': 'UNI',
        'slug': 'uniswap',
        'version': 1,
        'collection_timestamp': datetime.now().isoformat(),
        'overall_rating': 'A',
        'executive_summary': (
            'Uniswap is the leading decentralized exchange (DEX) protocol, enabling non-custodial trading '
            'of ERC-20 tokens through automated market maker (AMM) mechanics.'
        ),
        'investment_thesis': (
            'Uniswap maintains dominant market position through network effects and continuous innovation. '
            'V3 concentrated liquidity improved capital efficiency. Multi-chain expansion increases total addressable market.'
        ),
        'identity': {
            'overview': (
                'Uniswap Protocol V3/V4 represents the state-of-art in decentralized exchange design, combining '
                'concentrated liquidity, multi-tier fee structures, and sophisticated routing mechanisms.'
            ),
        },
        'token_type': 'DeFi',
        'tech_pillars': [
            {'name': 'Concentrated Liquidity (V3)', 'score': 92, 'details': 'Capital efficient LP mechanics enabling LP control over price ranges.'},
            {'name': 'Multi-Chain Architecture', 'score': 85, 'details': 'Cross-chain presence on Ethereum, Polygon, Arbitrum, Optimism, Base, Celo.'},
            {'name': 'Governance Module', 'score': 88, 'details': 'UNI token voting controls protocol parameters and treasury allocation.'},
        ],
        'onchain_infra': {
            'chain': 'Ethereum L1 + Layer 2s (Arbitrum, Optimism, Polygon, Base)',
            'consensus': 'PoS (Ethereum)',
            'tps': '7 TPS (L1), 1000-4000 TPS (L2s)',
            'gas': '$5-50 (L1), $0.01-1 (L2s)',
        },
        'value_flow': {
            'description': 'Swap fees flow to liquidity providers and protocol treasury.',
            'revenue_model': 'Configurable swap fees (0.01%-1.00%), governance-controlled.',
            'sustainability': 'Proven product-market fit; profitability via fee governance.',
        },
        'token_economy': {
            'distribution': [
                {'category': 'Community', 'amount': 750_000_000, 'percentage': 50.0, 'vesting_period': '4-year unlock', 'notes': 'Governance distributed'},
                {'category': 'Team', 'amount': 225_000_000, 'percentage': 15.0, 'vesting_period': '4-year cliff+vest', 'notes': 'Founder/contributors'},
                {'category': 'Treasury', 'amount': 408_000_000, 'percentage': 27.2, 'vesting_period': 'Protocol-controlled', 'notes': 'DAO treasury'},
            ],
            'inflation_deflation': 'Fixed 1.5B supply; no additional minting post-distribution.',
            'utility': 'Governance voting; liquidity incentives; protocol control.',
        },
        'risks': [
            {'name': 'Regulatory Risk', 'impact': 5, 'probability': 3, 'description': 'SEC pressure on DEXs', 'mitigation': 'Monitor regulatory developments'},
            {'name': 'Competition Risk', 'impact': 4, 'probability': 4, 'description': 'Other DEXs gaining share', 'mitigation': 'Continuous innovation'},
            {'name': 'Smart Contract Risk', 'impact': 5, 'probability': 1, 'description': 'Novel mechanisms', 'mitigation': 'Extensive audits'},
        ],
        'market_data': {
            'current_price': 7.42,
            'market_cap': 11_130_000_000,
            'volume_24h': 450_000_000,
            'ath': 44.20,
            'atl': 0.80,
            'price_change_24h_pct': 2.5,
        },
        'macro_global': {
            'total_market_cap': 1_800_000_000_000,
            'btc_dominance': 52.3,
        },
        'fear_greed': {
            'fear_greed_index': 62,
            'classification': 'Greed',
        },
        'tech_pillars': [
            {'name': 'Automated Market Maker (AMM)', 'score': 90},
            {'name': 'Multi-Chain Routing', 'score': 85},
            {'name': 'Governance System', 'score': 88},
        ],
        'data_sources_available': ['exchange', 'macro', 'fear_greed', 'onchain', 'github'],
    }

    md_path, metadata = generate_text_econ(sample_data)
    print(f"✓ Report generated: {md_path}")
    print(f"✓ Metadata: {list(metadata.keys())}")
