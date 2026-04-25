from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from utils.helpers import dataframe_to_records, normalize_payload
from storage.repository import DashboardRepository

repo = DashboardRepository()


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


from utils.helpers import safe_pct as _safe_pct


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
            "accuracy",
            "accuracy_gap",
            "misjudge_rate",
            "missjudge_rate",
            "issue_rate",
            "member_cnt",
            "training_days",
            "best_team_acc",
            "best_team_per_capita_acc",
            "worst_team_acc",
            "worst_team_per_capita_acc",
            "sample_gap_pct",
            "per_capita_gap_pct",
            "gap_pct",
            "top_error_share",
            "关注分",
            "p0_cnt",
            "p1_cnt",
            "team_cnt",
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
    if "sample_accuracy" not in normalized_df.columns:
        normalized_df["sample_accuracy"] = normalized_df["sample_accuracy_rate"]
    if "accuracy" not in normalized_df.columns:
        normalized_df["accuracy"] = normalized_df["sample_accuracy"]
    return normalized_df


def _display_text(value: Any, default: str = "未填写") -> str:
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def _format_name_list(values: pd.Series | list[Any], limit: int = 3, default: str = "暂无") -> str:
    cleaned: list[str] = []
    iterable = values.tolist() if isinstance(values, pd.Series) else list(values)
    for value in iterable:
        text = str(value).strip() if value is not None and not pd.isna(value) else ""
        if text and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        return default
    names = cleaned[:limit]
    suffix = f" 等{len(cleaned)}人" if len(cleaned) > limit else ""
    return "、".join(names) + suffix


def _classify_batch_risk(overall_acc: float, gap_pct: float, p0_cnt: int = 0, p1_cnt: int = 0) -> tuple[str, str, str]:
    if overall_acc < 95 or gap_pct >= 4 or p0_cnt > 0:
        return ("🔴 风险批次", "#dc2626", "#fef2f2")
    if overall_acc < 97 or gap_pct >= 2.5 or p1_cnt > 0:
        return ("🟡 关注批次", "#d97706", "#fffbeb")
    return ("🟢 稳定批次", "#059669", "#ecfdf5")


def _suggest_team_action(row: pd.Series) -> str:
    top_error_type = _display_text(row.get("top_error_type"), default="通用问题")
    top_error_share = float(row.get("top_error_share") or 0)
    missjudge_rate = float(row.get("missjudge_rate") or 0)
    misjudge_rate = float(row.get("misjudge_rate") or 0)
    accuracy = float(row.get("accuracy") or row.get("sample_accuracy") or 0)
    issue_rate = float(row.get("issue_rate") or 0)

    if missjudge_rate >= 1.5:
        return "优先做漏判复训，补边界案例抽样。"
    if misjudge_rate >= 1.5:
        return "优先统一判标口径，做错判复盘。"
    if top_error_share >= 35:
        return f"围绕“{top_error_type}”做专项复盘。"
    if accuracy < 97 or issue_rate >= 2.5:
        return "安排一对一带教，连续跟进近三天样本。"
    return "当前稳定，保持抽检观察。"


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
    result_df["accuracy"] = result_df["sample_accuracy"]
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
        "internal": "🏫 内检",
        "external": "🔍 外检",
        "formal": "✅ 正式上线",
    }).fillna("—")
    stage_df["sort_order"] = stage_df["stage"].map({"internal": 0, "external": 1, "formal": 2}).fillna(99)
    return stage_df[stage_df["sort_order"] < 99].sort_values("sort_order").drop(columns=["sort_order"])


def _build_batch_stage_summary(source_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "batch_name",
        "stage",
        "stage_label",
        "qa_cnt",
        "correct_cnt",
        "member_cnt",
        "sample_accuracy",
        "per_capita_accuracy",
        "accuracy_rate",
        "accuracy_gap",
        "misjudge_rate",
        "missjudge_rate",
        "issue_rate",
    ]
    if source_df is None or source_df.empty:
        return pd.DataFrame(columns=columns)

    stage_df = _build_dual_accuracy_group(source_df, ["batch_name", "stage"])
    if stage_df.empty:
        return pd.DataFrame(columns=columns)

    stage_df = stage_df.copy()
    stage_df["stage_label"] = stage_df["stage"].map({
        "internal": "🏫 内部质检",
        "external": "🔍 外部质检",
        "formal": "✅ 正式上线",
    }).fillna("—")
    stage_df["sort_order"] = stage_df["stage"].map({"internal": 0, "external": 1, "formal": 2}).fillna(99)
    stage_df = stage_df.sort_values(["batch_name", "sort_order", "sample_accuracy"], ascending=[True, True, False]).drop(columns=["sort_order"])
    return stage_df[columns]


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


