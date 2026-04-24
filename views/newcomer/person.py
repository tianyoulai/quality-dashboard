"""新人追踪 — 👤 个人追踪模块。

渲染个人信息卡片、逐日趋势、阶段结构、错误明细、全量质检记录。
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from views.newcomer._shared import display_text, get_stage_meta, render_plot, safe_pct, STAGE_SHORT_MAP


def render_person(ctx: dict) -> None:
    """渲染个人追踪视图。"""
    members_df = ctx["members_df"]
    combined_qa_df = ctx["combined_qa_df"]
    repo = ctx["repo"]
    load_newcomer_error_detail = ctx["load_newcomer_error_detail"]
    load_person_all_qa_records = ctx["load_person_all_qa_records"]

    st.markdown("#### 👤 个人追踪")
    st.caption("个人追踪页只展示单人样本正确率和错误明细，不展示聚合层的人均正确率。")

    if members_df.empty:
        st.info("暂无新人映射数据。")
        return

    person_options = members_df.apply(
        lambda r: f"{r['reviewer_alias'] or r['reviewer_name']} ({r['batch_name']} · {r['team_name'] or '未分组'})", axis=1
    ).tolist()
    selected_person = st.selectbox("选择审核人", options=person_options, key="nc_person_select")
    if not selected_person:
        return

    alias = selected_person.split(" (")[0]
    # 同时匹配 reviewer_alias 和 reviewer_name（兼容 alias 为空的情况）
    _match_mask = (members_df["reviewer_alias"] == alias) | (members_df["reviewer_name"] == alias)
    if not _match_mask.any():
        st.warning(f"未找到审核人：{alias}")
        return
    person_info = members_df[_match_mask].iloc[0]
    _short_alias = alias.replace("云雀联营-", "") if "云雀联营-" in alias else alias
    _dim_name = person_info["reviewer_name"]
    _match_names = {alias, _short_alias, _dim_name}
    person_qa = combined_qa_df[combined_qa_df["reviewer_name"].isin(_match_names)].copy() if not combined_qa_df.empty else pd.DataFrame()

    person_stage_view = person_qa.groupby("stage", as_index=False).agg(
        qa_cnt=("qa_cnt", "sum"), correct_cnt=("correct_cnt", "sum"),
    ) if not person_qa.empty else pd.DataFrame()
    if not person_stage_view.empty:
        person_stage_view["accuracy"] = person_stage_view.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)

    current_stage = "formal" if (not person_stage_view.empty and "formal" in person_stage_view["stage"].tolist()) else (
        "external" if (not person_stage_view.empty and "external" in person_stage_view["stage"].tolist()) else "internal"
    )
    stage_label, stage_color, stage_bg, _ = get_stage_meta(current_stage)
    days = (date.today() - person_info["join_date"]).days if person_info["join_date"] else 0

    def _acc(stage: str) -> float:
        if person_stage_view.empty or stage not in person_stage_view["stage"].values:
            return 0.0
        return float(person_stage_view.loc[person_stage_view["stage"] == stage, "accuracy"].max())

    internal_acc = _acc("internal")
    external_acc = _acc("external")
    formal_acc = _acc("formal")
    total_qa = int(person_qa["qa_cnt"].sum()) if not person_qa.empty else 0

    # --- 个人信息卡 ---
    st.markdown(f"""
    <div style="background:linear-gradient(135deg, #ffffff 0%, #F8FAFC 100%); border:1px solid #E5E7EB; border-radius:1rem; padding:1rem 1.2rem; margin-bottom:1rem;">
        <div style="display:flex; justify-content:space-between; gap:1rem; align-items:flex-start; flex-wrap:wrap;">
            <div>
                <div style="font-size:1.4rem; font-weight:700; color:#0F172A;">{person_info['reviewer_name']}</div>
                <div style="margin-top:0.35rem; font-size:0.84rem; color:#64748B; line-height:1.6;">
                    {person_info['batch_name']} · {display_text(person_info['team_name'])} · 入职 {days} 天<br>
                    联营管理：{display_text(person_info['team_leader'])} · 交付PM：{display_text(person_info['delivery_pm'])} · 质培owner：{display_text(person_info['owner'])} · 导师/质检：{display_text(person_info['mentor_name'])}
                </div>
            </div>
            <div style="padding:0.28rem 0.8rem; border-radius:999px; background:{stage_bg}; color:{stage_color}; font-size:0.8rem; font-weight:700; border:1px solid {stage_color};">{stage_label}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("🏫 内部正确率", f"{internal_acc:.1f}%")
    with m2:
        st.metric("🔍 外部正确率", f"{external_acc:.1f}%")
    with m3:
        st.metric("✅ 正式正确率", f"{formal_acc:.1f}%")
    with m4:
        st.metric("📦 累计质检量", f"{total_qa:,}")

    # --- 数据关联诊断 ---
    if total_qa == 0:
        _render_diagnosis(person_info, repo)

    # --- 逐日趋势 + 阶段结构 ---
    if not person_qa.empty:
        detail_col1, detail_col2 = st.columns([1.2, 1])
        with detail_col1:
            st.markdown("##### 📈 个人逐日趋势")
            daily = person_qa.groupby(["biz_date", "stage"], as_index=False).agg(
                qa_cnt=("qa_cnt", "sum"), correct_cnt=("correct_cnt", "sum"),
            )
            daily["accuracy"] = daily.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
            fig_p = go.Figure()
            for stg in ["internal", "external", "formal"]:
                subset = daily[daily["stage"] == stg]
                if subset.empty:
                    continue
                sname, scolor, _, _ = get_stage_meta(stg)
                fig_p.add_trace(go.Scatter(
                    x=pd.to_datetime(subset["biz_date"]), y=subset["accuracy"],
                    mode="lines+markers", name=sname,
                    line=dict(color=scolor, width=2.5), marker=dict(size=7),
                ))
            fig_p.add_hline(y=98, line_dash="dash", line_color="#10b981", annotation_text="转正线 98%")
            fig_p.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_p, f"person_trend_{alias}")
        with detail_col2:
            st.markdown("##### 📊 阶段结构")
            if not person_stage_view.empty:
                person_stage_view["阶段"] = person_stage_view["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检", "formal": "✅ 正式上线"})
                fig_ps = px.pie(
                    person_stage_view, values="qa_cnt", names="阶段", hole=0.55, color="阶段",
                    color_discrete_map={"🏫 内部质检": "#8b5cf6", "🔍 外部质检": "#3b82f6", "✅ 正式上线": "#10b981"},
                )
                fig_ps.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_ps, f"person_stage_{alias}")

    # --- 错误明细 ---
    st.markdown("##### 📋 近期错误明细")
    error_detail_df = load_newcomer_error_detail(alias, 80)
    if error_detail_df is not None and not error_detail_df.empty:
        display_errors = error_detail_df[["biz_date", "stage", "queue_name", "content_type", "training_topic", "risk_level", "comment_text", "raw_judgement", "final_judgement", "error_type", "qa_note"]].copy()
        display_errors.columns = ["日期", "阶段", "队列", "内容类型", "培训专题", "风险等级", "评论文本", "一审结果", "质检结果", "错误类型", "质检备注"]
        display_errors["阶段"] = display_errors["阶段"].map(STAGE_SHORT_MAP).fillna("—")
        st.dataframe(display_errors, use_container_width=True, hide_index=True, height=320)
        csv = display_errors.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 导出错误明细", csv, file_name=f"errors_{alias}.csv", mime="text/csv")
    else:
        st.success("🎉 该新人暂无错误记录。")

    # --- 全量质检记录 ---
    with st.expander("📄 查看全量质检记录", expanded=False):
        all_detail_df = load_person_all_qa_records(alias, 200)
        if all_detail_df is not None and not all_detail_df.empty:
            display_all = all_detail_df.copy()
            col_rename = {
                "biz_date": "日期", "stage": "阶段", "queue_name": "队列",
                "content_type": "内容类型", "training_topic": "培训专题",
                "risk_level": "风险等级", "comment_text": "评论文本",
                "raw_judgement": "一审结果", "final_judgement": "质检结果",
                "error_type": "错误类型", "qa_note": "质检备注", "is_correct": "是否正确",
            }
            for old_name, new_name in col_rename.items():
                if old_name in display_all.columns:
                    display_all = display_all.rename(columns={old_name: new_name})
            if "阶段" in display_all.columns:
                display_all["阶段"] = display_all["阶段"].map(STAGE_SHORT_MAP).fillna("—")
            if "是否正确" in display_all.columns:
                display_all["是否正确"] = display_all["是否正确"].map({1: "✅ 正确", 0: "❌ 错误"}).fillna("—")

            _total = len(display_all)
            _correct = int((all_detail_df.get("is_correct", pd.Series(dtype=int)) == 1).sum())
            _error = _total - _correct
            st.caption(f"共 {_total} 条记录 · ✅ 正确 {_correct} · ❌ 错误 {_error} · 正确率 {_correct / _total * 100:.1f}%" if _total > 0 else "暂无记录")
            st.dataframe(display_all, use_container_width=True, hide_index=True, height=400)
            all_csv = display_all.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 导出全量质检记录", all_csv, file_name=f"all_qa_{alias}.csv", mime="text/csv", key=f"dl_all_{alias}")
        else:
            st.info("暂无该审核人的质检记录数据。")


