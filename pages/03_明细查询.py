"""明细查询页：灵活筛选 + 下钻 + CSV 导出。"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services.dashboard_service import DashboardService
from storage.repository import DashboardRepository

# 设计系统 v3.0
from utils.design_system import ds, COLORS
ds.inject_theme()

repo = DashboardRepository()
service = DashboardService()

# Hero 区域（设计系统组件）
ds.hero("🔍", "明细查询", "多维度筛选 · 问题下钻 · 数据导出")


@st.cache_data(show_spinner="正在加载筛选选项...", ttl=600)
def get_filter_options() -> dict:
    """获取筛选选项（缓存 10 分钟）。
    
    优化 v2：合并5次查询为2次，减少DB往返：
    1. 一次查 DISTINCT group/queue/reviewer/error_type（利用 fact_qa_event 单表）
    2. 一次查日期范围（MIN/MAX）
    """
    # 查询1: 一次性获取所有维度选项
    dims = repo.fetch_df("""
        SELECT DISTINCT
            COALESCE(NULLIF(TRIM(group_name), ''), NULLIF(TRIM(mother_biz), ''), NULLIF(TRIM(sub_biz), '')) AS group_name,
            COALESCE(NULLIF(TRIM(queue_name), ''), NULLIF(TRIM(sub_biz), '')) AS queue_name,
            reviewer_name
        FROM fact_qa_event
        WHERE COALESCE(NULLIF(TRIM(group_name), ''), NULLIF(TRIM(mother_biz), ''), NULLIF(TRIM(sub_biz), '')) IS NOT NULL
    """)
    
    # 查询1b: 单独查错误类型（可能来自不同字段或不同表）
    error_type_df = repo.fetch_df("""
        SELECT DISTINCT NULLIF(TRIM(error_type), '') AS error_type
        FROM fact_qa_event
        WHERE error_type IS NOT NULL AND TRIM(error_type) != '' AND TRIM(error_type) != '正常'
        ORDER BY error_type
        LIMIT 500
    """)
    
    # 如果 fact_qa_event 中没有错误类型数据，尝试从文本字段推断
    if error_type_df.empty or error_type_df["error_type"].dropna().empty:
        try:
            error_type_df = repo.fetch_df("""
                SELECT DISTINCT
                    CASE
                        WHEN COALESCE(raw_judgement,'') LIKE '%%错判%%'
                          OR COALESCE(raw_judgement,'') LIKE '%%误判%%'
                          OR COALESCE(final_judgement,'') LIKE '%%错判%%'
                        THEN '错判'
                        WHEN COALESCE(raw_judgement,'') LIKE '%%漏判%%'
                          OR COALESCE(raw_judgement,'') LIKE '%%漏审%%'
                          OR COALESCE(final_judgement,'') LIKE '%%漏判%%'
                        THEN '漏判'
                        WHEN TRIM(COALESCE(raw_judgement, '')) IN ('', '正常', '通过', 'pass')
                        THEN '漏判'
                        ELSE '错判'
                    END AS error_type
                FROM fact_qa_event
                WHERE is_raw_correct = 0
                LIMIT 500
            """)
        except Exception:
            pass
    
    # 最终后备：从 mart 错误主题表获取
    if error_type_df.empty or error_type_df["error_type"].dropna().empty:
        try:
            error_type_df = repo.fetch_df("""
                SELECT DISTINCT NULLIF(TRIM(error_type), '') AS error_type
                FROM mart_day_error_topic
                WHERE error_type IS NOT NULL AND TRIM(error_type) != ''
                ORDER BY error_type
                LIMIT 500
            """)
        except Exception:
            pass
    
    # 查询2: 日期范围（聚合查询，极快）
    date_row = repo.fetch_one("SELECT MIN(biz_date) AS min_d, MAX(biz_date) AS max_d FROM fact_qa_event")
    
    if dims.empty:
        return {
            "groups": [],
            "queues": pd.DataFrame(columns=["group_name", "queue_name"]),
            "reviewers": [],
            "error_types": [],
            "min_date": date.today(),
            "max_date": date.today(),
        }

    groups = sorted(dims["group_name"].dropna().unique().tolist())
    queues = dims[["group_name", "queue_name"]].dropna().drop_duplicates().sort_values(["group_name", "queue_name"])
    reviewers = sorted(dims["reviewer_name"].dropna().unique().tolist())
    error_types = sorted([e for e in error_type_df["error_type"].dropna().unique().tolist() if e.strip()]) if not error_type_df.empty else []

    min_d = date_row.get("min_d") if date_row else None
    max_d = date_row.get("max_d") if date_row else None
    if hasattr(min_d, "date"):
        min_d = min_d.date()
    if hasattr(max_d, "date"):
        max_d = max_d.date()

    return {
        "groups": groups,
        "queues": queues,
        "reviewers": reviewers,
        "error_types": error_types,
        "min_date": min_d or date.today(),
        "max_date": max_d or date.today(),
    }


@st.cache_data(show_spinner="正在查询明细数据...")
def query_detail(
    date_start: date,
    date_end: date,
    group_name: str | None,
    queue_name: str | None,
    reviewer_name: str | None,
    error_type: str | None,
    only_issues: bool,
    issue_filter: str,
    limit: int = 2000,
) -> pd.DataFrame:
    conditions = ["biz_date >= %s", "biz_date <= %s"]
    params: list = [date_start, date_end]

    if group_name:
        conditions.append("group_name = %s")
        params.append(group_name)
    if queue_name:
        conditions.append("queue_name = %s")
        params.append(queue_name)
    if reviewer_name:
        conditions.append("reviewer_name = %s")
        params.append(reviewer_name)
    if error_type:
        conditions.append("error_type = %s")
        params.append(error_type)

    if only_issues:
        if issue_filter == "原始错误":
            conditions.append("NOT is_raw_correct")
        elif issue_filter == "最终错误":
            conditions.append("NOT is_final_correct")
        elif issue_filter == "错判":
            conditions.append("is_misjudge")
        elif issue_filter == "漏判":
            conditions.append("is_missjudge")
        elif issue_filter == "申诉改判":
            conditions.append("is_appeal_reversed")

    where = " AND ".join(conditions)
    sql = f"""
    SELECT
        biz_date AS 业务日期,
        COALESCE(group_name, '—') AS 组别,
        COALESCE(queue_name, '—') AS 队列,
        COALESCE(reviewer_name, '—') AS 审核人,
        COALESCE(content_type, '—') AS 内容类型,
        raw_judgement AS 一审结果,
        final_review_result AS 最终结果,
        appeal_status AS 申诉状态,
        appeal_result AS 申诉结果,
        CASE WHEN is_raw_correct = 1 THEN '正确' ELSE '错误' END AS 原始判断,
        CASE WHEN is_final_correct = 1 THEN '正确' ELSE '错误' END AS 最终判断,
        CASE WHEN is_misjudge = 1 THEN '是' ELSE '否' END AS 错判,
        CASE WHEN is_missjudge = 1 THEN '是' ELSE '否' END AS 漏判,
        CASE WHEN is_appeal_reversed = 1 THEN '是' ELSE '否' END AS 申诉改判,
        COALESCE(error_type, '—') AS 错误类型,
        COALESCE(error_reason, '—') AS 错误归因,
        comment_text AS 评论文本,
        COALESCE(qa_note, '—') AS 备注,
        join_key AS 关联主键,
        qa_time AS 质检时间
    FROM vw_qa_base
    WHERE {where}
    ORDER BY qa_time IS NULL, qa_time DESC, biz_date DESC
    LIMIT %s
    """
    params.append(int(limit))
    return repo.fetch_df(sql, params)


# to_csv_bytes 已统一到 utils/helpers.py
from utils.helpers import to_csv_bytes


opts = {}
try:
    opts = get_filter_options()
except Exception as _init_err:
    st.error(f"🚨 数据库连接异常：`{_init_err}`")
    if st.button("🔄 重试（硬刷新）", key="retry_detail"):
        from utils.error_boundary import hard_reset
        hard_reset()
        st.rerun()
    st.stop()

# Hero 区域
with st.container(border=True):
    st.markdown("### 🎯 筛选条件")
    st.caption("💡 提示：选择组别后会自动过滤队列列表，缩小查询范围可提高查询速度")
    
    # ---- 快速时间范围 ----
    quick_cols = st.columns(6)
    quick_ranges = {
        "今天": 0, "近3天": 2, "近7天": 6, "近14天": 13, "近30天": 29, "全部": None
    }
    for i, (label, days) in enumerate(quick_ranges.items()):
        with quick_cols[i]:
            if st.button(label, key=f"quick_{label}", use_container_width=True):
                if days is not None:
                    st.session_state["detail_quick_start"] = opts["max_date"] - timedelta(days=days)
                else:
                    st.session_state["detail_quick_start"] = opts["min_date"]
                st.session_state["detail_quick_end"] = opts["max_date"]
                st.rerun()

    c1, c2, c3 = st.columns(3)
    with c1:
        # 默认查最近7天，减少首次加载时间
        default_start = st.session_state.get("detail_quick_start", max(opts["min_date"], opts["max_date"] - timedelta(days=6)))
        date_start = st.date_input("起始日期", value=default_start, key="detail_start")
    with c2:
        default_end = st.session_state.get("detail_quick_end", opts["max_date"])
        date_end = st.date_input("截止日期", value=default_end, key="detail_end")
    with c3:
        # 接收从总览页跳转过来的预设组别
        _preset_group = st.session_state.pop("detail_group_preset", None)
        _group_options = ["(全部)"] + opts["groups"]
        _default_group_idx = 0
        if _preset_group and _preset_group in opts["groups"]:
            _default_group_idx = _group_options.index(_preset_group)
        group_sel = st.selectbox("组别", options=_group_options, index=_default_group_idx, key="detail_group")

    c4, c5, c6 = st.columns(3)
    queue_options = []
    if group_sel != "(全部)" and not opts["queues"].empty:
        queue_options = opts["queues"][opts["queues"]["group_name"] == group_sel]["queue_name"].tolist()
    with c4:
        # 接收预设队列
        _preset_queue = st.session_state.pop("detail_queue_preset", None)
        _queue_options = ["(全部)"] + queue_options
        _default_queue_idx = 0
        if _preset_queue and _preset_queue in queue_options:
            _default_queue_idx = _queue_options.index(_preset_queue)
        queue_sel = st.selectbox("队列", options=_queue_options, index=_default_queue_idx, key="detail_queue")
    with c5:
        # 接收预设审核人
        _preset_reviewer = st.session_state.pop("detail_reviewer_preset", None)
        _reviewer_options = ["(全部)"] + opts["reviewers"]
        _default_reviewer_idx = 0
        if _preset_reviewer and _preset_reviewer in opts["reviewers"]:
            _default_reviewer_idx = _reviewer_options.index(_preset_reviewer)
        reviewer_sel = st.selectbox("审核人", options=_reviewer_options, index=_default_reviewer_idx, key="detail_reviewer")
    with c6:
        error_sel = st.selectbox("错误类型", options=["(全部)"] + opts["error_types"], key="detail_error")

    c7, c8, c9 = st.columns([1, 2, 1])
    with c7:
        only_issues = st.checkbox("只看问题样本", value=False, key="detail_only_issues", help="勾选后仅显示有问题的样本")
    with c8:
        issue_filter = st.selectbox(
            "问题类型",
            options=["全部问题", "原始错误", "最终错误", "错判", "漏判", "申诉改判"],
            disabled=not only_issues,
            key="detail_issue_filter",
        )
    with c9:
        limit_options = {
            "2000条（默认）": 2000,
            "5000条": 5000,
            "10000条": 10000,
            "50000条": 50000,
        }
        limit_sel = st.selectbox(
            "显示条数",
            options=list(limit_options.keys()),
            index=0,
            key="detail_limit",
            help="选择显示的数据条数限制，过多数据可能影响性能",
        )
        query_limit = limit_options[limit_sel]

group_val = group_sel if group_sel != "(全部)" else None
queue_val = queue_sel if queue_sel != "(全部)" else None
reviewer_val = reviewer_sel if reviewer_sel != "(全部)" else None
error_val = error_sel if error_sel != "(全部)" else None
issue_mode = issue_filter if only_issues and issue_filter != "全部问题" else None

# 查询按钮 —— 点击后才触发数据查询，避免页面打开时自动加载全量数据
# 如果从总览页带着筛选条件跳转过来，自动触发查询
_has_preset = _default_group_idx > 0 or _default_queue_idx > 0 or _default_reviewer_idx > 0
query_btn_col1, query_btn_col2, query_btn_col3 = st.columns([1, 2, 1])
with query_btn_col1:
    do_query = st.button("🔍 开始查询", type="primary", use_container_width=True)
with query_btn_col2:
    if _has_preset:
        st.caption("✅ 已从总览页带入筛选条件，自动查询中...")
    else:
        st.caption("💡 设定好筛选条件后，点击「开始查询」按钮加载数据")
with query_btn_col3:
    if st.button("🗑️ 重置条件", use_container_width=True, help="清除所有筛选条件和查询状态"):
        for k in list(st.session_state.keys()):
            if k.startswith("detail_"):
                del st.session_state[k]
        st.rerun()

# 使用 session_state 记住是否已执行查询
if do_query or _has_preset:
    st.session_state["detail_queried"] = True

if not st.session_state.get("detail_queried", False):
    st.info("👆 请设定筛选条件后，点击「🔍 开始查询」按钮查看数据。")
    st.stop()

df = query_detail(date_start, date_end, group_val, queue_val, reviewer_val, error_val, only_issues, issue_filter if issue_filter != "全部问题" else "", query_limit)

if df.empty:
    st.info("当前筛选条件下没有数据。试试放宽筛选条件。")
else:
    # 结果统计（设计系统 v3.0）
    ds.divider()
    ds.section("📊 查询结果")
    
    # 统计概览卡片
    s1, s2, s3, s4, s5 = st.columns(5)
    total = len(df)
    raw_err = (df["原始判断"] == "错误").sum()
    final_err = (df["最终判断"] == "错误").sum()
    mis = (df["错判"] == "是").sum()
    miss = (df["漏判"] == "是").sum()
    
    with s1:
        ds.metric_card("总记录", f"{total:,}", icon="📋", border_color=COLORS.primary)
    with s2:
        ds.metric_card("原始错误", f"{raw_err:,}", delta=f"{raw_err/total*100:.1f}%", icon="✗", color=COLORS.danger, border_color=COLORS.danger)
    with s3:
        ds.metric_card("最终错误", f"{final_err:,}", delta=f"{final_err/total*100:.1f}%", icon="✗✗", color=COLORS.danger, border_color=COLORS.danger)
    with s4:
        ds.metric_card("错判", f"{mis:,}", icon="⚠️", color=COLORS.warning, border_color=COLORS.warning)
    with s5:
        ds.metric_card("漏判", f"{miss:,}", icon="🔍", color=COLORS.success, border_color=COLORS.success)
    
    # 导出按钮（优化样式）
    csv_data = to_csv_bytes(df)
    st.markdown("")  # 添加间距
    st.download_button(
        "📥 导出当前筛选结果 CSV",
        data=csv_data,
        file_name=f"qa_detail_{date_start}_{date_end}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # ---- 数据洞察 ----
    with st.expander("💡 数据洞察", expanded=True):
        insights = []
        # 洞察1: 正确率
        raw_acc = (total - raw_err) / total * 100 if total > 0 else 0
        if raw_acc < 95:
            insights.append(f"⚠️ 原始正确率 **{raw_acc:.2f}%**，低于95%基准线，需重点关注")
        elif raw_acc < 99:
            insights.append(f"📊 原始正确率 **{raw_acc:.2f}%**，接近目标但仍有优化空间")
        else:
            insights.append(f"✅ 原始正确率 **{raw_acc:.2f}%**，表现优秀")

        # 洞察2: 集中度分析
        if raw_err > 0 and "审核人" in df.columns:
            err_df = df[df["原始判断"] == "错误"]
            top_reviewer = err_df["审核人"].value_counts()
            if len(top_reviewer) > 0:
                top_name = top_reviewer.index[0]
                top_cnt = top_reviewer.iloc[0]
                top_pct = top_cnt / raw_err * 100
                if top_pct > 30:
                    insights.append(f"🎯 错误集中度高：**{top_name}** 贡献了 {top_pct:.1f}% 的原始错误（{top_cnt}条），建议专项关注")

        # 洞察3: 错误类型集中
        if raw_err > 0 and "错误类型" in df.columns:
            err_types = df[df["错误类型"] != "—"]["错误类型"].value_counts()
            if len(err_types) > 0:
                top_type = err_types.index[0]
                type_cnt = err_types.iloc[0]
                type_pct = type_cnt / raw_err * 100
                if type_pct > 25:
                    insights.append(f"🏷️ 高频错误类型：**{top_type}** 占比 {type_pct:.1f}%（{type_cnt}条），可考虑专题培训")

        # 洞察4: 申诉改判率
        appeal_cnt = (df["申诉改判"] == "是").sum() if "申诉改判" in df.columns else 0
        if appeal_cnt > 0:
            appeal_rate = appeal_cnt / total * 100
            if appeal_rate > 1:
                insights.append(f"📝 申诉改判率 **{appeal_rate:.2f}%**（{appeal_cnt}条），一审与终审口径可能存在偏差")

        for insight in insights:
            st.markdown(insight)

    # 错误类型分布（如果有问题样本）
    if only_issues or raw_err > 0:
        with st.expander("📊 错误类型分布", expanded=False):
            err_dist = df[df["错误类型"] != "—"]["错误类型"].value_counts().reset_index()
            err_dist.columns = ["错误类型", "数量"]
            st.dataframe(err_dist, use_container_width=True, hide_index=True)

    # 审核人维度快速统计
    if "审核人" in df.columns and total > 0:
        with st.expander("👤 审核人维度统计", expanded=False):
            reviewer_stats = df.groupby("审核人").agg(
                总量=("审核人", "count"),
            ).reset_index()
            if "原始判断" in df.columns:
                err_by_reviewer = df[df["原始判断"] == "错误"].groupby("审核人").size().reset_index(name="错误量")
                reviewer_stats = reviewer_stats.merge(err_by_reviewer, on="审核人", how="left")
                reviewer_stats["错误量"] = reviewer_stats["错误量"].fillna(0).astype(int)
                reviewer_stats["正确率"] = ((reviewer_stats["总量"] - reviewer_stats["错误量"]) / reviewer_stats["总量"] * 100).round(2)
                reviewer_stats = reviewer_stats.sort_values("正确率", ascending=True)
                reviewer_stats["正确率"] = reviewer_stats["正确率"].apply(lambda x: f"{x:.2f}%")
            reviewer_stats["总量"] = reviewer_stats["总量"].apply(lambda x: f"{x:,}")
            if "错误量" in reviewer_stats.columns:
                reviewer_stats["错误量"] = reviewer_stats["错误量"].apply(lambda x: f"{x:,}")
            st.caption(f"共 {len(reviewer_stats)} 位审核人")
            st.dataframe(reviewer_stats, use_container_width=True, hide_index=True, height=300)

    # 队列维度快速统计
    if "队列" in df.columns and total > 0:
        with st.expander("📋 队列维度统计", expanded=False):
            queue_stats = df.groupby("队列").agg(
                总量=("队列", "count"),
            ).reset_index()
            if "原始判断" in df.columns:
                err_by_queue = df[df["原始判断"] == "错误"].groupby("队列").size().reset_index(name="错误量")
                queue_stats = queue_stats.merge(err_by_queue, on="队列", how="left")
                queue_stats["错误量"] = queue_stats["错误量"].fillna(0).astype(int)
                queue_stats["正确率"] = ((queue_stats["总量"] - queue_stats["错误量"]) / queue_stats["总量"] * 100).round(2)
                queue_stats = queue_stats.sort_values("正确率", ascending=True)
                queue_stats["正确率"] = queue_stats["正确率"].apply(lambda x: f"{x:.2f}%")
            queue_stats["总量"] = queue_stats["总量"].apply(lambda x: f"{x:,}")
            if "错误量" in queue_stats.columns:
                queue_stats["错误量"] = queue_stats["错误量"].apply(lambda x: f"{x:,}")
            st.caption(f"共 {len(queue_stats)} 个队列")
            st.dataframe(queue_stats, use_container_width=True, hide_index=True, height=300)

    # 明细表格（分页展示）
    st.markdown("#### 📋 明细数据")
    
    PAGE_SIZE = 50
    total_rows = len(df)
    total_pages = max(1, (total_rows + PAGE_SIZE - 1) // PAGE_SIZE)
    
    # 分页控制
    if "detail_page" not in st.session_state:
        st.session_state["detail_page"] = 1
    
    # 确保页码有效
    current_page = min(st.session_state["detail_page"], total_pages)
    
    page_col1, page_col2, page_col3, page_col4, page_col5, page_col6 = st.columns([0.8, 0.8, 1.5, 0.8, 0.8, 1.2])
    with page_col1:
        if st.button("⏮ 首页", key="page_first", use_container_width=True, disabled=(current_page <= 1)):
            st.session_state["detail_page"] = 1
            st.rerun()
    with page_col2:
        if st.button("◀ 上页", key="page_prev", use_container_width=True, disabled=(current_page <= 1)):
            st.session_state["detail_page"] = current_page - 1
            st.rerun()
    with page_col3:
        st.markdown(f"<div style='text-align:center; padding:0.5rem; font-weight:600;'>第 {current_page} / {total_pages} 页 · 共 {total_rows:,} 条</div>", unsafe_allow_html=True)
    with page_col4:
        if st.button("下页 ▶", key="page_next", use_container_width=True, disabled=(current_page >= total_pages)):
            st.session_state["detail_page"] = current_page + 1
            st.rerun()
    with page_col5:
        if st.button("末页 ⏭", key="page_last", use_container_width=True, disabled=(current_page >= total_pages)):
            st.session_state["detail_page"] = total_pages
            st.rerun()
    with page_col6:
        jump_page = st.number_input("跳转到", min_value=1, max_value=total_pages, value=current_page, step=1, key="jump_page", label_visibility="collapsed")
        if jump_page != current_page:
            st.session_state["detail_page"] = jump_page
            st.rerun()
    
    # 分页展示数据
    start_idx = (current_page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_rows)
    page_df = df.iloc[start_idx:end_idx]
    
    st.caption(f"📄 当前显示第 {start_idx + 1} ~ {end_idx} 条")
    st.dataframe(page_df, use_container_width=True, hide_index=True, height=500)