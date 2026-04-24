"""明细查询页：灵活筛选 + 下钻 + CSV 导出。"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services.dashboard_service import DashboardService
from storage.repository import DashboardRepository

# 全局CSS + 明细查询页特有样式
from utils.styles import inject_global_css
inject_global_css()

st.markdown("""
<style>
    /* 明细查询特有：下载按钮样式 */
    .stDownloadButton > button {
        background: #2e7d32;
        color: white;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stDownloadButton > button:hover {
        background: #1b5e20;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(46, 125, 50, 0.3);
    }
</style>
""", unsafe_allow_html=True)

repo = DashboardRepository()
service = DashboardService()

# Hero 区域
st.markdown("""
<div style="margin-bottom: 1.5rem; padding: 1.5rem; background: #ffffff; border-radius: 1rem; border-left: 4px solid #2e7d32; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #1a1a1a;">🔍 明细查询</h1>
    </div>
    <div style="font-size: 0.9rem; color: #4b5563; line-height: 1.6;">
        多维度筛选 · 问题下钻 · 数据导出
    </div>
</div>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=600)
def get_filter_options() -> dict:
    """获取筛选选项（缓存 10 分钟）。
    
    优化：使用与 vw_qa_base 一致的 group_name 逻辑，
    但从 fact_qa_event 直表查询 DISTINCT 避免扫描全量视图。
    """
    groups = repo.fetch_df("""
        SELECT DISTINCT COALESCE(NULLIF(TRIM(group_name), ''), NULLIF(TRIM(mother_biz), ''), NULLIF(TRIM(sub_biz), '')) AS group_name 
        FROM fact_qa_event 
        WHERE COALESCE(NULLIF(TRIM(group_name), ''), NULLIF(TRIM(mother_biz), ''), NULLIF(TRIM(sub_biz), '')) IS NOT NULL 
        ORDER BY 1
    """)
    queues = repo.fetch_df("""
        SELECT DISTINCT 
            COALESCE(NULLIF(TRIM(group_name), ''), NULLIF(TRIM(mother_biz), ''), NULLIF(TRIM(sub_biz), '')) AS group_name, 
            COALESCE(NULLIF(TRIM(queue_name), ''), NULLIF(TRIM(sub_biz), '')) AS queue_name 
        FROM fact_qa_event 
        WHERE queue_name IS NOT NULL 
        ORDER BY 1, 2
    """)
    reviewers = repo.fetch_df("SELECT DISTINCT reviewer_name FROM fact_qa_event WHERE reviewer_name IS NOT NULL ORDER BY 1")
    error_types = repo.fetch_df("SELECT DISTINCT error_type FROM fact_qa_event WHERE error_type IS NOT NULL AND error_type <> '' ORDER BY 1")
    dates = repo.fetch_df("SELECT DISTINCT biz_date FROM fact_qa_event ORDER BY 1")
    return {
        "groups": groups["group_name"].tolist() if not groups.empty else [],
        "queues": queues if not queues.empty else pd.DataFrame(columns=["group_name", "queue_name"]),
        "reviewers": reviewers["reviewer_name"].tolist() if not reviewers.empty else [],
        "error_types": error_types["error_type"].tolist() if not error_types.empty else [],
        "min_date": dates["biz_date"].min() if not dates.empty else date.today(),
        "max_date": dates["biz_date"].max() if not dates.empty else date.today(),
    }


@st.cache_data(show_spinner=False)
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


opts = get_filter_options()

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
        group_sel = st.selectbox("组别", options=["(全部)"] + opts["groups"], key="detail_group")

    c4, c5, c6 = st.columns(3)
    queue_options = []
    if group_sel != "(全部)" and not opts["queues"].empty:
        queue_options = opts["queues"][opts["queues"]["group_name"] == group_sel]["queue_name"].tolist()
    with c4:
        queue_sel = st.selectbox("队列", options=["(全部)"] + queue_options, key="detail_queue")
    with c5:
        reviewer_sel = st.selectbox("审核人", options=["(全部)"] + opts["reviewers"], key="detail_reviewer")
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
query_btn_col1, query_btn_col2 = st.columns([1, 3])
with query_btn_col1:
    do_query = st.button("🔍 开始查询", type="primary", use_container_width=True)
with query_btn_col2:
    st.caption("💡 设定好筛选条件后，点击「开始查询」按钮加载数据")

# 使用 session_state 记住是否已执行查询
if do_query:
    st.session_state["detail_queried"] = True

if not st.session_state.get("detail_queried", False):
    st.info("👆 请设定筛选条件后，点击「🔍 开始查询」按钮查看数据。")
    st.stop()

df = query_detail(date_start, date_end, group_val, queue_val, reviewer_val, error_val, only_issues, issue_filter if issue_filter != "全部问题" else "", query_limit)

if df.empty:
    st.info("当前筛选条件下没有数据。试试放宽筛选条件。")
else:
    # 结果统计（优化样式）
    st.markdown("---")
    st.markdown("### 📊 查询结果")
    
    # 统计概览卡片
    s1, s2, s3, s4, s5 = st.columns(5)
    total = len(df)
    raw_err = (df["原始判断"] == "错误").sum()
    final_err = (df["最终判断"] == "错误").sum()
    mis = (df["错判"] == "是").sum()
    miss = (df["漏判"] == "是").sum()
    
    with s1:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); padding: 0.75rem; border-radius: 0.75rem; text-align: center; border: 2px solid #3B82F6;'>
                <div style='font-size: 0.75rem; color: #1E40AF; margin-bottom: 0.25rem;'>总记录</div>
                <div style='font-size: 1.5rem; font-weight: 700; color: #1E40AF;'>{total:,}</div>
            </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #FEF2F2 0%, #FEE2E2 100%); padding: 0.75rem; border-radius: 0.75rem; text-align: center; border: 2px solid #EF4444;'>
                <div style='font-size: 0.75rem; color: #991B1B; margin-bottom: 0.25rem;'>原始错误</div>
                <div style='font-size: 1.5rem; font-weight: 700; color: #EF4444;'>{raw_err:,}</div>
                <div style='font-size: 0.7rem; color: #991B1B;'>{raw_err/total*100:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #FEF2F2 0%, #FEE2E2 100%); padding: 0.75rem; border-radius: 0.75rem; text-align: center; border: 2px solid #DC2626;'>
                <div style='font-size: 0.75rem; color: #7F1D1D; margin-bottom: 0.25rem;'>最终错误</div>
                <div style='font-size: 1.5rem; font-weight: 700; color: #DC2626;'>{final_err:,}</div>
                <div style='font-size: 0.7rem; color: #7F1D1D;'>{final_err/total*100:.1f}%</div>
            </div>
        """, unsafe_allow_html=True)
    with s4:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%); padding: 0.75rem; border-radius: 0.75rem; text-align: center; border: 2px solid #F59E0B;'>
                <div style='font-size: 0.75rem; color: #92400E; margin-bottom: 0.25rem;'>错判</div>
                <div style='font-size: 1.5rem; font-weight: 700; color: #F59E0B;'>{mis:,}</div>
            </div>
        """, unsafe_allow_html=True)
    with s5:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%); padding: 0.75rem; border-radius: 0.75rem; text-align: center; border: 2px solid #10B981;'>
                <div style='font-size: 0.75rem; color: #047857; margin-bottom: 0.25rem;'>漏判</div>
                <div style='font-size: 1.5rem; font-weight: 700; color: #10B981;'>{miss:,}</div>
            </div>
        """, unsafe_allow_html=True)
    
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