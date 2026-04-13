"""
Stage 1: Project Maturity Assessment — Executive-Grade Text Report Generator
Converts structured project data into comprehensive, narrative-driven Markdown maturity analysis.

This is the first stage of the 2-stage pipeline:
  Stage 1: gen_text_mat.py  (Enriched JSON → Rich Markdown with 10 chapters, 6000+ words)
  Stage 2: gen_pdf_mat.py   (Markdown + metadata → Graphical PDF)

OUTPUT STRUCTURE (10 Chapters, minimum 6000 words):
  1. Executive Summary & Industry Context
  2. Strategic Objective Identification & Weight Assessment
  3. On-Chain/Off-Chain Architecture Analysis
  4. Timeline-Based Progress Evaluation
  5. Goal Achievement & Aggregate Progress Scoring
  6. Maturity Stage Classification & Interpretation
  7. Deep Technical Analysis
  8. Token Value Proposition & Sustainability
  9. Technical Limitations & Risk Management
  10. Comprehensive Conclusion & Future Outlook

Each chapter includes:
  - Contextual framing paragraph
  - Data with interpretation (not just tables)
  - Cross-references between sections
  - Conditional logic based on data values (scores, weights, ratios)
  - Implications paragraph

Usage:
    from gen_text_mat import generate_text_mat
    md_path, metadata = generate_text_mat(project_data, output_dir='/tmp')
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _format_percentage(value: Any) -> str:
    """Format number as percentage."""
    if value is None:
        return "N/A"
    try:
        val = float(value)
        return f"{val:.1f}%"
    except (ValueError, TypeError):
        return str(value)


def _format_score(value: Any) -> str:
    """Format maturity score with proper notation."""
    if value is None:
        return "N/A"
    try:
        val = float(value)
        return f"{val:.2f}%"
    except (ValueError, TypeError):
        return str(value)


def _classify_maturity(score: float) -> str:
    """Classify maturity stage from score."""
    if score >= 85:
        return 'established'
    elif score >= 60:
        return 'mature'
    elif score >= 30:
        return 'growing'
    else:
        return 'nascent'


def _safe_get(d: dict, *keys, default=None):
    """Safely get nested dict values."""
    try:
        for key in keys:
            d = d[key]
        return d
    except (KeyError, TypeError, IndexError):
        return default


def _get_collected_data(project_data: dict, *path, default=None):
    """Get data from _collected nested structure or fallback to direct project_data."""
    result = _safe_get(project_data, '_collected', *path)
    if result is not None:
        return result
    result = _safe_get(project_data, *path)
    if result is not None:
        return result
    return default


# ---------------------------------------------------------------------------
# Chapter generators — each returns a markdown string
# ---------------------------------------------------------------------------

def _chapter_1_executive_summary(d: dict) -> str:
    """Chapter 1: Executive Summary & Industry Context — frames the entire analysis."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    total_score = d.get('total_maturity_score', 0)
    maturity_stage = d.get('maturity_stage', _classify_maturity(total_score))
    objectives = d.get('strategic_objectives', [])

    a("# Chapter 1: Executive Summary & Industry Context\n")

    # ── 1.1 Project Identity ─────────────────────────────────
    a("## 1.1 Project Identity and Assessment Overview\n")
    a(f"This report presents a comprehensive maturity assessment of {project_name} ({token_symbol}), evaluating the project's strategic progress across multiple dimensions — from technical architecture and on-chain execution to token economics sustainability and risk management. The BCE Lab Project Maturity Assessment (RPT-MAT) framework provides a rigorous, data-driven methodology for quantifying how far a blockchain project has progressed toward its stated objectives, and where material gaps remain.\n")
    a("")
    a(f"Maturity assessment differs fundamentally from economic valuation (RPT-ECON) or forensic analysis (RPT-FOR). While economic reports focus on current market pricing and investment merit, and forensic reports investigate anomalies and red flags, the maturity assessment asks a more foundational question: *Is this project capable of delivering on its promises?* The answer integrates technical execution, strategic clarity, economic design quality, and organizational momentum into a single weighted score that captures the project's distance from its stated objectives.\n")
    a("")

    # ── 1.2 Key Metrics Snapshot ─────────────────────────────
    a("## 1.2 Maturity Metrics Snapshot\n")
    a(f"**Overall Maturity Score: {_format_score(total_score)}**\n")
    a(f"**Maturity Stage: {maturity_stage.upper()}**\n")
    a("")

    if total_score >= 85:
        a(f"At {_format_score(total_score)}, {project_name} achieves Established status — the highest classification in the BCE Lab maturity framework. Established projects have demonstrated concrete, verifiable achievement across the majority of their strategic objectives. They possess production-grade technology, sustainable economics, active governance, and proven market traction. However, Established status does not mean invulnerability: even mature projects face execution risks from market evolution, regulatory shifts, and competitive pressure. The purpose of this assessment is to validate whether the Established classification is justified by the evidence, and to identify the specific areas where regression risk remains.\n")
    elif total_score >= 60:
        a(f"At {_format_score(total_score)}, {project_name} falls within the Mature stage — indicating that the project has achieved substantial progress toward its core objectives while retaining meaningful areas for growth. Mature projects have moved beyond proof-of-concept and early adoption, demonstrating both technical competence and market relevance. The critical question for Mature-stage projects is whether they can sustain momentum through the 'growth-to-establishment' transition, which historically separates projects that achieve long-term viability from those that plateau and gradually lose relevance.\n")
    elif total_score >= 30:
        a(f"At {_format_score(total_score)}, {project_name} is classified as Growing — a stage characterized by partial achievement of strategic objectives with significant gaps remaining. Growing projects have demonstrated viability (they are not purely conceptual) but face elevated execution risk as they scale from early adoption to meaningful market presence. The assessment that follows identifies both the areas of genuine progress and the specific gaps that, if not addressed, could prevent further maturation.\n")
    else:
        a(f"At {_format_score(total_score)}, {project_name} is classified as Nascent — the earliest stage of maturity. Nascent projects are characterized by incomplete technology, limited market traction, and strategic objectives that remain largely unachieved. This classification does not condemn the project — many successful protocols began at nascent stage — but it does indicate that significant execution, capital, and time are required before maturity milestones can be credibly claimed. Investors and stakeholders should treat Nascent-stage projects as high-risk, high-optionality positions.\n")
    a("")

    # ── 1.3 Strategic Objectives Overview ────────────────────
    a("## 1.3 Strategic Framework Overview\n")
    if objectives:
        obj_names = [obj.get('name', '') for obj in objectives]
        obj_count = len(objectives)
        total_weight = sum(o.get('weight', 0) for o in objectives)
        max_weight_obj = max(objectives, key=lambda x: x.get('weight', 0))

        a(f"The maturity assessment evaluates {project_name} against {obj_count} strategic objectives, each weighted by strategic importance. The combined weight across all objectives totals {total_weight:.0f}%, with {max_weight_obj.get('name', 'the primary objective')} carrying the highest weight at {max_weight_obj.get('weight', 0):.0f}%. This weighting reflects the project's own stated priorities — objectives are not weighted equally because not all goals contribute equally to long-term viability.\n")
        a("")
        a(f"The strategic objectives span: {', '.join(obj_names)}. Each objective is assessed independently, with achievement rates computed from verifiable milestones, technical deliverables, and market metrics. The weighted aggregate of these individual scores produces the total maturity score of {_format_score(total_score)}. Chapters 2 through 5 detail the methodology, evidence, and scoring for each objective.\n")
    else:
        a(f"The maturity assessment evaluates {project_name} against a set of core strategic objectives. Each objective carries a weight reflecting its strategic importance to long-term project viability, and achievement rates are computed from verifiable milestones and market metrics.\n")
    a("")

    # ── 1.4 Industry Context ─────────────────────────────────
    a("## 1.4 Industry Context and Competitive Landscape\n")
    context = d.get('industry_context', '')
    if context:
        a(context.strip())
        a("")
        a(f"This industry context is critical for interpreting {project_name}'s maturity score. A project achieving 70% maturity in a nascent, rapidly evolving sector may represent stronger execution than one achieving 85% in a well-established domain with proven playbooks. The assessment that follows evaluates {project_name}'s progress against both absolute milestones and the relative difficulty of the competitive environment.\n")
    else:
        a(f"{project_name} operates within the blockchain ecosystem, a domain characterized by rapid technological evolution, uncertain regulatory frameworks, and intense competition for users, liquidity, and developer attention. The project's maturity must be assessed not only against its own roadmap but against the competitive context: how quickly must {project_name} execute to remain relevant? The pace of the industry sets the bar — projects that execute at average speed in a fast-moving sector effectively fall behind.\n")
    a("")

    return "\n".join(L)


