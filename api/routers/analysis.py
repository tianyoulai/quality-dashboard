"""
错误分析 API 路由模块

提供错误分析页面所需的数据接口：
1. 最近7天错误总览
2. 错误类型×队列热力矩阵
3. 根因分析数据
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from api.exceptions import DataNotFoundError, InvalidDateRangeError
from storage.tidb_manager import TiDBManager
import logging

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])
logger = logging.getLogger(__name__)


@router.get("/error-overview")
async def get_error_overview(
    days: int = Query(7, description="查询天数", ge=1, le=30)
) -> Dict[str, Any]:
    """
    获取最近N天错误总览
    
    返回：
    - date_range: 日期范围
    - total_errors: 总错误数
    - daily_trend: 每日错误趋势
    - error_distribution: 错误类型分布
    - top_queues: 错误最多的队列
    """
    db = TiDBManager()
    
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # 1. 总错误统计
        total_stats = await _get_total_error_stats(db, start_date, end_date)
        
        # 2. 每日趋势
        daily_trend = await _get_daily_error_trend(db, start_date, end_date)
        
        # 3. 错误类型分布
        error_distribution = await _get_error_type_distribution(db, start_date, end_date)
        
        # 4. Top队列
        top_queues = await _get_top_error_queues(db, start_date, end_date, limit=10)
        
        # 5. 误判/漏判统计
        misjudge_stats = await _get_misjudge_stats(db, start_date, end_date)
        
        return {
            "date_range": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "days": days
            },
            "total_errors": total_stats["total_errors"],
            "total_reviews": total_stats["total_reviews"],
            "error_rate": total_stats["error_rate"],
            "daily_trend": daily_trend,
            "error_distribution": error_distribution,
            "top_queues": top_queues,
            "misjudge_stats": misjudge_stats
        }
        
    except Exception as e:
        logger.error(f"获取错误总览失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    finally:
        db.close()


@router.get("/error-heatmap")
async def get_error_heatmap(
    days: int = Query(7, description="查询天数", ge=1, le=30)
) -> Dict[str, Any]:
    """
    获取错误类型×队列热力矩阵
    
    返回：
    - error_types: 错误类型列表
    - queues: 队列列表
    - matrix: 热力矩阵数据 [[error_type, queue, count, rate], ...]
    - summary: 汇总统计
    """
    db = TiDBManager()
    
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # 查询热力矩阵数据
        query = """
        SELECT 
            error_type,
            queue_name,
            COUNT(*) as error_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY queue_name), 2) as error_rate_in_queue
        FROM fact_qa_event
        WHERE biz_date BETWEEN %s AND %s
          AND is_final_correct = 0
          AND error_type IS NOT NULL
          AND queue_name IS NOT NULL
        GROUP BY error_type, queue_name
        ORDER BY queue_name, error_count DESC
        """
        
        results = db.execute_query(query, (str(start_date), str(end_date)))
        
        if not results:
            return {
                "date_range": {"start_date": str(start_date), "end_date": str(end_date)},
                "error_types": [],
                "queues": [],
                "matrix": [],
                "summary": {}
            }
        
        # 提取唯一的错误类型和队列
        error_types = sorted(list(set(row[0] for row in results)))
        queues = sorted(list(set(row[1] for row in results)))
        
        # 构建矩阵数据
        matrix = []
        for row in results:
            matrix.append({
                "error_type": row[0],
                "queue": row[1],
                "count": row[2],
                "rate": float(row[3]) if row[3] else 0.0
            })
        
        # 汇总统计
        summary = {
            "total_error_types": len(error_types),
            "total_queues": len(queues),
            "total_combinations": len(matrix),
            "total_errors": sum(item["count"] for item in matrix)
        }
        
        return {
            "date_range": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "days": days
            },
            "error_types": error_types,
            "queues": queues,
            "matrix": matrix,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"获取错误热力图失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    finally:
        db.close()


@router.get("/root-cause")
async def get_root_cause_analysis(
    error_type: Optional[str] = Query(None, description="错误类型"),
    queue_name: Optional[str] = Query(None, description="队列名称"),
    days: int = Query(7, description="查询天数", ge=1, le=30)
) -> Dict[str, Any]:
    """
    根因分析
    
    分析特定错误类型或队列的深层原因：
    - 时段分析：哪个时段错误率最高？
    - 审核人分析：哪些审核人容易犯错？
    - 关联错误：经常一起出现的错误
    - 趋势分析：错误趋势是上升还是下降？
    """
    db = TiDBManager()
    
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # 构建筛选条件
        filters = []
        params = [str(start_date), str(end_date)]
        
        if error_type:
            filters.append("error_type = %s")
            params.append(error_type)
        
        if queue_name:
            filters.append("queue_name = %s")
            params.append(queue_name)
        
        filter_clause = " AND " + " AND ".join(filters) if filters else ""
        
        # 1. 每日趋势分析
        daily_trend = await _get_filtered_daily_trend(
            db, start_date, end_date, error_type, queue_name
        )
        
        # 2. 审核人分析（Top 10易错审核人）
        top_reviewers = await _get_top_error_reviewers(
            db, start_date, end_date, error_type, queue_name, limit=10
        )
        
        # 3. 关联错误分析
        related_errors = await _get_related_errors(
            db, start_date, end_date, error_type, queue_name, limit=5
        )
        
        # 4. 趋势分析（前3天 vs 后3天）
        trend_analysis = await _analyze_trend(
            db, start_date, end_date, error_type, queue_name
        )
        
        return {
            "filters": {
                "error_type": error_type,
                "queue_name": queue_name,
                "date_range": {
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "days": days
                }
            },
            "daily_trend": daily_trend,
            "top_reviewers": top_reviewers,
            "related_errors": related_errors,
            "trend_analysis": trend_analysis
        }
        
    except Exception as e:
        logger.error(f"根因分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    finally:
        db.close()


# ==================== 辅助函数 ====================

async def _get_total_error_stats(db: TiDBManager, start_date, end_date) -> Dict[str, Any]:
    """获取总错误统计"""
    query = """
    SELECT 
        COUNT(*) as total_reviews,
        SUM(CASE WHEN is_final_correct = 0 THEN 1 ELSE 0 END) as total_errors,
        ROUND(AVG(CASE WHEN is_final_correct = 0 THEN 100.0 ELSE 0 END), 2) as error_rate
    FROM fact_qa_event
    WHERE biz_date BETWEEN %s AND %s
    """
    
    result = db.execute_query(query, (str(start_date), str(end_date)))
    
    if not result or not result[0][0]:
        return {
            "total_reviews": 0,
            "total_errors": 0,
            "error_rate": 0.0
        }
    
    row = result[0]
    return {
        "total_reviews": row[0],
        "total_errors": row[1],
        "error_rate": float(row[2]) if row[2] else 0.0
    }


async def _get_daily_error_trend(db: TiDBManager, start_date, end_date) -> List[Dict[str, Any]]:
    """获取每日错误趋势"""
    query = """
    SELECT 
        biz_date,
        COUNT(*) as review_count,
        SUM(CASE WHEN is_final_correct = 0 THEN 1 ELSE 0 END) as error_count,
        ROUND(AVG(CASE WHEN is_final_correct = 0 THEN 100.0 ELSE 0 END), 2) as error_rate
    FROM fact_qa_event
    WHERE biz_date BETWEEN %s AND %s
    GROUP BY biz_date
    ORDER BY biz_date
    """
    
    results = db.execute_query(query, (str(start_date), str(end_date)))
    
    trend = []
    for row in results:
        trend.append({
            "date": str(row[0]),
            "review_count": row[1],
            "error_count": row[2],
            "error_rate": float(row[3]) if row[3] else 0.0
        })
    
    return trend


async def _get_error_type_distribution(db: TiDBManager, start_date, end_date) -> List[Dict[str, Any]]:
    """获取错误类型分布"""
    query = """
    SELECT 
        error_type,
        COUNT(*) as error_count,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM fact_qa_event WHERE biz_date BETWEEN %s AND %s AND is_final_correct = 0), 2) as percentage
    FROM fact_qa_event
    WHERE biz_date BETWEEN %s AND %s
      AND is_final_correct = 0
      AND error_type IS NOT NULL
    GROUP BY error_type
    ORDER BY error_count DESC
    """
    
    results = db.execute_query(query, (str(start_date), str(end_date), str(start_date), str(end_date)))
    
    distribution = []
    for row in results:
        distribution.append({
            "error_type": row[0],
            "count": row[1],
            "percentage": float(row[2]) if row[2] else 0.0
        })
    
    return distribution


async def _get_top_error_queues(db: TiDBManager, start_date, end_date, limit: int) -> List[Dict[str, Any]]:
    """获取错误最多的队列"""
    query = """
    SELECT 
        queue_name,
        COUNT(*) as total_count,
        SUM(CASE WHEN is_final_correct = 0 THEN 1 ELSE 0 END) as error_count,
        ROUND(AVG(CASE WHEN is_final_correct = 0 THEN 100.0 ELSE 0 END), 2) as error_rate
    FROM fact_qa_event
    WHERE biz_date BETWEEN %s AND %s
      AND queue_name IS NOT NULL
    GROUP BY queue_name
    ORDER BY error_count DESC
    LIMIT %s
    """
    
    results = db.execute_query(query, (str(start_date), str(end_date), limit))
    
    queues = []
    for row in results:
        queues.append({
            "queue_name": row[0],
            "total_count": row[1],
            "error_count": row[2],
            "error_rate": float(row[3]) if row[3] else 0.0
        })
    
    return queues


async def _get_misjudge_stats(db: TiDBManager, start_date, end_date) -> Dict[str, Any]:
    """获取误判/漏判统计"""
    query = """
    SELECT 
        SUM(CASE WHEN is_misjudge = 1 THEN 1 ELSE 0 END) as misjudge_count,
        SUM(CASE WHEN is_missjudge = 1 THEN 1 ELSE 0 END) as missjudge_count,
        COUNT(*) as total_count
    FROM fact_qa_event
    WHERE biz_date BETWEEN %s AND %s
      AND is_final_correct = 0
    """
    
    result = db.execute_query(query, (str(start_date), str(end_date)))
    
    if not result or not result[0]:
        return {
            "misjudge_count": 0,
            "missjudge_count": 0,
            "misjudge_rate": 0.0,
            "missjudge_rate": 0.0
        }
    
    row = result[0]
    total = row[2] if row[2] else 1
    
    return {
        "misjudge_count": row[0],
        "missjudge_count": row[1],
        "misjudge_rate": round((row[0] / total * 100) if row[0] else 0.0, 2),
        "missjudge_rate": round((row[1] / total * 100) if row[1] else 0.0, 2)
    }


async def _get_filtered_daily_trend(
    db: TiDBManager, 
    start_date, 
    end_date, 
    error_type: Optional[str], 
    queue_name: Optional[str]
) -> List[Dict[str, Any]]:
    """获取筛选后的每日趋势"""
    conditions = ["biz_date BETWEEN %s AND %s", "is_final_correct = 0"]
    params = [str(start_date), str(end_date)]
    
    if error_type:
        conditions.append("error_type = %s")
        params.append(error_type)
    
    if queue_name:
        conditions.append("queue_name = %s")
        params.append(queue_name)
    
    query = f"""
    SELECT 
        biz_date,
        COUNT(*) as error_count
    FROM fact_qa_event
    WHERE {" AND ".join(conditions)}
    GROUP BY biz_date
    ORDER BY biz_date
    """
    
    results = db.execute_query(query, tuple(params))
    
    trend = []
    for row in results:
        trend.append({
            "date": str(row[0]),
            "count": row[1]
        })
    
    return trend


async def _get_top_error_reviewers(
    db: TiDBManager,
    start_date,
    end_date,
    error_type: Optional[str],
    queue_name: Optional[str],
    limit: int
) -> List[Dict[str, Any]]:
    """获取Top易错审核人"""
    conditions = ["biz_date BETWEEN %s AND %s", "is_final_correct = 0", "reviewer_name IS NOT NULL"]
    params = [str(start_date), str(end_date)]
    
    if error_type:
        conditions.append("error_type = %s")
        params.append(error_type)
    
    if queue_name:
        conditions.append("queue_name = %s")
        params.append(queue_name)
    
    params.append(limit)
    
    query = f"""
    SELECT 
        reviewer_name,
        COUNT(*) as error_count,
        GROUP_CONCAT(DISTINCT queue_name ORDER BY queue_name SEPARATOR ', ') as queues
    FROM fact_qa_event
    WHERE {" AND ".join(conditions)}
    GROUP BY reviewer_name
    ORDER BY error_count DESC
    LIMIT %s
    """
    
    results = db.execute_query(query, tuple(params))
    
    reviewers = []
    for row in results:
        reviewers.append({
            "reviewer_name": row[0],
            "error_count": row[1],
            "queues": row[2] or ""
        })
    
    return reviewers


async def _get_related_errors(
    db: TiDBManager,
    start_date,
    end_date,
    error_type: Optional[str],
    queue_name: Optional[str],
    limit: int
) -> List[Dict[str, Any]]:
    """获取关联错误（经常一起出现的错误）"""
    if not error_type:
        return []
    
    conditions = ["biz_date BETWEEN %s AND %s", "error_type != %s"]
    params = [str(start_date), str(end_date), error_type]
    
    if queue_name:
        conditions.append("queue_name = %s")
        params.append(queue_name)
    
    params.append(limit)
    
    query = f"""
    SELECT 
        error_type,
        COUNT(*) as co_occurrence_count
    FROM fact_qa_event
    WHERE {" AND ".join(conditions)}
      AND is_final_correct = 0
      AND error_type IS NOT NULL
    GROUP BY error_type
    ORDER BY co_occurrence_count DESC
    LIMIT %s
    """
    
    results = db.execute_query(query, tuple(params))
    
    related = []
    for row in results:
        related.append({
            "error_type": row[0],
            "co_occurrence_count": row[1]
        })
    
    return related


async def _analyze_trend(
    db: TiDBManager,
    start_date,
    end_date,
    error_type: Optional[str],
    queue_name: Optional[str]
) -> Dict[str, Any]:
    """趋势分析（前3天 vs 后3天）"""
    total_days = (end_date - start_date).days + 1
    
    if total_days < 6:
        return {
            "status": "insufficient_data",
            "message": "需要至少6天数据才能进行趋势分析"
        }
    
    # 前3天
    early_start = start_date
    early_end = start_date + timedelta(days=2)
    
    # 后3天
    late_start = end_date - timedelta(days=2)
    late_end = end_date
    
    conditions_base = ["is_final_correct = 0"]
    params_base = []
    
    if error_type:
        conditions_base.append("error_type = %s")
        params_base.append(error_type)
    
    if queue_name:
        conditions_base.append("queue_name = %s")
        params_base.append(queue_name)
    
    where_clause = " AND ".join(conditions_base)
    
    # 查询前3天
    query_early = f"""
    SELECT COUNT(*) FROM fact_qa_event
    WHERE biz_date BETWEEN %s AND %s AND {where_clause}
    """
    early_result = db.execute_query(query_early, (str(early_start), str(early_end)) + tuple(params_base))
    early_count = early_result[0][0] if early_result else 0
    
    # 查询后3天
    query_late = f"""
    SELECT COUNT(*) FROM fact_qa_event
    WHERE biz_date BETWEEN %s AND %s AND {where_clause}
    """
    late_result = db.execute_query(query_late, (str(late_start), str(late_end)) + tuple(params_base))
    late_count = late_result[0][0] if late_result else 0
    
    # 计算变化
    change = late_count - early_count
    change_rate = round((change / early_count * 100) if early_count > 0 else 0.0, 2)
    
    # 判断趋势
    if change_rate > 10:
        trend = "increasing"
        severity = "warning"
    elif change_rate < -10:
        trend = "decreasing"
        severity = "good"
    else:
        trend = "stable"
        severity = "normal"
    
    return {
        "early_period": {
            "start": str(early_start),
            "end": str(early_end),
            "count": early_count
        },
        "late_period": {
            "start": str(late_start),
            "end": str(late_end),
            "count": late_count
        },
        "change": change,
        "change_rate": change_rate,
        "trend": trend,
        "severity": severity
    }
