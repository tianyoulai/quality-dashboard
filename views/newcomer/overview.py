"""新人追踪 — 📊 批次概览模块。

渲染批次卡片、阶段双口径图表、基地差异热力图等。
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from views.newcomer._shared import (
    display_text,
    format_heatmap_text,
    get_stage_meta,
    render_plot,
)
from utils.design_system import COLORS


def render_overview(ctx: dict) -> None:
    """渲染批次概览视图。"""
    filtered_batch_df = ctx["filtered_batch_df"]
    batch_df = ctx["batch_df"]
    overall_stage_df = ctx["overall_stage_df"]
    batch_gap_df = ctx["batch_gap_df"]
    batch_watch_df = ctx["batch_watch_df"]
    batch_compare_df = ctx["batch_compare_df"]
    stage_summary_df = ctx["stage_summary_df"]
    team_accuracy_df = ctx["team_accuracy_df"]
    team_summary_df = ctx["team_summary_df"]

    overview_batch_df = filtered_batch_df if not filtered_batch_df.empty else batch_df.iloc[0:0]
    overview_total_people = int(overview_batch_df["total_cnt"].sum()) if not overview_batch_df.empty else 0
    avg_training_days = 0
    if not overview_batch_df.empty and overview_batch_df["join_date"].notna().any():
        avg_training_days = round(
            pd.Series([(date.today() - d).days for d in overview_batch_df["join_date"] if pd.notna(d)]).mean(), 1
        )

    # --- 阶段口径指标 ---
    def _stage_acc(stage: str, col: str) -> float:
        if overall_stage_df.empty or stage not in overall_stage_df["stage"].values:
            return 0.0
        return float(overall_stage_df.loc[overall_stage_df["stage"] == stage, col].max())

    internal_sample_acc = _stage_acc("internal", "sample_accuracy")
    internal_per_capita_acc = _stage_acc("internal", "per_capita_accuracy")
    external_sample_acc = _stage_acc("external", "sample_accuracy")
    external_per_capita_acc = _stage_acc("external", "per_capita_accuracy")
    formal_sample_acc = _stage_acc("formal", "sample_accuracy")
    formal_per_capita_acc = _stage_acc("formal", "per_capita_accuracy")

    max_gap_value = float(batch_gap_df["sample_gap_pct"].max()) if not batch_gap_df.empty and "sample_gap_pct" in batch_gap_df.columns else 0
    max_per_capita_gap = float(batch_gap_df["per_capita_gap_pct"].max()) if not batch_gap_df.empty and "per_capita_gap_pct" in batch_gap_df.columns else 0

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric("👥 当前新人数", overview_total_people)
    with mc2:
        st.metric("🏫 内部样本正确率", f"{internal_sample_acc:.1f}%", delta=f"人均 {internal_per_capita_acc:.1f}%")
    with mc3:
        st.metric("🔍 外部样本正确率", f"{external_sample_acc:.1f}%", delta=f"人均 {external_per_capita_acc:.1f}%")

    mc4, mc5, mc6 = st.columns(3)
    with mc4:
        st.metric("✅ 正式样本正确率", f"{formal_sample_acc:.1f}%", delta=f"人均 {formal_per_capita_acc:.1f}%")
    with mc5:
        st.metric("📅 平均培训天数", f"{avg_training_days}天")
    with mc6:
        st.metric("📏 最大基地样本差值", f"{max_gap_value:.1f}%", delta=f"人均差值 {max_per_capita_gap:.1f}%")

    st.markdown("""
    <div style="margin:-0.25rem 0 1rem; padding:0.85rem 1rem; border-radius:0.75rem; background:#eff6ff; border-left:4px solid #2563eb; font-size:0.82rem; color:#1d4ed8; line-height:1.7;">
        <strong>口径说明</strong>：聚合层统一同时看"样本正确率 + 人均正确率"。样本口径更适合看整体质量，人均口径更适合看队伍稳定性和带教公平性；个人追踪页仍只看单人样本正确率。
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    if overview_batch_df.empty:
        st.info("当前筛选条件下暂无新人成员。")
        return

    st.markdown("#### 🏷️ 批次一览")
    active_batches = []
    pending_batches = []
    for _, batch_row in overview_batch_df.iterrows():
        bn = batch_row["batch_name"]
        row_check = batch_compare_df[batch_compare_df["batch_name"] == bn].iloc[0] if not batch_compare_df.empty and bn in batch_compare_df["batch_name"].values else None
        total_qa_check = float(row_check["qa_cnt"]) if row_check is not None else 0
        if total_qa_check > 0:
            active_batches.append(batch_row)
        else:
            pending_batches.append(batch_row)

    if not active_batches:
        st.info("当前所有批次暂无质检数据。")

    for batch_row in active_batches:
        _render_batch_card(batch_row, stage_summary_df, batch_compare_df, batch_watch_df)

    if pending_batches:
        with st.expander(f"📭 待开始批次（{len(pending_batches)} 个，暂无质检数据）", expanded=False):
            for batch_row in pending_batches:
                bn = batch_row["batch_name"]
                join_d = batch_row["join_date"]
                cnt = int(batch_row["total_cnt"])
                leader = display_text(batch_row.get("leader_names"))
                owner_names = display_text(batch_row.get("owners"))
                st.markdown(f"""
                <div style="padding: 0.75rem 1rem; border-radius: 0.5rem; background: #F9FAFB; border: 1px dashed #D1D5DB; margin-bottom: 0.5rem;">
                    <span style="font-weight: 600; color: #6B7280;">📋 {bn}</span>
                    <span style="font-size: 0.8rem; color: #9CA3AF; margin-left: 1rem;">
                        人数 {cnt} · 入职 {join_d if pd.notna(join_d) else '—'} · 管理 {leader} · owner {owner_names}
                    </span>
                </div>
                """, unsafe_allow_html=True)

    # --- 阶段双口径图表 ---
    if not stage_summary_df.empty:
        col_a, col_b = st.columns([1.2, 1])
        with col_a:
            st.markdown("#### 📊 批次阶段双口径")
            stage_chart = stage_summary_df.copy()
            stage_chart["阶段"] = stage_chart["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检", "formal": "✅ 正式上线"})
            stage_chart = stage_chart.melt(
                id_vars=["batch_name", "阶段"],
                value_vars=["sample_accuracy", "per_capita_accuracy"],
                var_name="口径", value_name="正确率",
            )
            stage_chart["口径"] = stage_chart["口径"].map({"sample_accuracy": "样本正确率", "per_capita_accuracy": "人均正确率"})
            fig_stage = px.bar(
                stage_chart, x="batch_name", y="正确率", color="阶段", pattern_shape="口径",
                barmode="group", text="正确率",
                labels={"batch_name": "批次", "正确率": "正确率 (%)"},
                color_discrete_map={"🏫 内部质检": COLORS.stage_internal, "🔍 外部质检": COLORS.stage_external, "✅ 正式上线": COLORS.stage_formal},
                pattern_shape_map={"样本正确率": "", "人均正确率": "/"},
            )
            fig_stage.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_stage.update_layout(height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_stage, "overview_stage_accuracy_bar")
        with col_b:
            st.markdown("#### 🧭 阶段结构分布")
            stage_volume = stage_summary_df.groupby("stage", as_index=False)["qa_cnt"].sum()
            stage_volume["阶段"] = stage_volume["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检", "formal": "✅ 正式上线"})
            fig_volume = px.pie(
                stage_volume, values="qa_cnt", names="阶段", hole=0.55, color="阶段",
                color_discrete_map={"🏫 内部质检": COLORS.stage_internal, "🔍 外部质检": COLORS.stage_external, "✅ 正式上线": COLORS.stage_formal},
            )
            fig_volume.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_volume, "overview_stage_volume_pie")

    # --- 基地双口径 ---
    if not team_accuracy_df.empty:
        st.markdown("#### 📍 同批次不同基地双口径")
        col_team_chart, col_team_table = st.columns([1.15, 1])
        with col_team_chart:
            fig_team = px.bar(
                team_accuracy_df.sort_values(["batch_name", "sample_accuracy"], ascending=[True, False]),
                x="batch_name", y="sample_accuracy", color="team_name", barmode="group", text="sample_accuracy",
                labels={"batch_name": "批次", "sample_accuracy": "样本正确率 (%)", "team_name": "基地/团队"},
            )
            fig_team.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_team.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_team, "overview_team_accuracy_bar")
            st.caption("柱图默认看基地样本正确率；右侧表格同时补充人均正确率和口径差值，避免被高量审核人抹平差异。")
        with col_team_table:
            if not team_summary_df.empty:
                base_table = team_summary_df.rename(columns={
                    "batch_name": "批次", "team_name": "基地/团队", "team_leader": "联营管理",
                    "delivery_pm": "交付PM", "owner": "质培owner", "qa_cnt": "质检量",
                    "sample_accuracy": "样本正确率", "per_capita_accuracy": "人均正确率",
                    "accuracy_gap": "口径差值", "misjudge_rate": "错判率",
                    "missjudge_rate": "漏判率", "issue_rate": "总问题率",
                })
                base_table = base_table.sort_values(["批次", "样本正确率", "总问题率"], ascending=[True, False, True])
                st.dataframe(base_table, use_container_width=True, hide_index=True, height=360)

    # --- 基地差异聚焦 ---
    if not batch_gap_df.empty and not team_accuracy_df.empty:
        st.markdown("#### 🔭 基地差异聚焦")
        max_gap_row = batch_gap_df.sort_values("gap_pct", ascending=False).iloc[0]
        best_team_row = team_accuracy_df.sort_values(["accuracy", "qa_cnt"], ascending=[False, False]).iloc[0]
        weak_team_row = team_accuracy_df.sort_values(["accuracy", "qa_cnt"], ascending=[True, False]).iloc[0]

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            st.metric("批次内最大基地差值", f"{max_gap_row['gap_pct']:.1f}%",
                       delta=f"{max_gap_row['batch_name']} · {display_text(max_gap_row['best_team_name'])} vs {display_text(max_gap_row['worst_team_name'])}")
        with fc2:
            st.metric("当前表现最好基地", f"{best_team_row['accuracy']:.1f}%",
                       delta=f"{best_team_row['batch_name']} · {display_text(best_team_row['team_name'])}")
        with fc3:
            st.metric("当前待关注基地", f"{weak_team_row['accuracy']:.1f}%",
                       delta=f"{weak_team_row['batch_name']} · {display_text(weak_team_row['team_name'])}", delta_color="inverse")

        diff_col1, diff_col2 = st.columns([1.2, 1])
        with diff_col1:
            heatmap_df = team_accuracy_df.pivot(index="team_name", columns="batch_name", values="accuracy").sort_index()
            if not heatmap_df.empty:
                heatmap_values = heatmap_df.fillna(0)
                heatmap_text = format_heatmap_text(heatmap_df)
                fig_heatmap = go.Figure(data=go.Heatmap(
                    z=heatmap_values.values, x=heatmap_values.columns.tolist(), y=heatmap_values.index.tolist(),
                    text=heatmap_text.values, texttemplate="%{text}",
                    colorscale=[[0.0, "#fee2e2"], [0.45, "#fef3c7"], [0.7, "#dbeafe"], [1.0, "#10b981"]],
                    zmin=90, zmax=100,
                    hovertemplate="批次：%{x}<br>基地/团队：%{y}<br>正确率：%{z:.2f}%<extra></extra>",
                ))
                fig_heatmap.update_layout(
                    height=max(300, 90 + 52 * len(heatmap_values.index)),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=20, b=10),
                )
                render_plot(fig_heatmap, "overview_team_accuracy_heatmap")
        with diff_col2:
            gap_chart_df = batch_gap_df.sort_values(["gap_pct", "worst_team_acc"], ascending=[False, True]).copy()
            fig_gap = go.Figure()
            fig_gap.add_trace(go.Bar(
                x=gap_chart_df["batch_name"], y=gap_chart_df["gap_pct"], name="基地差值",
                marker_color=COLORS.warning, text=[f"{v:.1f}%" for v in gap_chart_df["gap_pct"]], textposition="outside",
            ))
            fig_gap.add_trace(go.Scatter(
                x=gap_chart_df["batch_name"], y=gap_chart_df["worst_team_acc"], name="最低基地正确率",
                mode="lines+markers", line=dict(color=COLORS.danger, width=2.5), marker=dict(size=8), yaxis="y2",
            ))
            fig_gap.update_layout(
                height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title="基地差值 (%)"),
                yaxis2=dict(title="最低基地正确率", overlaying="y", side="right", range=[90, 100]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(l=10, r=10, t=10, b=10),
            )
            render_plot(fig_gap, "overview_batch_gap_combo")

        gap_table = batch_gap_df.rename(columns={
            "batch_name": "批次", "team_cnt": "基地数", "best_team_name": "最好基地",
            "best_team_acc": "最高正确率", "worst_team_name": "待关注基地",
            "worst_team_acc": "最低正确率", "gap_pct": "批次内差值",
        })[["批次", "基地数", "最好基地", "最高正确率", "待关注基地", "最低正确率", "批次内差值"]]
        st.dataframe(gap_table.sort_values(["批次内差值", "最低正确率"], ascending=[False, True]),
                     use_container_width=True, hide_index=True, height=260)


