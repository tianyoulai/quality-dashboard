"""
新人追踪 API 路由模块 — 真实数据版

数据来源：
  - dim_newcomer_batch  : 批次元数据（人员名单、入职日期）
  - fact_newcomer_qa    : 新人质检记录（通过 reviewer_name JOIN 批次）

端点：
  GET /batches          — 批次列表（从 dim_newcomer_batch 聚合）
  GET /batch/{batch_id} — 批次详情 + 成员列表
  GET /newcomer/{name}  — 新人个人数据 + 趋势
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.serializers import dataframe_to_records, normalize_payload
from storage.repository import DashboardRepository

router = APIRouter(prefix="/api/v1/newcomers", tags=["newcomers"])
logger = logging.getLogger(__name__)
repo = DashboardRepository()

# 新人合格正确率阈值
PASS_THRESHOLD = 90.0


# ══════════════════════════════════════════════════════════════
#  1. 批次列表
# ══════════════════════════════════════════════════════════════

@router.get("/batches")
def get_batch_list(
    status: Optional[str] = Query(None, description="状态筛选: training / completed / all")
) -> dict:
    """批次列表：
    - dim_newcomer_batch 有批次名称的 → 按批次聚合
    - fact_newcomer_qa 中 batch_name IS NULL 的 → 归入「未归档批次」
    """
    batches = []

    # --- 来源1：dim_newcomer_batch 正式批次 ---
    status_filter = ""
    params: list = []
    if status and status != "all":
        status_filter = "WHERE b.status = %s"
        params.append(status)

    df_batch = repo.fetch_df(f"""
        SELECT
            b.batch_name,
            b.status,
            MIN(b.join_date)       AS join_date,
            COUNT(DISTINCT b.reviewer_name) AS total_people
        FROM dim_newcomer_batch b
        {status_filter}
        GROUP BY b.batch_name, b.status
        ORDER BY MIN(b.join_date) DESC
    """, params or None)

    for _, row in df_batch.iterrows():
        batch_name = row["batch_name"]
        total_people = int(row["total_people"])
        # 用批次成员名单去 fact_newcomer_qa 匹配
        perf = repo.fetch_one("""
            SELECT COUNT(DISTINCT q.reviewer_name) AS active_cnt,
                   COUNT(*) AS qa_cnt,
                   ROUND(SUM(q.is_correct)*100.0/NULLIF(COUNT(*),0),2) AS avg_acc,
                   MIN(q.biz_date) AS first_date, MAX(q.biz_date) AS last_date
            FROM fact_newcomer_qa q
            INNER JOIN dim_newcomer_batch b ON q.reviewer_name = b.reviewer_name
            WHERE b.batch_name = %s
        """, [batch_name])
        avg_acc = float(perf["avg_acc"] or 0) if perf else 0
        qa_cnt = int(perf["qa_cnt"] or 0) if perf else 0
        first_date = perf["first_date"] if perf else None
        last_date = perf["last_date"] if perf else None
        current_day = (last_date - first_date).days + 1 if (first_date and last_date) else 0

        df_pass = repo.fetch_df("""
            SELECT ROUND(SUM(q.is_correct)*100.0/NULLIF(COUNT(*),0),2) AS acc
            FROM fact_newcomer_qa q
            INNER JOIN dim_newcomer_batch b ON q.reviewer_name = b.reviewer_name
            WHERE b.batch_name = %s GROUP BY q.reviewer_name
        """, [batch_name])
        passed_count = int((df_pass["acc"] >= PASS_THRESHOLD).sum()) if not df_pass.empty else 0

        batches.append({
            "batch_id": batch_name,
            "batch_name": f"{batch_name} 批次",
            "status": str(row["status"]),
            "source": "dim_batch",
            "join_date": row["join_date"].isoformat() if hasattr(row["join_date"], "isoformat") else str(row["join_date"]),
            "total_people": total_people,
            "active_people": int(perf["active_cnt"] or 0) if perf else 0,
            "qa_cnt": qa_cnt,
            "current_day": current_day,
            "avg_accuracy": avg_acc,
            "passed_count": passed_count,
            "pass_rate": round(passed_count / total_people * 100, 1) if total_people else 0,
            "last_date": last_date.isoformat() if last_date and hasattr(last_date, "isoformat") else None,
        })

    # --- 来源2：fact_newcomer_qa 中未归档到 dim_newcomer_batch 的人员 ---
    # 将这批人按「最早出现日期月份」或统一归入一个「云雀新人」批次展示
    unmatched = repo.fetch_one("""
        SELECT COUNT(DISTINCT q.reviewer_name) AS cnt,
               COUNT(*) AS qa_cnt,
               ROUND(SUM(q.is_correct)*100.0/NULLIF(COUNT(*),0),2) AS avg_acc,
               MIN(q.biz_date) AS first_date, MAX(q.biz_date) AS last_date
        FROM fact_newcomer_qa q
        LEFT JOIN dim_newcomer_batch b ON q.reviewer_name = b.reviewer_name
        WHERE b.reviewer_name IS NULL
    """)

    if unmatched and int(unmatched["cnt"] or 0) > 0:
        total_p = int(unmatched["cnt"])
        avg_acc = float(unmatched["avg_acc"] or 0)
        qa_cnt = int(unmatched["qa_cnt"] or 0)
        fd = unmatched["first_date"]
        ld = unmatched["last_date"]
        current_day = (ld - fd).days + 1 if (fd and ld) else 0

        df_pass2 = repo.fetch_df("""
            SELECT ROUND(SUM(q.is_correct)*100.0/NULLIF(COUNT(*),0),2) AS acc
            FROM fact_newcomer_qa q
            LEFT JOIN dim_newcomer_batch b ON q.reviewer_name = b.reviewer_name
            WHERE b.reviewer_name IS NULL GROUP BY q.reviewer_name
        """)
        passed2 = int((df_pass2["acc"] >= PASS_THRESHOLD).sum()) if not df_pass2.empty else 0

        batches.append({
            "batch_id": "__unarchived__",
            "batch_name": "云雀联营新人（未归档）",
            "status": "training",
            "source": "fact_qa",
            "join_date": fd.isoformat() if fd and hasattr(fd, "isoformat") else None,
            "total_people": total_p,
            "active_people": total_p,
            "qa_cnt": qa_cnt,
            "current_day": current_day,
            "avg_accuracy": avg_acc,
            "passed_count": passed2,
            "pass_rate": round(passed2 / total_p * 100, 1) if total_p else 0,
            "last_date": ld.isoformat() if ld and hasattr(ld, "isoformat") else None,
        })

    return {"ok": True, "data": normalize_payload({"batches": batches, "total": len(batches)})}


# ══════════════════════════════════════════════════════════════
#  2. 批次详情 + 成员列表
# ══════════════════════════════════════════════════════════════

@router.get("/batch/{batch_id}")
def get_batch_detail(batch_id: str) -> dict:
    """批次详情，含每位成员的汇总指标。支持 __unarchived__ 查未归档批次。"""

    if batch_id == "__unarchived__":
        # 未归档批次：直接从 fact_newcomer_qa 查，排除已在 dim_newcomer_batch 的人
        df = repo.fetch_df("""
            SELECT q.reviewer_name AS name,
                   COUNT(q.id) AS qa_cnt,
                   ROUND(SUM(q.is_correct)*100.0/NULLIF(COUNT(q.id),0),2) AS accuracy,
                   SUM(CASE WHEN q.is_correct=0 THEN 1 ELSE 0 END) AS error_cnt,
                   MIN(q.biz_date) AS first_date, MAX(q.biz_date) AS last_date,
                   COUNT(DISTINCT q.queue_name) AS queue_cnt
            FROM fact_newcomer_qa q
            LEFT JOIN dim_newcomer_batch b ON q.reviewer_name = b.reviewer_name
            WHERE b.reviewer_name IS NULL
            GROUP BY q.reviewer_name ORDER BY accuracy ASC
        """)
        batch_label = "云雀联营新人（未归档）"
    else:
        # 正式批次
        exists = repo.fetch_one(
            "SELECT COUNT(*) AS cnt FROM dim_newcomer_batch WHERE batch_name = %s",
            [batch_id]
        )
        if not exists or int(exists["cnt"]) == 0:
            raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")

        df = repo.fetch_df("""
            SELECT b.reviewer_name AS name, b.join_date, b.team_name,
                   COUNT(q.id) AS qa_cnt,
                   ROUND(SUM(q.is_correct)*100.0/NULLIF(COUNT(q.id),0),2) AS accuracy,
                   SUM(CASE WHEN q.is_correct=0 THEN 1 ELSE 0 END) AS error_cnt,
                   MIN(q.biz_date) AS first_date, MAX(q.biz_date) AS last_date,
                   COUNT(DISTINCT q.queue_name) AS queue_cnt
            FROM dim_newcomer_batch b
            LEFT JOIN fact_newcomer_qa q ON q.reviewer_name = b.reviewer_name
            WHERE b.batch_name = %s
            GROUP BY b.reviewer_name, b.join_date, b.team_name
            ORDER BY accuracy ASC
        """, [batch_id])
        batch_label = f"{batch_id} 批次"

    newcomers = []
    for _, row in df.iterrows():
        acc = float(row["accuracy"] or 0)
        qa_cnt = int(row["qa_cnt"] or 0)
        first = row.get("first_date")
        last = row.get("last_date")
        try:
            days = (last - first).days + 1 if (first and last and first == first) else 0
        except Exception:
            days = 0

        if qa_cnt == 0:
            status = "no_data"
        elif acc >= 97:
            status = "excellent"
        elif acc >= PASS_THRESHOLD:
            status = "normal"
        elif acc >= 85:
            status = "warning"
        else:
            status = "problem"

        newcomers.append({
            "name": str(row["name"]),
            "team": str(row.get("team_name") or ""),
            "join_date": row["join_date"].isoformat() if row.get("join_date") and hasattr(row["join_date"], "isoformat") else None,
            "qa_cnt": qa_cnt,
            "accuracy": acc,
            "error_cnt": int(row["error_cnt"] or 0),
            "days": days,
            "status": status,
        })

    total_people = len(newcomers)
    active = [n for n in newcomers if n["qa_cnt"] > 0]
    avg_acc = round(sum(n["accuracy"] for n in active) / len(active), 2) if active else 0
    passed = [n for n in active if n["accuracy"] >= PASS_THRESHOLD]

    return {
        "ok": True,
        "data": normalize_payload({
            "id": batch_id,
            "name": batch_label,
            "total_people": total_people,
            "active_people": len(active),
            "avg_accuracy": avg_acc,
            "passed_count": len(passed),
            "pass_rate": round(len(passed) / total_people * 100, 1) if total_people else 0,
            "pass_threshold": PASS_THRESHOLD,
            "newcomers": newcomers,
        }),
    }


# ══════════════════════════════════════════════════════════════
#  3. 新人个人详情 + 趋势
# ══════════════════════════════════════════════════════════════

@router.get("/newcomer/{name}")
def get_newcomer_detail(
    name: str,
    batch_id: Optional[str] = Query(None, description="批次名称（可选，用于精确定位）")
) -> dict:
    """新人个人汇总指标 + 每日趋势 + 错误分布。"""

    # 查基础信息
    batch_filter = "AND b.batch_name = %s" if batch_id else ""
    batch_params = [name, batch_id] if batch_id else [name]

    meta = repo.fetch_one(f"""
        SELECT b.batch_name, b.join_date, b.team_name, b.mentor_name
        FROM dim_newcomer_batch b
        WHERE b.reviewer_name = %s {batch_filter}
        LIMIT 1
    """, batch_params)

    # 总体指标
    summary = repo.fetch_one("""
        SELECT COUNT(*) AS qa_cnt,
               ROUND(SUM(is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS accuracy,
               SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END)          AS error_cnt,
               SUM(is_misjudge)  AS misjudge_cnt,
               SUM(is_missjudge) AS missjudge_cnt,
               MIN(biz_date)     AS first_date,
               MAX(biz_date)     AS last_date,
               COUNT(DISTINCT queue_name) AS queue_cnt
        FROM fact_newcomer_qa
        WHERE reviewer_name = %s
    """, [name])

    if not summary or int(summary["qa_cnt"] or 0) == 0:
        raise HTTPException(status_code=404, detail=f"未找到新人数据: {name}")

    qa_cnt = int(summary["qa_cnt"])
    accuracy = float(summary["accuracy"] or 0)
    first_date = summary["first_date"]
    last_date = summary["last_date"]
    days = (last_date - first_date).days + 1 if (first_date and last_date) else 0

    # 错误类型分布
    df_err = repo.fetch_df("""
        SELECT COALESCE(NULLIF(TRIM(error_type), ''), '无标签') AS err_type,
               COUNT(*) AS cnt
        FROM fact_newcomer_qa
        WHERE reviewer_name = %s AND is_correct = 0
        GROUP BY err_type ORDER BY cnt DESC LIMIT 10
    """, [name])
    total_err = int(df_err["cnt"].sum()) if not df_err.empty else 0
    if not df_err.empty and total_err > 0:
        df_err["pct"] = (df_err["cnt"] / total_err * 100).round(1)
    errors = dataframe_to_records(df_err)

    # 每日趋势
    df_trend = repo.fetch_df("""
        SELECT biz_date AS stat_date,
               COUNT(*) AS qa_cnt,
               ROUND(SUM(is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS accuracy
        FROM fact_newcomer_qa
        WHERE reviewer_name = %s
        GROUP BY biz_date ORDER BY biz_date
    """, [name])
    trend = dataframe_to_records(df_trend)

    # 状态
    if accuracy >= 97:
        status = "excellent"
    elif accuracy >= PASS_THRESHOLD:
        status = "normal"
    elif accuracy >= 85:
        status = "warning"
    else:
        status = "problem"

    return {
        "ok": True,
        "data": normalize_payload({
            "name": name,
            "batch_id": meta["batch_name"] if meta else None,
            "team": meta["team_name"] if meta else None,
            "mentor": meta["mentor_name"] if meta else None,
            "join_date": meta["join_date"].isoformat() if meta and hasattr(meta["join_date"], "isoformat") else None,
            "days": days,
            "qa_cnt": qa_cnt,
            "accuracy": accuracy,
            "error_cnt": int(summary["error_cnt"] or 0),
            "misjudge_cnt": int(summary["misjudge_cnt"] or 0),
            "missjudge_cnt": int(summary["missjudge_cnt"] or 0),
            "queue_cnt": int(summary["queue_cnt"] or 0),
            "pass_threshold": PASS_THRESHOLD,
            "status": status,
            "errors": errors,
            "trend": trend,
        }),
    }
