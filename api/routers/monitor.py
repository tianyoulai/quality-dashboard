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
    finally:
        db.close()


@router.get("/queue-ranking")
async def get_queue_ranking(
    date: Optional[str] = Query(None, description="查询日期"),
    threshold: float = Query(90.0, description="正确率阈值", ge=0, le=100),
    limit: int = Query(10, description="返回数量", ge=1, le=50)
) -> List[Dict[str, Any]]:
    """
    获取重点关注队列排行
    
    返回正确率低于阈值的队列，按正确率升序排列
    """
    db = TiDBManager()
    
    try:
        target_date = _parse_date(date)
        
        query = """
        SELECT 
            queue_name,
            COUNT(*) as total_count,
            SUM(CASE WHEN is_final_correct = 1 THEN 1 ELSE 0 END) as correct_count,
            ROUND(AVG(CASE WHEN is_final_correct = 1 THEN 100.0 ELSE 0 END), 2) as correct_rate,
            ROUND(AVG(CASE WHEN is_misjudge = 1 THEN 100.0 ELSE 0 END), 2) as misjudge_rate,
            ROUND(AVG(CASE WHEN is_missjudge = 1 THEN 100.0 ELSE 0 END), 2) as missjudge_rate,
            GROUP_CONCAT(DISTINCT error_type ORDER BY error_type SEPARATOR ', ') as main_errors
        FROM fact_qa_event
        WHERE biz_date = %s
          AND queue_name IS NOT NULL
        GROUP BY queue_name
        HAVING correct_rate < %s
        ORDER BY correct_rate ASC
        LIMIT %s
        """
        
        results = db.execute_query(query, (str(target_date), threshold, limit))
        
        if not results:
            return []
        
        # 格式化结果
        ranking = []
        for idx, row in enumerate(results, start=1):
            ranking.append({
                "rank": idx,
                "queue_name": row[0],
                "total_count": row[1],
                "correct_count": row[2],
                "correct_rate": float(row[3]),
                "misjudge_rate": float(row[4]) if row[4] else 0.0,
                "missjudge_rate": float(row[5]) if row[5] else 0.0,
                "main_errors": row[6] or ""
            })
        
        return ranking
        
    except Exception as e:
        logger.error(f"获取队列排行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    finally:
        db.close()


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
    finally:
        db.close()


@router.get("/reviewer-ranking")
async def get_reviewer_ranking(
    date: Optional[str] = Query(None, description="查询日期"),
    threshold: float = Query(85.0, description="正确率阈值", ge=0, le=100),
    limit: int = Query(10, description="返回数量", ge=1, le=50)
) -> List[Dict[str, Any]]:
    """
    获取重点关注审核人排行
    
    返回正确率低于阈值的审核人，按正确率升序排列
    """
    db = TiDBManager()
    
    try:
        target_date = _parse_date(date)
        
        query = """
        SELECT 
            reviewer_name,
            queue_name,
            COUNT(*) as review_count,
            SUM(CASE WHEN is_final_correct = 1 THEN 1 ELSE 0 END) as correct_count,
            ROUND(AVG(CASE WHEN is_final_correct = 1 THEN 100.0 ELSE 0 END), 2) as correct_rate,
            ROUND(AVG(CASE WHEN is_misjudge = 1 THEN 100.0 ELSE 0 END), 2) as misjudge_rate,
            ROUND(AVG(CASE WHEN is_missjudge = 1 THEN 100.0 ELSE 0 END), 2) as missjudge_rate,
            GROUP_CONCAT(DISTINCT error_type ORDER BY error_type SEPARATOR ', ') as main_errors
        FROM fact_qa_event
        WHERE biz_date = %s
          AND reviewer_name IS NOT NULL
        GROUP BY reviewer_name, queue_name
        HAVING correct_rate < %s
        ORDER BY correct_rate ASC
        LIMIT %s
        """
        
        results = db.execute_query(query, (str(target_date), threshold, limit))
        
        if not results:
            return []
        
        # 格式化结果
        ranking = []
        for idx, row in enumerate(results, start=1):
            ranking.append({
                "rank": idx,
                "reviewer_name": row[0],
                "queue_name": row[1],
                "review_count": row[2],
                "correct_count": row[3],
                "correct_rate": float(row[4]),
                "misjudge_rate": float(row[5]) if row[5] else 0.0,
                "missjudge_rate": float(row[6]) if row[6] else 0.0,
                "main_errors": row[7] or ""
            })
        
        return ranking
        
    except Exception as e:
        logger.error(f"获取审核人排行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    finally:
        db.close()


# ==================== 辅助函数 ====================

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
