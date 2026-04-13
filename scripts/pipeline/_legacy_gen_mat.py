"""
Project Maturity (RPT-MAT) Report Generator for BCE Lab
Generates professional PDF reports with maturity assessment, on-chain metrics,
peer comparison, and risk analysis.
"""

# ╔══════════════════════════════════════════════════════════╗
# ║  DEPRECATED — DO NOT USE                                ║
# ║  Use gen_text_mat.py + gen_pdf_mat.py instead           ║
# ║  This file is kept for reference only.                  ║
# ╚══════════════════════════════════════════════════════════╝

import os
import sys
from datetime import datetime
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, FancyBboxPatch
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    Image as RLImage, KeepTogether
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# Import from local modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pdf_base import (
    make_styles, section_header, build_table, draw_cover_econ_mat,
    make_header_footer, add_disclaimer, create_doc, C, USABLE_W
)
from config import REPORT_TYPES, MATURITY_LEVELS, report_filename


def generate_mat_report(project_data: dict, lang: str, output_path: str) -> str:
    """
    Generate a professional Maturity (RPT-MAT) PDF report.

    Args:
        project_data: Dict with project info, scores, metrics, and analysis
        lang: Language code ('en' or 'ko')
        output_path: Directory path for output PDF

    Returns:
        Full path to generated PDF file
    """

    # Create document
    version = project_data.get('version', 1)
    filename = report_filename(project_data['slug'], 'mat', version, lang)
    filepath = os.path.join(output_path, filename)

    doc = create_doc(filepath)
    story = []
    styles = make_styles()

    # Cover page handled by onFirstPage callback
    story.append(PageBreak())

    # Add maturity overview
    _add_maturity_overview(story, doc, project_data, styles, lang)
    story.append(PageBreak())

    # Add tech pillar assessment
    _add_tech_pillar_assessment(story, doc, project_data, styles, lang)
    story.append(PageBreak())

    # Add on-chain metrics
    _add_onchain_metrics(story, doc, project_data, styles, lang)
    story.append(PageBreak())

    # Add peer comparison
    _add_peer_comparison(story, doc, project_data, styles, lang)
    story.append(PageBreak())

    # Add risk matrix
    _add_risk_matrix(story, doc, project_data, styles, lang)
    story.append(PageBreak())

    # Add growth trajectory
    _add_growth_trajectory(story, doc, project_data, styles, lang)
    story.append(PageBreak())

    # Disclaimer
    add_disclaimer(story, styles, 'mat')

    # Build with cover + header/footer
    project_name = project_data.get('project_name', 'Project')
    later_pages = make_header_footer(project_name, 'mat')

    def first_page(c, d):
        score = project_data.get('maturity_score', 0)
        level = project_data.get('maturity_level', 'growing')
        km = [(f'{score:.1f}%', 'Maturity Score'), (level.title(), 'Stage')]
        draw_cover_econ_mat(c, d, project_name, 'mat', version, lang,
                           subtitle=f'{project_data.get("token_symbol","")} Maturity Assessment',
                           key_metrics=km)

    doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
    return filepath




