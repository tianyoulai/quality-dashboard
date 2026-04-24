"""新人追踪 — 📈 成长曲线模块。

渲染入职天数视角的成长曲线、多批次速度对比、阶段达标时间。
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from views.newcomer._shared import get_stage_meta, render_plot, safe_pct


def render_growth(ctx: dict) -> None:
    """渲染成长曲线视图。"""
    combined_qa_df = ctx["combined_qa_df"]
    filtered_batch_df = ctx["filtered_batch_df"]

    st.markdown("#### 📈 批次成长曲线（入职天数视角）")

    if combined_qa_df.empty or filtered_batch_df.empty:
        st.info("暂无足够数据生成成长曲线。")
        return

    growth_df = combined_qa_df.merge(filtered_batch_df[["batch_name", "join_date"]], on="batch_name", how="left")
    growth_df["biz_date_dt"] = pd.to_datetime(growth_df["biz_date"], errors="coerce")
    growth_df["join_date_dt"] = pd.to_datetime(growth_df["join_date"], errors="coerce")
    growth_df = growth_df.dropna(subset=["biz_date_dt", "join_date_dt"])
    growth_df["day_no"] = (growth_df["biz_date_dt"] - growth_df["join_date_dt"]).dt.days + 1
    growth_df = growth_df[growth_df["day_no"] >= 1]

    # --- 主成长曲线（按阶段着色）---
    day_stage_df = growth_df.groupby(["batch_name", "day_no", "stage"], as_index=False).agg(
        qa_cnt=("qa_cnt", "sum"), correct_cnt=("correct_cnt", "sum"),
    )
    day_stage_df["accuracy"] = day_stage_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)

    fig_growth = go.Figure()
    for bn in sorted(day_stage_df["batch_name"].dropna().unique().tolist()):
        for stg in ["internal", "external", "formal"]:
            subset = day_stage_df[(day_stage_df["batch_name"] == bn) & (day_stage_df["stage"] == stg)]
            if subset.empty:
                continue
            stage_label, stage_color, _, _ = get_stage_meta(stg)
            fig_growth.add_trace(go.Scatter(
                x=subset["day_no"], y=subset["accuracy"],
                mode="lines+markers", name=f"{bn}-{stage_label}",
                line=dict(color=stage_color, width=2.5), marker=dict(size=6),
                hovertemplate="入职第 %{x} 天<br>正确率 %{y:.1f}%<extra></extra>",
            ))
    fig_growth.add_hline(y=98, line_dash="dash", line_color="#10b981", annotation_text="转正线 98%")
    fig_growth.update_layout(
        height=420, yaxis_title="正确率 (%)", xaxis_title="入职天数",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    render_plot(fig_growth, "growth_curve_main")

    # --- 多批次对比 + 阶段达标时间 ---
    col_g1, col_g2 = st.columns([1.2, 1])
    with col_g1:
        st.markdown("#### 📊 多批次成长速度对比")
        multi_growth = growth_df.groupby(["batch_name", "day_no"], as_index=False).agg(
            qa_cnt=("qa_cnt", "sum"), correct_cnt=("correct_cnt", "sum"),
        )
        multi_growth["accuracy"] = multi_growth.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
        fig_multi = px.line(
            multi_growth, x="day_no", y="accuracy", color="batch_name", markers=True,
            labels={"day_no": "入职天数", "accuracy": "正确率 (%)", "batch_name": "批次"},
        )
        fig_multi.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        render_plot(fig_multi, "growth_curve_compare")

    with col_g2:
        st.markdown("#### 🎯 阶段达标时间")
        milestone_rows = []
        for bn in sorted(growth_df["batch_name"].dropna().unique().tolist()):
            batch_stage_days = growth_df[growth_df["batch_name"] == bn].groupby("stage")["day_no"].max().to_dict()
            milestone_rows.append({
                "批次": bn,
                "内部天数": int(batch_stage_days.get("internal", 0) or 0),
                "外部天数": int(batch_stage_days.get("external", 0) or 0),
                "正式天数": int(batch_stage_days.get("formal", 0) or 0),
            })
        milestone_df = pd.DataFrame(milestone_rows)
        if not milestone_df.empty:
            milestone_long = milestone_df.melt(id_vars="批次", var_name="阶段", value_name="天数")
            fig_mile = px.bar(
                milestone_long, x="批次", y="天数", color="阶段", barmode="stack",
                color_discrete_map={"内部天数": "#8b5cf6", "外部天数": "#3b82f6", "正式天数": "#10b981"},
            )
            fig_mile.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_mile, "growth_milestone_chart")
