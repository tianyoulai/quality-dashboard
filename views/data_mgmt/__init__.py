"""数据管理页 - 拆分子模块统一导出。"""
from views.data_mgmt._shared import (
    preview_file_rows,
    get_upload_history,
    check_file_exists,
    compute_file_hash_from_bytes,
    compute_file_hash_chunked,
    PROJECT_ROOT,
    repo,
)
from views.data_mgmt.freshness import render_freshness_panel
from views.data_mgmt.health_check import render_health_check
from views.data_mgmt.newcomer_batch import render_newcomer_batch_tab
from views.data_mgmt.newcomer_status import render_newcomer_status_tab

__all__ = [
    "preview_file_rows",
    "get_upload_history",
    "check_file_exists",
    "compute_file_hash_from_bytes",
    "compute_file_hash_chunked",
    "PROJECT_ROOT",
    "repo",
    "render_freshness_panel",
    "render_health_check",
    "render_newcomer_batch_tab",
    "render_newcomer_status_tab",
]
