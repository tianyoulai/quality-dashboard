"""质培运营看板 — Streamlit 入口页（多页面导航）。"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="质培运营看板", page_icon="📊", layout="wide")

st.markdown("""
<div style="margin-bottom: 1.5rem; padding: 1.5rem; background: #ffffff;
            border-radius: 1rem; border-left: 4px solid #2e7d32;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #1a1a1a;">📊 质培运营看板</h1>
    </div>
    <div style="font-size: 0.9rem; color: #4b5563; line-height: 1.6;">
        数据概览 · 新人追踪 · 明细查询 · 告警监控
    </div>
</div>
""", unsafe_allow_html=True)

st.info(
    "👈 请从左侧边栏选择页面：**明细查询** 等功能模块。"
    "\n\n主要数据来自 TiDB 数据库（fact_qa_event / fact_newcomer_qa / mart_* 聚合表）。"
)
