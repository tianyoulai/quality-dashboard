"""外检看板 API — 基于 mart_day_queue / mart_day_auditor (inspect_type='external')"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
import logging
from datetime import date, timedelta

from storage.tidb_manager import TiDBManager

router = APIRouter(prefix="/api/v1/external", tags=["外检看板"])
logger = logging.getLogger(__name__)


def _db():
    return TiDBManager()


# ─────────────────────────────────────────
#  工具函数
# ─────────────────────────────────────────

def _date_range(start: Optional[str], end: Optional[str]):
    today = date.today()
    if end:
        end_d = date.fromisoformat(end)
    else:
        # 默认取最近有数据日期
        db = _db()
        rows = db.execute_query("SELECT MAX(biz_date) FROM mart_day_queue WHERE inspect_type='external'")
        end_d = rows[0][0] if rows and rows[0][0] else today
    if start:
        start_d = date.fromisoformat(start)
    else:
        start_d = end_d - timedelta(days=6)  # 默认近7天
    return str(start_d), str(end_d)


def _group_filter_sql(group_name: Optional[str]) -> tuple[str, list]:
    if not group_name or group_name in ("全部", "all", ""):
        return "", []
    if group_name.startswith("B组"):
        return " AND group_name LIKE %s", ["B组%"]
    return " AND group_name = %s", [group_name]


# ─────────────────────────────────────────
#  接口
# ─────────────────────────────────────────

@router.get("/summary")
async def get_summary(
    date: Optional[str] = Query(None, description="单日（优先）"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    group_name: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """单日或区间汇总核心指标"""
    db = _db()
    try:
        if date:
            start, end = date, date
        else:
            start, end = _date_range(start_date, end_date)

        gf_sql, gf_params = _group_filter_sql(group_name)
        query = f"""
        SELECT
            SUM(qa_cnt),
            SUM(final_correct_cnt),
            SUM(misjudge_cnt),
            SUM(missjudge_cnt),
            ROUND(SUM(final_correct_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            ROUND(SUM(misjudge_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            ROUND(SUM(missjudge_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            SUM(appeal_reversed_cnt),
            ROUND(SUM(appeal_reversed_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            COUNT(DISTINCT queue_name),
            MAX(reviewer_cnt)
        FROM mart_day_queue
        WHERE inspect_type='external'
          AND biz_date BETWEEN %s AND %s{gf_sql}
        """
        rows = db.execute_query(query, tuple([start, end] + gf_params))
        if not rows or not rows[0][0]:
            return {"start": start, "end": end, "has_data": False}
        r = rows[0]
        return {
            "start": start, "end": end, "has_data": True,
            "total_count": int(r[0]),
            "correct_count": int(r[1]) if r[1] else 0,
            "misjudge_cnt": int(r[2]) if r[2] else 0,
            "missjudge_cnt": int(r[3]) if r[3] else 0,
            "correct_rate": float(r[4]) if r[4] is not None else 0.0,
            "misjudge_rate": float(r[5]) if r[5] is not None else 0.0,
            "missjudge_rate": float(r[6]) if r[6] is not None else 0.0,
            "appeal_reversed_cnt": int(r[7]) if r[7] else 0,
            "appeal_reverse_rate": float(r[8]) if r[8] is not None else 0.0,
            "queue_count": int(r[9]) if r[9] else 0,
        }
    except Exception as e:
        logger.error(f"外检 summary 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trend")
async def get_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    group_name: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    """每日正确率/错判/漏判趋势（折线图数据）"""
    db = _db()
    try:
        start, end = _date_range(start_date, end_date)
        gf_sql, gf_params = _group_filter_sql(group_name)
        query = f"""
        SELECT
            biz_date,
            SUM(qa_cnt),
            ROUND(SUM(final_correct_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            SUM(misjudge_cnt),
            SUM(missjudge_cnt),
            ROUND(SUM(misjudge_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            ROUND(SUM(missjudge_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2)
        FROM mart_day_queue
        WHERE inspect_type='external'
          AND biz_date BETWEEN %s AND %s{gf_sql}
        GROUP BY biz_date
        ORDER BY biz_date ASC
        """
        rows = db.execute_query(query, tuple([start, end] + gf_params))
        return [
            {
                "date": str(r[0]),
                "total_count": int(r[1]) if r[1] else 0,
                "correct_rate": float(r[2]) if r[2] is not None else 0.0,
                "misjudge_cnt": int(r[3]) if r[3] else 0,
                "missjudge_cnt": int(r[4]) if r[4] else 0,
                "misjudge_rate": float(r[5]) if r[5] is not None else 0.0,
                "missjudge_rate": float(r[6]) if r[6] is not None else 0.0,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"外检 trend 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue-ranking")
async def get_queue_ranking(
    date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    group_name: Optional[str] = Query(None),
    limit: int = Query(50),
) -> List[Dict[str, Any]]:
    """队列正确率排名"""
    db = _db()
    try:
        if date:
            start, end = date, date
        else:
            start, end = _date_range(start_date, end_date)
        gf_sql, gf_params = _group_filter_sql(group_name)
        query = f"""
        SELECT
            group_name, queue_name,
            SUM(qa_cnt),
            ROUND(SUM(final_correct_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            ROUND(SUM(misjudge_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            ROUND(SUM(missjudge_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            SUM(misjudge_cnt),
            SUM(missjudge_cnt),
            ROUND(SUM(appeal_reversed_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            MAX(reviewer_cnt)
        FROM mart_day_queue
        WHERE inspect_type='external'
          AND biz_date BETWEEN %s AND %s{gf_sql}
        GROUP BY group_name, queue_name
        ORDER BY 4 ASC
        LIMIT %s
        """
        rows = db.execute_query(query, tuple([start, end] + gf_params + [limit]))
        return [
            {
                "group_name": r[0] or "",
                "queue_name": r[1] or "",
                "total_count": int(r[2]) if r[2] else 0,
                "correct_rate": float(r[3]) if r[3] is not None else 0.0,
                "misjudge_rate": float(r[4]) if r[4] is not None else 0.0,
                "missjudge_rate": float(r[5]) if r[5] is not None else 0.0,
                "misjudge_cnt": int(r[6]) if r[6] else 0,
                "missjudge_cnt": int(r[7]) if r[7] else 0,
                "appeal_reverse_rate": float(r[8]) if r[8] is not None else 0.0,
                "reviewer_cnt": int(r[9]) if r[9] else 0,
                "needs_attention": float(r[3] or 0) < 99,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"外检 queue-ranking 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reviewer-ranking")
async def get_reviewer_ranking(
    date: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    group_name: Optional[str] = Query(None),
    limit: int = Query(200),
) -> List[Dict[str, Any]]:
    """审核人正确率排名"""
    db = _db()
    try:
        if date:
            start, end = date, date
        else:
            start, end = _date_range(start_date, end_date)
        gf_sql, gf_params = _group_filter_sql(group_name)
        query = f"""
        SELECT
            reviewer_name, group_name, queue_name,
            SUM(qa_cnt),
            ROUND(SUM(final_correct_cnt)*100.0/NULLIF(SUM(qa_cnt),0), 2),
            SUM(misjudge_cnt),
            SUM(missjudge_cnt)
        FROM mart_day_auditor
        WHERE inspect_type='external'
          AND biz_date BETWEEN %s AND %s{gf_sql}
        GROUP BY reviewer_name, group_name, queue_name
        ORDER BY 5 ASC
        LIMIT %s
        """
        rows = db.execute_query(query, tuple([start, end] + gf_params + [limit]))
        return [
            {
                "reviewer_name": r[0] or "",
                "group_name": r[1] or "",
                "queue_name": r[2] or "",
                "review_count": int(r[3]) if r[3] else 0,
                "correct_rate": float(r[4]) if r[4] is not None else 0.0,
                "misjudge_cnt": int(r[5]) if r[5] else 0,
                "missjudge_cnt": int(r[6]) if r[6] else 0,
                "needs_attention": float(r[4] or 0) < 95,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"外检 reviewer-ranking 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta")
async def get_meta(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """获取组别/队列枚举（用于筛选下拉）"""
    db = _db()
    try:
        start, end = _date_range(start_date, end_date)
        groups = db.execute_query(
            "SELECT DISTINCT group_name FROM mart_day_queue WHERE inspect_type='external' AND biz_date BETWEEN %s AND %s ORDER BY group_name",
            (start, end)
        )
        return {
            "groups": [r[0] for r in groups if r[0]],
            "date_range": {"start": start, "end": end},
        }
    except Exception as e:
        logger.error(f"外检 meta 失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