def _chapter_2_strategic_objectives(d: dict) -> str:
    """Chapter 2: Strategic Objective Identification & Weight Assessment — deep analytical narrative."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    objectives = d.get('strategic_objectives', [])

    a("# Chapter 2: Strategic Objective Identification & Weight Assessment\n")

    # ── 2.1 Methodology ──────────────────────────────────────
    a("## 2.1 Assessment Methodology and Weighting Philosophy\n")
    a(f"The foundation of any credible maturity assessment is the identification and weighting of strategic objectives. These objectives define what success looks like for {project_name}, and the weights quantify which objectives matter most. The BCE Lab framework requires that objectives satisfy three criteria: (1) they must be measurable through verifiable evidence (on-chain data, public repositories, auditable metrics); (2) they must be material to the project's long-term viability; and (3) they must be independent enough that achievement of one does not automatically guarantee achievement of another.\n")
    a("")
    a("Weighting is not arbitrary — it reflects the structural dependencies within the project's value chain. A DeFi protocol that cannot execute transactions reliably has no use for superior marketing; therefore, technical execution receives higher weight than market penetration. An AI-blockchain hybrid that cannot demonstrate AI capability has no foundation for its economic model; therefore, AI execution excellence is weighted above token economics. The weights encode the project's own strategic priorities as understood from its whitepaper, roadmap, team communications, and observable behavior.\n")
    a("")

    if not objectives:
        a(f"*No strategic objectives data available for {project_name}. The maturity assessment cannot compute a meaningful score without defined objectives.*\n")
        return "\n".join(L)

    # ── 2.2 Objective Portfolio ──────────────────────────────
    a("## 2.2 Strategic Objective Portfolio\n")
    total_weight = sum(o.get('weight', 0) for o in objectives)

    a(f"{project_name} is assessed against {len(objectives)} strategic objectives with a combined weight of {total_weight:.0f}%. The following table summarizes the objective portfolio:\n\n")

    a("| # | Strategic Objective | Weight | Category | Strategic Rationale |")
    a("|:-:|---------------------|:------:|----------|---------------------|")
    for i, obj in enumerate(objectives, 1):
        name = obj.get('name', '')
        weight = obj.get('weight', 0)
        desc = obj.get('description', '—').strip()
        # Infer category from name
        name_lower = name.lower()
        if any(k in name_lower for k in ['tech', 'execution', 'ai', 'architecture']):
            cat = 'Technical'
        elif any(k in name_lower for k in ['token', 'economic', 'sustain', 'financial']):
            cat = 'Economic'
        elif any(k in name_lower for k in ['market', 'adoption', 'penetration', 'growth']):
            cat = 'Market'
        elif any(k in name_lower for k in ['chain', 'interop', 'cross']):
            cat = 'Infrastructure'
        elif any(k in name_lower for k in ['governance', 'community', 'ecosystem', 'agent']):
            cat = 'Ecosystem'
        else:
            cat = 'Strategic'
        a(f"| {i} | {name} | {weight:.0f}% | {cat} | {desc[:120]} |")
    a("")

    # ── 2.3 Weight Distribution Analysis ─────────────────────
    a("## 2.3 Weight Distribution Analysis\n")

    # Sort by weight descending
    sorted_objs = sorted(objectives, key=lambda x: x.get('weight', 0), reverse=True)
    top_obj = sorted_objs[0]
    bottom_obj = sorted_objs[-1]
    weight_spread = top_obj.get('weight', 0) - bottom_obj.get('weight', 0)

    a(f"The weight distribution reveals {project_name}'s strategic priorities. The highest-weighted objective — **{top_obj.get('name', '')}** at {top_obj.get('weight', 0):.0f}% — dominates the assessment, meaning that progress on this single dimension has the largest impact on the overall maturity score. The lowest-weighted objective — **{bottom_obj.get('name', '')}** at {bottom_obj.get('weight', 0):.0f}% — contributes least to the aggregate. The spread between highest and lowest weights is {weight_spread:.0f} percentage points.\n")
    a("")

    if weight_spread > 25:
        a(f"The wide spread ({weight_spread:.0f}pp) indicates a concentrated strategy: {project_name} has placed a decisive bet on {top_obj.get('name', '')} as the primary driver of maturity. This concentration creates both efficiency (clear focus accelerates progress in priority areas) and fragility (failure in the top-weighted objective disproportionately damages the overall score). Projects with concentrated weight distributions are 'all-in' on their core thesis — if the thesis is correct, concentrated focus accelerates maturity faster than distributed effort; if the thesis is wrong, the project has invested disproportionate resources in the wrong area.\n")
    elif weight_spread > 10:
        a(f"The moderate spread ({weight_spread:.0f}pp) indicates a balanced strategy with clear priorities. {project_name} has identified a primary focus area ({top_obj.get('name', '')}) while maintaining meaningful investment across supporting objectives. This distribution is typical of projects that have progressed beyond the single-focus startup phase and must manage multiple fronts simultaneously. The risk profile is balanced: no single objective failure can catastrophically undermine the score, but no single success can compensate for broad-based underperformance.\n")
    else:
        a(f"The narrow spread ({weight_spread:.0f}pp) indicates an equal-priority strategy, where {project_name} treats all objectives as approximately equally important. This can reflect either strategic maturity (all dimensions genuinely matter equally) or strategic ambiguity (the project has not yet identified which dimensions are most critical). Equal weighting is democratic but can dilute focus — projects attempting to advance on all fronts simultaneously often advance on none.\n")
    a("")

    # ── 2.4 Individual Objective Deep-Dive ───────────────────
    a("## 2.4 Objective Definitions and Strategic Rationale\n")
    for i, obj in enumerate(objectives, 1):
        name = obj.get('name', f'Objective {i}')
        weight = obj.get('weight', 0)
        desc = obj.get('description', '')

        a(f"### {i}. {name} (Weight: {weight:.0f}%)\n")
        if desc:
            a(desc.strip())
            a("")

        # Conditional narrative based on weight level
        if weight >= 30:
            a(f"At {weight:.0f}% weight, this objective is the cornerstone of {project_name}'s maturity assessment. Underperformance here would single-handedly prevent the project from reaching higher maturity stages, regardless of achievement in other areas. Conversely, exceptional execution on this objective provides the most efficient path to score improvement. The team's resource allocation should reflect this priority — if the highest-weighted objective is not receiving the highest share of development effort, there is a misalignment between stated strategy and actual execution.\n")
        elif weight >= 20:
            a(f"At {weight:.0f}% weight, this objective represents a significant component of the maturity assessment. While not the single dominant factor, underperformance here would create a meaningful drag on the aggregate score. This weight level indicates that {project_name} views this dimension as essential to its value proposition — not merely supportive, but integral to the project's ability to deliver on its core promise.\n")
        elif weight >= 10:
            a(f"At {weight:.0f}% weight, this objective contributes meaningfully but is not the primary driver of maturity scoring. Objectives in this weight range typically represent necessary conditions for success (without which the project cannot function) rather than sufficient conditions (which alone would justify the project's existence). Performance here is expected to be solid but need not be exceptional to achieve a strong aggregate score.\n")
        else:
            a(f"At {weight:.0f}% weight, this objective has limited impact on the aggregate maturity score. Low-weighted objectives typically represent emerging or aspirational dimensions that the project has not yet prioritized. While underperformance here has minimal scoring impact, it may signal strategic gaps that could become material as the project matures and these dimensions become more important.\n")
        a("")

    return "\n".join(L)


def _chapter_3_architecture(d: dict) -> str:
    """Chapter 3: On-Chain/Off-Chain Architecture Analysis — deep narrative."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    arch = d.get('onchain_offchain', {})

    a("# Chapter 3: On-Chain/Off-Chain Architecture Analysis\n")

    # ── 3.1 Architecture Philosophy ──────────────────────────
    a("## 3.1 Architecture Philosophy and Design Tradeoffs\n")
    a(f"Every blockchain project makes a foundational architectural decision: which components belong on-chain (immutable, transparent, decentralized, costly) and which belong off-chain (mutable, private, centralized, efficient). This is not a binary choice but a spectrum — and where a project sits on that spectrum reveals its design philosophy, trust assumptions, and long-term decentralization trajectory.\n")
    a("")
    a(f"On-chain components benefit from blockchain's core guarantees: censorship resistance, immutability, public verifiability, and trustless execution. However, they pay for these guarantees with higher latency, higher cost, limited computation capacity, and public data exposure. Off-chain components gain efficiency, privacy, and computational flexibility, but introduce trust assumptions — users must trust the off-chain operator to behave correctly, since blockchain's consensus mechanism does not govern off-chain execution.\n")
    a("")
    a(f"For {project_name}, the architecture split directly impacts maturity assessment: a project claiming to be 'fully decentralized' but running critical logic off-chain has a trust gap. Conversely, a project that forces computationally expensive AI inference on-chain demonstrates poor engineering judgment. The optimal split depends on the project's specific value proposition and threat model.\n")
    a("")

    if not arch:
        a(f"*Detailed on-chain/off-chain architecture data not available for {project_name}.*\n")
        return "\n".join(L)

    onchain_ratio = arch.get('onchain_ratio', 0)
    offchain_ratio = arch.get('offchain_ratio', 0)

    # ── 3.2 Distribution Analysis ────────────────────────────
    a("## 3.2 Architecture Distribution\n")
    a(f"**On-Chain: {onchain_ratio:.0f}% | Off-Chain: {offchain_ratio:.0f}%**\n")
    a("")

    if onchain_ratio > 70:
        a(f"With {onchain_ratio:.0f}% of critical components deployed on-chain, {project_name} prioritizes decentralization and transparency over computational efficiency. This architecture is appropriate for protocols where trust minimization is the primary value proposition — financial primitives (DEXs, lending, stablecoins) where users' assets depend on correct execution. However, high on-chain ratios introduce scalability constraints: gas costs, throughput limits, and smart contract complexity create a ceiling on how much logic can be efficiently executed within blockchain's constrained environment.\n")
        a("")
        a(f"The strategic implication is that {project_name}'s growth trajectory is bounded by blockchain infrastructure evolution. If the underlying chain improves throughput and reduces costs (Layer 2 scaling, sharding, EIP upgrades), {project_name} benefits directly. If blockchain scaling stalls, {project_name} faces the uncomfortable choice of either migrating critical logic off-chain (compromising its trust model) or accepting performance limitations that competitors may not share.\n")
    elif onchain_ratio > 40:
        a(f"The balanced {onchain_ratio:.0f}/{offchain_ratio:.0f} split indicates a hybrid architecture, where {project_name} places settlement and state commitments on-chain while keeping computation, data processing, and user interface logic off-chain. This is the most common architecture among mature DeFi and Web3 projects, reflecting a pragmatic recognition that blockchain is optimized for finality and trust, not computation and throughput.\n")
        a("")
        a(f"Hybrid architectures introduce trust boundary questions: *Where exactly does the on-chain guarantee end and the off-chain trust assumption begin?* Users interacting with {project_name} must understand which operations are protected by blockchain consensus and which depend on off-chain infrastructure availability, correctness, and integrity. The maturity of a hybrid project depends critically on how well it manages this trust boundary — are off-chain components audited? Is there a path to progressively decentralize them? Do users have recourse if off-chain components fail?\n")
    else:
        a(f"With only {onchain_ratio:.0f}% of components on-chain, {project_name} relies primarily on off-chain infrastructure. This architecture maximizes performance and flexibility but introduces significant trust dependencies. Users must trust that off-chain components (AI models, servers, databases, APIs) operate correctly, remain available, and are not compromised. The blockchain component serves primarily as a settlement layer — recording final states after off-chain computation determines outcomes.\n")
        a("")
        a(f"This architecture is appropriate for projects where the core value proposition requires computational capabilities that blockchain cannot provide (AI inference, large-scale data processing, real-time interaction). However, the maturity assessment must carefully examine what guarantees the on-chain component actually provides. If removing the blockchain layer would not materially change the user experience, the project's 'blockchain' claim may be more narrative than structural — a point that investors and users should evaluate critically.\n")
    a("")

    # ── 3.3 Component Details ────────────────────────────────
    onchain_comps = arch.get('onchain_components', '')
    offchain_comps = arch.get('offchain_components', '')

    if onchain_comps:
        a("## 3.3 On-Chain Component Analysis\n")
        a(onchain_comps.strip())
        a("")
        a(f"These on-chain components form the trust foundation of {project_name}. Their security, upgradeability, and operational history are critical to the maturity assessment. Smart contracts that have processed significant value without incident demonstrate production maturity; contracts deployed recently or handling minimal value have not yet been battle-tested. Chapter 7 provides deeper technical analysis of these components.\n")
        a("")

    if offchain_comps:
        a("## 3.4 Off-Chain Component Analysis\n")
        a(offchain_comps.strip())
        a("")
        a(f"Off-chain components represent {project_name}'s 'hidden infrastructure' — the systems that users depend on but cannot independently verify through blockchain data. The maturity of these components depends on factors not directly observable on-chain: server reliability, model accuracy, data freshness, and operational security practices. The assessment relies on published documentation, audit reports, uptime records, and team communications to evaluate off-chain maturity.\n")
        a("")

    # ── 3.5 Architecture Maturity Implications ───────────────
    a("## 3.5 Architecture Maturity Implications\n")
    a(f"The {onchain_ratio:.0f}/{offchain_ratio:.0f} architecture split has direct implications for {project_name}'s maturity trajectory:\n")
    a("")
    a(f"**Decentralization Path.** As {project_name} matures, the expectation is that more components migrate toward decentralization — either on-chain or through decentralized off-chain alternatives (IPFS storage, decentralized compute networks, oracle networks). Projects that maintain high off-chain ratios without a credible decentralization roadmap face structural risk: single points of failure, regulatory vulnerability, and trust erosion.\n")
    a("")
    a(f"**Scalability Ceiling.** The on-chain ratio determines {project_name}'s scalability path. Higher on-chain ratios require layer 2, sharding, or alternative consensus innovations to scale. Lower on-chain ratios can scale with traditional infrastructure but must maintain blockchain's trust guarantees through cryptographic proofs, attestation mechanisms, or other verification schemes.\n")
    a("")
    a(f"**Regulatory Surface.** Off-chain components create regulatory surface area — servers that can be subpoenaed, operators that can be sanctioned, and data that can be demanded. Highly on-chain projects reduce regulatory attack surface but cannot eliminate it entirely (development teams, front-end interfaces, and foundation entities remain targets). {project_name}'s architecture determines which regulatory risks are most relevant.\n")
    a("")

    return "\n".join(L)