def _build_recent_person_perf(combined_df: pd.DataFrame, members_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "reviewer_name",
        "short_name",
        "batch_name",
        "team_name",
        "team_leader",
        "delivery_pm",
        "owner",
        "mentor_name",
        "qa_cnt",
        "correct_cnt",
        "misjudge_cnt",
        "missjudge_cnt",
        "latest_date",
        "latest_stage",
        "sample_accuracy",
        "accuracy",
        "misjudge_rate",
        "missjudge_rate",
        "issue_rate",
        "risk_level",
    ]
    if combined_df is None or combined_df.empty or members_df is None or members_df.empty or "biz_date" not in combined_df.columns:
        return pd.DataFrame(columns=columns)

    recent_date = combined_df["biz_date"].max()
    if pd.isna(recent_date) or not recent_date:
        return pd.DataFrame(columns=columns)

    recent_cutoff = recent_date - timedelta(days=7)
    recent_meta_df = members_df[["reviewer_alias", "team_leader", "delivery_pm", "owner", "mentor_name"]].drop_duplicates()
    recent_qa_df = combined_df[combined_df["biz_date"] >= recent_cutoff].copy()
    if recent_qa_df.empty:
        return pd.DataFrame(columns=columns)

    recent_qa_df = recent_qa_df.merge(recent_meta_df, left_on="reviewer_name", right_on="reviewer_alias", how="left")
    recent_qa_df = recent_qa_df.fillna({
        "team_leader": "未填写",
        "delivery_pm": "未填写",
        "owner": "未填写",
        "mentor_name": "未填写",
    })

    result_df = recent_qa_df.groupby(
        ["reviewer_name", "short_name", "batch_name", "team_name", "team_leader", "delivery_pm", "owner", "mentor_name"],
        as_index=False,
    ).agg(
        qa_cnt=("qa_cnt", "sum"),
        correct_cnt=("correct_cnt", "sum"),
        misjudge_cnt=("misjudge_cnt", "sum"),
        missjudge_cnt=("missjudge_cnt", "sum"),
        latest_date=("biz_date", "max"),
    )

    latest_stage_df = recent_qa_df.sort_values(["reviewer_name", "biz_date"]).groupby("reviewer_name", as_index=False).tail(1)[["reviewer_name", "stage"]]
    latest_stage_df = latest_stage_df.rename(columns={"stage": "latest_stage"})
    result_df = result_df.merge(latest_stage_df, on="reviewer_name", how="left")
    result_df["sample_accuracy"] = result_df.apply(lambda row: _safe_pct(row.get("correct_cnt"), row.get("qa_cnt")), axis=1)
    result_df["accuracy"] = result_df["sample_accuracy"]
    result_df["misjudge_rate"] = result_df.apply(lambda row: _safe_pct(row.get("misjudge_cnt"), row.get("qa_cnt")), axis=1)
    result_df["missjudge_rate"] = result_df.apply(lambda row: _safe_pct(row.get("missjudge_cnt"), row.get("qa_cnt")), axis=1)
    result_df["issue_rate"] = (result_df["misjudge_rate"] + result_df["missjudge_rate"]).round(2)
    result_df["risk_level"] = result_df.apply(
        lambda row: "P0" if (row["accuracy"] < 90 or row["missjudge_rate"] >= 2.0)
        else ("P1" if (row["accuracy"] < 95 or row["issue_rate"] >= 2.5)
        else ("NEAR" if (row["latest_stage"] == "external" and 97.5 <= row["accuracy"] < 98) else "OK")),
        axis=1,
    )
    return result_df[columns]