def _add_maturity_overview(story, doc, project_data, styles, lang):
    """Add maturity overview section with score, change, and stage criteria."""

    title = "Maturity Overview" if lang == 'en' else "성숙도 개요"
    story.extend(section_header(title, styles))
    story.append(Spacer(1, 12))

    # Summary metrics
    score = project_data['maturity_score']
    change = project_data['score_change']
    level = project_data['maturity_level']

    change_text = f"+{change:.1f}" if change >= 0 else f"{change:.1f}"
    change_color = colors.green if change >= 0 else colors.red

    summary_data = [
        ["Current Score", f"{score:.1f}%"],
        ["Previous Change", change_text],
        ["Maturity Level", level.capitalize()],
    ]

    summary_table = build_table(
        summary_data,
        col_widths=[USABLE_W * 0.4, USABLE_W * 0.6],
        styles=styles
    )

    story.append(summary_table)
    story.append(Spacer(1, 18))

    # Maturity level criteria table
    criteria_title = "Maturity Stage Criteria" if lang == 'en' else "성숙도 단계 기준"
    story.append(Paragraph(criteria_title, styles['h2']))
    story.append(Spacer(1, 9))

    # Define criteria for each level
    criteria_data = [
        ["Stage", "Score Range", "Characteristics"] if lang == 'en'
        else ["단계", "점수 범위", "특성"]
    ]

    criteria_data.extend([
        ["Nascent", "0-25", "Early development, proof of concept stage"],
        ["Growing", "25-50", "Active development, increasing adoption"],
        ["Mature", "50-75", "Established ecosystem, stable metrics"],
        ["Established", "75-100", "Market leader, comprehensive maturity"],
    ] if lang == 'en' else [
        ["신생", "0-25", "초기 개발, 개념 증명 단계"],
        ["성장", "25-50", "활발한 개발, 채택 증가"],
        ["성숙", "50-75", "확립된 생태계, 안정적 지표"],
        ["확립", "75-100", "시장 리더, 포괄적 성숙도"],
    ])

    criteria_table = build_table(
        criteria_data,
        col_widths=[USABLE_W * 0.15, USABLE_W * 0.2, USABLE_W * 0.65],
        styles=styles
    )

    story.append(criteria_table)
    story.append(Spacer(1, 12))

    # Score interpretation
    interp_text = (
        f"The {project_data['project_name']} project has achieved a maturity score of {score:.1f}% "
        f"({level.capitalize()} stage). This represents a change of {change_text} points from the previous assessment."
        if lang == 'en'
        else
        f"{project_data['project_name']} 프로젝트는 {score:.1f}% 성숙도 점수({level.capitalize()} 단계)를 달성했습니다. "
        f"이는 이전 평가에서 {change_text} 포인트의 변화를 나타냅니다."
    )

    story.append(Paragraph(interp_text, styles['body']))


def _add_tech_pillar_assessment(story, doc, project_data, styles, lang):
    """Add tech pillar assessment with progress bars and trend analysis."""

    title = "Technology Pillar Assessment" if lang == 'en' else "기술 기둥 평가"
    story.extend(section_header(title, styles))
    story.append(Spacer(1, 12))

    pillars = project_data['tech_pillars']

    # Add progress chart for all pillars
    pillar_chart = _create_pillar_chart(pillars, lang)
    story.append(RLImage(pillar_chart, width=USABLE_W, height=216))
    story.append(Spacer(1, 18))

    # Add detailed pillar breakdown
    for i, pillar in enumerate(pillars):
        # Pillar header with score
        pillar_header = (
            f"{pillar['name']} — {pillar['score']:.1f}/100"
        )
        story.append(Paragraph(pillar_header, styles['h3']))

        # Trend indicator
        prev_score = pillar.get('prev_score', pillar['score'])
        change = pillar['score'] - prev_score

        trend_data = [
            [
                f"Current: {pillar['score']:.1f}" if lang == 'en' else f"현재: {pillar['score']:.1f}",
                f"Previous: {prev_score:.1f}" if lang == 'en' else f"이전: {prev_score:.1f}",
                f"Δ: {change:+.1f}" if lang == 'en' else f"변화: {change:+.1f}",
            ]
        ]

        trend_table = build_table(
            trend_data,
            col_widths=[USABLE_W * 0.33, USABLE_W * 0.33, USABLE_W * 0.34],
            styles=styles
        )

        story.append(trend_table)
        story.append(Spacer(1, 6))

        # Details text
        story.append(Paragraph(pillar['details'], styles['body']))

        if i < len(pillars) - 1:
            story.append(Spacer(1, 12))


