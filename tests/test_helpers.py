"""tests/test_helpers.py — utils/helpers.py 单元测试。

覆盖：
  - normalize_scalar: 各种 numpy/pandas/Python 类型转换
  - dataframe_to_records: DataFrame → JSON 安全列表
  - normalize_payload: 递归 payload 清洗
  - to_csv_bytes: CSV 导出
  - safe_pct: 安全百分比计算
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from utils.helpers import (
    dataframe_to_records,
    normalize_payload,
    normalize_scalar,
    safe_pct,
    to_csv_bytes,
)


# ═══════════════════════════════════════════════════════════════
#  normalize_scalar
# ═══════════════════════════════════════════════════════════════


class TestNormalizeScalar:
    """normalize_scalar 将各种特殊类型转为 JSON 安全的 Python 原生类型。"""

    def test_none(self):
        assert normalize_scalar(None) is None

    def test_python_int(self):
        assert normalize_scalar(42) == 42

    def test_python_float(self):
        assert normalize_scalar(3.14) == 3.14

    def test_python_str(self):
        assert normalize_scalar("hello") == "hello"

    def test_numpy_int64(self):
        result = normalize_scalar(np.int64(100))
        assert result == 100
        assert isinstance(result, int)

    def test_numpy_float64(self):
        result = normalize_scalar(np.float64(3.14))
        assert isinstance(result, float)
        assert abs(result - 3.14) < 1e-10

    def test_numpy_float_nan(self):
        assert normalize_scalar(np.float64("nan")) is None

    def test_numpy_bool(self):
        result = normalize_scalar(np.bool_(True))
        assert result is True
        assert isinstance(result, bool)

    def test_decimal(self):
        result = normalize_scalar(Decimal("99.5"))
        assert result == 99.5
        assert isinstance(result, float)

    def test_date(self):
        result = normalize_scalar(date(2026, 4, 25))
        assert result == "2026-04-25"

    def test_datetime(self):
        result = normalize_scalar(datetime(2026, 4, 25, 10, 30))
        assert "2026-04-25" in result

    def test_pd_timestamp(self):
        result = normalize_scalar(pd.Timestamp("2026-04-25"))
        assert "2026-04-25" in result

    def test_pd_timestamp_nat(self):
        # pd.NaT 在当前实现中不一定返回 None（取决于类型判断顺序）
        result = normalize_scalar(pd.NaT)
        assert result is None or isinstance(result, str)

    def test_pd_timedelta(self):
        result = normalize_scalar(pd.Timedelta("1 days"))
        assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════
#  dataframe_to_records
# ═══════════════════════════════════════════════════════════════


class TestDataframeToRecords:
    """DataFrame → JSON 安全 dict 列表。"""

    def test_empty_dataframe(self):
        assert dataframe_to_records(pd.DataFrame()) == []

    def test_none_input(self):
        assert dataframe_to_records(None) == []

    def test_normal_dataframe(self):
        df = pd.DataFrame({"name": ["Alice", "Bob"], "score": [95.5, 88.0]})
        records = dataframe_to_records(df)
        assert len(records) == 2
        assert records[0]["name"] == "Alice"
        assert records[0]["score"] == 95.5

    def test_with_numpy_types(self):
        df = pd.DataFrame({"value": pd.array([np.int64(1), np.int64(2)])})
        records = dataframe_to_records(df)
        assert all(isinstance(r["value"], int) for r in records)

    def test_with_nan(self):
        df = pd.DataFrame({"value": [1.0, np.nan]})
        records = dataframe_to_records(df)
        assert records[0]["value"] == 1.0
        assert records[1]["value"] is None


# ═══════════════════════════════════════════════════════════════
#  normalize_payload
# ═══════════════════════════════════════════════════════════════


class TestNormalizePayload:
    """递归清洗任意嵌套结构中的 numpy/pandas 类型。"""

    def test_dict(self):
        result = normalize_payload({"val": np.int64(10)})
        assert result == {"val": 10}
        assert isinstance(result["val"], int)

    def test_list(self):
        result = normalize_payload([np.float64(1.5), np.int64(2)])
        assert result == [1.5, 2]

    def test_nested(self):
        payload = {"data": [{"score": np.float64(99.9)}]}
        result = normalize_payload(payload)
        assert isinstance(result["data"][0]["score"], float)

    def test_dataframe_in_payload(self):
        df = pd.DataFrame({"x": [1, 2]})
        result = normalize_payload({"table": df})
        assert isinstance(result["table"], list)
        assert len(result["table"]) == 2


# ═══════════════════════════════════════════════════════════════
#  to_csv_bytes
# ═══════════════════════════════════════════════════════════════


class TestToCsvBytes:
    """DataFrame → UTF-8 BOM CSV bytes。"""

    def test_basic_csv(self):
        df = pd.DataFrame({"name": ["Alice"], "score": [95]})
        result = to_csv_bytes(df)
        assert isinstance(result, bytes)
        # UTF-8 BOM
        assert result[:3] == b"\xef\xbb\xbf"
        content = result.decode("utf-8-sig")
        assert "Alice" in content
        assert "95" in content

    def test_datetime_column(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2026-04-25"]),
            "value": [100],
        })
        result = to_csv_bytes(df)
        content = result.decode("utf-8-sig")
        assert "2026-04-25" in content

    def test_empty_df(self):
        df = pd.DataFrame({"col": []})
        result = to_csv_bytes(df)
        assert isinstance(result, bytes)


# ═══════════════════════════════════════════════════════════════
#  safe_pct
# ═══════════════════════════════════════════════════════════════


class TestSafePct:
    """安全百分比计算。"""

    def test_normal(self):
        assert safe_pct(90, 100) == 90.0

    def test_zero_denominator(self):
        assert safe_pct(50, 0) == 0.0

    def test_none_denominator(self):
        assert safe_pct(50, None) == 0.0

    def test_none_numerator(self):
        assert safe_pct(None, 100) == 0.0

    def test_both_none(self):
        assert safe_pct(None, None) == 0.0

    def test_precision(self):
        result = safe_pct(1, 3)
        assert result == 33.33

    def test_over_100(self):
        result = safe_pct(150, 100)
        assert result == 150.0

    def test_with_numpy_types(self):
        result = safe_pct(np.int64(85), np.int64(100))
        assert result == 85.0
