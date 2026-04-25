"""数据管理 - 新人状态管理 Tab。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from utils.audit import log_action
from views.data_mgmt._shared import repo

from services.newcomer_lifecycle import (
    ensure_lifecycle_schema,
    batch_infer_stages,
    generate_promotion_recommendations,
    update_member_status,
    load_graduation_rules,
    load_milestones,
    get_status_label,
    STATUS_LABELS,
    DEFAULT_RULES,
)


def render_newcomer_status_tab():
    """渲染「新人状态管理」Tab 内容。"""
    st.markdown("### 🔄 新人状态管理")
    st.caption("查看并管理新人的培训阶段状态。系统根据质检数据自动推断当前阶段，你可以一键确认晋级或手动调整。")

    # 确保表结构
    try:
        ensure_lifecycle_schema(repo)
    except Exception as e:
        st.error(f"初始化生命周期表失败：{e}")

    status_tab = st.radio(
        "功能选择",
        ["📊 状态总览", "🎯 晋级推荐", "⚙️ 毕业条件配置", "📜 里程碑记录"],
        horizontal=True, key="status_mgmt_mode",
    )

    if status_tab == "📊 状态总览":
        _render_status_overview()
    elif status_tab == "🎯 晋级推荐":
        _render_promotion_recommendations()
    elif status_tab == "⚙️ 毕业条件配置":
        _render_graduation_rules()
    elif status_tab == "📜 里程碑记录":
        _render_milestones()


def _render_status_overview():
    """状态总览面板。"""
    st.markdown("#### 状态同步")
    st.info("系统会根据已有质检数据推断每位新人的实际阶段。点击「同步」可自动将状态推进到正确的阶段。")

    if st.button("🔄 扫描并同步状态", key="sync_status", type="primary"):
        with st.spinner("正在分析所有新人的质检数据..."):
            try:
                from services.newcomer_lifecycle import batch_sync_inferred_status
                result = batch_sync_inferred_status(repo, operator="admin")
                st.success(f"✅ 同步完成！更新 {result['updated']} 人，跳过 {result['skipped']} 人")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"同步失败：{e}")

    st.markdown("---")
    st.markdown("#### 当前状态分布")
    try:
        status_dist = repo.fetch_df("""
            SELECT status, COUNT(*) AS cnt
            FROM dim_newcomer_batch
            GROUP BY status ORDER BY cnt DESC
        """)
        if status_dist is not None and not status_dist.empty:
            cols = st.columns(min(len(status_dist), 6))
            for i, (_, row) in enumerate(status_dist.iterrows()):
                label, color, bg = get_status_label(row["status"])
                with cols[i % len(cols)]:
                    st.markdown(f"""
                    <div style="background:{bg}; border:1px solid {color}; border-radius:0.75rem; padding:0.75rem; text-align:center;">
                        <div style="font-size:0.75rem; color:{color};">{label}</div>
                        <div style="font-size:1.5rem; font-weight:700; color:{color};">{int(row['cnt'])}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("暂无新人数据")
    except Exception as e:
        st.warning(f"查询失败：{e}")

    st.markdown("---")
    st.markdown("#### 详细状态列表")
    try:
        inferred_df = batch_infer_stages(repo)
        if not inferred_df.empty:
            display_df = inferred_df.copy()
            display_df["当前状态"] = display_df["current_status"].apply(lambda s: get_status_label(s)[0])
            display_df["推断状态"] = display_df["inferred_status"].apply(lambda s: get_status_label(s)[0])
            display_df["需更新"] = display_df["needs_update"].apply(lambda x: "⚠️ 是" if x else "✅ 一致")
            st.dataframe(
                display_df[["batch_name", "reviewer_name", "当前状态", "推断状态", "需更新"]].rename(
                    columns={"batch_name": "批次", "reviewer_name": "姓名"}
                ),
                use_container_width=True, hide_index=True, height=400,
            )
            needs_update_cnt = int(display_df["needs_update"].sum())
            if needs_update_cnt > 0:
                st.warning(f"有 {needs_update_cnt} 人的状态与实际阶段不一致，建议点击上方「同步」按钮更新。")
        else:
            st.info("暂无需要状态管理的新人")
    except Exception as e:
        st.warning(f"推断状态失败：{e}")

    st.markdown("---")
    st.markdown("#### 手动调整状态")
    try:
        all_members = repo.fetch_df("""
            SELECT reviewer_name, batch_name, status
            FROM dim_newcomer_batch ORDER BY batch_name, reviewer_name
        """)
        if all_members is not None and not all_members.empty:
            member_options = [f"{r['reviewer_name']} ({r['batch_name']})" for _, r in all_members.iterrows()]
            selected_member = st.selectbox("选择人员", member_options, key="manual_status_member")
            if selected_member:
                m_name = selected_member.split(" (")[0]
                m_batch = selected_member.split("(")[1].rstrip(")")
                m_current = all_members[
                    (all_members["reviewer_name"] == m_name) & (all_members["batch_name"] == m_batch)
                ].iloc[0]["status"]
                st.caption(f"当前状态：{get_status_label(m_current)[0]}")

                new_status = st.selectbox(
                    "新状态",
                    ["pending", "internal_training", "external_training", "formal_probation", "graduated", "exited"],
                    format_func=lambda s: get_status_label(s)[0],
                    key="manual_new_status",
                )
                manual_note = st.text_input("备注（可选）", key="manual_status_note", placeholder="如：提前毕业、转岗等")

                if st.button("✅ 确认变更", key="apply_manual_status"):
                    if new_status == m_current:
                        st.warning("新状态与当前状态相同，无需变更")
                    else:
                        success = update_member_status(
                            repo, m_name, m_batch, new_status,
                            trigger_type="manual", operator="admin", note=manual_note or None,
                        )
                        if success:
                            st.success(f"✅ {m_name} 状态已更新为 {get_status_label(new_status)[0]}")
                            st.cache_data.clear()
                        else:
                            st.error("状态更新失败")
    except Exception as e:
        st.warning(f"加载人员列表失败：{e}")


