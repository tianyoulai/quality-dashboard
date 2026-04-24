"""新人追踪 — ⚠️ 异常告警模块。

渲染 P0/P1 告警、风险驾驶舱、基地级拆解、批次级提醒、高频错误。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from views.newcomer._shared import display_text, safe_pct


def render_alert(ctx: dict) -> None:
    """渲染异常告警视图。"""
    combined_qa_df = ctx["combined_qa_df"]
    recent_person_perf_df = ctx["recent_person_perf_df"]
    batch_watch_df = ctx["batch_watch_df"]
    error_summary_df = ctx["error_summary_df"]
    team_alert_df = ctx["team_alert_df"]

    st.markdown("#### ⚠️ 异常告警")

    if combined_qa_df.empty:
        st.info("暂无质检数据，无法生成告警。")
        return

    # --- 分组 ---
    p0_df = recent_person_perf_df[recent_person_perf_df["risk_level"] == "P0"].copy() if not recent_person_perf_df.empty else pd.DataFrame()
    p1_df = recent_person_perf_df[recent_person_perf_df["risk_level"] == "P1"].copy() if not recent_person_perf_df.empty else pd.DataFrame()
    near_grad_df = recent_person_perf_df[recent_person_perf_df["risk_level"] == "NEAR"].copy() if not recent_person_perf_df.empty else pd.DataFrame()
    batch_risk_df = batch_watch_df[(batch_watch_df["gap_pct"] >= 2.5) | (batch_watch_df["p0_cnt"] > 0) | (batch_watch_df["p1_cnt"] > 0)].copy() if not batch_watch_df.empty else pd.DataFrame()
    practice_df = ctx.get("practice_df", pd.DataFrame())
    practice_count = int(practice_df["row_cnt"].sum()) if not practice_df.empty else 0

    error_focus_df = _build_error_focus(error_summary_df)

    st.info("告警口径：近 7 天滚动统计。个人与告警阈值继续按单人样本正确率判断；P0 = 样本正确率 < 90% 或漏判率 ≥ 2%；P1 = 样本正确率 < 95% 或总问题率 ≥ 2.5%；接近转正 = 外检样本正确率 97.5%~98%。")

    # --- 告警指标 ---
    a1, a2, a3, a4, a5 = st.columns(5)
    with a1:
        st.metric("🔴 P0", len(p0_df))
    with a2:
        st.metric("🟡 P1", len(p1_df))
    with a3:
        st.metric("🔵 接近转正", len(near_grad_df))
    with a4:
        st.metric("🧪 借调练习", practice_count)
    with a5:
        st.metric("🏷️ 批次级提醒", len(batch_risk_df) + len(error_focus_df))

    # --- 风险驾驶舱 ---
    if not batch_watch_df.empty:
        _render_cockpit(batch_watch_df)

    # --- P0/P1 人员 + 接近转正 ---
    risk_col1, risk_col2 = st.columns(2)
    with risk_col1:
        _render_risk_people(p0_df, p1_df)
    with risk_col2:
        _render_near_grad(near_grad_df, practice_df)

    # --- 基地级风险拆解 ---
    _render_team_risk(team_alert_df)

    # --- 批次级提醒 ---
    _render_batch_alerts(batch_risk_df, error_focus_df)

    # --- 高频错误 ---
    if error_summary_df is not None and not error_summary_df.empty:
        top_error = error_summary_df.groupby("error_type", as_index=False)["error_cnt"].sum().sort_values("error_cnt", ascending=False).head(5)
        st.markdown("#### 🧩 近期高频错误")
        st.dataframe(top_error.rename(columns={"error_type": "错误类型", "error_cnt": "错误次数"}), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
#  内部渲染函数
# ═══════════════════════════════════════════════════════════════

def _build_error_focus(error_summary_df):
    if error_summary_df is None or error_summary_df.empty:
        return pd.DataFrame()
    batch_total = error_summary_df.groupby("batch_name", as_index=False)["error_cnt"].sum().rename(columns={"error_cnt": "batch_error_cnt"})
    batch_top = error_summary_df.groupby(["batch_name", "error_type"], as_index=False)["error_cnt"].sum()
    batch_top = batch_top.sort_values(["batch_name", "error_cnt"], ascending=[True, False]).groupby("batch_name", as_index=False).head(1)
    df = batch_top.merge(batch_total, on="batch_name", how="left")
    df["top_error_share"] = df.apply(lambda r: safe_pct(r["error_cnt"], r["batch_error_cnt"]), axis=1)
    return df[df["top_error_share"] >= 30].copy()


def _render_cockpit(batch_watch_df):
    st.markdown("##### 🧭 风险驾驶舱")
    df = batch_watch_df.copy()
    df["风险批次数"] = df["risk_label"].str.contains("风险").astype(int)
    df["关注批次数"] = df["risk_label"].str.contains("关注").astype(int)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("🔴 风险批次数", int(df["风险批次数"].sum()))
    with c2:
        st.metric("🟡 关注批次数", int(df["关注批次数"].sum()))
    with c3:
        st.metric("📏 平均基地差值", f"{df['gap_pct'].mean():.1f}%")
    with c4:
        top_focus = df.sort_values(["gap_pct", "accuracy"], ascending=[False, True]).iloc[0]
        st.metric("🎯 当前最需盯批次", display_text(top_focus["batch_name"]), delta=f"差值 {float(top_focus['gap_pct']):.1f}%")


def _render_risk_people(p0_df, p1_df):
    st.markdown("##### 🔴 P0 / P1 人员")
    df = pd.concat([p0_df.assign(告警级别="P0"), p1_df.assign(告警级别="P1")], ignore_index=True) if (not p0_df.empty or not p1_df.empty) else pd.DataFrame()
    if not df.empty:
        view = df.rename(columns={
            "short_name": "姓名", "batch_name": "批次", "team_name": "基地/团队",
            "team_leader": "联营管理", "mentor_name": "导师/质检",
            "accuracy": "近7天样本正确率", "misjudge_rate": "错判率",
            "missjudge_rate": "漏判率", "issue_rate": "总问题率", "qa_cnt": "质检量",
        })[["告警级别", "姓名", "批次", "基地/团队", "联营管理", "导师/质检", "质检量", "近7天样本正确率", "错判率", "漏判率", "总问题率"]]
        st.dataframe(view.sort_values(["告警级别", "近7天样本正确率", "总问题率"], ascending=[True, True, False]),
                     use_container_width=True, hide_index=True, height=280)
    else:
        st.success("当前没有 P0 / P1 人员。")


def _render_near_grad(near_grad_df, practice_df):
    st.markdown("##### 🔵 接近转正 / 借调练习")
    if not near_grad_df.empty:
        view = near_grad_df.rename(columns={
            "short_name": "姓名", "batch_name": "批次", "team_name": "基地/团队",
            "accuracy": "近7天样本正确率", "qa_cnt": "质检量", "mentor_name": "导师/质检",
        })[["姓名", "批次", "基地/团队", "导师/质检", "质检量", "近7天样本正确率"]]
        st.dataframe(view.sort_values(["近7天样本正确率", "质检量"], ascending=[False, False]),
                     use_container_width=True, hide_index=True, height=160)
    else:
        st.info("当前没有接近转正人员。")

    if not practice_df.empty:
        view = practice_df.rename(columns={
            "reviewer_name": "审核人", "stage": "阶段", "row_cnt": "练习记录数",
            "start_date": "开始日期", "end_date": "结束日期",
        })[["审核人", "阶段", "练习记录数", "开始日期", "结束日期"]]
        st.dataframe(view, use_container_width=True, hide_index=True, height=120)


def _render_team_risk(team_alert_df):
    st.markdown("##### 🛠️ 基地级风险拆解与带教动作")
    if team_alert_df.empty:
        st.success("当前没有需要重点拆解的基地级风险。")
        return

    c1, c2 = st.columns([1.15, 1])
    with c1:
        view = team_alert_df.rename(columns={
            "batch_name": "批次", "team_name": "基地/团队", "member_cnt": "人数",
            "qa_cnt": "质检量", "sample_accuracy": "样本正确率",
            "per_capita_accuracy": "人均正确率", "accuracy_gap": "口径差值",
            "issue_rate": "总问题率", "misjudge_rate": "错判率", "missjudge_rate": "漏判率",
            "top_error_type": "主要错误类型", "top_error_share": "错误集中度",
            "risk_label": "批次风险", "建议动作": "建议动作",
        })[["批次风险", "批次", "基地/团队", "人数", "质检量", "样本正确率", "人均正确率", "口径差值", "总问题率", "错判率", "漏判率", "主要错误类型", "错误集中度", "建议动作"]]
        st.dataframe(view.head(12), use_container_width=True, hide_index=True, height=320)
    with c2:
        for _, row in team_alert_df.head(4).iterrows():
            accent = "#dc2626" if float(row["关注分"]) >= 8 else ("#d97706" if float(row["关注分"]) >= 5 else "#059669")
            bg = "#fef2f2" if accent == "#dc2626" else ("#fffbeb" if accent == "#d97706" else "#ecfdf5")
            st.markdown(f"""
            <div style="padding: 0.95rem 1rem; border-radius: 0.75rem; background: {bg}; border-left: 4px solid {accent}; margin-bottom: 0.75rem;">
                <div style="font-size: 0.82rem; color: {accent}; font-weight: 700; margin-bottom: 0.25rem;">{display_text(row.get('batch_name'))} · {display_text(row.get('team_name'))}</div>
                <div style="font-size: 0.92rem; color: #111827; line-height: 1.65;">
                    样本正确率 <strong>{float(row['sample_accuracy']):.1f}%</strong>，人均正确率 <strong>{float(row['per_capita_accuracy']):.1f}%</strong>，主要错误：<strong>{display_text(row.get('top_error_type'))}</strong>
                </div>
                <div style="font-size: 0.84rem; color: #475569; margin-top: 0.45rem;">建议动作：{row['建议动作']}</div>
            </div>
            """, unsafe_allow_html=True)


def _render_batch_alerts(batch_risk_df, error_focus_df):
    st.markdown("##### 🧭 批次级提醒")
    cards = []
    if not batch_risk_df.empty:
        for _, row in batch_risk_df.sort_values(["gap_pct", "accuracy"], ascending=[False, True]).iterrows():
            cards.append((
                row["risk_label"],
                f"**{row['batch_name']}** 批次内基地差值 **{row['gap_pct']:.1f}%**，待关注基地：**{display_text(row['worst_team_name'])}**（{float(row['worst_team_acc']):.1f}%）",
                f"优先辅导：{row['focus_people']}",
                row["risk_bg"], row["risk_color"],
            ))
    if not error_focus_df.empty:
        for _, row in error_focus_df.sort_values("top_error_share", ascending=False).iterrows():
            cards.append((
                "🟡 专题提醒",
                f"**{row['batch_name']}** 当前错误集中在 **{row['error_type']}**，占近 7 天错误的 **{row['top_error_share']:.1f}%**",
                "建议围绕该错误类型安排专项复盘或抽样复训。",
                "#fffbeb", "#d97706",
            ))

    if not cards:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%); padding: 1rem; border-radius: 0.75rem; text-align: center; border: 1px solid #10B981;'>
            <div style='color: #10B981; font-weight: 700; font-size: 1.2rem;'>✅ 当前无异常告警</div>
            <div style='font-size: 0.85rem; color: #047857;'>当前筛选范围内，新人整体表现稳定。</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for title, msg, suggestion, bg, border in cards[:12]:
            st.markdown(f"""
            <div style="padding: 1rem; border-radius: 0.75rem; background: {bg}; border-left: 4px solid {border}; margin-bottom: 0.75rem;">
                <div style="font-size: 0.82rem; color: {border}; font-weight: 700; margin-bottom: 0.3rem;">{title}</div>
                <div style="font-size: 0.92rem; color: #111827; line-height: 1.6;">{msg}</div>
                <div style="font-size: 0.84rem; color: #475569; margin-top: 0.45rem;">{suggestion}</div>
            </div>
            """, unsafe_allow_html=True)
