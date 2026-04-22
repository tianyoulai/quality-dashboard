"""Bad Case 库路由 — 外部投诉反馈 + 复盘案例"""
from __future__ import annotations

from pathlib import Path
import pandas as pd
from fastapi import APIRouter, Query
from typing import Optional
import math

router = APIRouter(prefix="/api/v1/badcase", tags=["badcase"])

BADCASE_DIR = Path(__file__).resolve().parents[2] / "data" / "badcase"

# 列名映射（原始 → 标准化）
COL_MAP = {
    "            ": "complaint_date",   # 第一列，日期
    "投诉人": "complainant",
    "动态id": "dynamic_id",
    "评论id": "comment_id",
    "评论内容": "comment_text",
    "错误类型": "error_type",
    "正确答案": "correct_answer",
    "姓名": "reviewer_name",
    "复盘原因": "review_reason",
    "案例截图": "screenshot",
    "质培侧案例分析": "qa_analysis",
    "业务组长": "team_lead",
    "反馈队列": "queue_name",
    "连续三个月被投诉次数": "repeated_complaint_cnt",
    "近7天质量数据\n（准确率、top3标签、bad case队列）": "recent_quality_data",
    "是否进行内部抽检\n（和常态数据对比，>98%抽检，不达标<98% 直接复培）": "has_internal_check",
    "抽检量级&抽检数据\n（抽检量级：被投诉当日 100-200，明显出错）": "check_data",
    "抽检出错分析\n（薄弱标签、质量情况）": "error_analysis",
    "跟进动作\n（内检>98%单点纠偏、\n95%-98%标签培训+验收、95%下线跟进）": "follow_up_action",
    "验收摸底\n（单标签：浅显+深度，共计40题，全标签2题，薄弱标签加题，达成要求：错误数≤4）": "acceptance_test",
    "持续观察数据\n(复培上线后三天)": "observation_data",
    "备注": "note",
}


import re as _re

def _extract_review_reason(raw: str | None) -> dict:
    """从复盘原因字段提取结构化字段，兼容两种格式：
    
    格式A（老格式）：
      一审标注时间：xxx 一审姓名：xxx 一审选项：xxx
      一审思路：xxx（一段，无"正确思路"分节）
      后续待跟进内容：xxx
    
    格式B（新格式）：
      一审标注时间：xxx 一审姓名：xxx 一审选项：正常 正常选项：低俗
      一审思路:xxx
      正确思路：xxx
      后续措施：xxx
    """
    empty = {"reviewer_time": None, "reviewer_name_parsed": None,
             "reviewer_choice": None, "correct_choice": None,
             "thinking": None, "correct_thinking": None, "action": None}

    if not raw or str(raw).strip() in ("", "nan", "None"):
        return empty

    text = str(raw).strip()

    # 一审时间（格式：12月10日 / 2026-04-15 / 04月14日）
    m = _re.search(r"一审标注时间[：:]\s*([^\n\s一]{4,25})", text)
    reviewer_time = m.group(1).strip() if m else None

    # 一审姓名
    m = _re.search(r"一审姓名[：:]\s*(\S+)", text)
    reviewer_name_parsed = m.group(1).strip() if m else None

    # 一审选项
    m = _re.search(r"一审选项[：:]\s*(\S+)", text)
    reviewer_choice = m.group(1).strip() if m else None

    # 正确选项（格式B 特有）
    m = _re.search(r"(?:正常选项|正确选项)[：:]\s*(\S+)", text)
    correct_choice = m.group(1).strip() if m else None

    # 一审思路：一直到「正确思路」或「后续」结束
    m = _re.search(
        r"一审思路[：:]\s*(.*?)(?=正确思路[：:]|后续(?:措施|待跟进)[内容]*[：:]|$)",
        text, _re.DOTALL
    )
    thinking = m.group(1).strip() if m else None
    if thinking:
        thinking = thinking[:250]

    # 正确思路（格式B）
    m = _re.search(
        r"正确思路[：:]\s*(.*?)(?=后续(?:措施|待跟进)|$)",
        text, _re.DOTALL
    )
    correct_thinking = m.group(1).strip()[:250] if m else None

    # 后续措施 / 后续待跟进内容
    m = _re.search(
        r"(?:后续措施|后续待跟进[内容]*)[：:]\s*(.*?)$",
        text, _re.DOTALL
    )
    action = m.group(1).strip()[:400] if m else None

    return {
        "reviewer_time": reviewer_time,
        "reviewer_name_parsed": reviewer_name_parsed,
        "reviewer_choice": reviewer_choice,
        "correct_choice": correct_choice,
        "thinking": thinking,
        "correct_thinking": correct_thinking,
        "action": action,
    }