def _add_onchain_metrics(story, doc, project_data, styles, lang):
    """Add on-chain metrics with TVL, addresses, transaction count, and gas."""

    title = "On-Chain Metrics" if lang == 'en' else "온체인 지표"
    story.extend(section_header(title, styles))
    story.append(Spacer(1, 12))

    metrics = project_data['onchain_metrics']

    # TVL summary
    tvl_title = "Total Value Locked (TVL)" if lang == 'en' else "잠금된 총 가치 (TVL)"
    story.append(Paragraph(tvl_title, styles['h3']))

    tvl_current = metrics.get('tvl_current', 0)
    tvl_text = f"${tvl_current:,.0f}" if lang == 'en' else f"${tvl_current:,.0f}"

    tvl_data = [[tvl_text]]
    tvl_table = build_table(
        tvl_data,
        col_widths=[USABLE_W],
        styles=styles
    )

    story.append(tvl_table)
    story.append(Spacer(1, 9))

    # TVL 90-day trend chart
    if metrics.get('tvl_90d_data'):
        tvl_chart = _create_trend_chart(
            metrics['tvl_90d_data'],
            "TVL Trend (90 days)" if lang == 'en' else "TVL 추세 (90일)",
            lang
        )
        story.append(RLImage(tvl_chart, width=USABLE_W * 0.95, height=158))
        story.append(Spacer(1, 12))

    # Active addresses
    addr_title = "Active Addresses" if lang == 'en' else "활성 주소"
    story.append(Paragraph(addr_title, styles['h3']))

    if metrics.get('active_addresses_data'):
        addr_chart = _create_trend_chart(
            metrics['active_addresses_data'],
            "Active Addresses Trend" if lang == 'en' else "활성 주소 추세",
            lang
        )
        story.append(RLImage(addr_chart, width=USABLE_W * 0.95, height=158))
        story.append(Spacer(1, 12))

    # Transaction count
    tx_title = "Transaction Count" if lang == 'en' else "거래 수"
    story.append(Paragraph(tx_title, styles['h3']))

    if metrics.get('tx_count_data'):
        tx_chart = _create_trend_chart(
            metrics['tx_count_data'],
            "Transaction Count Trend" if lang == 'en' else "거래 수 추세",
            lang
        )
        story.append(RLImage(tx_chart, width=USABLE_W * 0.95, height=158))
        story.append(Spacer(1, 12))

    # Gas metrics
    gas_title = "Gas Consumption" if lang == 'en' else "가스 소비"
    story.append(Paragraph(gas_title, styles['h3']))

    if metrics.get('gas_data'):
        gas_chart = _create_trend_chart(
            metrics['gas_data'],
            "Gas Consumption Trend" if lang == 'en' else "가스 소비 추세",
            lang
        )
        story.append(RLImage(gas_chart, width=USABLE_W * 0.95, height=158))


def _add_peer_comparison(story, doc, project_data, styles, lang):
    """Add peer comparison with table and positioning map."""

    title = "Peer Comparison" if lang == 'en' else "동종사 비교"
    story.extend(section_header(title, styles))
    story.append(Spacer(1, 12))

    peers = project_data.get('peer_comparison', [])

    if not peers:
        story.append(Paragraph(
            "No peer data available." if lang == 'en' else "동종사 데이터가 없습니다.",
            styles['body']
        ))
        return

    # Peer comparison table
    table_title = "Peer Metrics Comparison" if lang == 'en' else "동종사 지표 비교"
    story.append(Paragraph(table_title, styles['h3']))
    story.append(Spacer(1, 6))

    header = [
        ["Project", "Market Cap", "TVL", "Maturity Score"] if lang == 'en'
        else ["프로젝트", "시가총액", "TVL", "성숙도 점수"]
    ]

    table_data = header.copy()
    for peer in peers:
        table_data.append([
            peer['name'],
            f"${peer.get('market_cap', 0):,.0f}",
            f"${peer.get('tvl', 0):,.0f}",
            f"{peer.get('maturity_score', 0):.1f}",
        ])

    peer_table = build_table(
        table_data,
        col_widths=[USABLE_W * 0.25, USABLE_W * 0.25, USABLE_W * 0.25, USABLE_W * 0.25],
        styles=styles
    )

    story.append(peer_table)
    story.append(Spacer(1, 18))

    # Positioning map (scatter plot)
    positioning_title = "Market Positioning" if lang == 'en' else "시장 포지셔닝"
    story.append(Paragraph(positioning_title, styles['h3']))
    story.append(Spacer(1, 6))

    positioning_chart = _create_positioning_map(peers, project_data, lang)
    story.append(RLImage(positioning_chart, width=USABLE_W * 0.95, height=252))


