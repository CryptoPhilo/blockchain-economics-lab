---
title: "Blockchain Forensic Risk Analysis (FOR) Report"
date: 
author: "Blockchain Economics Lab"
version: "1.0"
slide_data:
  risk_level: "medium"  # low, medium, high, critical
  trigger_reason: "Anomalous market activity detected"
  manipulation_scores:
    - name: "Volume Manipulation"
      score: 0  # 0-100
    - name: "Price Manipulation"
      score: 0
    - name: "Insider Activity"
      score: 0
    - name: "Wash Trading"
      score: 0
  market_data:
    price: 0
    price_change_24h: 0
    volume_24h: 0
    market_cap: 0
    volume_to_market_cap_ratio: 0
  onchain_data:
    whale_concentration: 0  # % held by top 10 addresses
    team_wallet_flows: "unknown"
    exchange_inflows: 0  # % of daily volume
    large_transfer_count: 0
  technical_analysis:
    trend: "neutral"  # bullish, bearish, neutral
    support_level: 0
    resistance_level: 0
    patterns: []
  risk_indicators:
    - name: "Extreme Volume Spike"
      status: "inactive"
    - name: "Whale Accumulation"
      status: "inactive"
    - name: "Exchange Deposit Surge"
      status: "inactive"
    - name: "Insider Wallet Movement"
      status: "inactive"
  recommendations:
    - action: "Monitor price action"
      priority: "low"
      timeline: "ongoing"
  monitoring_checklist:
    - "Hourly price and volume monitoring"
    - "Daily whale movement tracking"
    - "Daily exchange flow analysis"
    - "Real-time alert setup for key metrics"
---

# Blockchain Forensic Risk Analysis (FOR) Report

**Project/Asset:** [Project Name / Token Symbol]
**Analysis Date:** [Date]
**Analysis Period:** [Start Date] - [End Date]
**Analyst:** [Analyst Name]
**Risk Level:** `[SLIDE_DATA.risk_level]`

---

## CHAPTER 1: Executive Summary & Forensic Alert Classification

### 1.1 Forensic Alert Summary

Provide immediate assessment of detected anomalies and classified risk level. Clearly communicate primary trigger factors and recommended immediate actions for stakeholders and traders.

**Risk Classification:**
- **Overall Risk Level:** `[SLIDE_DATA.risk_level]` (LOW / MEDIUM / HIGH / CRITICAL)
- **Trigger Reason:** `[SLIDE_DATA.trigger_reason]`
- **Alert Type:** [Price/Volume/Liquidity/Manipulation/Insider]
- **Time to Escalation:** [Immediate/24 hours/1 week]

**Key Alert Indicators:**
- Manipulation Risk Score: [X/100]
- Market Distress Indicator: [X/100]
- Insider Activity Probability: [X%]
- Recommended Action: [HOLD/CAUTION/EXIT/INVESTIGATE]

### 1.2 Forensic Analysis Scope & Methodology

Define the scope of forensic analysis, including data sources, timeframe, and analytical frameworks employed. Outline forensic investigation principles applied.

**Analysis Methodology:**
- On-Chain Analysis: [Address clustering, transaction tracing]
- Market Microstructure: [Order flow, volume distribution]
- Sentiment Analysis: [Social sentiment, exchange commentary]
- Network Topology: [Whale movements, fund flows]

**Data Sources:**
- On-Chain: [Blockchain explorer, node data]
- Market: [Exchange APIs, order book snapshots]
- Sentiment: [Social media monitoring, news feeds]
- Technical: [OHLCV data, derivatives positions]

### 1.3 Critical Findings & Immediate Risks

Highlight most critical discoveries with direct impact on investment/trading decisions. Include probability assessment and recommended immediate countermeasures.

| Finding | Severity | Probability | Immediate Risk | Status |
|---------|----------|-------------|-----------------|--------|
| [Anomaly 1] | High | [X%] | [Impact] | [Active] |
| [Anomaly 2] | Medium | [X%] | [Impact] | [Active] |

---

