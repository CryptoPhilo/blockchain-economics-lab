"""
Economy Design Analysis (RPT-ECON) Report Generator for BCE Lab.

Generates a professional PDF report analyzing blockchain project economic design,
token economy, value flows, and risk factors.
"""

# ╔══════════════════════════════════════════════════════════╗
# ║  DEPRECATED — DO NOT USE                                ║
# ║  Use gen_text_econ.py + gen_pdf_econ.py instead         ║
# ║  This file is kept for reference only.                  ║
# ╚══════════════════════════════════════════════════════════╝

import io
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any

import matplotlib
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image, KeepTogether, CondPageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

# Configure matplotlib
matplotlib.use('Agg')
plt.rcParams['font.family'] = 'DejaVu Sans'

# Import shared utilities
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from pdf_base import (
    make_styles, accent_line, thin_line, section_header,
    build_table, draw_cover_econ_mat, make_header_footer,
    add_disclaimer, create_doc, USABLE_W, C
)
from config import REPORT_TYPES, report_filename, COLORS


def chart_to_image(fig, width_mm: float, height_mm: float) -> Image:
    """Convert matplotlib figure to reportlab Image flowable."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    return Image(buf, width=width_mm*mm, height=height_mm*mm)


def draw_tech_pillars(project_data: dict, styles: Dict) -> List:
    """Generate Tech Stack - 4 Pillars section."""
    story = []

    story.extend(section_header("Core Tech Stack — 4 Pillars", styles, "econ"))
    story.append(Spacer(1, 6))

    tech_pillars = project_data.get('tech_pillars', [])

    # Create pillar score chart
    if tech_pillars:
        pillar_names = [p.get('name', 'Pillar') for p in tech_pillars]
        pillar_scores = [p.get('score', 0) for p in tech_pillars]

        fig, ax = plt.subplots(figsize=(10, 4))
        bars = ax.barh(pillar_names, pillar_scores, color=['#4F46E5', '#16A34A', '#D97706', '#DC2626'])
        ax.set_xlim(0, 100)
        ax.set_xlabel('Score', fontsize=10)
        ax.grid(axis='x', alpha=0.3)

        for i, (bar, score) in enumerate(zip(bars, pillar_scores)):
            ax.text(score + 2, i, f'{score}', va='center', fontsize=9, fontweight='bold')

        plt.tight_layout()
        story.append(chart_to_image(fig, 160, 60))
        plt.close(fig)
        story.append(Spacer(1, 12))

    # Pillar details
    for i, pillar in enumerate(tech_pillars, 1):
        pillar_name = pillar.get('name', f'Pillar {i}')
        pillar_score = pillar.get('score', 0)
        pillar_analysis = pillar.get('analysis', '')

        # Pillar header with score
        header_text = f"<b>{i}. {pillar_name}</b> — Score: {pillar_score}/100"
        story.append(Paragraph(header_text, styles['h3']))
        story.append(Spacer(1, 3))

        # Analysis text
        story.append(Paragraph(pillar_analysis, styles['body']))
        story.append(Spacer(1, 10))

    return story


def draw_onchain_infra(project_data: dict, styles: Dict) -> List:
    """Generate On-Chain Infrastructure Specification section."""
    story = []

    story.extend(section_header("On-Chain Infrastructure Specification", styles, "econ"))
    story.append(Spacer(1, 6))

    onchain = project_data.get('onchain_infra', {})

    # Key metrics table
    infra_data = [
        ['Blockchain', onchain.get('chain', 'N/A')],
        ['Consensus Mechanism', onchain.get('consensus', 'N/A')],
        ['Transaction Throughput (TPS)', onchain.get('tps', 'N/A')],
        ['Average Gas Cost', onchain.get('gas', 'N/A')],
    ]

    story.append(build_table(
        headers=['Metric', 'Specification'],
        rows=infra_data,
        col_widths=[USABLE_W * 0.35, USABLE_W * 0.65],
        styles=styles,
        first_col_bold=True,
        header_color=C('indigo')
    ))
    story.append(Spacer(1, 12))

    # Smart contracts
    contracts = onchain.get('contracts', [])
    if contracts:
        story.append(Paragraph("<b>Smart Contracts & Key Addresses</b>", styles['h3']))
        story.append(Spacer(1, 6))

        contract_rows = []
        for contract in contracts:
            contract_rows.append([
                contract.get('name', 'Unknown'),
                contract.get('address', 'N/A'),
                contract.get('purpose', '')
            ])

        story.append(build_table(
            headers=['Contract Name', 'Address', 'Purpose'],
            rows=contract_rows,
            col_widths=[USABLE_W * 0.25, USABLE_W * 0.45, USABLE_W * 0.30],
            styles=styles,
            header_color=C('indigo')
        ))
        story.append(Spacer(1, 10))

    return story


def draw_system_architecture(project_data: dict, styles: Dict) -> List:
    """Generate System Architecture section."""
    story = []

    story.extend(section_header("System Architecture", styles, "econ"))
    story.append(Spacer(1, 6))

    arch_text = project_data.get('system_architecture', '')
    if arch_text:
        story.append(Paragraph(arch_text, styles['body']))
        story.append(Spacer(1, 12))

    # Diagram description if available
    diagram_desc = project_data.get('architecture_diagram_description', '')
    if diagram_desc:
        story.append(Paragraph("<b>Architecture Diagram Description:</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(diagram_desc, styles['body_small']))
        story.append(Spacer(1, 10))

    return story


def draw_value_flow(project_data: dict, styles: Dict) -> List:
    """Generate Value Flow section."""
    story = []

    story.extend(section_header("Value Flow & Sustainability", styles, "econ"))
    story.append(Spacer(1, 6))

    # Value flow description
    value_flow = project_data.get('value_flow', {})
    value_text = value_flow.get('description', '')
    if value_text:
        story.append(Paragraph("<b>Value Flow Architecture:</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(value_text, styles['body']))
        story.append(Spacer(1, 10))

    # Revenue model
    revenue_model = value_flow.get('revenue_model', '')
    if revenue_model:
        story.append(Paragraph("<b>Revenue Model & Value Capture:</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(revenue_model, styles['body']))
        story.append(Spacer(1, 10))

    # Sustainability assessment
    sustainability = value_flow.get('sustainability', '')
    if sustainability:
        story.append(Paragraph("<b>Economic Sustainability:</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(sustainability, styles['body']))
        story.append(Spacer(1, 10))

    return story


def draw_token_economy(project_data: dict, styles: Dict) -> List:
    """Generate Token Economy section."""
    story = []

    story.extend(section_header("Token Economy", styles, "econ"))
    story.append(Spacer(1, 6))

    token_econ = project_data.get('token_economy', {})

    # Token distribution pie chart
    distribution = token_econ.get('distribution', [])
    if distribution:
        story.append(Paragraph("<b>Token Distribution</b>", styles['h3']))
        story.append(Spacer(1, 6))

        dist_labels = [d.get('category', 'Unknown') for d in distribution]
        dist_amounts = [d.get('amount', 0) for d in distribution]
        dist_percentages = [d.get('percentage', 0) for d in distribution]

        fig, ax = plt.subplots(figsize=(8, 6))
        colors_list = ['#4F46E5', '#16A34A', '#D97706',
                       '#DC2626', '#7C3AED', '#0EA5E9', '#64748B']
        wedges, texts, autotexts = ax.pie(
            dist_percentages,
            labels=dist_labels,
            autopct='%1.1f%%',
            colors=colors_list[:len(dist_labels)],
            startangle=90
        )
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(9)
            autotext.set_fontweight('bold')

        plt.tight_layout()
        story.append(chart_to_image(fig, 120, 90))
        plt.close(fig)
        story.append(Spacer(1, 12))

        # Distribution table
        dist_rows = []
        for d in distribution:
            dist_rows.append([
                d.get('category', 'Unknown'),
                f"{d.get('amount', 0):,.0f}",
                f"{d.get('percentage', 0):.1f}%",
                d.get('vesting_period', 'N/A')
            ])

        story.append(build_table(
            headers=['Category', 'Amount', 'Percentage', 'Vesting Period'],
            rows=dist_rows,
            col_widths=[USABLE_W * 0.25, USABLE_W * 0.25, USABLE_W * 0.20, USABLE_W * 0.30],
            styles=styles,
            header_color=C('indigo')
        ))
        story.append(Spacer(1, 12))

    # Vesting schedule
    vesting = token_econ.get('vesting', '')
    if vesting:
        story.append(Paragraph("<b>Vesting Schedule</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(vesting, styles['body']))
        story.append(Spacer(1, 10))

    # Inflation/Deflation
    inflation = token_econ.get('inflation_deflation', '')
    if inflation:
        story.append(Paragraph("<b>Inflation/Deflation Mechanism</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(inflation, styles['body']))
        story.append(Spacer(1, 10))

    # Token utility
    utility = token_econ.get('utility', '')
    if utility:
        story.append(Paragraph("<b>Token Utility & Use Cases</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(utility, styles['body']))
        story.append(Spacer(1, 10))

    return story


def draw_strategic_weight(project_data: dict, styles: Dict) -> List:
    """Generate Strategic Weight Framework section."""
    story = []

    story.extend(section_header("Strategic Weight Framework", styles, "econ"))
    story.append(Spacer(1, 6))

    strategic = project_data.get('strategic_weight', {})

    # Weights table
    weights = strategic.get('weights', [])
    if weights:
        weight_rows = []
        for w in weights:
            weight_rows.append([
                w.get('category', 'Unknown'),
                f"{w.get('weight', 0):.1f}%",
                w.get('rationale', '')
            ])

        story.append(build_table(
            headers=['Weight Category', 'Weight %', 'Rationale'],
            rows=weight_rows,
            col_widths=[USABLE_W * 0.25, USABLE_W * 0.15, USABLE_W * 0.60],
            styles=styles,
            header_color=C('indigo')
        ))
        story.append(Spacer(1, 12))

    # Assessment
    assessment = strategic.get('assessment', '')
    if assessment:
        story.append(Paragraph("<b>Assessment</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(assessment, styles['body']))
        story.append(Spacer(1, 10))

    return story


def draw_risks(project_data: dict, styles: Dict) -> List:
    """Generate Risk Factors section with impact/probability matrix."""
    story = []

    story.extend(section_header("Risk Factors", styles, "econ"))
    story.append(Spacer(1, 6))

    risks = project_data.get('risks', [])

    # Risk matrix scatter plot (top 5 risks)
    if risks:
        top_risks = risks[:5]

        fig, ax = plt.subplots(figsize=(8, 6))

        impact_scores = []
        probability_scores = []
        risk_names = []

        for risk in top_risks:
            impact = risk.get('impact', 0)  # 1-5
            probability = risk.get('probability', 0)  # 1-5
            name = risk.get('name', 'Risk')

            impact_scores.append(impact)
            probability_scores.append(probability)
            risk_names.append(name)

        scatter = ax.scatter(probability_scores, impact_scores, s=300, alpha=0.6,
                           c=range(len(risk_names)), cmap='YlOrRd')

        for i, name in enumerate(risk_names):
            ax.annotate(name, (probability_scores[i], impact_scores[i]),
                       fontsize=8, ha='center', va='center')

        ax.set_xlim(0, 6)
        ax.set_ylim(0, 6)
        ax.set_xlabel('Probability (1-5)', fontsize=10)
        ax.set_ylabel('Impact (1-5)', fontsize=10)
        ax.set_title('Risk Matrix', fontsize=11, fontweight='bold')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        story.append(chart_to_image(fig, 120, 90))
        plt.close(fig)
        story.append(Spacer(1, 12))

    # Risk details table
    if risks:
        risk_rows = []
        for risk in risks[:5]:  # Top 5 risks
            impact = risk.get('impact', 0)
            probability = risk.get('probability', 0)
            risk_score = impact * probability

            risk_rows.append([
                risk.get('name', 'Unknown'),
                f"{impact}/5",
                f"{probability}/5",
                f"{risk_score:.0f}",
                risk.get('description', '')
            ])

        story.append(build_table(
            headers=['Risk', 'Impact', 'Probability', 'Score', 'Description'],
            rows=risk_rows,
            col_widths=[USABLE_W * 0.15, USABLE_W * 0.10, USABLE_W * 0.12, USABLE_W * 0.10, USABLE_W * 0.53],
            styles=styles,
            header_color=C('indigo')
        ))
        story.append(Spacer(1, 10))

    return story


def draw_appendix(project_data: dict, styles: Dict) -> List:
    """Generate Appendix section."""
    story = []

    story.append(PageBreak())
    story.extend(section_header("Appendix", styles, "econ"))
    story.append(Spacer(1, 6))

    # Data sources
    story.append(Paragraph("<b>Data Sources & References</b>", styles['h3']))
    story.append(Spacer(1, 6))

    data_sources = project_data.get('data_sources', [])
    if data_sources:
        for source in data_sources:
            story.append(Paragraph(f"• {source}", styles['body_small']))
        story.append(Spacer(1, 12))
    else:
        story.append(Paragraph("No data sources specified.", styles['body_small']))
        story.append(Spacer(1, 12))

    # Disclaimer
    story.append(Spacer(1, 12))
    add_disclaimer(story, styles, 'econ')

    return story


def generate_econ_report(project_data: dict, lang: str = 'en', output_path: str = None) -> str:
    """
    Generate the Economy Design Analysis (RPT-ECON) PDF report.

    Args:
        project_data: Dictionary containing all project information
        lang: Language code ('en' or 'ko')
        output_path: Output file path for the PDF

    Returns:
        Path to the generated PDF file
    """
    if output_path is None:
        project_name = project_data.get('project_name', 'Project')
        token_symbol = project_data.get('token_symbol', 'TOKEN')
        slug = project_data.get('slug', project_name.lower().replace(' ', '-'))
        version = project_data.get('version', 1)
        output_path = os.path.join(os.path.dirname(__file__), 'output',
                                   report_filename(slug, 'econ', version, 'en'))

    # Create document
    doc = create_doc(output_path)

    # Create styles
    styles = make_styles()

    # Build story
    story = []

    # 1. Cover page
    project_name = project_data.get('project_name', 'Project')
    token_symbol = project_data.get('token_symbol', 'TOKEN')
    rating = project_data.get('overall_rating', 'N/A')
    version = project_data.get('version', 1)

    # Extract key metrics for cover
    identity = project_data.get('identity', {})
    key_metrics = identity.get('key_metrics', [])

    # Cover page handled by onFirstPage callback; just skip to next page
    story.append(PageBreak())

    # 2. Executive Summary
    story.extend(section_header("Executive Summary", styles, "econ"))
    story.append(Spacer(1, 6))

    exec_summary = project_data.get('executive_summary', '')
    story.append(Paragraph(exec_summary, styles['body']))
    story.append(Spacer(1, 10))

    # Overall Rating
    rating_text = f"<b>Overall Rating: <font color='#4F46E5' size=14>{rating}</font></b>"
    story.append(Paragraph(rating_text, styles['body']))
    story.append(Spacer(1, 6))
    story.append(thin_line())
    story.append(PageBreak())

    # 3. Project Identity
    story.extend(section_header("Project Identity", styles, "econ"))
    story.append(Spacer(1, 6))

    overview = identity.get('overview', '')
    if overview:
        story.append(Paragraph(overview, styles['body']))
        story.append(Spacer(1, 10))

    # Team info
    team_info = identity.get('team_info', '')
    if team_info:
        story.append(Paragraph("<b>Team & Leadership</b>", styles['h3']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(team_info, styles['body']))
        story.append(Spacer(1, 10))

    # Key metrics table
    if key_metrics:
        story.append(Paragraph("<b>Key Metrics</b>", styles['h3']))
        story.append(Spacer(1, 6))

        metric_rows = []
        for metric in key_metrics:
            metric_rows.append([
                metric.get('label', ''),
                metric.get('value', '')
            ])

        story.append(build_table(
            headers=['Metric', 'Value'],
            rows=metric_rows,
            col_widths=[USABLE_W * 0.40, USABLE_W * 0.60],
            styles=styles,
            first_col_bold=True,
            header_color=C('indigo')
        ))
        story.append(Spacer(1, 10))

    story.append(PageBreak())

    # 4. Tech Pillars
    story.extend(draw_tech_pillars(project_data, styles))
    story.append(PageBreak())

    # 5. On-Chain Infra
    story.extend(draw_onchain_infra(project_data, styles))
    story.append(PageBreak())

    # 6. System Architecture
    story.extend(draw_system_architecture(project_data, styles))
    story.append(PageBreak())

    # 7. Value Flow
    story.extend(draw_value_flow(project_data, styles))
    story.append(PageBreak())

    # 8. Token Economy
    story.extend(draw_token_economy(project_data, styles))
    story.append(PageBreak())

    # 9. Strategic Weight
    story.extend(draw_strategic_weight(project_data, styles))
    story.append(PageBreak())

    # 10. Risk Factors
    story.extend(draw_risks(project_data, styles))

    # 11. Appendix
    story.extend(draw_appendix(project_data, styles))

    # Build PDF with cover + header/footer
    later_pages = make_header_footer(project_name, 'econ')

    def first_page(c, doc):
        version = project_data.get('version', 1)
        draw_cover_econ_mat(c, doc, project_name, 'econ', version, lang,
                           subtitle=project_data.get('executive_summary', '')[:80],
                           key_metrics=None, rating=project_data.get('overall_rating'))

    doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)

    return output_path


if __name__ == '__main__':
    # Sample data for testing
    sample_data = {
        'project_name': 'HeyElsa AI',
        'token_symbol': 'ELSA',
        'slug': 'heyelsaai',
        'version': 1,
        'overall_rating': 'A',
        'executive_summary': """
            HeyElsa AI is an advanced conversational AI platform leveraging blockchain technology for decentralized model training and inference.
            The project combines state-of-the-art language models with tokenized incentive mechanisms, enabling community-driven AI development.
            Token economics are designed to balance user acquisition, model contributor incentives, and platform sustainability.
            The analysis reveals strong technical foundations with S-tier architecture, solid value flow design, and manageable risk profile.
        """,
        'identity': {
            'overview': """
                HeyElsa AI represents a novel approach to democratizing AI development through blockchain-based collaboration.
                Founded in 2024, the platform enables distributed participants to contribute computational resources, training data, and model improvements
                in exchange for ELSA token rewards. The protocol's governance structure ensures community control over model development roadmap.
            """,
            'team_info': """
                Led by experienced AI researchers and blockchain engineers. CEO Jane Smith previously worked at leading AI labs.
                CTO David Chen brings 15+ years of distributed systems expertise. Advisory board includes prominent figures from both AI and crypto communities.
            """,
            'key_metrics': [
                {'label': 'Total Token Supply', 'value': '1,000,000,000 ELSA'},
                {'label': 'Current Market Cap', 'value': '$150M USD'},
                {'label': 'Active Contributors', 'value': '50,000+'},
                {'label': 'Average Daily Transactions', 'value': '2.3M'},
                {'label': 'Model Accuracy (Benchmark)', 'value': '94.2%'},
            ]
        },
        'tech_pillars': [
            {
                'name': 'AI/ML Infrastructure',
                'score': 92,
                'analysis': """
                    HeyElsa employs state-of-the-art transformer architectures with custom optimization for distributed inference.
                    Multi-GPU coordination through proprietary sharding mechanism enables efficient model inference across 5,000+ nodes.
                    Regular benchmark testing against industry standards confirms performance superiority in 9 out of 12 key metrics.
                """
            },
            {
                'name': 'Blockchain Layer',
                'score': 85,
                'analysis': """
                    Built on Ethereum with custom rollup solution (Elsa Layer 2) achieving 10,000 TPS throughput.
                    Smart contracts implement Byzantine fault-tolerant consensus for model validation and reward distribution.
                    Security audited by top-tier firms; no critical vulnerabilities found in last 12 months.
                """
            },
            {
                'name': 'Incentive Mechanism Design',
                'score': 88,
                'analysis': """
                    Sophisticated game-theoretic reward system balances model quality, participation cost, and token inflation.
                    Quadratic voting mechanism prevents whale dominance in governance. Reputation scores tied to long-term contribution history.
                    Economic simulations indicate sustainable growth trajectory over 10-year planning horizon.
                """
            },
            {
                'name': 'Data & Privacy',
                'score': 79,
                'analysis': """
                    Implements differential privacy for federated learning with cryptographic guarantees.
                    Zero-knowledge proofs enable data contribution verification without exposing sensitive information.
                    Privacy compliance verified against GDPR and regional regulations; ongoing audit by third-party firm.
                """
            }
        ],
        'onchain_infra': {
            'chain': 'Ethereum Mainnet + Elsa L2 Rollup',
            'consensus': 'Proof-of-Stake (ETH) with custom validator set',
            'tps': '10,000 TPS (Layer 2)',
            'gas': '$0.001 - $0.01 per transaction (L2)',
            'contracts': [
                {
                    'name': 'ELSAToken',
                    'address': '0x1234567890abcdef...',
                    'purpose': 'ERC-20 token contract with minting/burning'
                },
                {
                    'name': 'RewardPool',
                    'address': '0xfedcba0987654321...',
                    'purpose': 'Manages contributor rewards and distributions'
                },
                {
                    'name': 'ModelRegistry',
                    'address': '0xabcdef1234567890...',
                    'purpose': 'Registers and versions AI models on-chain'
                }
            ]
        },
        'system_architecture': """
            The system architecture comprises four integrated layers: (1) AI Compute Layer with distributed inference nodes,
            (2) Smart Contract Layer handling token transfers and governance, (3) Consensus Layer ensuring data integrity,
            and (4) Client Application Layer providing user interface. Data flows unidirectionally through each layer with
            cryptographic commitments at layer boundaries ensuring atomicity of cross-layer operations.
            The architecture achieves 99.99% uptime through redundancy and automated failover mechanisms.
        """,
        'architecture_diagram_description': """
            [Architectural diagram would show vertical stack of four layers with bidirectional data flows indicated by arrows,
            color-coded by layer function: blue for compute, green for contracts, orange for consensus, purple for applications]
        """,
        'value_flow': {
            'description': """
                Value flows from end-users who purchase model inference services in ELSA tokens.
                50% of transaction fees flow to model contributors (distributed by contribution quality score).
                20% directed to protocol treasury for infrastructure and development.
                15% allocated to token holders via staking rewards.
                15% reserved for governance voting incentives.
                The design creates positive feedback loop: user adoption increases token utility, increasing token value,
                attracting contributors, improving model quality, driving further adoption.
            """,
            'revenue_model': """
                Primary revenue: Pay-per-use inference pricing (variable based on model complexity).
                Secondary revenue: Premium API access with SLA guarantees ($10K-$100K/month).
                Tertiary revenue: White-label model deployment for enterprise partners ($500K+).
                Quaternary revenue: Trading fees on ELSA/stablecoin DEX pair (0.25% spread).
                All revenue streams route through smart contract treasury, ensuring transparent auditing.
            """,
            'sustainability': """
                Sustainability analysis indicates 8-year runway at current burn rate with existing treasury.
                Protocol token inflation (3% annual) offsets by 40% of transaction volume growth projections.
                Elasticity modeling suggests protocol achieves break-even at $500M annualized inference volume (achievable by 2027 given current 2x QoQ growth).
            """
        },
        'token_economy': {
            'distribution': [
                {
                    'category': 'Community Rewards',
                    'amount': 500_000_000,
                    'percentage': 50.0,
                    'vesting_period': '4 years linear'
                },
                {
                    'category': 'Team & Advisors',
                    'amount': 150_000_000,
                    'percentage': 15.0,
                    'vesting_period': '4 years with 1-year cliff'
                },
                {
                    'category': 'Protocol Treasury',
                    'amount': 200_000_000,
                    'percentage': 20.0,
                    'vesting_period': 'Unlocked (governance-controlled)'
                },
                {
                    'category': 'Public Sale',
                    'amount': 150_000_000,
                    'percentage': 15.0,
                    'vesting_period': 'Fully liquid'
                }
            ],
            'vesting': """
                Community rewards vest linearly over 4 years post-genesis block.
                Team allocation subject to 1-year cliff then 36-month linear vesting.
                Treasury tokens remain locked in multi-sig requiring 5-of-7 governance vote for release.
                Public sale tokens fully liquid at token generation event.
            """,
            'inflation_deflation': """
                Year 1-4: 3% annual inflation reducing to 1% by year 5.
                Deflation mechanisms: 0.1% of all transaction fees burned permanently.
                Estimated net inflation (inflation - deflation) stabilizes at 1.2% annually by year 5.
                Protocol governance can adjust inflation via DAO vote with 48-hour timelock.
            """,
            'utility': """
                Governance: ELSA holders vote on protocol upgrades, fee structure, and treasury allocation.
                Staking: Lock ELSA to earn portion of transaction fees (target APY: 8-15%).
                Model evaluation: Contributors stake ELSA to validate model submissions (slashing for false votes).
                Premium services: Higher ELSA balances unlock faster inference queue and priority support.
                Trading: ELSA pairs with USDC and ETH on major DEXes with $50M+ daily volume.
            """
        },
        'strategic_weight': {
            'weights': [
                {
                    'category': 'Technology & Innovation',
                    'weight': 30.0,
                    'rationale': 'Core competitive advantage in AI accuracy and throughput'
                },
                {
                    'category': 'Token Economics',
                    'weight': 25.0,
                    'rationale': 'Sustainability and long-term growth incentives'
                },
                {
                    'category': 'Market Position',
                    'weight': 20.0,
                    'rationale': 'User adoption and competitive moat'
                },
                {
                    'category': 'Risk Management',
                    'weight': 15.0,
                    'rationale': 'Downside protection and systemic risk mitigation'
                },
                {
                    'category': 'Team & Governance',
                    'weight': 10.0,
                    'rationale': 'Execution capability and decentralization trajectory'
                }
            ],
            'assessment': """
                HeyElsa AI achieves above-average scores across all weight categories.
                Technology strength (92/100) provides substantial moat against competitors.
                Token economics design (88/100) balances sustainability with incentive alignment.
                Market position shows strong growth trajectory with no dominant competitors in niche.
                Risk profile manageable with identified mitigations for top 5 risks.
                Overall project exhibits institutional-grade execution and strategic clarity.
            """
        },
        'risks': [
            {
                'name': 'Regulatory Uncertainty',
                'impact': 4,
                'probability': 3,
                'description': 'AI regulatory frameworks in development globally could impact token classification or model deployment. Mitigation: Active engagement with policymakers; legal hedges across jurisdictions.'
            },
            {
                'name': 'Model Quality Degradation',
                'impact': 3,
                'probability': 2,
                'description': 'Poor data contributions could reduce model accuracy below benchmarks. Mitigation: Rigorous validation mechanism with reputation scoring; regular retraining with curated datasets.'
            },
            {
                'name': 'Token Liquidity Risk',
                'impact': 3,
                'probability': 2,
                'description': 'Low trading volume on secondary markets could limit exit liquidity. Mitigation: Market-making partnerships; exchange listings on top-tier platforms planned for Q2 2026.'
            },
            {
                'name': 'Smart Contract Vulnerabilities',
                'impact': 5,
                'probability': 1,
                'description': 'Undiscovered bugs in core contracts could enable value extraction. Mitigation: Formal verification underway; bug bounty program with $500K fund; multi-sig safeguards.'
            },
            {
                'name': 'Competitive Emergence',
                'impact': 3,
                'probability': 4,
                'description': 'Well-funded competitors could replicate model with superior execution. Mitigation: First-mover advantages in community and data; continuous innovation; potential strategic partnerships/acquisitions.'
            }
        ],
        'data_sources': [
            'HeyElsa AI Whitepaper v2.3 (2024-12-15)',
            'On-chain data from Etherscan and Dune Analytics',
            'Team interviews and strategic documentation',
            'Independent model benchmarking against HELM and SuperGLUE standards',
            'Third-party smart contract security audit (CertiK, 2024-10)',
            'Community survey (n=5,000 active users, 2024-11)',
            'Comparable project analysis (OpenAI, Anthropic, Hugging Face)',
            'Macroeconomic analysis and growth projections by BCE Lab Research'
        ]
    }

    # Generate report
    output = generate_econ_report(sample_data, lang='en')
    print(f"Report generated: {output}")