def _add_risk_matrix(story, doc, project_data, styles, lang):
    """Add risk matrix with 4-quadrant assessment."""

    title = "Risk Assessment Matrix" if lang == 'en' else "위험 평가 매트릭스"
    story.extend(section_header(title, styles))
    story.append(Spacer(1, 12))

    risks = project_data.get('risk_matrix', {})

    # Risk levels
    risk_types = [
        ('tech_risk', "Technology Risk" if lang == 'en' else "기술 위험"),
        ('market_risk', "Market Risk" if lang == 'en' else "시장 위험"),
        ('regulatory_risk', "Regulatory Risk" if lang == 'en' else "규제 위험"),
        ('operational_risk', "Operational Risk" if lang == 'en' else "운영 위험"),
    ]

    # Risk table
    table_data = [
        ["Risk Category", "Score (1-5)", "Assessment"] if lang == 'en'
        else ["위험 카테고리", "점수 (1-5)", "평가"]
    ]

    for risk_key, risk_label in risk_types:
        if risk_key in risks:
            risk_info = risks[risk_key]
            score = risk_info.get('score', 0) if isinstance(risk_info, dict) else risk_info
            text = risk_info.get('text', '') if isinstance(risk_info, dict) else ''

            # Color code by risk level
            if score <= 2:
                bg_color = HexColor('#d4edda')  # Green
            elif score <= 3:
                bg_color = HexColor('#fff3cd')  # Yellow
            else:
                bg_color = HexColor('#f8d7da')  # Red

            table_data.append([
                risk_label,
                str(int(score)),
                text[:80] + ('...' if len(text) > 80 else ''),
            ])

    risk_table = build_table(
        table_data,
        col_widths=[USABLE_W * 0.25, USABLE_W * 0.15, USABLE_W * 0.6],
        styles=styles
    )

    story.append(risk_table)
    story.append(Spacer(1, 18))

    # Risk descriptions
    for risk_key, risk_label in risk_types:
        if risk_key in risks:
            risk_info = risks[risk_key]
            text = risk_info.get('text', '') if isinstance(risk_info, dict) else ''

            if text:
                story.append(Paragraph(f"<b>{risk_label}</b>", styles['body']))
                story.append(Paragraph(text, styles['body']))
                story.append(Spacer(1, 6))


def _add_growth_trajectory(story, doc, project_data, styles, lang):
    """Add growth trajectory with outlook, milestones, and watch points."""

    title = "Growth Trajectory & Outlook" if lang == 'en' else "성장 궤적 및 전망"
    story.extend(section_header(title, styles))
    story.append(Spacer(1, 12))

    trajectory = project_data.get('growth_trajectory', {})

    # 3-month outlook
    outlook_title = "3-Month Outlook" if lang == 'en' else "3개월 전망"
    story.append(Paragraph(outlook_title, styles['h3']))
    story.append(Spacer(1, 6))

    outlook_text = trajectory.get('outlook_3m', '')
    if outlook_text:
        story.append(Paragraph(outlook_text, styles['body']))
    story.append(Spacer(1, 12))

    # Milestones
    milestones_title = "Key Milestones" if lang == 'en' else "주요 마일스톤"
    story.append(Paragraph(milestones_title, styles['h3']))
    story.append(Spacer(1, 6))

    milestones = trajectory.get('milestones', [])
    if milestones:
        for i, milestone in enumerate(milestones, 1):
            milestone_text = f"• {milestone}" if isinstance(milestone, str) else f"• {milestone.get('text', '')}"
            story.append(Paragraph(milestone_text, styles['body']))
    story.append(Spacer(1, 12))

    # Watch points
    watch_title = "Watch Points" if lang == 'en' else "주의 포인트"
    story.append(Paragraph(watch_title, styles['h3']))
    story.append(Spacer(1, 6))

    watch_points = trajectory.get('watch_points', [])
    if watch_points:
        for watch in watch_points:
            watch_text = f"• {watch}" if isinstance(watch, str) else f"• {watch.get('text', '')}"
            story.append(Paragraph(watch_text, styles['body']))




