"""新人追踪页：批次管理 + 成长曲线 + 阶段对比 + 个人追踪 + 维度分析 + 异常告警。

数据来源：
- dim_newcomer_batch: 新人映射表（姓名→批次→基地/团队→联营管理→交付PM→质培owner→导师/质检）
- fact_newcomer_qa: 新人质检明细（内检+外检，独立存储）
- fact_qa_event + mart_day_auditor: 正式上线后的质检数据（通过 reviewer_name 关联）

阶段识别规则：
- 内部质检: 文件队列含"新人评论测试" 或 文件名含"新人"
- 外部质检: 文件名含"10816"
- 正式上线: 走正常队列，审核人名出现在 dim_newcomer_batch 中
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from services.newcomer_aggregates import build_newcomer_aggregate_payload
from storage.repository import DashboardRepository

st.set_page_config(page_title="质培运营看板-新人追踪", page_icon="👶", layout="wide")

# 全局CSS
st.markdown("""
<style>
    .main > div { padding-top: 1rem; }
    .stDataFrame { border-radius: 0.75rem; overflow: hidden; border: 1px solid #E5E7EB; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { margin-bottom: 0.5rem; }
    h3 { margin-top: 1.5rem; margin-bottom: 1rem; }
    hr { margin: 1.5rem 0; border-color: #E5E7EB; }
</style>
""", unsafe_allow_html=True)

repo = DashboardRepository()


@st.cache_data(show_spinner=False, ttl=300)
def load_newcomer_aggregate_payload(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
) -> dict[str, object]:
    return build_newcomer_aggregate_payload(batch_names=batch_names, owner=owner, team_name=team_name)


@st.cache_data(show_spinner=False, ttl=600)
def get_table_columns(table_name: str) -> set[str]:
    """读取表结构字段，便于兼容历史库和做维度可用性判断。"""
    try:
        columns_df = repo.fetch_df(f"SHOW COLUMNS FROM {table_name}")
        return set(columns_df["Field"].tolist()) if columns_df is not None and not columns_df.empty else set()
    except Exception:
        return set()


def batch_effective_start_expr(dim_alias: str = "n") -> str:
    return f"COALESCE({dim_alias}.effective_start_date, {dim_alias}.join_date)"


def batch_effective_join_condition(fact_alias: str, dim_alias: str = "n", biz_date_field: str = "biz_date") -> str:
    start_expr = batch_effective_start_expr(dim_alias)
    return (
        f"{fact_alias}.reviewer_name = {dim_alias}.reviewer_alias "
        f"AND {fact_alias}.{biz_date_field} >= {start_expr} "
        f"AND ({dim_alias}.effective_end_date IS NULL OR {fact_alias}.{biz_date_field} <= {dim_alias}.effective_end_date)"
    )


@st.cache_resource(show_spinner=False)
def ensure_newcomer_schema() -> bool:
    """确保新人相关表具备最新字段，避免历史库结构落后导致页面报错。"""
    try:
        batch_columns = get_table_columns("dim_newcomer_batch")
        if "effective_start_date" not in batch_columns:
            repo.execute("ALTER TABLE dim_newcomer_batch ADD COLUMN effective_start_date DATE COMMENT '批次归属生效开始日期（默认同 join_date）' AFTER join_date")
        if "effective_end_date" not in batch_columns:
            repo.execute("ALTER TABLE dim_newcomer_batch ADD COLUMN effective_end_date DATE COMMENT '批次归属生效结束日期（为空表示仍在该批次口径内）' AFTER effective_start_date")
        if "delivery_pm" not in batch_columns:
            repo.execute("ALTER TABLE dim_newcomer_batch ADD COLUMN delivery_pm VARCHAR(128) COMMENT '交付PM' AFTER team_leader")

        newcomer_columns = get_table_columns("fact_newcomer_qa")
        if "content_type" not in newcomer_columns:
            repo.execute("ALTER TABLE fact_newcomer_qa ADD COLUMN content_type VARCHAR(128) COMMENT '内容类型' AFTER queue_name")
        if "risk_level" not in newcomer_columns:
            repo.execute("ALTER TABLE fact_newcomer_qa ADD COLUMN risk_level VARCHAR(64) COMMENT '风险等级' AFTER error_type")
        if "training_topic" not in newcomer_columns:
            repo.execute("ALTER TABLE fact_newcomer_qa ADD COLUMN training_topic VARCHAR(256) COMMENT '培训专题' AFTER risk_level")
        if "is_practice_sample" not in newcomer_columns:
            repo.execute("ALTER TABLE fact_newcomer_qa ADD COLUMN is_practice_sample TINYINT(1) DEFAULT 0 COMMENT '是否正式人力下线学习样例（1=是 0=否）' AFTER is_missjudge")
        return True
    except Exception:
        return False


def normalize_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """将数据库返回的 Decimal / 字符串数值统一转成可计算的数值类型。"""
    if df is None or df.empty:
        return df
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def safe_pct(numerator, denominator) -> float:
    denominator = float(denominator or 0)
    if denominator <= 0:
        return 0.0
    return round(float(numerator or 0) * 100.0 / denominator, 2)


def ensure_accuracy_columns(df: pd.DataFrame) -> pd.DataFrame:
    """统一补齐样本正确率/人均口径所需列，并保留旧 accuracy_rate 兼容字段。"""
    if df is None:
        df = pd.DataFrame()
    else:
        df = df.copy()

    numeric_columns = [
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
        "member_cnt",
        "training_days",
    ]
    for column in numeric_columns:
        if column not in df.columns:
            df[column] = 0

    df = normalize_numeric_columns(df, numeric_columns)
    if df.empty:
        return df
    if "sample_accuracy_rate" not in df.columns:
        if "accuracy_rate" in df.columns:
            df["sample_accuracy_rate"] = df["accuracy_rate"]
        else:
            df["sample_accuracy_rate"] = df.apply(lambda r: safe_pct(r.get("correct_cnt"), r.get("qa_cnt")), axis=1)
    if "reviewer_accuracy_rate" not in df.columns:
        df["reviewer_accuracy_rate"] = df["sample_accuracy_rate"]
    if "accuracy_rate" not in df.columns:
        df["accuracy_rate"] = df["sample_accuracy_rate"]
    if "sample_accuracy" not in df.columns:
        df["sample_accuracy"] = df["sample_accuracy_rate"]
    if "accuracy" not in df.columns:
        df["accuracy"] = df["sample_accuracy"]
    return df


def build_dual_accuracy_group(
    source_df: pd.DataFrame,
    group_cols: list[str],
    extra_agg: dict[str, tuple[str, str]] | None = None,
) -> pd.DataFrame:
    """聚合层同时产出样本正确率和人均正确率。"""
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
    if extra_agg:
        agg_spec.update(extra_agg)

    reviewer_df = source_df.groupby(reviewer_group_cols, as_index=False).agg(**agg_spec)
    reviewer_df["reviewer_accuracy_rate"] = reviewer_df.apply(
        lambda r: safe_pct(r.get("correct_cnt"), r.get("qa_cnt")),
        axis=1,
    )
    reviewer_df["member_key"] = reviewer_df["reviewer_name"].fillna(reviewer_df["short_name"])

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

    result = reviewer_df.groupby(group_cols, as_index=False).agg(**group_agg)
    result["sample_accuracy"] = result.apply(lambda r: safe_pct(r.get("correct_cnt"), r.get("qa_cnt")), axis=1)
    result["per_capita_accuracy"] = pd.to_numeric(result["per_capita_accuracy"], errors="coerce").fillna(0).round(2)
    result["accuracy"] = result["sample_accuracy"]
    result["accuracy_gap"] = (result["sample_accuracy"] - result["per_capita_accuracy"]).round(2)
    if "misjudge_cnt" in result.columns:
        result["misjudge_rate"] = result.apply(lambda r: safe_pct(r.get("misjudge_cnt"), r.get("qa_cnt")), axis=1)
    if "missjudge_cnt" in result.columns:
        result["missjudge_rate"] = result.apply(lambda r: safe_pct(r.get("missjudge_cnt"), r.get("qa_cnt")), axis=1)
    if "misjudge_rate" not in result.columns:
        result["misjudge_rate"] = 0.0
    if "missjudge_rate" not in result.columns:
        result["missjudge_rate"] = 0.0
    result["issue_rate"] = (result["misjudge_rate"] + result["missjudge_rate"]).round(2)
    return result


def display_text(value, default: str = "未填写") -> str:
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def format_heatmap_text(matrix_df: pd.DataFrame) -> pd.DataFrame:
    if matrix_df is None or matrix_df.empty:
        return matrix_df if matrix_df is not None else pd.DataFrame()
    return matrix_df.apply(
        lambda column: column.map(lambda value: f"{value:.1f}%" if pd.notna(value) and value > 0 else "—")
    )


def ensure_default_columns(df: pd.DataFrame | None, defaults: dict[str, object]) -> pd.DataFrame:
    if df is None:
        df = pd.DataFrame()
    else:
        df = df.copy()

    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default
        else:
            if isinstance(default, (int, float)):
                df[column] = pd.to_numeric(df[column], errors="coerce").fillna(default)
            else:
                df[column] = df[column].fillna(default)
    return df


def split_multi_values(value: str | None) -> list[str]:
    if value is None or pd.isna(value):
        return []
    text = str(value).replace("，", ",").replace("、", ",")
    return [x.strip() for x in text.split(",") if x.strip()]


def get_stage_meta(stage_code: str) -> tuple[str, str, str, int]:
    mapping = {
        "internal": ("🏫 内部质检", "#8b5cf6", "#f5f3ff", 33),
        "external": ("🔍 外部质检", "#3b82f6", "#eff6ff", 66),
        "formal": ("✅ 正式上线", "#10b981", "#ecfdf5", 100),
    }
    return mapping.get(stage_code, ("待开始", "#94a3b8", "#f8fafc", 0))


def classify_batch_risk(overall_acc: float, gap_pct: float, p0_cnt: int = 0, p1_cnt: int = 0) -> tuple[str, str, str]:
    if overall_acc < 95 or gap_pct >= 4 or p0_cnt > 0:
        return ("🔴 风险批次", "#dc2626", "#fef2f2")
    if overall_acc < 97 or gap_pct >= 2.5 or p1_cnt > 0:
        return ("🟡 关注批次", "#d97706", "#fffbeb")
    return ("🟢 稳定批次", "#059669", "#ecfdf5")


def format_name_list(values, limit: int = 3, default: str = "暂无") -> str:
    cleaned = []
    for value in values:
        text = str(value).strip() if value is not None and not pd.isna(value) else ""
        if text and text not in cleaned:
            cleaned.append(text)
    if not cleaned:
        return default
    names = cleaned[:limit]
    suffix = f" 等{len(cleaned)}人" if len(cleaned) > limit else ""
    return "、".join(names) + suffix


def suggest_team_action(row: pd.Series) -> str:
    top_error_type = display_text(row.get("top_error_type"), default="通用问题")
    top_error_share = float(row.get("top_error_share") or 0)
    missjudge_rate = float(row.get("missjudge_rate") or 0)
    misjudge_rate = float(row.get("misjudge_rate") or 0)
    accuracy = float(row.get("accuracy") or 0)
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


def render_plot(fig, key: str) -> None:
    """统一给 Plotly 图表传唯一 key，避免 Streamlit 重复元素报错。"""
    st.plotly_chart(fig, use_container_width=True, key=key)


ensure_newcomer_schema()

# 正式队列人员：偶尔会被下线到新人队列练习，这类记录不应计入新人批次
NON_NEWCOMER_PRACTICE_REVIEWERS = {
    "云雀联营-丁冠鑫": "正式队列人员，下线到新人队列练习",
    "云雀联营-季晨威": "正式队列人员，下线到新人队列练习",
    "李阳": "正式队列人员，下线到新人队列练习",
    "云雀联营-李阳": "正式队列人员，下线到新人队列练习",
    "朱明阳": "正式队列人员，下线到新人队列练习",
    "云雀联营-朱明阳": "正式队列人员，下线到新人队列练习",
    "陈洪恩": "正式人力，下线到新人队列学习",
    "云雀联营-陈洪恩": "正式人力，下线到新人队列学习",
    "云雀联营-评论-陈洪恩": "正式人力，下线到新人队列学习",
}
PRACTICE_SHORT_NAMES = {"丁冠鑫", "季晨威", "李阳", "朱明阳", "陈洪恩"}


def normalize_reviewer_name(name: object) -> str:
    text = str(name or "").strip()
    if not text:
        return ""
    text = text.removeprefix("云雀联营-")
    text = text.removeprefix("评论-")
    return text.strip()


def is_non_newcomer_practice_reviewer(name: object) -> bool:
    text = str(name or "").strip()
    return text in NON_NEWCOMER_PRACTICE_REVIEWERS or normalize_reviewer_name(text) in PRACTICE_SHORT_NAMES

# ==================== 数据加载 ====================

@st.cache_data(show_spinner=False, ttl=300)
def load_batch_list() -> pd.DataFrame:
    """加载所有批次摘要信息。"""
    return repo.fetch_df(f"""
        SELECT
            batch_name,
            MIN(join_date) AS join_date,
            MIN({batch_effective_start_expr('d')}) AS effective_start_date,
            MAX(effective_end_date) AS effective_end_date,
            COUNT(*) AS total_cnt,
            GROUP_CONCAT(DISTINCT team_leader ORDER BY team_leader) AS leader_names,
            GROUP_CONCAT(DISTINCT delivery_pm ORDER BY delivery_pm) AS delivery_pms,
            GROUP_CONCAT(DISTINCT mentor_name ORDER BY mentor_name) AS mentor_names,
            GROUP_CONCAT(DISTINCT team_name ORDER BY team_name) AS teams,
            GROUP_CONCAT(DISTINCT owner ORDER BY owner) AS owners,
            SUM(CASE WHEN status = 'graduated' THEN 1 ELSE 0 END) AS graduated_cnt,
            SUM(CASE WHEN status = 'training' THEN 1 ELSE 0 END) AS training_cnt
        FROM dim_newcomer_batch d
        GROUP BY batch_name
        ORDER BY MIN({batch_effective_start_expr('d')}) DESC
    """)


@st.cache_data(show_spinner=False, ttl=300)
def load_newcomer_members(
    batch_names: list[str] | None = None,
    owner: str | None = None,
    team_name: str | None = None,
) -> pd.DataFrame:
    """加载筛选后新人成员详情。"""
    sql = """
        SELECT batch_name, reviewer_name, reviewer_alias, join_date,
               COALESCE(effective_start_date, join_date) AS effective_start_date,
               effective_end_date,
               team_name, team_leader, delivery_pm, mentor_name, owner, status
        FROM dim_newcomer_batch
    """
    conditions = []
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


@st.cache_data(show_spinner=False, ttl=300)
def load_newcomer_qa_daily(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
    stage: str | None = None,
) -> pd.DataFrame:
    """加载新人质检日汇总（内检+外检，从 fact_newcomer_qa 聚合）。"""
    if reviewer_aliases == []:
        return pd.DataFrame()

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
          ON {batch_effective_join_condition("q", "n")}
    """
    conditions = []
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


@st.cache_data(show_spinner=False, ttl=300)
def load_formal_qa_daily(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
) -> pd.DataFrame:
    """加载新人正式上线后的质检数据（按批次生效时间归属后从 mart_day_auditor 查询）。"""
    if reviewer_aliases == []:
        return pd.DataFrame()

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
          ON {batch_effective_join_condition("m", "n")}
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


@st.cache_data(show_spinner=False, ttl=300)
def load_newcomer_qa_detail(reviewer_alias: str, limit: int = 100) -> pd.DataFrame:
    """加载某个新人的质检明细（内检+外检）。"""
    return repo.fetch_df("""
        SELECT biz_date, stage, queue_name, content_type,
               training_topic, risk_level, comment_text,
               raw_judgement, final_judgement, error_type, qa_note,
               is_correct, is_misjudge, is_missjudge
        FROM fact_newcomer_qa
        WHERE reviewer_name = %s
        ORDER BY biz_date DESC, qa_time DESC
        LIMIT %s
    """, [reviewer_alias, limit])


@st.cache_data(show_spinner=False, ttl=300)
def load_newcomer_error_summary(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
) -> pd.DataFrame:
    """加载新人错误类型分布（内检+外检）。"""
    if reviewer_aliases == []:
        return pd.DataFrame()

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
          ON {batch_effective_join_condition("q", "n")}
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


@st.cache_data(show_spinner=False, ttl=300)
def load_formal_dimension_detail(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
) -> pd.DataFrame:
    """加载正式阶段可用的专题/风险/内容类型维度。"""
    fact_columns = get_table_columns("fact_qa_event")
    required = {"reviewer_name", "training_topic", "risk_level", "content_type", "is_raw_correct"}
    if reviewer_aliases == [] or not required.issubset(fact_columns):
        return pd.DataFrame()

    sql = f"""
        SELECT
            n.batch_name,
            n.team_name,
            COALESCE(NULLIF(TRIM(f.training_topic), ''), '未标注') AS training_topic,
            COALESCE(NULLIF(TRIM(f.risk_level), ''), '未标注') AS risk_level,
            COALESCE(NULLIF(TRIM(f.content_type), ''), '未标注') AS content_type,
            COUNT(*) AS qa_cnt,
            SUM(CASE WHEN f.is_raw_correct = 1 THEN 1 ELSE 0 END) AS correct_cnt
        FROM fact_qa_event f
        JOIN dim_newcomer_batch n
          ON {batch_effective_join_condition("f", "n")}
        WHERE 1 = 1
    """
    params: list[str] = []
    if batch_names:
        placeholders = ", ".join(["%s"] * len(batch_names))
        sql += f" AND n.batch_name IN ({placeholders})"
        params.extend(batch_names)
    if reviewer_aliases:
        placeholders = ", ".join(["%s"] * len(reviewer_aliases))
        sql += f" AND f.reviewer_name IN ({placeholders})"
        params.extend(reviewer_aliases)
    sql += " GROUP BY n.batch_name, n.team_name, training_topic, risk_level, content_type ORDER BY qa_cnt DESC"
    return repo.fetch_df(sql, params)


@st.cache_data(show_spinner=False, ttl=300)
def load_newcomer_dimension_detail(
    batch_names: list[str] | None = None,
    reviewer_aliases: list[str] | None = None,
) -> pd.DataFrame:
    """加载新人内/外检可用的专题/风险/内容类型维度。"""
    fact_columns = get_table_columns("fact_newcomer_qa")
    required = {"reviewer_name", "stage", "training_topic", "risk_level", "content_type", "is_correct"}
    if reviewer_aliases == [] or not required.issubset(fact_columns):
        return pd.DataFrame()

    sql = f"""
        SELECT
            n.batch_name,
            n.team_name,
            q.stage,
            COALESCE(NULLIF(TRIM(q.training_topic), ''), '未标注') AS training_topic,
            COALESCE(NULLIF(TRIM(q.risk_level), ''), '未标注') AS risk_level,
            COALESCE(NULLIF(TRIM(q.content_type), ''), '未标注') AS content_type,
            COUNT(*) AS qa_cnt,
            SUM(CASE WHEN q.is_correct = 1 THEN 1 ELSE 0 END) AS correct_cnt
        FROM fact_newcomer_qa q
        JOIN dim_newcomer_batch n
          ON {batch_effective_join_condition("q", "n")}
        WHERE 1 = 1
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
    sql += " GROUP BY n.batch_name, n.team_name, q.stage, training_topic, risk_level, content_type ORDER BY qa_cnt DESC"
    return repo.fetch_df(sql, params)


@st.cache_data(show_spinner=False, ttl=300)
def load_unmatched_newcomer_rows() -> pd.DataFrame:
    """加载尚未关联到批次的新人质检记录。"""
    fact_columns = get_table_columns("fact_newcomer_qa")
    practice_expr = "COALESCE(is_practice_sample, 0)" if "is_practice_sample" in fact_columns else "0"
    return repo.fetch_df(f"""
        SELECT reviewer_name, stage,
               MAX({practice_expr}) AS is_practice_sample,
               COUNT(*) AS row_cnt,
               MIN(biz_date) AS start_date,
               MAX(biz_date) AS end_date
        FROM fact_newcomer_qa
        WHERE batch_name IS NULL OR batch_name = ''
        GROUP BY reviewer_name, stage
        ORDER BY row_cnt DESC, reviewer_name
    """)


# ==================== Hero 区 ====================

batch_df = load_batch_list()
unmatched_df = load_unmatched_newcomer_rows()

if batch_df is None or batch_df.empty:
    st.markdown("""
    <div style="margin-bottom: 1.5rem; padding: 1.5rem; background: #ffffff; border-radius: 1rem; border-left: 4px solid #2e7d32; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700;">👶 新人追踪</h1>
        <div style="font-size: 0.9rem; color: #4b5563; margin-top: 0.5rem;">暂无新人数据，请先在「数据导入 → 新人映射」上传新人名单。</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

total_people = int(batch_df["total_cnt"].sum())
total_batches = len(batch_df)
all_teams = set()
for t in batch_df["teams"].dropna():
    all_teams.update(t.split(","))

st.markdown(f"""
<div style="margin-bottom: 1.5rem; padding: 1.5rem; background: #ffffff; border-radius: 1rem; border-left: 4px solid #2e7d32; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
        <h1 style="margin: 0; font-size: 2rem; font-weight: 700; color: #1a1a1a;">👶 新人追踪</h1>
        <div style="font-size: 0.85rem; color: #6b7280;">共 {total_batches} 批次 · {total_people} 人 · {len(all_teams)} 个团队</div>
    </div>
    <div style="font-size: 0.9rem; color: #4b5563; line-height: 1.6;">
        📍 成长路径：
        <span style="background: #f3e8ff; padding: 0.15rem 0.5rem; border-radius: 0.3rem; color: #7c3aed;">🏫 内部质检</span> →
        <span style="background: #dbeafe; padding: 0.15rem 0.5rem; border-radius: 0.3rem; color: #1d4ed8;">🔍 外部质检</span> →
        <span style="background: #d1fae5; padding: 0.15rem 0.5rem; border-radius: 0.3rem; color: #047857;">✅ 正式上线</span>
        &nbsp;·&nbsp; 通过审核人名「云雀联营-姓名」自动关联
    </div>
</div>
""", unsafe_allow_html=True)

practice_df = pd.DataFrame(columns=["reviewer_name", "stage", "is_practice_sample", "row_cnt", "start_date", "end_date"])
true_unmatched_df = pd.DataFrame(columns=["reviewer_name", "stage", "is_practice_sample", "row_cnt", "start_date", "end_date"])

if not unmatched_df.empty:
    practice_mask = unmatched_df.get("is_practice_sample", pd.Series(0, index=unmatched_df.index)).fillna(0).astype(int).eq(1)
    practice_mask = practice_mask | unmatched_df["reviewer_name"].apply(is_non_newcomer_practice_reviewer)
    practice_df = unmatched_df[practice_mask].copy()
    true_unmatched_df = unmatched_df[~practice_mask].copy()

    if not practice_df.empty:
        practice_count = int(practice_df["row_cnt"].sum())
        practice_names = "、".join(practice_df["reviewer_name"].tolist())
        st.info(f"检测到 {practice_count} 条正式人力下线学习记录：{practice_names}。此类样例会写入 is_practice_sample=1，不计入新人批次统计，仅用于练习样例排查。")

    if not true_unmatched_df.empty:
        unmatched_count = int(true_unmatched_df["row_cnt"].sum())
        unmatched_names = "、".join(true_unmatched_df["reviewer_name"].tolist())
        st.warning(f"当前仍有 {unmatched_count} 条新人质检记录未关联到批次：{unmatched_names}。建议补齐名单后再看批次汇总。")

# ==================== 页面模块切换 + 侧边栏筛选 ====================

view_options = {
    "📊 批次概览": "overview",
    "📈 成长曲线": "growth",
    "🔄 阶段对比": "compare",
    "👤 个人追踪": "person",
    "📊 维度分析": "dimension",
    "⚠️ 异常告警": "alert",
}

with st.container(border=True):
    st.markdown("#### 查看模块")
    st.caption("模块切换放在新人追踪页内，侧边栏只保留筛选条件。")
    active_view_label = st.radio(
        "查看模块",
        options=list(view_options.keys()),
        key="nc_view_filter",
        horizontal=True,
        label_visibility="collapsed",
    )

active_view = view_options[active_view_label]
need_dimension_detail = active_view == "dimension"
need_alert_detail = active_view == "alert"

st.sidebar.markdown("### 🎯 新人追踪筛选")
selected_batches = st.sidebar.multiselect(
    "选择批次",
    options=batch_df["batch_name"].tolist(),
    default=batch_df["batch_name"].tolist(),
    key="nc_batch_filter",
)

owner_options = ["全部"] + sorted([o for o in batch_df["owners"].fillna("").str.split(",").explode().unique().tolist() if o])
owner_filter = st.sidebar.selectbox("质培owner 筛选", options=owner_options, key="nc_owner_filter")

stage_filter = st.sidebar.selectbox(
    "阶段筛选",
    options=["全部", "内部质检", "外部质检", "正式上线"],
    key="nc_stage_filter",
)

team_options = ["全部"] + sorted(all_teams)
team_filter = st.sidebar.selectbox("基地/团队筛选", options=team_options, key="nc_team_filter")

# ==================== 加载筛选后的数据 ====================

owner_value = None if owner_filter == "全部" else owner_filter
team_value = None if team_filter == "全部" else team_filter
members_df = load_newcomer_members(
    selected_batches if selected_batches else None,
    owner=owner_value,
    team_name=team_value,
)
if members_df is None:
    members_df = pd.DataFrame(columns=["batch_name", "reviewer_name", "reviewer_alias", "join_date", "effective_start_date", "effective_end_date", "team_name", "team_leader", "delivery_pm", "mentor_name", "owner", "status"])
else:
    members_df = members_df.copy()
    for col in ["team_name", "team_leader", "delivery_pm", "mentor_name", "owner"]:
        if col in members_df.columns:
            members_df[col] = members_df[col].fillna("未填写")

# 获取所有新人的系统审核人名
reviewer_aliases = members_df["reviewer_alias"].dropna().unique().tolist() if not members_df.empty else []

stage_map = {"内部质检": "internal", "外部质检": "external", "正式上线": "formal"}
stage_code = stage_map.get(stage_filter)
load_newcomer_stage = stage_code in (None, "internal", "external")
load_formal_stage = stage_code in (None, "formal")
newcomer_stage = stage_code if stage_code in {"internal", "external"} else None

# 加载新人质检数据（尽量把筛选下推到 SQL）
if reviewer_aliases and load_newcomer_stage:
    newcomer_qa_df = load_newcomer_qa_daily(
        selected_batches if selected_batches else None,
        reviewer_aliases=reviewer_aliases,
        stage=newcomer_stage,
    )
else:
    newcomer_qa_df = pd.DataFrame()

formal_qa_df = load_formal_qa_daily(
    selected_batches if selected_batches else None,
    reviewer_aliases=reviewer_aliases,
) if reviewer_aliases and load_formal_stage else pd.DataFrame()

newcomer_qa_df = ensure_accuracy_columns(newcomer_qa_df)
formal_qa_df = ensure_accuracy_columns(formal_qa_df)

combined_qa_df = pd.concat(
    [df for df in [newcomer_qa_df, formal_qa_df] if df is not None and not df.empty],
    ignore_index=True,
) if (not newcomer_qa_df.empty or not formal_qa_df.empty) else pd.DataFrame()
combined_qa_df = ensure_accuracy_columns(combined_qa_df)
error_summary_df = load_newcomer_error_summary(
    selected_batches if selected_batches else None,
    reviewer_aliases=reviewer_aliases,
) if reviewer_aliases and need_alert_detail else pd.DataFrame()
formal_dimension_df = load_formal_dimension_detail(
    selected_batches if selected_batches else None,
    reviewer_aliases=reviewer_aliases,
) if reviewer_aliases and need_dimension_detail else pd.DataFrame()
newcomer_dimension_df = load_newcomer_dimension_detail(
    selected_batches if selected_batches else None,
    reviewer_aliases=reviewer_aliases,
) if reviewer_aliases and need_dimension_detail else pd.DataFrame()

if need_dimension_detail:
    fact_newcomer_columns = get_table_columns("fact_newcomer_qa")
    fact_event_columns = get_table_columns("fact_qa_event")
    newcomer_dimension_ready = {"training_topic", "risk_level", "content_type"}.issubset(fact_newcomer_columns)
    formal_dimension_ready = {"training_topic", "risk_level", "content_type"}.issubset(fact_event_columns)
    if not newcomer_dimension_df.empty and not formal_dimension_df.empty:
        dimension_current_status = "新人内/外检 + 正式阶段已接"
    elif not newcomer_dimension_df.empty:
        dimension_current_status = "已接新人内/外检"
    elif newcomer_dimension_ready:
        dimension_current_status = "字段已就绪，待新导入/回填"
    elif not formal_dimension_df.empty:
        dimension_current_status = "已接正式阶段，待补新人字段"
    else:
        dimension_current_status = "待补新人内/外检字段"

    dimension_status_df = pd.DataFrame([
        {
            "维度": "培训专题达标率",
            "新人内/外检": "可用" if "training_topic" in fact_newcomer_columns else "缺失",
            "正式阶段": "可用" if "training_topic" in fact_event_columns else "缺失",
            "当前处理": dimension_current_status,
            "说明": "用于识别专项培训短板",
        },
        {
            "维度": "风险等级分布",
            "新人内/外检": "可用" if "risk_level" in fact_newcomer_columns else "缺失",
            "正式阶段": "可用" if "risk_level" in fact_event_columns else "缺失",
            "当前处理": dimension_current_status,
            "说明": "用于拆分高风险漏判和一般错判",
        },
        {
            "维度": "内容类型分布",
            "新人内/外检": "可用" if "content_type" in fact_newcomer_columns else "缺失",
            "正式阶段": "可用" if "content_type" in fact_event_columns else "缺失",
            "当前处理": dimension_current_status,
            "说明": "用于识别特定内容类型薄弱基地",
        },
        {
            "维度": "审核时效 / 人效",
            "新人内/外检": "可用" if "qa_time" in fact_newcomer_columns else "部分可用",
            "正式阶段": "缺失（当前汇总表无时效字段）",
            "当前处理": "待补稳定产能或耗时口径",
            "说明": "适合和正确率联动看赶量影响",
        },
    ])
else:
    fact_newcomer_columns = set()
    fact_event_columns = set()
    newcomer_dimension_ready = False
    formal_dimension_ready = False
    dimension_status_df = pd.DataFrame(columns=["维度", "新人内/外检", "正式阶段", "当前处理", "说明"])
aggregate_payload = load_newcomer_aggregate_payload(
    selected_batches if selected_batches else None,
    owner=owner_value,
    team_name=team_value,
) if not members_df.empty else {}
aggregate_batch_scope_df = pd.DataFrame(aggregate_payload.get("batch_scope") or [])
if not aggregate_batch_scope_df.empty and "join_date" in aggregate_batch_scope_df.columns:
    aggregate_batch_scope_df = aggregate_batch_scope_df.copy()
    aggregate_batch_scope_df["join_date"] = pd.to_datetime(aggregate_batch_scope_df["join_date"], errors="coerce").dt.date

filtered_batch_df = aggregate_batch_scope_df if not aggregate_batch_scope_df.empty else members_df.groupby("batch_name", as_index=False).agg(
    join_date=("join_date", "min"),
    total_cnt=("reviewer_name", "count"),
    leader_names=("team_leader", lambda x: "、".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    delivery_pms=("delivery_pm", lambda x: "、".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    mentor_names=("mentor_name", lambda x: "、".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    teams=("team_name", lambda x: ",".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    owners=("owner", lambda x: ",".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    graduated_cnt=("status", lambda x: int((x == "graduated").sum())),
    training_cnt=("status", lambda x: int((x == "training").sum())),
) if not members_df.empty else pd.DataFrame(columns=batch_df.columns)

# ==================== 复用衍生数据 ====================
if not members_df.empty:
    members_df = members_df.copy()
    members_df["join_date"] = pd.to_datetime(members_df["join_date"], errors="coerce").dt.date

if not combined_qa_df.empty:
    combined_qa_df = combined_qa_df.copy()
    combined_qa_df["biz_date"] = pd.to_datetime(combined_qa_df["biz_date"], errors="coerce").dt.date

stage_summary_df = pd.DataFrame()
overall_stage_df = pd.DataFrame()
person_stage_df = pd.DataFrame()
stage_team_accuracy_df = pd.DataFrame()
team_accuracy_df = pd.DataFrame()
team_issue_df = pd.DataFrame()
management_perf_df = pd.DataFrame()
batch_compare_df = pd.DataFrame()
batch_gap_df = pd.DataFrame()
recent_person_perf_df = pd.DataFrame()
batch_watch_df = pd.DataFrame()
team_summary_df = pd.DataFrame()
team_alert_df = pd.DataFrame()

aggregate_overall_stage_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("stage_summary") or []))
aggregate_batch_stage_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("batch_stage_summary") or []))
aggregate_stage_team_accuracy_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("stage_team_accuracy") or []))
aggregate_team_accuracy_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("team_accuracy") or []))
aggregate_batch_compare_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("batch_compare") or []))
aggregate_batch_gap_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("batch_gap") or []))
aggregate_batch_watch_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("batch_watch") or []))
aggregate_team_alert_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("team_alert") or []))
aggregate_management_perf_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get("management_summary") or []))

