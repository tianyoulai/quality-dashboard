"""
新人追踪 API 路由模块

提供新人追踪相关的数据接口：
1. 批次列表
2. 批次详情
3. 新人列表
4. 新人个人数据
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/v1/newcomers", tags=["newcomers"])
logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class BatchSummary(BaseModel):
    """批次概要信息"""
    batch_id: str
    batch_name: str
    total_people: int
    current_day: int
    total_days: int
    avg_accuracy: float
    passed_count: int
    pass_rate: float
    status: str  # active, completed, archived


class NewcomerStats(BaseModel):
    """新人统计数据"""
    name: str
    queue: str
    audit_count: int
    accuracy: float
    days: int
    status: str  # excellent, normal, warning, problem


class BatchDetail(BaseModel):
    """批次详情"""
    id: str
    name: str
    total_people: int
    current_day: int
    total_days: int
    avg_accuracy: float
    passed_count: int
    pass_rate: float
    newcomers: List[NewcomerStats]


# ==================== API 端点 ====================

@router.get("/batches")
async def get_batch_list(
    status: Optional[str] = Query(None, description="批次状态筛选: active, completed, archived")
) -> dict:
    """
    获取批次列表
    
    Args:
        status: 批次状态筛选
    
    Returns:
        批次列表数据
    """
    try:
        # TODO: 从数据库查询真实数据
        # 当前返回模拟数据
        
        batches = [
            {
                "batch_id": "2024Q1-01",
                "batch_name": "2024Q1-01 批次",
                "total_people": 60,
                "current_day": 15,
                "total_days": 21,
                "avg_accuracy": 95.3,
                "passed_count": 52,
                "pass_rate": 86.7,
                "status": "active"
            },
            {
                "batch_id": "2024Q1-02",
                "batch_name": "2024Q1-02 批次",
                "total_people": 52,
                "current_day": 8,
                "total_days": 21,
                "avg_accuracy": 93.8,
                "passed_count": 45,
                "pass_rate": 86.5,
                "status": "active"
            },
            {
                "batch_id": "2024Q1-03",
                "batch_name": "2024Q1-03 批次",
                "total_people": 44,
                "current_day": 3,
                "total_days": 21,
                "avg_accuracy": 92.5,
                "passed_count": 38,
                "pass_rate": 86.4,
                "status": "active"
            }
        ]
        
        # 状态筛选
        if status:
            batches = [b for b in batches if b["status"] == status]
        
        return {
            "ok": True,
            "data": {
                "batches": batches,
                "total": len(batches)
            }
        }
        
    except Exception as e:
        logger.exception("获取批次列表失败")
        raise HTTPException(status_code=500, detail=f"获取批次列表失败: {str(e)}")


@router.get("/batch/{batch_id}")
async def get_batch_detail(
    batch_id: str
) -> dict:
    """
    获取批次详情
    
    Args:
        batch_id: 批次ID
    
    Returns:
        批次详情数据（包含新人列表）
    """
    try:
        # TODO: 从数据库查询真实数据
        # 当前返回模拟数据
        
        if batch_id == "2024Q1-01":
            newcomers = [
                {"name": "张三", "queue": "评论_A组", "audit_count": 1234, "accuracy": 96.5, "days": 15, "status": "excellent"},
                {"name": "李四", "queue": "弹幕_B组", "audit_count": 987, "accuracy": 94.2, "days": 15, "status": "normal"},
                {"name": "王五", "queue": "评论_C组", "audit_count": 856, "accuracy": 85.5, "days": 15, "status": "problem"},
                {"name": "赵六", "queue": "账号_A组", "audit_count": 765, "accuracy": 88.2, "days": 15, "status": "warning"},
                {"name": "孙七", "queue": "评论_B组", "audit_count": 1123, "accuracy": 97.8, "days": 15, "status": "excellent"},
                {"name": "周八", "queue": "弹幕_A组", "audit_count": 945, "accuracy": 93.5, "days": 15, "status": "normal"},
                {"name": "吴九", "queue": "评论_A组", "audit_count": 1089, "accuracy": 94.8, "days": 15, "status": "normal"},
                {"name": "郑十", "queue": "账号_B组", "audit_count": 878, "accuracy": 91.2, "days": 15, "status": "normal"},
            ]
            
            batch_detail = {
                "id": batch_id,
                "name": "2024Q1-01 批次",
                "total_people": 60,
                "current_day": 15,
                "total_days": 21,
                "avg_accuracy": 95.3,
                "passed_count": 52,
                "pass_rate": 86.7,
                "newcomers": newcomers
            }
        elif batch_id == "2024Q1-02":
            newcomers = [
                {"name": "冯一", "queue": "评论_A组", "audit_count": 1045, "accuracy": 95.2, "days": 8, "status": "excellent"},
                {"name": "陈二", "queue": "弹幕_B组", "audit_count": 923, "accuracy": 93.1, "days": 8, "status": "normal"},
                {"name": "褚三", "queue": "评论_C组", "audit_count": 867, "accuracy": 89.5, "days": 8, "status": "warning"},
            ]
            
            batch_detail = {
                "id": batch_id,
                "name": "2024Q1-02 批次",
                "total_people": 52,
                "current_day": 8,
                "total_days": 21,
                "avg_accuracy": 93.8,
                "passed_count": 45,
                "pass_rate": 86.5,
                "newcomers": newcomers
            }
        elif batch_id == "2024Q1-03":
            newcomers = [
                {"name": "卫四", "queue": "评论_B组", "audit_count": 789, "accuracy": 94.3, "days": 3, "status": "normal"},
                {"name": "蒋五", "queue": "弹幕_A组", "audit_count": 845, "accuracy": 92.8, "days": 3, "status": "normal"},
            ]
            
            batch_detail = {
                "id": batch_id,
                "name": "2024Q1-03 批次",
                "total_people": 44,
                "current_day": 3,
                "total_days": 21,
                "avg_accuracy": 92.5,
                "passed_count": 38,
                "pass_rate": 86.4,
                "newcomers": newcomers
            }
        else:
            raise HTTPException(status_code=404, detail=f"批次不存在: {batch_id}")
        
        return {
            "ok": True,
            "data": batch_detail
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取批次详情失败: {batch_id}")
        raise HTTPException(status_code=500, detail=f"获取批次详情失败: {str(e)}")


@router.get("/newcomer/{name}")
async def get_newcomer_detail(
    name: str,
    batch_id: Optional[str] = Query(None, description="批次ID")
) -> dict:
    """
    获取新人详细数据
    
    Args:
        name: 新人姓名
        batch_id: 批次ID（可选）
    
    Returns:
        新人详细数据
    """
    try:
        # TODO: 从数据库查询真实数据
        # 当前返回模拟数据
        
        newcomer_data = {
            "name": name,
            "batch_id": batch_id or "2024Q1-01",
            "queue": "评论_A组",
            "join_date": "2026-03-18",
            "days": 15,
            "audit_count": 1234,
            "accuracy": 96.5,
            "misjudge_count": 43,
            "status": "excellent",
            "errors": [
                {"type": "引流判定", "count": 23, "pct": 53.5},
                {"type": "重要消息", "count": 12, "pct": 27.9},
                {"type": "低质导流", "count": 8, "pct": 18.6}
            ],
            "trend": [
                {"date": "2026-03-18", "accuracy": 92.1, "audit_count": 1050},
                {"date": "2026-03-19", "accuracy": 93.5, "audit_count": 1080},
                {"date": "2026-03-20", "accuracy": 94.2, "audit_count": 1120},
                {"date": "2026-03-21", "accuracy": 95.1, "audit_count": 1150},
                {"date": "2026-03-22", "accuracy": 96.0, "audit_count": 1180},
                {"date": "2026-03-23", "accuracy": 96.3, "audit_count": 1200},
                {"date": "2026-04-01", "accuracy": 96.5, "audit_count": 1234}
            ]
        }
        
        return {
            "ok": True,
            "data": newcomer_data
        }
        
    except Exception as e:
        logger.exception(f"获取新人详情失败: {name}")
        raise HTTPException(status_code=500, detail=f"获取新人详情失败: {str(e)}")