def _build_batch_gap(team_accuracy_df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "batch_name",
        "team_cnt",
        "avg_team_sample_accuracy",
        "avg_team_per_capita_accuracy",
        "best_team_name",
        "best_team_acc",
        "best_team_per_capita_acc",
        "best_team_issue_rate",
        "worst_team_name",
        "worst_team_acc",
        "worst_team_per_capita_acc",
        "worst_team_issue_rate",
        "sample_gap_pct",
        "per_capita_gap_pct",
        "gap_pct",
    ]
    if team_accuracy_df is None or team_accuracy_df.empty:
        return pd.DataFrame(columns=columns)

    gap_base = team_accuracy_df.groupby("batch_name", as_index=False).agg(
        team_cnt=("team_name", "nunique"),
        avg_team_sample_accuracy=("sample_accuracy", "mean"),
        avg_team_per_capita_accuracy=("per_capita_accuracy", "mean"),
    )
    best_rows = team_accuracy_df.sort_values(["batch_name", "sample_accuracy", "per_capita_accuracy"], ascending=[True, False, False]).drop_duplicates("batch_name")
    best_rows = best_rows.rename(columns={
        "team_name": "best_team_name",
        "sample_accuracy": "best_team_acc",
        "per_capita_accuracy": "best_team_per_capita_acc",
        "issue_rate": "best_team_issue_rate",
    })[["batch_name", "best_team_name", "best_team_acc", "best_team_per_capita_acc", "best_team_issue_rate"]]
    worst_rows = team_accuracy_df.sort_values(["batch_name", "sample_accuracy", "per_capita_accuracy"], ascending=[True, True, True]).drop_duplicates("batch_name")
    worst_rows = worst_rows.rename(columns={
        "team_name": "worst_team_name",
        "sample_accuracy": "worst_team_acc",
        "per_capita_accuracy": "worst_team_per_capita_acc",
        "issue_rate": "worst_team_issue_rate",
    })[["batch_name", "worst_team_name", "worst_team_acc", "worst_team_per_capita_acc", "worst_team_issue_rate"]]

    result_df = gap_base.merge(best_rows, on="batch_name", how="left").merge(worst_rows, on="batch_name", how="left")
    result_df = _ensure_accuracy_columns(result_df)
    result_df["sample_gap_pct"] = (result_df["best_team_acc"] - result_df["worst_team_acc"]).round(2)
    result_df["per_capita_gap_pct"] = (result_df["best_team_per_capita_acc"] - result_df["worst_team_per_capita_acc"]).round(2)
    result_df["gap_pct"] = result_df["sample_gap_pct"]
    result_df["best_team_name"] = result_df["best_team_name"].fillna("—")
    result_df["worst_team_name"] = result_df["worst_team_name"].fillna("—")
    return result_df[columns]


def _build_batch_watch(
    batch_compare_df: pd.DataFrame,
    batch_gap_df: pd.DataFrame,
    recent_person_perf_df: pd.DataFrame,
) -> pd.DataFrame:
    if batch_compare_df is None or batch_compare_df.empty:
        return pd.DataFrame()

    batch_watch_df = batch_compare_df.copy()
    if not batch_gap_df.empty:
        batch_watch_df = batch_watch_df.merge(
            batch_gap_df[[
                "batch_name",
                "gap_pct",
                "sample_gap_pct",
                "per_capita_gap_pct",
                "best_team_name",
                "best_team_acc",
                "best_team_per_capita_acc",
                "worst_team_name",
                "worst_team_acc",
                "worst_team_per_capita_acc",
            ]],
            on="batch_name",
            how="left",
        )

    if recent_person_perf_df is not None and not recent_person_perf_df.empty:
        risk_focus_df = recent_person_perf_df[recent_person_perf_df["risk_level"].isin(["P0", "P1"])].copy()
        if not risk_focus_df.empty:
            risk_rank_map = {"P0": 0, "P1": 1, "NEAR": 2, "OK": 3}
            risk_focus_df["risk_rank"] = risk_focus_df["risk_level"].map(risk_rank_map)
            risk_focus_df = risk_focus_df.sort_values(["batch_name", "risk_rank", "accuracy", "issue_rate"], ascending=[True, True, True, False])
            batch_focus_df = risk_focus_df.groupby("batch_name").agg(
                focus_people=("short_name", lambda values: _format_name_list(list(values), limit=3)),
                p0_cnt=("risk_level", lambda values: int((values == "P0").sum())),
                p1_cnt=("risk_level", lambda values: int((values == "P1").sum())),
            ).reset_index()
            batch_watch_df = batch_watch_df.merge(batch_focus_df, on="batch_name", how="left")

    for column, default in {
        "gap_pct": 0,
        "sample_gap_pct": 0,
        "per_capita_gap_pct": 0,
        "p0_cnt": 0,
        "p1_cnt": 0,
        "focus_people": "暂无",
        "best_team_name": "—",
        "worst_team_name": "—",
        "best_team_acc": 0,
        "best_team_per_capita_acc": 0,
        "worst_team_acc": 0,
        "worst_team_per_capita_acc": 0,
    }.items():
        if column not in batch_watch_df.columns:
            batch_watch_df[column] = default
        else:
            batch_watch_df[column] = batch_watch_df[column].fillna(default)

    batch_watch_df = _ensure_accuracy_columns(batch_watch_df)
    batch_watch_df[["risk_label", "risk_color", "risk_bg"]] = batch_watch_df.apply(
        lambda row: pd.Series(
            _classify_batch_risk(
                float(row.get("sample_accuracy") or row.get("accuracy") or 0),
                float(row.get("sample_gap_pct") or row.get("gap_pct") or 0),
                int(row.get("p0_cnt") or 0),
                int(row.get("p1_cnt") or 0),
            )
        ),
        axis=1,
    )
    batch_watch_df["accuracy"] = batch_watch_df["sample_accuracy"]

    preferred_columns = batch_compare_df.columns.tolist() + [
        "gap_pct",
        "sample_gap_pct",
        "per_capita_gap_pct",
        "best_team_name",
        "best_team_acc",
        "best_team_per_capita_acc",
        "worst_team_name",
        "worst_team_acc",
        "worst_team_per_capita_acc",
        "focus_people",
        "p0_cnt",
        "p1_cnt",
        "risk_label",
        "risk_color",
        "risk_bg",
        "accuracy",
    ]
    output_columns: list[str] = []
    for column in preferred_columns:
        if column in batch_watch_df.columns and column not in output_columns:
            output_columns.append(column)
    return batch_watch_df[output_columns]