if not aggregate_batch_compare_df.empty and "join_date" in aggregate_batch_compare_df.columns:
    aggregate_batch_compare_df = aggregate_batch_compare_df.copy()
    aggregate_batch_compare_df["join_date"] = pd.to_datetime(aggregate_batch_compare_df["join_date"], errors="coerce").dt.date

if not aggregate_overall_stage_df.empty:
    overall_stage_df = aggregate_overall_stage_df.copy()
if not aggregate_batch_stage_df.empty:
    stage_summary_df = aggregate_batch_stage_df.copy()
if not aggregate_stage_team_accuracy_df.empty:
    stage_team_accuracy_df = aggregate_stage_team_accuracy_df.copy()
if not aggregate_team_accuracy_df.empty:
    team_accuracy_df = aggregate_team_accuracy_df.copy()
    team_issue_df = team_accuracy_df.copy()
if not aggregate_batch_compare_df.empty:
    batch_compare_df = aggregate_batch_compare_df.copy()
if not aggregate_batch_gap_df.empty:
    batch_gap_df = aggregate_batch_gap_df.copy()
if not aggregate_batch_watch_df.empty:
    batch_watch_df = aggregate_batch_watch_df.copy()
if not aggregate_team_alert_df.empty:
    team_alert_df = aggregate_team_alert_df.copy()
