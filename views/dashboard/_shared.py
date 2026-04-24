"""总览页 - 共享常量与工具函数。"""
from __future__ import annotations

from datetime import date

from utils.helpers import to_csv_bytes  # noqa: F401 — re-export

# ── 粒度 ────────────────────
GRAIN_LABELS = {
    "day": "日监控",
    "week": "周复盘",
    "month": "月管理",
}

ALERT_STATUS_OPTIONS = ["open", "claimed", "ignored", "resolved"]

# ── 颜色 ────────────────────
COLOR_P0 = "#DC2626"
COLOR_P1 = "#F59E0B"
COLOR_P2 = "#3B82F6"
COLOR_SUCCESS = "#10B981"
COLOR_GOOD = "#10B981"
COLOR_BAD = "#EF4444"
COLOR_WARN = "#F59E0B"


def calc_change(current_rate: float, prev_rate: float | None) -> str:
    """计算环比变化HTML片段。"""
    if prev_rate is None:
        return ""
    diff = current_rate - prev_rate
    if abs(diff) < 0.01:
        return "<span style='color:#94A3B8;'>持平</span>"
    if diff > 0:
        return f"<span style='color:#10B981;'>▲ +{diff:.2f}%</span>"
    return f"<span style='color:#EF4444;'>▼ {diff:.2f}%</span>"


def safe_file_part(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    for old in ["/", "\\", " ", "|", ":"]:
        text = text.replace(old, "-")
    return text


def build_export_file_name(
    prefix: str,
    grain: str,
    anchor_date: date,
    group_name: str | None = None,
    queue_name: str | None = None,
    rule_code: str | None = None,
    reviewer_name: str | None = None,
    error_type: str | None = None,
) -> str:
    parts = [prefix, grain, str(anchor_date)]
    for value in [rule_code, group_name, queue_name, reviewer_name, error_type]:
        safe_value = safe_file_part(value)
        if safe_value:
            parts.append(safe_value)
    return "_".join(parts) + ".csv"