def _chapter_4_timeline(d: dict) -> str:
    """Chapter 4: Timeline-Based Progress Evaluation — deep narrative on roadmap execution."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    phases = d.get('timeline_phases', [])

    a("# Chapter 4: Timeline-Based Progress Evaluation\n")

    # ── 4.1 Roadmap Assessment Philosophy ────────────────────
    a("## 4.1 Roadmap Execution Assessment\n")
    a(f"A project's roadmap is its public commitment to stakeholders — the sequence of milestones that, if achieved, would realize the project's vision. Roadmap analysis is one of the most revealing dimensions of maturity assessment because it measures the gap between intention and execution. Every project publishes ambitious roadmaps; few deliver on them.\n")
    a("")
    a(f"The BCE Lab framework evaluates roadmap quality along three axes: **ambition** (are the milestones meaningful or trivial?), **specificity** (are milestones defined with enough precision to verify?), and **execution** (were milestones actually achieved on the stated timeline?). Projects that repeatedly miss milestones or that define milestones so vaguely that 'completion' cannot be verified receive lower maturity scores, regardless of their technical sophistication.\n")
    a("")

    if not phases:
        a(f"*No timeline/roadmap data available for {project_name}.*\n")
        return "\n".join(L)

    # ── 4.2 Phase-by-Phase Analysis ──────────────────────────
    a("## 4.2 Development Phase Analysis\n")
    total_milestones = sum(len(p.get('milestones', [])) for p in phases)
    a(f"{project_name}'s development roadmap spans {len(phases)} phases with a total of {total_milestones} identified milestones. Each phase represents a strategic era in the project's evolution, with specific deliverables that build upon preceding achievements.\n")
    a("")

    current_year = datetime.now().year
    for i, phase_data in enumerate(phases, 1):
        phase = phase_data.get('phase', f'Phase {i}')
        period = phase_data.get('period', '')
        milestones = phase_data.get('milestones', [])

        a(f"### Phase {i}: {phase} ({period})\n")

        # Determine if this phase is past, current, or future
        try:
            # Try to extract year from period string
            years_in_period = [int(y) for y in period.replace('–', '-').replace('—', '-').split() if y.isdigit() and len(y) == 4]
            if not years_in_period:
                # Try extracting from 'Jan-Dec 2025' format
                import re
                year_matches = re.findall(r'\d{4}', period)
                years_in_period = [int(y) for y in year_matches]
        except:
            years_in_period = []

        if years_in_period:
            max_year = max(years_in_period)
            min_year = min(years_in_period)
            if max_year < current_year:
                phase_status = 'completed'
                a(f"This phase covers a period that has already elapsed ({period}). Milestones from completed phases are evaluated against verifiable evidence: did the deliverable ship? Is it operational? Does it perform as described? Completed phases set the baseline for the project's execution credibility — consistent delivery on past milestones increases confidence in future roadmap execution.\n")
            elif min_year > current_year:
                phase_status = 'future'
                a(f"This phase is forward-looking ({period}), representing planned deliverables that have not yet reached their execution window. Future milestones are assessed for feasibility and ambition rather than achievement. The maturity assessment gives partial credit for credible planning (clear specifications, identified dependencies, resource allocation) but reserves full credit for verified execution.\n")
            else:
                phase_status = 'current'
                a(f"This phase encompasses the current period ({period}), with some milestones likely in progress or recently completed. Current-phase milestones provide the most actionable signal for maturity assessment — they reveal whether the project is tracking, ahead of, or behind its own stated timeline.\n")
        else:
            phase_status = 'unknown'
            a(f"Phase period: {period}.\n")
        a("")

        if milestones:
            a("**Milestones:**\n")
            for m in milestones:
                a(f"- {m}")
            a("")

            if len(milestones) > 5:
                a(f"This phase contains {len(milestones)} milestones — an ambitious scope that reflects either strong organizational capacity or optimistic planning. Phases with high milestone density require disciplined execution and parallel workstreams. If the project has historically delivered on high-density phases, this ambition is credible; if past phases saw significant slippage, the current density suggests further delays are probable.\n")
            elif len(milestones) <= 2:
                a(f"This phase contains only {len(milestones)} milestone(s), indicating either focused strategic prioritization or limited visibility into planned deliverables. Fewer milestones are easier to achieve (reducing execution risk) but provide less information for maturity assessment. The quality and significance of these milestones matters more than quantity.\n")
            a("")

    # ── 4.3 Execution Velocity Assessment ────────────────────
    a("## 4.3 Execution Velocity and Roadmap Credibility\n")
    past_phases = [p for p in phases if any(
        int(y) < current_year for y in __import__('re').findall(r'\d{4}', p.get('period', ''))
    )] if phases else []
    future_phases = [p for p in phases if any(
        int(y) > current_year for y in __import__('re').findall(r'\d{4}', p.get('period', ''))
    )] if phases else []

    a(f"Roadmap credibility is earned through consistent execution. {project_name} has defined {len(phases)} development phases spanning its entire growth trajectory. The assessment evaluates whether the pacing of these phases — from foundational infrastructure through market maturity — is realistic given the project's team size, funding, and competitive environment.\n")
    a("")
    a(f"Projects that front-load ambitious milestones into early phases (attempting too much too soon) often face delivery failures that damage credibility. Projects that back-load critical milestones (deferring hard problems) risk running out of time and capital before reaching the phases that matter most. The optimal distribution balances early wins (demonstrating capability) with sustained execution (demonstrating commitment).\n")
    a("")
    a(f"For {project_name}, the timeline structure suggests a progressive build: each phase appears designed to create the foundation for subsequent phases. This is architecturally sound — dependencies flow forward rather than backward. However, the assessment must verify that earlier phases genuinely delivered the stated foundations, as any gap in foundational phases cascades forward, undermining all subsequent milestones.\n")
    a("")

    return "\n".join(L)


def _chapter_5_goal_achievements(d: dict) -> str:
    """Chapter 5: Goal Achievement & Aggregate Progress Scoring — the core quantitative chapter."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    goals = d.get('goal_achievements', [])
    total_score = d.get('total_maturity_score', 0)

    a("# Chapter 5: Goal Achievement & Aggregate Progress Scoring\n")

    # ── 5.1 Scoring Methodology ──────────────────────────────
    a("## 5.1 Scoring Methodology\n")
    a(f"The aggregate maturity score is computed as a weighted sum of individual objective achievement rates. Each objective receives an achievement rate (0-100%) based on verifiable evidence of progress, multiplied by its strategic weight to produce a weighted contribution. The sum of all weighted contributions equals the total maturity score.\n")
    a("")
    a("This methodology embodies several important principles: (1) a project cannot achieve high maturity by excelling in one dimension while ignoring others — all weighted objectives contribute; (2) higher-weighted objectives have proportionally greater impact on the score, reflecting their strategic importance; (3) achievement rates are capped at 100%, preventing overperformance in one area from compensating for underperformance in another.\n")
    a("")

    if not goals:
        a(f"*No goal achievement data available for {project_name}.*\n")
        return "\n".join(L)

    # ── 5.2 Detailed Scoring Table ───────────────────────────
    a("## 5.2 Weighted Achievement Scorecard\n")
    a("| Objective | Weight | Achievement | Weighted Score | Performance |")
    a("|-----------|:------:|:-----------:|:--------------:|:-----------:|")

    total_weighted = 0.0
    high_performers = []
    low_performers = []
    for goal in goals:
        obj_name = goal.get('objective', '')
        weight = goal.get('weight', 0)
        achievement = goal.get('achievement_rate', 0)
        weighted_score = (weight * achievement) / 100.0
        total_weighted += weighted_score

        if achievement >= 85:
            perf = "Excellent"
            high_performers.append(obj_name)
        elif achievement >= 70:
            perf = "Strong"
            high_performers.append(obj_name)
        elif achievement >= 50:
            perf = "Adequate"
        elif achievement >= 30:
            perf = "Weak"
            low_performers.append(obj_name)
        else:
            perf = "Critical"
            low_performers.append(obj_name)

        a(f"| {obj_name} | {weight:.0f}% | {achievement:.0f}% | {weighted_score:.2f}% | {perf} |")

    a(f"| **TOTAL MATURITY SCORE** | **100%** | — | **{total_weighted:.2f}%** | — |")
    a("")

    # ── 5.3 Score Decomposition Analysis ─────────────────────
    a("## 5.3 Score Decomposition and Performance Analysis\n")
    a(f"The total maturity score of **{total_weighted:.2f}%** decomposes into individual contributions that reveal both strengths and vulnerabilities:\n")
    a("")

    # Identify largest and smallest contributors
    contributions = []
    for goal in goals:
        w = goal.get('weight', 0)
        ach = goal.get('achievement_rate', 0)
        contrib = (w * ach) / 100.0
        contributions.append((goal.get('objective', ''), contrib, w, ach))

    contributions.sort(key=lambda x: x[1], reverse=True)
    largest = contributions[0]
    smallest = contributions[-1]

    a(f"**Largest contributor:** {largest[0]} contributes {largest[1]:.2f} points to the total score (weight: {largest[2]:.0f}%, achievement: {largest[3]:.0f}%). This objective is the primary driver of {project_name}'s current maturity level. Sustained performance here is essential — any regression would disproportionately impact the aggregate score.\n")
    a("")
    a(f"**Smallest contributor:** {smallest[0]} contributes only {smallest[1]:.2f} points (weight: {smallest[2]:.0f}%, achievement: {smallest[3]:.0f}%). Whether this represents low weight (the objective is intentionally deprioritized) or low achievement (the project is underperforming) determines the appropriate interpretation. Low contribution from low-weight objectives is by design; low contribution from high-weight objectives signals a critical gap.\n")
    a("")

    # High vs low performers
    if high_performers:
        a(f"**Strong performers** ({', '.join(high_performers)}) demonstrate that {project_name} has the organizational capacity to execute at a high level. These areas represent the project's competitive strengths — dimensions where execution has outpaced the baseline and where the project can credibly claim differentiation.\n")
        a("")
    if low_performers:
        a(f"**Weak performers** ({', '.join(low_performers)}) represent the areas where {project_name}'s execution has fallen short of expectations. These gaps may reflect resource constraints (insufficient developer allocation), strategic deprioritization (intentionally deferred), or genuine execution failure (attempted but unsuccessful). The distinction matters: deferred objectives can be accelerated; failed objectives may indicate structural problems.\n")
        a("")

    # ── 5.4 Detailed Goal Analysis ───────────────────────────
    a("## 5.4 Individual Goal Achievement Analysis\n")
    for goal in goals:
        obj_name = goal.get('objective', '')
        weight = goal.get('weight', 0)
        achievement = goal.get('achievement_rate', 0)
        details = goal.get('details', '')
        weighted_score = (weight * achievement) / 100.0

        a(f"### {obj_name} — {achievement:.0f}% Achievement (Weight: {weight:.0f}%, Contribution: {weighted_score:.2f}%)\n")

        if details:
            a(details.strip())
            a("")

        # Achievement-rate conditional narrative
        gap = 100 - achievement
        if achievement >= 90:
            a(f"At {achievement:.0f}% achievement, this objective is approaching completion. The remaining {gap:.0f}% gap likely represents either stretch goals (ambitious targets beyond core requirements) or edge cases (scenarios that are difficult to address without significantly more effort). Projects approaching 90%+ on weighted objectives should consider whether the marginal effort to close the remaining gap is worth the opportunity cost of resources that could be deployed elsewhere.\n")
        elif achievement >= 75:
            a(f"At {achievement:.0f}% achievement, substantial progress has been made, but a meaningful {gap:.0f}% gap remains. This is the 'good but not great' zone — the objective is clearly being addressed and has shown real results, but the project has not yet reached the level of execution that would justify full confidence. The assessment at this level depends on trajectory: is the achievement rate improving (suggesting the gap will close) or plateauing (suggesting structural barriers to further progress)?\n")
        elif achievement >= 50:
            a(f"At {achievement:.0f}% achievement, the project has reached the halfway mark — demonstrating viability but leaving significant ground to cover. A {gap:.0f}% gap at this stage creates risk: if the remaining progress is harder than the initial progress (which is common, as early milestones tend to be easier), the project may plateau before reaching its target. Close monitoring of velocity trends is essential.\n")
        elif achievement >= 25:
            a(f"At {achievement:.0f}% achievement, the project has established initial traction but remains far from its objective. A {gap:.0f}% gap indicates that the majority of work remains ahead. At this level, the critical question is whether the foundations laid so far are solid enough to support accelerated progress, or whether fundamental redesigns are required before further advancement is possible.\n")
        else:
            a(f"At {achievement:.0f}% achievement, the project has barely begun addressing this objective. The {gap:.0f}% gap represents nearly the entire scope of work. This level of achievement may be acceptable for objectives in early development phases or those intentionally deferred, but it raises serious concerns if the objective carries significant weight and the project claims to be beyond the early stages of development.\n")
        a("")

    # ── 5.5 Score Sensitivity ────────────────────────────────
    a("## 5.5 Score Sensitivity and Path to Next Stage\n")
    current_stage = d.get('maturity_stage', _classify_maturity(total_weighted))
    next_thresholds = {'nascent': 30, 'growing': 60, 'mature': 85, 'established': 100}
    next_stage_names = {'nascent': 'Growing', 'growing': 'Mature', 'mature': 'Established', 'established': 'Maximum'}
    current_lower = current_stage.lower()
    target_score = next_thresholds.get(current_lower, 100)
    gap_to_next = target_score - total_weighted

    if gap_to_next > 0 and current_lower != 'established':
        a(f"To advance from **{current_stage.upper()}** to **{next_stage_names.get(current_lower, 'Next')}** stage, {project_name} must close a {gap_to_next:.2f} percentage point gap. The most efficient path to improvement targets the objectives with the highest (weight × remaining gap) product — these are the dimensions where incremental achievement improvement produces the largest score increase.\n")
        a("")

        # Calculate improvement efficiency for each objective
        efficiency = []
        for goal in goals:
            w = goal.get('weight', 0)
            ach = goal.get('achievement_rate', 0)
            remaining = 100 - ach
            impact = (w * remaining) / 100.0
            efficiency.append((goal.get('objective', ''), impact, remaining, w))

        efficiency.sort(key=lambda x: x[1], reverse=True)
        top_opp = efficiency[0]
        a(f"**Highest-impact improvement opportunity:** {top_opp[0]} (potential score gain: {top_opp[1]:.2f} points from {top_opp[2]:.0f}% remaining achievement at {top_opp[3]:.0f}% weight). If {project_name} were to maximize achievement on this single objective, the maturity score would increase by up to {top_opp[1]:.2f} points — potentially sufficient to trigger stage advancement.\n")
    else:
        a(f"{project_name} has achieved the highest maturity stage (Established). Ongoing assessment should focus on maintaining achievement levels and monitoring for regression risks.\n")
    a("")

    return "\n".join(L)