if not aggregate_management_perf_df.empty:
    management_perf_df = aggregate_management_perf_df.copy()

if not combined_qa_df.empty:
    if overall_stage_df.empty:
        overall_stage_df = build_dual_accuracy_group(combined_qa_df, ["stage"])
    if stage_summary_df.empty:
        stage_summary_df = build_dual_accuracy_group(combined_qa_df, ["batch_name", "stage"])

    person_stage_df = combined_qa_df.groupby(["batch_name", "reviewer_name", "short_name", "team_name", "stage"], as_index=False).agg(
        qa_cnt=("qa_cnt", "sum"),
        correct_cnt=("correct_cnt", "sum"),
        misjudge_cnt=("misjudge_cnt", "sum"),
        missjudge_cnt=("missjudge_cnt", "sum"),
    )
    person_stage_df["sample_accuracy"] = person_stage_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
    person_stage_df["accuracy"] = person_stage_df["sample_accuracy"]
    person_stage_df["accuracy_rate"] = person_stage_df["sample_accuracy"]
    person_stage_df["misjudge_rate"] = person_stage_df.apply(lambda r: safe_pct(r["misjudge_cnt"], r["qa_cnt"]), axis=1)
    person_stage_df["missjudge_rate"] = person_stage_df.apply(lambda r: safe_pct(r["missjudge_cnt"], r["qa_cnt"]), axis=1)
    person_stage_df["issue_rate"] = (person_stage_df["misjudge_rate"] + person_stage_df["missjudge_rate"]).round(2)

    if stage_team_accuracy_df.empty:
        stage_team_accuracy_df = build_dual_accuracy_group(combined_qa_df, ["batch_name", "team_name", "stage"])
    if team_accuracy_df.empty:
        team_accuracy_df = build_dual_accuracy_group(combined_qa_df, ["batch_name", "team_name"])
    team_issue_df = team_accuracy_df.copy() if not team_accuracy_df.empty else pd.DataFrame()

    if batch_compare_df.empty:
        batch_compare_df = build_dual_accuracy_group(combined_qa_df, ["batch_name"])
        batch_compare_df = batch_compare_df.merge(filtered_batch_df[["batch_name", "join_date"]], on="batch_name", how="left")
        batch_compare_df["training_days"] = batch_compare_df["join_date"].apply(
            lambda x: (date.today() - x).days if pd.notna(x) and x else 0
        )

    if batch_gap_df.empty and not team_accuracy_df.empty:
        gap_base = team_accuracy_df.groupby("batch_name", as_index=False).agg(
            team_cnt=("team_name", "nunique"),
            avg_team_sample_accuracy=("sample_accuracy", "mean"),
            avg_team_per_capita_accuracy=("per_capita_accuracy", "mean"),
        )
        best_rows = team_accuracy_df.loc[
            team_accuracy_df.groupby("batch_name")["sample_accuracy"].idxmax(),
            ["batch_name", "team_name", "sample_accuracy", "per_capita_accuracy", "issue_rate"],
        ].rename(columns={
            "team_name": "best_team_name",
            "sample_accuracy": "best_team_acc",
            "per_capita_accuracy": "best_team_per_capita_acc",
            "issue_rate": "best_team_issue_rate",
        })
        worst_rows = team_accuracy_df.loc[
            team_accuracy_df.groupby("batch_name")["sample_accuracy"].idxmin(),
            ["batch_name", "team_name", "sample_accuracy", "per_capita_accuracy", "issue_rate"],
        ].rename(columns={
            "team_name": "worst_team_name",
            "sample_accuracy": "worst_team_acc",
            "per_capita_accuracy": "worst_team_per_capita_acc",
            "issue_rate": "worst_team_issue_rate",
        })
        batch_gap_df = gap_base.merge(best_rows, on="batch_name", how="left").merge(worst_rows, on="batch_name", how="left")
        batch_gap_df["best_team_acc"] = pd.to_numeric(batch_gap_df["best_team_acc"], errors="coerce").fillna(0)
        batch_gap_df["worst_team_acc"] = pd.to_numeric(batch_gap_df["worst_team_acc"], errors="coerce").fillna(0)
        batch_gap_df["best_team_per_capita_acc"] = pd.to_numeric(batch_gap_df["best_team_per_capita_acc"], errors="coerce").fillna(0)
        batch_gap_df["worst_team_per_capita_acc"] = pd.to_numeric(batch_gap_df["worst_team_per_capita_acc"], errors="coerce").fillna(0)
        batch_gap_df["sample_gap_pct"] = (batch_gap_df["best_team_acc"] - batch_gap_df["worst_team_acc"]).round(2)
        batch_gap_df["per_capita_gap_pct"] = (batch_gap_df["best_team_per_capita_acc"] - batch_gap_df["worst_team_per_capita_acc"]).round(2)
        batch_gap_df["gap_pct"] = batch_gap_df["sample_gap_pct"]

    team_summary_df = members_df.groupby(["batch_name", "team_name", "team_leader", "delivery_pm", "owner"], as_index=False).agg(
        人数=("reviewer_name", "count"),
        培训中=("status", lambda x: (x == "training").sum()),
        已转正=("status", lambda x: (x == "graduated").sum()),
    )
    team_summary_df = team_summary_df.merge(
        team_accuracy_df[["batch_name", "team_name", "qa_cnt", "sample_accuracy", "per_capita_accuracy", "accuracy_gap", "misjudge_rate", "missjudge_rate", "issue_rate"]],
        on=["batch_name", "team_name"],
        how="left",
    )

    if management_perf_df.empty:
        management_person_df = combined_qa_df.merge(
            members_df[["reviewer_alias", "team_leader", "delivery_pm", "owner", "mentor_name"]].drop_duplicates(),
            left_on="reviewer_name",
            right_on="reviewer_alias",
            how="left",
        )
        management_person_df = management_person_df.fillna({
            "team_leader": "未填写",
            "delivery_pm": "未填写",
            "owner": "未填写",
            "mentor_name": "未填写",
        })
        management_perf_df = build_dual_accuracy_group(management_person_df, ["team_leader", "delivery_pm", "owner", "mentor_name"])
        management_perf_df = management_perf_df.fillna({
            "team_leader": "未填写",
            "delivery_pm": "未填写",
            "owner": "未填写",
            "mentor_name": "未填写",
        })

    recent_date = combined_qa_df["biz_date"].max()
    if recent_date:
        recent_cutoff = recent_date - timedelta(days=7)
        recent_meta_df = members_df[["reviewer_alias", "team_leader", "delivery_pm", "owner", "mentor_name"]].drop_duplicates()
        recent_qa_df = combined_qa_df[combined_qa_df["biz_date"] >= recent_cutoff].copy()
        recent_qa_df = recent_qa_df.merge(recent_meta_df, left_on="reviewer_name", right_on="reviewer_alias", how="left")
        recent_person_perf_df = recent_qa_df.groupby(
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
        recent_person_perf_df = recent_person_perf_df.merge(latest_stage_df, on="reviewer_name", how="left")
        recent_person_perf_df["sample_accuracy"] = recent_person_perf_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
        recent_person_perf_df["accuracy"] = recent_person_perf_df["sample_accuracy"]
        recent_person_perf_df["misjudge_rate"] = recent_person_perf_df.apply(lambda r: safe_pct(r["misjudge_cnt"], r["qa_cnt"]), axis=1)
        recent_person_perf_df["missjudge_rate"] = recent_person_perf_df.apply(lambda r: safe_pct(r["missjudge_cnt"], r["qa_cnt"]), axis=1)
        recent_person_perf_df["issue_rate"] = (recent_person_perf_df["misjudge_rate"] + recent_person_perf_df["missjudge_rate"]).round(2)
        recent_person_perf_df["risk_level"] = recent_person_perf_df.apply(
            lambda r: "P0" if (r["accuracy"] < 90 or r["missjudge_rate"] >= 2.0)
            else ("P1" if (r["accuracy"] < 95 or r["issue_rate"] >= 2.5)
            else ("NEAR" if (r["latest_stage"] == "external" and 97.5 <= r["accuracy"] < 98) else "OK")),
            axis=1,
        )

        if not recent_person_perf_df.empty:
            risk_rank_map = {"P0": 0, "P1": 1, "NEAR": 2, "OK": 3}
            risk_focus_df = recent_person_perf_df[recent_person_perf_df["risk_level"].isin(["P0", "P1"])].copy()
            if not risk_focus_df.empty:
                risk_focus_df["risk_rank"] = risk_focus_df["risk_level"].map(risk_rank_map)
                risk_focus_df = risk_focus_df.sort_values(["batch_name", "risk_rank", "accuracy", "issue_rate"], ascending=[True, True, True, False])
                batch_focus_df = risk_focus_df.groupby("batch_name").agg(
                    focus_people=("short_name", lambda x: format_name_list(list(x), limit=3)),
                    p0_cnt=("risk_level", lambda x: int((x == "P0").sum())),
                    p1_cnt=("risk_level", lambda x: int((x == "P1").sum())),
                ).reset_index()
            else:
                batch_focus_df = pd.DataFrame(columns=["batch_name", "focus_people", "p0_cnt", "p1_cnt"])

            if batch_watch_df.empty:
                batch_watch_df = batch_compare_df.merge(
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
                ) if not batch_gap_df.empty else batch_compare_df.copy()
                if not batch_focus_df.empty:
                    batch_watch_df = batch_watch_df.merge(batch_focus_df, on="batch_name", how="left")
                for col, default in {
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
                    if col not in batch_watch_df.columns:
                        batch_watch_df[col] = default
                    else:
                        batch_watch_df[col] = batch_watch_df[col].fillna(default)
                batch_watch_df[["risk_label", "risk_color", "risk_bg"]] = batch_watch_df.apply(
                    lambda r: pd.Series(classify_batch_risk(float(r["sample_accuracy"] or 0), float(r["sample_gap_pct"] or 0), int(r["p0_cnt"] or 0), int(r["p1_cnt"] or 0))),
                    axis=1,
                )

    if team_alert_df.empty and not team_issue_df.empty:
        team_alert_df = team_issue_df.copy()
        if error_summary_df is not None and not error_summary_df.empty:
            team_error_focus_df = error_summary_df.groupby(["batch_name", "team_name", "error_type"], as_index=False)["error_cnt"].sum()
            team_error_total_df = team_error_focus_df.groupby(["batch_name", "team_name"], as_index=False)["error_cnt"].sum().rename(columns={"error_cnt": "team_error_cnt"})
            team_error_focus_df = team_error_focus_df.sort_values(["batch_name", "team_name", "error_cnt"], ascending=[True, True, False]).groupby(["batch_name", "team_name"], as_index=False).head(1)
            team_error_focus_df = team_error_focus_df.merge(team_error_total_df, on=["batch_name", "team_name"], how="left")
            team_error_focus_df["top_error_share"] = team_error_focus_df.apply(lambda r: safe_pct(r["error_cnt"], r["team_error_cnt"]), axis=1)
            team_error_focus_df = team_error_focus_df.rename(columns={"error_type": "top_error_type"})
            team_alert_df = team_alert_df.merge(
                team_error_focus_df[["batch_name", "team_name", "top_error_type", "top_error_share"]],
                on=["batch_name", "team_name"],
                how="left",
            )
        if not batch_watch_df.empty:
            team_alert_df = team_alert_df.merge(batch_watch_df[["batch_name", "risk_label"]], on="batch_name", how="left")
        if "top_error_type" not in team_alert_df.columns:
            team_alert_df["top_error_type"] = "未标注"
        else:
            team_alert_df["top_error_type"] = team_alert_df["top_error_type"].fillna("未标注")
        if "top_error_share" not in team_alert_df.columns:
            team_alert_df["top_error_share"] = 0.0
        else:
            team_alert_df["top_error_share"] = pd.to_numeric(team_alert_df["top_error_share"], errors="coerce").fillna(0)
        team_alert_df["关注分"] = (100 - team_alert_df["sample_accuracy"]) + (team_alert_df["issue_rate"] * 2) + (team_alert_df["missjudge_rate"] * 1.5)
        team_alert_df["accuracy"] = team_alert_df["sample_accuracy"]
        team_alert_df["建议动作"] = team_alert_df.apply(suggest_team_action, axis=1)
        team_alert_df = team_alert_df.sort_values(["关注分", "sample_accuracy", "issue_rate"], ascending=[False, True, False])

# ==================== 模块切换 ====================

st.caption(f"当前查看：{active_view_label}。页面已改成按模块渲染，避免一次刷新把 6 个重模块一起跑完。")

# ==================== 模块 1: 批次概览 ====================
if active_view == "overview":
    overview_batch_df = filtered_batch_df if not filtered_batch_df.empty else batch_df.iloc[0:0]
    overview_total_people = int(overview_batch_df["total_cnt"].sum()) if not overview_batch_df.empty else 0
    avg_training_days = 0
    if not overview_batch_df.empty and overview_batch_df["join_date"].notna().any():
        avg_training_days = round(
            pd.Series([(date.today() - d).days for d in overview_batch_df["join_date"] if pd.notna(d)]).mean(), 1
        )

    internal_sample_acc = float(overall_stage_df.loc[overall_stage_df["stage"] == "internal", "sample_accuracy"].max()) if not overall_stage_df.empty and "internal" in overall_stage_df["stage"].values else 0
    internal_per_capita_acc = float(overall_stage_df.loc[overall_stage_df["stage"] == "internal", "per_capita_accuracy"].max()) if not overall_stage_df.empty and "internal" in overall_stage_df["stage"].values else 0
    external_sample_acc = float(overall_stage_df.loc[overall_stage_df["stage"] == "external", "sample_accuracy"].max()) if not overall_stage_df.empty and "external" in overall_stage_df["stage"].values else 0
    external_per_capita_acc = float(overall_stage_df.loc[overall_stage_df["stage"] == "external", "per_capita_accuracy"].max()) if not overall_stage_df.empty and "external" in overall_stage_df["stage"].values else 0
    formal_sample_acc = float(overall_stage_df.loc[overall_stage_df["stage"] == "formal", "sample_accuracy"].max()) if not overall_stage_df.empty and "formal" in overall_stage_df["stage"].values else 0
    formal_per_capita_acc = float(overall_stage_df.loc[overall_stage_df["stage"] == "formal", "per_capita_accuracy"].max()) if not overall_stage_df.empty and "formal" in overall_stage_df["stage"].values else 0

    max_gap_value = float(batch_gap_df["sample_gap_pct"].max()) if not batch_gap_df.empty and "sample_gap_pct" in batch_gap_df.columns else 0
    max_per_capita_gap = float(batch_gap_df["per_capita_gap_pct"].max()) if not batch_gap_df.empty and "per_capita_gap_pct" in batch_gap_df.columns else 0
    weak_batch_name = "—"
    weak_batch_acc = 0.0
    if not batch_watch_df.empty:
        weak_batch_row = batch_watch_df.sort_values(["risk_label", "sample_accuracy", "sample_gap_pct"], ascending=[True, True, False]).iloc[0]
        weak_batch_name = weak_batch_row["batch_name"]
        weak_batch_acc = float(weak_batch_row["sample_accuracy"])

    mc1, mc2, mc3, mc4, mc5, mc6 = st.columns(6)
    with mc1:
        st.metric("👥 当前新人数", overview_total_people)
    with mc2:
        st.metric("🏫 内部样本正确率", f"{internal_sample_acc:.1f}%", delta=f"人均 {internal_per_capita_acc:.1f}%")
    with mc3:
        st.metric("🔍 外部样本正确率", f"{external_sample_acc:.1f}%", delta=f"人均 {external_per_capita_acc:.1f}%")
    with mc4:
        st.metric("✅ 正式样本正确率", f"{formal_sample_acc:.1f}%", delta=f"人均 {formal_per_capita_acc:.1f}%")
    with mc5:
        st.metric("📅 平均培训天数", f"{avg_training_days}天")
    with mc6:
        st.metric("📏 最大基地样本差值", f"{max_gap_value:.1f}%", delta=f"人均差值 {max_per_capita_gap:.1f}% · {weak_batch_name} {weak_batch_acc:.1f}%")

    st.markdown("""
    <div style="margin:-0.25rem 0 1rem; padding:0.85rem 1rem; border-radius:0.75rem; background:#eff6ff; border-left:4px solid #2563eb; font-size:0.82rem; color:#1d4ed8; line-height:1.7;">
        <strong>口径说明</strong>：聚合层统一同时看“样本正确率 + 人均正确率”。样本口径更适合看整体质量，人均口径更适合看队伍稳定性和带教公平性；个人追踪页仍只看单人样本正确率。
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    if overview_batch_df.empty:
        st.info("当前筛选条件下暂无新人成员。")
    else:
        st.markdown("#### 🏷️ 批次一览")
        for _, batch_row in overview_batch_df.iterrows():
            bn = batch_row["batch_name"]
            join_d = batch_row["join_date"]
            days_since = (date.today() - join_d).days if pd.notna(join_d) and join_d else 0
            cnt = int(batch_row["total_cnt"])
            grad = int(batch_row["graduated_cnt"])
            leader = display_text(batch_row.get("leader_names"))
            delivery_pm = display_text(batch_row.get("delivery_pms"))
            mentor = display_text(batch_row.get("mentor_names"))
            owner_names = display_text(batch_row.get("owners"))
            teams_str = display_text(batch_row.get("teams"), default="-")

            batch_stage = stage_summary_df[stage_summary_df["batch_name"] == bn] if not stage_summary_df.empty else pd.DataFrame()
            batch_compare_row = batch_compare_df[batch_compare_df["batch_name"] == bn].iloc[0] if not batch_compare_df.empty and bn in batch_compare_df["batch_name"].values else None
            batch_sample_acc = float(batch_compare_row["sample_accuracy"]) if batch_compare_row is not None else 0.0
            batch_per_capita_acc = float(batch_compare_row["per_capita_accuracy"]) if batch_compare_row is not None else 0.0
            batch_accuracy_gap = float(batch_compare_row["accuracy_gap"]) if batch_compare_row is not None else 0.0
            total_qa = float(batch_compare_row["qa_cnt"]) if batch_compare_row is not None else 0
            available_stages = batch_stage["stage"].tolist() if not batch_stage.empty else []
            if "formal" in available_stages:
                current_stage = "formal"
            elif "external" in available_stages:
                current_stage = "external"
            elif "internal" in available_stages:
                current_stage = "internal"
            else:
                current_stage = "pending"
            stage_label, stage_color, stage_bg, progress_width = get_stage_meta(current_stage)

            watch_row = batch_watch_df[batch_watch_df["batch_name"] == bn].iloc[0] if not batch_watch_df.empty and bn in batch_watch_df["batch_name"].values else None
            risk_label = watch_row["risk_label"] if watch_row is not None else "🟢 稳定批次"
            risk_color = watch_row["risk_color"] if watch_row is not None else "#059669"
            risk_bg = watch_row["risk_bg"] if watch_row is not None else "#ecfdf5"
            gap_pct = float(watch_row["gap_pct"]) if watch_row is not None else 0.0
            best_team_name = display_text(watch_row["best_team_name"], default="—") if watch_row is not None else "—"
            worst_team_name = display_text(watch_row["worst_team_name"], default="—") if watch_row is not None else "—"
            best_team_acc = float(watch_row["best_team_acc"]) if watch_row is not None else 0.0
            worst_team_acc = float(watch_row["worst_team_acc"]) if watch_row is not None else 0.0
            focus_people = watch_row["focus_people"] if watch_row is not None else "暂无"
            p0_cnt = int(watch_row["p0_cnt"]) if watch_row is not None else 0
            p1_cnt = int(watch_row["p1_cnt"]) if watch_row is not None else 0
            risk_note = f"近7天优先辅导：{focus_people}" if focus_people != "暂无" else "近7天暂无明显风险新人"

            st.markdown(f"""
            <div style="padding: 1.25rem; border-radius: 1rem; background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%); border: 1px solid #E5E7EB; margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(15,23,42,0.06);">
                <div style="display:flex; justify-content:space-between; gap:1rem; align-items:flex-start; margin-bottom:0.9rem; flex-wrap:wrap;">
                    <div>
                        <div style="font-weight:700; font-size:1.15rem; color:#1E293B;">📋 {bn}</div>
                        <div style="font-size:0.82rem; color:#64748B; margin-top:0.35rem; line-height:1.6;">
                            入职 {days_since} 天 · 联营管理：{leader} · 交付PM：{delivery_pm} · 质培owner：{owner_names}<br>
                            导师/质检：{mentor} · 基地/团队：{teams_str}
                        </div>
                    </div>
                    <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap;">
                        <div style="padding:0.28rem 0.8rem; border-radius:999px; background:{risk_bg}; color:{risk_color}; font-size:0.8rem; font-weight:700; border:1px solid {risk_color};">{risk_label}</div>
                        <div style="padding:0.28rem 0.8rem; border-radius:999px; background:{stage_bg}; color:{stage_color}; font-size:0.8rem; font-weight:700; border:1px solid {stage_color};">{stage_label}</div>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(6, 1fr); gap:0.75rem;">
                    <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                        <div style="font-size:0.72rem; color:#64748B;">人数</div>
                        <div style="font-size:1.25rem; font-weight:700; color:#0F172A;">{cnt}</div>
                    </div>
                    <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                        <div style="font-size:0.72rem; color:#64748B;">样本正确率</div>
                        <div style="font-size:1.15rem; font-weight:700; color:#10b981;">{batch_sample_acc:.1f}%</div>
                    </div>
                    <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                        <div style="font-size:0.72rem; color:#64748B;">人均正确率</div>
                        <div style="font-size:1.15rem; font-weight:700; color:#2563eb;">{batch_per_capita_acc:.1f}%</div>
                    </div>
                    <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                        <div style="font-size:0.72rem; color:#64748B;">口径差值</div>
                        <div style="font-size:1.15rem; font-weight:700; color:#dc2626;">{batch_accuracy_gap:.1f}%</div>
                    </div>
                    <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                        <div style="font-size:0.72rem; color:#64748B;">质检量</div>
                        <div style="font-size:1.15rem; font-weight:700; color:#0F172A;">{int(total_qa):,}</div>
                    </div>
                    <div style="background:white; padding:0.75rem; border-radius:0.65rem; text-align:center; border:1px solid #E5E7EB;">
                        <div style="font-size:0.72rem; color:#64748B;">已转正</div>
                        <div style="font-size:1.15rem; font-weight:700; color:#10b981;">{grad}</div>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns:1.4fr 1fr 1fr; gap:0.75rem; margin-top:0.8rem;">
                    <div style="background:#ffffff; padding:0.85rem; border-radius:0.75rem; border:1px solid #E5E7EB;">
                        <div style="font-size:0.74rem; color:#64748B; margin-bottom:0.3rem;">差异聚焦</div>
                        <div style="font-size:0.92rem; color:#0F172A; font-weight:700;">{best_team_name} 样本 {best_team_acc:.1f}% / 人均 {float(watch_row['best_team_per_capita_acc']) if watch_row is not None and 'best_team_per_capita_acc' in watch_row else 0:.1f}%</div>
                        <div style="font-size:0.78rem; color:{risk_color}; margin-top:0.25rem;">待关注：{worst_team_name} · 样本差值 {gap_pct:.1f}% / 人均差值 {float(watch_row['per_capita_gap_pct']) if watch_row is not None and 'per_capita_gap_pct' in watch_row else 0:.1f}%</div>
                    </div>
                    <div style="background:#ffffff; padding:0.85rem; border-radius:0.75rem; border:1px solid #E5E7EB;">
                        <div style="font-size:0.74rem; color:#64748B; margin-bottom:0.3rem;">风险人数</div>
                        <div style="font-size:1.05rem; color:#0F172A; font-weight:700;">P0 {p0_cnt} / P1 {p1_cnt}</div>
                        <div style="font-size:0.78rem; color:#64748B; margin-top:0.25rem;">近7天滚动识别</div>
                    </div>
                    <div style="background:#ffffff; padding:0.85rem; border-radius:0.75rem; border:1px solid #E5E7EB;">
                        <div style="font-size:0.74rem; color:#64748B; margin-bottom:0.3rem;">优先动作</div>
                        <div style="font-size:0.84rem; color:#0F172A; line-height:1.45; font-weight:600;">{risk_note}</div>
                    </div>
                </div>
                <div style="margin-top:0.8rem; height:6px; background:#E2E8F0; border-radius:999px; overflow:hidden;">
                    <div style="width:{progress_width}%; height:100%; background:linear-gradient(90deg, #8b5cf6 0%, #3b82f6 60%, #10b981 100%);"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    if not stage_summary_df.empty:
        col_a, col_b = st.columns([1.2, 1])
        with col_a:
            st.markdown("#### 📊 批次阶段双口径")
            stage_chart = stage_summary_df.copy()
            stage_chart["阶段"] = stage_chart["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检", "formal": "✅ 正式上线"})
            stage_chart = stage_chart.melt(
                id_vars=["batch_name", "阶段"],
                value_vars=["sample_accuracy", "per_capita_accuracy"],
                var_name="口径",
                value_name="正确率",
            )
            stage_chart["口径"] = stage_chart["口径"].map({"sample_accuracy": "样本正确率", "per_capita_accuracy": "人均正确率"})
            fig_stage = px.bar(
                stage_chart,
                x="batch_name",
                y="正确率",
                color="阶段",
                pattern_shape="口径",
                barmode="group",
                text="正确率",
                labels={"batch_name": "批次", "正确率": "正确率 (%)"},
                color_discrete_map={"🏫 内部质检": "#8b5cf6", "🔍 外部质检": "#3b82f6", "✅ 正式上线": "#10b981"},
                pattern_shape_map={"样本正确率": "", "人均正确率": "/"},
            )
            fig_stage.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_stage.update_layout(height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_stage, "overview_stage_accuracy_bar")
        with col_b:
            st.markdown("#### 🧭 阶段结构分布")
            stage_volume = stage_summary_df.groupby("stage", as_index=False)["qa_cnt"].sum()
            stage_volume["阶段"] = stage_volume["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检", "formal": "✅ 正式上线"})
            fig_volume = px.pie(
                stage_volume,
                values="qa_cnt",
                names="阶段",
                hole=0.55,
                color="阶段",
                color_discrete_map={"🏫 内部质检": "#8b5cf6", "🔍 外部质检": "#3b82f6", "✅ 正式上线": "#10b981"},
            )
            fig_volume.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_volume, "overview_stage_volume_pie")

    if not team_accuracy_df.empty:
        st.markdown("#### 📍 同批次不同基地双口径")
        col_team_chart, col_team_table = st.columns([1.15, 1])
        with col_team_chart:
            fig_team = px.bar(
                team_accuracy_df.sort_values(["batch_name", "sample_accuracy"], ascending=[True, False]),
                x="batch_name",
                y="sample_accuracy",
                color="team_name",
                barmode="group",
                text="sample_accuracy",
                labels={"batch_name": "批次", "sample_accuracy": "样本正确率 (%)", "team_name": "基地/团队"},
            )
            fig_team.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_team.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_team, "overview_team_accuracy_bar")
            st.caption("柱图默认看基地样本正确率；右侧表格同时补充人均正确率和口径差值，避免被高量审核人抹平差异。")
        with col_team_table:
            base_table = team_summary_df.rename(columns={
                "batch_name": "批次",
                "team_name": "基地/团队",
                "team_leader": "联营管理",
                "delivery_pm": "交付PM",
                "owner": "质培owner",
                "qa_cnt": "质检量",
                "sample_accuracy": "样本正确率",
                "per_capita_accuracy": "人均正确率",
                "accuracy_gap": "口径差值",
                "misjudge_rate": "错判率",
                "missjudge_rate": "漏判率",
                "issue_rate": "总问题率",
            }) if not team_summary_df.empty else pd.DataFrame()
            if not base_table.empty:
                base_table = base_table.sort_values(["批次", "样本正确率", "总问题率"], ascending=[True, False, True])
                st.dataframe(base_table, use_container_width=True, hide_index=True, height=360)

        if not batch_gap_df.empty:
            st.markdown("#### 🔭 基地差异聚焦")
            max_gap_row = batch_gap_df.sort_values("gap_pct", ascending=False).iloc[0]
            best_team_row = team_accuracy_df.sort_values(["accuracy", "qa_cnt"], ascending=[False, False]).iloc[0]
            weak_team_row = team_accuracy_df.sort_values(["accuracy", "qa_cnt"], ascending=[True, False]).iloc[0]

            focus_col1, focus_col2, focus_col3 = st.columns(3)
            with focus_col1:
                st.metric(
                    "批次内最大基地差值",
                    f"{max_gap_row['gap_pct']:.1f}%",
                    delta=f"{max_gap_row['batch_name']} · {display_text(max_gap_row['best_team_name'])} vs {display_text(max_gap_row['worst_team_name'])}",
                )
            with focus_col2:
                st.metric(
                    "当前表现最好基地",
                    f"{best_team_row['accuracy']:.1f}%",
                    delta=f"{best_team_row['batch_name']} · {display_text(best_team_row['team_name'])}",
                )
            with focus_col3:
                st.metric(
                    "当前待关注基地",
                    f"{weak_team_row['accuracy']:.1f}%",
                    delta=f"{weak_team_row['batch_name']} · {display_text(weak_team_row['team_name'])}",
                    delta_color="inverse",
                )

            diff_col1, diff_col2 = st.columns([1.2, 1])
            with diff_col1:
                heatmap_df = team_accuracy_df.pivot(index="team_name", columns="batch_name", values="accuracy").sort_index()
                if not heatmap_df.empty:
                    heatmap_values = heatmap_df.fillna(0)
                    heatmap_text = format_heatmap_text(heatmap_df)
                    fig_heatmap = go.Figure(
                        data=go.Heatmap(
                            z=heatmap_values.values,
                            x=heatmap_values.columns.tolist(),
                            y=heatmap_values.index.tolist(),
                            text=heatmap_text.values,
                            texttemplate="%{text}",
                            colorscale=[
                                [0.0, "#fee2e2"],
                                [0.45, "#fef3c7"],
                                [0.7, "#dbeafe"],
                                [1.0, "#10b981"],
                            ],
                            zmin=90,
                            zmax=100,
                            hovertemplate="批次：%{x}<br>基地/团队：%{y}<br>正确率：%{z:.2f}%<extra></extra>",
                        )
                    )
                    fig_heatmap.update_layout(
                        height=max(300, 90 + 52 * len(heatmap_values.index)),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=10, r=10, t=20, b=10),
                    )
                    render_plot(fig_heatmap, "overview_team_accuracy_heatmap")
            with diff_col2:
                gap_chart_df = batch_gap_df.sort_values(["gap_pct", "worst_team_acc"], ascending=[False, True]).copy()
                fig_gap = go.Figure()
                fig_gap.add_trace(go.Bar(
                    x=gap_chart_df["batch_name"],
                    y=gap_chart_df["gap_pct"],
                    name="基地差值",
                    marker_color="#f59e0b",
                    text=[f"{v:.1f}%" for v in gap_chart_df["gap_pct"]],
                    textposition="outside",
                ))
                fig_gap.add_trace(go.Scatter(
                    x=gap_chart_df["batch_name"],
                    y=gap_chart_df["worst_team_acc"],
                    name="最低基地正确率",
                    mode="lines+markers",
                    line=dict(color="#ef4444", width=2.5),
                    marker=dict(size=8),
                    yaxis="y2",
                ))
                fig_gap.update_layout(
                    height=340,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(title="基地差值 (%)"),
                    yaxis2=dict(title="最低基地正确率", overlaying="y", side="right", range=[90, 100]),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                render_plot(fig_gap, "overview_batch_gap_combo")

            gap_table = batch_gap_df.rename(columns={
                "batch_name": "批次",
                "team_cnt": "基地数",
                "best_team_name": "最好基地",
                "best_team_acc": "最高正确率",
                "worst_team_name": "待关注基地",
                "worst_team_acc": "最低正确率",
                "gap_pct": "批次内差值",
            })[["批次", "基地数", "最好基地", "最高正确率", "待关注基地", "最低正确率", "批次内差值"]]
            st.dataframe(gap_table.sort_values(["批次内差值", "最低正确率"], ascending=[False, True]), use_container_width=True, hide_index=True, height=260)

# ==================== 模块 2: 成长曲线 ====================
if active_view == "growth":
    st.markdown("#### 📈 批次成长曲线（入职天数视角）")

    if combined_qa_df.empty or filtered_batch_df.empty:
        st.info("暂无足够数据生成成长曲线。")
    else:
        growth_df = combined_qa_df.merge(filtered_batch_df[["batch_name", "join_date"]], on="batch_name", how="left")
        growth_df["biz_date_dt"] = pd.to_datetime(growth_df["biz_date"], errors="coerce")
        growth_df["join_date_dt"] = pd.to_datetime(growth_df["join_date"], errors="coerce")
        growth_df = growth_df.dropna(subset=["biz_date_dt", "join_date_dt"])
        growth_df["day_no"] = (growth_df["biz_date_dt"] - growth_df["join_date_dt"]).dt.days + 1
        growth_df = growth_df[growth_df["day_no"] >= 1]

        day_stage_df = growth_df.groupby(["batch_name", "day_no", "stage"], as_index=False).agg(
            qa_cnt=("qa_cnt", "sum"),
            correct_cnt=("correct_cnt", "sum"),
        )
        day_stage_df["accuracy"] = day_stage_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)

        fig_growth = go.Figure()
        for bn in sorted(day_stage_df["batch_name"].dropna().unique().tolist()):
            for stg in ["internal", "external", "formal"]:
                subset = day_stage_df[(day_stage_df["batch_name"] == bn) & (day_stage_df["stage"] == stg)]
                if subset.empty:
                    continue
                stage_label, stage_color, _, _ = get_stage_meta(stg)
                fig_growth.add_trace(go.Scatter(
                    x=subset["day_no"],
                    y=subset["accuracy"],
                    mode="lines+markers",
                    name=f"{bn}-{stage_label}",
                    line=dict(color=stage_color, width=2.5),
                    marker=dict(size=6),
                    hovertemplate="入职第 %{x} 天<br>正确率 %{y:.1f}%<extra></extra>",
                ))
        fig_growth.add_hline(y=98, line_dash="dash", line_color="#10b981", annotation_text="转正线 98%")
        fig_growth.update_layout(height=420, yaxis_title="正确率 (%)", xaxis_title="入职天数",
                                 legend=dict(orientation="h", yanchor="bottom", y=1.02),
                                 paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        render_plot(fig_growth, "growth_curve_main")

        col_g1, col_g2 = st.columns([1.2, 1])
        with col_g1:
            st.markdown("#### 📊 多批次成长速度对比")
            multi_growth = growth_df.groupby(["batch_name", "day_no"], as_index=False).agg(
                qa_cnt=("qa_cnt", "sum"),
                correct_cnt=("correct_cnt", "sum"),
            )
            multi_growth["accuracy"] = multi_growth.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
            fig_multi = px.line(
                multi_growth,
                x="day_no",
                y="accuracy",
                color="batch_name",
                markers=True,
                labels={"day_no": "入职天数", "accuracy": "正确率 (%)", "batch_name": "批次"},
            )
            fig_multi.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_multi, "growth_curve_compare")
        with col_g2:
            st.markdown("#### 🎯 阶段达标时间")
            milestone_rows = []
            for bn in sorted(growth_df["batch_name"].dropna().unique().tolist()):
                batch_stage_days = growth_df[growth_df["batch_name"] == bn].groupby("stage")["day_no"].max().to_dict()
                milestone_rows.append({
                    "批次": bn,
                    "内部天数": int(batch_stage_days.get("internal", 0) or 0),
                    "外部天数": int(batch_stage_days.get("external", 0) or 0),
                    "正式天数": int(batch_stage_days.get("formal", 0) or 0),
                })
            milestone_df = pd.DataFrame(milestone_rows)
            if not milestone_df.empty:
                milestone_long = milestone_df.melt(id_vars="批次", var_name="阶段", value_name="天数")
                fig_mile = px.bar(
                    milestone_long,
                    x="批次",
                    y="天数",
                    color="阶段",
                    barmode="stack",
                    color_discrete_map={"内部天数": "#8b5cf6", "外部天数": "#3b82f6", "正式天数": "#10b981"},
                )
                fig_mile.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_mile, "growth_milestone_chart")

