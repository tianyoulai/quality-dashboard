"""导出中心 -- 一键导出 Excel/CSV 格式的日报、周报、月报。"""
from __future__ import annotations

import io
from datetime import date, timedelta
from typing import Any

import pandas as pd


def _safe_int(v) -> int:
    try:
        return int(v) if v is not None else 0
    except (ValueError, TypeError):
        return 0


def _safe_float(v, d: int = 2) -> float:
    try:
        return round(float(v), d) if v is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


def export_daily_excel(report_data: dict, report_date: date) -> bytes:
    """导出日报数据为 Excel bytes。

    report_data 来自 DashboardService.load_dashboard_payload()
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet1: 组别概览
        group_df = report_data.get("group_df", pd.DataFrame())
        if not group_df.empty:
            group_show = pd.DataFrame()
            group_show["组别"] = group_df["group_name"]
            group_show["质检量"] = group_df["qa_cnt"]
            group_show["原始正确率"] = group_df["raw_accuracy_rate"].apply(lambda x: f"{x:.2f}%")
            group_show["最终正确率"] = group_df["final_accuracy_rate"].apply(lambda x: f"{x:.2f}%")
            if "raw_error_cnt" in group_df.columns:
                group_show["原始错误量"] = group_df["raw_error_cnt"]
            if "misjudge_rate" in group_df.columns:
                group_show["错判率"] = group_df["misjudge_rate"].apply(lambda x: f"{x:.2f}%")
            if "missjudge_rate" in group_df.columns:
                group_show["漏判率"] = group_df["missjudge_rate"].apply(lambda x: f"{x:.2f}%")
            group_show.to_excel(writer, sheet_name="组别概览", index=False)

        # Sheet2: 队列明细
        queue_df = report_data.get("queue_df", pd.DataFrame())
        if not queue_df.empty:
            queue_df.to_excel(writer, sheet_name="队列明细", index=False)

        # Sheet3: 审核人明细
        auditor_df = report_data.get("auditor_df", pd.DataFrame())
        if not auditor_df.empty:
            auditor_df.to_excel(writer, sheet_name="审核人明细", index=False)

        # Sheet4: 告警
        alerts_df = report_data.get("alerts_df", pd.DataFrame())
        if not alerts_df.empty:
            alert_cols = ["severity", "rule_name", "target_key", "metric_value",
                          "threshold_value", "alert_status", "owner_name", "alert_date"]
            avail = [c for c in alert_cols if c in alerts_df.columns]
            alerts_df[avail].to_excel(writer, sheet_name="告警列表", index=False)

    return output.getvalue()


def export_weekly_excel(
    daily_payloads: list[dict],
    week_start: date,
    week_end: date,
) -> bytes:
    """导出周报数据为 Excel bytes。

    daily_payloads: 本周每日的 load_dashboard_payload() 结果列表
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet1: 每日汇总
        rows = []
        for p in daily_payloads:
            gdf = p.get("group_df", pd.DataFrame())
            d = p.get("anchor_date", "")
            total_qa = gdf["qa_cnt"].sum() if not gdf.empty else 0
            if total_qa > 0:
                raw_acc = (gdf["raw_accuracy_rate"] * gdf["qa_cnt"]).sum() / total_qa
                final_acc = (gdf["final_accuracy_rate"] * gdf["qa_cnt"]).sum() / total_qa
            else:
                raw_acc = 0
                final_acc = 0
            rows.append({
                "日期": str(d),
                "质检量": int(total_qa),
                "原始正确率": f"{raw_acc:.2f}%",
                "最终正确率": f"{final_acc:.2f}%",
            })
        if rows:
            pd.DataFrame(rows).to_excel(writer, sheet_name="每日汇总", index=False)

        # Sheet2: 组别周汇总
        all_groups = pd.concat(
            [p.get("group_df", pd.DataFrame()) for p in daily_payloads],
            ignore_index=True,
        )
        if not all_groups.empty and "group_name" in all_groups.columns:
            week_group = all_groups.groupby("group_name").agg(
                总质检量=("qa_cnt", "sum"),
            ).reset_index()
            if "raw_correct_cnt" in all_groups.columns:
                correct_sum = all_groups.groupby("group_name")["raw_correct_cnt"].sum().reset_index()
                week_group = week_group.merge(correct_sum, on="group_name", how="left")
                week_group["原始正确率"] = (week_group["raw_correct_cnt"] / week_group["总质检量"] * 100).round(2).astype(str) + "%"
            week_group.rename(columns={"group_name": "组别"}).to_excel(
                writer, sheet_name="组别周汇总", index=False
            )

    return output.getvalue()
