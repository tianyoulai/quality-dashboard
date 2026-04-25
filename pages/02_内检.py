"""数据总览页：跨周期趋势对比 + 全量组别排名。

简化版：专注于核心指标展示，移除复杂的筛选逻辑。
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from storage.repository import DashboardRepository

# 设计系统 v3.0
from utils.design_system import ds, COLORS
ds.inject_theme()

repo = DashboardRepository()

from utils.helpers import to_csv_bytes


def _build_group_ranking(df: pd.DataFrame, date_col: str, grain_label: str) -> None:
    """通用的组别排名渲染函数，消除日/周/月三个维度的重复代码。"""
    if df.empty:
        st.warning(f"暂无{grain_label}数据。")
        return

    group_agg = df.groupby("group_name").agg(
        qa_cnt=("qa_cnt", "sum"),
    ).reset_index()
    # 加权平均正确率
    for grp in group_agg["group_name"]:
        grp_data = df[df["group_name"] == grp]
        total_qa = grp_data["qa_cnt"].sum()
        group_agg.loc[group_agg["group_name"] == grp, "raw_accuracy_rate"] = (
            (grp_data["raw_accuracy_rate"] * grp_data["qa_cnt"]).sum() / total_qa
        )
        group_agg.loc[group_agg["group_name"] == grp, "final_accuracy_rate"] = (
            (grp_data["final_accuracy_rate"] * grp_data["qa_cnt"]).sum() / total_qa
        )
    group_agg["raw_error_cnt"] = (group_agg["qa_cnt"] * (100 - group_agg["raw_accuracy_rate"]) / 100).round(0).astype(int)
    group_agg["final_error_cnt"] = (group_agg["qa_cnt"] * (100 - group_agg["final_accuracy_rate"]) / 100).round(0).astype(int)
    group_agg = group_agg.sort_values("final_accuracy_rate", ascending=False)

    total_all_qa = group_agg["qa_cnt"].sum()
    group_show = pd.DataFrame({
        "组别": group_agg["group_name"],
        "总质检量": group_agg["qa_cnt"].apply(lambda x: f"{int(x):,}"),
        "抽检占比": group_agg["qa_cnt"].apply(lambda x: f"{x / total_all_qa * 100:.1f}%" if total_all_qa > 0 else "—"),
        "原始正确率": group_agg["raw_accuracy_rate"].apply(lambda x: f"{x:.2f}%"),
        "最终正确率": group_agg["final_accuracy_rate"].apply(lambda x: f"{x:.2f}%"),
        "原始错误量": group_agg["raw_error_cnt"].apply(lambda x: f"{x:,}"),
        "最终错误量": group_agg["final_error_cnt"].apply(lambda x: f"{x:,}"),
    })

    st.dataframe(group_show, use_container_width=True, hide_index=True, column_config={
        "组别": st.column_config.TextColumn("组别", width="medium"),
    })

    # CSV 导出
    csv_data = to_csv_bytes(group_show)
    st.download_button(f"📥 导出{grain_label}组别排名", csv_data, file_name=f"group_ranking_{grain_label}.csv", mime="text/csv", key=f"dl_grp_{grain_label}")


def _build_group_trend(df: pd.DataFrame, date_col: str, grain_label: str, key_suffix: str) -> str | None:
    """通用的组别趋势渲染函数，返回选中的组别名。"""
    groups = sorted(df["group_name"].unique().tolist())
    sel_group = st.selectbox("选择组别", options=groups, key=f"{key_suffix}_group")

    if sel_group:
        trend = df[df["group_name"] == sel_group].sort_values(date_col)
        if not trend.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trend[date_col], y=trend["final_accuracy_rate"],
                mode="lines+markers", name="最终正确率",
                line=dict(color=COLORS.success, width=3), marker=dict(size=8),
                text=[f"{v:.2f}%" for v in trend["final_accuracy_rate"]],
                hovertemplate="<b>%{x}</b><br>最终正确率: %{text}<extra></extra>"
            ))
            fig.add_trace(go.Scatter(
                x=trend[date_col], y=trend["raw_accuracy_rate"],
                mode="lines+markers", name="原始正确率",
                line=dict(color=COLORS.text_muted, width=2, dash="dot"), marker=dict(size=6),
                text=[f"{v:.2f}%" for v in trend["raw_accuracy_rate"]],
                hovertemplate="<b>%{x}</b><br>原始正确率: %{text}<extra></extra>"
            ))
            fig.add_hline(y=99.0, line_dash="dash", line_color=COLORS.warning, annotation_text="目标 99%", annotation_position="right")
            # 增加区间均值参考线
            if len(trend) > 1:
                avg_final = trend["final_accuracy_rate"].mean()
                fig.add_hline(y=avg_final, line_dash="dot", line_color=COLORS.chart_palette[4],
                              annotation_text=f"均值 {avg_final:.2f}%",
                              annotation_position="bottom right")
            _layout = ds.chart_layout(height=400)
            _layout["yaxis"] = {**_layout.get("yaxis", {}), "range": [95, 100.5], "title": "正确率 (%)"}
            _layout["xaxis"] = {**_layout.get("xaxis", {}), "tickformat": "%Y-%m-%d", "tickangle": -45}
            fig.update_layout(**_layout)
            st.plotly_chart(fig, use_container_width=True)

            # 最新数据指标 + 环比变化
            row_latest = trend.iloc[-1]
            m1, m2, m3 = st.columns(3)
            if len(trend) >= 2:
                prev = trend.iloc[-2]
                delta_raw = row_latest['raw_accuracy_rate'] - prev['raw_accuracy_rate']
                delta_final = row_latest['final_accuracy_rate'] - prev['final_accuracy_rate']
                delta_qa = int(row_latest['qa_cnt'] - prev['qa_cnt'])
                m1.metric("原始正确率", f"{row_latest['raw_accuracy_rate']:.2f}%", delta=f"{delta_raw:+.2f}%")
                m2.metric("最终正确率", f"{row_latest['final_accuracy_rate']:.2f}%", delta=f"{delta_final:+.2f}%")
                m3.metric("质检量", f"{int(row_latest['qa_cnt']):,}", delta=f"{delta_qa:+,}")
            else:
                m1.metric("原始正确率", f"{row_latest['raw_accuracy_rate']:.2f}%")
                m2.metric("最终正确率", f"{row_latest['final_accuracy_rate']:.2f}%")
                m3.metric("质检量", f"{int(row_latest['qa_cnt']):,}")
    return sel_group


@st.cache_data(show_spinner="正在加载日期范围...", ttl=600)
def get_date_range() -> tuple[date, date]:
    row = repo.fetch_one("SELECT MIN(biz_date) AS min_d, MAX(biz_date) AS max_d FROM fact_qa_event")
    if not row or row.get("min_d") is None:
        return date.today(), date.today()
    min_val = row["min_d"]
    max_val = row["max_d"]
    if hasattr(min_val, "date"):
        min_val = min_val.date()
    if hasattr(max_val, "date"):
        max_val = max_val.date()
    return min_val, max_val

@st.cache_data(show_spinner="正在加载日维度数据...", ttl=600)
def load_all_group_daily() -> pd.DataFrame:
    return repo.fetch_df("SELECT * FROM mart_day_group ORDER BY biz_date, group_name")

@st.cache_data(show_spinner="正在加载周维度数据...", ttl=600)
def load_all_group_weekly() -> pd.DataFrame:
    return repo.fetch_df("SELECT * FROM mart_week_group ORDER BY week_begin_date, group_name")

@st.cache_data(show_spinner="正在加载月维度数据...", ttl=600)
def load_all_group_monthly() -> pd.DataFrame:
    return repo.fetch_df("SELECT * FROM mart_month_group ORDER BY month_begin_date, group_name")


min_d, max_d = get_date_range()

# Hero 区域（设计系统 v3.0）
ds.hero("🔍", "内检分析", "跨周期趋势对比 · 全量组别排名 · 审核一致性分析")

# 检查数据范围
if min_d is None or max_d is None:
    st.warning("数据库中没有质检数据，请先导入数据。")
    st.stop()

# 数据范围提示
st.markdown(f"""
<div class="ds-card" style="padding: 0.75rem 1rem; border-left: 4px solid {COLORS.text_secondary}; margin-bottom: 1rem;">
    <span style='font-weight: 600; color: {COLORS.text_primary};'>📅 数据日期范围：</span>
    <span style='color: {COLORS.text_primary};'>{min_d} ~ {max_d}</span>
