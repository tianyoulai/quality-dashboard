"""全局 CSS 样式管理。

所有页面通过 inject_global_css() 注入统一的基础样式，
避免各页面重复定义 max-width / padding / 表格美化等 CSS。
"""
from __future__ import annotations

from datetime import date

import streamlit as st


def inject_global_css() -> None:
    """注入全局基础 CSS，所有页面统一调用。"""
    st.markdown("""
    <style>
        /* ===== 全局布局 ===== */
        .main > div { padding-top: 1rem; }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 100% !important;
            width: 100% !important;
        }
        section[data-testid="stSidebar"] ~ div.main .block-container {
            max-width: 100% !important;
        }

        /* ===== 表格美化 ===== */
        .stDataFrame {
            border-radius: 0.75rem;
            overflow: hidden;
            border: 1px solid #E5E7EB;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        /* ===== 折叠面板 ===== */
        .streamlit-expanderHeader {
            background: #F8FAFC;
            border-radius: 0.5rem;
            border: 1px solid #E5E7EB;
        }

        /* ===== 按钮美化 ===== */
        .stButton > button {
            border-radius: 0.5rem;
            transition: all 0.2s ease;
            font-weight: 500;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
        }

        /* ===== 标题/分割线 ===== */
        h1 { margin-bottom: 0.5rem; }
        h3 { margin-top: 1.5rem; margin-bottom: 1rem; }
        hr { margin: 1.5rem 0; border-color: #E5E7EB; }

        /* ===== 移动端适配（企微内嵌/手机浏览） ===== */
        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
                padding-top: 0.5rem !important;
            }
            /* 侧边栏默认折叠 */
            section[data-testid="stSidebar"] {
                width: 0 !important;
                min-width: 0 !important;
            }
            /* 卡片紧凑化 */
            .metric-card, [data-testid="stMetricValue"] {
                font-size: 0.9rem !important;
            }
            /* 列布局自动堆叠 */
            [data-testid="column"] {
                min-width: 100% !important;
            }
            /* 表格横向滚动 */
            .stDataFrame {
                overflow-x: auto !important;
            }
            /* Hero 区域紧凑 */
            h1 { font-size: 1.5rem !important; }
            h3 { font-size: 1.1rem !important; margin-top: 0.75rem !important; }
            /* 按钮更大的点击区域 */
            .stButton > button {
                min-height: 2.5rem;
                font-size: 0.85rem;
            }
        }

        /* ===== 平板适配 ===== */
        @media (min-width: 769px) and (max-width: 1024px) {
            .block-container {
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    # 侧边栏品牌标识
    _render_sidebar_brand()


def _render_sidebar_brand() -> None:
    """在侧边栏底部渲染品牌信息和数据时间。"""
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"""
    <div style="text-align:center; padding: 0.5rem; opacity: 0.7;">
        <div style="font-size: 0.75rem; color: #6B7280;">
            📊 质培运营看板 v2.0<br>
            🕐 {date.today().strftime('%Y-%m-%d')}
        </div>
    </div>
    """, unsafe_allow_html=True)
