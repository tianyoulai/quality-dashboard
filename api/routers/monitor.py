"""
实时监控 API 路由模块

提供实时监控页面所需的数据接口：
1. 当日 vs 昨日核心指标对比
2. 重点关注队列排行（正确率 <90%）
3. 高频错误类型排行（Top 5）
4. 重点关注审核人排行（正确率 <85%）
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from api.exceptions import DataNotFoundError, InvalidDateRangeError
from storage.tidb_manager import TiDBManager
import logging

router = APIRouter(prefix="/api/v1/monitor", tags=["monitor"])
logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def get_monitor_dashboard(
    date: Optional[str] = Query(None, description="监控日期 (YYYY-MM-DD)，默认今天")
) -> Dict[str, Any]:
    """
    获取实时监控看板核心数据
    
    返回：
    - today: 当日核心指标
    - yesterday: 昨日核心指标
    - alerts: 异常告警列表
    """
    db = TiDBManager()
    
    try:
        # 确定日期
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise InvalidDateRangeError(f"日期格式错误: {date}")
        else:
            target_date = datetime.now().date()
        
        yesterday_date = target_date - timedelta(days=1)
        
        # 查询当日数据
        today_stats = await _get_daily_stats(db, target_date)
        
        # 查询昨日数据
        yesterday_stats = await _get_daily_stats(db, yesterday_date)
        
        # 计算变化
        changes = _calculate_changes(today_stats, yesterday_stats)
        
        # 检测异常
        alerts = _detect_alerts(today_stats, yesterday_stats, changes)
        
        return {
            "date": str(target_date),
            "yesterday_date": str(yesterday_date),
            "today": today_stats,
            "yesterday": yesterday_stats,
            "changes": changes,
            "alerts": alerts
        }
        
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取监控数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
@router.get("/queue-ranking")
async def get_queue_ranking(
    date: Optional[str] = Query(None, description="查询日期"),
    threshold: float = Query(99.0, description="正确率阈值，低于此值显示（默认99%）", ge=0, le=100),
    group_name: Optional[str] = Query(None, description="组别筛选"),
    limit: int = Query(50, description="返回数量", ge=1, le=200)
) -> List[Dict[str, Any]]:
    """
    获取队列排行（来自 mart_day_queue，含错判率/漏判率/申诉改判率）
    返回全部队列（含正常达标的），按正确率升序排列；threshold 用于标记哪些需关注
    """
    db = TiDBManager()
    try:
        target_date = _parse_date(date)
        params: list = [str(target_date)]
        group_filter = ""
        if group_name:
            if group_name.startswith("B组"):
                group_filter = " AND group_name LIKE %s"
                params.append("B组%")
            else:
                group_filter = " AND group_name = %s"
                params.append(group_name)
        params.append(limit)

        query = f"""
        SELECT
            group_name,
            queue_name,
            qa_cnt,
            raw_correct_cnt,
            final_correct_cnt,
            raw_error_cnt,
            final_error_cnt,
            misjudge_cnt,
            missjudge_cnt,
            raw_accuracy_rate,
            final_accuracy_rate,
            misjudge_rate,
            missjudge_rate,
            appeal_cnt,
            appeal_reversed_cnt,
            appeal_reverse_rate,
            reviewer_cnt
        FROM mart_day_queue
        WHERE biz_date = %s{group_filter}
        ORDER BY final_accuracy_rate ASC
        LIMIT %s
        """
        results = db.execute_query(query, tuple(params))
        if not results:
            return []

        ranking = []
        for idx, row in enumerate(results, start=1):
            acc = float(row[10]) if row[10] is not None else 0.0
            ranking.append({
                "rank": idx,
                "group_name": row[0] or "",
                "queue_name": row[1] or "",
                "total_count": int(row[2]) if row[2] else 0,
                "raw_correct_cnt": int(row[3]) if row[3] else 0,
                "final_correct_cnt": int(row[4]) if row[4] else 0,
                "raw_error_cnt": int(row[5]) if row[5] else 0,
                "final_error_cnt": int(row[6]) if row[6] else 0,
                "misjudge_cnt": int(row[7]) if row[7] else 0,
                "missjudge_cnt": int(row[8]) if row[8] else 0,
                "raw_accuracy_rate": float(row[9]) if row[9] is not None else 0.0,
                "correct_rate": acc,
                "misjudge_rate": float(row[11]) if row[11] is not None else 0.0,
                "missjudge_rate": float(row[12]) if row[12] is not None else 0.0,
                "appeal_cnt": int(row[13]) if row[13] else 0,
                "appeal_reversed_cnt": int(row[14]) if row[14] else 0,
                "appeal_reverse_rate": float(row[15]) if row[15] is not None else 0.0,
                "reviewer_cnt": int(row[16]) if row[16] else 0,
                "needs_attention": acc < threshold,
            })
        return ranking
    except Exception as e:
        logger.error(f"获取队列排行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
@router.get("/error-ranking")
async def get_error_ranking(
    date: Optional[str] = Query(None, description="查询日期"),
    limit: int = Query(5, description="返回数量", ge=1, le=20)
) -> List[Dict[str, Any]]:
    """
    获取高频错误类型排行
    
    返回错误次数最多的 Top N 错误类型
    """
    db = TiDBManager()
    
    try:
        target_date = _parse_date(date)
        
        query = """
        SELECT 
            error_type,
            COUNT(*) as error_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM fact_qa_event WHERE biz_date = %s AND is_final_correct = 0), 2) as error_percentage,
            SUM(CASE WHEN is_misjudge = 1 THEN 1 ELSE 0 END) as misjudge_count,
            SUM(CASE WHEN is_missjudge = 1 THEN 1 ELSE 0 END) as missjudge_count,
            GROUP_CONCAT(DISTINCT queue_name ORDER BY queue_name SEPARATOR ', ') as main_queues
        FROM fact_qa_event
        WHERE biz_date = %s
          AND is_final_correct = 0
          AND error_type IS NOT NULL
        GROUP BY error_type
        ORDER BY error_count DESC
        LIMIT %s
        """
        
        results = db.execute_query(query, (str(target_date), str(target_date), limit))
        
        if not results:
            return []
        
        # 格式化结果
        ranking = []
        for idx, row in enumerate(results, start=1):
            total_errors = row[1]
            misjudge = row[3]
            missjudge = row[4]
            
            ranking.append({
                "rank": idx,
                "error_type": row[0],
                "error_count": row[1],
                "error_percentage": float(row[2]) if row[2] else 0.0,
                "misjudge_count": misjudge,
                "missjudge_count": missjudge,
                "misjudge_rate": round(misjudge * 100.0 / total_errors, 2) if total_errors > 0 else 0.0,
                "missjudge_rate": round(missjudge * 100.0 / total_errors, 2) if total_errors > 0 else 0.0,
                "main_queues": row[5] or ""
            })
        
        return ranking
        
    except Exception as e:
        logger.error(f"获取错误排行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
@router.get("/reviewer-ranking")
async def get_reviewer_ranking(
    date: Optional[str] = Query(None, description="查询日期"),
    threshold: float = Query(95.0, description="正确率阈值，低于此值显示（默认95%）", ge=0, le=100),
    group_name: Optional[str] = Query(None, description="组别筛选"),
    queue_name: Optional[str] = Query(None, description="队列筛选"),
    limit: int = Query(50, description="返回数量", ge=1, le=200)
) -> List[Dict[str, Any]]:
    """
    获取审核人排行（来自 mart_day_auditor，含错判/漏判数据）
    返回全部审核人，threshold 用于标记需关注的人；按正确率升序
    """
    db = TiDBManager()
    try:
        target_date = _parse_date(date)
        params: list = [str(target_date)]
        filters = ""
        if group_name:
            if group_name.startswith("B组"):
                filters += " AND group_name LIKE %s"
                params.append("B组%")
            else:
                filters += " AND group_name = %s"
                params.append(group_name)
        if queue_name:
            filters += " AND queue_name = %s"
            params.append(queue_name)
        params.append(limit)

        query = f"""
        SELECT
            reviewer_name,
            group_name,
            queue_name,
            qa_cnt,
            raw_correct_cnt,
            final_correct_cnt,
            misjudge_cnt,
            missjudge_cnt,
            raw_accuracy_rate,
            final_accuracy_rate,
            misjudge_rate,
            missjudge_rate
        FROM mart_day_auditor
        WHERE biz_date = %s{filters}
        ORDER BY raw_accuracy_rate ASC
        LIMIT %s
        """
        results = db.execute_query(query, tuple(params))
        if not results:
            return []

        ranking = []
        for idx, row in enumerate(results, start=1):
            acc = float(row[8]) if row[8] is not None else 0.0
            ranking.append({
                "rank": idx,
                "reviewer_name": row[0] or "",
                "group_name": row[1] or "",
                "queue_name": row[2] or "",
                "review_count": int(row[3]) if row[3] else 0,
                "raw_correct_cnt": int(row[4]) if row[4] else 0,
                "final_correct_cnt": int(row[5]) if row[5] else 0,
                "misjudge_cnt": int(row[6]) if row[6] else 0,
                "missjudge_cnt": int(row[7]) if row[7] else 0,
                "correct_rate": acc,
                "final_accuracy_rate": float(row[9]) if row[9] is not None else 0.0,
                "misjudge_rate": float(row[10]) if row[10] is not None else 0.0,
                "missjudge_rate": float(row[11]) if row[11] is not None else 0.0,
                "needs_attention": acc < threshold,
            })
        return ranking
    except Exception as e:
        logger.error(f"获取审核人排行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
# ==================== 辅助函数 ====================

@router.get("/meta")
async def get_monitor_meta(
    date: Optional[str] = Query(None, description="查询日期"),
) -> Dict[str, Any]:
    """获取筛选用的组别/队列列表"""
    db = TiDBManager()
    try:
        target_date = _parse_date(date)
        groups = db.execute_query(
            "SELECT DISTINCT group_name FROM mart_day_queue WHERE biz_date=%s ORDER BY group_name",
            (str(target_date),)
        )
        queues = db.execute_query(
            "SELECT DISTINCT queue_name FROM mart_day_queue WHERE biz_date=%s ORDER BY queue_name",
            (str(target_date),)
        )
        return {
            "groups": [r[0] for r in groups if r[0]],
            "queues": [r[0] for r in queues if r[0]],
        }
    except Exception as e:
        logger.error(f"获取 meta 失败: {e}", exc_info=True)
        return {"groups": [], "queues": []}

async def _get_daily_stats(db: TiDBManager, date) -> Dict[str, Any]:
    """获取单日统计数据"""
    query = """
    SELECT 
        COUNT(*) as total_count,
        SUM(CASE WHEN is_final_correct = 1 THEN 1 ELSE 0 END) as correct_count,
        ROUND(AVG(CASE WHEN is_final_correct = 1 THEN 100.0 ELSE 0 END), 2) as correct_rate,
        ROUND(AVG(CASE WHEN is_misjudge = 1 THEN 100.0 ELSE 0 END), 2) as misjudge_rate,
        ROUND(AVG(CASE WHEN is_appealed = 1 THEN 100.0 ELSE 0 END), 2) as appeal_rate
    FROM fact_qa_event
    WHERE biz_date = %s
    """
    
    result = db.execute_query(query, (str(date),))
    
    if not result or not result[0][0]:
        raise DataNotFoundError(f"未找到日期 {date} 的数据")
    
    row = result[0]
    return {
        "total_count": row[0],
        "correct_count": row[1],
        "correct_rate": float(row[2]) if row[2] else 0.0,
        "misjudge_rate": float(row[3]) if row[3] else 0.0,
        "appeal_rate": float(row[4]) if row[4] else 0.0
    }


def _calculate_changes(today: Dict[str, Any], yesterday: Dict[str, Any]) -> Dict[str, Any]:
    """计算变化值"""
    changes = {}
    
    # 计算数量变化
    changes["total_count"] = today["total_count"] - yesterday["total_count"]
    changes["total_count_rate"] = round(
        (changes["total_count"] / yesterday["total_count"] * 100) if yesterday["total_count"] > 0 else 0.0,
        2
    )
    
    # 计算率值变化（绝对值变化）
    changes["correct_rate"] = round(today["correct_rate"] - yesterday["correct_rate"], 2)
    changes["misjudge_rate"] = round(today["misjudge_rate"] - yesterday["misjudge_rate"], 2)
    changes["appeal_rate"] = round(today["appeal_rate"] - yesterday["appeal_rate"], 2)
    
    return changes


def _detect_alerts(today: Dict[str, Any], yesterday: Dict[str, Any], changes: Dict[str, Any]) -> List[Dict[str, Any]]:
    """检测异常告警"""
    alerts = []
    
    # 告警阈值
    CORRECT_RATE_THRESHOLD = -5.0  # 正确率下降超过5%
    MISJUDGE_RATE_THRESHOLD = 2.0  # 误判率上升超过2%
    APPEAL_RATE_THRESHOLD = 3.0    # 申诉率上升超过3%
    
    # 检测正确率异常
    if changes["correct_rate"] < CORRECT_RATE_THRESHOLD:
        alerts.append({
            "type": "correct_rate_drop",
            "level": "critical",
            "title": "正确率大幅下降",
            "message": f"当前正确率 {today['correct_rate']:.2f}%，较昨日下降 {abs(changes['correct_rate']):.2f}%",
            "current_value": today["correct_rate"],
            "previous_value": yesterday["correct_rate"],
            "change": changes["correct_rate"]
        })
    
    # 检测误判率异常
    if changes["misjudge_rate"] > MISJUDGE_RATE_THRESHOLD:
        alerts.append({
            "type": "misjudge_rate_increase",
            "level": "warning",
            "title": "误判率异常上升",
            "message": f"当前误判率 {today['misjudge_rate']:.2f}%，较昨日上升 {changes['misjudge_rate']:.2f}%",
            "current_value": today["misjudge_rate"],
            "previous_value": yesterday["misjudge_rate"],
            "change": changes["misjudge_rate"]
        })
    
    # 检测申诉率异常
    if changes["appeal_rate"] > APPEAL_RATE_THRESHOLD:
        alerts.append({
            "type": "appeal_rate_increase",
            "level": "warning",
            "title": "申诉率异常上升",
            "message": f"当前申诉率 {today['appeal_rate']:.2f}%，较昨日上升 {changes['appeal_rate']:.2f}%",
            "current_value": today["appeal_rate"],
            "previous_value": yesterday["appeal_rate"],
            "change": changes["appeal_rate"]
        })
    
    return alerts


def _parse_date(date_str: Optional[str]):
    """解析日期字符串"""
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise InvalidDateRangeError(f"日期格式错误: {date_str}")
    else:
        return datetime.now().date()