## CHAPTER 2: Macro & Sector Context

### 2.1 Macro Market Conditions

Assess broader market environment including Bitcoin/Ethereum price action, sector sentiment, and macro economic indicators affecting asset valuations.

**Macro Environment:**
- **BTC Price:** [Current / 7d change / 30d trend]
- **ETH Price:** [Current / 7d change / 30d trend]
- **Market Cap (Top 10):** [Total / % change]
- **Dominance Shift:** [BTC %] / [ETH %]
- **Volatility Index:** [VIX equivalent / Crypto Vol Index]

**Macro Risk Factors:**
- Federal Reserve Policy: [Impact assessment]
- Traditional Markets: [Equity/Bond market correlation]
- Geopolitical Events: [Relevant incidents, contagion risk]

### 2.2 Sector Positioning & Category Analysis

Position the analyzed asset within its sector category. Assess relative strength vs. peer assets and category-level anomalies.

**Sector Analysis:**
- **Category:** [DeFi / Layer 1 / Layer 2 / Stablecoin / etc.]
- **Category Leaders:** [Top 3 by market cap in category]
- **Peer Comparison:** [Asset vs. category average performance]
- **Sector Momentum:** [Positive/Negative/Neutral]

**Category-Level Anomalies:**
- [Anomaly 1 with implications]
- [Anomaly 2 with implications]

### 2.3 Cross-Asset Correlation & Contagion Risk

Analyze correlation with other assets. Identify potential contagion vectors from other platforms/protocols and systemic risk exposure.

| Asset | 7d Correlation | 30d Correlation | Contagion Risk |
|-------|-----------------|-----------------|-----------------|
| Bitcoin | [X%] | [X%] | [Low/Med/High] |
| Ethereum | [X%] | [X%] | [Low/Med/High] |
| Peer Asset 1 | [X%] | [X%] | [Low/Med/High] |
| Peer Asset 2 | [X%] | [X%] | [Low/Med/High] |

---

## CHAPTER 3: Technical Analysis & Chart Forensics

### 3.1 Price Action Analysis

Conduct detailed technical analysis of price movements including trend identification, support/resistance, and pattern formation.

**Price Analysis:**

| Metric | 24h | 7d | 30d | 90d | 1y |
|--------|-----|-----|-----|-----|-----|
| Current Price | $[X] | - | - | - | - |
| Change % | [X%] | [X%] | [X%] | [X%] | [X%] |
| High | $[X] | $[X] | $[X] | $[X] | $[X] |
| Low | $[X] | $[X] | $[X] | $[X] | $[X] |

**Technical Structure:**
- **Trend:** `[SLIDE_DATA.technical_analysis.trend]` (BULLISH / BEARISH / NEUTRAL)
- **Key Support:** `[SLIDE_DATA.technical_analysis.support_level]`
- **Key Resistance:** `[SLIDE_DATA.technical_analysis.resistance_level]`
- **Moving Averages:** [20-day, 50-day, 200-day crossover status]

### 3.2 Pattern Recognition & Chart Forensics

Identify significant chart patterns including head-and-shoulders, triangles, flags, or other formations that may indicate manipulation or genuine market movement.

**Identified Patterns:**
- [Pattern 1: Formation type, probability of breakout direction]
- [Pattern 2: Formation type, probability of breakout direction]
- [Pattern 3: Formation type, probability of breakout direction]

**Pattern Forensics:**
- Formation legitimacy assessment
- Natural vs. artificial pattern probability
- Breakout probability and projected targets

### 3.3 Volatility & Risk Profile

Analyze volatility metrics and drawdown history. Assess whether current volatility is within normal ranges or indicative of manipulation.

**Volatility Metrics:**
- **30-day Volatility:** [X%]
- **Historical Volatility Range:** [Low X%, High Y%]
- **Current vs. Historical:** [Above/Below average]
- **Volatility Trend:** [Increasing/Decreasing/Stable]
- **Max Drawdown (90d):** [X%]
- **Sharpe Ratio:** [X]

---

## CHAPTER 4: Volume Forensics & Anomaly Detection

