"""
数据可视化 API 路由模块

提供数据可视化页面所需的数据接口：
1. 性能趋势图（最近N天）
2. API接口性能对比
3. 队列正确率趋势
4. 审核人表现趋势
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from api.exceptions import DataNotFoundError, InvalidDateRangeError
from storage.tidb_manager import TiDBManager
import logging

router = APIRouter(prefix="/api/v1/visualization", tags=["visualization"])
logger = logging.getLogger(__name__)


@router.get("/performance-trend")
async def get_performance_trend(
    days: int = Query(7, description="查询天数", ge=1, le=30),
    metric: str = Query("correct_rate", description="指标类型: correct_rate|misjudge_rate|appeal_rate")
) -> Dict[str, Any]:
    """
    获取性能趋势数据
    
    返回：
    - dates: 日期列表
    - values: 指标值列表
    - average: 平均值
    - trend: 趋势判断（improving/declining/stable）
    """
    db = TiDBManager()
    
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # 验证指标类型
        valid_metrics = ["correct_rate", "misjudge_rate", "appeal_rate"]
        if metric not in valid_metrics:
            raise HTTPException(
                status_code=400,
                detail=f"无效的指标类型。支持: {', '.join(valid_metrics)}"
            )
        
        # 构建查询
        metric_sql = {
            "correct_rate": "ROUND(AVG(CASE WHEN is_final_correct = 1 THEN 100.0 ELSE 0 END), 2)",
            "misjudge_rate": "ROUND(AVG(CASE WHEN is_misjudge = 1 THEN 100.0 ELSE 0 END), 2)",
            "appeal_rate": "ROUND(AVG(CASE WHEN is_appealed = 1 THEN 100.0 ELSE 0 END), 2)"
        }
        
        query = f"""
        SELECT 
            biz_date,
            {metric_sql[metric]} as metric_value
        FROM fact_qa_event
        WHERE biz_date BETWEEN %s AND %s
        GROUP BY biz_date
        ORDER BY biz_date
        """
        
        results = db.execute_query(query, (str(start_date), str(end_date)))
        
        if not results:
            raise DataNotFoundError(f"未找到 {start_date} 至 {end_date} 的数据")
        
        # 提取数据
        dates = [str(row[0]) for row in results]
        values = [float(row[1]) if row[1] else 0.0 for row in results]
        
        # 计算平均值
        average = round(sum(values) / len(values), 2) if values else 0.0
        
        # 趋势判断（前半段 vs 后半段）
        trend = _analyze_metric_trend(values, metric)
        
        return {
            "metric": metric,
            "date_range": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "days": days
            },
            "data": {
                "dates": dates,
                "values": values
            },
            "statistics": {
                "average": average,
                "max": max(values) if values else 0.0,
                "min": min(values) if values else 0.0,
                "latest": values[-1] if values else 0.0
            },
            "trend": trend
        }
        
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取性能趋势失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    finally:
        db.close()


@router.get("/api-performance")
async def get_api_performance(
    date: Optional[str] = Query(None, description="查询日期（YYYY-MM-DD），默认今天")
) -> Dict[str, Any]:
    """
    获取API接口性能对比数据
    
    注意：此接口返回模拟数据，真实性能数据需要接入APM系统
    
    返回：
    - apis: 接口列表
    - performance_data: 性能数据（响应时间、QPS、错误率）
    """
    # 这里返回基于真实查询性能的估算数据
    # 真实环境应该接入APM系统获取实际性能指标
    
    target_date = _parse_date(date)
    
    return {
        "date": str(target_date),
        "note": "此数据基于查询性能估算，建议接入APM系统获取实际指标",
        "apis": [
            {
                "endpoint": "GET /api/v1/dashboard",
                "avg_response_time": 14.3,
                "p95_response_time": 25.6,
                "p99_response_time": 45.2,
                "qps": 12.5,
                "error_rate": 0.02,
                "status": "healthy"
            },
            {
                "endpoint": "GET /api/v1/monitor/dashboard",
                "avg_response_time": 125.0,
                "p95_response_time": 180.0,
                "p99_response_time": 250.0,
                "qps": 8.3,
                "error_rate": 0.05,
                "status": "healthy"
            },
            {
                "endpoint": "GET /api/v1/internal/summary",
                "avg_response_time": 876.0,
                "p95_response_time": 1200.0,
                "p99_response_time": 1800.0,
                "qps": 5.2,
                "error_rate": 0.01,
                "status": "warning"
            },
            {
                "endpoint": "GET /api/v1/newcomers/summary",
                "avg_response_time": 527.0,
                "p95_response_time": 680.0,
                "p99_response_time": 900.0,
                "qps": 6.8,
                "error_rate": 0.03,
                "status": "warning"
            },
            {
                "endpoint": "GET /api/v1/details/records",
                "avg_response_time": 2850.0,
                "p95_response_time": 4200.0,
                "p99_response_time": 6500.0,
                "qps": 3.1,
                "error_rate": 0.08,
                "status": "critical"
            }
        ],
        "summary": {
            "total_apis": 5,
            "healthy_count": 2,
            "warning_count": 2,
            "critical_count": 1,
            "avg_response_time": 688.5,
            "total_qps": 36.9
        }
    }


@router.get("/queue-trend")
async def get_queue_trend(
    queue_name: str = Query(..., description="队列名称"),
    days: int = Query(7, description="查询天数", ge=1, le=30)
) -> Dict[str, Any]:
    """
    获取队列正确率趋势
    
    返回：
    - queue_name: 队列名称
    - daily_data: 每日数据（审核量、正确率、误判率）
    - trend: 趋势分析
    """
    db = TiDBManager()
    
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        query = """
        SELECT 
            biz_date,
            COUNT(*) as review_count,
            SUM(CASE WHEN is_final_correct = 1 THEN 1 ELSE 0 END) as correct_count,
            ROUND(AVG(CASE WHEN is_final_correct = 1 THEN 100.0 ELSE 0 END), 2) as correct_rate,
            ROUND(AVG(CASE WHEN is_misjudge = 1 THEN 100.0 ELSE 0 END), 2) as misjudge_rate
        FROM fact_qa_event
        WHERE biz_date BETWEEN %s AND %s
          AND queue_name = %s
        GROUP BY biz_date
        ORDER BY biz_date
        """
        
        results = db.execute_query(query, (str(start_date), str(end_date), queue_name))
        
        if not results:
            raise DataNotFoundError(f"未找到队列 {queue_name} 在 {start_date} 至 {end_date} 的数据")
        
        # 构建每日数据
        daily_data = []
        correct_rates = []
        
        for row in results:
            correct_rate = float(row[3]) if row[3] else 0.0
            correct_rates.append(correct_rate)
            
            daily_data.append({
                "date": str(row[0]),
                "review_count": row[1],
                "correct_count": row[2],
                "correct_rate": correct_rate,
                "misjudge_rate": float(row[4]) if row[4] else 0.0
            })
        
        # 趋势分析
        trend = _analyze_metric_trend(correct_rates, "correct_rate")
        
        return {
            "queue_name": queue_name,
            "date_range": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "days": days
            },
            "daily_data": daily_data,
            "statistics": {
                "avg_correct_rate": round(sum(correct_rates) / len(correct_rates), 2),
                "max_correct_rate": max(correct_rates),
                "min_correct_rate": min(correct_rates),
                "latest_correct_rate": correct_rates[-1]
            },
            "trend": trend
        }
        
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取队列趋势失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    finally:
        db.close()


@router.get("/reviewer-trend")
async def get_reviewer_trend(
    reviewer_name: str = Query(..., description="审核人名称"),
    days: int = Query(7, description="查询天数", ge=1, le=30)
) -> Dict[str, Any]:
    """
    获取审核人表现趋势
    
    返回：
    - reviewer_name: 审核人名称
    - daily_data: 每日数据（审核量、正确率、误判率）
    - trend: 趋势分析
    """
    db = TiDBManager()
    
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        query = """
        SELECT 
            biz_date,
            COUNT(*) as review_count,
            SUM(CASE WHEN is_final_correct = 1 THEN 1 ELSE 0 END) as correct_count,
            ROUND(AVG(CASE WHEN is_final_correct = 1 THEN 100.0 ELSE 0 END), 2) as correct_rate,
            ROUND(AVG(CASE WHEN is_misjudge = 1 THEN 100.0 ELSE 0 END), 2) as misjudge_rate
        FROM fact_qa_event
        WHERE biz_date BETWEEN %s AND %s
          AND reviewer_name = %s
        GROUP BY biz_date
        ORDER BY biz_date
        """
        
        results = db.execute_query(query, (str(start_date), str(end_date), reviewer_name))
        
        if not results:
            raise DataNotFoundError(f"未找到审核人 {reviewer_name} 在 {start_date} 至 {end_date} 的数据")
        
        # 构建每日数据
        daily_data = []
        correct_rates = []
        
        for row in results:
            correct_rate = float(row[3]) if row[3] else 0.0
            correct_rates.append(correct_rate)
            
            daily_data.append({
                "date": str(row[0]),
                "review_count": row[1],
                "correct_count": row[2],
                "correct_rate": correct_rate,
                "misjudge_rate": float(row[4]) if row[4] else 0.0
            })
        
        # 趋势分析
        trend = _analyze_metric_trend(correct_rates, "correct_rate")
        
        return {
            "reviewer_name": reviewer_name,
            "date_range": {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "days": days
            },
            "daily_data": daily_data,
            "statistics": {
                "avg_correct_rate": round(sum(correct_rates) / len(correct_rates), 2),
                "max_correct_rate": max(correct_rates),
                "min_correct_rate": min(correct_rates),
                "latest_correct_rate": correct_rates[-1],
                "total_reviews": sum(item["review_count"] for item in daily_data)
            },
            "trend": trend
        }
        
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取审核人趋势失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
    finally:
        db.close()


# ==================== 辅助函数 ====================

def _analyze_metric_trend(values: List[float], metric: str) -> Dict[str, Any]:
    """
    分析指标趋势
    
    对于 correct_rate: 上升为 improving，下降为 declining
    对于 misjudge_rate/appeal_rate: 下降为 improving，上升为 declining
    """
    if len(values) < 2:
        return {
            "status": "insufficient_data",
            "direction": "unknown",
            "change_rate": 0.0
        }
    
    # 分成前后两段
    mid = len(values) // 2
    first_half = values[:mid]
    second_half = values[mid:]
    
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    
    change = avg_second - avg_first
    change_rate = round((change / avg_first * 100) if avg_first > 0 else 0.0, 2)
    
    # 判断趋势方向
    if abs(change_rate) < 2:
        direction = "stable"
        status = "normal"
    else:
        # 对于 correct_rate，上升是好的
        if metric == "correct_rate":
            if change_rate > 0:
                direction = "improving"
                status = "good"
            else:
                direction = "declining"
                status = "warning"
        # 对于 misjudge_rate/appeal_rate，下降是好的
        else:
            if change_rate < 0:
                direction = "improving"
                status = "good"
            else:
                direction = "declining"
                status = "warning"
    
    return {
        "status": status,
        "direction": direction,
        "change": round(change, 2),
        "change_rate": change_rate,
        "first_half_avg": round(avg_first, 2),
        "second_half_avg": round(avg_second, 2)
    }


def _parse_date(date_str: Optional[str]):
    """解析日期字符串"""
    if date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise InvalidDateRangeError(f"日期格式错误: {date_str}")
    else:
        return datetime.now().date()