def _render_promotion_recommendations():
    """晋级推荐面板。"""
    st.markdown("#### 系统推荐晋级名单")
    st.info("系统根据每位新人的连续达标天数和累计质检量，自动检查是否满足晋级条件。")

    if st.button("🔍 扫描晋级条件", key="scan_promotion", type="primary"):
        with st.spinner("正在检查所有在训新人的晋级条件..."):
            try:
                recommendations = generate_promotion_recommendations(repo)
                st.session_state["promotion_recommendations"] = recommendations
            except Exception as e:
                st.error(f"扫描失败：{e}")

    recommendations = st.session_state.get("promotion_recommendations", pd.DataFrame())
    if not isinstance(recommendations, pd.DataFrame) or recommendations.empty:
        st.info("暂无晋级推荐，请先点击「扫描晋级条件」按钮。")
    else:
        st.success(f"🎯 发现 {len(recommendations)} 位新人满足晋级条件！")

        for idx, rec in recommendations.iterrows():
            from_label = get_status_label(rec["current_status_mapped"])[0]
            to_label = get_status_label(rec["recommended_status"])[0]

            with st.container():
                col_info, col_action = st.columns([3, 1])
                with col_info:
                    st.markdown(f"""
                    **{rec['reviewer_name']}** · {rec['batch_name']} · {rec.get('team_name', '')}
                    <br><span style="font-size:0.85rem; color:#6B7280;">
                    {from_label} → {to_label} · {rec['evidence_summary']}
                    </span>
                    """, unsafe_allow_html=True)
                with col_action:
                    if st.button(f"✅ 确认", key=f"promote_{idx}"):
                        success = update_member_status(
                            repo,
                            reviewer_name=rec["reviewer_name"],
                            batch_name=rec["batch_name"],
                            new_status=rec["recommended_status"],
                            trigger_type="auto",
                            rule_code=rec["rule_code"],
                            evidence=rec.get("evidence_json"),
                            operator="admin",
                            note=f"通过晋级推荐确认: {rec['rule_name']}",
                        )
                        if success:
                            st.success(f"✅ {rec['reviewer_name']} 已晋级为 {to_label}")
                            st.cache_data.clear()
                            st.rerun()
                st.divider()


