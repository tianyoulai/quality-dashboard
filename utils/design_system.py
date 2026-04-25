"""设计系统 v3.0 — 统一色彩、排版、组件、图表主题。

所有页面通过本模块获取一致的设计语言，避免硬编码颜色和样式。
支持亮/暗主题自动适配。

用法：
    from utils.design_system import ds
    ds.inject_theme()                        # 注入全局CSS
    ds.hero("📊", "质培运营看板", "实时监控")  # Hero 区域
    ds.metric_card("质检量", "1,234", icon="📊") # 指标卡片
    ds.section("🚨 告警监控")                 # 分区标题
"""
from __future__ import annotations

from datetime import date
from typing import Literal

import streamlit as st


# ═══════════════════════════════════════════════════════════════
#  色彩系统 — 语义化色值命名，自动适配亮暗主题
# ═══════════════════════════════════════════════════════════════

class _Colors:
    """语义化颜色令牌。"""
    # 品牌主色
    primary = "#2563EB"       # 蓝
    primary_light = "#EFF6FF"
    primary_border = "#BFDBFE"

    # 语义色
    success = "#10B981"       # 绿
    success_light = "#ECFDF5"
    success_border = "#A7F3D0"

    warning = "#F59E0B"       # 黄
    warning_light = "#FFFBEB"
    warning_border = "#FDE68A"

    danger = "#EF4444"        # 红
    danger_light = "#FEF2F2"
    danger_border = "#FECACA"

    # 告警级别
    p0 = "#DC2626"
    p0_bg = "linear-gradient(135deg, #FEF2F2 0%, #FEE2E2 100%)"
    p1 = "#F59E0B"
    p1_bg = "linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%)"
    p2 = "#3B82F6"
    p2_bg = "linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%)"

    # 中性色
    text_primary = "#1E293B"
    text_secondary = "#64748B"
    text_muted = "#94A3B8"
    border = "#E2E8F0"
    bg_card = "#FFFFFF"
    bg_subtle = "#F8FAFC"
    bg_page = "#F1F5F9"

    # 图表色板（8色渐进）
    chart_palette = [
        "#3B82F6", "#10B981", "#F59E0B", "#EF4444",
        "#8B5CF6", "#EC4899", "#06B6D4", "#84CC16",
    ]


COLORS = _Colors()


# ═══════════════════════════════════════════════════════════════
#  排版系统
# ═══════════════════════════════════════════════════════════════

class _Typography:
    hero_title = "font-size: 1.75rem; font-weight: 800; letter-spacing: -0.025em; line-height: 1.2;"
    hero_subtitle = "font-size: 0.9rem; color: {muted}; line-height: 1.5;"
    section_title = "font-size: 1.15rem; font-weight: 700; letter-spacing: -0.01em; margin-bottom: 0.5rem;"
    card_value = "font-size: 1.75rem; font-weight: 800; letter-spacing: -0.02em;"
    card_label = "font-size: 0.78rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;"
    caption = "font-size: 0.72rem; color: {muted};"

TYPO = _Typography()


# ═══════════════════════════════════════════════════════════════
#  间距系统
# ═══════════════════════════════════════════════════════════════

class _Spacing:
    xs = "0.25rem"
    sm = "0.5rem"
    md = "1rem"
    lg = "1.5rem"
    xl = "2rem"
    xxl = "3rem"

SPACE = _Spacing()


# ═══════════════════════════════════════════════════════════════
#  DesignSystem 主类
# ═══════════════════════════════════════════════════════════════

