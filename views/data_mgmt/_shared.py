"""数据管理页 - 共享工具函数和常量。"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from storage.repository import DashboardRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
repo = DashboardRepository()


def preview_file_rows(file_obj, file_type: str) -> dict:
    """预览文件数据量（只读一次，避免大文件性能问题）。"""
    try:
        if file_type == "qa":
            full_df = pd.read_excel(file_obj, dtype=str)
            file_obj.seek(0)
        else:
            try:
                full_df = pd.read_csv(file_obj, encoding="utf-8-sig", dtype=str)
            except UnicodeDecodeError:
                file_obj.seek(0)
                full_df = pd.read_csv(file_obj, encoding="gb18030", dtype=str)
            file_obj.seek(0)
        return {
            "rows": len(full_df),
            "columns": len(full_df.columns),
            "preview_df": full_df.head(5),
            "error": None,
        }
    except Exception as e:
        return {"rows": 0, "columns": 0, "preview_df": None, "error": str(e)}


def get_upload_history(limit: int = 20) -> list[dict]:
    """获取最近的上传记录。"""
    try:
        result = repo.fetch_df(
            """
            SELECT upload_id, upload_time, file_name, file_type,
                   file_size_bytes, source_rows, inserted_rows,
                   dedup_rows, business_line, upload_status, error_message
            FROM fact_upload_log ORDER BY upload_time DESC LIMIT %s
            """,
            [limit],
        )
        return result.to_dict(orient="records") if result is not None and not result.empty else []
    except Exception:
        return []


def check_file_exists(file_hash: str) -> dict | None:
    """检查文件是否已存在（用于前端提示）。"""
    try:
        result = repo.fetch_one(
            "SELECT file_name, first_upload_time, upload_count FROM fact_file_dedup WHERE file_hash = %s",
            [file_hash],
        )
        return result if result else None
    except Exception:
        return None


def compute_file_hash_from_bytes(data: bytes) -> str:
    """计算文件内容哈希（适用于小文件）。"""
    return hashlib.sha256(data).hexdigest()


def compute_file_hash_chunked(file_obj, chunk_size: int = 8192) -> str:
    """分块计算文件哈希，避免大文件内存溢出。"""
    hasher = hashlib.sha256()
    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        hasher.update(chunk)
    file_obj.seek(0)
    return hasher.hexdigest()