def _build_team_alert(
    team_accuracy_df: pd.DataFrame,
    error_summary_df: pd.DataFrame,
    batch_watch_df: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "risk_label",
        "batch_name",
        "team_name",
        "member_cnt",
        "qa_cnt",
        "sample_accuracy",
        "per_capita_accuracy",
        "accuracy",
        "accuracy_gap",
        "issue_rate",
        "misjudge_rate",
        "missjudge_rate",
        "top_error_type",
        "top_error_share",
        "关注分",
        "建议动作",
    ]
    if team_accuracy_df is None or team_accuracy_df.empty:
        return pd.DataFrame(columns=columns)

    result_df = team_accuracy_df.copy()
    if error_summary_df is not None and not error_summary_df.empty:
        team_error_focus_df = error_summary_df.groupby(["batch_name", "team_name", "error_type"], as_index=False)["error_cnt"].sum()
        team_error_total_df = team_error_focus_df.groupby(["batch_name", "team_name"], as_index=False)["error_cnt"].sum().rename(columns={"error_cnt": "team_error_cnt"})
        team_error_focus_df = team_error_focus_df.sort_values(["batch_name", "team_name", "error_cnt"], ascending=[True, True, False]).groupby(["batch_name", "team_name"], as_index=False).head(1)
        team_error_focus_df = team_error_focus_df.merge(team_error_total_df, on=["batch_name", "team_name"], how="left")
        team_error_focus_df["top_error_share"] = team_error_focus_df.apply(lambda row: _safe_pct(row.get("error_cnt"), row.get("team_error_cnt")), axis=1)
        team_error_focus_df = team_error_focus_df.rename(columns={"error_type": "top_error_type"})
        result_df = result_df.merge(
            team_error_focus_df[["batch_name", "team_name", "top_error_type", "top_error_share"]],
            on=["batch_name", "team_name"],
            how="left",
        )

    if batch_watch_df is not None and not batch_watch_df.empty and "risk_label" in batch_watch_df.columns:
        result_df = result_df.merge(batch_watch_df[["batch_name", "risk_label"]], on="batch_name", how="left")

    result_df = _ensure_accuracy_columns(result_df)
    if "risk_label" not in result_df.columns:
        result_df["risk_label"] = "🟢 稳定批次"
    else:
        result_df["risk_label"] = result_df["risk_label"].fillna("🟢 稳定批次")
    if "top_error_type" not in result_df.columns:
        result_df["top_error_type"] = "未标注"
    else:
        result_df["top_error_type"] = result_df["top_error_type"].fillna("未标注")
    if "top_error_share" not in result_df.columns:
        result_df["top_error_share"] = 0.0
    else:
        result_df["top_error_share"] = pd.to_numeric(result_df["top_error_share"], errors="coerce").fillna(0)
    result_df["关注分"] = (100 - result_df["sample_accuracy"]) + (result_df["issue_rate"] * 2) + (result_df["missjudge_rate"] * 1.5)
    result_df["accuracy"] = result_df["sample_accuracy"]
    result_df["建议动作"] = result_df.apply(_suggest_team_action, axis=1)
    result_df = result_df.sort_values(["关注分", "sample_accuracy", "issue_rate"], ascending=[False, True, False])
    return result_df[columns]


