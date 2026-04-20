"""Newcomers (新人追踪) router —— 聚合、日报推送、分享链接、错误明细等全部收口在此。

对外暴露的"公有名"统一列在 __all__ 里；main.py 直接按名引用，
不走 services.newcomer_aggregates（该模块尚未迁完，不在此引入）。
"""

from __future__ import annotations

import base64
import json
import zlib
from datetime import date
from urllib.parse import urlencode

import pandas as pd
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.serializers import dataframe_to_records, normalize_payload
from services.wecom_push import send_wecom_webhook_with_split
from storage.repository import DashboardRepository


# ==================== 公有导出 ====================
# 方案A：router 内定义所有外部需要的符号为公有名，
# main.py 直接 from api.routers.newcomers import router 即可，
# 不动 services/newcomer_aggregates，最小风险。
__all__ = [
    "router",
    # 以下为前端/下游可能直接引用的工具函数（预留）:
    "NEWCOMER_SHARE_QUERY_KEY",
    "NON_NEWCOMER_PRACTICE_REVIEWERS",
    "encode_newcomer_share_query",
    "build_newcomer_detail_url",
    "build_training_daily_payload",
    "format_training_daily_markdown",
    "send_training_daily_report",
]

# ==================== 共享常量 ====================
# 详情页分享 token 的 URL 查询参数名
NEWCOMER_SHARE_QUERY_KEY = "nq"

# 正式队列人员：偶尔下线到新人队列做练习，这类样本不计入新人错误统计
NON_NEWCOMER_PRACTICE_REVIEWERS: list[str] = [
    "云雀联营-丁冠鑫",
    "云雀联营-季晨威",
    "李阳",
    "云雀联营-李阳",
    "朱明阳",
    "云雀联营-朱明阳",
    "陈洪恩",
    "云雀联营-陈洪恩",
    "云雀联营-评论-陈洪恩",
]


# ==================== 详情页分享链接 ====================
def encode_newcomer_share_query(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
    stage: str | None = None,
    risk_level: str | None = None,
    error_type: str | None = None,
    reviewer_alias: str | None = None,
    reviewer_name: str | None = None,
) -> str:
    """把筛选条件压进紧凑 token，供前端 URL 短链传递"""
    payload = {
        k: v
        for k, v in {
            "b": batch_names or None,
            "o": (owner or None),
            "t": (team_name or None),
            "s": (stage or None),
            "r": (risk_level or None),
            "e": (error_type or None),
            "a": (reviewer_alias or None),
            "n": (reviewer_name or None),
        }.items()
        if v
    }
    if not payload:
        return ""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii").rstrip("=")


def build_newcomer_detail_url(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
    stage: str | None = None,
    risk_level: str | None = None,
    error_type: str | None = None,
    reviewer_alias: str | None = None,
    reviewer_name: str | None = None,
    base_url: str | None = None,
    use_compact_query: bool = True,
) -> str:
    """构造跳到 /newcomers 详情下钻的链接"""
    base = (base_url or "").strip() or "/newcomers"
    if base and not base.startswith(("http://", "https://", "/")):
        base = "/" + base
    if use_compact_query:
        token = encode_newcomer_share_query(
            batch_names=batch_names,
            owner=owner,
            team_name=team_name,
            stage=stage,
            risk_level=risk_level,
            error_type=error_type,
            reviewer_alias=reviewer_alias,
            reviewer_name=reviewer_name,
        )
        if not token:
            return base
        return f"{base}?{NEWCOMER_SHARE_QUERY_KEY}={token}"
    # 传统长链：逐字段挂 query
    params: list[tuple[str, str]] = []
    for name in batch_names or []:
        if name:
            params.append(("batch_names", str(name)))
    if owner:
        params.append(("owner", str(owner)))
    if team_name:
        params.append(("team_name", str(team_name)))
    if stage:
        params.append(("detail_stage", str(stage)))
    if risk_level:
        params.append(("detail_risk", str(risk_level)))
    if error_type:
        params.append(("detail_error_type", str(error_type)))
    if reviewer_alias:
        params.append(("detail_reviewer_alias", str(reviewer_alias)))
    if reviewer_name:
        params.append(("detail_reviewer_name", str(reviewer_name)))
    if not params:
        return base
    return f"{base}?{urlencode(params)}"


def build_newcomer_error_type_case_sql(alias: str = "q") -> str:
    """把 fact_newcomer_qa 的 error_type 字段归一到展示友好的分类文案"""
    col = f"{alias}.error_type"
    return (
        f"CASE "
        f"WHEN {col} IS NULL OR TRIM({col}) = '' THEN '未标注' "
        f"ELSE TRIM({col}) "
        f"END"
    )


# ==================== 培训日报 markdown / 推送 ====================
def build_training_daily_payload(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
) -> dict[str, object]:
    """复用聚合逻辑，抽出日报用到的摘要字段"""
    aggregate = _build_newcomer_aggregate_payload(
        batch_names=batch_names, owner=owner, team_name=team_name
    )
    overview = aggregate.get("overview") or {}
    team_accuracy = aggregate.get("team_accuracy") or []
    team_alert = aggregate.get("team_alert") or []
    batch_watch = aggregate.get("batch_watch") or []
    management_summary = aggregate.get("management_summary") or []
    return {
        "report_date": str(date.today()),
        "filters": aggregate.get("filters") or {},
        "overview": overview,
        "team_accuracy": team_accuracy[:20],
        "team_alert": team_alert[:20],
        "batch_watch": batch_watch[:20],
        "management_summary": management_summary[:30],
        "row_count": aggregate.get("row_count") or {},
    }


def format_training_daily_markdown(payload: dict[str, object]) -> str:
    """把 training_daily payload 渲染成企微 markdown"""
    report_date = payload.get("report_date") or str(date.today())
    overview = payload.get("overview") or {}
    team_alert = payload.get("team_alert") or []
    batch_watch = payload.get("batch_watch") or []

    def _fmt_pct(value: object) -> str:
        try:
            return f"{float(value or 0):.2f}%"
        except (TypeError, ValueError):
            return "0.00%"

    lines: list[str] = []
    lines.append(f"### 📚 新人培训日报 · {report_date}")
    lines.append("")
    lines.append("**总览**")
    lines.append(
        f"> 样本量: `{int(overview.get('qa_cnt') or 0)}` · "
        f"样本正确率: `{_fmt_pct(overview.get('sample_accuracy'))}` · "
        f"人均正确率: `{_fmt_pct(overview.get('per_capita_accuracy'))}` · "
        f"参与人数: `{int(overview.get('member_cnt') or 0)}`"
    )
    lines.append("")

    if team_alert:
        lines.append("**⚠️ 需关注的团队（TOP 5）**")
        for row in team_alert[:5]:
            team = row.get("team_name") or "未知团队"
            acc = _fmt_pct(row.get("sample_accuracy") or row.get("accuracy_rate"))
            gap = _fmt_pct(row.get("accuracy_gap"))
            lines.append(f"- `{team}`：样本正确率 `{acc}`，与均值差 `{gap}`")
        lines.append("")

    if batch_watch:
        lines.append("**批次跟踪（TOP 5）**")
        for row in batch_watch[:5]:
            batch = row.get("batch_name") or "未知批次"
            risk = row.get("risk_label") or row.get("risk") or "—"
            acc = _fmt_pct(row.get("overall_acc") or row.get("sample_accuracy"))
            lines.append(f"- `{batch}`：{risk} · 整体正确率 `{acc}`")
        lines.append("")

    return "\n".join(lines).strip()


