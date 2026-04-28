"""
Chart Engine v2 — BCE Lab High-Quality Chart Renderer
=====================================================
Replaces matplotlib-only rendering with Plotly + Kaleido for publication-grade visuals.

Quality Targets:
    ┌─────────────────────────────────────────────────────┐
    │  Parameter        │  Before (v1)  │  After (v2)     │
    ├───────────────────┼───────────────┼─────────────────┤
    │  DPI              │  150          │  300 (2x)       │
    │  Format           │  PNG          │  PNG @2x scale  │
    │  Anti-aliasing    │  matplotlib   │  Plotly/SVG     │
    │  Color scheme     │  5-color      │  12-color pro   │
    │  Chart width      │  130-140mm    │  110-120mm      │
    │  Chart types      │  3 per report │  5-7 per report │
    │  Gauge quality    │  Custom arc   │  Plotly native  │
    │  Infographics     │  None         │  KPI cards      │
    └─────────────────────────────────────────────────────┘

Architecture:
    chart_engine.py (this module)
        ├── render_bar_chart()
        ├── render_pie_chart() / render_donut_chart()
        ├── render_radar_chart()
        ├── render_gauge_chart()
        ├── render_risk_matrix()
        ├── render_line_chart()
        ├── render_heatmap()
        ├── render_kpi_card()         ← NEW: infographic-style
        ├── render_lifecycle_timeline() ← NEW: methodology
        └── _export_image()           ← central quality control

    All functions return BytesIO PNG buffer ready for ReportLab Image().

Usage:
    from chart_engine import ChartEngine
    engine = ChartEngine()
    buf = engine.render_bar_chart(
        labels=['DeFi', 'NFT', 'L2'],
        values=[85, 72, 90],
        title='Tech Pillar Scores',
    )
    # Use in ReportLab:
    from reportlab.lib.units import mm
    from reportlab.platypus import Image
    img = Image(buf, width=110*mm, height=70*mm)
"""

import io
import math
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import plotly.graph_objects as go
    import plotly.io as pio
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ═══════════════════════════════════════════════════════════════
#  COLOR SYSTEM — Publication-grade palette
# ═══════════════════════════════════════════════════════════════

class Palette:
    """Professional color palette for blockchain research reports."""

    # ── Primary (indigo spectrum) ──
    INDIGO_900 = '#312E81'
    INDIGO_700 = '#4338CA'
    INDIGO_600 = '#4F46E5'
    INDIGO_500 = '#6366F1'
    INDIGO_400 = '#818CF8'
    INDIGO_300 = '#A5B4FC'
    INDIGO_200 = '#C7D2FE'
    INDIGO_100 = '#E0E7FF'

    # ── Semantic colors ──
    SUCCESS    = '#059669'   # Emerald-600
    WARNING    = '#D97706'   # Amber-600
    DANGER     = '#DC2626'   # Red-600
    INFO       = '#0284C7'   # Sky-600

    # ── Neutral ──
    SLATE_900  = '#0F172A'
    SLATE_800  = '#1E293B'
    SLATE_700  = '#334155'
    SLATE_600  = '#475569'
    SLATE_400  = '#94A3B8'
    SLATE_200  = '#E2E8F0'
    SLATE_100  = '#F1F5F9'
    SLATE_50   = '#F8FAFC'
    WHITE      = '#FFFFFF'

    # ── Forensic (red spectrum) ──
    FORENSIC_900 = '#7F1D1D'
    FORENSIC_700 = '#B91C1C'
    FORENSIC_500 = '#EF4444'
    FORENSIC_300 = '#FCA5A5'

    # ── Extended categorical palette (12 colors for diverse charts) ──
    CATEGORICAL = [
        '#4F46E5',  # Indigo
        '#0891B2',  # Cyan
        '#059669',  # Emerald
        '#D97706',  # Amber
        '#DC2626',  # Red
        '#7C3AED',  # Violet
        '#DB2777',  # Pink
        '#0284C7',  # Sky
        '#65A30D',  # Lime
        '#EA580C',  # Orange
        '#6366F1',  # Indigo light
        '#14B8A6',  # Teal
    ]

    # ── Gradient presets ──
    INDIGO_GRADIENT = [INDIGO_600, INDIGO_500, INDIGO_400, INDIGO_300, INDIGO_200, INDIGO_100]
    RED_GRADIENT = ['#DC2626', '#EF4444', '#F87171', '#FCA5A5', '#FECACA', '#FEE2E2']
    RISK_SEVERITY = {
        'critical': '#DC2626',
        'high':     '#EA580C',
        'medium':   '#D97706',
        'low':      '#059669',
    }

    @classmethod
    def score_color(cls, score: float, max_score: float = 100) -> str:
        """Return color based on score percentage."""
        pct = (score / max_score) * 100 if max_score > 0 else 0
        if pct >= 80:
            return cls.SUCCESS
        elif pct >= 60:
            return cls.INDIGO_600
        elif pct >= 40:
            return cls.WARNING
        else:
            return cls.DANGER

    @classmethod
    def risk_color(cls, score: float) -> str:
        """Return color based on risk score (higher = worse)."""
        if score >= 15:
            return cls.DANGER
        elif score >= 9:
            return cls.WARNING
        else:
            return cls.SUCCESS


