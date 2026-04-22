"""Agent对话查询路由 - 通过HTTP调用后端API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import re
import logging
import httpx

router = APIRouter(prefix="/api/v1/agent", tags=["Agent对话"])
logger = logging.getLogger(__name__)

# 后端API基础URL
API_BASE = "http://localhost:8000"


class AgentQueryRequest(BaseModel):
    """Agent查询请求"""
    query: str = Field(..., description="用户的自然语言问题")
    context: Optional[Dict[str, Any]] = Field(default=None, description="上下文信息（可选）")


class AgentQueryResponse(BaseModel):
    """Agent查询响应"""
    query: str = Field(..., description="原始问题")
    intent: str = Field(..., description="识别的意图")
    answer: str = Field(..., description="自然语言回答")
    data: Optional[Dict[str, Any]] = Field(default=None, description="原始数据（可选）")
    api_called: str = Field(..., description="调用的API接口")
    timestamp: str = Field(..., description="响应时间")


def parse_intent(query: str) -> Dict[str, Any]:
    """NLU意图识别"""
    query_lower = query.lower()
    
    intent_patterns = {
        "dashboard": ["今天", "数据", "概览", "总览", "怎么样", "情况"],
        "queue_ranking": ["队列", "哪些队列", "重点队列", "关注队列"],
        "error_ranking": ["错误", "高频错误", "错误类型", "问题类型"],
        "reviewer_ranking": ["审核人", "人员", "谁需要关注", "重点人员"],
        "error_overview": ["错误总览", "最近.*错误", "错误情况"],
        "performance_trend": ["趋势", "变化", "走势", "最近.*天"],
    }
    
    matched_intent = "dashboard"
    max_score = 0
    
    for intent, keywords in intent_patterns.items():
        score = sum(1 for kw in keywords if re.search(kw, query_lower))
        if score > max_score:
            max_score = score
            matched_intent = intent
    
    params = {}
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if "今天" in query_lower:
        params["date"] = today
    elif "昨天" in query_lower:
        params["date"] = yesterday
    else:
        params["date"] = today
    
    days_match = re.search(r'最近(\d+)天', query_lower)
    if days_match:
        params["days"] = int(days_match.group(1))
    elif "最近" in query_lower:
        params["days"] = 7
    
    top_match = re.search(r'top\s*(\d+)', query_lower)
    if top_match:
        params["top_n"] = int(top_match.group(1))
    
    return {"intent": matched_intent, "params": params}


def format_dashboard_answer(data: Dict[str, Any], date: str) -> str:
    """格式化dashboard回答"""
    today = data.get("today", {})
    yesterday = data.get("yesterday", {})
    
    answer = f"📊 **{date} 质检数据播报**\n\n"
    answer += f"**核心指标**:\n"
    answer += f"- 正确率: {today.get('accuracy', 0):.1f}% "
    diff = today.get('accuracy', 0) - yesterday.get('accuracy', 0)
    answer += f"({'↑' if diff > 0 else '↓'}{abs(diff):.1f}% vs昨日)\n"
    answer += f"- 质检量: {today.get('total_count', 0)}条 "
    answer += f"(昨日{yesterday.get('total_count', 0)}条)\n"
    answer += f"- 误判率: {today.get('error_rate', 0):.1f}%\n"
    answer += f"- 漏判率: {today.get('miss_rate', 0):.1f}%\n"
    
    alerts = data.get("alerts", [])
    if alerts:
        answer += f"\n⚠️ **异常告警** ({len(alerts)}项):\n"
        for alert in alerts[:3]:
            answer += f"- {alert.get('message', '')}\n"
    
    return answer


def format_queue_ranking_answer(data: list) -> str:
    """格式化队列排行回答"""
    if not data:
        return "✅ 当前所有队列质检正确率都在90%以上，表现良好！"
    
    answer = f"⚠️ **需要重点关注的队列** (正确率<90%):\n\n"
    for i, queue in enumerate(data[:5], 1):
        answer += f"{i}. **{queue.get('queue_name', '未知')}**\n"
        answer += f"   - 正确率: {queue.get('correct_rate', 0):.1f}%\n"
        answer += f"   - 质检量: {queue.get('total_count', 0)}条\n\n"
    
    return answer


def format_error_ranking_answer(data: list, top_n: int) -> str:
    """格式化错误排行回答"""
    if not data:
        return "✅ 今日暂无错误记录！"
    
    answer = f"📊 **高频错误类型 Top {min(top_n, len(data))}**:\n\n"
    for i, error in enumerate(data[:top_n], 1):
        answer += f"{i}. **{error.get('error_type', '未知错误')}**\n"
        answer += f"   - 出现次数: {error.get('error_count', 0)}次\n"
        answer += f"   - 占比: {error.get('error_percentage', 0):.1f}%\n\n"
    
    return answer


@router.post("/query", response_model=AgentQueryResponse, summary="自然语言查询")
async def agent_query(request: AgentQueryRequest):
    """Agent对话查询接口"""
    try:
        intent_result = parse_intent(request.query)
        intent = intent_result["intent"]
        params = intent_result["params"]
        
        logger.info(f"Agent查询 - 问题: {request.query}, 意图: {intent}, 参数: {params}")
        
        data = None
        answer = ""
        api_called = ""
        
        async with httpx.AsyncClient() as client:
            if intent == "dashboard":
                api_url = f"{API_BASE}/api/v1/monitor/dashboard"
                response = await client.get(api_url, params={"date": params.get("date")})
                response.raise_for_status()
                data = response.json()
                answer = format_dashboard_answer(data, params.get("date"))
                api_called = "/api/v1/monitor/dashboard"
            
            elif intent == "queue_ranking":
                api_url = f"{API_BASE}/api/v1/monitor/queue-ranking"
                response = await client.get(api_url, params={"date": params.get("date")})
                response.raise_for_status()
                data = response.json()
                answer = format_queue_ranking_answer(data)
                api_called = "/api/v1/monitor/queue-ranking"
            
            elif intent == "error_ranking":
                api_url = f"{API_BASE}/api/v1/monitor/error-ranking"
                top_n = params.get("top_n", 10)
                response = await client.get(api_url, params={"date": params.get("date"), "limit": top_n})
                response.raise_for_status()
                data = response.json()
                answer = format_error_ranking_answer(data, top_n)
                api_called = "/api/v1/monitor/error-ranking"
            
            elif intent == "reviewer_ranking":
                api_url = f"{API_BASE}/api/v1/monitor/reviewer-ranking"
                response = await client.get(api_url, params={"date": params.get("date")})
                response.raise_for_status()
                data = response.json()
                answer = "📊 **重点关注审核人** (正确率<85%):\n\n"
                if data:
                    for i, reviewer in enumerate(data[:5], 1):
                        answer += f"{i}. {reviewer.get('reviewer_name', '未知')}: {reviewer.get('correct_rate', 0):.1f}%\n"
                else:
                    answer = "✅ 所有审核人正确率都在85%以上！"
                api_called = "/api/v1/monitor/reviewer-ranking"
            
            elif intent == "error_overview":
                api_url = f"{API_BASE}/api/v1/analysis/error-overview"
                days = params.get("days", 7)
                response = await client.get(api_url, params={"days": days, "end_date": params.get("date")})
                response.raise_for_status()
                data = response.json()
                answer = f"📊 **最近{days}天错误总览**:\n\n"
                summary = data.get("summary", {})
                answer += f"- 总错误数: {summary.get('total_errors', 0)}次\n"
                answer += f"- 日均错误: {summary.get('avg_daily_errors', 0):.1f}次\n"
                api_called = "/api/v1/analysis/error-overview"
            
            elif intent == "performance_trend":
                api_url = f"{API_BASE}/api/v1/visualization/performance-trend"
                days = params.get("days", 7)
                response = await client.get(api_url, params={"days": days, "end_date": params.get("date")})
                response.raise_for_status()
                data = response.json()
                metrics = data.get("metrics", {})
                accuracy_data = metrics.get("accuracy", [])
                if accuracy_data:
                    trend = "上升" if len(accuracy_data) >= 2 and accuracy_data[-1] > accuracy_data[0] else "下降"
                    answer = f"📈 **最近{days}天质检趋势**:\n\n"
                    answer += f"- 正确率趋势: {trend}\n"
                    answer += f"- 当前正确率: {accuracy_data[-1]:.1f}%\n"
                    answer += f"- {days}天平均: {sum(accuracy_data)/len(accuracy_data):.1f}%\n"
                else:
                    answer = f"暂无最近{days}天的数据。"
                api_called = "/api/v1/visualization/performance-trend"
            
            else:
                answer = f"抱歉，我还不太理解您的问题：'{request.query}'。\n\n请尝试这些问题：\n"
                answer += "- 今天数据怎么样？\n- 哪些队列需要关注？\n- 最近3天错误趋势？\n"
                api_called = "none"
        
        return AgentQueryResponse(
            query=request.query,
            intent=intent,
            answer=answer,
            data=data if data else {},
            api_called=api_called,
            timestamp=datetime.now().isoformat()
        )
    
    except httpx.HTTPStatusError as e:
        logger.error(f"API调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"后端API调用失败: {str(e)}")
    except Exception as e:
        logger.error(f"Agent查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/intents", summary="获取支持的意图列表")
async def get_supported_intents():
    """获取Agent支持的意图和示例问题"""
    return {
        "intents": [
            {"intent": "dashboard", "description": "查询今日质检数据概览", "examples": ["今天数据怎么样？"]},
            {"intent": "queue_ranking", "description": "查询需要关注的队列", "examples": ["哪些队列需要关注？"]},
            {"intent": "error_ranking", "description": "查询高频错误类型", "examples": ["高频错误有哪些？"]},
            {"intent": "reviewer_ranking", "description": "查询需要关注的审核人", "examples": ["哪些人需要关注？"]},
            {"intent": "error_overview", "description": "查询最近N天错误总览", "examples": ["最近7天错误情况"]},
            {"intent": "performance_trend", "description": "查询性能趋势", "examples": ["最近趋势如何？"]}
        ]
    }
