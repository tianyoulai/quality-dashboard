"""新人追踪 — 📊 维度分析模块。

渲染批次×基地热力图、专题/风险/内容类型维度、管理链路、错误类型、稳定性象限。
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from views.newcomer._shared import (
    display_text,
    ensure_default_columns,
    format_heatmap_text,
    normalize_numeric_columns,
    render_plot,
    safe_pct,
)


def render_dimension(ctx: dict) -> None:
    """渲染维度分析视图。"""
    combined_qa_df = ctx["combined_qa_df"]
    team_accuracy_df = ctx["team_accuracy_df"]
    stage_team_accuracy_df = ctx["stage_team_accuracy_df"]
    batch_gap_df = ctx["batch_gap_df"]
    batch_compare_df = ctx["batch_compare_df"]
    team_issue_df = ctx["team_issue_df"]
    management_perf_df = ctx["management_perf_df"]
    error_summary_df = ctx["error_summary_df"]
    newcomer_dimension_df = ctx["newcomer_dimension_df"]
    formal_dimension_df = ctx["formal_dimension_df"]
    dimension_status_df = ctx["dimension_status_df"]
    newcomer_dimension_ready = ctx["newcomer_dimension_ready"]

    st.markdown("#### 📊 维度分析")

    if combined_qa_df.empty:
        st.info("暂无质检数据，暂时无法生成维度分析。")
        return

    st.info("对照 local demo，这一页已经补齐批次/基地差异、管理链路、错误类型、问题率。下面这张表会直接告诉你哪些维度当前已经可做，哪些还卡在数据层。")
    st.markdown("##### 🔧 对照 demo 的维度可用性")
    st.dataframe(dimension_status_df, use_container_width=True, hide_index=True)

    # --- 热力图 + 批次差异榜 ---
    row1_col1, row1_col2 = st.columns([1.15, 1])
    with row1_col1:
        _render_team_heatmap(team_accuracy_df, stage_team_accuracy_df, batch_gap_df)
    with row1_col2:
        _render_batch_rank(batch_compare_df, batch_gap_df)

    # --- 专题/风险/内容类型 ---
    st.markdown("##### 🧠 专题 / 风险 / 内容类型")
    _render_newcomer_dimensions(newcomer_dimension_df, newcomer_dimension_ready)
    _render_formal_dimensions(formal_dimension_df)

    # --- 管理链路 ---
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        _render_mentor_view(management_perf_df)
    with row2_col2:
        _render_owner_view(management_perf_df)

    # --- 错判/漏判 + 错误类型 ---
    row3_col1, row3_col2 = st.columns(2)
    with row3_col1:
        _render_issue_rate(team_issue_df)
    with row3_col2:
        _render_error_top(error_summary_df)

    # --- 稳定性象限 + 关注基地榜 ---
    row4_col1, row4_col2 = st.columns([1.15, 1])
    with row4_col1:
        _render_stability_scatter(team_issue_df)
    with row4_col2:
        _render_watch_team(team_issue_df)

    # --- 管理链路明细表 ---
    st.markdown("#### 🔍 管理链路明细")
    if not management_perf_df.empty:
        mgmt_table = management_perf_df.rename(columns={
            "team_leader": "联营管理", "delivery_pm": "交付PM", "owner": "质培owner",
            "mentor_name": "导师/质检", "member_cnt": "人数", "qa_cnt": "质检量",
            "sample_accuracy": "样本正确率", "per_capita_accuracy": "人均正确率",
            "accuracy_gap": "口径差值", "misjudge_rate": "错判率", "missjudge_rate": "漏判率",
        })[["联营管理", "交付PM", "质培owner", "导师/质检", "人数", "质检量", "样本正确率", "人均正确率", "口径差值", "错判率", "漏判率"]]
        st.dataframe(mgmt_table.sort_values(["样本正确率", "质检量"], ascending=[False, False]),
                     use_container_width=True, hide_index=True, height=360)


# ═══════════════════════════════════════════════════════════════
#  内部渲染函数
# ═══════════════════════════════════════════════════════════════

def _render_team_heatmap(team_accuracy_df, stage_team_accuracy_df, batch_gap_df):
    st.markdown("##### 🏢 批次 × 基地差异热力图")
    heatmap_options = {"整体": "all", "内部质检": "internal", "外部质检": "external", "正式上线": "formal"}
    heatmap_label = st.selectbox("热力图口径", options=list(heatmap_options.keys()), key="nc_dim_heatmap_stage")
    heatmap_code = heatmap_options[heatmap_label]
    source = team_accuracy_df.copy() if heatmap_code == "all" else stage_team_accuracy_df[stage_team_accuracy_df["stage"] == heatmap_code].copy()

    if not source.empty:
        matrix = source.pivot(index="team_name", columns="batch_name", values="sample_accuracy").sort_index()
        text_df = format_heatmap_text(matrix)
        fig = go.Figure(data=go.Heatmap(
            z=matrix.fillna(0).values, x=matrix.columns.tolist(), y=matrix.index.tolist(),
            text=text_df.values, texttemplate="%{text}",
            colorscale=[[0.0, "#fee2e2"], [0.45, "#fef3c7"], [0.7, "#dbeafe"], [1.0, "#10b981"]],
            zmin=90, zmax=100,
            hovertemplate="批次：%{x}<br>基地/团队：%{y}<br>样本正确率：%{z:.2f}%<extra></extra>",
        ))
        fig.update_layout(
            height=max(320, 90 + 52 * len(matrix.index)),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        render_plot(fig, "dimension_team_heatmap")
    else:
        st.info("当前口径下暂无基地差异数据。")

    if not batch_gap_df.empty:
        gap_preview = batch_gap_df.rename(columns={
            "batch_name": "批次", "best_team_name": "最好基地", "best_team_acc": "最高正确率",
            "worst_team_name": "待关注基地", "worst_team_acc": "最低正确率", "gap_pct": "批次内差值",
        })[["批次", "最好基地", "最高正确率", "待关注基地", "最低正确率", "批次内差值"]]
        st.dataframe(gap_preview.sort_values("批次内差值", ascending=False), use_container_width=True, hide_index=True, height=220)


def _render_batch_rank(batch_compare_df, batch_gap_df):
    st.markdown("##### 🥊 批次差异榜")
    if batch_compare_df.empty:
        return
    rank_df = batch_compare_df.merge(batch_gap_df[["batch_name", "sample_gap_pct", "per_capita_gap_pct"]], on="batch_name", how="left") if not batch_gap_df.empty else batch_compare_df.copy()
    rank_df = ensure_default_columns(rank_df, {"sample_gap_pct": 0.0, "per_capita_gap_pct": 0.0})
    fig = px.bar(
        rank_df.sort_values(["sample_accuracy", "sample_gap_pct"], ascending=[False, False]),
        x="batch_name", y="sample_accuracy", color="sample_gap_pct", text="sample_accuracy",
        labels={"batch_name": "批次", "sample_accuracy": "样本正确率 (%)", "sample_gap_pct": "样本口径基地差值"},
        color_continuous_scale="Bluered",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(height=320, coloraxis_colorbar_title="样本差值", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    render_plot(fig, "dimension_batch_rank")

    table = rank_df.rename(columns={
        "batch_name": "批次", "member_cnt": "人数", "qa_cnt": "质检量",
        "sample_accuracy": "样本正确率", "per_capita_accuracy": "人均正确率", "accuracy_gap": "口径差值",
        "misjudge_rate": "错判率", "missjudge_rate": "漏判率",
        "sample_gap_pct": "样本口径基地差值", "per_capita_gap_pct": "人均口径基地差值", "training_days": "培训天数",
    })[["批次", "人数", "质检量", "样本正确率", "人均正确率", "口径差值", "样本口径基地差值", "人均口径基地差值", "错判率", "漏判率", "培训天数"]]
    st.dataframe(table.sort_values(["样本正确率", "样本口径基地差值"], ascending=[False, False]),
                 use_container_width=True, hide_index=True, height=260)


def _render_newcomer_dimensions(newcomer_dimension_df, newcomer_dimension_ready):
    if not newcomer_dimension_df.empty:
        df = normalize_numeric_columns(newcomer_dimension_df, ["qa_cnt", "correct_cnt"])
        df["accuracy"] = df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
        df["stage_label"] = df["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检"}).fillna("新人质检")

        st.markdown("###### 👶 新人内 / 外检专题维度")
        c1, c2, c3 = st.columns(3)
        with c1:
            topic = df.groupby(["training_topic", "stage_label"], as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False).head(12)
            topic["正确率"] = topic.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
            fig = px.bar(topic.sort_values(["stage_label", "正确率"], ascending=[True, True]),
                         x="正确率", y="training_topic", color="stage_label", orientation="h", text="正确率",
                         labels={"training_topic": "培训专题", "正确率": "正确率 (%)", "stage_label": "阶段"},
                         color_discrete_map={"🏫 内部质检": "#8b5cf6", "🔍 外部质检": "#3b82f6"})
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig, "dimension_newcomer_topic_bar")
        with c2:
            risk = df.groupby(["risk_level", "stage_label"], as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False)
            risk["正确率"] = risk.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
            fig = px.bar(risk, x="risk_level", y="质检量", color="stage_label", barmode="group", text="正确率",
                         labels={"risk_level": "风险等级", "质检量": "质检量", "stage_label": "阶段"},
                         color_discrete_map={"🏫 内部质检": "#8b5cf6", "🔍 外部质检": "#3b82f6"})
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig, "dimension_newcomer_risk_bar")
        with c3:
            content = df.groupby("content_type", as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False).head(8)
            content["正确率"] = content.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
            fig = px.bar(content.sort_values("质检量", ascending=True), x="质检量", y="content_type", orientation="h", text="正确率",
                         labels={"content_type": "内容类型", "质检量": "质检量"}, color="正确率", color_continuous_scale="RdYlGn")
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(height=340, coloraxis_colorbar_title="正确率", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig, "dimension_newcomer_content_bar")

        topic_view = df.groupby(["batch_name", "team_name", "stage_label", "training_topic"], as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False)
        topic_view["正确率"] = topic_view.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
        topic_view = topic_view.rename(columns={"batch_name": "批次", "team_name": "基地/团队", "stage_label": "阶段", "training_topic": "培训专题"})
        st.dataframe(topic_view[["批次", "基地/团队", "阶段", "培训专题", "质检量", "正确率"]].head(20), use_container_width=True, hide_index=True, height=220)
    elif newcomer_dimension_ready:
        st.caption("新人内/外检字段已经补齐，但当前筛选范围内还没有带专题/风险/内容类型的新导入数据；继续导新文件或回填历史数据后，这块会直接亮起来。")
    else:
        st.caption("当前新人内/外检还没有可用的专题/风险/内容类型字段，暂时先由正式阶段补位展示。")


def _render_formal_dimensions(formal_dimension_df):
    st.markdown("###### ✅ 正式阶段专题维度")
    if formal_dimension_df.empty:
        st.caption("当前筛选范围下，正式阶段还没有可用的专题/风险/内容类型明细，或底层表未补这些字段。")
        return

    df = normalize_numeric_columns(formal_dimension_df, ["qa_cnt", "correct_cnt"])
    df["accuracy"] = df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)

    c1, c2, c3 = st.columns(3)
    with c1:
        topic = df.groupby("training_topic", as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False).head(8)
        topic["正确率"] = topic.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
        fig = px.bar(topic.sort_values("正确率", ascending=True), x="正确率", y="training_topic", orientation="h", text="正确率",
                     labels={"training_topic": "培训专题", "正确率": "正确率 (%)"}, color="质检量", color_continuous_scale="Blues")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=340, coloraxis_colorbar_title="质检量", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        render_plot(fig, "dimension_formal_topic_bar")
    with c2:
        risk = df.groupby("risk_level", as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False)
        risk["正确率"] = risk.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
        fig = px.pie(risk, values="质检量", names="risk_level", hole=0.55, color="risk_level")
        fig.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        render_plot(fig, "dimension_formal_risk_pie")
    with c3:
        content = df.groupby("content_type", as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False).head(8)
        content["正确率"] = content.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
        fig = px.bar(content.sort_values("质检量", ascending=True), x="质检量", y="content_type", orientation="h", text="正确率",
                     labels={"content_type": "内容类型", "质检量": "质检量"}, color="正确率", color_continuous_scale="RdYlGn")
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=340, coloraxis_colorbar_title="正确率", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        render_plot(fig, "dimension_formal_content_bar")

    topic_view = df.groupby(["batch_name", "team_name", "training_topic"], as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False)
    topic_view["正确率"] = topic_view.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
    topic_view = topic_view.rename(columns={"batch_name": "批次", "team_name": "基地/团队", "training_topic": "培训专题"})
    st.dataframe(topic_view[["批次", "基地/团队", "培训专题", "质检量", "正确率"]].head(20), use_container_width=True, hide_index=True, height=220)


def _render_mentor_view(management_perf_df):
    st.markdown("##### 👨‍🏫 导师/质检视角")
    if management_perf_df.empty:
        return
    df = management_perf_df.groupby("mentor_name", as_index=False).agg(
        member_cnt=("member_cnt", "sum"), qa_cnt=("qa_cnt", "sum"), correct_cnt=("correct_cnt", "sum"),
        misjudge_cnt=("misjudge_cnt", "sum"), missjudge_cnt=("missjudge_cnt", "sum"),
    )
    df["sample_accuracy"] = df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
    df["issue_rate"] = df.apply(lambda r: safe_pct(r["misjudge_cnt"] + r["missjudge_cnt"], r["qa_cnt"]), axis=1)
    fig = px.bar(df.sort_values("sample_accuracy", ascending=False), x="mentor_name", y="sample_accuracy",
                 color="issue_rate", text="sample_accuracy",
                 labels={"mentor_name": "导师/质检", "sample_accuracy": "样本正确率 (%)", "issue_rate": "问题率 (%)"},
                 color_continuous_scale="Blues")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(height=360, coloraxis_colorbar_title="问题率", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    render_plot(fig, "dimension_mentor_bar")


def _render_owner_view(management_perf_df):
    st.markdown("##### 📊 质培owner / 交付PM 总览")
    if management_perf_df.empty:
        return
    df = management_perf_df.groupby(["owner", "delivery_pm"], as_index=False).agg(
        member_cnt=("member_cnt", "sum"), qa_cnt=("qa_cnt", "sum"), correct_cnt=("correct_cnt", "sum"),
        misjudge_cnt=("misjudge_cnt", "sum"), missjudge_cnt=("missjudge_cnt", "sum"),
    )
    df["sample_accuracy"] = df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
    df["issue_rate"] = df.apply(lambda r: safe_pct(r["misjudge_cnt"] + r["missjudge_cnt"], r["qa_cnt"]), axis=1)
    df["owner_label"] = df["owner"] + " · " + df["delivery_pm"]
    fig = px.bar(df.sort_values("sample_accuracy", ascending=False), x="owner_label", y="sample_accuracy",
                 color="issue_rate", text="sample_accuracy",
                 labels={"owner_label": "质培owner / 交付PM", "sample_accuracy": "样本正确率 (%)", "issue_rate": "问题率 (%)"},
                 color_continuous_scale="Greens")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(height=360, coloraxis_colorbar_title="问题率", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    render_plot(fig, "dimension_owner_bar")


def _render_issue_rate(team_issue_df):
    st.markdown("##### ⚠️ 基地错判 / 漏判率")
    if team_issue_df.empty:
        return
    df = team_issue_df.copy()
    df["label"] = df["batch_name"] + " · " + df["team_name"]
    df = df.sort_values(["misjudge_rate", "missjudge_rate"], ascending=[False, False]).head(10)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["misjudge_rate"], y=df["label"], orientation="h", name="错判率",
                         marker_color="#f97316", text=[f"{v:.1f}%" for v in df["misjudge_rate"]], textposition="outside"))
    fig.add_trace(go.Bar(x=df["missjudge_rate"], y=df["label"], orientation="h", name="漏判率",
                         marker_color="#ef4444", text=[f"{v:.1f}%" for v in df["missjudge_rate"]], textposition="outside"))
    fig.update_layout(barmode="group", height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    render_plot(fig, "dimension_issue_rate_bar")


def _render_error_top(error_summary_df):
    st.markdown("##### 🏷️ 错误类型 Top")
    if error_summary_df is None or error_summary_df.empty:
        st.info("当前筛选范围内暂无错误类型明细。")
        return
    top = error_summary_df.groupby("error_type", as_index=False)["error_cnt"].sum().sort_values("error_cnt", ascending=False).head(10)
    fig = px.bar(top.sort_values("error_cnt"), x="error_cnt", y="error_type", orientation="h", text="error_cnt",
                 labels={"error_cnt": "错误次数", "error_type": "错误类型"}, color="error_cnt", color_continuous_scale="Reds")
    fig.update_layout(height=360, coloraxis_showscale=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    render_plot(fig, "dimension_error_top_bar")


def _render_stability_scatter(team_issue_df):
    st.markdown("##### 🎯 基地稳定性象限")
    if team_issue_df.empty:
        st.info("当前暂无可用于象限分析的基地数据。")
        return
    df = team_issue_df.copy()
    df["label"] = df["batch_name"] + " · " + df["team_name"]
    fig = px.scatter(df, x="issue_rate", y="accuracy", size="qa_cnt", color="batch_name", text="team_name", hover_name="label",
                     labels={"issue_rate": "总问题率 (%)", "accuracy": "样本正确率 (%)", "qa_cnt": "质检量", "batch_name": "批次"})
    fig.add_vline(x=2.5, line_dash="dash", line_color="#f59e0b")
    fig.add_hline(y=97, line_dash="dash", line_color="#10b981")
    fig.update_traces(textposition="top center", marker=dict(line=dict(width=1, color="#ffffff")))
    fig.update_layout(height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    render_plot(fig, "dimension_team_stability_scatter")


def _render_watch_team(team_issue_df):
    st.markdown("##### 🧾 待关注基地榜")
    if team_issue_df.empty:
        st.info("当前没有需要额外关注的基地数据。")
        return
    df = team_issue_df.copy()
    df["关注分"] = (100 - df["accuracy"]) + (df["issue_rate"] * 2)
    view = df.rename(columns={
        "batch_name": "批次", "team_name": "基地/团队", "member_cnt": "人数", "qa_cnt": "质检量",
        "sample_accuracy": "样本正确率", "per_capita_accuracy": "人均正确率", "accuracy_gap": "口径差值",
        "misjudge_rate": "错判率", "missjudge_rate": "漏判率", "issue_rate": "总问题率", "关注分": "关注分",
    })[["批次", "基地/团队", "人数", "质检量", "样本正确率", "人均正确率", "口径差值", "错判率", "漏判率", "总问题率", "关注分"]]
    st.dataframe(view.sort_values(["关注分", "样本正确率"], ascending=[False, True]).head(12),
                 use_container_width=True, hide_index=True, height=380)
