"""看板全局常量定义。

集中管理颜色、阈值等跨页面共享常量，
避免各页面硬编码散落。
"""
from __future__ import annotations

from datetime import date

# ==================== 告警颜色 ====================
COLOR_P0 = "#DC2626"  # 红色 - 严重告警
COLOR_P1 = "#F59E0B"  # 橙色 - 重要告警
COLOR_P2 = "#3B82F6"  # 蓝色 - 一般告警

# ==================== 状态颜色 ====================
COLOR_SUCCESS = "#10B981"  # 绿色 - 正常/成功
COLOR_GOOD = "#10B981"     # 绿色 - 良好
COLOR_BAD = "#EF4444"      # 红色 - 异常/差
COLOR_WARN = "#F59E0B"     # 橙色 - 警告

# ==================== 正确率阈值（%）====================
# 所有页面的红/黄/绿判定统一走这里
ACC_EXCELLENT = 99.0   # >= 99% 绿（优秀）
ACC_WARNING = 98.0     # 97~99% 黄（注意）
ACC_CRITICAL = 97.0    # < 97% 红（告警）

# ==================== 模块目标线（%）====================
# 外检（供应商审核员）和内检（内部团队）目标不同，不能混用一个 99%
ACC_TARGET_EXTERNAL = 99.0   # 外检目标
ACC_TARGET_INTERNAL = 99.5   # 内检目标（内部团队标准更严）

# ==================== 模块色系 ====================
# 外检 = 绿、内检 = 紫（与现有趋势图/卡片保持一致）
COLOR_EXTERNAL = "#10B981"
COLOR_INTERNAL = "#8B5CF6"

# 小样本门槛（低于此值不做对比/不进入问题名单）
MIN_SAMPLE_EXT = 50    # 外检审核人样本门槛
MIN_SAMPLE_INT = 30    # 内检审核人样本门槛
MIN_SAMPLE_BASELINE = 10  # 画像卡同期基线最小样本


def acc_color(acc: float | None) -> str:
    """根据正确率返回对应颜色。None 视为最差。"""
    if acc is None:
        return COLOR_BAD
    if acc >= ACC_EXCELLENT:
        return COLOR_GOOD
    if acc >= ACC_CRITICAL:
        return COLOR_WARN
    return COLOR_BAD


def acc_level(acc: float | None) -> str:
    """返回等级文字 excellent / warning / critical / unknown。"""
    if acc is None:
        return "unknown"
    if acc >= ACC_EXCELLENT:
        return "excellent"
    if acc >= ACC_CRITICAL:
        return "warning"
    return "critical"


# ==================== 数据保留策略 ====================
RETENTION_DAYS = 45  # 数据裁剪保留天数

# ==================== 缓存 TTL 策略 ====================
# 今天的数据可能还会增长 → 5 分钟；历史日期不会变 → 24 小时
TTL_TODAY = 300         # 5 min
TTL_HISTORY = 86400     # 24 h
TTL_LIGHT = 180         # 轻量实时数据


def cache_ttl(biz_date: date) -> int:
    """根据业务日期返回合适的缓存 TTL。历史日期的数据不会变，缓存久一点。"""
    try:
        if biz_date < date.today():
            return TTL_HISTORY
    except Exception:
        pass
    return TTL_TODAY