def _create_pillar_chart(pillars, lang):
    """Create matplotlib progress bar chart for tech pillars."""

    fig, ax = plt.subplots(figsize=(10, 4))

    names = [p['name'] for p in pillars]
    scores = [p['score'] for p in pillars]
    prev_scores = [p.get('prev_score', p['score']) for p in pillars]

    x = np.arange(len(names))
    width = 0.35

    bars1 = ax.bar(x - width/2, prev_scores, width, label="Previous" if lang == 'en' else "이전", color='#D0D0D0')
    bars2 = ax.bar(x + width/2, scores, width, label="Current" if lang == 'en' else "현재", color='#2C3E50')

    ax.set_ylabel("Score (0-100)" if lang == 'en' else "점수 (0-100)")
    ax.set_title("Technology Pillar Scores" if lang == 'en' else "기술 기둥 점수")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15, ha='right')
    ax.set_ylim(0, 105)
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.0f}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf


def _create_trend_chart(data, title, lang):
    """Create matplotlib line chart for 90-day trends."""

    fig, ax = plt.subplots(figsize=(10, 2.5))

    # Handle different data formats
    if isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], (int, float)):
            values = data
            days = list(range(len(values)))
        elif isinstance(data[0], dict):
            days = [d.get('day', i) for i, d in enumerate(data)]
            values = [d.get('value', 0) for d in data]
        else:
            days = list(range(len(data)))
            values = data
    else:
        days = [0]
        values = [0]

    ax.plot(days, values, color='#2C3E50', linewidth=2, marker='o')
    ax.fill_between(days, values, alpha=0.3, color='#2C3E50')

    ax.set_xlabel("Days" if lang == 'en' else "일수")
    ax.set_ylabel("Value" if lang == 'en' else "값")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf


def _create_positioning_map(peers, project_data, lang):
    """Create 2x2 positioning map (maturity vs market size)."""

    fig, ax = plt.subplots(figsize=(10, 8))

    # Prepare data
    all_projects = [{'name': project_data['project_name'], **project_data}] + peers

    x_values = []  # Market cap (log scale)
    y_values = []  # Maturity score
    labels = []

    for proj in all_projects:
        market_cap = proj.get('market_cap', 1000000)
        maturity = proj.get('maturity_score', 50)

        x_values.append(np.log10(max(market_cap, 1)))
        y_values.append(maturity)
        labels.append(proj.get('name', proj.get('project_name', 'Unknown')))

    # Plot points
    colors_map = ['#E74C3C' if label == project_data['project_name'] else '#2C3E50' for label in labels]
    sizes = [300 if label == project_data['project_name'] else 150 for label in labels]

    ax.scatter(x_values, y_values, s=sizes, c=colors_map, alpha=0.6, edgecolors='black', linewidth=1)

    # Add labels
    for i, label in enumerate(labels):
        ax.annotate(label, (x_values[i], y_values[i]), xytext=(5, 5),
                   textcoords='offset points', fontsize=9)

    # Add quadrant lines
    ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(x=np.log10(1000000000), color='gray', linestyle='--', alpha=0.5)

    # Quadrant labels
    quadrant_labels = [
        ("High Maturity\nSmall Cap" if lang == 'en' else "높은 성숙도\n소형주", 4, 75),
        ("High Maturity\nLarge Cap" if lang == 'en' else "높은 성숙도\n대형주", 9, 75),
        ("Early Stage\nSmall Cap" if lang == 'en' else "초기 단계\n소형주", 4, 25),
        ("Early Stage\nLarge Cap" if lang == 'en' else "초기 단계\n대형주", 9, 25),
    ]

    for text, x, y in quadrant_labels:
        ax.text(x, y, text, fontsize=8, alpha=0.5, ha='center', va='center',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.3))

    ax.set_xlabel("Market Cap (log scale, USD)" if lang == 'en' else "시가총액 (로그 스케일, USD)")
    ax.set_ylabel("Maturity Score" if lang == 'en' else "성숙도 점수")
    ax.set_title("Market Positioning" if lang == 'en' else "시장 포지셔닝")
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf


