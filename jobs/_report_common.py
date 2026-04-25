"""报告任务公共工具。

抽取 daily_report / weekly_report / newcomer_daily_report 三个入口脚本
的共享逻辑：
- 去重缓存（sent 文件读写）
- 配置加载
- 错误推送
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# 不同报告类型对应不同的去重缓存文件
_SENT_FILES = {
    "daily": CACHE_DIR / "report_sent.txt",
    "weekly": CACHE_DIR / "weekly_report_sent.txt",
    "newcomer": CACHE_DIR / "newcomer_report_sent.txt",
}


def load_sent(report_type: str) -> set[str]:
    """读取已发送记录。"""
    sent_file = _SENT_FILES.get(report_type, CACHE_DIR / f"{report_type}_sent.txt")
    if sent_file.exists():
        return {l.strip() for l in sent_file.read_text("utf-8").splitlines() if l.strip()}
    return set()


def mark_sent(report_type: str, key: str | date) -> None:
    """标记已发送。"""
    sent_file = _SENT_FILES.get(report_type, CACHE_DIR / f"{report_type}_sent.txt")
    s = load_sent(report_type)
    s.add(str(key))
    sent_file.write_text("\n".join(sorted(s)), encoding="utf-8")


def load_settings() -> dict:
    """加载 config/settings.json 配置。"""
    settings_path = PROJECT_ROOT / "config" / "settings.json"
    if settings_path.exists():
        return json.loads(settings_path.read_text("utf-8"))
    return {}


def push_error_notification(report_name: str, label: str, error: Exception) -> None:
    """推送错误通知到企微。"""
    try:
        from services.wecom_push import send_wecom_webhook
        send_wecom_webhook(f"⚠️ {report_name}生成失败 | {label}\n\n错误：{error}")
    except Exception:
        pass


def save_deliverable(content: str, filename: str, subdir: str = "deliverables") -> Path:
    """保存报告产出物到 deliverables 目录。"""
    out_dir = PROJECT_ROOT / subdir
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path