</div>
""", unsafe_allow_html=True)

tab_grain = st.tabs(["日维度", "周维度", "月维度"])

# 侧边栏筛选
st.sidebar.markdown("### 🎯 内检筛选")
inspect_type_options = {"全部": None, "内检": "internal", "外检": "external"}
inspect_type_label = st.sidebar.selectbox("质检类型", options=list(inspect_type_options.keys()), key="inspect_type_filter")
inspect_type_value = inspect_type_options[inspect_type_label]

# ==================== 日维度 ====================
with tab_grain[0]:
    df_daily = load_all_group_daily()
    
    if df_daily.empty:
        st.warning("暂无日维度数据。请运行 `python jobs/refresh_warehouse.py` 刷新数仓。")
    else:
        # 按质检类型过滤
        if inspect_type_value and "inspect_type" in df_daily.columns:
            df_daily = df_daily[df_daily["inspect_type"] == inspect_type_value]
        
        # 日期筛选（优化样式）——默认最近7天，避免查询全量数据导致加载过慢
        st.markdown("#### 📅 日期筛选")
        col1, col2 = st.columns(2)
        default_day_start = max(min_d, max_d - timedelta(days=6))
        with col1:
            date_start = st.date_input("起始日期", value=default_day_start, key="day_start")
        with col2:
            date_end = st.date_input("截止日期", value=max_d, key="day_end")
        
        st.caption(f"💡 默认展示最近7天数据。完整数据范围：{min_d} ~ {max_d}")
        
        # 转换日期格式并过滤空值
        df_daily["biz_date"] = pd.to_datetime(df_daily["biz_date"]).dt.date
        filtered = df_daily[
            df_daily["biz_date"].notna() & 
            (df_daily["biz_date"] >= date_start) & 
            (df_daily["biz_date"] <= date_end)
        ]
        
        if filtered.empty:
            st.warning("所选日期范围内没有数据。")
        else:
            # 全量组别排名（通用函数）
            ds.section("🏆 全量组别排名")
            _build_group_ranking(filtered, "biz_date", "日维度")
            
            # 组别趋势（通用函数）
            ds.section("📊 组别趋势图")
            sel_group = _build_group_trend(filtered, "biz_date", "日维度", "day")
        # ---- 审核人排名（日维度汇总） ----
        with st.expander("👤 审核人正确率排名", expanded=False):
            auditor_sql = """
                SELECT reviewer_name,
                       COUNT(*) AS qa_cnt,
                       SUM(CASE WHEN raw_judgement='正确' THEN 1 ELSE 0 END) AS raw_correct,
                       SUM(CASE WHEN final_judgement='正确' THEN 1 ELSE 0 END) AS final_correct
                FROM vw_qa_base
                WHERE biz_date BETWEEN %s AND %s
                GROUP BY reviewer_name
                HAVING qa_cnt >= 5
                ORDER BY raw_correct/qa_cnt ASC
            """
            auditor_df = repo.fetch_df(auditor_sql, (date_start, date_end))
            if not auditor_df.empty:
                auditor_df["raw_accuracy"] = auditor_df["raw_correct"] / auditor_df["qa_cnt"] * 100
                auditor_df["final_accuracy"] = auditor_df["final_correct"] / auditor_df["qa_cnt"] * 100
                auditor_df["error_cnt"] = auditor_df["qa_cnt"] - auditor_df["raw_correct"]

                a_show = pd.DataFrame()
                a_show["审核人"] = auditor_df["reviewer_name"].apply(lambda x: x.split("-")[-1] if "-" in str(x) else x)
                a_show["质检量"] = auditor_df["qa_cnt"].apply(lambda x: f"{int(x):,}")
                a_show["出错量"] = auditor_df["error_cnt"].apply(lambda x: f"{int(x):,}")
                a_show["原始正确率"] = auditor_df["raw_accuracy"].apply(lambda x: f"{x:.2f}%")
                a_show["最终正确率"] = auditor_df["final_accuracy"].apply(lambda x: f"{x:.2f}%")

                st.caption(f"共 {len(auditor_df)} 位审核人（≥5条质检记录），按原始正确率升序排列")
                st.dataframe(a_show, use_container_width=True, hide_index=True, height=400)
            else:
                st.info("所选日期范围内无审核人数据")

        # ---- 错误类型 TOP5 分布 ----
        with st.expander("🏷️ 错误类型 TOP5 分布", expanded=False):
            error_type_sql = """
                SELECT COALESCE(error_type, '未标注') AS error_type,
                       COUNT(*) AS cnt
                FROM vw_qa_base
                WHERE biz_date BETWEEN %s AND %s
                  AND raw_judgement != '正确'
                GROUP BY error_type
                ORDER BY cnt DESC
                LIMIT 10
            """
            error_type_df = repo.fetch_df(error_type_sql, (date_start, date_end))
            if not error_type_df.empty:
                import plotly.express as px
                fig_et = px.bar(
                    error_type_df.head(5),
                    x="cnt", y="error_type", orientation="h",
                    text="cnt", color="cnt",
                    color_continuous_scale="Reds",
                )
                fig_et.update_traces(textposition="outside", textfont_size=12)
                _layout_et = ds.chart_layout(height=280)
                _layout_et["yaxis"] = {**_layout_et.get("yaxis", {}), "autorange": "reversed"}
                _layout_et.update({"showlegend": False, "coloraxis_showscale": False})
                _layout_et["xaxis"] = {**_layout_et.get("xaxis", {}), "title": "错误数量"}
                _layout_et["yaxis"]["title"] = ""
                fig_et.update_layout(**_layout_et)
                st.plotly_chart(fig_et, use_container_width=True)

                total_errors = error_type_df["cnt"].sum()
                top5_pct = error_type_df.head(5)["cnt"].sum() / total_errors * 100 if total_errors > 0 else 0
                st.caption(f"共 {total_errors:,} 个错误，TOP5 占比 {top5_pct:.1f}%")
            else:
                st.success("🎉 所选日期范围内无错误记录")


# ==================== 周维度 ====================
with tab_grain[1]:
    df_weekly = load_all_group_weekly()
    
    if df_weekly.empty:
        st.warning("暂无周维度数据。")
    else:
        # 按质检类型过滤
        if inspect_type_value and "inspect_type" in df_weekly.columns:
            df_weekly = df_weekly[df_weekly["inspect_type"] == inspect_type_value]
        
        # 全量组别周度排名（通用函数）
        ds.section("🏆 全量组别周度排名")
        _build_group_ranking(df_weekly, "week_begin_date", "周维度")
        
        # 组别趋势（通用函数）
        ds.section("📊 组别周趋势")
        _build_group_trend(df_weekly, "week_begin_date", "周维度", "week")


# ==================== 月维度 ====================
with tab_grain[2]:
    df_monthly = load_all_group_monthly()
    
    if df_monthly.empty:
        st.warning("暂无月维度数据。")
    else:
        # 按质检类型过滤
        if inspect_type_value and "inspect_type" in df_monthly.columns:
            df_monthly = df_monthly[df_monthly["inspect_type"] == inspect_type_value]
        
        # 全量组别月度排名（通用函数）
        ds.section("🏆 全量组别月度排名")
        _build_group_ranking(df_monthly, "month_begin_date", "月维度")
        
        # 组别趋势（通用函数）
        ds.section("📊 组别月趋势")
        _build_group_trend(df_monthly, "month_begin_date", "月维度", "month")