class DesignSystem:
    """设计系统单例，提供统一的 UI 组件和样式注入。"""

    colors = COLORS
    typo = TYPO
    space = SPACE

    # ── 全局样式注入 ──────────────────────────────────────
    def inject_theme(self) -> None:
        """注入全局CSS主题 + 侧边栏品牌 + 导航。
        
        注意：Streamlit 每次页面切换/刷新都会清空 DOM，因此 CSS **必须每次注入**。
        这里不能用 session_state 缓存，否则切换页面后样式会丢失导致布局变窄。
        """
        st.markdown(self._global_css(), unsafe_allow_html=True)
        self._render_sidebar()

    def _global_css(self) -> str:
        return f"""
        <style>
            /* ===== 全局布局（强制全宽） ===== */
            .main > div {{ padding-top: 0.75rem; }}
            .block-container {{
                padding-top: 1.5rem;
                padding-bottom: 2rem;
                max-width: 100% !important;
                width: 100% !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
            }}
            /* 覆盖 Streamlit 内部的嵌套宽度限制 */
            .main .block-container {{
                max-width: 100% !important;
                width: 100% !important;
            }}
            section[data-testid="stSidebar"] ~ div.main .block-container {{
                max-width: 100% !important;
                width: 100% !important;
            }}
            .appview-container .main .block-container {{
                max-width: 100% !important;
            }}

            /* ===== 表格 ===== */
            .stDataFrame {{
                border-radius: 0.75rem;
                overflow: hidden;
                border: 1px solid {COLORS.border};
                box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            }}

            /* ===== 折叠面板 ===== */
            .streamlit-expanderHeader {{
                background: {COLORS.bg_subtle};
                border-radius: 0.5rem;
                border: 1px solid {COLORS.border};
                font-weight: 600;
            }}

            /* ===== 按钮 ===== */
            .stButton > button {{
                border-radius: 0.625rem;
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
                font-weight: 600;
                font-size: 0.85rem;
                letter-spacing: 0.01em;
            }}
            .stButton > button:hover {{
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
            }}

            /* ===== 下载按钮 ===== */
            .stDownloadButton > button {{
                background: {COLORS.success};
                color: white;
                border-radius: 0.625rem;
                font-weight: 600;
            }}
            .stDownloadButton > button:hover {{
                background: #059669;
                transform: translateY(-1px);
            }}

            /* ===== ds-card: 统一卡片基类 ===== */
            .ds-card {{
                background: {COLORS.bg_card};
                border: 1px solid {COLORS.border};
                border-radius: 0.875rem;
                padding: 1.25rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06);
                transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            }}
            .ds-card:hover {{
                box-shadow: 0 4px 16px rgba(0,0,0,0.08);
                transform: translateY(-2px);
            }}
            .ds-card-selected {{
                border: 2px solid {COLORS.primary} !important;
                box-shadow: 0 4px 16px rgba(37, 99, 235, 0.15);
            }}

            /* ===== ds-metric: 指标卡片 ===== */
            .ds-metric {{
                text-align: center;
            }}
            .ds-metric-value {{
                {TYPO.card_value}
            }}
            .ds-metric-label {{
                {TYPO.card_label}
                color: {COLORS.text_secondary};
                margin-bottom: 0.375rem;
            }}
            .ds-metric-delta {{
                font-size: 0.72rem;
                margin-top: 0.25rem;
            }}

            /* ===== ds-hero ===== */
            .ds-hero {{
                padding: 1.5rem;
                border-radius: 1rem;
                border-left: 4px solid {COLORS.primary};
                background: {COLORS.bg_card};
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                margin-bottom: 1.25rem;
            }}
            .ds-hero-title {{
                {TYPO.hero_title}
                color: {COLORS.text_primary};
                margin: 0;
            }}
            .ds-hero-subtitle {{
                {TYPO.hero_subtitle.format(muted=COLORS.text_secondary)}
                margin-top: 0.5rem;
            }}
            .ds-hero-badge {{
                display: inline-block;
                background: {COLORS.bg_subtle};
                padding: 0.15rem 0.5rem;
                border-radius: 0.375rem;
                font-size: 0.8rem;
                color: {COLORS.text_primary};
                border: 1px solid {COLORS.border};
            }}

            /* ===== ds-section ===== */
            .ds-section {{
                {TYPO.section_title}
                color: {COLORS.text_primary};
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-top: 1.75rem;
                padding-bottom: 0.5rem;
                border-bottom: 2px solid {COLORS.border};
            }}

            /* ===== ds-alert-badge ===== */
            .ds-alert-badge {{
                padding: 0.75rem;
                border-radius: 0.75rem;
                text-align: center;
                border: 2px solid;
                transition: transform 0.15s ease;
            }}
            .ds-alert-badge:hover {{ transform: scale(1.03); }}
            .ds-alert-badge-value {{
                font-size: 1.75rem;
                font-weight: 800;
                line-height: 1;
            }}
            .ds-alert-badge-label {{
                font-size: 0.72rem;
                font-weight: 600;
                margin-top: 0.25rem;
            }}

            /* ===== ds-breadcrumb ===== */
            .ds-breadcrumb {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.85rem;
                padding: 0.5rem 0;
            }}
            .ds-breadcrumb-item {{
                display: inline-flex;
                align-items: center;
                gap: 0.25rem;
                padding: 0.2rem 0.625rem;
                border-radius: 0.375rem;
                font-weight: 600;
                font-size: 0.82rem;
            }}
            .ds-breadcrumb-sep {{
                color: {COLORS.text_muted};
                font-size: 0.75rem;
            }}

            /* ===== ds-divider ===== */
            .ds-divider {{
                height: 1px;
                background: {COLORS.border};
                margin: 1.25rem 0;
            }}

            /* ===== ds-status-chip ===== */
            .ds-chip {{
                display: inline-flex;
                align-items: center;
                gap: 0.25rem;
                font-size: 0.72rem;
                font-weight: 600;
                padding: 0.2rem 0.5rem;
                border-radius: 9999px;
            }}

            /* ===== 动画 ===== */
            @keyframes ds-fadein {{
                from {{ opacity: 0; transform: translateY(8px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .ds-animate {{ animation: ds-fadein 0.3s ease-out; }}

            /* ===== 移动端适配 ===== */
            @media (max-width: 768px) {{
                .block-container {{
                    padding-left: 0.5rem !important;
                    padding-right: 0.5rem !important;
                }}
                section[data-testid="stSidebar"] {{
                    width: 0 !important;
                    min-width: 0 !important;
                }}
                [data-testid="column"] {{
                    min-width: 100% !important;
                }}
                .ds-hero {{ padding: 1rem; }}
                .ds-hero-title {{ font-size: 1.35rem !important; }}
                .ds-metric-value {{ font-size: 1.4rem !important; }}
                .stButton > button {{ min-height: 2.5rem; }}
                .stDataFrame {{ overflow-x: auto !important; }}
            }}

            /* ===== 平板适配 ===== */
            @media (min-width: 769px) and (max-width: 1024px) {{
                .block-container {{
                    padding-left: 1rem !important;
                    padding-right: 1rem !important;
                }}
            }}
        </style>
        """

    # ── 侧边栏 ──────────────────────────────────────
    def _render_sidebar(self) -> None:
        """渲染侧边栏：快捷导航 + 品牌标识。"""
        with st.sidebar:
            st.markdown(f"""
            <div style="text-align: center; padding: 0.75rem 0 0.5rem;">
                <div style="font-size: 1.25rem; font-weight: 800; color: {COLORS.primary};">📊 质培运营看板</div>
                <div style="font-size: 0.7rem; color: {COLORS.text_muted}; margin-top: 0.25rem;">v3.0 · 数据驱动质量提升</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")

            # 快捷导航
            st.markdown(f"""
            <div style="font-size: 0.75rem; font-weight: 600; color: {COLORS.text_secondary}; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem;">
                快捷操作
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔄 刷新缓存", key="ds_refresh_cache", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

            st.markdown("---")

            # 底部信息
            st.markdown(f"""
            <div style="text-align: center; padding: 0.5rem; opacity: 0.6;">
                <div style="font-size: 0.7rem; color: {COLORS.text_muted};">
                    🕐 {date.today().strftime('%Y-%m-%d')}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Hero 组件 ──────────────────────────────────────
    def hero(self, icon: str, title: str, subtitle: str, badges: list[str] | None = None) -> None:
        """渲染页面顶部 Hero 区域。"""
        badge_html = ""
        if badges:
            badge_html = '<div style="margin-top: 0.75rem;">' + " ".join(
                f'<span class="ds-hero-badge">{b}</span>' for b in badges
            ) + '</div>'

        st.markdown(f"""
        <div class="ds-hero ds-animate">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h1 class="ds-hero-title">{icon} {title}</h1>
                <div style="font-size: 0.8rem; color: {COLORS.text_muted};">{subtitle}</div>
            </div>
            {badge_html}
        </div>
        """, unsafe_allow_html=True)

    # ── 分区标题 ──────────────────────────────────────
    def section(self, text: str) -> None:
        """渲染分区标题（带底部分割线）。"""
        st.markdown(f'<div class="ds-section">{text}</div>', unsafe_allow_html=True)

    # ── 分割线 ──────────────────────────────────────
    def divider(self) -> None:
        st.markdown('<div class="ds-divider"></div>', unsafe_allow_html=True)

    # ── 指标卡片 ──────────────────────────────────────
    def metric_card(
        self,
        label: str,
        value: str,
        delta: str = "",
        icon: str = "",
        color: str = "",
        border_color: str = "",
    ) -> None:
        """渲染单个指标卡片。"""
        _border = f"border-left: 3px solid {border_color};" if border_color else ""
        _color = f"color: {color};" if color else f"color: {COLORS.text_primary};"
        _icon = f'<span style="font-size: 1.1rem;">{icon}</span> ' if icon else ""
        _delta = f'<div class="ds-metric-delta">{delta}</div>' if delta else ""

        st.markdown(f"""
        <div class="ds-card ds-metric" style="{_border}">
            <div class="ds-metric-label">{_icon}{label}</div>
            <div class="ds-metric-value" style="{_color}">{value}</div>
            {_delta}
        </div>
        """, unsafe_allow_html=True)

    # ── 告警徽章 ──────────────────────────────────────
    def alert_badge(
        self,
        level: Literal["P0", "P1", "P2", "total"],
        count: int,
    ) -> None:
        """渲染告警级别徽章。"""
        config = {
            "P0": {"bg": COLORS.p0_bg, "color": COLORS.p0, "label": "🔴 P0 紧急", "text_color": "#991B1B"},
            "P1": {"bg": COLORS.p1_bg, "color": COLORS.p1, "label": "🟡 P1 重要", "text_color": "#92400E"},
            "P2": {"bg": COLORS.p2_bg, "color": COLORS.p2, "label": "🔵 P2 关注", "text_color": "#1E40AF"},
            "total": {"bg": f"linear-gradient(135deg, {COLORS.bg_subtle} 0%, {COLORS.bg_page} 100%)", "color": "#64748B", "label": "📊 总计", "text_color": "#1E293B"},
        }
        c = config[level]
        st.markdown(f"""
        <div class="ds-alert-badge" style="background: {c['bg']}; border-color: {c['color']};">
            <div class="ds-alert-badge-value" style="color: {c['color']};">{count}</div>
            <div class="ds-alert-badge-label" style="color: {c['text_color']};">{c['label']}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── 面包屑导航 ──────────────────────────────────────
    def breadcrumb(self, items: list[tuple[str, str]]) -> None:
        """渲染面包屑导航。items = [(label, color), ...]"""
        parts = []
        for i, (label, color) in enumerate(items):
            bg = f"{color}15"  # 15% 透明度
            parts.append(f'<span class="ds-breadcrumb-item" style="color: {color}; background: {bg};">{label}</span>')
            if i < len(items) - 1:
                parts.append('<span class="ds-breadcrumb-sep">›</span>')
        st.markdown(f"""
        <div class="ds-card" style="padding: 0.75rem 1rem;">
            <div style="font-size: 0.7rem; color: {COLORS.text_muted}; margin-bottom: 0.375rem;">📍 下探路径</div>
            <div class="ds-breadcrumb">{"".join(parts)}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── 状态标签 ──────────────────────────────────────
    def status_chip(
        self,
        text: str,
        variant: Literal["success", "warning", "danger", "info"] = "info",
    ) -> str:
        """返回状态标签 HTML（inline）。"""
        color_map = {
            "success": (COLORS.success, COLORS.success_light),
            "warning": (COLORS.warning, COLORS.warning_light),
            "danger": (COLORS.danger, COLORS.danger_light),
            "info": (COLORS.primary, COLORS.primary_light),
        }
        fg, bg = color_map[variant]
        return f'<span class="ds-chip" style="color: {fg}; background: {bg};">{text}</span>'

    # ── Plotly 图表主题 ──────────────────────────────────────
    def chart_layout(self, height: int = 300, **overrides) -> dict:
        """返回统一的 Plotly 图表 layout 配置。"""
        base = {
            "height": height,
            "margin": dict(l=20, r=20, t=10, b=30),
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": dict(family="Inter, system-ui, sans-serif", size=12, color=COLORS.text_primary),
            "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
            "xaxis": dict(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0"),
            "yaxis": dict(gridcolor="#F1F5F9", zerolinecolor="#E2E8F0"),
            "colorway": COLORS.chart_palette,
            "hoverlabel": dict(bgcolor="white", font_size=12, font_color=COLORS.text_primary),
        }
        base.update(overrides)
        return base

    # ── 组别卡片颜色方案 ──────────────────────────────────────
    def group_card_style(self, accuracy_rate: float, is_selected: bool = False) -> dict:
        """根据正确率返回组别卡片的颜色方案。"""
        if accuracy_rate >= 99:
            bg = f"linear-gradient(135deg, {COLORS.success_light} 0%, #D1FAE5 100%)"
            border = COLORS.success
            icon = "✅"
            text = "达标"
            text_color = "#047857"
        elif accuracy_rate >= 98:
            bg = f"linear-gradient(135deg, {COLORS.warning_light} 0%, #FEF3C7 100%)"
            border = COLORS.warning
            icon = "⚠️"
            text = "观察中"
            text_color = "#92400E"
        else:
            bg = f"linear-gradient(135deg, {COLORS.danger_light} 0%, #FEE2E2 100%)"
            border = COLORS.danger
            icon = "❌"
            text = "需关注"
            text_color = "#991B1B"

        if is_selected:
            border = COLORS.primary
            shadow = f"0 8px 24px rgba(37, 99, 235, 0.2)"
        else:
            shadow = "0 2px 8px rgba(0,0,0,0.06)"

        return {
            "bg": bg,
            "border": f"{'3px' if is_selected else '2px'} solid {border}",
            "shadow": shadow,
            "icon": icon,
            "text": text,
            "text_color": text_color,
        }

    # ── SLA 状态卡片 ──────────────────────────────────────
    def sla_status(self, overdue_count: int, open_overdue: int = 0, claimed_overdue: int = 0) -> None:
        """渲染 SLA 状态卡片。"""
        if overdue_count > 0:
            st.markdown(f"""
            <div class="ds-card" style="border-left: 4px solid {COLORS.danger}; background: {COLORS.danger_light};">
                <div style="color: {COLORS.danger}; font-weight: 700; font-size: 1rem; margin-bottom: 0.25rem;">
                    ⚠️ SLA 超时 {overdue_count} 条
                </div>
                <div style="font-size: 0.72rem; color: #991B1B;">
                    待处理 {open_overdue} · 已认领 {claimed_overdue}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="ds-card" style="border-left: 4px solid {COLORS.success}; background: {COLORS.success_light}; text-align: center;">
                <div style="color: {COLORS.success}; font-weight: 700; font-size: 1rem;">✅ 无 SLA 超时</div>
                <div style="font-size: 0.72rem; color: #047857;">所有告警均在处理时限内</div>
            </div>
            """, unsafe_allow_html=True)

    # ── 页面底部说明 ──────────────────────────────────────
    def footer(self, notes: list[str]) -> None:
        """渲染页面底部说明区。"""
        lines = "<br>".join(notes)
        st.markdown(f"""
        <div class="ds-card" style="margin-top: 1.5rem; background: {COLORS.bg_subtle}; border: 1px solid {COLORS.border};">
            <div style="font-size: 0.82rem; color: {COLORS.text_secondary}; line-height: 1.8;">
                {lines}
            </div>
        </div>
        """, unsafe_allow_html=True)


# 单例
ds = DesignSystem()
