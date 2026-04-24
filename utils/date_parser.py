"""日期解析工具。

从质检文件名中提取业务日期。
统一了 daily_refresh / import_fact_data / import_newcomer_qa 三处的解析逻辑。

支持格式：
- 2026-04-21 / 2026.04.21 / 20260421 （完整带年份）
- 4.21 / 04.21 / 4/21 （无年份，自动推断）
- 4月21日 （中文格式）
- 0421 （MMDD 格式，自动推断年份）
"""
from __future__ import annotations

import re
from datetime import date


def _infer_year(month: int, day: int, reference_year: int | None = None) -> int:
    """推断合理的年份，避免未来日期。

    尝试今年 → 去年 → 前年，取第一个不超过今天的。
    """
    today = date.today()
    current_year = reference_year or today.year

    for year_offset in range(3):
        candidate_year = current_year - year_offset
        try:
            candidate_date = date(candidate_year, month, day)
            if candidate_date <= today:
                return candidate_year
        except ValueError:
            continue
    return current_year - 1  # 默认去年


def extract_date_from_filename(filename: str, reference_year: int | None = None) -> date | None:
    """从文件名中提取业务日期。

    支持多种格式：
    - 2026.3.6长沙云雀... → 2026-03-06
    - 2026-04-08_xxx → 2026-04-08
    - 20260421 → 2026-04-21
    - 0322迁移人力... → 推断年份-03-22
    - 3.20迁移人力... → 推断年份-03-20
    - 4月21日 → 推断年份-04-21

    年份推断逻辑（无年份时）：
    - 优先使用今年，如果该日期 > 今天则回退去年
    - 最多回溯 2 年

    Args:
        filename: 文件名
        reference_year: 参考年份（用于测试/回退），默认当前年份

    Returns:
        date | None: 提取成功返回日期，否则返回 None
    """
    if reference_year is None:
        reference_year = date.today().year

    name = filename.strip()

    # 1. 完整日期: YYYY.M.D / YYYY-MM-DD / YYYY/MM/DD
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", name)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # 2. 紧凑格式: YYYYMMDD
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", name)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # 3. 中文格式: 4月21日
    m = re.search(r"(\d{1,2})月(\d{1,2})日?", name)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                year = _infer_year(month, day, reference_year)
                return date(year, month, day)
            except ValueError:
                pass

    # 4. MMDD 紧凑格式: 0322
    m = re.search(r"(?:^|[^\d])(\d{2})(\d{2})(?:[^\d]|$)", name)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                year = _infer_year(month, day, reference_year)
                return date(year, month, day)
            except ValueError:
                pass

    # 5. 点分/斜线分: M.D / MM.DD / M/D
    m = re.search(r"(?:^|[^\d])(\d{1,2})[./](\d{1,2})(?:[^\d./]|$)", name)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                year = _infer_year(month, day, reference_year)
                return date(year, month, day)
            except ValueError:
                pass

    return None
