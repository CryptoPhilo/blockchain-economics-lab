"""
Forensic (RPT-FOR) Report Generator for BCE Lab Report Pipeline
Generates professional PDF reports with RED WARNING theme for market risk alerts.
Implements STR-002 §1.3 forensic analysis report specifications.
"""

# ╔══════════════════════════════════════════════════════════╗
# ║  DEPRECATED — DO NOT USE                                ║
# ║  Use gen_text_for.py + gen_pdf_for.py instead           ║
# ║  This file is kept for reference only.                  ║
# ╚══════════════════════════════════════════════════════════╝

import io
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.dates import DateFormatter
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image, KeepTogether
)
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# Import from local modules
from pdf_base import (
    make_styles, section_header, build_table, draw_cover_forensic,
    make_header_footer, add_disclaimer, create_doc, C, USABLE_W
)
from config import REPORT_TYPES, report_filename, COLORS


def generate_for_report(project_data: Dict[str, Any], lang: str, output_path: str) -> str:
    """
    Generate a professional Forensic (RPT-FOR) PDF report.

    Args:
        project_data: Dictionary containing project and analysis data
        lang: Language code ('en', 'ko', etc.)
        output_path: Directory path for output file

    Returns:
        Full path to generated PDF file

    Project data keys:
        - project_name, token_symbol, slug, version
        - risk_level ('critical'/'warning'/'watch')
        - trigger_reason (str)
        - alert_summary (dict with event_description, timeline, immediate_risk)
        - insider_activity (dict with wallets, shell_routing, mixer_usage)
        - whale_behavior (dict with top_whales, exchange_flow_summary)
        - market_microstructure (dict with candlestick_analysis, volume_anomaly,
          orderbook_analysis, dead_cat_bounce)
        - external_factors (dict with news, regulatory, macro_impact, similar_cases)
        - risk_conclusion (dict with overall_level, recommendation, next_monitoring)
        - data_sources (list)
    """

    # Generate filename
    version = project_data.get('version', 1)
    filename = report_filename(
        project_data['slug'],
        'for',
        version,
        lang
    )
    filepath = os.path.join(output_path, filename)

    # Create output directory if needed
    os.makedirs(output_path, exist_ok=True)

    # Initialize styles
    styles = make_styles()

    # Create document
    doc = create_doc(filepath)

    # Build content
    story = []

    # 1. Cover Page
    story.append(PageBreak())

    # 2. Alert Summary (1 page)
    story.extend(section_header(
        "Alert Summary",
        styles,
        report_type='for'
    ))

    alert_data = project_data['alert_summary']
    story.append(Paragraph(
        f"<b>Event Description:</b>",
        styles['body']
    ))
    story.append(Paragraph(
        alert_data['event_description'],
        styles['body']
    ))
    story.append(Spacer(1, 0.2*inch))

    # Timeline
    story.append(Paragraph("<b>Timeline:</b>", styles['body']))
    timeline_items = alert_data.get('timeline', [])
    for item in timeline_items:
        story.append(Paragraph(
            f"• {item}",
            styles['body']
        ))
    story.append(Spacer(1, 0.2*inch))

    # Immediate Risk
    story.append(Paragraph(
        f"<b>Immediate Risk:</b><br/>{alert_data['immediate_risk']}",
        styles['callout_forensic']
    ))
    story.append(PageBreak())

    # 3. Insider Activity Analysis (2-3 pages)
    story.extend(section_header(
        "Insider Activity Analysis",
        styles,
        report_type='for'
    ))

    insider_data = project_data['insider_activity']
    wallets = insider_data.get('wallets', [])

    if wallets:
        # Build insider wallet table
        insider_table_data = [
            ['Wallet Address', 'Label', 'Action', 'Amount', 'Date']
        ]
        for wallet in wallets:
            insider_table_data.append([
                wallet.get('address', 'N/A')[:16] + '...',
                wallet.get('label', 'Unknown'),
                wallet.get('action', 'N/A'),
                wallet.get('amount', 'N/A'),
                wallet.get('date', 'N/A')
            ])

        insider_table = build_table(
            insider_table_data,
            col_widths=[1.6*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch],
            header_color='forensic_red',
            styles=styles
        )
        story.append(insider_table)
        story.append(Spacer(1, 0.2*inch))

    # Shell routing analysis
    shell_routing = insider_data.get('shell_routing', '')
    if shell_routing:
        story.append(Paragraph(
            f"<b>Shell Routing Analysis:</b><br/>{shell_routing}",
            styles['body']
        ))
        story.append(Spacer(1, 0.15*inch))

    # Mixer usage
    mixer_usage = insider_data.get('mixer_usage', '')
    if mixer_usage:
        story.append(Paragraph(
            f"<b>Mixer Usage Detection:</b><br/>{mixer_usage}",
            styles['body']
        ))

    story.append(PageBreak())

    # 4. Whale Wallet Behavior (2-3 pages with chart)
    story.extend(section_header(
        "Whale Wallet Behavior",
        styles,
        report_type='for'
    ))

    whale_data = project_data['whale_behavior']
    top_whales = whale_data.get('top_whales', [])

    if top_whales:
        # Build whale table
        whale_table_data = [
            ['Rank', 'Address', 'Balance', '30d Net Change', 'Exchange Flow']
        ]
        for idx, whale in enumerate(top_whales[:10], 1):
            whale_table_data.append([
                str(idx),
                whale.get('address', 'N/A')[:14] + '...',
                whale.get('balance', 'N/A'),
                whale.get('net_change_30d', 'N/A'),
                whale.get('exchange_flow', 'N/A')
            ])

        whale_table = build_table(
            whale_table_data,
            col_widths=[0.6*inch, 1.6*inch, 1.2*inch, 1.4*inch, 1.4*inch],
            header_color='forensic_red',
            styles=styles
        )
        story.append(whale_table)
        story.append(Spacer(1, 0.3*inch))

    # Exchange flow chart
    exchange_flow_img = _create_whale_exchange_chart(top_whales)
    if exchange_flow_img:
        story.append(Image(exchange_flow_img, width=6.5*inch, height=3.5*inch))
        story.append(Spacer(1, 0.15*inch))

    # Exchange flow summary
    exchange_summary = whale_data.get('exchange_flow_summary', '')
    if exchange_summary:
        story.append(Paragraph(
            f"<b>Exchange Flow Summary:</b><br/>{exchange_summary}",
            styles['body']
        ))

    story.append(PageBreak())

    # 5. Market Microstructure (2-3 pages)
    story.extend(section_header(
        "Market Microstructure Analysis",
        styles,
        report_type='for'
    ))

    market_data = project_data['market_microstructure']

    # Candlestick analysis
    candlestick = market_data.get('candlestick_analysis', '')
    if candlestick:
        story.append(Paragraph(
            f"<b>Candlestick Pattern Analysis:</b><br/>{candlestick}",
            styles['body']
        ))
        story.append(Spacer(1, 0.15*inch))

    # Volume anomaly
    volume_anomaly = market_data.get('volume_anomaly', '')
    if volume_anomaly:
        story.append(Paragraph(
            f"<b>Volume Anomaly:</b><br/>{volume_anomaly}",
            styles['body']
        ))
        story.append(Spacer(1, 0.15*inch))

    # Orderbook analysis
    orderbook = market_data.get('orderbook_analysis', '')
    if orderbook:
        story.append(Paragraph(
            f"<b>Orderbook Analysis:</b><br/>{orderbook}",
            styles['body']
        ))
        story.append(Spacer(1, 0.15*inch))

    # Dead cat bounce warning
    dca_data = market_data.get('dead_cat_bounce', {})
    if isinstance(dca_data, dict):
        dca_bool = dca_data.get('detected', False)
        dca_text = dca_data.get('text', '')
    else:
        dca_bool = dca_data
        dca_text = ''

    if dca_bool:
        warning_style = styles.get('callout_forensic', styles['body'])
        story.append(Paragraph(
            f"<b>⚠ Dead Cat Bounce Detected:</b><br/>{dca_text}",
            warning_style
        ))

    story.append(PageBreak())

    # 6. External Factor Assessment (1-2 pages)
    story.extend(section_header(
        "External Factor Assessment",
        styles,
        report_type='for'
    ))

    external_data = project_data['external_factors']

    # News
    news_list = external_data.get('news', [])
    if news_list:
        story.append(Paragraph("<b>Recent News & Developments:</b>", styles['body']))
        for news_item in news_list:
            story.append(Paragraph(
                f"• {news_item}",
                styles['body']
            ))
        story.append(Spacer(1, 0.15*inch))

    # Regulatory
    regulatory = external_data.get('regulatory', '')
    if regulatory:
        story.append(Paragraph(
            f"<b>Regulatory Environment:</b><br/>{regulatory}",
            styles['body']
        ))
        story.append(Spacer(1, 0.15*inch))

    # Macro impact
    macro = external_data.get('macro_impact', '')
    if macro:
        story.append(Paragraph(
            f"<b>Macroeconomic Impact:</b><br/>{macro}",
            styles['body']
        ))
        story.append(Spacer(1, 0.15*inch))

    # Similar cases
    similar = external_data.get('similar_cases', '')
    if similar:
        story.append(Paragraph(
            f"<b>Similar Historical Cases:</b><br/>{similar}",
            styles['body']
        ))

    story.append(PageBreak())

    # 7. Risk Conclusion (1 page)
    story.extend(section_header(
        "Risk Conclusion & Recommendations",
        styles,
        report_type='for'
    ))

    conclusion_data = project_data['risk_conclusion']

    # Overall risk level
    overall_level = conclusion_data.get('overall_level', 'UNKNOWN')
    story.append(Paragraph(
        f"<b>Overall Risk Level: {overall_level.upper()}</b>",
        styles.get('h1_forensic', styles['h1'])
    ))
    story.append(Spacer(1, 0.15*inch))

    # Recommendation
    recommendation = conclusion_data.get('recommendation', '')
    if recommendation:
        story.append(Paragraph(
            f"<b>Recommendation:</b><br/>{recommendation}",
            styles['callout_forensic'] if 'callout_forensic' in styles else styles['body']
        ))
        story.append(Spacer(1, 0.2*inch))

    # Next monitoring steps
    next_monitoring = conclusion_data.get('next_monitoring', '')
    if next_monitoring:
        story.append(Paragraph(
            f"<b>Next Monitoring Steps:</b><br/>{next_monitoring}",
            styles['body']
        ))

    story.append(PageBreak())

    # 8. Data Sources
    story.extend(section_header(
        "Data Sources & Methodology",
        styles,
        report_type='for'
    ))

    sources = project_data.get('data_sources', [])
    for source in sources:
        story.append(Paragraph(f"• {source}", styles['body']))

    story.append(Spacer(1, 0.3*inch))

    # Add disclaimer
    add_disclaimer(story, styles, report_type='for')

    # Build PDF
    # Cover page callback wrapping draw_cover_forensic
    def first_page(c, doc):
        draw_cover_forensic(
            c, doc,
            project_name=project_data['project_name'],
            token_symbol=project_data['token_symbol'],
            risk_level=project_data['risk_level'],
            trigger_reason=project_data['trigger_reason'],
            version=version,
            lang=lang
        )

    later_pages = make_header_footer(project_data['project_name'], 'for')

    doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)

    return filepath