def _load_newcomer_members(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
) -> pd.DataFrame:
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
) -> pd.DataFrame:
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
) -> pd.DataFrame:
    if reviewer_aliases == []:
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
        WHERE 1 = 1
    """
    params: list[str] = []
    if batch_names:
        placeholders = ", ".join(["%s"] * len(batch_names))
        sql += f" AND n.batch_name IN ({placeholders})"
        params.extend(batch_names)
    if reviewer_aliases:
        placeholders = ", ".join(["%s"] * len(reviewer_aliases))
        sql += f" AND m.reviewer_name IN ({placeholders})"
        params.extend(reviewer_aliases)
    sql += " GROUP BY m.biz_date, m.reviewer_name, n.batch_name, n.team_name, n.reviewer_name"
    sql += " ORDER BY m.biz_date"
    return repo.fetch_df(sql, params)


def _load_newcomer_error_summary(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
) -> pd.DataFrame:
    if reviewer_aliases == []:
        return repo.fetch_df("SELECT 1 WHERE 1 = 0")

    sql = f"""
        SELECT
            n.batch_name,
            n.team_name,
            n.team_leader,
            COALESCE(NULLIF(TRIM(n.delivery_pm), ''), '未填写') AS delivery_pm,
            COALESCE(NULLIF(TRIM(n.owner), ''), '未填写') AS owner_name,
            COALESCE(NULLIF(TRIM(q.error_type), ''), '未标注') AS error_type,
            COUNT(*) AS error_cnt
        FROM fact_newcomer_qa q
        JOIN dim_newcomer_batch n
          ON {_batch_effective_join_condition("q", "n")}
        WHERE q.is_correct = 0
    """
    params: list[str] = []
    if batch_names:
        placeholders = ", ".join(["%s"] * len(batch_names))
        sql += f" AND n.batch_name IN ({placeholders})"
        params.extend(batch_names)
    if reviewer_aliases:
        placeholders = ", ".join(["%s"] * len(reviewer_aliases))
        sql += f" AND q.reviewer_name IN ({placeholders})"
        params.extend(reviewer_aliases)
    sql += " GROUP BY n.batch_name, n.team_name, n.team_leader, n.delivery_pm, n.owner, error_type ORDER BY error_cnt DESC"
    return repo.fetch_df(sql, params)


def build_newcomer_aggregate_payload(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
) -> dict[str, object]:
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

    newcomer_qa_df = _ensure_accuracy_columns(
        _load_newcomer_qa_daily(batch_names=batch_names, reviewer_aliases=reviewer_aliases)
    ) if reviewer_aliases else pd.DataFrame()
    formal_qa_df = _ensure_accuracy_columns(
        _load_formal_qa_daily(batch_names=batch_names, reviewer_aliases=reviewer_aliases)
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
    batch_stage_summary_df = _build_batch_stage_summary(combined_qa_df)
    batch_compare_df = _build_batch_compare(batch_scope_df, combined_qa_df)
    management_summary_df = _build_management_summary(combined_qa_df, members_df)
    error_summary_df = _load_newcomer_error_summary(batch_names=batch_names, reviewer_aliases=reviewer_aliases) if reviewer_aliases else pd.DataFrame()
    recent_person_perf_df = _build_recent_person_perf(combined_qa_df, members_df)
    batch_gap_df = _build_batch_gap(team_accuracy_df)
    batch_watch_df = _build_batch_watch(batch_compare_df, batch_gap_df, recent_person_perf_df)
    team_alert_df = _build_team_alert(team_accuracy_df, error_summary_df, batch_watch_df)

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
            "batch_stage_summary": int(len(batch_stage_summary_df)),
            "batch_compare": int(len(batch_compare_df)),
            "batch_gap": int(len(batch_gap_df)),
            "batch_watch": int(len(batch_watch_df)),
            "team_accuracy": int(len(team_accuracy_df)),
            "team_alert": int(len(team_alert_df)),
            "management_summary": int(len(management_summary_df)),
        },
        "overview": normalize_payload(overview_record),
        "batch_scope": dataframe_to_records(batch_scope_df),
        "training_trend": dataframe_to_records(_build_dual_accuracy_trend(newcomer_qa_df)),
        "formal_trend": dataframe_to_records(_build_dual_accuracy_trend(formal_qa_df)),
        "stage_summary": dataframe_to_records(stage_summary_df),
        "batch_stage_summary": dataframe_to_records(batch_stage_summary_df),
        "team_accuracy": dataframe_to_records(team_accuracy_df),
        "stage_team_accuracy": dataframe_to_records(stage_team_accuracy_df),
        "batch_compare": dataframe_to_records(batch_compare_df),
        "batch_gap": dataframe_to_records(batch_gap_df),
        "batch_watch": dataframe_to_records(batch_watch_df),
        "team_alert": dataframe_to_records(team_alert_df),
        "management_summary": dataframe_to_records(management_summary_df),
    }