# ═══════════════════════════════════════════════════════════════
#  QUALITY PARAMETERS
# ═══════════════════════════════════════════════════════════════

class Quality:
    """Central quality control parameters."""
    SCALE = 3             # Plotly export scale (3x = ~300 DPI equivalent)
    DPI = 300             # Matplotlib fallback DPI
    FORMAT = 'png'
    FONT_FAMILY = 'Arial, Helvetica, sans-serif'
    TITLE_SIZE = 14
    LABEL_SIZE = 11
    TICK_SIZE = 10
    ANNOTATION_SIZE = 10
    BG_COLOR = Palette.WHITE
    PLOT_BG = Palette.SLATE_50
    GRID_COLOR = Palette.SLATE_200
    GRID_WIDTH = 0.5

    # Default chart dimensions (pixels at scale=3)
    DEFAULT_WIDTH = 800
    DEFAULT_HEIGHT = 500


# ═══════════════════════════════════════════════════════════════
#  CHART ENGINE
# ═══════════════════════════════════════════════════════════════

class ChartEngine:
    """
    High-quality chart renderer for BCE Lab reports.
    Primary: Plotly + Kaleido. Fallback: Matplotlib.
    """

    def __init__(self, theme: str = 'default'):
        """
        Args:
            theme: 'default' (indigo) or 'forensic' (red)
        """
        self.theme = theme
        self._plotly_available = HAS_PLOTLY

        if self._plotly_available:
            # Configure Plotly defaults
            pio.templates.default = 'plotly_white'

    # ─── Internal: Export to BytesIO ──────────────────────────

    def _export_plotly(
        self,
        fig: 'go.Figure',
        width: int = Quality.DEFAULT_WIDTH,
        height: int = Quality.DEFAULT_HEIGHT,
    ) -> io.BytesIO:
        """Export Plotly figure to high-quality PNG BytesIO."""
        buf = io.BytesIO()
        # Compatible with both Kaleido v0 (bundled Chromium) and v1 (system Chrome)
        try:
            fig.write_image(
                buf,
                format=Quality.FORMAT,
                width=width,
                height=height,
                scale=Quality.SCALE,
            )
        except Exception:
            # Fallback: try without scale
            fig.write_image(buf, format=Quality.FORMAT, width=width * 2, height=height * 2)
        buf.seek(0)
        return buf

    def _export_matplotlib(
        self,
        fig: 'plt.Figure',
    ) -> io.BytesIO:
        """Export Matplotlib figure to high-quality PNG BytesIO."""
        buf = io.BytesIO()
        fig.savefig(
            buf,
            format='png',
            dpi=Quality.DPI,
            bbox_inches='tight',
            facecolor=Quality.BG_COLOR,
            edgecolor='none',
            pad_inches=0.1,
        )
        plt.close(fig)
        buf.seek(0)
        return buf

    def _base_layout(
        self,
        title: str = '',
        width: int = Quality.DEFAULT_WIDTH,
        height: int = Quality.DEFAULT_HEIGHT,
        show_legend: bool = True,
    ) -> dict:
        """Base Plotly layout with BCE Lab styling."""
        return dict(
            title=dict(
                text=title,
                font=dict(size=Quality.TITLE_SIZE, color=Palette.SLATE_800, family=Quality.FONT_FAMILY),
                x=0.5,
                xanchor='center',
            ) if title else None,
            font=dict(family=Quality.FONT_FAMILY, size=Quality.LABEL_SIZE, color=Palette.SLATE_700),
            plot_bgcolor=Quality.PLOT_BG,
            paper_bgcolor=Quality.BG_COLOR,
            width=width,
            height=height,
            margin=dict(l=60, r=30, t=50 if title else 20, b=50),
            showlegend=show_legend,
            legend=dict(
                font=dict(size=Quality.TICK_SIZE),
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor=Palette.SLATE_200,
                borderwidth=1,
            ),
        )

    # ═══════════════════════════════════════════════════════════
    #  CHART RENDERERS
    # ═══════════════════════════════════════════════════════════

    def render_bar_chart(
        self,
        labels: List[str],
        values: List[float],
        title: str = '',
        horizontal: bool = True,
        color: str = None,
        color_map: List[str] = None,
        value_suffix: str = '',
        max_value: float = None,
        width: int = 800,
        height: int = None,
    ) -> io.BytesIO:
        """
        Professional bar chart with value labels.

        Args:
            labels: Category names
            values: Numeric values
            horizontal: If True, horizontal bars (better for long labels)
            color: Single color for all bars
            color_map: Per-bar colors (overrides color)
            value_suffix: e.g., '%', 'pts'
            max_value: Force x/y axis max
        """
        if not self._plotly_available:
            return self._fallback_bar(labels, values, title, horizontal)

        if height is None:
            height = max(350, len(labels) * 45 + 80) if horizontal else 450

        colors = color_map or [color or Palette.INDIGO_600] * len(values)
        if len(colors) < len(values):
            colors = (colors * (len(values) // len(colors) + 1))[:len(values)]

        text_vals = [f'{v:.1f}{value_suffix}' if isinstance(v, float) else f'{v}{value_suffix}' for v in values]

        if horizontal:
            fig = go.Figure(go.Bar(
                y=labels, x=values,
                orientation='h',
                marker=dict(
                    color=colors,
                    line=dict(color=Palette.SLATE_200, width=1),
                    cornerradius=4,
                ),
                text=text_vals,
                textposition='outside',
                textfont=dict(size=Quality.ANNOTATION_SIZE, color=Palette.SLATE_700),
            ))
            xmax = max_value or (max(values) * 1.25 if values else 100)
            fig.update_xaxes(range=[0, xmax], gridcolor=Quality.GRID_COLOR, gridwidth=Quality.GRID_WIDTH)
            fig.update_yaxes(gridcolor='rgba(0,0,0,0)')
        else:
            fig = go.Figure(go.Bar(
                x=labels, y=values,
                marker=dict(
                    color=colors,
                    line=dict(color=Palette.SLATE_200, width=1),
                    cornerradius=4,
                ),
                text=text_vals,
                textposition='outside',
                textfont=dict(size=Quality.ANNOTATION_SIZE, color=Palette.SLATE_700),
            ))
            ymax = max_value or (max(values) * 1.25 if values else 100)
            fig.update_yaxes(range=[0, ymax], gridcolor=Quality.GRID_COLOR, gridwidth=Quality.GRID_WIDTH)
            fig.update_xaxes(gridcolor='rgba(0,0,0,0)')

        layout = self._base_layout(title, width, height, show_legend=False)
        fig.update_layout(**layout)

        return self._export_plotly(fig, width, height)

    def render_pie_chart(
        self,
        labels: List[str],
        values: List[float],
        title: str = '',
        hole: float = 0,
        colors: List[str] = None,
        width: int = 650,
        height: int = 500,
    ) -> io.BytesIO:
        """
        Professional pie/donut chart.

        Args:
            hole: 0 for pie, 0.35-0.5 for donut
            colors: Custom color list
        """
        if not self._plotly_available:
            return self._fallback_pie(labels, values, title, hole)

        palette = colors or Palette.CATEGORICAL[:len(labels)]

        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=hole,
            marker=dict(
                colors=palette,
                line=dict(color=Palette.WHITE, width=2),
            ),
            textinfo='label+percent',
            textfont=dict(size=Quality.LABEL_SIZE, color=Palette.SLATE_800),
            hoverinfo='label+value+percent',
            pull=[0.02] * len(labels),
        ))

        layout = self._base_layout(title, width, height, show_legend=False)
        fig.update_layout(**layout)

        return self._export_plotly(fig, width, height)

    def render_donut_chart(
        self,
        labels: List[str],
        values: List[float],
        title: str = '',
        center_text: str = '',
        colors: List[str] = None,
        width: int = 550,
        height: int = 450,
    ) -> io.BytesIO:
        """Donut chart with optional center annotation."""
        buf = self.render_pie_chart(labels, values, title, hole=0.45, colors=colors, width=width, height=height)

        if center_text and self._plotly_available:
            # Re-render with center annotation
            palette = colors or Palette.CATEGORICAL[:len(labels)]
            fig = go.Figure(go.Pie(
                labels=labels, values=values, hole=0.45,
                marker=dict(colors=palette, line=dict(color=Palette.WHITE, width=2)),
                textinfo='label+percent',
                textfont=dict(size=Quality.LABEL_SIZE),
                pull=[0.02] * len(labels),
            ))
            layout = self._base_layout(title, width, height, show_legend=False)
            layout['annotations'] = [dict(
                text=center_text,
                x=0.5, y=0.5,
                font=dict(size=16, color=Palette.SLATE_800, family=Quality.FONT_FAMILY),
                showarrow=False,
            )]
            fig.update_layout(**layout)
            return self._export_plotly(fig, width, height)

        return buf

    def render_gauge_chart(
        self,
        value: float,
        max_value: float = 100,
        title: str = '',
        suffix: str = '%',
        thresholds: Dict[str, float] = None,
        width: int = 500,
        height: int = 350,
    ) -> io.BytesIO:
        """
        Professional gauge/speedometer chart.

        Args:
            thresholds: {'danger': 40, 'warning': 70} — boundaries
        """
        if not self._plotly_available:
            return self._fallback_gauge(value, max_value, title)

        if thresholds is None:
            thresholds = {'danger': max_value * 0.4, 'warning': max_value * 0.7}

        danger_bound = thresholds.get('danger', max_value * 0.4)
        warning_bound = thresholds.get('warning', max_value * 0.7)

        fig = go.Figure(go.Indicator(
            mode='gauge+number',
            value=value,
            number=dict(suffix=suffix, font=dict(size=28, color=Palette.SLATE_800)),
            gauge=dict(
                axis=dict(
                    range=[0, max_value],
                    tickwidth=1,
                    tickcolor=Palette.SLATE_400,
                    tickfont=dict(size=Quality.TICK_SIZE),
                ),
                bar=dict(color=Palette.INDIGO_600, thickness=0.75),
                bgcolor=Palette.SLATE_100,
                borderwidth=0,
                steps=[
                    dict(range=[0, danger_bound], color='#FEE2E2'),
                    dict(range=[danger_bound, warning_bound], color='#FEF3C7'),
                    dict(range=[warning_bound, max_value], color='#D1FAE5'),
                ],
                threshold=dict(
                    line=dict(color=Palette.DANGER, width=3),
                    thickness=0.8,
                    value=value,
                ),
            ),
        ))

        layout = self._base_layout(title, width, height, show_legend=False)
        layout['margin'] = dict(l=30, r=30, t=60 if title else 30, b=10)
        fig.update_layout(**layout)

        return self._export_plotly(fig, width, height)

    def render_radar_chart(
        self,
        categories: List[str],
        values: List[float],
        title: str = '',
        max_value: float = 100,
        fill: bool = True,
        color: str = None,
        width: int = 600,
        height: int = 500,
    ) -> io.BytesIO:
        """
        Radar/spider chart for multi-dimensional scoring.
        NEW chart type — not available in v1.
        """
        if not self._plotly_available:
            return self._fallback_radar(categories, values, title, max_value)

        c = color or Palette.INDIGO_600
        # Close the polygon
        cats = categories + [categories[0]]
        vals = values + [values[0]]

        fig = go.Figure(go.Scatterpolar(
            r=vals,
            theta=cats,
            fill='toself' if fill else 'none',
            fillcolor=f'rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.15)',
            line=dict(color=c, width=2.5),
            marker=dict(size=6, color=c),
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, max_value],
                    gridcolor=Quality.GRID_COLOR,
                    tickfont=dict(size=Quality.TICK_SIZE - 1),
                ),
                angularaxis=dict(
                    gridcolor=Quality.GRID_COLOR,
                    tickfont=dict(size=Quality.LABEL_SIZE),
                ),
                bgcolor=Quality.PLOT_BG,
            ),
            **self._base_layout(title, width, height, show_legend=False),
        )

        return self._export_plotly(fig, width, height)

    def render_risk_matrix(
        self,
        risks: List[Dict[str, Any]],
        title: str = '',
        width: int = 750,
        height: int = 550,
    ) -> io.BytesIO:
        """
        Risk matrix scatter plot with sized bubbles.

        Args:
            risks: List of {'name': str, 'impact': 1-5, 'probability': 1-5}
        """
        if not self._plotly_available or not risks:
            return self._fallback_risk_matrix(risks, title)

        names = [r.get('name', '?') for r in risks]
        impacts = [r.get('impact', 3) for r in risks]
        probs = [r.get('probability', 3) for r in risks]
        scores = [i * p for i, p in zip(impacts, probs)]
        colors = [Palette.risk_color(s) for s in scores]
        sizes = [max(20, s * 4) for s in scores]

        fig = go.Figure(go.Scatter(
            x=probs,
            y=impacts,
            mode='markers+text',
            marker=dict(
                size=sizes,
                color=colors,
                opacity=0.7,
                line=dict(color=Palette.SLATE_700, width=1.5),
            ),
            text=names,
            textposition='top center',
            textfont=dict(size=Quality.ANNOTATION_SIZE - 1, color=Palette.SLATE_700),
        ))

        # Background zones
        fig.add_shape(type='rect', x0=0.5, y0=0.5, x1=3, y1=3,
                      fillcolor='rgba(209,250,229,0.3)', line=dict(width=0))
        fig.add_shape(type='rect', x0=3, y0=3, x1=5.5, y1=5.5,
                      fillcolor='rgba(254,226,226,0.3)', line=dict(width=0))

        fig.update_xaxes(
            title='Probability →', range=[0.5, 5.5],
            dtick=1, gridcolor=Quality.GRID_COLOR, gridwidth=Quality.GRID_WIDTH,
        )
        fig.update_yaxes(
            title='Impact →', range=[0.5, 5.5],
            dtick=1, gridcolor=Quality.GRID_COLOR, gridwidth=Quality.GRID_WIDTH,
        )

        layout = self._base_layout(title, width, height, show_legend=False)
        fig.update_layout(**layout)

        return self._export_plotly(fig, width, height)

    def render_line_chart(
        self,
        x_data: List[Any],
        y_series: Dict[str, List[float]],
        title: str = '',
        x_title: str = '',
        y_title: str = '',
        colors: List[str] = None,
        width: int = 800,
        height: int = 450,
    ) -> io.BytesIO:
        """
        Multi-series line chart.
        NEW chart type — for price trends, volume history.

        Args:
            y_series: {'Series A': [1,2,3], 'Series B': [4,5,6]}
        """
        if not self._plotly_available:
            return self._fallback_line(x_data, y_series, title)

        palette = colors or Palette.CATEGORICAL
        fig = go.Figure()

        for i, (name, y_vals) in enumerate(y_series.items()):
            c = palette[i % len(palette)]
            fig.add_trace(go.Scatter(
                x=x_data, y=y_vals,
                mode='lines+markers',
                name=name,
                line=dict(color=c, width=2.5),
                marker=dict(size=5, color=c),
            ))

        fig.update_xaxes(title=x_title, gridcolor=Quality.GRID_COLOR, gridwidth=Quality.GRID_WIDTH)
        fig.update_yaxes(title=y_title, gridcolor=Quality.GRID_COLOR, gridwidth=Quality.GRID_WIDTH)

        layout = self._base_layout(title, width, height, show_legend=len(y_series) > 1)
        fig.update_layout(**layout)

        return self._export_plotly(fig, width, height)

    def render_heatmap(
        self,
        z_data: List[List[float]],
        x_labels: List[str],
        y_labels: List[str],
        title: str = '',
        colorscale: str = 'RdYlGn',
        width: int = 750,
        height: int = 500,
    ) -> io.BytesIO:
        """
        Heatmap for correlation matrices, risk cross-analysis.
        NEW chart type.
        """
        if not self._plotly_available:
            return self._fallback_heatmap(z_data, x_labels, y_labels, title)

        fig = go.Figure(go.Heatmap(
            z=z_data,
            x=x_labels,
            y=y_labels,
            colorscale=colorscale,
            texttemplate='%{z:.1f}',
            textfont=dict(size=Quality.ANNOTATION_SIZE),
            hoverinfo='x+y+z',
        ))

        layout = self._base_layout(title, width, height, show_legend=False)
        fig.update_layout(**layout)
        fig.update_xaxes(side='bottom')

        return self._export_plotly(fig, width, height)

    def render_kpi_card(
        self,
        metrics: List[Dict[str, Any]],
        title: str = '',
        width: int = 800,
        height: int = 200,
    ) -> io.BytesIO:
        """
        KPI scorecard infographic.
        NEW: infographic-style element not possible with matplotlib.

        Args:
            metrics: [{'label': 'Market Cap', 'value': '$45M', 'delta': '+12%', 'color': 'green'}, ...]
        """
        if not self._plotly_available or not metrics:
            return io.BytesIO()

        n = len(metrics)
        fig = go.Figure()

        for i, m in enumerate(metrics):
            col_center = (i + 0.5) / n
            color = m.get('color', Palette.INDIGO_600)
            delta = m.get('delta', '')
            delta_color = Palette.SUCCESS if delta.startswith('+') else (Palette.DANGER if delta.startswith('-') else Palette.SLATE_600)

            # Value
            fig.add_annotation(
                x=col_center, y=0.6,
                text=f"<b>{m.get('value', 'N/A')}</b>",
                font=dict(size=22, color=Palette.SLATE_800, family=Quality.FONT_FAMILY),
                showarrow=False, xref='paper', yref='paper',
            )
            # Label
            fig.add_annotation(
                x=col_center, y=0.25,
                text=m.get('label', ''),
                font=dict(size=12, color=Palette.SLATE_600, family=Quality.FONT_FAMILY),
                showarrow=False, xref='paper', yref='paper',
            )
            # Delta
            if delta:
                fig.add_annotation(
                    x=col_center, y=0.85,
                    text=delta,
                    font=dict(size=13, color=delta_color, family=Quality.FONT_FAMILY),
                    showarrow=False, xref='paper', yref='paper',
                )

            # Divider line (except last)
            if i < n - 1:
                x_div = (i + 1) / n
                fig.add_shape(
                    type='line',
                    x0=x_div, y0=0.1, x1=x_div, y1=0.9,
                    xref='paper', yref='paper',
                    line=dict(color=Palette.SLATE_200, width=1),
                )

        fig.update_layout(
            **self._base_layout(title, width, height, show_legend=False),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        fig.update_layout(margin=dict(l=10, r=10, t=30 if title else 10, b=10))

        return self._export_plotly(fig, width, height)

    def render_lifecycle_timeline(
        self,
        current_stage: str,
        stages: List[str] = None,
        title: str = '',
        width: int = 800,
        height: int = 200,
    ) -> io.BytesIO:
        """
        Lifecycle stage timeline infographic.
        NEW: Shows Genesis → Bootstrap → Mature → Stability → Evolution
        with current stage highlighted.
        """
        if not self._plotly_available:
            return io.BytesIO()

        if stages is None:
            stages = ['Genesis', 'Bootstrap', 'Mature', 'Stability', 'Evolution']

        n = len(stages)
        fig = go.Figure()

        for i, stage in enumerate(stages):
            x = (i + 0.5) / n
            is_current = stage.lower() == current_stage.lower()
            is_past = i < [s.lower() for s in stages].index(current_stage.lower()) if current_stage.lower() in [s.lower() for s in stages] else False

            # Circle marker
            color = Palette.INDIGO_600 if is_current else (Palette.INDIGO_300 if is_past else Palette.SLATE_200)
            size = 18 if is_current else 12

            fig.add_trace(go.Scatter(
                x=[x], y=[0.5],
                mode='markers+text',
                marker=dict(size=size, color=color, line=dict(color=Palette.WHITE, width=2)),
                text=[stage],
                textposition='bottom center',
                textfont=dict(
                    size=Quality.LABEL_SIZE if is_current else Quality.TICK_SIZE,
                    color=Palette.SLATE_800 if is_current else Palette.SLATE_400,
                    family=Quality.FONT_FAMILY,
                ),
                showlegend=False,
            ))

            # Connecting line
            if i < n - 1:
                x_next = (i + 1.5) / n
                line_color = Palette.INDIGO_300 if (is_past or is_current) else Palette.SLATE_200
                fig.add_shape(
                    type='line',
                    x0=x + 0.02, y0=0.5, x1=x_next - 0.02, y1=0.5,
                    xref='paper', yref='paper',
                    line=dict(color=line_color, width=2.5),
                )

        fig.update_layout(
            **self._base_layout(title, width, height, show_legend=False),
            xaxis=dict(visible=False, range=[0, 1]),
            yaxis=dict(visible=False, range=[0, 1]),
        )
        fig.update_layout(margin=dict(l=10, r=10, t=30 if title else 10, b=40))

        return self._export_plotly(fig, width, height)

    # ═══════════════════════════════════════════════════════════
    #  MATPLOTLIB FALLBACKS (if Plotly unavailable)
    # ═══════════════════════════════════════════════════════════

    def _fallback_bar(self, labels, values, title, horizontal):
        fig, ax = plt.subplots(figsize=(7, max(3, len(labels)*0.5)), dpi=Quality.DPI)
        fig.patch.set_facecolor(Quality.BG_COLOR)
        ax.set_facecolor(Quality.PLOT_BG)
        if horizontal:
            ax.barh(labels, values, color=Palette.INDIGO_600, edgecolor=Palette.SLATE_200)
        else:
            ax.bar(labels, values, color=Palette.INDIGO_600, edgecolor=Palette.SLATE_200)
        if title:
            ax.set_title(title, fontsize=Quality.TITLE_SIZE, color=Palette.SLATE_800)
        ax.grid(axis='x' if horizontal else 'y', alpha=0.2, linestyle='--')
        return self._export_matplotlib(fig)

    def _fallback_pie(self, labels, values, title, hole):
        fig, ax = plt.subplots(figsize=(6, 5), dpi=Quality.DPI)
        fig.patch.set_facecolor(Quality.BG_COLOR)
        colors = Palette.CATEGORICAL[:len(labels)]
        wedgeprops = {'width': 0.55, 'edgecolor': 'white', 'linewidth': 2} if hole > 0 else {'edgecolor': 'white', 'linewidth': 2}
        ax.pie(values, labels=labels, colors=colors, autopct='%1.1f%%', wedgeprops=wedgeprops, startangle=90)
        if title:
            ax.set_title(title, fontsize=Quality.TITLE_SIZE, color=Palette.SLATE_800)
        return self._export_matplotlib(fig)

    def _fallback_gauge(self, value, max_value, title):
        fig, ax = plt.subplots(figsize=(5, 3.5), dpi=Quality.DPI)
        fig.patch.set_facecolor(Quality.BG_COLOR)
        ax.set_facecolor(Quality.PLOT_BG)
        ax.barh([0], [value], color=Palette.INDIGO_600, height=0.5)
        ax.barh([0], [max_value - value], left=value, color=Palette.SLATE_200, height=0.5)
        ax.set_xlim(0, max_value)
        ax.set_yticks([])
        ax.text(value / 2, 0, f'{value:.0f}%', ha='center', va='center', fontsize=14, fontweight='bold', color='white')
        if title:
            ax.set_title(title, fontsize=Quality.TITLE_SIZE, color=Palette.SLATE_800)
        return self._export_matplotlib(fig)

    def _fallback_radar(self, categories, values, title, max_value):
        fig, ax = plt.subplots(figsize=(6, 5), dpi=Quality.DPI, subplot_kw=dict(polar=True))
        fig.patch.set_facecolor(Quality.BG_COLOR)
        angles = [n / float(len(categories)) * 2 * math.pi for n in range(len(categories))]
        angles += angles[:1]
        vals = values + values[:1]
        ax.plot(angles, vals, color=Palette.INDIGO_600, linewidth=2)
        ax.fill(angles, vals, color=Palette.INDIGO_600, alpha=0.15)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, size=Quality.TICK_SIZE)
        ax.set_ylim(0, max_value)
        if title:
            ax.set_title(title, fontsize=Quality.TITLE_SIZE, color=Palette.SLATE_800, pad=15)
        return self._export_matplotlib(fig)

    def _fallback_risk_matrix(self, risks, title):
        if not risks:
            return io.BytesIO()
        fig, ax = plt.subplots(figsize=(7, 5), dpi=Quality.DPI)
        fig.patch.set_facecolor(Quality.BG_COLOR)
        ax.set_facecolor(Quality.PLOT_BG)
        for r in risks:
            s = r.get('impact', 3) * r.get('probability', 3)
            ax.scatter(r.get('probability', 3), r.get('impact', 3),
                      s=s*50, c=Palette.risk_color(s), alpha=0.7, edgecolors=Palette.SLATE_700, linewidth=1.5)
            ax.annotate(r.get('name', ''), (r.get('probability', 3), r.get('impact', 3)),
                       fontsize=8, ha='center', va='bottom')
        ax.set_xlabel('Probability')
        ax.set_ylabel('Impact')
        ax.set_xlim(0.5, 5.5)
        ax.set_ylim(0.5, 5.5)
        if title:
            ax.set_title(title, fontsize=Quality.TITLE_SIZE)
        return self._export_matplotlib(fig)

    def _fallback_line(self, x_data, y_series, title):
        fig, ax = plt.subplots(figsize=(7, 4), dpi=Quality.DPI)
        fig.patch.set_facecolor(Quality.BG_COLOR)
        ax.set_facecolor(Quality.PLOT_BG)
        for i, (name, vals) in enumerate(y_series.items()):
            c = Palette.CATEGORICAL[i % len(Palette.CATEGORICAL)]
            ax.plot(x_data[:len(vals)], vals, label=name, color=c, linewidth=2, marker='o', markersize=4)
        ax.legend(fontsize=Quality.TICK_SIZE)
        ax.grid(alpha=0.2, linestyle='--')
        if title:
            ax.set_title(title, fontsize=Quality.TITLE_SIZE)
        return self._export_matplotlib(fig)

    def _fallback_heatmap(self, z_data, x_labels, y_labels, title):
        fig, ax = plt.subplots(figsize=(7, 5), dpi=Quality.DPI)
        fig.patch.set_facecolor(Quality.BG_COLOR)
        import numpy as np
        data = np.array(z_data)
        im = ax.imshow(data, cmap='RdYlGn', aspect='auto')
        ax.set_xticks(range(len(x_labels)))
        ax.set_xticklabels(x_labels, fontsize=Quality.TICK_SIZE)
        ax.set_yticks(range(len(y_labels)))
        ax.set_yticklabels(y_labels, fontsize=Quality.TICK_SIZE)
        fig.colorbar(im)
        if title:
            ax.set_title(title, fontsize=Quality.TITLE_SIZE)
        return self._export_matplotlib(fig)


# ─── Singleton ───────────────────────────────────────────────

_default_engine: Optional[ChartEngine] = None
_forensic_engine: Optional[ChartEngine] = None


def get_chart_engine(theme: str = 'default') -> ChartEngine:
    """Get or create a chart engine singleton."""
    global _default_engine, _forensic_engine
    if theme == 'forensic':
        if _forensic_engine is None:
            _forensic_engine = ChartEngine(theme='forensic')
        return _forensic_engine
    else:
        if _default_engine is None:
            _default_engine = ChartEngine(theme='default')
        return _default_engine
