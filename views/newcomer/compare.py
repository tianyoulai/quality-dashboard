"""新人追踪 — 🔄 阶段对比模块。

渲染个人阶段跃迁、双口径对比、阶段转化明细表。
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from views.newcomer._shared import render_plot, safe_pct


def render_compare(ctx: dict) -> None:
    """渲染阶段对比视图。"""
    person_stage_df = ctx["person_stage_df"]

    st.markdown("#### 🔄 个人阶段跃迁与结构对比")

    if person_stage_df.empty:
        st.info("暂无质检数据。")
        return

    stage_avg = person_stage_df.groupby("stage", as_index=False).agg(
        qa_cnt=("qa_cnt", "sum"),
        correct_cnt=("correct_cnt", "sum"),
        per_capita_accuracy=("sample_accuracy", "mean"),
    )
    stage_avg["sample_accuracy"] = stage_avg.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
    stage_avg["accuracy"] = stage_avg["sample_accuracy"]

    # --- 阶段指标卡 ---
    p1, p2, p3, p4 = st.columns(4)
    for col_widget, stage_code, label in [
        (p1, "internal", "🏫 内部样本正确率"),
        (p2, "external", "🔍 外部样本正确率"),
        (p3, "formal", "✅ 正式样本正确率"),
    ]:
        with col_widget:
            sv = stage_avg.loc[stage_avg["stage"] == stage_code, "sample_accuracy"].max() if stage_code in stage_avg["stage"].values else 0
            pv = stage_avg.loc[stage_avg["stage"] == stage_code, "per_capita_accuracy"].max() if stage_code in stage_avg["stage"].values else 0
            st.metric(label, f"{sv:.1f}%", delta=f"人均 {pv:.1f}%")
    with p4:
        weak_cnt = int(person_stage_df[
            (person_stage_df["stage"] == "external") & (person_stage_df["sample_accuracy"] < 95)
        ]["short_name"].nunique())
        st.metric("⚠️ 外部待关注", weak_cnt)

    # --- 个人阶段柱图 + 阶段均值 ---
    compare_col1, compare_col2 = st.columns([1.15, 1])
    with compare_col1:
        fig_person = px.bar(
            person_stage_df.sort_values(["batch_name", "short_name", "stage"]),
            x="short_name", y="accuracy", color="stage", barmode="group", facet_row="batch_name",
            labels={"short_name": "姓名", "accuracy": "正确率 (%)", "stage": "阶段"},
            color_discrete_map={"internal": "#8b5cf6", "external": "#3b82f6", "formal": "#10b981"},
        )
        fig_person.update_layout(
            height=max(360, 280 * max(person_stage_df["batch_name"].nunique(), 1)),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        render_plot(fig_person, "compare_person_stage_bar")
    with compare_col2:
        stage_avg["阶段"] = stage_avg["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检", "formal": "✅ 正式上线"})
        stage_avg_long = stage_avg.melt(
            id_vars=["阶段"], value_vars=["sample_accuracy", "per_capita_accuracy"],
            var_name="口径", value_name="正确率",
        )
        stage_avg_long["口径"] = stage_avg_long["口径"].map({"sample_accuracy": "样本正确率", "per_capita_accuracy": "人均正确率"})
        fig_stage_avg = px.bar(
            stage_avg_long, x="阶段", y="正确率", color="口径", barmode="group", text="正确率",
            color_discrete_map={"样本正确率": "#10b981", "人均正确率": "#2563eb"},
        )
        fig_stage_avg.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_stage_avg.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        render_plot(fig_stage_avg, "compare_stage_average_bar")

    # --- 阶段转化明细表 ---
    pivot_acc = person_stage_df.pivot_table(
        index=["batch_name", "short_name", "team_name"], columns="stage", values="accuracy", aggfunc="first",
    ).reset_index()
    pivot_qa = person_stage_df.pivot_table(
        index=["batch_name", "short_name", "team_name"], columns="stage", values="qa_cnt", aggfunc="first",
    ).reset_index()
    compare_table = pivot_acc.merge(pivot_qa, on=["batch_name", "short_name", "team_name"], how="left", suffixes=("", "_qa"))
    compare_table = compare_table.rename(columns={
        "batch_name": "批次", "short_name": "姓名", "team_name": "基地/团队",
        "internal": "🏫 内检正确率", "external": "🔍 外检正确率", "formal": "✅ 正式正确率",
        "internal_qa": "内检量", "external_qa": "外检量", "formal_qa": "正式量",
    })
    if "🏫 内检正确率" in compare_table.columns and "🔍 外检正确率" in compare_table.columns:
        compare_table["外检跃迁"] = (compare_table["🔍 外检正确率"] - compare_table["🏫 内检正确率"]).round(2)
    if "✅ 正式正确率" in compare_table.columns and "🔍 外检正确率" in compare_table.columns:
        compare_table["转正跃迁"] = (compare_table["✅ 正式正确率"] - compare_table["🔍 外检正确率"]).round(2)

    def _current_status(row):
        if pd.notna(row.get("✅ 正式正确率")):
            return "✅ 已正式上线"
        if pd.notna(row.get("🔍 外检正确率")) and row.get("🔍 外检正确率", 0) >= 98:
            return "🟢 接近转正"
        if pd.notna(row.get("🔍 外检正确率")) and row.get("🔍 外检正确率", 0) < 95:
            return "🔴 需关注"
        if pd.notna(row.get("🔍 外检正确率")):
            return "🔍 外部阶段"
        return "🏫 内部阶段"

    compare_table["当前状态"] = compare_table.apply(_current_status, axis=1)
    st.caption("这里仍然只展示单人样本正确率；人均正确率只用于批次、团队、owner 等聚合层。")
    st.markdown("#### 📋 阶段转化明细")
    st.dataframe(compare_table, use_container_width=True, hide_index=True, height=420)