def send_training_daily_report(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
    webhook_url: str | None = None,
    detail_url: str | None = None,
    mentioned_list: list[str] | None = None,
    detail_base_url: str | None = None,
    detail_stage: str | None = None,
    detail_risk_level: str | None = None,
    detail_error_type: str | None = None,
    detail_reviewer_alias: str | None = None,
    detail_reviewer_name: str | None = None,
) -> dict[str, object]:
    """拼接 markdown 并发送到企微群"""
    payload = build_training_daily_payload(
        batch_names=batch_names, owner=owner, team_name=team_name
    )
    content = format_training_daily_markdown(payload)
    if not detail_url:
        detail_url = build_newcomer_detail_url(
            batch_names=batch_names,
            owner=owner,
            team_name=team_name,
            stage=detail_stage,
            risk_level=detail_risk_level,
            error_type=detail_error_type,
            reviewer_alias=detail_reviewer_alias,
            reviewer_name=detail_reviewer_name,
            base_url=detail_base_url,
            use_compact_query=True,
        )
    try:
        ok, message = send_wecom_webhook_with_split(
            content,
            mentioned_list=mentioned_list,
            webhook_url=webhook_url,
            title="📚 新人培训日报",
            detail_url=detail_url,
        )
        return {
            "ok": ok,
            "message": message,
            "markdown": content,
            "detail_url": detail_url,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "message": f"推送失败: {exc}",
            "markdown": content,
            "detail_url": detail_url,
        }