def _create_whale_exchange_chart(top_whales: List[Dict[str, Any]]) -> Optional[str]:
    """
    Create a matplotlib bar chart of whale exchange flow.

    Args:
        top_whales: List of whale dictionaries with exchange_flow data

    Returns:
        Path to temporary image file, or None if no data
    """
    if not top_whales:
        return None

    try:
        # Extract exchange flow data
        addresses = []
        flows = []

        for whale in top_whales[:5]:  # Top 5 for clarity
            addr = whale.get('address', 'Unknown')[:10] + '...'
            addresses.append(addr)

            flow_str = whale.get('exchange_flow', '0')
            # Parse flow string (e.g., "+1500 ETH", "-2000 BTC")
            try:
                flow_val = float(''.join(c for c in flow_str if c.isdigit() or c == '-' or c == '.'))
                if '-' in flow_str:
                    flow_val = -flow_val
            except (ValueError, AttributeError):
                flow_val = 0

            flows.append(flow_val)

        if not flows:
            return None

        # Create figure
        fig, ax = plt.subplots(figsize=(7, 4))

        colors_list = ['#B91C1C' if f > 0 else '#1F2937' for f in flows]
        bars = ax.bar(addresses, flows, color=colors_list, alpha=0.8, edgecolor='#374151', linewidth=1.5)

        # Styling
        ax.set_ylabel('Net Flow (Units)', fontsize=11, fontweight='bold')
        ax.set_xlabel('Wallet Address', fontsize=11, fontweight='bold')
        ax.set_title('Top Whale Exchange Flow (30-day)', fontsize=13, fontweight='bold', color='#1F2937')
        ax.axhline(y=0, color='#6B7280', linestyle='-', linewidth=0.8)
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        # Add value labels on bars
        for bar, flow in zip(bars, flows):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{flow:+.0f}',
                   ha='center', va='bottom' if height > 0 else 'top',
                   fontsize=9, fontweight='bold')

        plt.tight_layout()

        # Save to temp file
        temp_img = io.BytesIO()
        fig.savefig(temp_img, format='png', dpi=300, bbox_inches='tight')
        temp_img.seek(0)
        plt.close(fig)

        return temp_img

    except Exception as e:
        print(f"Error creating whale exchange chart: {e}")
        return None