# ==================== 模块 3: 阶段对比 ====================
if active_view == "compare":
    st.markdown("#### 🔄 个人阶段跃迁与结构对比")

    if person_stage_df.empty:
        st.info("暂无质检数据。")
    else:
        stage_avg = person_stage_df.groupby("stage", as_index=False).agg(
            qa_cnt=("qa_cnt", "sum"),
            correct_cnt=("correct_cnt", "sum"),
            per_capita_accuracy=("sample_accuracy", "mean"),
        )
        stage_avg["sample_accuracy"] = stage_avg.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
        stage_avg["accuracy"] = stage_avg["sample_accuracy"]

        p1, p2, p3, p4 = st.columns(4)
        with p1:
            sample_val = stage_avg.loc[stage_avg['stage'] == 'internal', 'sample_accuracy'].max() if 'internal' in stage_avg['stage'].values else 0
            per_capita_val = stage_avg.loc[stage_avg['stage'] == 'internal', 'per_capita_accuracy'].max() if 'internal' in stage_avg['stage'].values else 0
            st.metric("🏫 内部样本正确率", f"{sample_val:.1f}%", delta=f"人均 {per_capita_val:.1f}%")
        with p2:
            sample_val = stage_avg.loc[stage_avg['stage'] == 'external', 'sample_accuracy'].max() if 'external' in stage_avg['stage'].values else 0
            per_capita_val = stage_avg.loc[stage_avg['stage'] == 'external', 'per_capita_accuracy'].max() if 'external' in stage_avg['stage'].values else 0
            st.metric("🔍 外部样本正确率", f"{sample_val:.1f}%", delta=f"人均 {per_capita_val:.1f}%")
        with p3:
            sample_val = stage_avg.loc[stage_avg['stage'] == 'formal', 'sample_accuracy'].max() if 'formal' in stage_avg['stage'].values else 0
            per_capita_val = stage_avg.loc[stage_avg['stage'] == 'formal', 'per_capita_accuracy'].max() if 'formal' in stage_avg['stage'].values else 0
            st.metric("✅ 正式样本正确率", f"{sample_val:.1f}%", delta=f"人均 {per_capita_val:.1f}%")
        with p4:
            weak_cnt = int(person_stage_df[(person_stage_df["stage"] == "external") & (person_stage_df["sample_accuracy"] < 95)]["short_name"].nunique())
            st.metric("⚠️ 外部待关注", weak_cnt)

        compare_col1, compare_col2 = st.columns([1.15, 1])
        with compare_col1:
            fig_person = px.bar(
                person_stage_df.sort_values(["batch_name", "short_name", "stage"]),
                x="short_name",
                y="accuracy",
                color="stage",
                barmode="group",
                facet_row="batch_name",
                labels={"short_name": "姓名", "accuracy": "正确率 (%)", "stage": "阶段"},
                color_discrete_map={"internal": "#8b5cf6", "external": "#3b82f6", "formal": "#10b981"},
            )
            fig_person.update_layout(height=max(360, 280 * max(person_stage_df["batch_name"].nunique(), 1)), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_person, "compare_person_stage_bar")
        with compare_col2:
            stage_avg["阶段"] = stage_avg["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检", "formal": "✅ 正式上线"})
            stage_avg_long = stage_avg.melt(
                id_vars=["阶段"],
                value_vars=["sample_accuracy", "per_capita_accuracy"],
                var_name="口径",
                value_name="正确率",
            )
            stage_avg_long["口径"] = stage_avg_long["口径"].map({"sample_accuracy": "样本正确率", "per_capita_accuracy": "人均正确率"})
            fig_stage_avg = px.bar(
                stage_avg_long,
                x="阶段",
                y="正确率",
                color="口径",
                barmode="group",
                text="正确率",
                color_discrete_map={"样本正确率": "#10b981", "人均正确率": "#2563eb"},
            )
            fig_stage_avg.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_stage_avg.update_layout(height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            render_plot(fig_stage_avg, "compare_stage_average_bar")

        pivot_acc = person_stage_df.pivot_table(
            index=["batch_name", "short_name", "team_name"],
            columns="stage",
            values="accuracy",
            aggfunc="first",
        ).reset_index()
        pivot_qa = person_stage_df.pivot_table(
            index=["batch_name", "short_name", "team_name"],
            columns="stage",
            values="qa_cnt",
            aggfunc="first",
        ).reset_index()
        compare_table = pivot_acc.merge(pivot_qa, on=["batch_name", "short_name", "team_name"], how="left", suffixes=("", "_qa"))
        compare_table = compare_table.rename(columns={
            "batch_name": "批次",
            "short_name": "姓名",
            "team_name": "基地/团队",
            "internal": "🏫 内检正确率",
            "external": "🔍 外检正确率",
            "formal": "✅ 正式正确率",
            "internal_qa": "内检量",
            "external_qa": "外检量",
            "formal_qa": "正式量",
        })
        if "🏫 内检正确率" in compare_table.columns and "🔍 外检正确率" in compare_table.columns:
            compare_table["外检跃迁"] = (compare_table["🔍 外检正确率"] - compare_table["🏫 内检正确率"]).round(2)
        if "✅ 正式正确率" in compare_table.columns and "🔍 外检正确率" in compare_table.columns:
            compare_table["转正跃迁"] = (compare_table["✅ 正式正确率"] - compare_table["🔍 外检正确率"]).round(2)

        def _current_status(row):
            if pd.notna(row.get("✅ 正式正确率")):
                return "✅ 已正式上线"
            if pd.notna(row.get("🔍 外检正确率")) and row.get("🔍 外检正确率", 0) >= 98:
                return "🟢 接近转正"
            if pd.notna(row.get("🔍 外检正确率")) and row.get("🔍 外检正确率", 0) < 95:
                return "🔴 需关注"
            if pd.notna(row.get("🔍 外检正确率")):
                return "🔍 外部阶段"
            return "🏫 内部阶段"

        compare_table["当前状态"] = compare_table.apply(_current_status, axis=1)
        st.caption("这里仍然只展示单人样本正确率；人均正确率只用于批次、团队、owner 等聚合层。")
        st.markdown("#### 📋 阶段转化明细")
        st.dataframe(compare_table, use_container_width=True, hide_index=True, height=420)

# ==================== 模块 4: 个人追踪 ====================
if active_view == "person":
    st.markdown("#### 👤 个人追踪")
    st.caption("个人追踪页只展示单人样本正确率和错误明细，不展示聚合层的人均正确率。")

    if members_df.empty:
        st.info("暂无新人映射数据。")
    else:
        person_options = members_df.apply(
            lambda r: f"{r['reviewer_alias']} ({r['batch_name']} · {r['team_name']})", axis=1
        ).tolist()
        selected_person = st.selectbox("选择审核人", options=person_options, key="nc_person_select")

        if selected_person:
            alias = selected_person.split(" (")[0]
            person_info = members_df[members_df["reviewer_alias"] == alias].iloc[0]
            person_qa = combined_qa_df[combined_qa_df["reviewer_name"] == alias].copy() if not combined_qa_df.empty else pd.DataFrame()
            person_stage_view = person_qa.groupby("stage", as_index=False).agg(
                qa_cnt=("qa_cnt", "sum"),
                correct_cnt=("correct_cnt", "sum"),
            ) if not person_qa.empty else pd.DataFrame()
            if not person_stage_view.empty:
                person_stage_view["accuracy"] = person_stage_view.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)

            current_stage = "formal" if (not person_stage_view.empty and "formal" in person_stage_view["stage"].tolist()) else (
                "external" if (not person_stage_view.empty and "external" in person_stage_view["stage"].tolist()) else "internal"
            )
            stage_label, stage_color, stage_bg, _ = get_stage_meta(current_stage)
            days = (date.today() - person_info["join_date"]).days if person_info["join_date"] else 0

            internal_person_acc = person_stage_view.loc[person_stage_view["stage"] == "internal", "accuracy"].max() if not person_stage_view.empty and "internal" in person_stage_view["stage"].values else 0
            external_person_acc = person_stage_view.loc[person_stage_view["stage"] == "external", "accuracy"].max() if not person_stage_view.empty and "external" in person_stage_view["stage"].values else 0
            formal_person_acc = person_stage_view.loc[person_stage_view["stage"] == "formal", "accuracy"].max() if not person_stage_view.empty and "formal" in person_stage_view["stage"].values else 0
            total_person_qa = int(person_qa["qa_cnt"].sum()) if not person_qa.empty else 0

            st.markdown(f"""
            <div style="background:linear-gradient(135deg, #ffffff 0%, #F8FAFC 100%); border:1px solid #E5E7EB; border-radius:1rem; padding:1rem 1.2rem; margin-bottom:1rem;">
                <div style="display:flex; justify-content:space-between; gap:1rem; align-items:flex-start; flex-wrap:wrap;">
                    <div>
                        <div style="font-size:1.4rem; font-weight:700; color:#0F172A;">{person_info['reviewer_name']}</div>
                        <div style="margin-top:0.35rem; font-size:0.84rem; color:#64748B; line-height:1.6;">
                            {person_info['batch_name']} · {display_text(person_info['team_name'])} · 入职 {days} 天<br>
                            联营管理：{display_text(person_info['team_leader'])} · 交付PM：{display_text(person_info['delivery_pm'])} · 质培owner：{display_text(person_info['owner'])} · 导师/质检：{display_text(person_info['mentor_name'])}
                        </div>
                    </div>
                    <div style="padding:0.28rem 0.8rem; border-radius:999px; background:{stage_bg}; color:{stage_color}; font-size:0.8rem; font-weight:700; border:1px solid {stage_color};">{stage_label}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("🏫 内部正确率", f"{float(internal_person_acc or 0):.1f}%")
            with m2:
                st.metric("🔍 外部正确率", f"{float(external_person_acc or 0):.1f}%")
            with m3:
                st.metric("✅ 正式正确率", f"{float(formal_person_acc or 0):.1f}%")
            with m4:
                st.metric("📦 累计质检量", f"{total_person_qa:,}")

            if not person_qa.empty:
                detail_col1, detail_col2 = st.columns([1.2, 1])
                with detail_col1:
                    st.markdown("##### 📈 个人逐日趋势")
                    daily = person_qa.groupby(["biz_date", "stage"], as_index=False).agg(
                        qa_cnt=("qa_cnt", "sum"),
                        correct_cnt=("correct_cnt", "sum"),
                    )
                    daily["accuracy"] = daily.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
                    fig_p = go.Figure()
                    for stg in ["internal", "external", "formal"]:
                        subset = daily[daily["stage"] == stg]
                        if subset.empty:
                            continue
                        stage_name, stage_color, _, _ = get_stage_meta(stg)
                        fig_p.add_trace(go.Scatter(
                            x=pd.to_datetime(subset["biz_date"]),
                            y=subset["accuracy"],
                            mode="lines+markers",
                            name=stage_name,
                            line=dict(color=stage_color, width=2.5),
                            marker=dict(size=7),
                        ))
                    fig_p.add_hline(y=98, line_dash="dash", line_color="#10b981", annotation_text="转正线 98%")
                    fig_p.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    render_plot(fig_p, f"person_trend_{alias}")
                with detail_col2:
                    st.markdown("##### 📊 阶段结构")
                    if not person_stage_view.empty:
                        person_stage_view["阶段"] = person_stage_view["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检", "formal": "✅ 正式上线"})
                        fig_person_stage = px.pie(
                            person_stage_view,
                            values="qa_cnt",
                            names="阶段",
                            hole=0.55,
                            color="阶段",
                            color_discrete_map={"🏫 内部质检": "#8b5cf6", "🔍 外部质检": "#3b82f6", "✅ 正式上线": "#10b981"},
                        )
                        fig_person_stage.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                        render_plot(fig_person_stage, f"person_stage_{alias}")

            st.markdown("##### 📋 近期错误明细")
            detail_df = load_newcomer_qa_detail(alias, 80)
            if detail_df is not None and not detail_df.empty:
                errors = detail_df[detail_df["is_correct"] == 0].copy()
                if not errors.empty:
                    display_errors = errors[["biz_date", "stage", "queue_name", "content_type", "training_topic", "risk_level", "comment_text", "raw_judgement", "final_judgement", "error_type", "qa_note"]].copy()
                    display_errors.columns = ["日期", "阶段", "队列", "内容类型", "培训专题", "风险等级", "评论文本", "一审结果", "质检结果", "错误类型", "质检备注"]
                    display_errors["阶段"] = display_errors["阶段"].map({"internal": "🏫 内检", "external": "🔍 外检", "formal": "✅ 正式上线"}).fillna("—")
                    st.dataframe(display_errors, use_container_width=True, hide_index=True, height=320)
                    csv = display_errors.to_csv(index=False).encode("utf-8-sig")
                    st.download_button("📥 导出错误明细", csv, file_name=f"errors_{alias}.csv", mime="text/csv")
                else:
                    st.success("🎉 该新人暂无错误记录。")
            else:
                st.info("暂无个人明细数据。")

# ==================== 模块 5: 维度分析 ====================
if active_view == "dimension":
    st.markdown("#### 📊 维度分析")

    if combined_qa_df.empty:
        st.info("暂无质检数据，暂时无法生成维度分析。")
    else:
        st.info("对照 local demo，这一页已经补齐批次/基地差异、管理链路、错误类型、问题率。下面这张表会直接告诉你哪些维度当前已经可做，哪些还卡在数据层。")
        st.markdown("##### 🔧 对照 demo 的维度可用性")
        st.dataframe(dimension_status_df, use_container_width=True, hide_index=True)

        row1_col1, row1_col2 = st.columns([1.15, 1])
        with row1_col1:
            st.markdown("##### 🏢 批次 × 基地差异热力图")
            heatmap_options = {"整体": "all", "内部质检": "internal", "外部质检": "external", "正式上线": "formal"}
            heatmap_label = st.selectbox("热力图口径", options=list(heatmap_options.keys()), key="nc_dim_heatmap_stage")
            heatmap_code = heatmap_options[heatmap_label]
            if heatmap_code == "all":
                heatmap_source = team_accuracy_df.copy()
            else:
                heatmap_source = stage_team_accuracy_df[stage_team_accuracy_df["stage"] == heatmap_code].copy()

            if not heatmap_source.empty:
                heatmap_matrix = heatmap_source.pivot(index="team_name", columns="batch_name", values="sample_accuracy").sort_index()
                heatmap_text = format_heatmap_text(heatmap_matrix)
                fig_base = go.Figure(
                    data=go.Heatmap(
                        z=heatmap_matrix.fillna(0).values,
                        x=heatmap_matrix.columns.tolist(),
                        y=heatmap_matrix.index.tolist(),
                        text=heatmap_text.values,
                        texttemplate="%{text}",
                        colorscale=[
                            [0.0, "#fee2e2"],
                            [0.45, "#fef3c7"],
                            [0.7, "#dbeafe"],
                            [1.0, "#10b981"],
                        ],
                        zmin=90,
                        zmax=100,
                        hovertemplate="批次：%{x}<br>基地/团队：%{y}<br>样本正确率：%{z:.2f}%<extra></extra>",
                    )
                )
                fig_base.update_layout(
                    height=max(320, 90 + 52 * len(heatmap_matrix.index)),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                render_plot(fig_base, "dimension_team_heatmap")
            else:
                st.info("当前口径下暂无基地差异数据。")

            if not batch_gap_df.empty:
                gap_preview = batch_gap_df.rename(columns={
                    "batch_name": "批次",
                    "best_team_name": "最好基地",
                    "best_team_acc": "最高正确率",
                    "worst_team_name": "待关注基地",
                    "worst_team_acc": "最低正确率",
                    "gap_pct": "批次内差值",
                })[["批次", "最好基地", "最高正确率", "待关注基地", "最低正确率", "批次内差值"]]
                st.dataframe(gap_preview.sort_values("批次内差值", ascending=False), use_container_width=True, hide_index=True, height=220)

        with row1_col2:
            st.markdown("##### 🥊 批次差异榜")
            if not batch_compare_df.empty:
                batch_rank_df = batch_compare_df.merge(batch_gap_df[["batch_name", "sample_gap_pct", "per_capita_gap_pct"]], on="batch_name", how="left") if not batch_gap_df.empty else batch_compare_df.copy()
                batch_rank_df = ensure_default_columns(batch_rank_df, {"sample_gap_pct": 0.0, "per_capita_gap_pct": 0.0})
                fig_batch_rank = px.bar(
                    batch_rank_df.sort_values(["sample_accuracy", "sample_gap_pct"], ascending=[False, False]),
                    x="batch_name",
                    y="sample_accuracy",
                    color="sample_gap_pct",
                    text="sample_accuracy",
                    labels={"batch_name": "批次", "sample_accuracy": "样本正确率 (%)", "sample_gap_pct": "样本口径基地差值"},
                    color_continuous_scale="Bluered",
                )
                fig_batch_rank.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_batch_rank.update_layout(height=320, coloraxis_colorbar_title="样本差值", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_batch_rank, "dimension_batch_rank")

                batch_rank_table = batch_rank_df.rename(columns={
                    "batch_name": "批次",
                    "member_cnt": "人数",
                    "qa_cnt": "质检量",
                    "sample_accuracy": "样本正确率",
                    "per_capita_accuracy": "人均正确率",
                    "accuracy_gap": "口径差值",
                    "misjudge_rate": "错判率",
                    "missjudge_rate": "漏判率",
                    "sample_gap_pct": "样本口径基地差值",
                    "per_capita_gap_pct": "人均口径基地差值",
                    "training_days": "培训天数",
                })[["批次", "人数", "质检量", "样本正确率", "人均正确率", "口径差值", "样本口径基地差值", "人均口径基地差值", "错判率", "漏判率", "培训天数"]]
                st.dataframe(batch_rank_table.sort_values(["样本正确率", "样本口径基地差值"], ascending=[False, False]), use_container_width=True, hide_index=True, height=260)

        st.markdown("##### 🧠 专题 / 风险 / 内容类型")
        if not newcomer_dimension_df.empty:
            newcomer_dimension_df = normalize_numeric_columns(newcomer_dimension_df, ["qa_cnt", "correct_cnt"])
            newcomer_dimension_df["accuracy"] = newcomer_dimension_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
            newcomer_dimension_df["stage_label"] = newcomer_dimension_df["stage"].map({"internal": "🏫 内部质检", "external": "🔍 外部质检"}).fillna("新人质检")

            st.markdown("###### 👶 新人内 / 外检专题维度")
            n_dim_col1, n_dim_col2, n_dim_col3 = st.columns(3)
            with n_dim_col1:
                newcomer_topic_df = newcomer_dimension_df.groupby(["training_topic", "stage_label"], as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False).head(12)
                newcomer_topic_df["正确率"] = newcomer_topic_df.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
                fig_newcomer_topic = px.bar(
                    newcomer_topic_df.sort_values(["stage_label", "正确率"], ascending=[True, True]),
                    x="正确率",
                    y="training_topic",
                    color="stage_label",
                    orientation="h",
                    text="正确率",
                    labels={"training_topic": "培训专题", "正确率": "正确率 (%)", "stage_label": "阶段"},
                    color_discrete_map={"🏫 内部质检": "#8b5cf6", "🔍 外部质检": "#3b82f6"},
                )
                fig_newcomer_topic.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_newcomer_topic.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_newcomer_topic, "dimension_newcomer_topic_bar")
            with n_dim_col2:
                newcomer_risk_df = newcomer_dimension_df.groupby(["risk_level", "stage_label"], as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False)
                newcomer_risk_df["正确率"] = newcomer_risk_df.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
                fig_newcomer_risk = px.bar(
                    newcomer_risk_df,
                    x="risk_level",
                    y="质检量",
                    color="stage_label",
                    barmode="group",
                    text="正确率",
                    labels={"risk_level": "风险等级", "质检量": "质检量", "stage_label": "阶段"},
                    color_discrete_map={"🏫 内部质检": "#8b5cf6", "🔍 外部质检": "#3b82f6"},
                )
                fig_newcomer_risk.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_newcomer_risk.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_newcomer_risk, "dimension_newcomer_risk_bar")
            with n_dim_col3:
                newcomer_content_df = newcomer_dimension_df.groupby("content_type", as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False).head(8)
                newcomer_content_df["正确率"] = newcomer_content_df.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
                fig_newcomer_content = px.bar(
                    newcomer_content_df.sort_values("质检量", ascending=True),
                    x="质检量",
                    y="content_type",
                    orientation="h",
                    text="正确率",
                    labels={"content_type": "内容类型", "质检量": "质检量"},
                    color="正确率",
                    color_continuous_scale="RdYlGn",
                )
                fig_newcomer_content.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_newcomer_content.update_layout(height=340, coloraxis_colorbar_title="正确率", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_newcomer_content, "dimension_newcomer_content_bar")

            newcomer_topic_view = newcomer_dimension_df.groupby(["batch_name", "team_name", "stage_label", "training_topic"], as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False)
            newcomer_topic_view["正确率"] = newcomer_topic_view.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
            newcomer_topic_view = newcomer_topic_view.rename(columns={"batch_name": "批次", "team_name": "基地/团队", "stage_label": "阶段", "training_topic": "培训专题"})
            st.dataframe(newcomer_topic_view[["批次", "基地/团队", "阶段", "培训专题", "质检量", "正确率"]].head(20), use_container_width=True, hide_index=True, height=220)
        elif newcomer_dimension_ready:
            st.caption("新人内/外检字段已经补齐，但当前筛选范围内还没有带专题/风险/内容类型的新导入数据；继续导新文件或回填历史数据后，这块会直接亮起来。")
        else:
            st.caption("当前新人内/外检还没有可用的专题/风险/内容类型字段，暂时先由正式阶段补位展示。")

        st.markdown("###### ✅ 正式阶段专题维度")
        if not formal_dimension_df.empty:
            formal_dimension_df = normalize_numeric_columns(formal_dimension_df, ["qa_cnt", "correct_cnt"])
            formal_dimension_df["accuracy"] = formal_dimension_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)

            dim_col1, dim_col2, dim_col3 = st.columns(3)
            with dim_col1:
                topic_df = formal_dimension_df.groupby("training_topic", as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False).head(8)
                topic_df["正确率"] = topic_df.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
                fig_topic = px.bar(
                    topic_df.sort_values("正确率", ascending=True),
                    x="正确率",
                    y="training_topic",
                    orientation="h",
                    text="正确率",
                    labels={"training_topic": "培训专题", "正确率": "正确率 (%)"},
                    color="质检量",
                    color_continuous_scale="Blues",
                )
                fig_topic.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_topic.update_layout(height=340, coloraxis_colorbar_title="质检量", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_topic, "dimension_formal_topic_bar")
            with dim_col2:
                risk_df = formal_dimension_df.groupby("risk_level", as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False)
                risk_df["正确率"] = risk_df.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
                fig_risk = px.pie(
                    risk_df,
                    values="质检量",
                    names="risk_level",
                    hole=0.55,
                    color="risk_level",
                )
                fig_risk.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_risk, "dimension_formal_risk_pie")
            with dim_col3:
                content_df = formal_dimension_df.groupby("content_type", as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False).head(8)
                content_df["正确率"] = content_df.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
                fig_content = px.bar(
                    content_df.sort_values("质检量", ascending=True),
                    x="质检量",
                    y="content_type",
                    orientation="h",
                    text="正确率",
                    labels={"content_type": "内容类型", "质检量": "质检量"},
                    color="正确率",
                    color_continuous_scale="RdYlGn",
                )
                fig_content.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_content.update_layout(height=340, coloraxis_colorbar_title="正确率", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_content, "dimension_formal_content_bar")

            topic_view = formal_dimension_df.groupby(["batch_name", "team_name", "training_topic"], as_index=False).agg(质检量=("qa_cnt", "sum"), 正确量=("correct_cnt", "sum")).sort_values("质检量", ascending=False)
            topic_view["正确率"] = topic_view.apply(lambda r: safe_pct(r["正确量"], r["质检量"]), axis=1)
            topic_view = topic_view.rename(columns={"batch_name": "批次", "team_name": "基地/团队", "training_topic": "培训专题"})
            st.dataframe(topic_view[["批次", "基地/团队", "培训专题", "质检量", "正确率"]].head(20), use_container_width=True, hide_index=True, height=220)
        else:
            st.caption("当前筛选范围下，正式阶段还没有可用的专题/风险/内容类型明细，或底层表未补这些字段。")

        row2_col1, row2_col2 = st.columns(2)
        with row2_col1:
            st.markdown("##### 👨‍🏫 导师/质检视角")
            mentor_df = management_perf_df.groupby("mentor_name", as_index=False).agg(
                member_cnt=("member_cnt", "sum"),
                qa_cnt=("qa_cnt", "sum"),
                correct_cnt=("correct_cnt", "sum"),
                misjudge_cnt=("misjudge_cnt", "sum"),
                missjudge_cnt=("missjudge_cnt", "sum"),
            ) if not management_perf_df.empty else pd.DataFrame()
            if not mentor_df.empty:
                mentor_df["sample_accuracy"] = mentor_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
                mentor_df["issue_rate"] = mentor_df.apply(lambda r: safe_pct(r["misjudge_cnt"] + r["missjudge_cnt"], r["qa_cnt"]), axis=1)
                fig_mentor = px.bar(
                    mentor_df.sort_values("sample_accuracy", ascending=False),
                    x="mentor_name",
                    y="sample_accuracy",
                    color="issue_rate",
                    text="sample_accuracy",
                    labels={"mentor_name": "导师/质检", "sample_accuracy": "样本正确率 (%)", "issue_rate": "问题率 (%)"},
                    color_continuous_scale="Blues",
                )
                fig_mentor.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_mentor.update_layout(height=360, coloraxis_colorbar_title="问题率", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_mentor, "dimension_mentor_bar")

        with row2_col2:
            st.markdown("##### 📊 质培owner / 交付PM 总览")
            owner_df = management_perf_df.groupby(["owner", "delivery_pm"], as_index=False).agg(
                member_cnt=("member_cnt", "sum"),
                qa_cnt=("qa_cnt", "sum"),
                correct_cnt=("correct_cnt", "sum"),
                misjudge_cnt=("misjudge_cnt", "sum"),
                missjudge_cnt=("missjudge_cnt", "sum"),
            ) if not management_perf_df.empty else pd.DataFrame()
            if not owner_df.empty:
                owner_df["sample_accuracy"] = owner_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
                owner_df["issue_rate"] = owner_df.apply(lambda r: safe_pct(r["misjudge_cnt"] + r["missjudge_cnt"], r["qa_cnt"]), axis=1)
                owner_df["owner_label"] = owner_df["owner"] + " · " + owner_df["delivery_pm"]
                fig_owner = px.bar(
                    owner_df.sort_values("sample_accuracy", ascending=False),
                    x="owner_label",
                    y="sample_accuracy",
                    color="issue_rate",
                    text="sample_accuracy",
                    labels={"owner_label": "质培owner / 交付PM", "sample_accuracy": "样本正确率 (%)", "issue_rate": "问题率 (%)"},
                    color_continuous_scale="Greens",
                )
                fig_owner.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_owner.update_layout(height=360, coloraxis_colorbar_title="问题率", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_owner, "dimension_owner_bar")

        row3_col1, row3_col2 = st.columns(2)
        with row3_col1:
            st.markdown("##### ⚠️ 基地错判 / 漏判率")
            if not team_issue_df.empty:
                issue_chart_df = team_issue_df.copy()
                issue_chart_df["label"] = issue_chart_df["batch_name"] + " · " + issue_chart_df["team_name"]
                issue_chart_df = issue_chart_df.sort_values(["misjudge_rate", "missjudge_rate"], ascending=[False, False]).head(10)
                fig_issue = go.Figure()
                fig_issue.add_trace(go.Bar(
                    x=issue_chart_df["misjudge_rate"],
                    y=issue_chart_df["label"],
                    orientation="h",
                    name="错判率",
                    marker_color="#f97316",
                    text=[f"{v:.1f}%" for v in issue_chart_df["misjudge_rate"]],
                    textposition="outside",
                ))
                fig_issue.add_trace(go.Bar(
                    x=issue_chart_df["missjudge_rate"],
                    y=issue_chart_df["label"],
                    orientation="h",
                    name="漏判率",
                    marker_color="#ef4444",
                    text=[f"{v:.1f}%" for v in issue_chart_df["missjudge_rate"]],
                    textposition="outside",
                ))
                fig_issue.update_layout(barmode="group", height=360, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_issue, "dimension_issue_rate_bar")

        with row3_col2:
            st.markdown("##### 🏷️ 错误类型 Top")
            if error_summary_df is not None and not error_summary_df.empty:
                error_top = error_summary_df.groupby("error_type", as_index=False)["error_cnt"].sum().sort_values("error_cnt", ascending=False).head(10)
                fig_error = px.bar(
                    error_top.sort_values("error_cnt"),
                    x="error_cnt",
                    y="error_type",
                    orientation="h",
                    text="error_cnt",
                    labels={"error_cnt": "错误次数", "error_type": "错误类型"},
                    color="error_cnt",
                    color_continuous_scale="Reds",
                )
                fig_error.update_layout(height=360, coloraxis_showscale=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_error, "dimension_error_top_bar")
            else:
                st.info("当前筛选范围内暂无错误类型明细。")

        row4_col1, row4_col2 = st.columns([1.15, 1])
        with row4_col1:
            st.markdown("##### 🎯 基地稳定性象限")
            if not team_issue_df.empty:
                stability_df = team_issue_df.copy()
                stability_df["label"] = stability_df["batch_name"] + " · " + stability_df["team_name"]
                fig_stability = px.scatter(
                    stability_df,
                    x="issue_rate",
                    y="accuracy",
                    size="qa_cnt",
                    color="batch_name",
                    text="team_name",
                    hover_name="label",
                    labels={"issue_rate": "总问题率 (%)", "accuracy": "样本正确率 (%)", "qa_cnt": "质检量", "batch_name": "批次"},
                )
                fig_stability.add_vline(x=2.5, line_dash="dash", line_color="#f59e0b")
                fig_stability.add_hline(y=97, line_dash="dash", line_color="#10b981")
                fig_stability.update_traces(textposition="top center", marker=dict(line=dict(width=1, color="#ffffff")))
                fig_stability.update_layout(height=380, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                render_plot(fig_stability, "dimension_team_stability_scatter")
            else:
                st.info("当前暂无可用于象限分析的基地数据。")

        with row4_col2:
            st.markdown("##### 🧾 待关注基地榜")
            if not team_issue_df.empty:
                watch_team_df = team_issue_df.copy()
                watch_team_df["关注分"] = (100 - watch_team_df["accuracy"]) + (watch_team_df["issue_rate"] * 2)
                watch_view = watch_team_df.rename(columns={
                    "batch_name": "批次",
                    "team_name": "基地/团队",
                    "member_cnt": "人数",
                    "qa_cnt": "质检量",
                    "sample_accuracy": "样本正确率",
                    "per_capita_accuracy": "人均正确率",
                    "accuracy_gap": "口径差值",
                    "misjudge_rate": "错判率",
                    "missjudge_rate": "漏判率",
                    "issue_rate": "总问题率",
                    "关注分": "关注分",
                })[["批次", "基地/团队", "人数", "质检量", "样本正确率", "人均正确率", "口径差值", "错判率", "漏判率", "总问题率", "关注分"]]
                st.dataframe(watch_view.sort_values(["关注分", "样本正确率"], ascending=[False, True]).head(12), use_container_width=True, hide_index=True, height=380)
            else:
                st.info("当前没有需要额外关注的基地数据。")

        st.markdown("#### 🔍 管理链路明细")
        if not management_perf_df.empty:
            management_table = management_perf_df.rename(columns={
                "team_leader": "联营管理",
                "delivery_pm": "交付PM",
                "owner": "质培owner",
                "mentor_name": "导师/质检",
                "member_cnt": "人数",
                "qa_cnt": "质检量",
                "sample_accuracy": "样本正确率",
                "per_capita_accuracy": "人均正确率",
                "accuracy_gap": "口径差值",
                "misjudge_rate": "错判率",
                "missjudge_rate": "漏判率",
            })[["联营管理", "交付PM", "质培owner", "导师/质检", "人数", "质检量", "样本正确率", "人均正确率", "口径差值", "错判率", "漏判率"]]
            st.dataframe(management_table.sort_values(["样本正确率", "质检量"], ascending=[False, False]), use_container_width=True, hide_index=True, height=360)

# ==================== 模块 6: 异常告警 ====================
if active_view == "alert":
    st.markdown("#### ⚠️ 异常告警")

    if combined_qa_df.empty:
        st.info("暂无质检数据，无法生成告警。")
    else:
        recent_date = combined_qa_df["biz_date"].max()
        p0_df = recent_person_perf_df[recent_person_perf_df["risk_level"] == "P0"].copy() if not recent_person_perf_df.empty else pd.DataFrame()
        p1_df = recent_person_perf_df[recent_person_perf_df["risk_level"] == "P1"].copy() if not recent_person_perf_df.empty else pd.DataFrame()
        near_grad_df = recent_person_perf_df[recent_person_perf_df["risk_level"] == "NEAR"].copy() if not recent_person_perf_df.empty else pd.DataFrame()
        batch_risk_df = batch_watch_df[(batch_watch_df["gap_pct"] >= 2.5) | (batch_watch_df["p0_cnt"] > 0) | (batch_watch_df["p1_cnt"] > 0)].copy() if not batch_watch_df.empty else pd.DataFrame()
        practice_count = int(practice_df["row_cnt"].sum()) if 'practice_df' in locals() and not practice_df.empty else 0

        error_focus_df = pd.DataFrame()
        if error_summary_df is not None and not error_summary_df.empty:
            batch_error_total = error_summary_df.groupby("batch_name", as_index=False)["error_cnt"].sum().rename(columns={"error_cnt": "batch_error_cnt"})
            batch_error_top = error_summary_df.groupby(["batch_name", "error_type"], as_index=False)["error_cnt"].sum()
            batch_error_top = batch_error_top.sort_values(["batch_name", "error_cnt"], ascending=[True, False]).groupby("batch_name", as_index=False).head(1)
            error_focus_df = batch_error_top.merge(batch_error_total, on="batch_name", how="left")
            error_focus_df["top_error_share"] = error_focus_df.apply(lambda r: safe_pct(r["error_cnt"], r["batch_error_cnt"]), axis=1)
            error_focus_df = error_focus_df[error_focus_df["top_error_share"] >= 30].copy()

        st.info("告警口径：近 7 天滚动统计。个人与告警阈值继续按单人样本正确率判断；P0 = 样本正确率 < 90% 或漏判率 ≥ 2%；P1 = 样本正确率 < 95% 或总问题率 ≥ 2.5%；接近转正 = 外检样本正确率 97.5%~98%。")

        a1, a2, a3, a4, a5 = st.columns(5)
        with a1:
            st.metric("🔴 P0", len(p0_df))
        with a2:
            st.metric("🟡 P1", len(p1_df))
        with a3:
            st.metric("🔵 接近转正", len(near_grad_df))
        with a4:
            st.metric("🧪 借调练习", practice_count)
        with a5:
            st.metric("🏷️ 批次级提醒", len(batch_risk_df) + len(error_focus_df))

        if not batch_watch_df.empty:
            st.markdown("##### 🧭 风险驾驶舱")
            cockpit_df = batch_watch_df.copy()
            cockpit_df["风险批次数"] = cockpit_df["risk_label"].str.contains("风险").astype(int)
            cockpit_df["关注批次数"] = cockpit_df["risk_label"].str.contains("关注").astype(int)
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("🔴 风险批次数", int(cockpit_df["风险批次数"].sum()))
            with c2:
                st.metric("🟡 关注批次数", int(cockpit_df["关注批次数"].sum()))
            with c3:
                st.metric("📏 平均基地差值", f"{cockpit_df['gap_pct'].mean():.1f}%")
            with c4:
                top_focus = cockpit_df.sort_values(["gap_pct", "accuracy"], ascending=[False, True]).iloc[0]
                st.metric("🎯 当前最需盯批次", display_text(top_focus["batch_name"]), delta=f"差值 {float(top_focus['gap_pct']):.1f}%")

        risk_col1, risk_col2 = st.columns(2)
        with risk_col1:
            st.markdown("##### 🔴 P0 / P1 人员")
            risk_people_df = pd.concat([p0_df.assign(告警级别="P0"), p1_df.assign(告警级别="P1")], ignore_index=True) if (not p0_df.empty or not p1_df.empty) else pd.DataFrame()
            if not risk_people_df.empty:
                risk_people_view = risk_people_df.rename(columns={
                    "short_name": "姓名",
                    "batch_name": "批次",
                    "team_name": "基地/团队",
                    "team_leader": "联营管理",
                    "mentor_name": "导师/质检",
                    "accuracy": "近7天样本正确率",
                    "misjudge_rate": "错判率",
                    "missjudge_rate": "漏判率",
                    "issue_rate": "总问题率",
                    "qa_cnt": "质检量",
                })[["告警级别", "姓名", "批次", "基地/团队", "联营管理", "导师/质检", "质检量", "近7天样本正确率", "错判率", "漏判率", "总问题率"]]
                st.dataframe(risk_people_view.sort_values(["告警级别", "近7天样本正确率", "总问题率"], ascending=[True, True, False]), use_container_width=True, hide_index=True, height=280)
            else:
                st.success("当前没有 P0 / P1 人员。")

        with risk_col2:
            st.markdown("##### 🔵 接近转正 / 借调练习")
            if not near_grad_df.empty:
                near_view = near_grad_df.rename(columns={
                    "short_name": "姓名",
                    "batch_name": "批次",
                    "team_name": "基地/团队",
                    "accuracy": "近7天样本正确率",
                    "qa_cnt": "质检量",
                    "mentor_name": "导师/质检",
                })[["姓名", "批次", "基地/团队", "导师/质检", "质检量", "近7天样本正确率"]]
                st.dataframe(near_view.sort_values(["近7天样本正确率", "质检量"], ascending=[False, False]), use_container_width=True, hide_index=True, height=160)
            else:
                st.info("当前没有接近转正人员。")

            if 'practice_df' in locals() and not practice_df.empty:
                practice_view = practice_df.rename(columns={
                    "reviewer_name": "审核人",
                    "stage": "阶段",
                    "row_cnt": "练习记录数",
                    "start_date": "开始日期",
                    "end_date": "结束日期",
                })[["审核人", "阶段", "练习记录数", "开始日期", "结束日期"]]
                st.dataframe(practice_view, use_container_width=True, hide_index=True, height=120)

        st.markdown("##### 🛠️ 基地级风险拆解与带教动作")
        if not team_alert_df.empty:
            alert_team_col1, alert_team_col2 = st.columns([1.15, 1])
            with alert_team_col1:
                team_alert_view = team_alert_df.rename(columns={
                    "batch_name": "批次",
                    "team_name": "基地/团队",
                    "member_cnt": "人数",
                    "qa_cnt": "质检量",
                    "sample_accuracy": "样本正确率",
                    "per_capita_accuracy": "人均正确率",
                    "accuracy_gap": "口径差值",
                    "issue_rate": "总问题率",
                    "misjudge_rate": "错判率",
                    "missjudge_rate": "漏判率",
                    "top_error_type": "主要错误类型",
                    "top_error_share": "错误集中度",
                    "risk_label": "批次风险",
                    "建议动作": "建议动作",
                })[["批次风险", "批次", "基地/团队", "人数", "质检量", "样本正确率", "人均正确率", "口径差值", "总问题率", "错判率", "漏判率", "主要错误类型", "错误集中度", "建议动作"]]
                st.dataframe(team_alert_view.head(12), use_container_width=True, hide_index=True, height=320)
            with alert_team_col2:
                for _, row in team_alert_df.head(4).iterrows():
                    accent = "#dc2626" if float(row["关注分"]) >= 8 else ("#d97706" if float(row["关注分"]) >= 5 else "#059669")
                    bg = "#fef2f2" if accent == "#dc2626" else ("#fffbeb" if accent == "#d97706" else "#ecfdf5")
                    st.markdown(f"""
                    <div style="padding: 0.95rem 1rem; border-radius: 0.75rem; background: {bg}; border-left: 4px solid {accent}; margin-bottom: 0.75rem;">
                        <div style="font-size: 0.82rem; color: {accent}; font-weight: 700; margin-bottom: 0.25rem;">{display_text(row.get('batch_name'))} · {display_text(row.get('team_name'))}</div>
                        <div style="font-size: 0.92rem; color: #111827; line-height: 1.65;">
                            样本正确率 <strong>{float(row['sample_accuracy']):.1f}%</strong>，人均正确率 <strong>{float(row['per_capita_accuracy']):.1f}%</strong>，主要错误：<strong>{display_text(row.get('top_error_type'))}</strong>
                        </div>
                        <div style="font-size: 0.84rem; color: #475569; margin-top: 0.45rem;">建议动作：{row['建议动作']}</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.success("当前没有需要重点拆解的基地级风险。")

        st.markdown("##### 🧭 批次级提醒")
        batch_alert_cards = []
        if not batch_risk_df.empty:
            for _, row in batch_risk_df.sort_values(["gap_pct", "accuracy"], ascending=[False, True]).iterrows():
                batch_alert_cards.append((
                    row["risk_label"],
                    f"**{row['batch_name']}** 批次内基地差值 **{row['gap_pct']:.1f}%**，待关注基地：**{display_text(row['worst_team_name'])}**（{float(row['worst_team_acc']):.1f}%）",
                    f"优先辅导：{row['focus_people']}",
                    row["risk_bg"],
                    row["risk_color"],
                ))
        if not error_focus_df.empty:
            for _, row in error_focus_df.sort_values("top_error_share", ascending=False).iterrows():
                batch_alert_cards.append((
                    "🟡 专题提醒",
                    f"**{row['batch_name']}** 当前错误集中在 **{row['error_type']}**，占近 7 天错误的 **{row['top_error_share']:.1f}%**",
                    "建议围绕该错误类型安排专项复盘或抽样复训。",
                    "#fffbeb",
                    "#d97706",
                ))

        if not batch_alert_cards:
            st.markdown("""
            <div style='background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%); padding: 1rem; border-radius: 0.75rem; text-align: center; border: 1px solid #10B981;'>
                <div style='color: #10B981; font-weight: 700; font-size: 1.2rem;'>✅ 当前无异常告警</div>
                <div style='font-size: 0.85rem; color: #047857;'>当前筛选范围内，新人整体表现稳定。</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for title, msg, suggestion, bg, border in batch_alert_cards[:12]:
                st.markdown(f"""
                <div style="padding: 1rem; border-radius: 0.75rem; background: {bg}; border-left: 4px solid {border}; margin-bottom: 0.75rem;">
                    <div style="font-size: 0.82rem; color: {border}; font-weight: 700; margin-bottom: 0.3rem;">{title}</div>
                    <div style="font-size: 0.92rem; color: #111827; line-height: 1.6;">{msg}</div>
                    <div style="font-size: 0.84rem; color: #475569; margin-top: 0.45rem;">{suggestion}</div>
                </div>
                """, unsafe_allow_html=True)

        if error_summary_df is not None and not error_summary_df.empty:
            top_error = error_summary_df.groupby("error_type", as_index=False)["error_cnt"].sum().sort_values("error_cnt", ascending=False).head(5)
            st.markdown("#### 🧩 近期高频错误")
            st.dataframe(top_error.rename(columns={"error_type": "错误类型", "error_cnt": "错误次数"}), use_container_width=True, hide_index=True)

# ==================== 底部说明 ====================
st.markdown("---")
st.markdown("""
<div style='background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%); padding: 1rem; border-radius: 0.75rem; border: 1px solid #E5E7EB;'>
    <div style='font-size: 0.85rem; color: #475569; line-height: 1.6;'>
        <strong>💡 阶段识别规则：</strong><br>
        · 文件名含「10816」→ 外部质检<br>
        · 文件队列含「新人评论测试」或文件名含「新人」→ 内部质检<br>
        · 其他 → 正式上线（通过审核人名自动关联）<br>
        · 正式队列借调到新人队列练习的人员，不计入新人批次统计<br>
        · 聚合层统一同时展示「样本正确率 + 人均正确率」；个人追踪页只看单人样本正确率<br>
        <span style='color: #64748B; font-size: 0.8rem;'>审核人映射：名单姓名 → 「云雀联营-」+ 姓名；批次归属按 reviewer_alias + biz_date + 生效区间判断</span>
    </div>
</div>
""", unsafe_allow_html=True)
