"""数据管理页 - 数据健康检查面板。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from views.data_mgmt._shared import repo


def render_health_check() -> None:
    """渲染数据健康检查面板。"""
    if not st.button("🔍 执行数据健康检查", use_container_width=True, key="health_check"):
        return

    with st.spinner("正在检查..."):
        checks = []

        # 1. fact_qa_event 总量
        total_row = repo.fetch_one("SELECT COUNT(*) AS cnt FROM fact_qa_event")
        total_cnt = total_row["cnt"] if total_row else 0
        checks.append(("fact_qa_event 总记录数", f"{total_cnt:,}", "✅" if total_cnt > 0 else "⚠️ 无数据"))

        # 2. 关键字段缺失率
        null_checks = [
            ("group_name 为空", "SELECT COUNT(*) AS cnt FROM fact_qa_event WHERE group_name IS NULL OR TRIM(group_name) = ''"),
            ("queue_name 为空", "SELECT COUNT(*) AS cnt FROM fact_qa_event WHERE queue_name IS NULL OR TRIM(queue_name) = ''"),
            ("reviewer_name 为空", "SELECT COUNT(*) AS cnt FROM fact_qa_event WHERE reviewer_name IS NULL OR TRIM(reviewer_name) = ''"),
            ("biz_date 为空", "SELECT COUNT(*) AS cnt FROM fact_qa_event WHERE biz_date IS NULL"),
        ]
        for label, sql in null_checks:
            r = repo.fetch_one(sql)
            cnt = r["cnt"] if r else 0
            pct = cnt / total_cnt * 100 if total_cnt > 0 else 0
            status = "✅" if pct < 1 else ("⚠️" if pct < 10 else "❌")
            checks.append((label, f"{cnt:,} ({pct:.1f}%)", status))

        # 3. mart 表是否有数据
        mart_tables = ["mart_day_group", "mart_day_queue", "mart_day_auditor", "mart_week_group", "mart_month_group"]
        for tbl in mart_tables:
            try:
                r = repo.fetch_one(f"SELECT COUNT(*) AS cnt FROM {tbl}")
                cnt = r["cnt"] if r else 0
                checks.append((f"{tbl} 记录数", f"{cnt:,}", "✅" if cnt > 0 else "⚠️ 需刷新数仓"))
            except Exception:
                checks.append((f"{tbl} 记录数", "表不存在", "❌"))

        # 4. 日期连续性检查
        date_gaps = repo.fetch_df("""
            SELECT a.d AS gap_date FROM (
                SELECT DATE_ADD(MIN(biz_date), INTERVAL seq DAY) AS d
                FROM fact_qa_event,
                (SELECT 0 AS seq UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9
                 UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12 UNION ALL SELECT 13 UNION ALL SELECT 14) seqs
                WHERE DATE_ADD(MIN(biz_date), INTERVAL seq DAY) <= (SELECT MAX(biz_date) FROM fact_qa_event)
            ) a
            LEFT JOIN (SELECT DISTINCT biz_date FROM fact_qa_event) b ON a.d = b.biz_date
            WHERE b.biz_date IS NULL
            LIMIT 10
        """)
        gap_cnt = len(date_gaps) if date_gaps is not None else 0
        checks.append(("日期连续性（最近15天）", f"缺失 {gap_cnt} 天" if gap_cnt > 0 else "连续", "⚠️" if gap_cnt > 0 else "✅"))

        # 5. 新人数据检查
        newcomer_total = repo.fetch_one("SELECT COUNT(*) AS cnt FROM dim_newcomer_batch")
        newcomer_cnt = newcomer_total["cnt"] if newcomer_total else 0
        checks.append(("新人名单", f"{newcomer_cnt:,} 人", "✅" if newcomer_cnt > 0 else "💡 可选"))

        newcomer_qa = repo.fetch_one("SELECT COUNT(*) AS cnt FROM fact_newcomer_qa")
        newcomer_qa_cnt = newcomer_qa["cnt"] if newcomer_qa else 0
        checks.append(("新人质检", f"{newcomer_qa_cnt:,} 条", "✅" if newcomer_qa_cnt > 0 else "💡 可选"))

        # 展示结果
        health_df = pd.DataFrame(checks, columns=["检查项", "结果", "状态"])
        st.dataframe(health_df, use_container_width=True, hide_index=True, height=400)

        error_cnt = sum(1 for _, _, s in checks if "❌" in s)
        warn_cnt = sum(1 for _, _, s in checks if "⚠️" in s)
        if error_cnt > 0:
            st.error(f"发现 {error_cnt} 个严重问题，请尽快处理。")
        elif warn_cnt > 0:
            st.warning(f"发现 {warn_cnt} 个需注意的问题。")
        else:
            st.success("🎉 数据健康检查通过，所有指标正常！")