# ═══════════════════════════════════════════════════════════════
#  内部：批次卡片渲染
# ═══════════════════════════════════════════════════════════════

def _render_batch_card(
    batch_row: pd.Series,
    stage_summary_df: pd.DataFrame,
    batch_compare_df: pd.DataFrame,
    batch_watch_df: pd.DataFrame,
) -> None:
    """渲染单个批次的详细卡片。"""
    bn = batch_row["batch_name"]
    join_d = batch_row["join_date"]
    days_since = (date.today() - join_d).days if pd.notna(join_d) and join_d else 0
    cnt = int(batch_row["total_cnt"])
    grad = int(batch_row["graduated_cnt"])
    leader = display_text(batch_row.get("leader_names"))
    delivery_pm = display_text(batch_row.get("delivery_pms"))
    mentor = display_text(batch_row.get("mentor_names"))
    owner_names = display_text(batch_row.get("owners"))
    teams_str = display_text(batch_row.get("teams"), default="-")

    batch_stage = stage_summary_df[stage_summary_df["batch_name"] == bn] if not stage_summary_df.empty else pd.DataFrame()
    compare_row = batch_compare_df[batch_compare_df["batch_name"] == bn].iloc[0] if not batch_compare_df.empty and bn in batch_compare_df["batch_name"].values else None
    batch_sample_acc = float(compare_row["sample_accuracy"]) if compare_row is not None else 0.0
    batch_per_capita_acc = float(compare_row["per_capita_accuracy"]) if compare_row is not None else 0.0
    batch_accuracy_gap = float(compare_row["accuracy_gap"]) if compare_row is not None else 0.0
    total_qa = float(compare_row["qa_cnt"]) if compare_row is not None else 0
    available_stages = batch_stage["stage"].tolist() if not batch_stage.empty else []

    if "formal" in available_stages:
        current_stage = "formal"
    elif "external" in available_stages:
        current_stage = "external"
    elif "internal" in available_stages:
        current_stage = "internal"
    else:
        current_stage = "pending"
    stage_label, stage_color, stage_bg, progress_width = get_stage_meta(current_stage)

    watch_row = batch_watch_df[batch_watch_df["batch_name"] == bn].iloc[0] if not batch_watch_df.empty and bn in batch_watch_df["batch_name"].values else None
    risk_label = watch_row["risk_label"] if watch_row is not None else "🟢 稳定批次"
    risk_color = watch_row["risk_color"] if watch_row is not None else COLORS.success
    risk_bg = watch_row["risk_bg"] if watch_row is not None else COLORS.success_light
    gap_pct = float(watch_row["gap_pct"]) if watch_row is not None else 0.0
    best_team_name = display_text(watch_row["best_team_name"], default="—") if watch_row is not None else "—"
    worst_team_name = display_text(watch_row["worst_team_name"], default="—") if watch_row is not None else "—"
    best_team_acc = float(watch_row["best_team_acc"]) if watch_row is not None else 0.0
    worst_team_acc = float(watch_row["worst_team_acc"]) if watch_row is not None else 0.0
    focus_people = watch_row["focus_people"] if watch_row is not None else "暂无"
    p0_cnt = int(watch_row["p0_cnt"]) if watch_row is not None else 0
    p1_cnt = int(watch_row["p1_cnt"]) if watch_row is not None else 0
    risk_note = f"近7天优先辅导：{focus_people}" if focus_people != "暂无" else "近7天暂无明显风险新人"
    best_per_capita = float(watch_row['best_team_per_capita_acc']) if watch_row is not None and 'best_team_per_capita_acc' in watch_row else 0
    per_capita_gap = float(watch_row['per_capita_gap_pct']) if watch_row is not None and 'per_capita_gap_pct' in watch_row else 0

    st.markdown(f"""
    <div style="padding: 1.25rem; border-radius: 1rem; background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%); border: 1px solid #E5E7EB; margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(15,23,42,0.06);">
        <div style="display:flex; justify-content:space-between; gap:1rem; align-items:flex-start; margin-bottom:0.9rem; flex-wrap:wrap;">
            <div>
                <div style="font-weight:700; font-size:1.15rem; color:#1E293B;">📋 {bn}</div>
                <div style="font-size:0.82rem; color:#64748B; margin-top:0.35rem; line-height:1.6;">
                    入职 {days_since} 天 · 联营管理：{leader} · 交付PM：{delivery_pm} · 质培owner：{owner_names}<br>
                    导师/质检：{mentor} · 基地/团队：{teams_str}
                </div>
            </div>
            <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap;">
                <div style="padding:0.28rem 0.8rem; border-radius:999px; background:{risk_bg}; color:{risk_color}; font-size:0.8rem; font-weight:700; border:1px solid {risk_color};">{risk_label}</div>
                <div style="padding:0.28rem 0.8rem; border-radius:999px; background:{stage_bg}; color:{stage_color}; font-size:0.8rem; font-weight:700; border:1px solid {stage_color};">{stage_label}</div>
            </div>
        </div>
        <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:0.75rem;">
            <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                <div style="font-size:0.72rem; color:#64748B;">人数</div>
                <div style="font-size:1.25rem; font-weight:700; color:#0F172A;">{cnt}</div>
            </div>
            <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                <div style="font-size:0.72rem; color:#64748B;">样本正确率</div>
                <div style="font-size:1.15rem; font-weight:700; color:#10b981;">{batch_sample_acc:.1f}%</div>
            </div>
            <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                <div style="font-size:0.72rem; color:#64748B;">人均正确率</div>
                <div style="font-size:1.15rem; font-weight:700; color:#2563eb;">{batch_per_capita_acc:.1f}%</div>
            </div>
            <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                <div style="font-size:0.72rem; color:#64748B;">口径差值</div>
                <div style="font-size:1.15rem; font-weight:700; color:#dc2626;">{batch_accuracy_gap:.1f}%</div>
            </div>
            <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                <div style="font-size:0.72rem; color:#64748B;">质检量</div>
                <div style="font-size:1.15rem; font-weight:700; color:#0F172A;">{int(total_qa):,}</div>
            </div>
            <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                <div style="font-size:0.72rem; color:#64748B;">已转正</div>
                <div style="font-size:1.15rem; font-weight:700; color:#10b981;">{grad}</div>
            </div>
        </div>
        <div style="display:grid; grid-template-columns:1.4fr 1fr 1fr; gap:0.75rem; margin-top:0.8rem;">
            <div style="background:#ffffff; padding:0.85rem; border-radius:0.75rem; border:1px solid #E5E7EB;">
                <div style="font-size:0.74rem; color:#64748B; margin-bottom:0.3rem;">差异聚焦</div>
                <div style="font-size:0.92rem; color:#0F172A; font-weight:700;">{best_team_name} 样本 {best_team_acc:.1f}% / 人均 {best_per_capita:.1f}%</div>
                <div style="font-size:0.78rem; color:{risk_color}; margin-top:0.25rem;">待关注：{worst_team_name} · 样本差值 {gap_pct:.1f}% / 人均差值 {per_capita_gap:.1f}%</div>
            </div>
            <div style="background:#ffffff; padding:0.85rem; border-radius:0.75rem; border:1px solid #E5E7EB;">
                <div style="font-size:0.74rem; color:#64748B; margin-bottom:0.3rem;">风险人数</div>
                <div style="font-size:1.05rem; color:#0F172A; font-weight:700;">P0 {p0_cnt} / P1 {p1_cnt}</div>
                <div style="font-size:0.78rem; color:#64748B; margin-top:0.25rem;">近7天滚动识别</div>
            </div>
            <div style="background:#ffffff; padding:0.85rem; border-radius:0.75rem; border:1px solid #E5E7EB;">
                <div style="font-size:0.74rem; color:#64748B; margin-bottom:0.3rem;">优先动作</div>
                <div style="font-size:0.84rem; color:#0F172A; line-height:1.45; font-weight:600;">{risk_note}</div>
            </div>
        </div>
        <div style="margin-top:0.8rem; height:6px; background:#E2E8F0; border-radius:999px; overflow:hidden;">
            <div style="width:{progress_width}%; height:100%; background:linear-gradient(90deg, {COLORS.stage_internal} 0%, {COLORS.stage_external} 60%, {COLORS.stage_formal} 100%);"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
