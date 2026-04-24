"""质培运营看板 — Streamlit 入口页。"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="质培运营看板",
    page_icon="📊",
    layout="wide",
)

# 自动跳转到总览页面（注意：跳转前不要注入任何 HTML/CSS，否则会导致前端 DOM removeChild 错误）
try:
    st.switch_page("pages/01_总览.py")
except Exception:
    # Streamlit 版本不支持 switch_page 时的回退方案
    st.title("📊 质培运营看板")
    st.info(
        "请从左侧边栏选择功能页面：\n\n"
        "- 📈 **总览** — 核心运营看板，实时监控与智能告警\n"
        "- 📥 **数据管理** — 数据导入与维护\n"
        "- 🔍 **内检** — 审核一致性分析\n"
        "- 📋 **明细查询** — 多维度筛选与数据导出\n"
        "- 👶 **新人追踪** — 新人培养全流程追踪"
    )