if __name__ == '__main__':
    """Test the report generator with sample Uniswap data."""

    # Create output directory
    output_dir = '/tmp/bce_reports'
    os.makedirs(output_dir, exist_ok=True)

    # Sample project data
    sample_data = {
        'project_name': 'Uniswap',
        'token_symbol': 'UNI',
        'slug': 'uniswap',
        'version': 'v1.0',
        'maturity_score': 82.5,
        'maturity_level': 'established',
        'score_change': 3.2,
        'tech_pillars': [
            {
                'name': 'Architecture',
                'score': 85.0,
                'prev_score': 82.0,
                'details': 'Uniswap V4 introduces innovative architectural improvements with hooks and flash accounting. The AMM design is battle-tested with continuous refinement across versions.'
            },
            {
                'name': 'Security',
                'score': 80.0,
                'prev_score': 78.5,
                'details': 'Multiple audits by leading firms (OpenZeppelin, Trail of Bits). Formal verification in progress. Security incident response protocols established.'
            },
            {
                'name': 'Scalability',
                'score': 85.0,
                'prev_score': 83.0,
                'details': 'Multi-chain deployment across Ethereum, Arbitrum, Polygon, Optimism. Layer 2 integration strategies mature. Gas optimization ongoing.'
            },
            {
                'name': 'Governance',
                'score': 78.0,
                'prev_score': 75.0,
                'details': 'Comprehensive DAO governance via UNI token. Multi-sig security, timelock mechanisms. Community participation growing. Protocol improvements driven by governance proposals.'
            },
        ],
        'onchain_metrics': {
            'tvl_current': 4500000000,
            'tvl_90d_data': [
                {'day': i, 'value': 4200000000 + (i * 3571428)} for i in range(90)
            ],
            'active_addresses_data': [
                {'day': i, 'value': 18000 + (i * 50)} for i in range(90)
            ],
            'tx_count_data': [
                {'day': i, 'value': 500000 + (i * 1000)} for i in range(90)
            ],
            'gas_data': [
                {'day': i, 'value': 125000000 + (i * 300000)} for i in range(90)
            ],
        },
        'peer_comparison': [
            {
                'name': 'Aave',
                'market_cap': 15000000000,
                'tvl': 8000000000,
                'maturity_score': 79.5,
            },
            {
                'name': 'Curve',
                'market_cap': 3000000000,
                'tvl': 3500000000,
                'maturity_score': 75.0,
            },
            {
                'name': 'Balancer',
                'market_cap': 1500000000,
                'tvl': 800000000,
                'maturity_score': 68.5,
            },
        ],
        'risk_matrix': {
            'tech_risk': {
                'score': 2,
                'text': 'Low technical risk. Mature codebase with extensive testing and auditing. Continuous innovation managed through governance.'
            },
            'market_risk': {
                'score': 2,
                'text': 'Market leadership position. Diversified across multiple chains and pool types. Competitive pressures from other AMMs.'
            },
            'regulatory_risk': {
                'score': 3,
                'text': 'Moderate regulatory uncertainty. Ongoing discussions about DEX regulation. Governance structure provides adaptive response capability.'
            },
            'operational_risk': {
                'score': 2,
                'text': 'Minimal operational risk. Decentralized governance model. Established protocols for upgrades and emergency responses.'
            },
        },
        'growth_trajectory': {
            'outlook_3m': 'Uniswap is positioned for continued growth through V4 adoption, multi-chain expansion, and integration with emerging DeFi protocols. Expected improvements in capital efficiency and user experience should drive adoption metrics upward.',
            'milestones': [
                'Uniswap V4 mainnet deployment',
                'Increased institutional adoption',
                'Cross-chain liquidity protocols',
                'Enhanced governance participation',
            ],
            'watch_points': [
                'Regulatory developments affecting DEX operations',
                'Competition from other AMM protocols',
                'Smart contract security vulnerabilities',
                'Liquidity distribution across chains',
            ],
        },
        'data_sources': [
            'Dune Analytics - On-chain metrics',
            'DefiLlama - TVL tracking',
            'Etherscan - Transaction data',
            'CoinGecko - Market data',
            'Official Uniswap documentation',
        ],
    }

    # Generate report
    print("Generating Maturity Report for Uniswap...")
    filepath = generate_mat_report(sample_data, 'en', output_dir)
    print(f"Report generated: {filepath}")

    # Test Korean version
    print("Generating Korean version...")
    filepath_ko = generate_mat_report(sample_data, 'ko', output_dir)
    print(f"Korean report generated: {filepath_ko}")