### 4.1 Volume Pattern Analysis

Examine trading volume patterns including distribution across exchanges, time-of-day analysis, and volume-price divergences.

**Volume Metrics:**

| Exchange | 24h Vol | % of Total | VWAP Deviation | Liquidity Score |
|----------|---------|------------|-----------------|-----------------|
| [Exchange 1] | $[X]M | [X%] | [X%] | [X/100] |
| [Exchange 2] | $[X]M | [X%] | [X%] | [X/100] |
| [Exchange 3] | $[X]M | [X%] | [X%] | [X/100] |
| **Total** | **$[X]M** | **100%** | - | - |

**Volume Distribution Analysis:**
- **Concentration Ratio:** [Top exchange % of volume]
- **Volume Weighted Avg Price (VWAP):** $[X]
- **Current Price vs. VWAP:** [X% deviation]

### 4.2 Anomaly Detection: Spike Analysis

Identify and classify volume/price spikes. Determine whether spikes correspond to organic news, coordinated trading, or artificial manipulation.

**Recent Anomalies:**

| Date | Spike Type | Size | Duration | Cause Assessment | Legitimacy |
|------|-----------|------|----------|------------------|-----------|
| [Date] | Volume | [X]% | [Xmin] | [News/Coordinated/Artificial] | [X%] |
| [Date] | Price | [X]% | [Xmin] | [News/Coordinated/Artificial] | [X%] |

**Spike Legitimacy Scoring:**
- Spike Legitimacy: [X%] (natural event vs. manipulation)
- Supporting Events: [News, partnerships, regulatory action]
- Contradiction Signals: [Indicators suggesting artificial movement]

### 4.3 Wash Trading & Circular Volume Detection

Analyze transaction patterns for evidence of wash trading, round-tripping, or artificial volume generation. Cross-reference exchange data for circular fund flows.

**Wash Trading Indicators:**
- **Circular Volume (24h):** [X% of reported volume]
- **Same-Size Order Patterns:** [X suspicious patterns detected]
- **Automated Trading Signature:** [Yes/No/Uncertain]
- **Likely Wash Volume:** [X% of daily volume]

---

## CHAPTER 5: Derivatives & Supply-Side Pressure

### 5.1 Futures Market Analysis

Examine futures markets on major exchanges including open interest, funding rates, and leverage positions.

**Futures Overview:**

| Exchange | Open Interest | Funding Rate | Long/Short Ratio | Liquidation Risk |
|----------|---------------|--------------|-----------------|------------------|
| [Exchange 1] | $[X]M | [X%] | [X.XX] | [Low/Med/High] |
| [Exchange 2] | $[X]M | [X%] | [X.XX] | [Low/Med/High] |
| **Total** | **$[X]M** | **Avg: [X%]** | **Avg: [X.XX]** | - |

**Funding Rate Forensics:**
- **Current Rate:** [X%] per 8h
- **Historical Average:** [X%]
- **Rate Trend:** [Increasing/Decreasing/Stable]
- **Liquidation Level:** Price target where cascading liquidations likely

### 5.2 Options Market & Implied Volatility

Analyze options market data including implied volatility skew, put/call ratios, and large option position accumulation.

**Options Market:**
- **Implied Volatility:** [X%]
- **Put/Call Ratio:** [X] (above/below neutral)
- **Skew Direction:** [Bullish/Bearish/Neutral]
- **Largest Positions:** [Expiry, strike, side, notional value]

### 5.3 Supply-Side Pressure & Exchange Inventory

Track exchange inflows/outflows and custodial holding changes. Assess selling pressure and inventory depletion indicators.

**Supply Analysis:**

| Metric | 7d Change | 30d Change | 90d Trend |
|--------|-----------|------------|-----------|
| Exchange Balance | [X%] | [X%] | [Increasing/Decreasing] |
| Staking Balance | [X%] | [X%] | [Increasing/Decreasing] |
| Custodial Holdings | [X%] | [X%] | [Increasing/Decreasing] |
| Estimated Sell Pressure | [X% daily] | [X% daily] | [Trend] |

