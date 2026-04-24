"""质培运营看板 — Streamlit 入口页（多页面导航）。"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="质培运营看板",
    page_icon="📊",
    layout="wide",
)

st.title("📊 质培运营看板")
st.info(
    "请从左侧边栏选择功能页面：\n"
    "【明细查询】多维度筛选、问题下钻、数据导出"
)