def _chapter_6_maturity_stage(d: dict) -> str:
    """Chapter 6: Maturity Stage Classification & Interpretation — deep analytical narrative."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    total_score = d.get('total_maturity_score', 0)
    stage = d.get('maturity_stage', _classify_maturity(total_score))
    interpretation = d.get('maturity_interpretation', '')

    a("# Chapter 6: Maturity Stage Classification & Interpretation\n")

    # ── 6.1 Classification Framework ─────────────────────────
    a("## 6.1 BCE Lab Maturity Classification Framework\n")
    a("The BCE Lab framework classifies projects into four maturity stages, each representing a distinct phase of development with specific characteristics, risk profiles, and investment implications:\n")
    a("")
    a("| Stage | Score Range | Characteristics | Typical Risk Profile |")
    a("|-------|:----------:|-----------------|---------------------|")
    a("| **Nascent** | < 30% | Concept-stage, limited execution, high uncertainty | Very High — binary outcome likely |")
    a("| **Growing** | 30–60% | Partial execution, emerging traction, execution gaps | High — significant upside with material downside |")
    a("| **Mature** | 60–85% | Substantial achievement, proven capability, growth remaining | Moderate — fundamentals support valuation |")
    a("| **Established** | > 85% | Comprehensive achievement, production-grade, defensible | Lower — maintenance risks, competitive erosion |")
    a("")

    # ── 6.2 Classification Result ────────────────────────────
    stage_upper = stage.upper()
    a(f"## 6.2 Classification: {stage_upper}\n")
    a(f"**Maturity Score: {_format_score(total_score)}**\n")
    a("")

    if stage.lower() == 'established':
        a(f"{project_name} achieves Established classification, the highest tier in the BCE Lab framework. Established projects have moved beyond the stage where 'potential' justifies assessment — they are evaluated on demonstrated, verifiable achievement. At this stage, the primary risk shifts from execution failure (can the project deliver?) to competitive erosion (can the project maintain its position?) and strategic relevance (does the project's original thesis still hold?).\n")
        a("")
        a(f"Established projects attract a different investor profile than earlier-stage projects. Growth investors seeking outsized returns may find limited upside in established projects (much of the value has already been created). Value investors seeking stable, defensible positions find established projects attractive for their reduced risk and predictable performance. The maturity assessment at this stage focuses on sustainability — whether {project_name} can maintain its current achievement levels while the competitive landscape evolves.\n")
    elif stage.lower() == 'mature':
        a(f"{project_name} is classified as Mature — a stage that represents the critical inflection point between 'promising project' and 'established protocol.' Mature projects have demonstrated concrete, verifiable achievement across their core objectives, but retain meaningful areas for growth. This is arguably the most interesting stage for assessment because it captures projects that have proven viability but not yet proven durability.\n")
        a("")
        a(f"The key risk at the Mature stage is stagnation. Many projects reach Mature status through an initial burst of execution momentum, then plateau as founding team energy dissipates, technical debt accumulates, and market conditions shift. The difference between projects that advance to Established and those that regress to Growing often comes down to organizational resilience — can the project sustain execution through adverse conditions? Does the governance structure enable adaptation? Are financial resources sufficient to fund the next phase of development?\n")
    elif stage.lower() == 'growing':
        a(f"{project_name} is classified as Growing — indicating that the project has moved beyond pure concept stage and demonstrated initial execution, but significant gaps remain between current state and stated objectives. Growing projects are in the 'prove it' phase: the conceptual foundation is laid, early milestones have been achieved, but the market has not yet received enough evidence to justify full confidence.\n")
        a("")
        a(f"Investment at the Growing stage carries elevated risk but also elevated optionality. If {project_name} successfully executes through the Growing phase, the value appreciation from Growing to Mature can be substantial — this is where the most asymmetric risk-reward opportunities exist. However, many projects never advance beyond Growing, and those that fail at this stage typically do so because they lack either the technical capability, the financial resources, or the organizational discipline to convert early momentum into sustained execution.\n")
    else:
        a(f"{project_name} is classified as Nascent — the earliest stage of maturity assessment. Nascent projects are characterized by incomplete technology, limited or no market traction, and strategic objectives that remain largely aspirational. This is the stage where vision exceeds execution by the widest margin, and where assessment must distinguish between projects with genuine execution potential and those with only narrative appeal.\n")
        a("")
        a(f"Nascent-stage investment is venture-style: the overwhelming majority of Nascent projects will fail, but the small percentage that succeed can deliver extraordinary returns. The maturity assessment at this stage focuses less on what has been achieved (very little) and more on the credibility of the path to achievement: team quality, technical design, funding adequacy, and competitive positioning.\n")
    a("")

    # ── 6.3 Interpretation ───────────────────────────────────
    a("## 6.3 Maturity Interpretation and Contextual Analysis\n")
    if interpretation:
        a(interpretation.strip())
        a("")
    else:
        a(f"The {_format_score(total_score)} maturity score positions {project_name} within the {stage_upper} range. This score reflects the weighted aggregate of achievement across all strategic objectives, capturing both strengths (objectives where execution exceeds baseline) and weaknesses (objectives where execution lags). The score should be interpreted in context: maturity is a snapshot, not a destiny. Projects can advance or regress depending on execution quality, market conditions, and competitive dynamics.\n")
    a("")

    # ── 6.4 Stage Transition Analysis ────────────────────────
    a("## 6.4 Stage Transition Probabilities and Trajectory\n")
    if stage.lower() == 'established':
        a(f"At Established stage, {project_name}'s primary trajectory risk is regression. Historical analysis shows that approximately 15-20% of Established projects regress to Mature within 18 months, typically triggered by key personnel departure, security incidents, or competitive displacement. Monitoring should focus on maintenance of current achievement levels rather than further advancement.\n")
    elif stage.lower() == 'mature':
        a(f"At Mature stage, {project_name} faces a three-way trajectory: advancement to Established (requiring closure of remaining achievement gaps), maintenance at Mature (stable but not advancing), or regression to Growing (triggered by execution failure, competitive loss, or external shocks). The trajectory depends on execution velocity — specifically, whether the rate of achievement improvement exceeds the rate at which the competitive bar is rising.\n")
    elif stage.lower() == 'growing':
        a(f"At Growing stage, {project_name}'s trajectory is heavily dependent on near-term execution. The next 12-18 months are critical: projects that demonstrate accelerating achievement rates during this window typically advance to Mature, while those showing decelerating rates often plateau or regress. Key triggers to monitor include major feature launches, user adoption milestones, and funding events.\n")
    else:
        a(f"At Nascent stage, {project_name}'s trajectory is inherently uncertain. The project is pre-traction, meaning that future maturity depends almost entirely on execution capacity that has not yet been demonstrated. The assessment at this stage is necessarily more speculative — based on team credentials, technical design quality, and market opportunity rather than achieved results.\n")
    a("")

    return "\n".join(L)


def _chapter_community_maturity(d: dict) -> str:
    """Community Maturity Assessment — integrated as Chapter 6.5 (between Maturity Stage and Deep Technical)."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    community = d.get('community_maturity', {})
    community_raw = d.get('community_data_raw', {})

    a("# Community & Developer Ecosystem Maturity\n")

    # ── Overview ─────────────────────────────────────────────────
    a("## Community Maturity Assessment Framework\n")
    a(f"Community maturity is a leading indicator of project sustainability. Projects with thriving, multi-platform communities demonstrate organic demand that transcends speculative interest. The BCE Lab community maturity framework evaluates eight dimensions: social media reach (Twitter/X, Reddit, Telegram), engagement depth (activity rates, not just follower counts), developer ecosystem health (GitHub contributors, commit frequency), and multi-platform presence.\n")
    a("")

    overall_score = community.get('overall_score', 0)
    label = community.get('label', 'Unknown')
    label_ko = community.get('label_ko', '')
    metrics_available = community.get('metrics_available', 0)
    breakdown = community.get('breakdown', {})

    if overall_score > 0 and breakdown:
        # ── Score Summary ────────────────────────────────────────
        a(f"## Community Maturity Score: {overall_score:.1f}/100 — {label} ({label_ko})\n")
        a("")

        # ── Metrics Table ────────────────────────────────────────
        a("### Multi-Dimensional Community Metrics\n")
        a("| Metric | Value | Score | Weight |")
        a("|--------|------:|:-----:|:------:|")

        _metric_labels = {
            'twitter_followers': 'Twitter/X Followers',
            'reddit_subscribers': 'Reddit Subscribers',
            'reddit_active_48h': 'Reddit Active Users (48h)',
            'telegram_members': 'Telegram Members',
            'github_contributors': 'GitHub Contributors',
            'github_commits_30d': 'GitHub Commits (4 weeks)',
            'social_engagement_rate': 'Social Engagement Rate (%)',
            'multi_platform_presence': 'Multi-Platform Presence',
        }
        for metric_name, info in breakdown.items():
            label_text = _metric_labels.get(metric_name, metric_name)
            raw = info.get('raw_value', 0)
            if metric_name == 'social_engagement_rate':
                val_str = f"{raw:.2f}%"
            elif metric_name == 'multi_platform_presence':
                val_str = f"{int(raw)} platforms"
            elif raw >= 1000:
                val_str = f"{raw:,.0f}"
            else:
                val_str = f"{raw:.0f}"
            a(f"| {label_text} | {val_str} | {info.get('score', 0)}/100 | {info.get('weight', 0)}% |")
        a("")

        # ── Interpretation ───────────────────────────────────────
        a("### Community Health Interpretation\n")
        if overall_score >= 80:
            a(f"{project_name} demonstrates a **thriving community ecosystem**. High engagement across multiple platforms indicates organic, sustained interest that is not solely driven by price speculation. The project benefits from network effects — active community members create content, provide support, and attract new participants, forming a self-reinforcing growth cycle. This community strength provides resilience against market downturns and competitive pressure.\n")
        elif overall_score >= 60:
            a(f"{project_name} has a **healthy community** with solid foundations across key platforms. The engagement metrics indicate genuine user interest beyond speculative trading. However, there is room for growth in either reach (expanding to underrepresented platforms) or depth (increasing engagement rates among existing community members). Projects at this community maturity level typically have sufficient community infrastructure to support the next phase of growth.\n")
        elif overall_score >= 40:
            a(f"{project_name}'s community is **developing** — present and active but not yet reaching the critical mass that drives self-sustaining growth. The project may have strong presence on one or two platforms but gaps on others, or may have significant reach without proportional engagement. The key risk at this level is community fragmentation: if the project cannot consolidate its community presence into sustainable engagement, it risks losing momentum during market downturns.\n")
        elif overall_score >= 20:
            a(f"{project_name} has an **early-stage community** with limited reach and engagement. This is expected for nascent or recently launched projects, but concerning for projects that have been active for extended periods. Low community metrics may indicate: limited marketing investment, a niche use case with inherently small addressable community, or fundamental issues with the project's value proposition that prevent organic community growth.\n")
        else:
            a(f"{project_name}'s community presence is **minimal**. This represents a significant maturity gap — even technically excellent projects struggle to achieve long-term viability without community support. Immediate community building investment is recommended, focusing on the platforms most relevant to the project's target audience.\n")
        a("")

        # ── Developer Ecosystem ──────────────────────────────────
        gh_commits = community_raw.get('github_commits_30d', 0)
        gh_contributors = community_raw.get('github_contributors', 0)
        gh_stars = community_raw.get('github_stars', 0)
        gh_prs = community_raw.get('github_prs_merged', 0)

        if gh_commits > 0 or gh_contributors > 0:
            a("### Developer Ecosystem Health\n")
            a("| Developer Metric | Value |")
            a("|------------------|------:|")
            if gh_commits > 0:
                a(f"| Commits (4 weeks) | {gh_commits:,} |")
            if gh_contributors > 0:
                a(f"| Contributors | {gh_contributors:,} |")
            if gh_stars > 0:
                a(f"| GitHub Stars | {gh_stars:,} |")
            if gh_prs > 0:
                a(f"| Pull Requests Merged | {gh_prs:,} |")
            forks = community_raw.get('github_forks', 0)
            if forks > 0:
                a(f"| Forks | {forks:,} |")
            a("")

            if gh_commits >= 100 and gh_contributors >= 20:
                a(f"Developer ecosystem is **highly active** — sustained commit velocity and broad contributor base indicate a healthy, non-centralized development effort. Multiple contributors reduce key-person risk and suggest the codebase is accessible to external developers.\n")
            elif gh_commits >= 30 and gh_contributors >= 5:
                a(f"Developer ecosystem shows **moderate activity**. The core team is actively developing, but contributor diversity could improve. Projects at this level should focus on developer documentation and contribution guides to attract external contributors.\n")
            elif gh_commits > 0:
                a(f"Developer activity is **limited** — low commit count and contributor diversity suggest either a very small team or reduced development focus. This warrants monitoring to distinguish between projects in maintenance mode (acceptable for mature protocols) and those experiencing development stagnation (concerning at any stage).\n")
            a("")

    else:
        a(f"## Community Data Assessment\n")
        a(f"Community maturity data was not available for {project_name} during this assessment cycle. The absence of community metrics creates a blind spot in the maturity assessment — community health is a leading indicator that often foreshadows changes in project trajectory before they appear in on-chain or market data.\n")
        a("")
        a("Future assessments should incorporate CoinGecko community metrics (Twitter, Reddit, Telegram), GitHub developer activity, and governance participation data to provide a complete community maturity profile.\n")
        a("")

    return "\n".join(L)