---

## CHAPTER 6: On-Chain Intelligence & Wallet Forensics

### 6.1 Whale Activity & Concentration Analysis

Track large holder movements, accumulation/distribution patterns, and whale wallet behaviors. Assess market concentration risk.

**Whale Metrics:**
- **Top 10 Holders:** `[SLIDE_DATA.onchain_data.whale_concentration]`% of supply
- **Top 100 Holders:** [X]% of supply
- **Gini Coefficient:** [X] (concentration measure)
- **Centralization Risk:** [Low/Medium/High]

**Recent Whale Movements:**

| Address Type | 24h Volume | Direction | Size | Implication |
|--------------|-----------|-----------|------|------------|
| Whale 1 | $[X]M | In/Out | [X tokens] | [Intent assessment] |
| Whale 2 | $[X]M | In/Out | [X tokens] | [Intent assessment] |
| Whale 3 | $[X]M | In/Out | [X tokens] | [Intent assessment] |

### 6.2 Team & Insider Wallet Tracking

Monitor team member and founder wallets. Identify insider selling/buying signals and token vesting schedules.

**Team Wallet Activity:**

| Wallet ID | Owner/Role | Balance | 30d Change | Status | Signal |
|-----------|-----------|---------|-----------|--------|--------|
| [Address] | [Founder/Team] | [X tokens] | [+/-X%] | [Active] | [Accumulating/Distributing] |
| [Address] | [Founder/Team] | [X tokens] | [+/-X%] | [Active] | [Accumulating/Distributing] |

**Insider Trading Signals:**
- **Team Selling:** `[SLIDE_DATA.onchain_data.team_wallet_flows]`
- **Vesting Schedule Impact:** [% of supply unlocking in next 90d]
- **Insider Confidence Indicator:** [Neutral/Positive/Negative]

### 6.3 Exchange Flow Analysis & Deposit/Withdrawal Patterns

Monitor exchange inflows/outflows to predict selling/buying pressure. Identify large wallet movements targeting exchanges.

**Exchange Flow Data:**

| Exchange | Inflow 24h | Outflow 24h | Net Flow | Trend |
|----------|-----------|------------|----------|-------|
| [Exchange 1] | [X tokens] | [X tokens] | [X tokens] | [In/Out/Neutral] |
| [Exchange 2] | [X tokens] | [X tokens] | [X tokens] | [In/Out/Neutral] |
| **Total** | **[X tokens]** | **[X tokens]** | **[X tokens]** | **[Direction]** |

**Flow Interpretation:**
- **Exchange Inflow %:** `[SLIDE_DATA.onchain_data.exchange_inflows]`% of daily volume
- **Deposit Destination:** [Exchange names with large inflows]
- **Selling Pressure:** [Estimated %/day]
- **Market Impact Timeline:** [Hours/Days]

---

## CHAPTER 7: Market Manipulation Detection

### 7.1 Manipulation Scoring Framework

Apply comprehensive framework to detect various manipulation schemes. Score each manipulation vector on 0-100 scale.

**Manipulation Vectors & Scores:**

| Manipulation Type | Score | Confidence | Evidence |
|------------------|-------|-----------|----------|
| Volume Manipulation | `[SLIDE_DATA.manipulation_scores[0].score]` | [X%] | [Evidence] |
| Price Manipulation | `[SLIDE_DATA.manipulation_scores[1].score]` | [X%] | [Evidence] |
| Insider Activity | `[SLIDE_DATA.manipulation_scores[2].score]` | [X%] | [Evidence] |
| Wash Trading | `[SLIDE_DATA.manipulation_scores[3].score]` | [X%] | [Evidence] |

**Aggregate Manipulation Risk Score:** [X/100] - [Low/Medium/High/Critical]

### 7.2 Pump & Dump Pattern Detection

Analyze price movement patterns for classic pump-and-dump signatures including coordinated buying, volume acceleration, and sudden sell-offs.