def _load_all() -> pd.DataFrame:
    """加载所有 bad case 文件，合并返回"""
    frames = []
    for f in BADCASE_DIR.glob("*.xlsx"):
        try:
            df = pd.read_excel(f, sheet_name=0, engine="calamine", dtype=str)
            # 重命名列
            rename_map = {k: v for k, v in COL_MAP.items() if k in df.columns}
            df = df.rename(columns=rename_map)
            # 只保留有 complainant 的行（过滤空行）
            if "complainant" in df.columns:
                df = df[df["complainant"].notna() & (df["complainant"].str.strip() != "")]
            frames.append(df)
        except Exception:
            pass
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    # 清理 reviewer_name：去掉 "ilabelsec|" 前缀
    if "reviewer_name" in merged.columns:
        merged["reviewer_name"] = (
            merged["reviewer_name"]
            .astype(str)
            .str.replace(r"^ilabelsec\|", "", regex=True)
            .str.strip()
        )
    # complaint_date 转字符串
    if "complaint_date" in merged.columns:
        merged["complaint_date"] = pd.to_datetime(
            merged["complaint_date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
    return merged


@router.get("/list")
def list_badcases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    error_type: Optional[str] = Query(None),
    queue_name: Optional[str] = Query(None),
    reviewer_name: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
):
    """分页查询 bad case 列表"""
    df = _load_all()
    if df.empty:
        return {"ok": True, "data": {"items": [], "total": 0, "page": page, "page_size": page_size}}

    # 筛选
    if error_type:
        df = df[df.get("error_type", pd.Series(dtype=str)).str.contains(error_type, na=False)]
    if queue_name:
        df = df[df.get("queue_name", pd.Series(dtype=str)).str.contains(queue_name, na=False)]
    if reviewer_name:
        df = df[df.get("reviewer_name", pd.Series(dtype=str)).str.contains(reviewer_name, na=False)]
    if keyword:
        text_cols = ["comment_text", "review_reason", "qa_analysis", "correct_answer"]
        mask = pd.Series(False, index=df.index)
        for col in text_cols:
            if col in df.columns:
                mask |= df[col].astype(str).str.contains(keyword, na=False)
        df = df[mask]

    total = len(df)
    # 按日期倒序
    if "complaint_date" in df.columns:
        df = df.sort_values("complaint_date", ascending=False)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_df = df.iloc[start:end]

    keep_cols = [
        "complaint_date", "complainant", "error_type", "correct_answer",
        "reviewer_name", "queue_name", "comment_text", "review_reason",
        "qa_analysis", "follow_up_action", "repeated_complaint_cnt",
        "has_internal_check", "check_data", "error_analysis",
    ]
    out_cols = [c for c in keep_cols if c in page_df.columns]
    raw_items = page_df[out_cols].where(pd.notna(page_df[out_cols]), None).to_dict(orient="records")

    # 对 review_reason 做结构化拆解
    items = []
    for row in raw_items:
        parsed = _extract_review_reason(row.get("review_reason"))
        row["reviewer_time"] = parsed["reviewer_time"]
        row["reviewer_name_parsed"] = parsed["reviewer_name_parsed"]
        row["reviewer_choice"] = parsed["reviewer_choice"]
        row["correct_choice"] = parsed["correct_choice"]
        row["review_thinking"] = parsed["thinking"]
        row["correct_thinking"] = parsed["correct_thinking"]
        row["review_action"] = parsed["action"]
        items.append(row)

    return {
        "ok": True,
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size),
        },
    }


@router.get("/stats")
def get_stats():
    """Bad case 统计摘要"""
    df = _load_all()
    if df.empty:
        return {"ok": True, "data": {}}

    stats: dict = {
        "total": len(df),
        "error_type_dist": [],
        "queue_dist": [],
        "reviewer_dist": [],
        "date_range": {},
    }

    if "error_type" in df.columns:
        et = df["error_type"].value_counts().head(10)
        stats["error_type_dist"] = [{"label": k, "cnt": int(v)} for k, v in et.items()]

    if "queue_name" in df.columns:
        qd = df["queue_name"].dropna().value_counts().head(10)
        stats["queue_dist"] = [{"label": k, "cnt": int(v)} for k, v in qd.items()]

    if "reviewer_name" in df.columns:
        rd = df["reviewer_name"].dropna().value_counts().head(10)
        stats["reviewer_dist"] = [{"label": k, "cnt": int(v)} for k, v in rd.items()]

    if "complaint_date" in df.columns:
        dates = df["complaint_date"].dropna()
        if len(dates):
            stats["date_range"] = {"min": dates.min(), "max": dates.max()}

    return {"ok": True, "data": stats}


@router.get("/filters")
def get_filters():
    """获取可用筛选项"""
    df = _load_all()
    if df.empty:
        return {"ok": True, "data": {"error_types": [], "queues": [], "reviewers": []}}

    return {
        "ok": True,
        "data": {
            "error_types": sorted(df["error_type"].dropna().unique().tolist()) if "error_type" in df.columns else [],
            "queues": sorted(df["queue_name"].dropna().unique().tolist()) if "queue_name" in df.columns else [],
            "reviewers": sorted(df["reviewer_name"].dropna().unique().tolist()) if "reviewer_name" in df.columns else [],
        },
    }