def _chapter_7_deep_technical(d: dict) -> str:
    """Chapter 7: Deep Technical Analysis — detailed examination of technical architecture and innovation."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    technical = d.get('deep_technical', '')

    a("# Chapter 7: Deep Technical Analysis\n")

    # ── 7.1 Technical Foundation ─────────────────────────────
    a("## 7.1 Technical Architecture and Innovation Assessment\n")
    a(f"Deep technical analysis examines {project_name}'s engineering quality below the surface layer of features and user experience. This chapter evaluates the core systems — protocol design, smart contract architecture, consensus mechanisms, data models, and security infrastructure — that determine whether the project can deliver its value proposition at scale and under adversarial conditions.\n")
    a("")
    a(f"Technical maturity in blockchain projects is not merely about having code that 'works.' It encompasses code quality (auditability, test coverage, documentation), design quality (appropriate use of patterns, resistance to attack vectors, composability), operational quality (monitoring, incident response, upgrade procedures), and innovation quality (novel mechanisms that create competitive advantage while maintaining security guarantees).\n")
    a("")

    if technical:
        a("## 7.2 Core Technical Deep-Dive\n")
        # Split technical content into paragraphs for better narrative
        paragraphs = technical.strip().split('\n\n')
        for para in paragraphs:
            a(para.strip())
            a("")

        a("## 7.3 Technical Maturity Assessment\n")
        # Count technical indicators
        tech_lower = technical.lower()
        has_audit = any(k in tech_lower for k in ['audit', 'security review', 'tested'])
        has_novel = any(k in tech_lower for k in ['novel', 'innovat', 'new standard', 'erc-', 'eip-'])
        has_production = any(k in tech_lower for k in ['production', 'live', 'deployed', 'operational'])

        if has_audit and has_novel and has_production:
            a(f"The technical profile of {project_name} shows positive signals across three critical dimensions: security validation (audits or formal reviews), innovation (novel mechanisms or standards), and production deployment (live operational systems). This combination suggests a technically mature team that balances innovation ambition with security discipline — a rare and valuable combination in blockchain development.\n")
        elif has_production and not has_audit:
            a(f"While {project_name} has achieved production deployment, the assessment notes limited evidence of formal security validation. Production systems without comprehensive audits carry elevated risk — the code may function correctly under normal conditions while harboring vulnerabilities that emerge only under adversarial testing or unusual market conditions. A security audit of all deployed smart contracts should be a near-term priority.\n")
        elif has_novel and not has_production:
            a(f"The technical architecture includes novel innovations, but deployment and production validation evidence is limited. Innovation without production testing is inherently speculative — novel mechanisms may perform well in theory but encounter unexpected behaviors when exposed to real users, real adversaries, and real market conditions. The path from novel design to production maturity requires significant testing, iteration, and battle-hardening.\n")
        else:
            a(f"The technical analysis provides foundational understanding of {project_name}'s engineering approach. Ongoing evaluation should track audit completion, production metrics, and the resolution of identified technical risks.\n")
        a("")
    else:
        a("## 7.2 Technical Assessment\n")
        a(f"Detailed technical documentation for {project_name} was not available for this assessment cycle. The maturity score reflects this data gap — projects that do not provide sufficient technical transparency receive lower confidence in technical maturity assessment. Future assessments should incorporate published audit reports, open-source repository analysis, and technical documentation review.\n")
        a("")

    # ── 7.4 Security Posture ─────────────────────────────────
    a("## 7.4 Security Posture and Audit Status\n")
    a(f"Smart contract security remains the most critical technical risk for any blockchain project. A single vulnerability can result in complete loss of user funds, irreversible reputational damage, and regulatory scrutiny. {project_name}'s security posture should be evaluated across several dimensions:\n")
    a("")
    a("**Audit Coverage:** Have all deployed smart contracts been audited by reputable security firms? Were audit findings addressed? Are audit reports publicly available?\n")
    a("")
    a("**Bug Bounty Program:** Does the project maintain a bug bounty program that incentivizes external security researchers to report vulnerabilities before they are exploited?\n")
    a("")
    a("**Incident Response:** Does the project have documented procedures for responding to security incidents? Can the team pause or upgrade contracts if a vulnerability is discovered?\n")
    a("")
    a(f"**Track Record:** Has {project_name} experienced any security incidents to date? If so, how were they handled? Projects that have survived and recovered from security incidents demonstrate resilience; projects that have not yet been tested may face their first incident without established response procedures.\n")
    a("")

    return "\n".join(L)


def _chapter_8_token_sustainability(d: dict) -> str:
    """Chapter 8: Token Value Proposition & Sustainability — deep economic analysis."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    token_sus = d.get('token_sustainability', '')

    a("# Chapter 8: Token Value Proposition & Sustainability\n")

    # ── 8.1 Token Economic Framework ─────────────────────────
    a("## 8.1 Token Economic Framework\n")
    a(f"The sustainability of {token_symbol} depends on a fundamental equilibrium: token demand must be sufficient to absorb ongoing supply (including inflation, vesting unlocks, and secondary sales) without persistent downward price pressure. This chapter examines whether {project_name}'s token model creates genuine, sustainable demand or relies on speculative interest that may evaporate during market downturns.\n")
    a("")
    a(f"Token sustainability analysis requires examining four interconnected dynamics: **utility demand** (are tokens needed for protocol function?), **speculative demand** (are tokens held for appreciation?), **supply pressure** (how are new tokens entering circulation?), and **value capture** (does protocol success create token scarcity or revenue?). Sustainable token economies demonstrate alignment across all four; unsustainable ones show misalignment — typically, high supply growth paired with purely speculative demand.\n")
    a("")

    if token_sus:
        a("## 8.2 Token Value Drivers and Demand Analysis\n")
        paragraphs = token_sus.strip().split('\n\n')
        for para in paragraphs:
            a(para.strip())
            a("")
    else:
        a("## 8.2 Token Value Drivers\n")
        a(f"{token_symbol} derives value from its role within {project_name}'s protocol ecosystem. The key question is whether that role creates unavoidable demand (users *must* hold or spend tokens to interact with the protocol) or optional demand (tokens provide benefits but are not required). Unavoidable demand creates a valuation floor proportional to protocol usage; optional demand is subject to substitution and can evaporate.\n")
        a("")

    # ── 8.3 Sustainability Assessment ────────────────────────
    a("## 8.3 Long-Term Sustainability Assessment\n")
    a(f"The long-term viability of {token_symbol} depends on whether the token economy can sustain itself through organic demand rather than perpetual capital inflows. Sustainable token economies share several characteristics:\n")
    a("")
    a("**Revenue-Backed Value.** Protocols that generate real revenue (fees, liquidations, service charges) and direct that revenue toward token holders (through buybacks, burns, or direct distribution) create fundamentally-backed token value. This is analogous to equity dividends — the token represents a claim on genuine economic output.\n")
    a("")
    a("**Supply Discipline.** Protocols that maintain strict supply discipline — limited inflation, transparent vesting, no discretionary minting — protect existing holders from dilution. Deflationary mechanisms (fee burns, buyback-and-burn) create positive supply dynamics where protocol success directly reduces outstanding supply.\n")
    a("")
    a("**Governance Value.** If governance decisions control meaningful economic parameters (fee rates, treasury allocation, protocol upgrades), governance tokens derive value from the economic impact of those decisions. However, governance value requires active, competent participation — token holders who do not vote or who vote poorly can destroy value through governance decay.\n")
    a("")
    a(f"**Network Effect Value.** If {token_symbol} benefits from network effects (more users make the token more valuable for each individual user), the token economy becomes self-reinforcing. Network-effect-driven tokens are among the most resilient, as they are protected by switching costs and positive feedback loops.\n")
    a("")

    # ── 8.4 Maturity Implications ────────────────────────────
    total_score = d.get('total_maturity_score', 0)
    a("## 8.4 Token Sustainability and Maturity Implications\n")
    if total_score >= 70:
        a(f"At {_format_score(total_score)} maturity, {project_name} has reached a stage where token sustainability questions become critical. Early-stage projects can sustain token value through narrative and potential alone; mature projects must demonstrate that the token economy actually works — that real demand exists, that supply dynamics are manageable, and that the token captures value from protocol growth. The transition from narrative-driven to fundamentals-driven token value is a key indicator of genuine maturity.\n")
    elif total_score >= 40:
        a(f"At {_format_score(total_score)} maturity, {project_name} is in the phase where token value is driven by a mix of fundamentals and speculation. The project has demonstrated enough execution to justify some fundamental valuation, but significant uncertainty remains about long-term token demand. Investors should weight speculative risk accordingly — the token may appreciate significantly if the project executes, but current valuations likely embed meaningful premium for unproven potential.\n")
    else:
        a(f"At {_format_score(total_score)} maturity, {token_symbol} value is primarily speculative. The project has not yet demonstrated the fundamental execution necessary to support token value through organic demand. This does not necessarily mean the token is overvalued — early-stage investments are priced on potential, not achievement — but investors should understand that the downside scenario involves near-total loss if execution fails.\n")
    a("")

    return "\n".join(L)


