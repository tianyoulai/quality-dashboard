"""看板共享工具函数。

集中管理跨页面重复的纯逻辑工具（CSV 导出、日期处理、数据序列化等），
避免各页面各自定义相同函数。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


# ── DataFrame → 序列化 ─────────────────────────────────────


def normalize_scalar(value: Any) -> Any:
    """将 numpy/pandas 特殊类型转为 Python 原生类型。"""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, pd.Timedelta):
        return str(value)
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """将 DataFrame 转为 JSON 安全的 dict 列表。"""
    if df is None or df.empty:
        return []
    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        records.append({key: normalize_scalar(value) for key, value in row.items()})
    return records


def normalize_payload(payload: Any) -> Any:
    """递归将 payload 中的 numpy/pandas 类型转为 JSON 安全类型。"""
    if isinstance(payload, pd.DataFrame):
        return dataframe_to_records(payload)
    if isinstance(payload, dict):
        return {key: normalize_payload(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [normalize_payload(item) for item in payload]
    return normalize_scalar(payload)


# ── CSV 导出 ────────────────────────────────────────────────


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """将 DataFrame 转为 UTF-8 BOM CSV 的字节数据，供 st.download_button 使用。

    自动将 datetime 列转为字符串避免序列化问题。
    """
    export_df = df.copy()
    for column in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[column]):
            export_df[column] = export_df[column].astype(str)
    return export_df.to_csv(index=False).encode("utf-8-sig")


# ── 安全百分比计算 ─────────────────────────────────────────


def safe_pct(numerator: Any, denominator: Any) -> float:
    """安全计算百分比，分母为0时返回0.0。"""
    den = float(denominator or 0)
    return round(float(numerator or 0) * 100.0 / den, 2) if den > 0 else 0.0