**Pump Indicators:**
- **Price Acceleration:** [X% in Xhours]
- **Volume Concentration:** [X% of volume in Y% of time]
- **Coordination Signals:** [Bot signatures, aligned orders]
- **Dump Risk:** [Probability of reversal in next 24h]

**Pattern Assessment:**
- Legitimate Catalyst: [Yes/No]
- Artificial Inflation Probability: [X%]
- Collapse Risk Timeline: [Hours/Days]

### 7.3 Spoofing, Layering & Order Book Manipulation

Examine order book dynamics for fake order placement, order layering, and spoofing patterns that artificially move prices.

**Order Book Forensics:**

| Level | Large Orders | Behavior | Intent Assessment |
|-------|--------------|----------|------------------|
| Support | [X orders] | [Pattern] | [Potential spoofing/support] |
| Resistance | [X orders] | [Pattern] | [Potential spoofing/resistance] |

**Spoofing Signals:**
- **Fake Orders (24h):** [X large orders appearing/disappearing]
- **Order Layering:** [Evidence of coordinated order stacking]
- **Blinking Orders:** [Orders cancelled without execution]

---

## CHAPTER 8: Information Asymmetry & Insider Activity

### 8.1 Unusual Market Behavior Before News Events

Identify abnormal trading patterns preceding major announcements, partnerships, or regulatory developments. Assess probability of insider information leakage.

**Pre-Event Analysis:**

| Event | Date | Pre-Event Anomalies | Probability of Advance Knowledge | Evidence |
|-------|------|-------------------|----------------------------------|----------|
| [News 1] | [Date] | [Volume/Price spike] | [X%] | [Details] |
| [News 2] | [Date] | [Volume/Price spike] | [X%] | [Details] |

**Insider Information Risk:**
- **Information Leakage Probability:** [X%]
- **Unfair Advantage Likely:** [Yes/No]
- **Regulatory Concern:** [Low/Medium/High]

### 8.2 Unusual Wallet Activation Patterns

Monitor dormant wallets and exchange accounts for sudden reactivation suggesting insider awareness or preparation for announcements.

**Suspicious Account Activity:**

| Account Type | Reactivations (7d) | Reason | Risk Assessment |
|--------------|-------------------|--------|-----------------|
| Old Whale Wallets | [X] | [Catalyst] | [Low/Med/High] |
| Team Wallets | [X] | [Catalyst] | [Low/Med/High] |
| Exchange Reserves | [X] | [Catalyst] | [Low/Med/High] |

### 8.3 Correlation with Team Communications & Media Coverage

Cross-reference market movements with team announcements, social media activity, and media coverage timing. Identify suspicious temporal relationships.

**Communication Timeline Analysis:**
- **Announcement Date:** [Date]
- **Price Movement:** [X% in Y hours]
- **Advance Movement:** [Yes/No] [How many hours before announcement]
- **Publicity Lag:** [Hours between announcement and price response]

---

## CHAPTER 9: Risk Synthesis & Threat Matrix

### 9.1 Risk Score Aggregation & Weighting

Synthesize individual risk assessments into comprehensive risk matrix. Weight factors based on market impact and statistical significance.

**Risk Component Weighting:**

| Risk Category | Weight | Individual Score | Weighted Score |
|---------------|--------|------------------|-----------------|
| Technical Risk | 20% | [X/100] | [X] |
| Manipulation Risk | 25% | [X/100] | [X] |
| Liquidity Risk | 15% | [X/100] | [X] |
| Operational Risk | 20% | [X/100] | [X] |
| Regulatory Risk | 20% | [X/100] | [X] |
| **TOTAL RISK SCORE** | **100%** | - | **[X/100]** |

**Overall Risk Level:** `[SLIDE_DATA.risk_level]`

### 9.2 Threat Matrix & Scenario Analysis

Develop threat matrix assessing probability and impact of various risk scenarios. Model cascading failure scenarios and contagion pathways.

**Risk Scenarios:**