def _create_timeline_visualization(timeline: List[str]) -> Optional[str]:
    """
    Create a matplotlib timeline visualization.

    Args:
        timeline: List of timeline events

    Returns:
        Path to temporary image file, or None if no data
    """
    if not timeline or len(timeline) < 2:
        return None

    try:
        fig, ax = plt.subplots(figsize=(7, 3))

        y_positions = range(len(timeline))

        ax.scatter(y_positions, [1]*len(timeline), s=200, color='#B91C1C', zorder=3)
        ax.plot(y_positions, [1]*len(timeline), 'k-', linewidth=2, zorder=1)

        for i, event in enumerate(timeline):
            ax.text(i, 1.15, event, ha='center', fontsize=9, wrap=True)

        ax.set_ylim(0.8, 1.4)
        ax.set_xlim(-0.5, len(timeline) - 0.5)
        ax.axis('off')

        plt.tight_layout()

        temp_img = io.BytesIO()
        fig.savefig(temp_img, format='png', dpi=300, bbox_inches='tight')
        temp_img.seek(0)
        plt.close(fig)

        return temp_img

    except Exception as e:
        print(f"Error creating timeline visualization: {e}")
        return None


if __name__ == '__main__':
    # Sample data for fictional "TokenX" project under critical alert
    sample_project_data = {
        'project_name': 'TokenX',
        'token_symbol': 'TOKENX',
        'slug': 'tokenx',
        'version': 1,
        'risk_level': 'critical',
        'trigger_reason': '24h price drop -22.5%, volume spike 450% of 7d avg, major whale movement detected',
        'alert_summary': {
            'event_description': 'TokenX experienced a sharp price decline of 22.5% over 24 hours, accompanied by a volume spike of 450% above the 7-day average. This unusual market activity was preceded by significant whale wallet movements and unusual insider trading patterns.',
            'timeline': [
                '2026-04-08 14:30 UTC: Initial price decline begins',
                '2026-04-08 16:45 UTC: Volume spike detected',
                '2026-04-08 18:20 UTC: Whale wallet movements identified',
                '2026-04-08 22:15 UTC: Mixer usage detected on insider addresses',
                '2026-04-09 08:00 UTC: Alert generated'
            ],
            'immediate_risk': 'Immediate risks include further price decline, potential regulatory scrutiny, and loss of investor confidence. The unusual insider activity suggests possible market manipulation or insider trading.'
        },
        'insider_activity': {
            'wallets': [
                {
                    'address': '0x1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p',
                    'label': 'Founder Wallet',
                    'action': 'Large sell',
                    'amount': '500,000 TOKENX',
                    'date': '2026-04-08 14:15 UTC'
                },
                {
                    'address': '0x2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p',
                    'label': 'Treasury Account',
                    'action': 'Withdrawal',
                    'amount': '2,000,000 TOKENX',
                    'date': '2026-04-08 15:00 UTC'
                },
                {
                    'address': '0x3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p',
                    'label': 'Advisor Unknown',
                    'action': 'Bridge to mixing service',
                    'amount': '750,000 TOKENX',
                    'date': '2026-04-08 16:30 UTC'
                }
            ],
            'shell_routing': 'Detected routing through 3 intermediate shell wallets with no prior transaction history. Wallets created within 48 hours of activity. High probability of obfuscation attempt.',
            'mixer_usage': 'Identified usage of Tornado Cash mixer service by wallet 0x3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p for 750,000 tokens. Withdrawal to new exchange account detected 4 hours post-mixing.'
        },
        'whale_behavior': {
            'top_whales': [
                {
                    'address': '0xwhale1234567890abcdef',
                    'balance': '5,000,000 TOKENX',
                    'net_change_30d': '-1,500,000 (-23%)',
                    'exchange_flow': '-1,500,000'
                },
                {
                    'address': '0xwhale2345678901bcdef0',
                    'balance': '3,200,000 TOKENX',
                    'net_change_30d': '-800,000 (-20%)',
                    'exchange_flow': '-800,000'
                },
                {
                    'address': '0xwhale3456789012cdef01',
                    'balance': '2,100,000 TOKENX',
                    'net_change_30d': '+200,000 (+10%)',
                    'exchange_flow': '+200,000'
                },
                {
                    'address': '0xwhale4567890123def012',
                    'balance': '1,800,000 TOKENX',
                    'net_change_30d': '-900,000 (-33%)',
                    'exchange_flow': '-900,000'
                },
                {
                    'address': '0xwhale5678901234ef0123',
                    'balance': '1,500,000 TOKENX',
                    'net_change_30d': '-450,000 (-23%)',
                    'exchange_flow': '-450,000'
                }
            ],
            'exchange_flow_summary': 'Whale activity shows net negative flow to exchanges, with 4 of top 5 whales reducing positions by 20-33% in past 30 days. This suggests prior knowledge of current price decline or coordinated exit strategy.'
        },
        'market_microstructure': {
            'candlestick_analysis': 'Daily candlesticks show formation of Bearish Engulfing pattern on 2026-04-08, with rejection from 50-day MA resistance. Long upper wicks indicate strong selling pressure at higher prices. Volume profile shows distribution of institutional holders.',
            'volume_anomaly': 'Trading volume spike to 450% of 7-day average on 2026-04-08. Spike is concentrated in 2 hour window (16:45-18:45 UTC), suggesting coordinated selling event. No corresponding buy-side volume recovery.',
            'orderbook_analysis': 'Order book shows extreme imbalance with sell orders outnumbering buy orders by 4.2:1. Bid-ask spread widened from 0.03% to 0.67%. Multiple levels of market depth evaporated within 60 seconds at market open.',
            'dead_cat_bounce': {
                'detected': True,
                'text': 'Current 4-hour bounce (+8%) from 24h lows shows characteristics of dead cat bounce: low volume, rejection at key MA resistance, and continued negative sentiment. Probability of bounce reversal: 78% within 24 hours.'
            }
        },
        'external_factors': {
            'news': [
                'TokenX team announces reduced marketing budget (April 7)',
                'Key partnership announcement cancelled without explanation (April 6)',
                'Rumors of CEO health issues circulating on social media (April 5)',
                'Competitor launches new feature directly competing with TokenX (April 4)'
            ],
            'regulatory': 'No direct regulatory action identified. However, increased regulatory scrutiny on Layer-1 blockchain projects noted in industry. Potential for retroactive classification of TOKENX as security under review.',
            'macro_impact': 'Broader crypto market down 5% over past 24 hours on inflation concerns. Risk-off sentiment in equities markets affecting crypto asset allocation. Federal Reserve policy uncertainty creating headwinds for speculative assets.',
            'similar_cases': 'Pattern matches Luna/UST collapse (May 2022) - rapid depletion of reserves, insider liquidation, mixer service usage. Also similar to Celsius Network (June 2022) - large whale positions liquidating before public announcement.'
        },
        'risk_conclusion': {
            'overall_level': 'CRITICAL',
            'recommendation': 'IMMEDIATE ACTION REQUIRED: (1) Freeze all TOKENX positions and prepare emergency hedging strategies. (2) Initiate withdrawal of positions to cold storage if possible. (3) Monitor insider addresses for further movement. (4) Prepare communication strategy for potential total loss scenario. (5) Conduct forensic analysis of smart contracts for vulnerabilities.',
            'next_monitoring': 'Continue monitoring at 15-minute intervals for next 72 hours. Key monitoring points: (1) Insider wallet movements, (2) Whale position changes, (3) Regulatory announcements, (4) Social sentiment shifts, (5) Exchange flow patterns. Alert if additional 10% price decline or 500%+ volume spike detected.'
        },
        'data_sources': [
            'On-chain data from Etherscan and Blockchain.com',
            'Exchange flow analysis from Glassnode',
            'Social sentiment from LunarCrush and Santiment',
            'Regulatory news aggregation from regulatory databases',
            'Market microstructure data from Binance and Kraken APIs',
            'Whale tracking from Whale Alert service',
            'Mixer detection from Chainalysis'
        ]
    }

    # Generate report
    output_dir = '/tmp/bce_lab_reports'
    try:
        pdf_path = generate_for_report(
            project_data=sample_project_data,
            lang='en',
            output_path=output_dir
        )
        print(f"✓ Forensic report generated successfully")
        print(f"  Output: {pdf_path}")
    except Exception as e:
        print(f"✗ Error generating forensic report: {e}")
        import traceback
        traceback.print_exc()
