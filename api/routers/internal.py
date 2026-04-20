"""Internal Inspection（内检看板）API 路由。

对标 pages/03_内检.py 的全部查询能力，按 qc_module='internal' 过滤，
为 Next.js 前端提供结构化 JSON 接口。

端点清单：
  GET /summary          — 当日核心指标卡 + 环比
  GET /queues           — 队列正确率排名
  GET /trend            — 日级正确率趋势
  GET /reviewers         — 审核人明细（含错判/漏判）
  GET /error-types       — 错误标签分布 TOP10
  GET /qa-owners         — 质检员工作量
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query
from pydantic import Field

from api.serializers import dataframe_to_records, normalize_payload
from storage.repository import DashboardRepository
from utils.constants import ACC_TARGET_INTERNAL, COLOR_INTERNAL

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])
repo = DashboardRepository()

MODULE = "internal"


# ══════════════════════════════════════════════════════════════
#  1. Summary — 核心指标卡（5 卡：总量/原始正确率/最终正确率/错误量/队列&质检员）
# ══════════════════════════════════════════════════════════════

@router.get("/summary")
def get_internal_summary(
    selected_date: date = Query(..., description="业务日期"),
    with_prev: bool = Query(default=False, description="是否返回前一天数据用于环比"),
) -> dict:
    """当日核心指标 + 可选前一天环比。"""
    row = repo.fetch_one(f"""
        SELECT COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS err,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_acc,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_acc,
               SUM(CASE WHEN is_misjudge=1 THEN 1 ELSE 0 END) AS mis_cnt,
               SUM(CASE WHEN is_missjudge=1 THEN 1 ELSE 0 END) AS miss_cnt,
               COUNT(DISTINCT queue_name) AS queue_cnt,
               COUNT(DISTINCT qa_owner_name) AS owner_cnt
        FROM fact_qa_event WHERE biz_date = %s AND qc_module = '{MODULE}'
    """, [selected_date])

    payload: dict = {
        "module": MODULE,
        "selected_date": selected_date.isoformat(),
        "target_rate": ACC_TARGET_INTERNAL,
        "color": COLOR_INTERNAL,
    }

    if row and row.get("qa_cnt", 0):
        payload["metrics"] = {
            "qa_cnt": int(row["qa_cnt"]),
            "raw_accuracy_rate": float(row["raw_acc"] or 0),
            "final_accuracy_rate": float(row["final_acc"] or 0),
            "error_count": int(row["err"] or 0),
            "queue_count": int(row["queue_cnt"] or 0),
            "owner_count": int(row["owner_cnt"] or 0),
            "misjudge_count": int(row["mis_cnt"] or 0),
            "missjudge_count": int(row["miss_cnt"] or 0),
        }
    else:
        payload["metrics"] = None
        return {"ok": True, "data": normalize_payload(payload)}

    # 环比
    if with_prev:
        prev_row = repo.fetch_one(f"""
            SELECT COUNT(*) AS qa_cnt,
                   ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_acc
            FROM fact_qa_event WHERE biz_date = %s AND qc_module = '{MODULE}'
        """, [selected_date - timedelta(days=1)])
        if prev_row:
            prev_qa = int(prev_row["qa_cnt"] or 0)
            prev_acc = float(prev_row["raw_acc"] or 0)
            cur_qa = payload["metrics"]["qa_cnt"]
            cur_acc = payload["metrics"]["raw_accuracy_rate"]
            payload["prev"] = {
                "qa_cnt": prev_qa,
                "raw_accuracy_rate": prev_acc,
                "qa_delta": cur_qa - prev_qa if prev_qa else None,
                "acc_delta_pp": round(cur_acc - prev_acc, 2) if prev_acc else None,
            }

    return {"ok": True, "data": normalize_payload(payload)}


# ══════════════════════════════════════════════════════════════
#  2. Queues — 队列正确率排名
# ══════════════════════════════════════════════════════════════

@router.get("/queues")
def get_internal_queues(
    selected_date: date = Query(..., description="业务日期"),
) -> dict:
    """队列维度聚合，按原始正确率升序排列（问题队列优先）。"""
    df = repo.fetch_df(f"""
        SELECT queue_name, COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS error_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_accuracy_rate,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_accuracy_rate
        FROM fact_qa_event WHERE biz_date = %s AND qc_module = '{MODULE}'
        GROUP BY queue_name ORDER BY raw_accuracy_rate ASC
    """, [selected_date])
    return {
        "ok": True,
        "data": normalize_payload({
            "items": dataframe_to_records(df),
            "total": len(df),
        }),
    }


# ══════════════════════════════════════════════════════════════
#  3. Trend — 日级正确率趋势
# ══════════════════════════════════════════════════════════════

@router.get("/trend")
def get_internal_trend(
    start_date: date = Query(..., description="趋势起始日期"),
    end_date: date = Query(..., description="趋势截止日期"),
) -> dict:
    """日级趋势线数据（原始正确率 + 最终正确率），前端渲染折线图。"""
    df = repo.fetch_df(f"""
        SELECT biz_date AS anchor_date, COUNT(*) AS qa_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_accuracy_rate,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_accuracy_rate
        FROM fact_qa_event WHERE biz_date BETWEEN %s AND %s AND qc_module = '{MODULE}'
        GROUP BY biz_date ORDER BY biz_date
    """, [start_date, end_date])
    return {
        "ok": True,
        "data": normalize_payload({
            "series": dataframe_to_records(df),
            "target_rate": ACC_TARGET_INTERNAL,
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        }),
    }


# ══════════════════════════════════════════════════════════════
#  4. Reviewers — 审核人分析（含错判/漏判）
# ══════════════════════════════════════════════════════════════

@router.get("/reviewers")
def get_internal_reviewers(
    selected_date: date = Query(..., description="业务日期"),
    limit: int = Query(default=30, ge=1, le=200, description="返回条数上限"),
) -> dict:
    """审核人（被检人）明细，含错判/漏判量，按正确率升序。"""
    df = repo.fetch_df(f"""
        SELECT reviewer_name, COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS error_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS raw_accuracy_rate,
               ROUND(SUM(CASE WHEN is_final_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS final_accuracy_rate,
               SUM(CASE WHEN is_misjudge=1 THEN 1 ELSE 0 END) AS misjudge_cnt,
               SUM(CASE WHEN is_missjudge=1 THEN 1 ELSE 0 END) AS missjudge_cnt
        FROM fact_qa_event
        WHERE biz_date = %s AND qc_module = '{MODULE}'
          AND reviewer_name IS NOT NULL AND reviewer_name != ''
        GROUP BY reviewer_name ORDER BY raw_accuracy_rate ASC LIMIT %s
    """, [selected_date, limit])
    return {
        "ok": True,
        "data": normalize_payload({
            "items": dataframe_to_records(df),
            "total": len(df),
        }),
    }


# ══════════════════════════════════════════════════════════════
#  5. Error Types — 出错类型分布 TOP10
# ══════════════════════════════════════════════════════════════

@router.get("/error-types")
def get_internal_error_types(
    selected_date: date = Query(..., description="业务日期"),
    top_n: int = Query(default=10, ge=1, le=50, description="TOP N"),
) -> dict:
    """错误标签分布，含占比%，供饼图+柱状图使用。"""
    df = repo.fetch_df(f"""
        SELECT COALESCE(NULLIF(TRIM(error_type),''), '无标签') AS label_name, COUNT(*) AS cnt
        FROM fact_qa_event
        WHERE biz_date = %s AND qc_module = '{MODULE}' AND is_raw_correct = 0
        GROUP BY label_name ORDER BY cnt DESC LIMIT %s
    """, [selected_date, top_n])

    total = int(df["cnt"].sum()) if not df.empty else 0
    if not df.empty:
        df["pct"] = (df["cnt"] / total * 100).round(1)

    return {
        "ok": True,
        "data": normalize_payload({
            "items": dataframe_to_records(df),
            "total_errors": total,
        }),
    }


# ══════════════════════════════════════════════════════════════
#  6. QA Owners — 质检员工作量
# ══════════════════════════════════════════════════════════════

@router.get("/qa-owners")
def get_internal_qa_owners(
    selected_date: date = Query(..., description="业务日期"),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """质检员工作量统计（执行质检的人）。"""
    df = repo.fetch_df(f"""
        SELECT qa_owner_name, COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct=0 THEN 1 ELSE 0 END) AS error_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS accuracy_rate
        FROM fact_qa_event
        WHERE biz_date = %s AND qc_module = '{MODULE}'
          AND qa_owner_name IS NOT NULL AND qa_owner_name != ''
        GROUP BY qa_owner_name ORDER BY qa_cnt DESC LIMIT %s
    """, [selected_date, limit])
    return {
        "ok": True,
        "data": normalize_payload({
            "items": dataframe_to_records(df),
            "total": len(df),
        }),
    }
