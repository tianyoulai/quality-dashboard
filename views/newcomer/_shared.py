"""新人追踪 — 共享工具函数与常量。

所有视图模块共用的工具函数集中在这里，避免各模块重复定义。
主页面 (04_新人追踪.py) 同样从此模块导入。
"""
from __future__ import annotations

from typing import Any

import pandas as pd

# safe_pct 统一使用 utils/helpers.py 中的版本（消除重复定义）
from utils.helpers import safe_pct  # noqa: F401 — re-exported for downstream modules
from utils.design_system import COLORS


# ═══════════════════════════════════════════════════════════════
#  阶段元数据
# ═══════════════════════════════════════════════════════════════

STAGE_META = {
    "internal": ("🏫 内部质检", COLORS.stage_internal, COLORS.stage_internal_light, 33),
    "external": ("🔍 外部质检", COLORS.stage_external, COLORS.stage_external_light, 66),
    "formal":   ("✅ 正式上线", COLORS.stage_formal,   COLORS.stage_formal_light,   100),
}

# 新人生命周期 6 态（对应 dim_newcomer_batch.status）
STATUS_META = {
    "pending":           ("⏳ 待开始",    COLORS.stage_pending,  COLORS.stage_pending_light),
    "internal_training": ("🏫 内检培训中", COLORS.stage_internal, COLORS.stage_internal_light),
    "external_training": ("🔍 外检培训中", COLORS.stage_external, COLORS.stage_external_light),
    "formal_probation":  ("✅ 正式队列",  COLORS.warning,        COLORS.warning_light),
    "graduated":         ("🎓 已毕业",    COLORS.stage_formal,   COLORS.stage_formal_light),
    "exited":            ("🚪 已退出",    COLORS.stage_exited,   COLORS.stage_exited_light),
    "training":          ("📚 培训中",    COLORS.stage_internal, COLORS.stage_internal_light),  # 兼容旧值
}

STAGE_LABEL_MAP = {
    "internal": "🏫 内部质检",
    "external": "🔍 外部质检",
    "formal":   "✅ 正式上线",
}

STAGE_SHORT_MAP = {
    "internal": "🏫 内检",
    "external": "🔍 外检",
    "formal":   "✅ 正式上线",
}

# 正式队列人员：偶尔会被下线到新人队列练习，不计入新人批次
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


# ═══════════════════════════════════════════════════════════════
#  通用工具函数
# ═══════════════════════════════════════════════════════════════

def display_text(value: Any, default: str = "未填写") -> str:
    """安全地将值转为展示文本，空值返回默认值。"""
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def get_stage_meta(stage_code: str) -> tuple[str, str, str, int]:
    """返回 (标签, 颜色, 背景色, 进度百分比)。"""
    return STAGE_META.get(stage_code, ("待开始", "#94a3b8", "#f8fafc", 0))


def normalize_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """将 Decimal / 字符串数值统一转成可计算的数值类型。"""
    if df is None or df.empty:
        return df
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def format_heatmap_text(matrix_df: pd.DataFrame) -> pd.DataFrame:
    """将热力图矩阵转为百分比展示文本。"""
    if matrix_df is None or matrix_df.empty:
        return matrix_df if matrix_df is not None else pd.DataFrame()
    return matrix_df.apply(
        lambda col: col.map(lambda v: f"{v:.1f}%" if pd.notna(v) and v > 0 else "—")
    )


def ensure_default_columns(df: pd.DataFrame | None, defaults: dict[str, object]) -> pd.DataFrame:
    """确保 DataFrame 包含所有指定列，缺失时用默认值填充。"""
    if df is None:
        df = pd.DataFrame()
    else:
        df = df.copy()
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
        else:
            if isinstance(default, (int, float)):
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default)
            else:
                df[col] = df[col].fillna(default)
    return df


def format_name_list(values: Any, limit: int = 3, default: str = "暂无") -> str:
    """将人名列表格式化为 "A、B、C 等N人" 形式。"""
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


def classify_batch_risk(
    overall_acc: float,
    gap_pct: float,
    p0_cnt: int = 0,
    p1_cnt: int = 0,
) -> tuple[str, str, str]:
    """分类批次风险等级，返回 (标签, 颜色, 背景色)。"""
    if overall_acc < 95 or gap_pct >= 4 or p0_cnt > 0:
        return ("🔴 风险批次", "#dc2626", "#fef2f2")
    if overall_acc < 97 or gap_pct >= 2.5 or p1_cnt > 0:
        return ("🟡 关注批次", "#d97706", "#fffbeb")
    return ("🟢 稳定批次", "#059669", "#ecfdf5")


def suggest_team_action(row: pd.Series) -> str:
    """根据基地数据生成建议动作文本。"""
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
        return f'围绕"{top_error_type}"做专项复盘。'
    if accuracy < 97 or issue_rate >= 2.5:
        return "安排一对一带教，连续跟进近三天样本。"
    return "当前稳定，保持抽检观察。"


def normalize_reviewer_name(name: object) -> str:
    """提取核心姓名（去掉「云雀联营-」「评论-」前缀）。"""
    text = str(name or "").strip()
    if not text:
        return ""
    text = text.removeprefix("云雀联营-")
    text = text.removeprefix("评论-")
    return text.strip()


def is_non_newcomer_practice_reviewer(name: object) -> bool:
    """判断是否为正式人力下线学习的审核人。"""
    text = str(name or "").strip()
    return text in NON_NEWCOMER_PRACTICE_REVIEWERS or normalize_reviewer_name(text) in PRACTICE_SHORT_NAMES


def render_plot(fig: Any, key: str) -> None:
    """统一给 Plotly 图表传唯一 key，避免 Streamlit 重复元素报错。"""
    import streamlit as st
    st.plotly_chart(fig, use_container_width=True, key=key)
