"""reports -- 统一报告引擎（日报 / 周报 / 新人日报）。

对外暴露三个入口函数，供 jobs/*.py 和 Streamlit 页面调用：
    generate_daily_report(report_date) -> ReportResult
    generate_weekly_report(week_end_date) -> ReportResult
    generate_newcomer_report(report_date) -> ReportResult
"""
from __future__ import annotations

from .engine import ReportResult, generate_daily_report, generate_weekly_report, generate_newcomer_report

__all__ = [
    "ReportResult",
    "generate_daily_report",
    "generate_weekly_report",
    "generate_newcomer_report",
]