def _render_diagnosis(person_info: pd.Series, repo) -> None:
    """当质检量为 0 时，渲染数据关联诊断面板。"""
    with st.expander("🔍 数据关联诊断（质检量为 0，可能存在关联问题）", expanded=True):
        diag_alias = person_info["reviewer_alias"]
        diag_name = person_info["reviewer_name"]
        st.markdown(f"""
        **当前审核人信息**：
        - 姓名：`{diag_name}` → 系统映射名（reviewer_alias）：`{diag_alias}`
        - 批次：{person_info['batch_name']} · 生效日期：{person_info.get('effective_start_date', '—')} ~ {person_info.get('effective_end_date', '无限期')}
        """)
        diag_newcomer = repo.fetch_df("""
            SELECT reviewer_name, stage, COUNT(*) AS cnt, MIN(biz_date) AS min_date, MAX(biz_date) AS max_date
            FROM fact_newcomer_qa
            WHERE reviewer_name = %s OR reviewer_name LIKE %s
            GROUP BY reviewer_name, stage
        """, [diag_alias, f"%{diag_name}%"])

        if diag_newcomer is not None and not diag_newcomer.empty:
            st.warning("⚠️ fact_newcomer_qa 中**存在**该审核人的记录，但未被关联到当前批次。可能原因：")
            st.dataframe(diag_newcomer, use_container_width=True, hide_index=True)
            st.markdown("""
            - **日期不在生效区间内**：质检数据日期早于 `effective_start_date`
            - **reviewer_name 不匹配**：fact表中的名称与 dim 表中的 `reviewer_alias` 不一致
            - **batch_name 未回填**：请点击页面顶部的「🔗 自动关联到批次」按钮
            """)
        else:
            diag_formal = repo.fetch_df("""
                SELECT reviewer_name, COUNT(*) AS cnt, MIN(biz_date) AS min_date, MAX(biz_date) AS max_date
                FROM mart_day_auditor
                WHERE reviewer_name = %s OR reviewer_name LIKE %s
                GROUP BY reviewer_name
            """, [diag_alias, f"%{diag_name}%"])
            if diag_formal is not None and not diag_formal.empty:
                st.info("📋 该审核人在 **正式质检数据**（mart_day_auditor）中存在记录，但可能尚未进入新人质检阶段。")
                st.dataframe(diag_formal, use_container_width=True, hide_index=True)
            else:
                st.error(f"❌ 该审核人在 fact_newcomer_qa 和 mart_day_auditor 中均**无记录**，请确认：\n"
                         f"1. 数据是否已导入\n"
                         f"2. reviewer_alias 映射名是否正确（当前为 `{diag_alias}`）")
