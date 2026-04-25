"""模块级查询函数 — 支持外检/内检/BadCase 独立页面。

所有查询直接走 fact_qa_event 按 qc_module 过滤聚合，不依赖 mart 表。
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from storage.repository import DashboardRepository

repo = DashboardRepository()

# ── 颜色常量 ──
COLOR_SUCCESS = "#10B981"
COLOR_WARN = "#F59E0B"

# ── 模块元数据 ──
QC_MODULE_META = {
    "external": {"label": "外检看板", "icon": "🔍", "color": "#10B981", "desc": "外部质检（供应商审核员被抽检）"},
    "internal": {"label": "内检看板", "icon": "🔬", "color": "#8B5CF6", "desc": "内部质检（内部团队质检员执行）"},
    "badcase":  {"label": "BadCase", "icon": "⚠️", "color": "#EF4444", "desc": "外部 BadCase 反馈（独立数据源）"},
}


# ═══════════════════════════════════════════════════════════════
#  缓存查询函数
# ═══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=900)
def load_module_summary(selected_date: date) -> pd.DataFrame:
    """按 qc_module 聚合当日指标。"""
    return repo.fetch_df("""
        SELECT qc_module,
               COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END) AS raw_correct_cnt,
               SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END) AS final_correct_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS raw_error_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_accuracy_rate,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_accuracy_rate
        FROM fact_qa_event WHERE biz_date = %s
        GROUP BY qc_module
    """, [selected_date])


@st.cache_data(show_spinner=False, ttl=900)
def load_module_group_detail(selected_date: date, qc_module: str) -> pd.DataFrame:
    """模块内按组别聚合。"""
    return repo.fetch_df("""
        SELECT group_name, COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END) AS raw_correct_cnt,
               SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END) AS final_correct_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS raw_error_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_accuracy_rate,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_accuracy_rate,
               ROUND(SUM(CASE WHEN is_misjudge=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS misjudge_rate,
               ROUND(SUM(CASE WHEN is_missjudge=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS missjudge_rate
        FROM fact_qa_event
        WHERE biz_date = %s AND qc_module = %s
        GROUP BY group_name ORDER BY qa_cnt DESC
    """, [selected_date, qc_module])


@st.cache_data(show_spinner=False, ttl=900)
def load_module_trend(start_date: date, end_date: date, qc_module: str) -> pd.DataFrame:
    """模块日趋势。"""
    return repo.fetch_df("""
        SELECT biz_date AS anchor_date, COUNT(*) AS total_qa_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_accuracy_rate,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_accuracy_rate
        FROM fact_qa_event
        WHERE biz_date BETWEEN %s AND %s AND qc_module = %s
        GROUP BY biz_date ORDER BY biz_date
    """, [start_date, end_date, qc_module])


@st.cache_data(show_spinner=False, ttl=900)
def load_module_queue_detail(selected_date: date, qc_module: str) -> pd.DataFrame:
    """模块内按队列聚合。"""
    return repo.fetch_df("""
        SELECT queue_name, COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS error_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_accuracy_rate,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_accuracy_rate,
               ROUND(SUM(CASE WHEN is_misjudge=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS misjudge_rate,
               ROUND(SUM(CASE WHEN is_missjudge=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS missjudge_rate
        FROM fact_qa_event
        WHERE biz_date = %s AND qc_module = %s AND queue_name IS NOT NULL AND queue_name != ''
        GROUP BY queue_name ORDER BY raw_accuracy_rate ASC
    """, [selected_date, qc_module])


@st.cache_data(show_spinner=False, ttl=900)
def load_module_qa_owner_detail(selected_date: date, qc_module: str) -> pd.DataFrame:
    """模块内质检员工作量。"""
    return repo.fetch_df("""
        SELECT qa_owner_name, COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS error_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS accuracy_rate
        FROM fact_qa_event
        WHERE biz_date = %s AND qc_module = %s AND qa_owner_name IS NOT NULL AND qa_owner_name != ''
        GROUP BY qa_owner_name ORDER BY qa_cnt DESC LIMIT 20
    """, [selected_date, qc_module])


@st.cache_data(show_spinner=False, ttl=900)
def load_module_reviewer_detail(selected_date: date, qc_module: str) -> pd.DataFrame:
    """模块内审核人（被检人）明细。"""
    return repo.fetch_df("""
        SELECT reviewer_name, COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS error_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_accuracy_rate,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_accuracy_rate,
               SUM(CASE WHEN is_misjudge=1 THEN 1 ELSE 0 END) AS misjudge_cnt,
               SUM(CASE WHEN is_missjudge=1 THEN 1 ELSE 0 END) AS missjudge_cnt
        FROM fact_qa_event
        WHERE biz_date = %s AND qc_module = %s AND reviewer_name IS NOT NULL AND reviewer_name != ''
        GROUP BY reviewer_name ORDER BY raw_accuracy_rate ASC LIMIT 30
    """, [selected_date, qc_module])


@st.cache_data(show_spinner=False, ttl=900)
def get_data_date_range() -> tuple[date, date]:
    """获取数据库日期范围（委托给 _data.py 统一实现）。"""
    from views.dashboard._data import get_data_date_range as _get_range
    return _get_range()


# ═══════════════════════════════════════════════════════════════
#  渲染组件
# ═══════════════════════════════════════════════════════════════

def render_module_page(module_key: str):
    """渲染一个模块的完整页面（供各独立页面调用）。"""
    meta = QC_MODULE_META[module_key]

    # CSS 已由 app.py 的 layout="wide" 全局设置，此处不再重复注入

    # Hero
    st.markdown(f"""
    <div style="margin-bottom:1.5rem;padding:1.5rem;background:#fff;border-radius:1rem;border-left:4px solid {meta['color']};box-shadow:0 1px 3px rgba(0,0,0,0.1);">
        <h1 style="margin:0;font-size:2rem;font-weight:700;color:#1a1a1a;">{meta['icon']} {meta['label']}</h1>
        <div style="font-size:0.9rem;color:#4b5563;margin-top:0.5rem;">{meta['desc']}</div>
    </div>
    """, unsafe_allow_html=True)

    # 日期选择
    _min_d, _max_d = get_data_date_range()
    _default = _max_d if _max_d <= date.today() else date.today()

    col_d1, col_d2, col_d3 = st.columns([1, 1, 3])
    with col_d1:
        selected_date = st.date_input("业务日期", value=_default)
    with col_d2:
        date_start = st.date_input("趋势起始", value=selected_date - timedelta(days=6), key=f"{module_key}_start")
    with col_d3:
        st.markdown("")  # 占位

    st.markdown("---")

    # ── 指标卡 ──
    summary = load_module_summary(selected_date)
    row = summary[summary["qc_module"] == module_key]
    if row.empty:
        st.warning(f"当前日期（{selected_date}）暂无{meta['label']}数据。")
        st.stop()

    r = row.iloc[0]
    qa_cnt = int(r["qa_cnt"])
    raw_acc = float(r["raw_accuracy_rate"])
    final_acc = float(r["final_accuracy_rate"])
    error_cnt = int(r["raw_error_cnt"])

    c1, c2, c3, c4 = st.columns(4)
    _card = lambda label, value, color: f"""
        <div style="background:#fff;padding:1rem;border-radius:0.75rem;border:1px solid #e5e7eb;border-left:4px solid {color};">
            <div style="font-size:0.8rem;color:#6b7280;font-weight:500;">{label}</div>
            <div style="font-size:1.75rem;font-weight:700;color:{color};">{value}</div>
        </div>"""
    with c1:
        st.markdown(_card("📊 质检总量", f"{qa_cnt:,}", meta["color"]), unsafe_allow_html=True)
    with c2:
        st.markdown(_card("✓ 原始正确率", f"{raw_acc:.2f}%", "#10B981" if raw_acc >= 99 else "#EF4444"), unsafe_allow_html=True)
    with c3:
        st.markdown(_card("✓✓ 最终正确率", f"{final_acc:.2f}%", "#10B981" if final_acc >= 99 else "#EF4444"), unsafe_allow_html=True)
    with c4:
        st.markdown(_card("✗ 错误量", f"{error_cnt:,}", "#EF4444"), unsafe_allow_html=True)

    st.markdown("---")

    # ── 组别明细 + 趋势 ──
    col_group, col_trend = st.columns([1, 1.2])

    with col_group:
        st.markdown("#### 🏢 组别明细")
        gdf = load_module_group_detail(selected_date, module_key)
        if not gdf.empty:
            show = pd.DataFrame({
                "组别": gdf["group_name"],
                "质检量": pd.to_numeric(gdf["qa_cnt"], errors="coerce").fillna(0).astype(int),
                "错误量": pd.to_numeric(gdf["raw_error_cnt"], errors="coerce").fillna(0).astype(int),
                "原始正确率": pd.to_numeric(gdf["raw_accuracy_rate"], errors="coerce").fillna(0).astype(float),
                "最终正确率": pd.to_numeric(gdf["final_accuracy_rate"], errors="coerce").fillna(0).astype(float),
            })
            st.dataframe(show, use_container_width=True, hide_index=True, height=300,
                         column_config={
                             "质检量": st.column_config.NumberColumn(format="%d"),
                             "错误量": st.column_config.NumberColumn(format="%d"),
                             "原始正确率": st.column_config.NumberColumn(format="%.2f%%"),
                             "最终正确率": st.column_config.NumberColumn(format="%.2f%%"),
                         })
        else:
            st.info("暂无数据")

    with col_trend:
        st.markdown("#### 📈 正确率趋势")
        trend = load_module_trend(date_start, selected_date, module_key)
        if not trend.empty:
            trend["anchor_date"] = pd.to_datetime(trend["anchor_date"])
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=trend["anchor_date"], y=trend["final_accuracy_rate"],
                                     mode="lines+markers", name="最终正确率",
                                     line=dict(color=meta["color"], width=3), marker=dict(size=7)))
            fig.add_trace(go.Scatter(x=trend["anchor_date"], y=trend["raw_accuracy_rate"],
                                     mode="lines+markers", name="原始正确率",
                                     line=dict(color="#94A3B8", width=2, dash="dot"), marker=dict(size=5)))
            fig.add_hline(y=99.0, line_dash="dash", line_color=COLOR_WARN, annotation_text="目标 99%")
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=10, b=30),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                              yaxis_range=[min(95, trend["raw_accuracy_rate"].min() - 1), 100.5],
                              yaxis_title="正确率 (%)",
                              xaxis=dict(tickformat="%m-%d", tickangle=-45),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True, key=f"trend_{module_key}")
        else:
            st.info("暂无趋势数据")

    st.markdown("---")

    # ── 队列排名 + 审核人 ──
    col_queue, col_reviewer = st.columns([1.2, 1])

    with col_queue:
        st.markdown("#### 🏆 队列正确率排名")
        qdf = load_module_queue_detail(selected_date, module_key)
        if not qdf.empty:
            st.caption(f"共 {len(qdf)} 个队列，按原始正确率升序（问题队列优先）")
            show = pd.DataFrame({
                "队列": qdf["queue_name"],
                "质检量": pd.to_numeric(qdf["qa_cnt"], errors="coerce").fillna(0).astype(int),
                "错误量": pd.to_numeric(qdf["error_cnt"], errors="coerce").fillna(0).astype(int),
                "原始正确率": pd.to_numeric(qdf["raw_accuracy_rate"], errors="coerce").fillna(0).astype(float),
                "最终正确率": pd.to_numeric(qdf["final_accuracy_rate"], errors="coerce").fillna(0).astype(float),
            })
            st.dataframe(show, use_container_width=True, hide_index=True, height=350,
                         column_config={
                             "队列": st.column_config.TextColumn(width="medium"),
                             "质检量": st.column_config.NumberColumn(format="%d"),
                             "错误量": st.column_config.NumberColumn(format="%d"),
                             "原始正确率": st.column_config.NumberColumn(format="%.2f%%"),
                             "最终正确率": st.column_config.NumberColumn(format="%.2f%%"),
                         })
        else:
            st.info("暂无队列数据")

    with col_reviewer:
        st.markdown("#### 👥 审核人视图")
        rdf = load_module_reviewer_detail(selected_date, module_key)
        if not rdf.empty:
            st.caption(f"共 {len(rdf)} 位审核人，按正确率升序")
            show = pd.DataFrame({
                "审核人": rdf["reviewer_name"],
                "质检量": pd.to_numeric(rdf["qa_cnt"], errors="coerce").fillna(0).astype(int),
                "原始正确率": pd.to_numeric(rdf["raw_accuracy_rate"], errors="coerce").fillna(0).astype(float),
                "最终正确率": pd.to_numeric(rdf["final_accuracy_rate"], errors="coerce").fillna(0).astype(float),
                "错判量": pd.to_numeric(rdf["misjudge_cnt"], errors="coerce").fillna(0).astype(int),
                "漏判量": pd.to_numeric(rdf["missjudge_cnt"], errors="coerce").fillna(0).astype(int),
            })
            st.dataframe(show, use_container_width=True, hide_index=True, height=350,
                         column_config={
                             "审核人": st.column_config.TextColumn(width="medium"),
                             "质检量": st.column_config.NumberColumn(format="%d"),
                             "原始正确率": st.column_config.NumberColumn(format="%.2f%%"),
                             "最终正确率": st.column_config.NumberColumn(format="%.2f%%"),
                             "错判量": st.column_config.NumberColumn(format="%d"),
                             "漏判量": st.column_config.NumberColumn(format="%d"),
                         })
        else:
            st.info("暂无审核人数据")

    st.markdown("---")

    # ── 质检员工作量 ──
    st.markdown("#### 👨‍💼 质检员工作量")
    odf = load_module_qa_owner_detail(selected_date, module_key)
    if not odf.empty:
        show = pd.DataFrame({
            "质检员": odf["qa_owner_name"].apply(lambda x: x.split("-")[-1] if "-" in str(x) else x),
            "质检量": pd.to_numeric(odf["qa_cnt"], errors="coerce").fillna(0).astype(int),
            "错误量": pd.to_numeric(odf["error_cnt"], errors="coerce").fillna(0).astype(int),
            "正确率": pd.to_numeric(odf["accuracy_rate"], errors="coerce").fillna(0).astype(float),
        })
        st.dataframe(show, use_container_width=True, hide_index=True,
                     column_config={
                         "质检量": st.column_config.NumberColumn(format="%d"),
                         "错误量": st.column_config.NumberColumn(format="%d"),
                         "正确率": st.column_config.NumberColumn(format="%.2f%%"),
                     })
    else:
        st.info("暂无质检员数据")
