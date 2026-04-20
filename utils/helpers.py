"""看板共享工具函数。

集中管理跨页面重复的纯逻辑工具（CSV 导出、日期处理等），
避免各页面各自定义相同函数。
"""
from __future__ import annotations

from io import BytesIO

import pandas as pd


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """将 DataFrame 转为 UTF-8 BOM CSV 的字节数据，供 st.download_button 使用。

    自动将 datetime 列转为字符串避免序列化问题。
    """
    export_df = df.copy()
    for column in export_df.columns:
        if pd.api.types.is_datetime64_any_dtype(export_df[column]):
            export_df[column] = export_df[column].astype(str)
    return export_df.to_csv(index=False).encode("utf-8-sig")