def _render_graduation_rules():
    """毕业条件配置面板。"""
    st.markdown("#### 晋级/毕业条件规则")
    st.caption("配置每个阶段的晋级条件。规则修改后，下次扫描推荐时生效。")

    try:
        rules_df = repo.fetch_df("""
            SELECT rule_code, rule_name, from_status, to_status, metric,
                   compare_op, threshold, consecutive_days, min_qa_cnt, enabled, description
            FROM dim_graduation_rule ORDER BY from_status
        """)
        if rules_df is not None and not rules_df.empty:
            for _, rule in rules_df.iterrows():
                from_label = get_status_label(rule["from_status"])[0]
                to_label = get_status_label(rule["to_status"])[0]
                status_icon = "🟢" if rule["enabled"] else "⚪"
                with st.expander(f"{status_icon} {rule['rule_name']} ({from_label} → {to_label})", expanded=False):
                    st.caption(rule["description"] or "")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_threshold = st.number_input(
                            "阈值 (%)", value=float(rule["threshold"]),
                            min_value=0.0, max_value=100.0, step=0.5,
                            key=f"rule_threshold_{rule['rule_code']}",
                        )
                    with col2:
                        new_days = st.number_input(
                            "连续天数", value=int(rule["consecutive_days"]),
                            min_value=1, max_value=30, step=1,
                            key=f"rule_days_{rule['rule_code']}",
                        )
                    with col3:
                        new_min_qa = st.number_input(
                            "最低质检量", value=int(rule["min_qa_cnt"]),
                            min_value=1, max_value=500, step=10,
                            key=f"rule_qa_{rule['rule_code']}",
                        )
                    new_enabled = st.checkbox("启用", value=bool(rule["enabled"]), key=f"rule_enabled_{rule['rule_code']}")

                    if st.button("💾 保存", key=f"save_rule_{rule['rule_code']}"):
                        repo.execute("""
                            UPDATE dim_graduation_rule
                            SET threshold = %s, consecutive_days = %s, min_qa_cnt = %s, enabled = %s
                            WHERE rule_code = %s
                        """, [new_threshold, new_days, new_min_qa, 1 if new_enabled else 0, rule["rule_code"]])
                        st.success(f"✅ 规则 {rule['rule_name']} 已更新")
                        log_action("modify", "dim_graduation_rule",
                                   f"更新规则 {rule['rule_code']}: threshold={new_threshold}, days={new_days}, min_qa={new_min_qa}")
        else:
            st.info("暂无毕业条件规则，系统将自动初始化默认规则。")
    except Exception as e:
        st.warning(f"加载规则失败：{e}")


def _render_milestones():
    """里程碑记录面板。"""
    st.markdown("#### 状态变更历史")
    try:
        milestones = load_milestones(repo, limit=100)
        if milestones is not None and not milestones.empty:
            display_ms = milestones.copy()
            display_ms["变更前"] = display_ms["from_status"].apply(lambda s: get_status_label(s)[0] if s else "—")
            display_ms["变更后"] = display_ms["to_status"].apply(lambda s: get_status_label(s)[0])
            display_ms["触发方式"] = display_ms["trigger_type"].map({
                "auto": "🤖 自动推荐", "manual": "✋ 手动操作", "system": "⚙️ 系统同步"
            }).fillna("—")
            st.dataframe(
                display_ms[[
                    "created_at", "reviewer_name", "batch_name",
                    "变更前", "变更后", "触发方式", "operator", "note",
                ]].rename(columns={
                    "created_at": "时间", "reviewer_name": "姓名",
                    "batch_name": "批次", "operator": "操作人", "note": "备注",
                }),
                use_container_width=True, hide_index=True, height=500,
            )
        else:
            st.info("暂无状态变更记录")
    except Exception as e:
        st.warning(f"加载里程碑失败：{e}")