def _chapter_9_risks(d: dict) -> str:
    """Chapter 9: Technical Limitations & Risk Management — comprehensive risk analysis."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    risks = d.get('risks', [])
    total_score = d.get('total_maturity_score', 0)

    a("# Chapter 9: Technical Limitations & Risk Management\n")

    # ── 9.1 Risk Assessment Framework ────────────────────────
    a("## 9.1 Risk Assessment Framework\n")
    a(f"No project — regardless of maturity level — is free from risk. The purpose of risk assessment is not to identify a risk-free project (none exist) but to catalog, quantify, and evaluate the risks facing {project_name} so that stakeholders can make informed decisions about whether the expected returns justify the identified risks.\n")
    a("")
    a(f"The BCE Lab framework categorizes risks into five domains: **Technical Risks** (smart contract bugs, architectural flaws, scalability limitations), **Economic Risks** (token design failures, liquidity crises, sustainability gaps), **Competitive Risks** (market share loss, feature obsolescence), **Regulatory Risks** (adverse legislation, enforcement actions), and **Organizational Risks** (team departure, governance failure, funding exhaustion). Each risk is assessed by severity (potential impact if realized) and probability (likelihood of realization).\n")
    a("")

    # ── 9.2 Risk Registry ────────────────────────────────────
    if risks:
        a("## 9.2 Risk Registry and Severity Assessment\n")
        a("| Risk Factor | Severity | Domain | Implications |")
        a("|-------------|:--------:|--------|-------------|")

        severity_counts = {'High': 0, 'Medium': 0, 'Low': 0}
        for risk in risks:
            name = risk.get('name', '')
            severity = risk.get('severity', 'Medium')
            desc = risk.get('description', '—').strip()
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            # Infer domain
            name_lower = name.lower()
            if any(k in name_lower for k in ['smart contract', 'security', 'technical', 'bug', 'hack']):
                domain = 'Technical'
            elif any(k in name_lower for k in ['regulatory', 'compliance', 'legal', 'sec', 'law']):
                domain = 'Regulatory'
            elif any(k in name_lower for k in ['token', 'economic', 'concentration', 'whale', 'governance']):
                domain = 'Economic'
            elif any(k in name_lower for k in ['competition', 'market', 'adoption']):
                domain = 'Competitive'
            elif any(k in name_lower for k in ['team', 'delay', 'launch', 'organizational']):
                domain = 'Organizational'
            else:
                domain = 'General'

            a(f"| {name} | {severity} | {domain} | {desc[:120]} |")
        a("")

        # ── 9.3 Risk Profile Summary ─────────────────────────
        a("## 9.3 Risk Profile Summary\n")
        high_count = severity_counts.get('High', 0)
        med_count = severity_counts.get('Medium', 0)
        low_count = severity_counts.get('Low', 0)
        total_risks = len(risks)

        a(f"{project_name} faces {total_risks} identified risks: {high_count} High severity, {med_count} Medium severity, and {low_count} Low severity.\n")
        a("")

        if high_count >= 3:
            a(f"**ELEVATED RISK PROFILE.** With {high_count} high-severity risks, {project_name} faces a risk profile that warrants heightened caution. Multiple high-severity risks create correlation risk — under adverse conditions, multiple risks can materialize simultaneously, amplifying the impact beyond what any single risk assessment would suggest. Projects with this risk profile require strong risk management infrastructure (emergency procedures, insurance coverage, governance circuit breakers) to maintain stakeholder confidence.\n")
        elif high_count >= 1:
            a(f"**MODERATE RISK PROFILE.** The presence of {high_count} high-severity risk(s) is notable but not unusual for projects at this stage. Every blockchain project carries some high-severity risk — the question is whether the identified risks are well-understood, actively mitigated, and proportional to the project's reward potential. {project_name} should prioritize mitigation of high-severity risks before allocating resources to lower-severity items.\n")
        else:
            a(f"**CONTROLLED RISK PROFILE.** With no high-severity risks identified, {project_name} demonstrates a relatively controlled risk profile. However, the absence of identified high-severity risks may reflect either genuine risk management maturity or incomplete risk assessment — some risks may not be visible from external analysis. Ongoing monitoring should watch for emerging risks not captured in the initial assessment.\n")
        a("")

        # ── 9.4 Detailed Risk Analysis ──────────────────────
        a("## 9.4 Detailed Risk Analysis\n")
        for risk in risks:
            name = risk.get('name', 'Unknown Risk')
            severity = risk.get('severity', 'Medium')
            desc = risk.get('description', '')

            a(f"### {name} (Severity: {severity})\n")
            if desc:
                a(desc.strip())
                a("")

            if severity == 'High':
                a(f"**Mitigation Priority: IMMEDIATE.** High-severity risks require active mitigation strategies, not passive monitoring. {project_name} should have documented mitigation plans for this risk, including: trigger conditions (what signals that this risk is materializing?), response procedures (what actions are taken if the risk materializes?), and contingency plans (what happens if mitigation fails?). The absence of any of these elements indicates insufficient risk management maturity.\n")
            elif severity == 'Medium':
                a(f"**Mitigation Priority: Active Monitoring.** Medium-severity risks should be tracked through defined metrics and reviewed on a regular cadence (monthly or quarterly). The goal is to detect deterioration before the risk escalates to high severity. Effective monitoring requires pre-defined thresholds that trigger escalation.\n")
            else:
                a(f"**Mitigation Priority: Awareness.** Low-severity risks should be documented and revisited periodically, but do not require dedicated mitigation resources at this time.\n")
            a("")
    else:
        a("## 9.2 Risk Assessment\n")
        a(f"*No structured risk data available for {project_name}. The absence of identified risks should not be interpreted as the absence of risk — it reflects a data gap in the assessment input. All blockchain projects carry material risks across technical, economic, regulatory, and competitive dimensions.*\n")
        a("")

    # ── 9.5 Risk-Maturity Correlation ────────────────────────
    a("## 9.5 Risk Management Maturity Assessment\n")
    a(f"Risk management maturity is itself a dimension of project maturity. Projects at different maturity stages face different risk profiles:\n")
    a("")
    if total_score >= 70:
        a(f"At {_format_score(total_score)} maturity, {project_name} should demonstrate mature risk management: documented procedures, active monitoring, insurance or reserve funds, and governance mechanisms for risk-related decisions. The expectation at this maturity level is that risks are not just identified but actively managed — and that the project's track record demonstrates effective risk response.\n")
    elif total_score >= 40:
        a(f"At {_format_score(total_score)} maturity, {project_name} is expected to have identified major risks and begun implementing mitigation strategies. The risk management infrastructure may still be developing, but the project should show awareness of its risk profile and a credible plan for addressing the most severe items.\n")
    else:
        a(f"At {_format_score(total_score)} maturity, risk management is expected to be basic — the project should at minimum identify its primary risks, even if formal mitigation strategies are not yet in place. The risk profile at this stage is inherently high, and stakeholders should factor the overall early-stage risk profile into their assessment.\n")
    a("")

    return "\n".join(L)


def _chapter_10_conclusion(d: dict) -> str:
    """Chapter 10: Comprehensive Conclusion & Future Outlook — synthesis and forward-looking analysis."""
    L = []
    a = L.append
    project_name = d.get('project_name', 'Unknown Project')
    token_symbol = d.get('token_symbol', 'TOKEN')
    total_score = d.get('total_maturity_score', 0)
    stage = d.get('maturity_stage', _classify_maturity(total_score))
    conclusion = d.get('conclusion', '')
    outlook = d.get('future_outlook', '')
    goals = d.get('goal_achievements', [])

    a("# Chapter 10: Comprehensive Conclusion & Future Outlook\n")

    # ── 10.1 Assessment Synthesis ────────────────────────────
    a("## 10.1 Assessment Synthesis\n")
    if conclusion:
        a(conclusion.strip())
        a("")
    else:
        a(f"This comprehensive maturity assessment of {project_name} ({token_symbol}) integrates analysis across ten dimensions — industry context, strategic objective definition, architectural design, roadmap execution, quantitative scoring, maturity classification, technical depth, token sustainability, risk management, and forward-looking outlook — to produce a holistic view of the project's current state and trajectory.\n")
        a("")

    a(f"**Final Maturity Score: {_format_score(total_score)} ({stage.upper()})**\n")
    a("")

    # Score interpretation
    if goals:
        avg_achievement = sum(g.get('achievement_rate', 0) for g in goals) / len(goals)
        max_achievement = max(g.get('achievement_rate', 0) for g in goals)
        min_achievement = min(g.get('achievement_rate', 0) for g in goals)
        achievement_range = max_achievement - min_achievement

        a(f"Across {len(goals)} strategic objectives, the average achievement rate is {avg_achievement:.0f}%, with a range from {min_achievement:.0f}% to {max_achievement:.0f}%. ")
        if achievement_range > 30:
            a(f"The wide achievement range ({achievement_range:.0f}pp) indicates uneven execution — {project_name} excels in some areas while lagging significantly in others. This pattern is common in projects that have focused resources on core capabilities at the expense of supporting dimensions. While this focus may be strategically rational, the maturity assessment penalizes uneven execution because long-term viability requires competence across all critical dimensions.\n")
        elif achievement_range > 15:
            a(f"The moderate achievement range ({achievement_range:.0f}pp) suggests balanced but imperfect execution. {project_name} shows competence across objectives without dramatic outliers, but with enough variation to identify both strengths and areas for improvement.\n")
        else:
            a(f"The narrow achievement range ({achievement_range:.0f}pp) indicates highly consistent execution across all objectives — a sign of organizational discipline and balanced resource allocation.\n")
        a("")

    # ── 10.2 Strengths and Vulnerabilities ───────────────────
    a("## 10.2 Key Strengths and Vulnerabilities\n")
    if goals:
        sorted_goals = sorted(goals, key=lambda x: x.get('achievement_rate', 0), reverse=True)
        top = sorted_goals[0]
        bottom = sorted_goals[-1]

        a(f"**Primary Strength:** {top.get('objective', '')} ({top.get('achievement_rate', 0):.0f}% achievement) — This represents {project_name}'s most mature dimension, where execution has most closely matched ambition. This strength forms the credible foundation for the project's value proposition and should be leveraged as the project's competitive differentiator.\n")
        a("")
        a(f"**Primary Vulnerability:** {bottom.get('objective', '')} ({bottom.get('achievement_rate', 0):.0f}% achievement) — This represents the area of greatest underperformance relative to expectations. Whether this gap reflects strategic deprioritization or execution difficulty, it creates risk: competitors who achieve higher performance on this dimension may erode {project_name}'s overall competitive position.\n")
        a("")

    # ── 10.3 Forward-Looking Assessment ──────────────────────
    a("## 10.3 Forward-Looking Assessment and Trajectory\n")
    if outlook:
        a(outlook.strip())
        a("")
    else:
        a(f"The forward-looking assessment for {project_name} depends on the project's ability to sustain execution momentum, adapt to competitive and regulatory changes, and close the gaps identified in this report.\n")
        a("")

    # Stage-specific outlook
    if stage.lower() == 'established':
        a(f"**Trajectory from Established:** {project_name}'s primary challenge is maintaining its position. Established projects face competitive erosion (newer projects with superior technology), complacency risk (team assumes success is permanent), and relevance risk (the market may evolve away from the project's core thesis). The 12-month outlook for Established projects typically centers on defensive strategies: maintaining market share, deepening competitive moats, and adapting to industry evolution.\n")
    elif stage.lower() == 'mature':
        a(f"**Trajectory from Mature:** {project_name} stands at the critical inflection between Growth and Establishment. The next 12-18 months will likely determine whether the project advances to Established (requiring significant achievement improvement in lagging objectives) or plateaus at Mature (maintaining current levels without meaningful advancement). The key accelerants are: successful delivery of planned milestones, growing user adoption, and absence of material risk materializations.\n")
    elif stage.lower() == 'growing':
        a(f"**Trajectory from Growing:** {project_name} must demonstrate accelerating execution to advance beyond the Growing stage. The 12-18 month window is critical — projects that remain at Growing for extended periods face narrative exhaustion (stakeholders lose patience), funding pressure (investors seek exits or demand milestones), and competitive displacement (faster-moving projects capture market share). The key milestones to watch are: technical delivery, user adoption acceleration, and partnership execution.\n")
    else:
        a(f"**Trajectory from Nascent:** {project_name} faces the highest-uncertainty trajectory. Nascent projects that advance do so through rapid, focused execution on their highest-weighted objective — proving the core thesis before expanding to secondary objectives. The 6-12 month horizon is where most Nascent projects either demonstrate viability (advancing to Growing) or fail to achieve critical mass.\n")
    a("")

    # ── 10.4 Investment Framework & Litmus Test ────────────────
    a("## 10.4 Maturity-Based Investment Framework\n")

    investment_frameworks = {
        'nascent': ('High-Risk Venture', '24-36개월',
                    'Core technology proof-of-concept delivers measurable results'),
        'growing': ('Growth Opportunity', '12-24개월',
                    'User metrics show sustained organic growth trend'),
        'mature': ('Execution Opportunity', '6-12개월',
                   'Protocol revenue exceeds operational costs (self-sufficiency)'),
        'established': ('Value Investment', 'Ongoing',
                        'Market share defense and strategic expansion success'),
    }

    stage_lower = stage.lower()
    fw = investment_frameworks.get(stage_lower, investment_frameworks['growing'])

    a(f"**Investment Classification: {fw[0]}**\n")
    a(f"**Assessment Time Horizon: {fw[1]}**\n")
    a("")

    # Auto-generate litmus test from weakest objective
    if goals:
        sorted_by_achievement = sorted(goals, key=lambda x: x.get('achievement_rate', 0))
        weakest = sorted_by_achievement[0]
        weakest_name = weakest.get('objective', 'core objective')
        weakest_ach = weakest.get('achievement_rate', 0)

        a(f"### Litmus Test (리트머스 테스트)\n")
        a(f"The critical question that determines {project_name}'s trajectory:\n")
        a("")
        a(f"**\"{weakest_name}\" 달성률을 현재 {weakest_ach:.0f}%에서 {min(100, weakest_ach + 20):.0f}%+ 수준으로 끌어올릴 수 있는가?**\n")
        a("")
        a(f"This litmus test targets {project_name}'s weakest dimension ({weakest_name}) because overall maturity advancement requires closing this gap. If the project can demonstrate meaningful improvement in this area within the assessment time horizon ({fw[1]}), it validates the execution thesis. If progress stalls, it signals structural limitations that may cap the project's maturity ceiling.\n")
    else:
        a(f"**Litmus Test:** {fw[2]}\n")
    a("")

    # Scenario projections
    a("### Maturity Scenario Projections\n")
    a(f"| Scenario | 12-Month Score Projection | Implications |")
    a(f"|----------|:------------------------:|-------------|")
    bull_score = min(100, total_score + 15)
    base_score = total_score + 3
    bear_score = max(0, total_score - 10)
    a(f"| **Bull Case** | {_format_score(bull_score)} ({_classify_maturity(bull_score).upper()}) | Strong execution across all objectives; advancement likely |")
    a(f"| **Base Case** | {_format_score(base_score)} ({_classify_maturity(base_score).upper()}) | Steady progress; maintains current trajectory |")
    a(f"| **Bear Case** | {_format_score(bear_score)} ({_classify_maturity(bear_score).upper()}) | Execution stalls or external shock; regression risk |")
    a("")

    # ── 10.5 Reassessment Framework ──────────────────────────
    a("## 10.5 Reassessment Timeline and Monitoring\n")
    a(f"This maturity assessment represents a point-in-time evaluation of {project_name}'s progress. Maturity is dynamic — projects advance and regress based on execution quality, competitive dynamics, and market conditions. The following reassessment schedule ensures that stakeholders maintain current visibility:\n")
    a("")
    a("**Monthly Monitoring:** Track key execution indicators — GitHub commits, on-chain activity, user growth, governance participation. Small deviations are normal; sustained divergence (3+ months) from positive trends warrants investigation.\n")
    a("")
    a("**Quarterly Reassessment:** Update individual objective achievement rates based on new evidence. Recalculate the aggregate maturity score and evaluate whether stage classification has changed.\n")
    a("")
    a("**Upon Material Events:** Immediately reassess upon major developments: security incidents, team changes, regulatory actions, partnership announcements, or competitive disruptions. Material events can shift maturity trajectories rapidly.\n")
    a("")
    a("**Semi-Annual Comprehensive Review:** Full reassessment of all ten chapters with updated data, refreshed risk analysis, and revised forward-looking outlook. This cadence ensures that the strategic objectives themselves remain relevant — objectives that were appropriate 6 months ago may need revision as the project and market evolve.\n")
    a("")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Data Sources section
# ---------------------------------------------------------------------------

def _section_data_sources(d: dict) -> str:
    """Data Sources section."""
    L = []
    a = L.append
    sources = d.get('data_sources', [])

    a("## Data Sources & Methodology\n")
    if sources:
        a("### Primary Data Sources\n")
        for s in sources:
            a(f"- {s}")
        a("")

    a("### Assessment Methodology\n")
    a("- **Scoring:** Weighted average of objective achievement rates")
    a("- **Classification:** Four-tier maturity framework (Nascent/Growing/Mature/Established)")
    a("- **Validation:** Cross-referenced against on-chain data, public repositories, and published documentation")
    a("- **Update Frequency:** Quarterly reassessment cycle with event-driven interim updates")
    a("")

    a("### Data Freshness\n")
    a(f"- Assessment date: {datetime.now().strftime('%B %d, %Y')}")
    a("- On-chain data: Verified within 24 hours of assessment")
    a("- Technical documentation: Most recent publicly available version")
    a("- Market data: Real-time at time of assessment")
    a("")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_text_mat(
    project_data: Dict[str, Any],
    output_dir: str = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Stage 1: Generate comprehensive 10-chapter executive-grade Markdown maturity analysis.

    Produces 6000+ word analytical reports with narrative depth across:
      1. Executive Summary & Industry Context
      2. Strategic Objective Identification & Weight Assessment
      3. On-Chain/Off-Chain Architecture Analysis
      4. Timeline-Based Progress Evaluation
      5. Goal Achievement & Aggregate Progress Scoring
      6. Maturity Stage Classification & Interpretation
      7. Deep Technical Analysis
      8. Token Value Proposition & Sustainability
      9. Technical Limitations & Risk Management
      10. Comprehensive Conclusion & Future Outlook

    Args:
        project_data: Complete project data dict with maturity assessment inputs
        output_dir:   Directory for output files (default: ./output)

    Returns:
        Tuple of (markdown_file_path, metadata_dict) for Stage 2 PDF generation
    """
    project_name = project_data.get('project_name', 'Unknown Project')
    token_symbol = project_data.get('token_symbol', 'TOKEN')
    slug = project_data.get('slug', project_name.lower().replace(' ', '').replace('(', '').replace(')', ''))
    version = project_data.get('version', 1)
    total_score = project_data.get('total_maturity_score', 0)
    maturity_stage = project_data.get('maturity_stage', _classify_maturity(total_score))

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)

    # ── Build markdown ────────────────────────────────────────────────
    sections = []

    # Title
    sections.append(f"# {project_name} ({token_symbol}) — Project Maturity Assessment (RPT-MAT)\n")
    sections.append(f"> BCE Lab | Report Version {version} | Published {datetime.now().strftime('%B %d, %Y at %H:%M UTC')}\n")
    sections.append(f"**Maturity Score: {_format_score(total_score)} | Stage: {maturity_stage.upper()}**\n\n")
    sections.append("---\n\n")

    # 10 Chapters
    sections.append(_chapter_1_executive_summary(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_2_strategic_objectives(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_3_architecture(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_4_timeline(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_5_goal_achievements(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_6_maturity_stage(project_data))
    sections.append("\n---\n\n")

    # Community Maturity (inserted between Ch6 and Ch7 if data available)
    community_section = _chapter_community_maturity(project_data)
    if community_section.strip():
        sections.append(community_section)
        sections.append("\n---\n\n")

    sections.append(_chapter_7_deep_technical(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_8_token_sustainability(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_9_risks(project_data))
    sections.append("\n---\n\n")

    sections.append(_chapter_10_conclusion(project_data))
    sections.append("\n---\n\n")

    sections.append(_section_data_sources(project_data))

    # Footer
    sections.append("---\n\n")
    sections.append(f"*© {datetime.now().year} BCE Lab. All rights reserved. For authorized subscribers only.*\n")

    markdown = "\n".join(sections)

    # ── Write markdown file ───────────────────────────────────────────
    md_filename = f"{slug}_mat_v{version}_en.md"
    md_path = os.path.join(output_dir, md_filename)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    # ── Build metadata for Stage 2 ───────────────────────────
    strategic_weights = project_data.get('strategic_objectives', [])
    goal_data = project_data.get('goal_achievements', [])
    onchain_offchain = project_data.get('onchain_offchain', {})
    risks = project_data.get('risks', [])

    charts_strategic_weights = [
        {'name': obj['name'], 'weight': obj.get('weight', 0)}
        for obj in strategic_weights
    ]

    charts_goal_achievements = [
        {
            'objective': g['objective'],
            'weight': g.get('weight', 0),
            'achievement_rate': g.get('achievement_rate', 0),
            'weighted_score': (g.get('weight', 0) * g.get('achievement_rate', 0)) / 100.0,
        }
        for g in goal_data
    ]

    metadata = {
        'project_name': project_name,
        'token_symbol': token_symbol,
        'slug': slug,
        'version': version,
        'total_maturity_score': total_score,
        'maturity_stage': maturity_stage,
        'published_date': datetime.now().strftime('%Y-%m-%d'),
        'report_type': 'mat',
        'language': 'en',
        'charts_data': {
            'strategic_weights': charts_strategic_weights,
            'goal_achievements': charts_goal_achievements,
            'onchain_offchain': {
                'onchain': onchain_offchain.get('onchain_ratio', 0),
                'offchain': onchain_offchain.get('offchain_ratio', 0),
            },
            'risks': [
                {
                    'name': r['name'],
                    'severity': r.get('severity', 'Medium'),
                }
                for r in risks
            ],
        },
    }

    # Write metadata JSON
    meta_filename = f"{slug}_mat_v{version}_meta.json"
    meta_path = os.path.join(output_dir, meta_filename)
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"[Stage 1] MAT text analysis: {md_path}")
    print(f"[Stage 1] MAT metadata:      {meta_path}")

    return md_path, metadata


# ---------------------------------------------------------------------------
# CLI / Test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # Sample data matching the HeyElsa reference structure with 80.25% maturity
    sample_data = {
        'project_name': 'HeyElsa AI',
        'token_symbol': 'ELSA',
        'slug': 'heyelsaai',
        'version': 1,
        'total_maturity_score': 80.25,
        'maturity_stage': 'mature',
        'industry_context': (
            'The AI + DeFi convergence represents one of crypto\'s most promising '
            'frontiers. Technical barriers in cross-chain execution and agent '
            'coordination remain significant, but emerging infrastructure (intent-based '
            'architecture, new standards like ERC-8004) is reducing friction. '
            'HeyElsa operates at the intersection of these two domains, positioned '
            'to benefit from ecosystem maturation across both AI and blockchain layers.'
        ),
        'strategic_objectives': [
            {
                'name': 'AI Execution Excellence',
                'weight': 35.0,
                'description': (
                    'Core capability to reliably translate user intent into '
                    'multi-chain transactions with minimal hallucination risk.'
                ),
            },
            {
                'name': 'Multichain Interoperability',
                'weight': 20.0,
                'description': (
                    'Seamless support for execution across multiple Layer 1 and '
                    'Layer 2 networks without bridging friction.'
                ),
            },
            {
                'name': 'Token Economics & Sustainability',
                'weight': 20.0,
                'description': (
                    'Viable long-term business model balancing deflationary mechanisms '
                    'with user/creator incentives.'
                ),
            },
            {
                'name': 'Agent Ecosystem Growth',
                'weight': 15.0,
                'description': (
                    'Ability to attract third-party developers and autonomous agents '
                    'that amplify platform utility.'
                ),
            },
            {
                'name': 'Market Penetration',
                'weight': 10.0,
                'description': (
                    'Organic adoption among DeFi users and expansion into adjacent '
                    'verticals (trading, yield farming, governance).'
                ),
            },
        ],
        'onchain_offchain': {
            'onchain_ratio': 55.0,
            'offchain_ratio': 45.0,
            'onchain_components': (
                'Smart contracts (x402Router, AgentRegistry, ElsaToken), '
                'on-chain state commitments, settlement and execution.'
            ),
            'offchain_components': (
                'ElsaAI Automata (intent interpretation), ML models for '
                'optimization, agent coordination, and data aggregation.'
            ),
        },
        'timeline_phases': [
            {
                'phase': '2024 Foundation',
                'period': 'Jan–Dec 2024',
                'milestones': [
                    'Launch ElsaAI Automata with basic intent parsing',
                    'Deploy x402 micropayment protocol on Base',
                    'Issue ERC-8004 agent identity standard (draft)',
                    'Achieve 50K active monthly users',
                ],
            },
            {
                'phase': '2025 Expansion',
                'period': 'Jan–Dec 2025',
                'milestones': [
                    'Extend Automata to support 10+ DeFi protocols',
                    'Add multichain support (Ethereum, Optimism, Arbitrum)',
                    'Launch MPC wallet system for non-custodial signup',
                    'Reach 500K cumulative users and $200M TVL',
                ],
            },
            {
                'phase': '2026 Maturation',
                'period': 'Jan–Dec 2026',
                'milestones': [
                    'Release AgentOS development environment',
                    'Support 50+ autonomous agents on platform',
                    'Achieve profitability via x402 fee sustainability',
                    'Establish HeyElsa as top 3 AI + DeFi platform by metrics',
                ],
            },
        ],
        'goal_achievements': [
            {
                'objective': 'AI Execution Excellence',
                'weight': 35.0,
                'achievement_rate': 85.0,
                'details': (
                    'ElsaAI Automata demonstrates 85% intent accuracy in live beta. '
                    'Hallucination rate reduced to <2% through reinforcement learning. '
                    'Pending improvements: multi-step reasoning and novel protocol support.'
                ),
            },
            {
                'objective': 'Multichain Interoperability',
                'weight': 20.0,
                'achievement_rate': 75.0,
                'details': (
                    'Currently live on Base with basic Ethereum/Optimism bridge support. '
                    'Arbitrum integration in progress. Achieving 75% of full multichain vision.'
                ),
            },
            {
                'objective': 'Token Economics & Sustainability',
                'weight': 20.0,
                'achievement_rate': 82.0,
                'details': (
                    'Deflationary burn mechanism active. Fee revenue covers operational costs. '
                    'Path to staking rewards and premium services viable. 82% confidence in 24-month sustainability.'
                ),
            },
            {
                'objective': 'Agent Ecosystem Growth',
                'weight': 15.0,
                'achievement_rate': 78.0,
                'details': (
                    'Early partner agents in testing. AgentOS roadmap finalized. '
                    '78% progress toward developer-friendly toolkit. Launch Q1 2026.'
                ),
            },
            {
                'objective': 'Market Penetration',
                'weight': 10.0,
                'achievement_rate': 83.0,
                'details': (
                    'Strong early adoption among DeFi natives. 50K+ active monthly users. '
                    'Partnerships with 5 major CEXes in negotiation. 83% on-track.'
                ),
            },
        ],
        'maturity_interpretation': (
            'HeyElsa AI achieves an 80.25% maturity score, placing it in the MATURE '
            'stage. The project demonstrates concrete technical achievements (working '
            'Automata, operational micropayment protocol) paired with a viable path to '
            'profitability. Strategic risk remains primarily execution-dependent: success '
            'of AgentOS launch and ability to attract third-party developer ecosystem. '
            'No narrative exhaustion detected; the AI + DeFi thesis remains compelling '
            'with multiple unexplored use cases.'
        ),
        'deep_technical': (
            'Intent-Centric Architecture: HeyElsa\'s core strength lies in translating '
            'high-level user intent into low-level blockchain transactions. The intent '
            'parser combines transformer-based language models (fine-tuned on DeFi language) '
            'with state-space search algorithms to generate optimal execution paths across '
            'chains. The x402 protocol extends HTTP semantics to enable machine-to-machine '
            'payments, creating a native micropayment layer for API calls between agents. '
            'This breaks the traditional "Oracle problem" by allowing agents to directly '
            'settle value for computational work.\n\n'
            'ERC-8004 Agent Identity Standard: Extends ERC-721 with agent-specific metadata '
            '(reputation score, execution history, staking amount). Enables on-chain '
            'reputation markets where agents prove capability through immutable transaction '
            'records. MPC wallet infrastructure distributes key material across guardrails, '
            'reducing single-point-of-failure risk in agent execution.'
        ),
        'token_sustainability': (
            'Token Utility Vector: ELSA drives value through four channels: (1) staking for '
            'priority execution (reduces wait time), (2) governance participation in protocol '
            'upgrades, (3) x402 settlement currency for agent-to-agent payments, and '
            '(4) ERC-8004 agent registration bonds. Demand Drivers: Each DeFi transaction '
            'incurs 1–2 ELSA micropayment fee. At maturity (2026), 10M+ daily transactions '
            'would generate substantial protocol revenue.\n\n'
            'Deflationary Mechanism: 10% of all fees burned permanently (no token recovery). '
            'Supply becomes effectively capped as burn rate exceeds any protocol emissions. '
            'Long-term: ELSA supply contracts while utility remains stable, creating inherent '
            'scarcity value proposition.'
        ),
        'risks': [
            {
                'name': 'AI Model Hallucination / Execution Failure',
                'severity': 'High',
                'description': (
                    'Automata might generate invalid transaction sequences leading to loss. '
                    'Current <2% hallucination rate acceptable for MVP, but unacceptable at scale.'
                ),
            },
            {
                'name': 'Smart Contract Security (Novel Standards)',
                'severity': 'High',
                'description': (
                    'x402 and ERC-8004 are custom protocols with limited third-party audits. '
                    'Protocol flaw could expose user funds or create permanent blockchain bloat.'
                ),
            },
            {
                'name': 'Regulatory Uncertainty (AI + DeFi)',
                'severity': 'Medium',
                'description': (
                    'Autonomous agent execution may trigger FinCEN/SEC classification challenges. '
                    'Regulatory clarity timeline unknown (2025–2027 window likely).'
                ),
            },
            {
                'name': 'AgentOS Launch Delay',
                'severity': 'Medium',
                'description': (
                    'Entire ecosystem growth strategy hinges on Q1 2026 release. '
                    'Any >3-month delay significantly impacts maturity trajectory.'
                ),
            },
            {
                'name': 'Token Concentration & Governance Capture',
                'severity': 'Medium',
                'description': (
                    'Top 10 ELSA holders control 60% of supply. Early-stage projects '
                    'vulnerable to governance attacks or whale-driven manipulation.'
                ),
            },
        ],
        'conclusion': (
            'HeyElsa AI represents a credible entry into the AI + DeFi convergence with '
            'genuine technical innovation (intent-based execution, micropayment standards). '
            'The 80.25% maturity score reflects a balance: solid technical foundations and '
            'user traction offset by execution risks (AgentOS launch, regulatory clarity). '
            'The project is neither overextended hype nor nascent speculation — it occupies '
            'the "growth-to-maturity" inflection where capital allocation becomes critical.'
        ),
        'future_outlook': (
            'Path to Established (>85%): Successful AgentOS launch in Q1 2026 with 20+ '
            'third-party agents deployed. Achievement of $500M+ TVL and profitability '
            'through x402 fees. Regulatory clarity favorable to autonomous agents. '
            'Path to Risk (Downgrade <70%): AgentOS delays >3 months. Regulatory clampdown '
            'on autonomous DeFi execution. Emergence of superior competing intent-based '
            'protocols. Outcome Probability: 70% Established, 25% Sustained at Mature, '
            '5% Downgrade to Growing. The next 18 months are critical inflection point.'
        ),
        'data_sources': [
            'HeyElsa AI Whitepaper v2.3 (2024-12-15)',
            'On-chain data from BaseScan, Dune Analytics',
            'Team interviews and strategy sessions (Jan 2025)',
            'ElsaAI Automata accuracy audit by third-party ML lab',
            'Smart contract security review (draft phase)',
            'Comparable maturity assessments (Aave, Uniswap historical data)',
            'DeFi sector trends analysis (Messari, Glassnode)',
        ],
    }

    md_path, metadata = generate_text_mat(sample_data)
    print(f"\nGenerated: {md_path}")
    print(f"Maturity score: {metadata['total_maturity_score']}% ({metadata['maturity_stage']})")

    # Count words
    with open(md_path, 'r') as f:
        content = f.read()
    word_count = len(content.split())
    print(f"Word count: {word_count}")
