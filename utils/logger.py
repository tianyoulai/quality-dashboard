"""轻量日志：给看板排障用。

特性：
- 统一 INFO/WARNING/ERROR 级别格式（时间 / 模块 / 消息）
- 仅落本地文件 ``logs/dashboard.log``，不写控制台（避免污染 Streamlit 输出）
- 按天切分 + 保留 14 天

用法::

    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("load_overview hit", extra={"date": "2026-04-18"})

"""
from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(os.getenv("DASHBOARD_LOG_DIR", "logs"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "dashboard.log"

_FMT = "%(asctime)s | %(levelname)-7s | %(name)-24s | %(message)s"

_configured: set[str] = set()


def get_logger(name: str = "dashboard", level: int = logging.INFO) -> logging.Logger:
    """取得已配置好的 logger。首次取用会挂 TimedRotatingFileHandler。"""
    logger = logging.getLogger(name)
    if name in _configured:
        return logger

    logger.setLevel(level)
    # 避免和 Streamlit 内部 root logger 重复打印
    logger.propagate = False

    handler = TimedRotatingFileHandler(
        _LOG_FILE, when="midnight", backupCount=14, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_FMT))
    logger.addHandler(handler)

    _configured.add(name)
    return logger
