"""审计日志工具 -- 记录关键操作，便于追溯。

用法:
    from utils.audit import log_action
    log_action("upload", "fact_qa_event", "上传质检Excel 1200行", operator="张三")
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.logger import get_logger

_log = get_logger(__name__)


def log_action(
    action: str,
    target: str = "",
    detail: str = "",
    operator: str = "system",
) -> None:
    """写入一条审计日志。静默失败，不影响主流程。"""
    try:
        from storage.repository import DashboardRepository
        repo = DashboardRepository()
        repo.execute(
            """INSERT INTO sys_audit_log (action, target, detail, operator)
               VALUES (%s, %s, %s, %s)""",
            [action[:64], target[:128], detail[:2000], operator[:64]],
        )
    except Exception as e:
        # 审计失败不阻塞主流程
        _log.warning("audit log failed: %s", e)
