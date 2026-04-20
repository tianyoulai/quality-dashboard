"""API 响应缓存管理器 —— 基于 cachetools.TTLCache。

设计原则：
- 只缓存 GET 读接口，写操作（PATCH/POST/PUT）不缓存
- 缓存 key = 规范化查询参数 hash，同参数直接命中
- TTL 策略按接口数据更新频率分级：
   - overview: 300s（5 分钟，聚合数据不需要实时）
   - alerts: 180s（3 分钟，告警状态变化稍快）
- 写操作自动 invalidate 相关缓存
- 单进程内有效（uvicorn 单 worker 或多 worker 各自独立缓存）
"""

from __future__ import annotations

import hashlib
import json
import time
from functools import wraps

from cachetools import TTLCache


def _make_cache_key(**kwargs: object) -> str:
    """将查询参数序列化为确定性的 cache key。

    排除值为 None 的参数，保证同一组"默认值+显式值"命中同一缓存。
    """
    filtered = {k: v for k, v in sorted(kwargs.items()) if v is not None}
    raw = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class DashboardCache:
    """Dashboard API 专用缓存容器。

    用法::

        cache = DashboardCache()
        payload = cache.get_or_compute("overview", lambda: service.load_dashboard_payload(...), grain="day", selected_date=date(2026,4,19))
        # 后续同样参数调用会直接返回缓存
    """

    def __init__(
        self,
        overview_ttl: int = 300,
        alerts_ttl: int = 180,
        alert_detail_ttl: int = 60,
        group_detail_ttl: int = 120,
        maxsize: int = 128,
    ) -> None:
        self._overview = TTLCache(maxsize=maxsize, ttl=overview_ttl)
        self._alerts = TTLCache(maxsize=maxsize, ttl=alerts_ttl)
        self._alert_detail = TTLCache(maxsize=maxsize * 2, ttl=alert_detail_ttl)
        self._group_detail = TTLCache(maxsize=maxsize, ttl=group_detail_ttl)

        # 命中统计（供日志和监控用）
        self.stats = {"hits": 0, "misses": 0}

    # ---- 公开接口 ----

    def get_overview(self, **params: object) -> dict | None:
        key = _make_cache_key(**params)
        return self._cache_get(self._overview, key, "overview")

    def set_overview(self, payload: dict, **params: object) -> None:
        key = _make_cache_key(**params)
        self._overview[key] = payload

    def get_alerts(self, **params: object) -> list | None:
        key = _make_cache_key(**params)
        return self._cache_get(self._alerts, key, "alerts")

    def set_alerts(self, payload: list, **params: object) -> None:
        key = _make_cache_key(**params)
        self._alerts[key] = payload

    def get_alert_detail(self, **params: object) -> dict | None:
        key = _make_cache_key(**params)
        return self._cache_get(self._alert_detail, key, "alert_detail")

    def set_alert_detail(self, payload: dict, **params: object) -> None:
        key = _make_cache_key(**params)
        self._alert_detail[key] = payload

    def get_group_detail(self, **params: object) -> dict | None:
        key = _make_cache_key(**params)
        return self._cache_get(self._group_detail, key, "group_detail")

    def set_group_detail(self, payload: dict, **params: object) -> None:
        key = _make_cache_key(**params)
        self._group_detail[key] = payload

    # ---- 失效操作 ----

    def invalidate_alerts(self, grain: str, anchor_date) -> None:
        """告警状态变更时清除对应日期的 alerts 缓存。"""
        prefix = _make_cache_key(grain=grain, anchor_date=anchor_date.isoformat())
        keys_to_remove = [k for k in self._alerts if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._alerts[k]

    def invalidate_alert_detail(self, alert_id: str) -> None:
        """单条告警状态变更时清除该条详情缓存。"""
        keys_to_remove = [k for k in self._alert_detail if k.endswith(alert_id[:12])]
        for k in keys_to_remove:
            del self._alert_detail[k]

    def invalidate_overview(self, **params: object) -> None:
        """数据导入/刷新后清除特定 overview 缓存。"""
        key = _make_cache_key(**params)
        self._overview.pop(key, None)

    def invalidate_group_detail(self, **params: object) -> None:
        key = _make_cache_key(**params)
        self._group_detail.pop(key, None)

    # ---- 内部 ----

    def _cache_get(self, store: TTLCache, key: str, label: str) -> object | None:
        result = store.get(key)
        if result is not None:
            self.stats["hits"] += 1
            return result
        self.stats["misses"] += 1
        return None

    @property
    def hit_rate(self) -> float:
        total = self.stats["hits"] + self.stats["misses"]
        if total == 0:
            return 0.0
        return self.stats["hits"] / total

    def __repr__(self) -> str:
        return (
            f"DashboardCache(hits={self.stats['hits']}, misses={self.stats['misses']}, "
            f"hit_rate={self.hit_rate:.1%})"
        )


# 模块级单例 —— 所有 router 共享同一个实例
_cache_instance: DashboardCache | None = None


def get_cache() -> DashboardCache:
    """获取全局缓存单例。"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DashboardCache()
    return _cache_instance