| Scenario | Probability | Max Impact | Timeline | Mitigation |
|----------|------------|-----------|----------|-----------|
| Flash Crash | [X%] | [-X%] | [Minutes] | [Action] |
| Regulatory Action | [X%] | [-X%] | [Weeks] | [Action] |
| Exchange Hack | [X%] | [-X%] | [Immediate] | [Action] |
| Liquidity Crisis | [X%] | [-X%] | [Hours] | [Action] |

### 9.3 Probability-Weighted Risk Outlook

Calculate probability-weighted outcomes across multiple scenarios. Provide trading decision framework based on risk/reward assessment.

**Weighted Risk Outlook (7-day):**
- **Downside Risk:** [X%] probability of [X%] decline
- **Upside Potential:** [X%] probability of [X%] advance
- **Expected Value:** [X%] (probability-weighted return)
- **Risk/Reward Ratio:** [X:1]

---

## CHAPTER 10: Conclusion, Strategy & Monitoring Framework

### 10.1 Final Risk Assessment & Recommendation

Provide definitive risk assessment and clear trading/holding recommendations with supporting rationale.

**Final Assessment:**

**Risk Level:** `[SLIDE_DATA.risk_level]` (LOW / MEDIUM / HIGH / CRITICAL)

**Key Conclusion:** [2-3 sentence synthesis of key findings and overall assessment]

**Recommendation:** [ACCUMULATE / HOLD / CAUTION / REDUCE / EXIT]
- **For Long-Term Holders:** [Action]
- **For Active Traders:** [Action]
- **For Risk-Averse Investors:** [Action]

### 10.2 Strategic Recommendations by Risk Profile

Tailor recommendations to different investor archetypes and risk tolerances.

**Conservative Strategy (Risk-Averse):**
- Position sizing: [X% of portfolio maximum]
- Entry strategy: [Dollar-cost average vs. direct entry]
- Exit triggers: [Price targets, time stops]
- Hedging recommendations: [Derivatives strategies]

**Moderate Strategy (Balanced):**
- Position sizing: [X% of portfolio maximum]
- Entry strategy: [Phased or direct entry]
- Exit triggers: [Technical + fundamental targets]
- Rebalancing: [Frequency and thresholds]

**Aggressive Strategy (Growth-Oriented):**
- Position sizing: [X% of portfolio maximum]
- Leverage considerations: [Recommended/Not recommended]
- Momentum strategy: [Entry/exit rules]
- Concentration risk: [Assessment]

### 10.3 Real-Time Monitoring Framework

Establish ongoing monitoring checklist and alert thresholds for continued risk management.

**Real-Time Monitoring Checklist:**
`[SLIDE_DATA.monitoring_checklist]`

**Alert Thresholds:**

| Metric | Normal Range | Caution Level | Alert Level | Action |
|--------|--------------|---------------|------------|--------|
| Price Change | [±X%] | [±X%] | [>±X%] | [Review analysis] |
| Volume Spike | [X×avg] | [X× avg] | [>X× avg] | [Escalate monitoring] |
| Exchange Inflow | [<X%] | [X-Y%] | [>Y%] | [Adjust position] |
| Whale Movement | [<X coins] | [X-Y coins] | [>Y coins] | [Emergency review] |

### 10.4 Next Review Schedule & Trigger Points

Establish schedule for follow-up forensic analysis and define triggers for accelerated reassessment.

**Scheduled Reviews:**
- **Next Regular Review:** [Date + 7 days / 30 days]
- **Deep Dive Analysis:** [Trigger conditions]
- **Emergency Reassessment:** [Risk escalation thresholds]

**Trigger Points for Immediate Reanalysis:**
1. Price moves >X% in 24 hours
2. Volume increases >X times normal level
3. Major exchange inflow/outflow >$X million
4. Regulatory announcement or adverse news
5. Whale movement >X tokens in single transaction

---

**Document Metadata**
- Analysis Type: Blockchain Forensic Risk Analysis (FOR)
- Methodology Version: 1.0
- Data Collection Period: [Period]
- Confidence Level: [X%]
- Analysis Date: [Date]
- Next Review: [Date]
- Classification: [Public / Confidential]
