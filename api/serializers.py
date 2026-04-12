from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd


def normalize_scalar(value: Any) -> Any:
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
    if df is None or df.empty:
        return []

    records: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        records.append({key: normalize_scalar(value) for key, value in row.items()})
    return records


def normalize_payload(payload: Any) -> Any:
    if isinstance(payload, pd.DataFrame):
        return dataframe_to_records(payload)
    if isinstance(payload, dict):
        return {key: normalize_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [normalize_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return [normalize_payload(item) for item in payload]
    return normalize_scalar(payload)
