"""新人追踪页：批次管理 + 成长曲线 + 阶段对比 + 个人追踪 + 维度分析 + 异常告警。

数据来源：
- dim_newcomer_batch: 新人映射表（姓名→批次→基地/团队→联营管理→交付PM→质培owner→导师/质检）
- fact_newcomer_qa: 新人质检明细（内检+外检，独立存储）
- fact_qa_event + mart_day_auditor: 正式上线后的质检数据（通过 reviewer_name 关联）

阶段识别规则：
- 内部质检: 文件队列含"新人评论测试" 或 文件名含"新人"
- 外部质检: 文件名含"10816"
- 正式上线: 走正常队列，审核人名出现在 dim_newcomer_batch 中

架构说明（Phase 7 拆分后）：
  本文件只负责：全局样式、数据加载协调、侧边栏筛选、ctx 组装、视图路由分发。
  所有视图渲染逻辑拆到 views/newcomer/ 下的独立模块中。
  所有共享工具函数提到 views/newcomer/_shared.py。
  所有 SQL 查询函数提到 views/newcomer/_data.py。
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from services.newcomer_aggregates import build_newcomer_aggregate_payload
from storage.repository import DashboardRepository
from views.newcomer import (
    render_overview,
    render_growth,
    render_compare,
    render_person,
    render_dimension,
    render_alert,
)
from views.newcomer._shared import (
    classify_batch_risk,
    display_text,
    format_name_list,
    is_non_newcomer_practice_reviewer,
    safe_pct,
    suggest_team_action,
    normalize_numeric_columns,
)
from views.newcomer._data import create_data_loaders

# ═══════════════════════════════════════════════════════════════
#  全局配置
# ═══════════════════════════════════════════════════════════════

# 设计系统 v3.0
from utils.design_system import ds, COLORS
ds.inject_theme()

repo = DashboardRepository()

# ═══════════════════════════════════════════════════════════════
#  SQL 辅助函数（与 repo 绑定，供数据加载层使用）
# ═══════════════════════════════════════════════════════════════

def batch_effective_start_expr(dim_alias: str = "n") -> str:
    return f"COALESCE({dim_alias}.effective_start_date, {dim_alias}.join_date)"


def _extract_short_names(aliases: list[str]) -> list[str]:
    short = set()
    for a in aliases:
        name = a.replace("云雀联营-", "") if "云雀联营-" in a else a
        short.add(name)
    return list(short)


def reviewer_name_in_condition(fact_alias: str, aliases: list[str], has_short_name: bool = True) -> tuple[str, list[str]]:
    short_names = _extract_short_names(aliases)
    all_names = list(set(aliases + short_names))
    placeholders = ", ".join(["%s"] * len(all_names))
    if has_short_name:
        short_placeholders = ", ".join(["%s"] * len(short_names))
        condition = (
            f"({fact_alias}.reviewer_name IN ({placeholders})"
            f" OR {fact_alias}.reviewer_short_name IN ({short_placeholders}))"
        )
        params = all_names + short_names
    else:
        condition = f"{fact_alias}.reviewer_name IN ({placeholders})"
        params = all_names
    return condition, params


def batch_effective_join_condition(fact_alias: str, dim_alias: str = "n", biz_date_field: str = "biz_date", has_short_name: bool = True) -> str:
    start_expr = batch_effective_start_expr(dim_alias)
    if has_short_name:
        name_cond = (
            f"({fact_alias}.reviewer_name = {dim_alias}.reviewer_alias "
            f"OR {fact_alias}.reviewer_short_name = {dim_alias}.reviewer_name "
            f"OR {fact_alias}.reviewer_name = {dim_alias}.reviewer_name)"
        )
    else:
        name_cond = (
            f"({fact_alias}.reviewer_name = {dim_alias}.reviewer_alias "
            f"OR {fact_alias}.reviewer_name = {dim_alias}.reviewer_name)"
        )
    return (
        f"{name_cond} "
        f"AND {fact_alias}.{biz_date_field} >= {start_expr} "
        f"AND ({dim_alias}.effective_end_date IS NULL OR {fact_alias}.{biz_date_field} <= {dim_alias}.effective_end_date)"
    )


@st.cache_resource(show_spinner=False)
def get_table_columns(table_name: str) -> set[str]:
    try:
        columns_df = repo.fetch_df(f"SHOW COLUMNS FROM {table_name}")
        return set(columns_df["Field"].tolist()) if columns_df is not None and not columns_df.empty else set()
    except Exception:
        return set()


# ═══════════════════════════════════════════════════════════════
#  Schema 兼容
# ═══════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def ensure_newcomer_schema() -> bool:
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
        if "reviewer_short_name" not in newcomer_columns:
            repo.execute("ALTER TABLE fact_newcomer_qa ADD COLUMN reviewer_short_name VARCHAR(128) COMMENT '审核人核心姓名（去掉前缀）' AFTER reviewer_name")
            repo.execute("""
                UPDATE fact_newcomer_qa
                SET reviewer_short_name = CASE
                    WHEN reviewer_name LIKE '云雀联营-%' THEN SUBSTRING(reviewer_name, 5)
                    ELSE reviewer_name
                END
                WHERE reviewer_short_name IS NULL OR reviewer_short_name = ''
            """)
        return True
    except Exception:
        return False


ensure_newcomer_schema()

# ═══════════════════════════════════════════════════════════════
#  数据计算辅助函数
# ═══════════════════════════════════════════════════════════════

# normalize_numeric_columns 已从 views.newcomer._shared 导入


def ensure_accuracy_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        df = pd.DataFrame()
    else:
        df = df.copy()
    numeric_columns = [
        "qa_cnt", "correct_cnt", "misjudge_cnt", "missjudge_cnt",
        "accuracy_rate", "sample_accuracy_rate", "reviewer_accuracy_rate",
        "sample_accuracy", "per_capita_accuracy", "accuracy", "accuracy_gap",
        "misjudge_rate", "missjudge_rate", "issue_rate",
        "best_team_acc", "best_team_per_capita_acc", "worst_team_acc", "worst_team_per_capita_acc",
        "sample_gap_pct", "per_capita_gap_pct", "gap_pct", "top_error_share",
        "关注分", "p0_cnt", "p1_cnt", "team_cnt", "member_cnt", "training_days",
    ]
    for column in numeric_columns:
        if column not in df.columns:
            df[column] = 0
    df = normalize_numeric_columns(df, numeric_columns)
    if df.empty:
        return df
    if "sample_accuracy_rate" not in df.columns:
        df["sample_accuracy_rate"] = df.get("accuracy_rate", df.apply(lambda r: safe_pct(r.get("correct_cnt"), r.get("qa_cnt")), axis=1))
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
    if source_df is None or source_df.empty:
        return pd.DataFrame()
    reviewer_group_cols = [*group_cols, "reviewer_name", "short_name"]
    if "team_name" in source_df.columns and "team_name" not in reviewer_group_cols:
        reviewer_group_cols.append("team_name")
    agg_spec: dict = {"qa_cnt": ("qa_cnt", "sum"), "correct_cnt": ("correct_cnt", "sum")}
    if "misjudge_cnt" in source_df.columns:
        agg_spec["misjudge_cnt"] = ("misjudge_cnt", "sum")
    if "missjudge_cnt" in source_df.columns:
        agg_spec["missjudge_cnt"] = ("missjudge_cnt", "sum")
    if extra_agg:
        agg_spec.update(extra_agg)
    reviewer_df = source_df.groupby(reviewer_group_cols, as_index=False).agg(**agg_spec)
    reviewer_df["reviewer_accuracy_rate"] = reviewer_df.apply(lambda r: safe_pct(r.get("correct_cnt"), r.get("qa_cnt")), axis=1)
    reviewer_df["member_key"] = reviewer_df["reviewer_name"].fillna(reviewer_df["short_name"])
    group_agg: dict = {
        "qa_cnt": ("qa_cnt", "sum"), "correct_cnt": ("correct_cnt", "sum"),
        "member_cnt": ("member_key", "nunique"), "per_capita_accuracy": ("reviewer_accuracy_rate", "mean"),
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
    for col in ["misjudge_rate", "missjudge_rate"]:
        if col not in result.columns:
            result[col] = 0.0
    result["issue_rate"] = (result["misjudge_rate"] + result["missjudge_rate"]).round(2)
    return result


# ═══════════════════════════════════════════════════════════════
#  初始化数据加载器
# ═══════════════════════════════════════════════════════════════

_loaders = create_data_loaders(repo, {
    "batch_effective_start_expr": batch_effective_start_expr,
    "batch_effective_join_condition": batch_effective_join_condition,
    "reviewer_name_in_condition": reviewer_name_in_condition,
    "_extract_short_names": _extract_short_names,
    "get_table_columns": get_table_columns,
})

# 用 st.cache_data 包裹每个加载器（数据加载层本身不加装饰器）
@st.cache_data(show_spinner="正在加载批次数据...", ttl=600)
def load_batch_list():
    return _loaders["load_batch_list"]()

@st.cache_data(show_spinner=False, ttl=600)
def load_newcomer_members(batch_names=None, owner=None, team_name=None):
    return _loaders["load_newcomer_members"](batch_names, owner, team_name)

@st.cache_data(show_spinner="正在加载质检数据...", ttl=600)
def load_newcomer_qa_daily(batch_names=None, reviewer_aliases=None, stage=None):
    return _loaders["load_newcomer_qa_daily"](batch_names, reviewer_aliases, stage)

@st.cache_data(show_spinner=False, ttl=600)
def load_formal_qa_daily(batch_names=None, reviewer_aliases=None):
    return _loaders["load_formal_qa_daily"](batch_names, reviewer_aliases)

@st.cache_data(show_spinner=False, ttl=600)
def load_newcomer_error_detail(reviewer_alias, limit=100):
    return _loaders["load_newcomer_error_detail"](reviewer_alias, limit)

@st.cache_data(show_spinner=False, ttl=600)
def load_person_all_qa_records(reviewer_alias, limit=200):
    return _loaders["load_person_all_qa_records"](reviewer_alias, limit)

@st.cache_data(show_spinner=False, ttl=600)
def load_newcomer_error_summary(batch_names=None, reviewer_aliases=None):
    return _loaders["load_newcomer_error_summary"](batch_names, reviewer_aliases)

@st.cache_data(show_spinner=False, ttl=600)
def load_formal_dimension_detail(batch_names=None, reviewer_aliases=None):
    return _loaders["load_formal_dimension_detail"](batch_names, reviewer_aliases)

@st.cache_data(show_spinner=False, ttl=600)
def load_newcomer_dimension_detail(batch_names=None, reviewer_aliases=None):
    return _loaders["load_newcomer_dimension_detail"](batch_names, reviewer_aliases)

@st.cache_data(show_spinner=False, ttl=600)
def load_unmatched_newcomer_rows():
    return _loaders["load_unmatched_newcomer_rows"]()

@st.cache_data(show_spinner="正在计算新人聚合指标...", ttl=600)
def load_newcomer_aggregate_payload(batch_names=None, owner=None, team_name=None):
    return build_newcomer_aggregate_payload(batch_names=batch_names, owner=owner, team_name=team_name)


# ═══════════════════════════════════════════════════════════════
#  Hero 区
# ═══════════════════════════════════════════════════════════════

batch_df = pd.DataFrame()
unmatched_df = pd.DataFrame()
try:
    batch_df = load_batch_list()
    unmatched_df = load_unmatched_newcomer_rows()
except Exception as _init_err:
    st.error(f"🚨 数据库连接异常：`{_init_err}`")
    if st.button("🔄 重试", key="retry_newcomer"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

if batch_df is None or batch_df.empty:
    ds.hero("👶", "新人追踪", "暂无新人数据，请先在「数据导入 → 新人映射」上传新人名单。")
    st.stop()

total_people = int(batch_df["total_cnt"].sum())
total_batches = len(batch_df)
all_teams: set[str] = set()
for t in batch_df["teams"].dropna():
    all_teams.update(t.split(","))

ds.hero(
    "👶", "新人追踪",
    f"共 {total_batches} 批次 · {total_people} 人 · {len(all_teams)} 个团队",
    badges=["🏫 内部质检", "🔍 外部质检", "✅ 正式上线", "自动关联「云雀联营-姓名」"],
)

# --- 未关联 / 借调练习提示 ---
practice_df = pd.DataFrame(columns=["reviewer_name", "stage", "is_practice_sample", "row_cnt", "start_date", "end_date"])
true_unmatched_df = pd.DataFrame(columns=["reviewer_name", "stage", "is_practice_sample", "row_cnt", "start_date", "end_date"])

if not unmatched_df.empty:
    practice_mask = unmatched_df.get("is_practice_sample", pd.Series(0, index=unmatched_df.index)).fillna(0).astype(int).eq(1)
    practice_mask = practice_mask | unmatched_df["reviewer_name"].apply(is_non_newcomer_practice_reviewer)
    practice_df = unmatched_df[practice_mask].copy()
    true_unmatched_df = unmatched_df[~practice_mask].copy()

    if not practice_df.empty:
        practice_count = int(practice_df["row_cnt"].sum())
        practice_names_list = practice_df["reviewer_name"].tolist()
        st.info(f"检测到 {practice_count} 条正式人力下线学习记录（共 {len(practice_names_list)} 人）。此类样例会写入 is_practice_sample=1，不计入新人批次统计，仅用于练习样例排查。")
        if len(practice_names_list) > 5:
            with st.expander(f"📋 查看 {len(practice_names_list)} 位正式人力名单", expanded=False):
                st.write("、".join(practice_names_list))
        else:
            st.caption("涉及：" + "、".join(practice_names_list))

    if not true_unmatched_df.empty:
        unmatched_count = int(true_unmatched_df["row_cnt"].sum())
        unmatched_names_list = true_unmatched_df["reviewer_name"].tolist()
        st.warning(f"当前仍有 {unmatched_count} 条新人质检记录未关联到批次（共 {len(unmatched_names_list)} 人）。建议补齐名单后再看批次汇总。")
        _unmatch_col1, _unmatch_col2 = st.columns([3, 1])
        with _unmatch_col1:
            if len(unmatched_names_list) > 5:
                with st.expander(f"📋 查看 {len(unmatched_names_list)} 位未关联人员名单", expanded=False):
                    _cols_per_row = 4
                    for i in range(0, len(unmatched_names_list), _cols_per_row):
                        _row_names = unmatched_names_list[i:i + _cols_per_row]
                        _exp_cols = st.columns(_cols_per_row)
                        for j, name in enumerate(_row_names):
                            with _exp_cols[j]:
                                st.write(name)
            else:
                st.caption("涉及：" + "、".join(unmatched_names_list))
        with _unmatch_col2:
            if st.button("🔗 自动关联到批次", key="auto_link_batch", use_container_width=True, type="primary",
                         help="根据 reviewer_name 匹配 dim_newcomer_batch 名单，自动回填 batch_name"):
                try:
                    link_sql = f"""
                        UPDATE fact_newcomer_qa q
                        JOIN dim_newcomer_batch n
                          ON {batch_effective_join_condition("q", "n")}
                        SET q.batch_name = n.batch_name
                        WHERE (q.batch_name IS NULL OR q.batch_name = '')
                    """
                    repo.execute(link_sql)
                    st.success("✅ 自动关联完成！请刷新页面查看结果。")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 自动关联失败：{e}")

# ═══════════════════════════════════════════════════════════════
#  模块切换 + 侧边栏筛选
# ═══════════════════════════════════════════════════════════════

view_options = {
    "📊 批次概览": "overview",
    "📈 成长曲线": "growth",
    "🔄 阶段对比": "compare",
    "👤 个人追踪": "person",
    "📊 维度分析": "dimension",
    "⚠️ 异常告警": "alert",
}

st.markdown("#### 📂 查看模块")
_tab_labels = list(view_options.keys())
_tab_cols = st.columns(len(_tab_labels))
if "nc_active_tab" not in st.session_state:
    st.session_state["nc_active_tab"] = _tab_labels[0]

for i, label in enumerate(_tab_labels):
    with _tab_cols[i]:
        is_active = st.session_state["nc_active_tab"] == label
        btn_type = "primary" if is_active else "secondary"
        if st.button(label, key=f"nc_tab_{i}", use_container_width=True, type=btn_type):
            st.session_state["nc_active_tab"] = label
            st.rerun()

active_view_label = st.session_state["nc_active_tab"]
active_view = view_options[active_view_label]
need_dimension_detail = active_view == "dimension"
need_alert_detail = active_view == "alert"

st.sidebar.markdown("### 🎯 新人追踪筛选")
selected_batches = st.sidebar.multiselect(
    "选择批次", options=batch_df["batch_name"].tolist(),
    default=batch_df["batch_name"].tolist(), key="nc_batch_filter",
)
owner_options = ["全部"] + sorted([o for o in batch_df["owners"].fillna("").str.split(",").explode().unique().tolist() if o])
owner_filter = st.sidebar.selectbox("质培owner 筛选", options=owner_options, key="nc_owner_filter")
stage_filter = st.sidebar.selectbox("阶段筛选", options=["全部", "内部质检", "外部质检", "正式上线"], key="nc_stage_filter")
team_options = ["全部"] + sorted(all_teams)
team_filter = st.sidebar.selectbox("基地/团队筛选", options=team_options, key="nc_team_filter")

# ═══════════════════════════════════════════════════════════════
#  数据加载与 ctx 组装
# ═══════════════════════════════════════════════════════════════

owner_value = None if owner_filter == "全部" else owner_filter
team_value = None if team_filter == "全部" else team_filter
members_df = load_newcomer_members(selected_batches if selected_batches else None, owner=owner_value, team_name=team_value)
if members_df is None:
    members_df = pd.DataFrame(columns=["batch_name", "reviewer_name", "reviewer_alias", "join_date", "effective_start_date", "effective_end_date", "team_name", "team_leader", "delivery_pm", "mentor_name", "owner", "status"])
else:
    members_df = members_df.copy()
    for col in ["team_name", "team_leader", "delivery_pm", "mentor_name", "owner"]:
        if col in members_df.columns:
            members_df[col] = members_df[col].fillna("未填写")

reviewer_aliases = members_df["reviewer_alias"].dropna().unique().tolist() if not members_df.empty else []

stage_map = {"内部质检": "internal", "外部质检": "external", "正式上线": "formal"}
stage_code = stage_map.get(stage_filter)
load_newcomer_stage = stage_code in (None, "internal", "external")
load_formal_stage = stage_code in (None, "formal")
newcomer_stage = stage_code if stage_code in {"internal", "external"} else None

# === 按需加载优化 ===
# overview 模块仅需聚合层数据，不需要加载全量质检明细
# 只有进入 growth/compare/person/dimension/alert 时才加载 combined_qa_df
need_combined_qa = active_view in ("growth", "compare", "person", "dimension", "alert")

if need_combined_qa and reviewer_aliases:
    newcomer_qa_df = load_newcomer_qa_daily(
        selected_batches if selected_batches else None, reviewer_aliases=reviewer_aliases, stage=newcomer_stage,
    ) if load_newcomer_stage else pd.DataFrame()
    formal_qa_df = load_formal_qa_daily(
        selected_batches if selected_batches else None, reviewer_aliases=reviewer_aliases,
    ) if load_formal_stage else pd.DataFrame()
else:
    newcomer_qa_df = pd.DataFrame()
    formal_qa_df = pd.DataFrame()

newcomer_qa_df = ensure_accuracy_columns(newcomer_qa_df)
formal_qa_df = ensure_accuracy_columns(formal_qa_df)
combined_qa_df = pd.concat(
    [df for df in [newcomer_qa_df, formal_qa_df] if df is not None and not df.empty], ignore_index=True,
) if (not newcomer_qa_df.empty or not formal_qa_df.empty) else pd.DataFrame()
combined_qa_df = ensure_accuracy_columns(combined_qa_df)

error_summary_df = load_newcomer_error_summary(
    selected_batches if selected_batches else None, reviewer_aliases=reviewer_aliases,
) if reviewer_aliases and need_alert_detail else pd.DataFrame()
formal_dimension_df = load_formal_dimension_detail(
    selected_batches if selected_batches else None, reviewer_aliases=reviewer_aliases,
) if reviewer_aliases and need_dimension_detail else pd.DataFrame()
newcomer_dimension_df = load_newcomer_dimension_detail(
    selected_batches if selected_batches else None, reviewer_aliases=reviewer_aliases,
) if reviewer_aliases and need_dimension_detail else pd.DataFrame()

# --- 维度可用性判断 ---
if need_dimension_detail:
    fact_newcomer_columns = get_table_columns("fact_newcomer_qa")
    fact_event_columns = get_table_columns("fact_qa_event")
    newcomer_dimension_ready = {"training_topic", "risk_level", "content_type"}.issubset(fact_newcomer_columns)
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
        {"维度": "培训专题达标率", "新人内/外检": "可用" if "training_topic" in fact_newcomer_columns else "缺失", "正式阶段": "可用" if "training_topic" in fact_event_columns else "缺失", "当前处理": dimension_current_status, "说明": "用于识别专项培训短板"},
        {"维度": "风险等级分布", "新人内/外检": "可用" if "risk_level" in fact_newcomer_columns else "缺失", "正式阶段": "可用" if "risk_level" in fact_event_columns else "缺失", "当前处理": dimension_current_status, "说明": "用于拆分高风险漏判和一般错判"},
        {"维度": "内容类型分布", "新人内/外检": "可用" if "content_type" in fact_newcomer_columns else "缺失", "正式阶段": "可用" if "content_type" in fact_event_columns else "缺失", "当前处理": dimension_current_status, "说明": "用于识别特定内容类型薄弱基地"},
        {"维度": "审核时效 / 人效", "新人内/外检": "可用" if "qa_time" in fact_newcomer_columns else "部分可用", "正式阶段": "缺失（当前汇总表无时效字段）", "当前处理": "待补稳定产能或耗时口径", "说明": "适合和正确率联动看赶量影响"},
    ])
else:
    fact_newcomer_columns = set()
    newcomer_dimension_ready = False
    dimension_status_df = pd.DataFrame(columns=["维度", "新人内/外检", "正式阶段", "当前处理", "说明"])

# --- 聚合层数据 ---
aggregate_payload = load_newcomer_aggregate_payload(
    selected_batches if selected_batches else None, owner=owner_value, team_name=team_value,
) if not members_df.empty else {}
aggregate_batch_scope_df = pd.DataFrame(aggregate_payload.get("batch_scope") or [])
if not aggregate_batch_scope_df.empty and "join_date" in aggregate_batch_scope_df.columns:
    aggregate_batch_scope_df = aggregate_batch_scope_df.copy()
    aggregate_batch_scope_df["join_date"] = pd.to_datetime(aggregate_batch_scope_df["join_date"], errors="coerce").dt.date

filtered_batch_df = aggregate_batch_scope_df if not aggregate_batch_scope_df.empty else members_df.groupby("batch_name", as_index=False).agg(
    join_date=("join_date", "min"), total_cnt=("reviewer_name", "count"),
    leader_names=("team_leader", lambda x: "、".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    delivery_pms=("delivery_pm", lambda x: "、".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    mentor_names=("mentor_name", lambda x: "、".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    teams=("team_name", lambda x: ",".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    owners=("owner", lambda x: ",".join(sorted({str(v) for v in x if pd.notna(v) and str(v).strip()}))),
    graduated_cnt=("status", lambda x: int((x == "graduated").sum())),
    training_cnt=("status", lambda x: int((~x.isin(["graduated", "exited"])).sum())),
) if not members_df.empty else pd.DataFrame(columns=batch_df.columns)

# --- 衍生计算 ---
if not members_df.empty:
    members_df = members_df.copy()
    members_df["join_date"] = pd.to_datetime(members_df["join_date"], errors="coerce").dt.date
if not combined_qa_df.empty:
    combined_qa_df = combined_qa_df.copy()
    combined_qa_df["biz_date"] = pd.to_datetime(combined_qa_df["biz_date"], errors="coerce").dt.date

# 初始化所有衍生 DataFrame
stage_summary_df = overall_stage_df = person_stage_df = pd.DataFrame()
stage_team_accuracy_df = team_accuracy_df = team_issue_df = pd.DataFrame()
management_perf_df = batch_compare_df = batch_gap_df = pd.DataFrame()
recent_person_perf_df = batch_watch_df = team_summary_df = team_alert_df = pd.DataFrame()

# 从聚合层加载（使用字典映射，避免 locals() 赋值的 CPython 陷阱）
_agg_mapping = {
    "stage_summary": "overall_stage_df",
    "batch_stage_summary": "stage_summary_df",
    "stage_team_accuracy": "stage_team_accuracy_df",
    "team_accuracy": "team_accuracy_df",
    "batch_compare": "batch_compare_df",
    "batch_gap": "batch_gap_df",
    "batch_watch": "batch_watch_df",
    "team_alert": "team_alert_df",
    "management_summary": "management_perf_df",
}
_agg_results = {}
for src_key, target_name in _agg_mapping.items():
    agg_df = ensure_accuracy_columns(pd.DataFrame(aggregate_payload.get(src_key) or []))
    if not agg_df.empty:
        _agg_results[target_name] = agg_df

# 从聚合结果中安全赋值
overall_stage_df = _agg_results.get("overall_stage_df", overall_stage_df)
stage_summary_df = _agg_results.get("stage_summary_df", stage_summary_df)
stage_team_accuracy_df = _agg_results.get("stage_team_accuracy_df", stage_team_accuracy_df)
team_accuracy_df = _agg_results.get("team_accuracy_df", team_accuracy_df)
team_issue_df = _agg_results.get("team_issue_df", team_issue_df)
batch_compare_df = _agg_results.get("batch_compare_df", batch_compare_df)
batch_gap_df = _agg_results.get("batch_gap_df", batch_gap_df)
batch_watch_df = _agg_results.get("batch_watch_df", batch_watch_df)
team_alert_df = _agg_results.get("team_alert_df", team_alert_df)
management_perf_df = _agg_results.get("management_perf_df", management_perf_df)

if not batch_compare_df.empty and "join_date" in batch_compare_df.columns:
    batch_compare_df = batch_compare_df.copy()
    batch_compare_df["join_date"] = pd.to_datetime(batch_compare_df["join_date"], errors="coerce").dt.date

if not team_accuracy_df.empty and team_issue_df.empty:
    team_issue_df = team_accuracy_df.copy()

# --- 从 combined_qa_df 补齐缺失的聚合 ---
if not combined_qa_df.empty:
    if overall_stage_df.empty:
        overall_stage_df = build_dual_accuracy_group(combined_qa_df, ["stage"])
    if stage_summary_df.empty:
        stage_summary_df = build_dual_accuracy_group(combined_qa_df, ["batch_name", "stage"])

    person_stage_df = combined_qa_df.groupby(["batch_name", "reviewer_name", "short_name", "team_name", "stage"], as_index=False).agg(
        qa_cnt=("qa_cnt", "sum"), correct_cnt=("correct_cnt", "sum"),
        misjudge_cnt=("misjudge_cnt", "sum"), missjudge_cnt=("missjudge_cnt", "sum"),
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
        batch_compare_df["training_days"] = batch_compare_df["join_date"].apply(lambda x: (date.today() - x).days if pd.notna(x) and x else 0)

    if batch_gap_df.empty and not team_accuracy_df.empty:
        gap_base = team_accuracy_df.groupby("batch_name", as_index=False).agg(
            team_cnt=("team_name", "nunique"),
            avg_team_sample_accuracy=("sample_accuracy", "mean"),
            avg_team_per_capita_accuracy=("per_capita_accuracy", "mean"),
        )
        best_rows = team_accuracy_df.loc[
            team_accuracy_df.groupby("batch_name")["sample_accuracy"].idxmax(),
            ["batch_name", "team_name", "sample_accuracy", "per_capita_accuracy", "issue_rate"],
        ].rename(columns={"team_name": "best_team_name", "sample_accuracy": "best_team_acc", "per_capita_accuracy": "best_team_per_capita_acc", "issue_rate": "best_team_issue_rate"})
        worst_rows = team_accuracy_df.loc[
            team_accuracy_df.groupby("batch_name")["sample_accuracy"].idxmin(),
            ["batch_name", "team_name", "sample_accuracy", "per_capita_accuracy", "issue_rate"],
        ].rename(columns={"team_name": "worst_team_name", "sample_accuracy": "worst_team_acc", "per_capita_accuracy": "worst_team_per_capita_acc", "issue_rate": "worst_team_issue_rate"})
        batch_gap_df = gap_base.merge(best_rows, on="batch_name", how="left").merge(worst_rows, on="batch_name", how="left")
        for col in ["best_team_acc", "worst_team_acc", "best_team_per_capita_acc", "worst_team_per_capita_acc"]:
            batch_gap_df[col] = pd.to_numeric(batch_gap_df[col], errors="coerce").fillna(0)
        batch_gap_df["sample_gap_pct"] = (batch_gap_df["best_team_acc"] - batch_gap_df["worst_team_acc"]).round(2)
        batch_gap_df["per_capita_gap_pct"] = (batch_gap_df["best_team_per_capita_acc"] - batch_gap_df["worst_team_per_capita_acc"]).round(2)
        batch_gap_df["gap_pct"] = batch_gap_df["sample_gap_pct"]

    team_summary_df = members_df.groupby(["batch_name", "team_name", "team_leader", "delivery_pm", "owner"], as_index=False).agg(
        人数=("reviewer_name", "count"), 培训中=("status", lambda x: (~x.isin(["graduated", "exited"])).sum()), 已转正=("status", lambda x: (x == "graduated").sum()),
    )
    team_summary_df = team_summary_df.merge(
        team_accuracy_df[["batch_name", "team_name", "qa_cnt", "sample_accuracy", "per_capita_accuracy", "accuracy_gap", "misjudge_rate", "missjudge_rate", "issue_rate"]],
        on=["batch_name", "team_name"], how="left",
    )

    if management_perf_df.empty:
        mgmt_person = combined_qa_df.merge(
            members_df[["reviewer_alias", "team_leader", "delivery_pm", "owner", "mentor_name"]].drop_duplicates(),
            left_on="reviewer_name", right_on="reviewer_alias", how="left",
        ).fillna({"team_leader": "未填写", "delivery_pm": "未填写", "owner": "未填写", "mentor_name": "未填写"})
        management_perf_df = build_dual_accuracy_group(mgmt_person, ["team_leader", "delivery_pm", "owner", "mentor_name"])
        management_perf_df = management_perf_df.fillna({"team_leader": "未填写", "delivery_pm": "未填写", "owner": "未填写", "mentor_name": "未填写"})

    # --- 近 7 天个人风险 ---
    recent_date = combined_qa_df["biz_date"].max()
    if recent_date:
        recent_cutoff = recent_date - timedelta(days=7)
        recent_meta_df = members_df[["reviewer_alias", "team_leader", "delivery_pm", "owner", "mentor_name"]].drop_duplicates()
        recent_qa_df = combined_qa_df[combined_qa_df["biz_date"] >= recent_cutoff].copy()
        recent_qa_df = recent_qa_df.merge(recent_meta_df, left_on="reviewer_name", right_on="reviewer_alias", how="left")
        recent_person_perf_df = recent_qa_df.groupby(
            ["reviewer_name", "short_name", "batch_name", "team_name", "team_leader", "delivery_pm", "owner", "mentor_name"],
            as_index=False,
        ).agg(qa_cnt=("qa_cnt", "sum"), correct_cnt=("correct_cnt", "sum"), misjudge_cnt=("misjudge_cnt", "sum"), missjudge_cnt=("missjudge_cnt", "sum"), latest_date=("biz_date", "max"))
        latest_stage_df = recent_qa_df.sort_values(["reviewer_name", "biz_date"]).groupby("reviewer_name", as_index=False).tail(1)[["reviewer_name", "stage"]].rename(columns={"stage": "latest_stage"})
        recent_person_perf_df = recent_person_perf_df.merge(latest_stage_df, on="reviewer_name", how="left")
        recent_person_perf_df["sample_accuracy"] = recent_person_perf_df.apply(lambda r: safe_pct(r["correct_cnt"], r["qa_cnt"]), axis=1)
        recent_person_perf_df["accuracy"] = recent_person_perf_df["sample_accuracy"]
        recent_person_perf_df["misjudge_rate"] = recent_person_perf_df.apply(lambda r: safe_pct(r["misjudge_cnt"], r["qa_cnt"]), axis=1)
        recent_person_perf_df["missjudge_rate"] = recent_person_perf_df.apply(lambda r: safe_pct(r["missjudge_cnt"], r["qa_cnt"]), axis=1)
        recent_person_perf_df["issue_rate"] = (recent_person_perf_df["misjudge_rate"] + recent_person_perf_df["missjudge_rate"]).round(2)
        recent_person_perf_df["risk_level"] = recent_person_perf_df.apply(
            lambda r: "P0" if (r["accuracy"] < 90 or r["missjudge_rate"] >= 2.0)
            else ("P1" if (r["accuracy"] < 95 or r["issue_rate"] >= 2.5)
            else ("NEAR" if (r["latest_stage"] == "external" and 97.5 <= r["accuracy"] < 98) else "OK")), axis=1,
        )

        if not recent_person_perf_df.empty:
            risk_focus_df = recent_person_perf_df[recent_person_perf_df["risk_level"].isin(["P0", "P1"])].copy()
            if not risk_focus_df.empty:
                risk_rank_map = {"P0": 0, "P1": 1}
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
                    batch_gap_df[["batch_name", "gap_pct", "sample_gap_pct", "per_capita_gap_pct",
                                  "best_team_name", "best_team_acc", "best_team_per_capita_acc",
                                  "worst_team_name", "worst_team_acc", "worst_team_per_capita_acc"]],
                    on="batch_name", how="left",
                ) if not batch_gap_df.empty else batch_compare_df.copy()
                if not batch_focus_df.empty:
                    batch_watch_df = batch_watch_df.merge(batch_focus_df, on="batch_name", how="left")
                for col, default in {"gap_pct": 0, "sample_gap_pct": 0, "per_capita_gap_pct": 0,
                                     "p0_cnt": 0, "p1_cnt": 0, "focus_people": "暂无",
                                     "best_team_name": "—", "worst_team_name": "—",
                                     "best_team_acc": 0, "best_team_per_capita_acc": 0,
                                     "worst_team_acc": 0, "worst_team_per_capita_acc": 0}.items():
                    if col not in batch_watch_df.columns:
                        batch_watch_df[col] = default
                    else:
                        batch_watch_df[col] = batch_watch_df[col].fillna(default)
                batch_watch_df[["risk_label", "risk_color", "risk_bg"]] = batch_watch_df.apply(
                    lambda r: pd.Series(classify_batch_risk(float(r["sample_accuracy"] or 0), float(r["sample_gap_pct"] or 0), int(r["p0_cnt"] or 0), int(r["p1_cnt"] or 0))), axis=1,
                )

    # --- 基地级告警 ---
    if team_alert_df.empty and not team_issue_df.empty:
        team_alert_df = team_issue_df.copy()
        if error_summary_df is not None and not error_summary_df.empty:
            team_error_focus = error_summary_df.groupby(["batch_name", "team_name", "error_type"], as_index=False)["error_cnt"].sum()
            team_error_total = team_error_focus.groupby(["batch_name", "team_name"], as_index=False)["error_cnt"].sum().rename(columns={"error_cnt": "team_error_cnt"})
            team_error_focus = team_error_focus.sort_values(["batch_name", "team_name", "error_cnt"], ascending=[True, True, False]).groupby(["batch_name", "team_name"], as_index=False).head(1)
            team_error_focus = team_error_focus.merge(team_error_total, on=["batch_name", "team_name"], how="left")
            team_error_focus["top_error_share"] = team_error_focus.apply(lambda r: safe_pct(r["error_cnt"], r["team_error_cnt"]), axis=1)
            team_error_focus = team_error_focus.rename(columns={"error_type": "top_error_type"})
            team_alert_df = team_alert_df.merge(team_error_focus[["batch_name", "team_name", "top_error_type", "top_error_share"]], on=["batch_name", "team_name"], how="left")
        if not batch_watch_df.empty:
            team_alert_df = team_alert_df.merge(batch_watch_df[["batch_name", "risk_label"]], on="batch_name", how="left")
        team_alert_df["top_error_type"] = team_alert_df.get("top_error_type", pd.Series("未标注", index=team_alert_df.index)).fillna("未标注")
        team_alert_df["top_error_share"] = pd.to_numeric(team_alert_df.get("top_error_share", 0), errors="coerce").fillna(0)
        team_alert_df["关注分"] = (100 - team_alert_df["sample_accuracy"]) + (team_alert_df["issue_rate"] * 2) + (team_alert_df["missjudge_rate"] * 1.5)
        team_alert_df["accuracy"] = team_alert_df["sample_accuracy"]
        team_alert_df["建议动作"] = team_alert_df.apply(suggest_team_action, axis=1)
        team_alert_df = team_alert_df.sort_values(["关注分", "sample_accuracy", "issue_rate"], ascending=[False, True, False])


# ═══════════════════════════════════════════════════════════════
#  组装 ctx 并分发到视图模块
# ═══════════════════════════════════════════════════════════════

ctx = {
    # 基础数据
    "batch_df": batch_df,
    "filtered_batch_df": filtered_batch_df,
    "members_df": members_df,
    "combined_qa_df": combined_qa_df,
    "practice_df": practice_df,
    "repo": repo,
    # 加载函数（个人追踪模块需要按需调用）
    "load_newcomer_error_detail": load_newcomer_error_detail,
    "load_person_all_qa_records": load_person_all_qa_records,
    # 聚合层
    "overall_stage_df": overall_stage_df,
    "stage_summary_df": stage_summary_df,
    "person_stage_df": person_stage_df,
    "batch_compare_df": batch_compare_df,
    "batch_gap_df": batch_gap_df,
    "batch_watch_df": batch_watch_df,
    "team_accuracy_df": team_accuracy_df,
    "stage_team_accuracy_df": stage_team_accuracy_df,
    "team_issue_df": team_issue_df,
    "team_summary_df": team_summary_df,
    "team_alert_df": team_alert_df,
    "management_perf_df": management_perf_df,
    "recent_person_perf_df": recent_person_perf_df,
    "error_summary_df": error_summary_df,
    # 维度
    "newcomer_dimension_df": newcomer_dimension_df,
    "formal_dimension_df": formal_dimension_df,
    "dimension_status_df": dimension_status_df,
    "newcomer_dimension_ready": newcomer_dimension_ready if need_dimension_detail else False,
}

st.caption(f"当前查看：{active_view_label}。页面已改成按模块渲染，避免一次刷新把 6 个重模块一起跑完。")

# ═══════════════════════════════════════════════════════════════
#  视图路由
# ═══════════════════════════════════════════════════════════════

VIEW_ROUTER = {
    "overview":  render_overview,
    "growth":    render_growth,
    "compare":   render_compare,
    "person":    render_person,
    "dimension": render_dimension,
    "alert":     render_alert,
}

VIEW_ROUTER[active_view](ctx)

# ═══════════════════════════════════════════════════════════════
#  数据导出区
# ═══════════════════════════════════════════════════════════════

ds.divider()
with st.expander("📥 数据导出", expanded=False):
    from utils.helpers import to_csv_bytes
    exp_c1, exp_c2, exp_c3 = st.columns(3)
    with exp_c1:
        if not members_df.empty:
            _member_csv = to_csv_bytes(members_df)
            st.download_button(
                "👥 导出新人名单",
                data=_member_csv,
                file_name=f"newcomer_members_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.button("👥 新人名单（无数据）", disabled=True, use_container_width=True)
    with exp_c2:
        if not combined_qa_df.empty:
            _qa_csv = to_csv_bytes(combined_qa_df)
            st.download_button(
                "📊 导出质检数据",
                data=_qa_csv,
                file_name=f"newcomer_qa_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.button("📊 质检数据（无数据）", disabled=True, use_container_width=True)
    with exp_c3:
        if not filtered_batch_df.empty:
            _batch_csv = to_csv_bytes(filtered_batch_df)
            st.download_button(
                "📋 导出批次概览",
                data=_batch_csv,
                file_name=f"newcomer_batch_overview_{date.today()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.button("📋 批次概览（无数据）", disabled=True, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
#  底部说明
# ═══════════════════════════════════════════════════════════════

ds.divider()
ds.footer([
    "<strong>💡 阶段识别规则：</strong>",
    "· 文件名含「10816」→ 外部质检",
    "· 文件队列含「新人评论测试」或文件名含「新人」→ 内部质检",
    "· 其他 → 正式上线（通过审核人名自动关联）",
    "· 正式队列借调到新人队列练习的人员，不计入新人批次统计",
    "· 聚合层统一同时展示「样本正确率 + 人均正确率」；个人追踪页只看单人样本正确率",
    f"<span style='color: {COLORS.text_muted}; font-size: 0.78rem;'>审核人映射：名单姓名 → 「云雀联营-」+ 姓名；批次归属按 reviewer_alias + biz_date + 生效区间判断</span>",
])
