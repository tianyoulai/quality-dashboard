"""总览页 - 数据加载层。

所有 @st.cache_data 函数集中管理，避免分散在视图中。
数据追踪链路：_data.py → ctx dict → 各视图组件。
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from services.dashboard_service import DashboardService
from storage.repository import DashboardRepository

service = DashboardService()
repo = DashboardRepository()


@st.cache_data(show_spinner="正在加载日期范围...", ttl=300)
def get_data_date_range() -> tuple[date, date]:
    """获取数据库中的日期范围, 用于设置默认日期。"""
    row = repo.fetch_one(
        "SELECT MIN(biz_date) AS min_d, MAX(biz_date) AS max_d FROM fact_qa_event"
    )
    if not row or row.get("min_d") is None:
        return date.today(), date.today()
    min_val = row["min_d"]
    max_val = row["max_d"]
    if hasattr(min_val, "date"):
        min_val = min_val.date()
    if hasattr(max_val, "date"):
        max_val = max_val.date()
    return min_val, max_val


@st.cache_data(show_spinner="正在加载看板数据...", ttl=300)
def load_dashboard_lite(grain: str, selected_date: date) -> dict:
    """轻量首屏加载：只查 group_df + alerts_df（2次DB查询）。
    
    相比 load_group_overview 减少 5 次 DB 查询，首屏渲染从 ~4s 降到 ~1s。
    """
    return service.load_dashboard_lite(grain, selected_date)


@st.cache_data(show_spinner="正在加载环比数据...", ttl=300)
def load_prev_group_df(grain: str, prev_date: date) -> pd.DataFrame:
    """环比专用：只加载上期 group_df（1次DB查询）。
    
    旧逻辑调用 load_group_overview 获取完整 payload 再取 group_df，
    浪费 6 次 DB 查询。
    """
    anchor = service.normalize_anchor_date(grain, prev_date)
    return repo.fetch_df(
        f"""
        SELECT * FROM {_summary_table(grain)}
        WHERE {_anchor_col(grain)} = %s
        ORDER BY final_accuracy_rate ASC, qa_cnt DESC
        """,
        [anchor],
    )


def _summary_table(grain: str) -> str:
    return {"day": "mart_day_group", "week": "mart_week_group", "month": "mart_month_group"}[grain]

def _anchor_col(grain: str) -> str:
    return {"day": "biz_date", "week": "week_begin_date", "month": "month_begin_date"}[grain]


@st.cache_data(show_spinner="正在加载组别数据...", ttl=300)
def load_group_overview(grain: str, selected_date: date) -> dict:
    return service.load_dashboard_payload(grain, selected_date)


@st.cache_data(show_spinner="正在加载组别详情...", ttl=300)
def load_group_detail(
    grain: str,
    selected_date: date,
    group_name: str,
    queue_name: str | None,
    reviewer_name: str | None,
    focus_rule_code: str | None,
    focus_error_type: str | None,
) -> dict:
    return service.load_group_payload(
        grain, selected_date, group_name,
        queue_name, reviewer_name,
        focus_rule_code, focus_error_type,
    )


@st.cache_data(show_spinner="正在加载队列数据...", ttl=300)
def load_queue_overview_data(
    grain: str,
    start_date: date,
    end_date: date,
    group_name: str | None = None,
) -> dict:
    """加载队列概览数据。"""
    if grain == "day":
        time_filter = "biz_date BETWEEN %s AND %s"
        anchor_col = "biz_date"
    elif grain == "week":
        time_filter = "week_begin_date BETWEEN %s AND %s"
        anchor_col = "week_begin_date"
    else:
        time_filter = "month_begin_date BETWEEN %s AND %s"
        anchor_col = "month_begin_date"

    if grain == "day":
        queue_table = "mart_day_queue"
        group_table = "mart_day_group"
    elif grain == "week":
        queue_table = "mart_week_queue"
        group_table = "mart_week_group"
    else:
        queue_table = "mart_month_queue"
        group_table = "mart_month_group"

    # 队列数据
    queue_sql = f"""
    SELECT
        group_name, queue_name,
        SUM(qa_cnt) AS total_qa_cnt,
        ROUND(SUM(raw_correct_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS raw_accuracy_rate,
        ROUND(SUM(final_correct_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS final_accuracy_rate,
        ROUND(SUM(misjudge_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS misjudge_rate,
        ROUND(SUM(missjudge_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS missjudge_rate
    FROM {queue_table}
    WHERE {time_filter}
    """
    params = [start_date, end_date]
    if group_name:
        if group_name == "B组":
            queue_sql += " AND group_name LIKE %s"
            params.append("B组%")
        else:
            queue_sql += " AND group_name = %s"
            params.append(group_name)
    queue_sql += " GROUP BY group_name, queue_name ORDER BY total_qa_cnt DESC"
    queue_df = repo.fetch_df(queue_sql, params)

    # 趋势数据
    trend_sql = f"""
    SELECT
        {anchor_col} AS anchor_date,
        SUM(qa_cnt) AS total_qa_cnt,
        ROUND(SUM(raw_correct_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS raw_accuracy_rate,
        ROUND(SUM(final_correct_cnt) * 100.0 / NULLIF(SUM(qa_cnt), 0), 2) AS final_accuracy_rate
    FROM {group_table}
    WHERE {time_filter}
    """
    params_trend = [start_date, end_date]
    if group_name:
        if group_name == "B组":
            trend_sql += " AND group_name LIKE %s"
            params_trend.append("B组%")
        else:
            trend_sql += " AND group_name = %s"
            params_trend.append(group_name)
    trend_sql += f" GROUP BY {anchor_col} ORDER BY {anchor_col}"
    trend_df = repo.fetch_df(trend_sql, params_trend)

    return {"queue_df": queue_df, "trend_df": trend_df}


@st.cache_data(show_spinner=False, ttl=300)
def load_alert_history(alert_id: str | None) -> pd.DataFrame:
    if not alert_id:
        return pd.DataFrame()
    return service.load_alert_history(alert_id)


@st.cache_data(show_spinner=False, ttl=300)
def load_qa_label_distribution_cached(
    grain: str, selected_date: date,
    group_name: str | None = None, top_n: int = 10,
) -> pd.DataFrame:
    return service.load_qa_label_distribution(grain, selected_date, group_name, top_n)


@st.cache_data(show_spinner=False, ttl=300)
def load_qa_owner_distribution_cached(
    grain: str, selected_date: date,
    group_name: str | None = None, top_n: int = 10,
) -> pd.DataFrame:
    return service.load_qa_owner_distribution(grain, selected_date, group_name, top_n)
