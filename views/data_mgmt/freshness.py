"""数据管理页 - 数据新鲜度面板。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from views.data_mgmt._shared import repo


def render_freshness_panel() -> None:
    """渲染数据新鲜度面板。"""
    freshness_sql = """
    SELECT '质检事实表' AS table_cn, 'fact_qa_event' AS tbl,
           COUNT(*) AS row_cnt, MAX(biz_date) AS latest_date
    FROM fact_qa_event
    UNION ALL
    SELECT '申诉事实表', 'fact_appeal_event', COUNT(*), MAX(biz_date)
    FROM fact_appeal_event
    UNION ALL
    SELECT '新人质检表', 'fact_newcomer_qa', COUNT(*), MAX(biz_date)
    FROM fact_newcomer_qa
    UNION ALL
    SELECT '新人名单表', 'dim_newcomer_batch', COUNT(*), NULL
    FROM dim_newcomer_batch
    UNION ALL
    SELECT '日聚合-组', 'mart_day_group', COUNT(*), MAX(biz_date)
    FROM mart_day_group
    UNION ALL
    SELECT '日聚合-队列', 'mart_day_queue', COUNT(*), MAX(biz_date)
    FROM mart_day_queue
    """
    try:
        freshness_df = repo.fetch_df(freshness_sql)
        if not freshness_df.empty:
            show_fresh = pd.DataFrame()
            show_fresh["数据表"] = freshness_df["table_cn"]
            show_fresh["记录数"] = freshness_df["row_cnt"].apply(
                lambda x: f"{int(x):,}" if pd.notna(x) else "0"
            )
            show_fresh["最新日期"] = freshness_df["latest_date"].apply(
                lambda x: str(x)[:10] if pd.notna(x) else "—"
            )
            today = date.today()

            def freshness_badge(d):
                if pd.isna(d) or str(d) == "—":
                    return "—"
                try:
                    d_date = pd.to_datetime(d).date()
                    gap = (today - d_date).days
                    if gap <= 1:
                        return "🟢 当日"
                    elif gap <= 3:
                        return "🟡 近3天"
                    elif gap <= 7:
                        return "🟠 近1周"
                    else:
                        return f"🔴 {gap}天前"
                except Exception:
                    return "—"

            show_fresh["新鲜度"] = freshness_df["latest_date"].apply(freshness_badge)
            st.dataframe(show_fresh, use_container_width=True, hide_index=True)
        else:
            st.info("暂无数据表信息")
    except Exception as e:
        st.warning(f"获取新鲜度信息失败: {e}")