# ==================== 错误明细查询（分页版） ====================
def load_newcomer_error_details(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
    reviewer_alias: str | None = None,
    stage: str | None = None,
    risk_level: str | None = None,
    error_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> pd.DataFrame:
    """基于 fact_newcomer_qa 的错误明细分页查询"""
    error_type_expr = build_newcomer_error_type_case_sql("q")
    sql = f"""
        SELECT
            q.biz_date,
            q.reviewer_name,
            q.stage,
            q.queue_name,
            q.content_type,
            q.training_topic,
            q.risk_level,
            q.comment_text,
            q.raw_judgement,
            q.final_judgement,
            {error_type_expr} AS error_type,
            q.qa_note,
            q.is_correct,
            q.is_misjudge,
            q.is_missjudge,
            n.batch_name,
            n.team_name,
            n.team_leader,
            COALESCE(NULLIF(TRIM(n.owner), ''), '未填写') AS owner_name
        FROM fact_newcomer_qa q
        JOIN dim_newcomer_batch n
          ON {_batch_effective_join_condition("q", "n")}
        WHERE q.is_correct = 0
    """
    params: list[object] = []

    newcomer_columns = _get_table_columns("fact_newcomer_qa")
    if "is_practice_sample" in newcomer_columns:
        sql += " AND COALESCE(q.is_practice_sample, 0) = 0"
    if NON_NEWCOMER_PRACTICE_REVIEWERS:
        ph = ", ".join(["%s"] * len(NON_NEWCOMER_PRACTICE_REVIEWERS))
        sql += f" AND q.reviewer_name NOT IN ({ph})"
        params.extend(NON_NEWCOMER_PRACTICE_REVIEWERS)

    if batch_names:
        ph = ", ".join(["%s"] * len(batch_names))
        sql += f" AND n.batch_name IN ({ph})"
        params.extend(batch_names)
    if reviewer_alias:
        sql += " AND q.reviewer_name = %s"
        params.append(reviewer_alias)
    elif reviewer_aliases:
        ph = ", ".join(["%s"] * len(reviewer_aliases))
        sql += f" AND q.reviewer_name IN ({ph})"
        params.extend(reviewer_aliases)
    if owner:
        sql += " AND n.owner = %s"
        params.append(owner)
    if team_name:
        sql += " AND n.team_name = %s"
        params.append(team_name)
    if stage:
        sql += " AND q.stage = %s"
        params.append(stage)
    if risk_level:
        sql += " AND q.risk_level = %s"
        params.append(risk_level)
    if error_type:
        sql += f" AND {error_type_expr} = %s"
        params.append(error_type)
    if start_date:
        sql += " AND q.biz_date >= %s"
        params.append(start_date)
    if end_date:
        sql += " AND q.biz_date <= %s"
        params.append(end_date)

    sql += " ORDER BY q.biz_date DESC, q.qa_time DESC"
    sql += " LIMIT %s OFFSET %s"
    params.extend([int(limit), int(offset)])
    return repo.fetch_df(sql, params)


def load_newcomer_error_summary(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
    stage: str | None = None,
) -> pd.DataFrame:
    """供 /error-summary 接口调用，保留 stage 过滤"""
    error_type_expr = build_newcomer_error_type_case_sql("q")
    sql = f"""
        SELECT
            n.batch_name,
            n.team_name,
            n.team_leader,
            COALESCE(NULLIF(TRIM(n.delivery_pm), ''), '未填写') AS delivery_pm,
            COALESCE(NULLIF(TRIM(n.owner), ''), '未填写') AS owner_name,
            {error_type_expr} AS error_type,
            COUNT(*) AS error_cnt
        FROM fact_newcomer_qa q
        JOIN dim_newcomer_batch n
          ON {_batch_effective_join_condition("q", "n")}
        WHERE q.is_correct = 0
    """
    params: list[object] = []
    newcomer_columns = _get_table_columns("fact_newcomer_qa")
    if "is_practice_sample" in newcomer_columns:
        sql += " AND COALESCE(q.is_practice_sample, 0) = 0"
    if NON_NEWCOMER_PRACTICE_REVIEWERS:
        ph = ", ".join(["%s"] * len(NON_NEWCOMER_PRACTICE_REVIEWERS))
        sql += f" AND q.reviewer_name NOT IN ({ph})"
        params.extend(NON_NEWCOMER_PRACTICE_REVIEWERS)
    if batch_names:
        ph = ", ".join(["%s"] * len(batch_names))
        sql += f" AND n.batch_name IN ({ph})"
        params.extend(batch_names)
    if reviewer_aliases:
        ph = ", ".join(["%s"] * len(reviewer_aliases))
        sql += f" AND q.reviewer_name IN ({ph})"
        params.extend(reviewer_aliases)
    if stage:
        sql += " AND q.stage = %s"
        params.append(stage)
    sql += (
        f" GROUP BY n.batch_name, n.team_name, n.team_leader, n.delivery_pm, n.owner, {error_type_expr}"
        " ORDER BY error_cnt DESC"
    )
    return repo.fetch_df(sql, params)

router = APIRouter(prefix="/api/v1/newcomers", tags=["newcomers"])
repo = DashboardRepository()


class TrainingDailySendRequest(BaseModel):
    batch_names: list[str] | None = None
    owner: str | None = None
    team_name: str | None = None
    webhook_url: str | None = Field(default=None, description="临时覆盖的企业微信群 webhook 完整 URL")
    detail_url: str | None = Field(default=None, description="日报中附带的详情链接")
    detail_base_url: str | None = Field(default=None, description="详情跳转基址，未传则尝试读取配置")
    detail_stage: str | None = Field(default=None, description="详情页默认阶段筛选")
    detail_risk_level: str | None = Field(default=None, description="详情页默认风险等级筛选")
    detail_error_type: str | None = Field(default=None, description="详情页默认错误类型筛选")
    detail_reviewer_alias: str | None = Field(default=None, description="详情页默认审核人 alias")
    detail_reviewer_name: str | None = Field(default=None, description="详情页默认审核人展示名")
    mentioned_list: list[str] | None = Field(default=None, description="可选的企微 userId 列表")


def _build_detail_link_payload(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
    detail_base_url: str | None = None,
    detail_stage: str | None = None,
    detail_risk_level: str | None = None,
    detail_error_type: str | None = None,
    detail_reviewer_alias: str | None = None,
    detail_reviewer_name: str | None = None,
) -> dict[str, object]:
    detail_filters = normalize_payload({
        "batch_names": batch_names or [],
        "owner": owner,
        "team_name": team_name,
        "stage": detail_stage,
        "risk_level": detail_risk_level,
        "error_type": detail_error_type,
        "reviewer_alias": detail_reviewer_alias,
        "reviewer_name": detail_reviewer_name,
    })
    detail_share_token = encode_newcomer_share_query(
        batch_names=batch_names,
        owner=owner,
        team_name=team_name,
        stage=detail_stage,
        risk_level=detail_risk_level,
        error_type=detail_error_type,
        reviewer_alias=detail_reviewer_alias,
        reviewer_name=detail_reviewer_name,
    )
    return {
        "detail_filters": detail_filters,
        "detail_query_key": NEWCOMER_SHARE_QUERY_KEY,
        "detail_share_token": detail_share_token,
        "detail_url": build_newcomer_detail_url(
            batch_names=batch_names,
            owner=owner,
            team_name=team_name,
            stage=detail_stage,
            risk_level=detail_risk_level,
            error_type=detail_error_type,
            reviewer_alias=detail_reviewer_alias,
            reviewer_name=detail_reviewer_name,
            base_url=detail_base_url,
            use_compact_query=True,
        ),
        "detail_url_legacy": build_newcomer_detail_url(
            batch_names=batch_names,
            owner=owner,
            team_name=team_name,
            stage=detail_stage,
            risk_level=detail_risk_level,
            error_type=detail_error_type,
            reviewer_alias=detail_reviewer_alias,
            reviewer_name=detail_reviewer_name,
            base_url=detail_base_url,
            use_compact_query=False,
        ),
    }


def _batch_effective_start_expr(dim_alias: str = "n") -> str:
    return f"COALESCE({dim_alias}.effective_start_date, {dim_alias}.join_date)"


def _batch_effective_join_condition(fact_alias: str, dim_alias: str = "n", biz_date_field: str = "biz_date") -> str:
    start_expr = _batch_effective_start_expr(dim_alias)
    return (
        f"{fact_alias}.reviewer_name = {dim_alias}.reviewer_alias "
        f"AND {fact_alias}.{biz_date_field} >= {start_expr} "
        f"AND ({dim_alias}.effective_end_date IS NULL OR {fact_alias}.{biz_date_field} <= {dim_alias}.effective_end_date)"
    )


def _normalize_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    normalized_df = df.copy()
    for column in columns:
        if column in normalized_df.columns:
            normalized_df[column] = pd.to_numeric(normalized_df[column], errors="coerce").fillna(0)
    return normalized_df


def _safe_pct(numerator: object, denominator: object) -> float:
    denominator_value = float(denominator or 0)
    if denominator_value <= 0:
        return 0.0
    return round(float(numerator or 0) * 100.0 / denominator_value, 2)


def _empty_dual_accuracy_stats() -> dict[str, float | int]:
    return {
        "qa_cnt": 0,
        "correct_cnt": 0,
        "member_cnt": 0,
        "sample_accuracy": 0.0,
        "per_capita_accuracy": 0.0,
        "accuracy_rate": 0.0,
        "accuracy_gap": 0.0,
        "misjudge_rate": 0.0,
        "missjudge_rate": 0.0,
        "issue_rate": 0.0,
    }


def _ensure_accuracy_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df if df is not None else pd.DataFrame()
    normalized_df = _normalize_numeric_columns(
        df,
        [
            "qa_cnt",
            "correct_cnt",
            "misjudge_cnt",
            "missjudge_cnt",
            "accuracy_rate",
            "sample_accuracy_rate",
            "reviewer_accuracy_rate",
            "sample_accuracy",
            "per_capita_accuracy",
        ],
    )
    if "sample_accuracy_rate" not in normalized_df.columns:
        if "accuracy_rate" in normalized_df.columns:
            normalized_df["sample_accuracy_rate"] = normalized_df["accuracy_rate"]
        else:
            normalized_df["sample_accuracy_rate"] = normalized_df.apply(
                lambda row: _safe_pct(row.get("correct_cnt"), row.get("qa_cnt")),
                axis=1,
            )
    if "reviewer_accuracy_rate" not in normalized_df.columns:
        normalized_df["reviewer_accuracy_rate"] = normalized_df["sample_accuracy_rate"]
    if "accuracy_rate" not in normalized_df.columns:
        normalized_df["accuracy_rate"] = normalized_df["sample_accuracy_rate"]
    return normalized_df


def _join_unique_values(values: pd.Series, separator: str = ",") -> str:
    items = sorted({str(value).strip() for value in values if pd.notna(value) and str(value).strip()})
    return separator.join(items)


def _build_filtered_batch_list(members_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "batch_name",
        "join_date",
        "total_cnt",
        "leader_names",
        "delivery_pms",
        "mentor_names",
        "teams",
        "owners",
        "graduated_cnt",
        "training_cnt",
    ]
    if members_df is None or members_df.empty:
        return pd.DataFrame(columns=columns)

    return members_df.groupby("batch_name", as_index=False).agg(
        join_date=("join_date", "min"),
        total_cnt=("reviewer_name", "count"),
        leader_names=("team_leader", lambda values: _join_unique_values(values, "、")),
        delivery_pms=("delivery_pm", lambda values: _join_unique_values(values, "、")),
        mentor_names=("mentor_name", lambda values: _join_unique_values(values, "、")),
        teams=("team_name", lambda values: _join_unique_values(values, ",")),
        owners=("owner", lambda values: _join_unique_values(values, ",")),
        graduated_cnt=("status", lambda values: int((values == "graduated").sum())),
        training_cnt=("status", lambda values: int((values == "training").sum())),
    )


def _build_dual_accuracy_group(source_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if source_df is None or source_df.empty:
        return pd.DataFrame()

    reviewer_group_cols = [*group_cols, "reviewer_name", "short_name"]
    if "team_name" in source_df.columns and "team_name" not in reviewer_group_cols:
        reviewer_group_cols.append("team_name")

    agg_spec: dict[str, tuple[str, str]] = {
        "qa_cnt": ("qa_cnt", "sum"),
        "correct_cnt": ("correct_cnt", "sum"),
    }
    if "misjudge_cnt" in source_df.columns:
        agg_spec["misjudge_cnt"] = ("misjudge_cnt", "sum")
    if "missjudge_cnt" in source_df.columns:
        agg_spec["missjudge_cnt"] = ("missjudge_cnt", "sum")

    reviewer_df = source_df.groupby(reviewer_group_cols, as_index=False).agg(**agg_spec)
    reviewer_df["reviewer_accuracy_rate"] = reviewer_df.apply(
        lambda row: _safe_pct(row.get("correct_cnt"), row.get("qa_cnt")),
        axis=1,
    )
    reviewer_df["member_key"] = (
        reviewer_df["reviewer_name"].replace("", pd.NA).fillna(reviewer_df["short_name"].replace("", pd.NA)).fillna("")
    )

    group_agg: dict[str, tuple[str, str]] = {
        "qa_cnt": ("qa_cnt", "sum"),
        "correct_cnt": ("correct_cnt", "sum"),
        "member_cnt": ("member_key", "nunique"),
        "per_capita_accuracy": ("reviewer_accuracy_rate", "mean"),
    }
    if "misjudge_cnt" in reviewer_df.columns:
        group_agg["misjudge_cnt"] = ("misjudge_cnt", "sum")
    if "missjudge_cnt" in reviewer_df.columns:
        group_agg["missjudge_cnt"] = ("missjudge_cnt", "sum")

    result_df = reviewer_df.groupby(group_cols, as_index=False).agg(**group_agg)
    result_df["sample_accuracy"] = result_df.apply(lambda row: _safe_pct(row.get("correct_cnt"), row.get("qa_cnt")), axis=1)
    result_df["per_capita_accuracy"] = pd.to_numeric(result_df["per_capita_accuracy"], errors="coerce").fillna(0).round(2)
    result_df["accuracy_rate"] = result_df["sample_accuracy"]
    result_df["accuracy_gap"] = (result_df["sample_accuracy"] - result_df["per_capita_accuracy"]).round(2)
    if "misjudge_cnt" in result_df.columns:
        result_df["misjudge_rate"] = result_df.apply(lambda row: _safe_pct(row.get("misjudge_cnt"), row.get("qa_cnt")), axis=1)
    if "missjudge_cnt" in result_df.columns:
        result_df["missjudge_rate"] = result_df.apply(lambda row: _safe_pct(row.get("missjudge_cnt"), row.get("qa_cnt")), axis=1)
    if "misjudge_rate" not in result_df.columns:
        result_df["misjudge_rate"] = 0.0
    if "missjudge_rate" not in result_df.columns:
        result_df["missjudge_rate"] = 0.0
    result_df["issue_rate"] = (result_df["misjudge_rate"] + result_df["missjudge_rate"]).round(2)
    return result_df


def _build_dual_accuracy_trend(source_df: pd.DataFrame) -> pd.DataFrame:
    if source_df is None or source_df.empty:
        return pd.DataFrame(columns=["label", "primary", "secondary"])

    trend_df = _build_dual_accuracy_group(source_df, ["biz_date"])
    if trend_df.empty:
        return pd.DataFrame(columns=["label", "primary", "secondary"])

    trend_df = trend_df.copy()
    trend_df["label"] = pd.to_datetime(trend_df["biz_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    trend_df["label"] = trend_df["label"].fillna(trend_df["biz_date"].astype(str))
    trend_df["primary"] = trend_df["sample_accuracy"]
    trend_df["secondary"] = trend_df["per_capita_accuracy"]
    return trend_df.sort_values("label")[["label", "primary", "secondary"]]


def _build_stage_summary(source_df: pd.DataFrame) -> pd.DataFrame:
    if source_df is None or source_df.empty:
        return pd.DataFrame(columns=["stage", "stage_label"])

    stage_df = _build_dual_accuracy_group(source_df, ["stage"])
    if stage_df.empty:
        return pd.DataFrame(columns=["stage", "stage_label"])

    stage_df = stage_df.copy()
    stage_df["stage_label"] = stage_df["stage"].map({
        "internal": "🏫 内部质检",
        "external": "🔍 外部质检",
        "formal": "✅ 正式上线",
    }).fillna("—")
    stage_df["sort_order"] = stage_df["stage"].map({"internal": 0, "external": 1, "formal": 2}).fillna(99)
    return stage_df[stage_df["sort_order"] < 99].sort_values("sort_order").drop(columns=["sort_order"])


def _build_batch_compare(batch_meta_df: pd.DataFrame, combined_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "batch_name",
        "join_date",
        "total_cnt",
        "training_cnt",
        "graduated_cnt",
        "member_cnt",
        "qa_cnt",
        "sample_accuracy",
        "per_capita_accuracy",
        "accuracy_rate",
        "accuracy_gap",
        "issue_rate",
        "training_days",
        "best_team_name",
        "best_team_acc",
        "best_team_per_capita_acc",
        "worst_team_name",
        "worst_team_acc",
        "worst_team_per_capita_acc",
        "sample_gap_pct",
        "per_capita_gap_pct",
        "owners",
    ]
    if batch_meta_df is None or batch_meta_df.empty:
        return pd.DataFrame(columns=columns)

    comparison_df = _normalize_numeric_columns(batch_meta_df.copy(), ["total_cnt", "training_cnt", "graduated_cnt"])
    if "join_date" in comparison_df.columns:
        comparison_df["join_date"] = pd.to_datetime(comparison_df["join_date"], errors="coerce").dt.date
        comparison_df["training_days"] = comparison_df["join_date"].apply(
            lambda value: (date.today() - value).days if pd.notna(value) and value else 0
        )
    else:
        comparison_df["training_days"] = 0

    batch_accuracy_df = _build_dual_accuracy_group(combined_df, ["batch_name"]) if combined_df is not None and not combined_df.empty else pd.DataFrame()
    if not batch_accuracy_df.empty:
        comparison_df = comparison_df.merge(
            batch_accuracy_df[["batch_name", "member_cnt", "qa_cnt", "sample_accuracy", "per_capita_accuracy", "accuracy_gap", "issue_rate"]],
            on="batch_name",
            how="left",
        )
    else:
        for column in ["member_cnt", "qa_cnt", "sample_accuracy", "per_capita_accuracy", "accuracy_gap", "issue_rate"]:
            comparison_df[column] = 0

    team_accuracy_df = _build_dual_accuracy_group(combined_df, ["batch_name", "team_name"]) if combined_df is not None and not combined_df.empty else pd.DataFrame()
    if not team_accuracy_df.empty:
        best_rows = team_accuracy_df.sort_values(["batch_name", "sample_accuracy", "per_capita_accuracy"], ascending=[True, False, False]).drop_duplicates("batch_name")
        best_rows = best_rows.rename(columns={
            "team_name": "best_team_name",
            "sample_accuracy": "best_team_acc",
            "per_capita_accuracy": "best_team_per_capita_acc",
        })[["batch_name", "best_team_name", "best_team_acc", "best_team_per_capita_acc"]]
        worst_rows = team_accuracy_df.sort_values(["batch_name", "sample_accuracy", "per_capita_accuracy"], ascending=[True, True, True]).drop_duplicates("batch_name")
        worst_rows = worst_rows.rename(columns={
            "team_name": "worst_team_name",
            "sample_accuracy": "worst_team_acc",
            "per_capita_accuracy": "worst_team_per_capita_acc",
        })[["batch_name", "worst_team_name", "worst_team_acc", "worst_team_per_capita_acc"]]
        comparison_df = comparison_df.merge(best_rows, on="batch_name", how="left").merge(worst_rows, on="batch_name", how="left")
    else:
        comparison_df["best_team_name"] = "—"
        comparison_df["best_team_acc"] = 0.0
        comparison_df["best_team_per_capita_acc"] = 0.0
        comparison_df["worst_team_name"] = "—"
        comparison_df["worst_team_acc"] = 0.0
        comparison_df["worst_team_per_capita_acc"] = 0.0

    for column in [
        "member_cnt",
        "qa_cnt",
        "sample_accuracy",
        "per_capita_accuracy",
        "accuracy_gap",
        "issue_rate",
        "best_team_acc",
        "best_team_per_capita_acc",
        "worst_team_acc",
        "worst_team_per_capita_acc",
    ]:
        if column not in comparison_df.columns:
            comparison_df[column] = 0.0
        comparison_df[column] = pd.to_numeric(comparison_df[column], errors="coerce").fillna(0)

    for column in ["best_team_name", "worst_team_name", "owners"]:
        if column not in comparison_df.columns:
            comparison_df[column] = "—" if column != "owners" else "未填写"
        comparison_df[column] = comparison_df[column].fillna("—" if column != "owners" else "未填写")

    comparison_df["sample_gap_pct"] = (comparison_df["best_team_acc"] - comparison_df["worst_team_acc"]).round(2)
    comparison_df["per_capita_gap_pct"] = (comparison_df["best_team_per_capita_acc"] - comparison_df["worst_team_per_capita_acc"]).round(2)
    comparison_df["accuracy_rate"] = comparison_df["sample_accuracy"]
    comparison_df = comparison_df.sort_values(["sample_gap_pct", "sample_accuracy"], ascending=[False, True])
    return comparison_df[columns]


def _build_management_summary(combined_df: pd.DataFrame, members_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "team_leader",
        "delivery_pm",
        "owner",
        "mentor_name",
        "member_cnt",
        "qa_cnt",
        "correct_cnt",
        "sample_accuracy",
        "per_capita_accuracy",
        "accuracy_rate",
        "accuracy_gap",
        "misjudge_rate",
        "missjudge_rate",
        "issue_rate",
    ]
    if combined_df is None or combined_df.empty or members_df is None or members_df.empty:
        return pd.DataFrame(columns=columns)

    meta_df = members_df[["reviewer_alias", "team_leader", "delivery_pm", "owner", "mentor_name"]].drop_duplicates()
    management_df = combined_df.merge(meta_df, left_on="reviewer_name", right_on="reviewer_alias", how="left")
    management_df = management_df.fillna({
        "team_leader": "未填写",
        "delivery_pm": "未填写",
        "owner": "未填写",
        "mentor_name": "未填写",
    })
    result_df = _build_dual_accuracy_group(management_df, ["team_leader", "delivery_pm", "owner", "mentor_name"])
    if result_df.empty:
        return pd.DataFrame(columns=columns)
    result_df = result_df.fillna({
        "team_leader": "未填写",
        "delivery_pm": "未填写",
        "owner": "未填写",
        "mentor_name": "未填写",
    })
    return result_df[columns]


def _build_newcomer_aggregate_payload(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
    stage: str | None = None,
) -> dict[str, object]:
    # stage 目前仅作为元数据透传，实际阶段过滤在下游聚合函数内再细化
    _stage_filter = str(stage or "").strip().lower() or None
    members_df = _load_newcomer_members(batch_names=batch_names, owner=owner, team_name=team_name)
    if members_df is None:
        members_df = pd.DataFrame()
    members_df = members_df.copy()
    for column in ["team_name", "team_leader", "delivery_pm", "mentor_name", "owner"]:
        if column in members_df.columns:
            members_df[column] = members_df[column].fillna("未填写")

    reviewer_aliases = list(dict.fromkeys(
        str(value).strip()
        for value in members_df.get("reviewer_alias", pd.Series(dtype=object)).tolist()
        if str(value).strip()
    ))

    # 提取已毕业成员名单，用于正式数据精确过滤
    # 防止正式同学下线做培训测试时，其跨批次 graduated 记录导致脏 formal 数据混入培训批次
    graduated_only_aliases: list[str] = []
    if "status" in members_df.columns and "reviewer_alias" in members_df.columns:
        graduated_only_aliases = list(dict.fromkeys(
            str(row["reviewer_alias"]).strip()
            for row in members_df.to_dict("records")
            if str(row.get("status", "") or "").strip().lower() == "graduated"
            and str(row.get("reviewer_alias", "") or "").strip()
        ))

    newcomer_qa_df = _ensure_accuracy_columns(
        _load_newcomer_qa_daily(batch_names=batch_names, reviewer_aliases=reviewer_aliases)
    ) if reviewer_aliases else pd.DataFrame()
    formal_qa_df = _ensure_accuracy_columns(
        _load_formal_qa_daily(batch_names=batch_names, reviewer_aliases=reviewer_aliases, graduated_only_aliases=graduated_only_aliases or None)
    ) if reviewer_aliases else pd.DataFrame()

    combined_frames = [df for df in [newcomer_qa_df, formal_qa_df] if df is not None and not df.empty]
    combined_qa_df = pd.concat(combined_frames, ignore_index=True) if combined_frames else pd.DataFrame()
    combined_qa_df = _ensure_accuracy_columns(combined_qa_df)
    if not combined_qa_df.empty and "biz_date" in combined_qa_df.columns:
        combined_qa_df = combined_qa_df.copy()
        combined_qa_df["biz_date"] = pd.to_datetime(combined_qa_df["biz_date"], errors="coerce").dt.date

    batch_scope_df = _build_filtered_batch_list(members_df)
    overview_df = _build_dual_accuracy_group(
        combined_qa_df.assign(__scope__="selected"),
        ["__scope__"],
    ) if not combined_qa_df.empty else pd.DataFrame()
    overview_record = (
        dataframe_to_records(overview_df.drop(columns=["__scope__"], errors="ignore"))[0]
        if not overview_df.empty else _empty_dual_accuracy_stats()
    )

    team_accuracy_df = _build_dual_accuracy_group(combined_qa_df, ["batch_name", "team_name"]) if not combined_qa_df.empty else pd.DataFrame()
    stage_team_accuracy_df = _build_dual_accuracy_group(combined_qa_df, ["batch_name", "team_name", "stage"]) if not combined_qa_df.empty else pd.DataFrame()
    stage_summary_df = _build_stage_summary(combined_qa_df)
    batch_compare_df = _build_batch_compare(batch_scope_df, combined_qa_df)
    management_summary_df = _build_management_summary(combined_qa_df, members_df)

    return {
        "filters": normalize_payload({
            "batch_names": batch_names or [],
            "owner": owner,
            "team_name": team_name,
        }),
        "row_count": {
            "members": int(len(members_df)),
            "newcomer_daily": int(len(newcomer_qa_df)),
            "formal_daily": int(len(formal_qa_df)),
            "combined_daily": int(len(combined_qa_df)),
            "stage_summary": int(len(stage_summary_df)),
            "batch_compare": int(len(batch_compare_df)),
            "team_accuracy": int(len(team_accuracy_df)),
            "management_summary": int(len(management_summary_df)),
        },
        "overview": normalize_payload(overview_record),
        "batch_scope": dataframe_to_records(batch_scope_df),
        "training_trend": dataframe_to_records(_build_dual_accuracy_trend(newcomer_qa_df)),
        "formal_trend": dataframe_to_records(_build_dual_accuracy_trend(formal_qa_df)),
        "stage_summary": dataframe_to_records(stage_summary_df),
        "team_accuracy": dataframe_to_records(team_accuracy_df),
        "stage_team_accuracy": dataframe_to_records(stage_team_accuracy_df),
        "batch_compare": dataframe_to_records(batch_compare_df),
        "management_summary": dataframe_to_records(management_summary_df),
    }


def _get_table_columns(table_name: str) -> set[str]:
    try:
        columns_df = repo.fetch_df(f"SHOW COLUMNS FROM {table_name}")
        if columns_df is None or columns_df.empty or "Field" not in columns_df.columns:
            return set()
        return set(columns_df["Field"].tolist())
    except Exception:
        return set()


def _load_batch_list():
    return repo.fetch_df(
        """
        SELECT
            batch_name,
            MIN(join_date) AS join_date,
            MIN(COALESCE(effective_start_date, join_date)) AS effective_start_date,
            MAX(effective_end_date) AS effective_end_date,
            COUNT(*) AS total_cnt,
            GROUP_CONCAT(DISTINCT team_leader ORDER BY team_leader) AS leader_names,
            GROUP_CONCAT(DISTINCT delivery_pm ORDER BY delivery_pm) AS delivery_pms,
            GROUP_CONCAT(DISTINCT mentor_name ORDER BY mentor_name) AS mentor_names,
            GROUP_CONCAT(DISTINCT team_name ORDER BY team_name) AS teams,
            GROUP_CONCAT(DISTINCT owner ORDER BY owner) AS owners,
            SUM(CASE WHEN status = 'graduated' THEN 1 ELSE 0 END) AS graduated_cnt,
            SUM(CASE WHEN status = 'training' THEN 1 ELSE 0 END) AS training_cnt
        FROM dim_newcomer_batch
        GROUP BY batch_name
        ORDER BY MIN(COALESCE(effective_start_date, join_date)) DESC
        """
    )


def _load_unmatched_newcomer_rows():
    return repo.fetch_df(
        """
        SELECT reviewer_name, stage,
               COUNT(*) AS row_cnt,
               MIN(biz_date) AS start_date,
               MAX(biz_date) AS end_date
        FROM fact_newcomer_qa
        WHERE batch_name IS NULL OR batch_name = ''
        GROUP BY reviewer_name, stage
        ORDER BY row_cnt DESC, reviewer_name
        """
    )


def _load_newcomer_members(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
):
    sql = """
        SELECT batch_name, reviewer_name, reviewer_alias, join_date,
               COALESCE(effective_start_date, join_date) AS effective_start_date,
               effective_end_date,
               team_name, team_leader, delivery_pm, mentor_name, owner, status
        FROM dim_newcomer_batch
    """
    conditions: list[str] = []
    params: list[str] = []

    if batch_names:
        placeholders = ", ".join(["%s"] * len(batch_names))
        conditions.append(f"batch_name IN ({placeholders})")
        params.extend(batch_names)
    if owner:
        conditions.append("owner = %s")
        params.append(owner)
    if team_name:
        conditions.append("team_name = %s")
        params.append(team_name)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY batch_name, team_name, reviewer_name"
    return repo.fetch_df(sql, params)


def _load_newcomer_qa_daily(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
    stage: str | None = None,
):
    if reviewer_aliases == []:
        return repo.fetch_df("SELECT 1 WHERE 1 = 0")

    sql = f"""
        SELECT
            q.biz_date,
            q.reviewer_name,
            q.stage,
            n.batch_name,
            n.team_name,
            n.reviewer_name AS short_name,
            COUNT(*) AS qa_cnt,
            SUM(q.is_correct) AS correct_cnt,
            ROUND(SUM(q.is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS accuracy_rate,
            ROUND(SUM(q.is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS sample_accuracy_rate,
            ROUND(SUM(q.is_correct) * 100.0 / NULLIF(COUNT(*), 0), 2) AS reviewer_accuracy_rate,
            SUM(q.is_misjudge) AS misjudge_cnt,
            SUM(q.is_missjudge) AS missjudge_cnt
        FROM fact_newcomer_qa q
        JOIN dim_newcomer_batch n
          ON {_batch_effective_join_condition("q", "n")}
    """
    conditions: list[str] = []
    params: list[str] = []

    # 排除正式人力下线学习的样例
    newcomer_columns = _get_table_columns("fact_newcomer_qa")
    if "is_practice_sample" in newcomer_columns:
        conditions.append("COALESCE(q.is_practice_sample, 0) = 0")
    # 排除已知正式人员
    if NON_NEWCOMER_PRACTICE_REVIEWERS:
        ph = ", ".join(["%s"] * len(NON_NEWCOMER_PRACTICE_REVIEWERS))
        conditions.append(f"q.reviewer_name NOT IN ({ph})")
        params.extend(NON_NEWCOMER_PRACTICE_REVIEWERS)

    if batch_names:
        placeholders = ", ".join(["%s"] * len(batch_names))
        conditions.append(f"n.batch_name IN ({placeholders})")
        params.extend(batch_names)
    if reviewer_aliases:
        placeholders = ", ".join(["%s"] * len(reviewer_aliases))
        conditions.append(f"q.reviewer_name IN ({placeholders})")
        params.extend(reviewer_aliases)
    if stage:
        conditions.append("q.stage = %s")
        params.append(stage)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " GROUP BY q.biz_date, q.reviewer_name, q.stage, n.batch_name, n.team_name, n.reviewer_name"
    sql += " ORDER BY q.biz_date"
    return repo.fetch_df(sql, params)


def _load_formal_qa_daily(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
    graduated_only_aliases: list[str] | None = None,
):
    """加载新人正式上线后的质检数据（按批次生效时间归属后从 mart_day_auditor 查询）。

    Args:
        batch_names: 限制批次名。
        reviewer_aliases: 候选审核人列表（宽泛过滤）。
        graduated_only_aliases: 仅拉取这些人的正式数据。用于防止正式同学下线做培训测试时
            其历史/跨批次 graduated 记录导致脏 formal 数据混入培训批次。
            传入时优先以此为准，忽略 reviewer_aliases 中非 graduated 成员。
    """
    if reviewer_aliases == []:
        return repo.fetch_df("SELECT 1 WHERE 1 = 0")

    # 以 graduated_only_aliases 为准：如果指定了已毕业名单，只用这些人查正式数据
    effective_aliases = graduated_only_aliases if graduated_only_aliases else reviewer_aliases
    if not effective_aliases:
        return repo.fetch_df("SELECT 1 WHERE 1 = 0")

    sql = f"""
        SELECT
            m.biz_date,
            m.reviewer_name,
            'formal' AS stage,
            n.batch_name,
            n.team_name,
            n.reviewer_name AS short_name,
            SUM(m.qa_cnt) AS qa_cnt,
            SUM(m.raw_correct_cnt) AS correct_cnt,
            ROUND(SUM(m.raw_correct_cnt) * 100.0 / NULLIF(SUM(m.qa_cnt), 0), 2) AS accuracy_rate,
            ROUND(SUM(m.raw_correct_cnt) * 100.0 / NULLIF(SUM(m.qa_cnt), 0), 2) AS sample_accuracy_rate,
            ROUND(SUM(m.raw_correct_cnt) * 100.0 / NULLIF(SUM(m.qa_cnt), 0), 2) AS reviewer_accuracy_rate,
            SUM(m.misjudge_cnt) AS misjudge_cnt,
            SUM(m.missjudge_cnt) AS missjudge_cnt
        FROM mart_day_auditor m
        JOIN dim_newcomer_batch n
          ON {_batch_effective_join_condition("m", "n")}
        WHERE COALESCE(NULLIF(TRIM(n.status), ''), 'training') = 'graduated'
    """
    params: list[str] = []
    if batch_names:
        placeholders = ", ".join(["%s"] * len(batch_names))
        sql += f" AND n.batch_name IN ({placeholders})"
        params.extend(batch_names)
    if effective_aliases:
        placeholders = ", ".join(["%s"] * len(effective_aliases))
        sql += f" AND m.reviewer_name IN ({placeholders})"
        params.extend(effective_aliases)
    sql += " GROUP BY m.biz_date, m.reviewer_name, n.batch_name, n.team_name, n.reviewer_name"
    sql += " ORDER BY m.biz_date"
    return repo.fetch_df(sql, params)


def _load_newcomer_qa_detail(reviewer_alias: str, limit: int = 100):
    error_type_expr = build_newcomer_error_type_case_sql("q")
    return repo.fetch_df(
        f"""
        SELECT biz_date, stage, queue_name, content_type,
               training_topic, risk_level, comment_text,
               raw_judgement, final_judgement, {error_type_expr} AS error_type, qa_note,
               is_correct, is_misjudge, is_missjudge
        FROM fact_newcomer_qa q
        WHERE reviewer_name = %s
        ORDER BY biz_date DESC, qa_time DESC
        LIMIT %s
        """,
        [reviewer_alias, limit],
    )


def _load_newcomer_error_summary(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
):
    if reviewer_aliases == []:
        return repo.fetch_df("SELECT 1 WHERE 1 = 0")

    error_type_expr = build_newcomer_error_type_case_sql("q")
    sql = f"""
        SELECT
            n.batch_name,
            n.team_name,
            n.team_leader,
            COALESCE(NULLIF(TRIM(n.delivery_pm), ''), '未填写') AS delivery_pm,
            COALESCE(NULLIF(TRIM(n.owner), ''), '未填写') AS owner_name,
            {error_type_expr} AS error_type,
            COUNT(*) AS error_cnt
        FROM fact_newcomer_qa q
        JOIN dim_newcomer_batch n
          ON {_batch_effective_join_condition("q", "n")}
        WHERE q.is_correct = 0
    """
    params: list[str] = []
    # 排除正式人力下线学习的样例
    newcomer_columns = _get_table_columns("fact_newcomer_qa")
    if "is_practice_sample" in newcomer_columns:
        sql += " AND COALESCE(q.is_practice_sample, 0) = 0"
    # 排除已知正式人员
    if NON_NEWCOMER_PRACTICE_REVIEWERS:
        ph = ", ".join(["%s"] * len(NON_NEWCOMER_PRACTICE_REVIEWERS))
        sql += f" AND q.reviewer_name NOT IN ({ph})"
        params.extend(NON_NEWCOMER_PRACTICE_REVIEWERS)
    if batch_names:
        placeholders = ", ".join(["%s"] * len(batch_names))
        sql += f" AND n.batch_name IN ({placeholders})"
        params.extend(batch_names)
    if reviewer_aliases:
        placeholders = ", ".join(["%s"] * len(reviewer_aliases))
        sql += f" AND q.reviewer_name IN ({placeholders})"
        params.extend(reviewer_aliases)
    sql += f" GROUP BY n.batch_name, n.team_name, n.team_leader, n.delivery_pm, n.owner, {error_type_expr} ORDER BY error_cnt DESC"
    return repo.fetch_df(sql, params)


@router.get("/summary")
def newcomer_summary() -> dict[str, object]:
    batch_df = _load_batch_list()
    unmatched_df = _load_unmatched_newcomer_rows()
    total_people = int(batch_df["total_cnt"].sum()) if not batch_df.empty else 0
    total_batches = int(len(batch_df))
    total_teams = 0
    if not batch_df.empty and "teams" in batch_df.columns:
        teams: set[str] = set()
        for value in batch_df["teams"].dropna().tolist():
            for item in str(value).split(","):
                item = item.strip()
                if item:
                    teams.add(item)
        total_teams = len(teams)

    return {
        "ok": True,
        "data": {
            "metrics": {
                "total_people": total_people,
                "total_batches": total_batches,
                "total_teams": total_teams,
                "unmatched_rows": int(unmatched_df["row_cnt"].sum()) if not unmatched_df.empty else 0,
            },
            "batches": dataframe_to_records(batch_df),
            "unmatched": dataframe_to_records(unmatched_df),
        },
    }


@router.get("/members")
def newcomer_members(
    batch_names: list[str] | None = Query(default=None),
    owner: str | None = Query(default=None),
    team_name: str | None = Query(default=None),
) -> dict[str, object]:
    members_df = _load_newcomer_members(batch_names=batch_names, owner=owner, team_name=team_name)
    return {
        "ok": True,
        "data": {
            "filters": normalize_payload({
                "batch_names": batch_names or [],
                "owner": owner,
                "team_name": team_name,
            }),
            "row_count": int(len(members_df)),
            "items": dataframe_to_records(members_df),
        },
    }


@router.get("/qa-daily")
def newcomer_qa_daily(
    batch_names: list[str] | None = Query(default=None),
    reviewer_aliases: list[str] | None = Query(default=None),
    stage: str | None = Query(default=None, description="internal / external"),
) -> dict[str, object]:
    qa_df = _load_newcomer_qa_daily(batch_names=batch_names, reviewer_aliases=reviewer_aliases, stage=stage)
    return {
        "ok": True,
        "data": {
            "filters": normalize_payload({
                "batch_names": batch_names or [],
                "reviewer_aliases": reviewer_aliases or [],
                "stage": stage,
            }),
            "row_count": int(len(qa_df)),
            "items": dataframe_to_records(qa_df),
        },
    }


@router.get("/formal-daily")
def newcomer_formal_daily(
    batch_names: list[str] | None = Query(default=None),
    reviewer_aliases: list[str] = Query(..., description="正式上线阶段使用的审核人别名列表"),
    graduated_only_aliases: list[str] | None = Query(default=None, description="仅拉取这些人的正式数据，防止非毕业人员污染正式阶段"),
) -> dict[str, object]:
    qa_df = _load_formal_qa_daily(batch_names=batch_names, reviewer_aliases=reviewer_aliases, graduated_only_aliases=graduated_only_aliases)
    return {
        "ok": True,
        "data": {
            "filters": normalize_payload({
                "batch_names": batch_names or [],
                "reviewer_aliases": reviewer_aliases,
                "graduated_only_aliases": graduated_only_aliases or [],
            }),
            "row_count": int(len(qa_df)),
            "items": dataframe_to_records(qa_df),
        },
    }


@router.get("/aggregates")
def newcomer_aggregates(
    batch_names: list[str] | None = Query(default=None),
    owner: str | None = Query(default=None),
    team_name: str | None = Query(default=None),
    stage: str | None = Query(default=None, description="按阶段过滤: internal / external / formal"),
) -> dict[str, object]:
    return {
        "ok": True,
        "data": _build_newcomer_aggregate_payload(batch_names=batch_names, owner=owner, team_name=team_name, stage=stage),
    }


@router.get("/person-detail")
def newcomer_person_detail(
    reviewer_alias: str = Query(..., description="系统审核人别名，含前缀"),
    limit: int = Query(default=80, ge=1, le=500),
) -> dict[str, object]:
    detail_df = _load_newcomer_qa_detail(reviewer_alias, limit=limit)
    return {
        "ok": True,
        "data": {
            "filters": normalize_payload({"reviewer_alias": reviewer_alias, "limit": limit}),
            "row_count": int(len(detail_df)),
            "items": dataframe_to_records(detail_df),
        },
    }


@router.get("/error-summary")
def newcomer_error_summary(
    batch_names: list[str] | None = Query(default=None),
    reviewer_aliases: list[str] | None = Query(default=None),
    stage: str | None = Query(default=None, description="internal / external / formal"),
) -> dict[str, object]:
    error_df = load_newcomer_error_summary(batch_names=batch_names, reviewer_aliases=reviewer_aliases, stage=stage)
    return {
        "ok": True,
        "data": {
            "filters": normalize_payload({
                "batch_names": batch_names or [],
                "reviewer_aliases": reviewer_aliases or [],
                "stage": stage,
            }),
            "row_count": int(len(error_df)),
            "items": dataframe_to_records(error_df),
        },
    }


@router.get("/training-daily")
def newcomer_training_daily(
    batch_names: list[str] | None = Query(default=None),
    owner: str | None = Query(default=None),
    team_name: str | None = Query(default=None),
    detail_base_url: str | None = Query(default=None),
    detail_stage: str | None = Query(default=None),
    detail_risk_level: str | None = Query(default=None),
    detail_error_type: str | None = Query(default=None),
    detail_reviewer_alias: str | None = Query(default=None),
    detail_reviewer_name: str | None = Query(default=None),
) -> dict[str, object]:
    payload = build_training_daily_payload(batch_names=batch_names, owner=owner, team_name=team_name)
    return {
        "ok": True,
        "data": {
            "payload": payload,
            **_build_detail_link_payload(
                batch_names=batch_names,
                owner=owner,
                team_name=team_name,
                detail_base_url=detail_base_url,
                detail_stage=detail_stage,
                detail_risk_level=detail_risk_level,
                detail_error_type=detail_error_type,
                detail_reviewer_alias=detail_reviewer_alias,
                detail_reviewer_name=detail_reviewer_name,
            ),
        },
    }


@router.get("/training-daily/markdown")
def newcomer_training_daily_markdown(
    batch_names: list[str] | None = Query(default=None),
    owner: str | None = Query(default=None),
    team_name: str | None = Query(default=None),
    detail_base_url: str | None = Query(default=None),
    detail_stage: str | None = Query(default=None),
    detail_risk_level: str | None = Query(default=None),
    detail_error_type: str | None = Query(default=None),
    detail_reviewer_alias: str | None = Query(default=None),
    detail_reviewer_name: str | None = Query(default=None),
) -> dict[str, object]:
    payload = build_training_daily_payload(batch_names=batch_names, owner=owner, team_name=team_name)
    return {
        "ok": True,
        "data": {
            "payload": payload,
            "markdown": format_training_daily_markdown(payload),
            **_build_detail_link_payload(
                batch_names=batch_names,
                owner=owner,
                team_name=team_name,
                detail_base_url=detail_base_url,
                detail_stage=detail_stage,
                detail_risk_level=detail_risk_level,
                detail_error_type=detail_error_type,
                detail_reviewer_alias=detail_reviewer_alias,
                detail_reviewer_name=detail_reviewer_name,
            ),
        },
    }


@router.get("/error-details")
def newcomer_error_details(
    batch_names: list[str] | None = Query(default=None),
    reviewer_aliases: list[str] | None = Query(default=None),
    owner: str | None = Query(default=None),
    team_name: str | None = Query(default=None),
    reviewer_alias: str | None = Query(default=None, description="单个审核人别名，优先精确过滤"),
    stage: str | None = Query(default=None, description="internal / external / formal"),
    risk_level: str | None = Query(default=None),
    error_type: str | None = Query(default=None),
    start_date: str | None = Query(default=None, description="起始日期 (YYYY-MM-DD)"),
    end_date: str | None = Query(default=None, description="截止日期 (YYYY-MM-DD)"),
    detail_base_url: str | None = Query(default=None),
    reviewer_name: str | None = Query(default=None, description="详情页跳转时使用的审核人展示名"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    fetch_limit = limit + 1
    offset = (page - 1) * limit
    detail_df = load_newcomer_error_details(
        batch_names=batch_names,
        reviewer_aliases=reviewer_aliases,
        owner=owner,
        team_name=team_name,
        reviewer_alias=reviewer_alias,
        stage=stage,
        risk_level=risk_level,
        error_type=error_type,
        start_date=start_date,
        end_date=end_date,
        limit=fetch_limit,
        offset=offset,
    )
    has_more = len(detail_df) > limit if detail_df is not None else False
    if detail_df is None:
        detail_df = pd.DataFrame()
    if has_more:
        detail_df = detail_df.head(limit)
    if not detail_df.empty and "comment_text" in detail_df.columns:
        detail_df = detail_df.copy()
        detail_df["content_snippet"] = detail_df["comment_text"].fillna("").astype(str).str.slice(0, 80)

    return {
        "ok": True,
        "data": {
            "filters": normalize_payload({
                "batch_names": batch_names or [],
                "reviewer_aliases": reviewer_aliases or [],
                "owner": owner,
                "team_name": team_name,
                "reviewer_alias": reviewer_alias,
                "reviewer_name": reviewer_name,
                "stage": stage,
                "risk_level": risk_level,
                "error_type": error_type,
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "limit": limit,
            }),
            "row_count": int(len(detail_df)),
            "has_more": has_more,
            "items": dataframe_to_records(detail_df),
            **_build_detail_link_payload(
                batch_names=batch_names,
                owner=owner,
                team_name=team_name,
                detail_base_url=detail_base_url,
                detail_stage=stage,
                detail_risk_level=risk_level,
                detail_error_type=error_type,
                detail_reviewer_alias=reviewer_alias,
                detail_reviewer_name=reviewer_name,
            ),
        },
    }


@router.post("/training-daily/test-send")
def newcomer_training_daily_test_send(payload: TrainingDailySendRequest) -> dict[str, object]:
    result = send_training_daily_report(
        batch_names=payload.batch_names,
        owner=payload.owner,
        team_name=payload.team_name,
        webhook_url=payload.webhook_url,
        detail_url=payload.detail_url,
        mentioned_list=payload.mentioned_list,
        detail_base_url=payload.detail_base_url,
        detail_stage=payload.detail_stage,
        detail_risk_level=payload.detail_risk_level,
        detail_error_type=payload.detail_error_type,
        detail_reviewer_alias=payload.detail_reviewer_alias,
        detail_reviewer_name=payload.detail_reviewer_name,
    )
    return {
        "ok": bool(result.get("ok")),
        "data": result,
    }
