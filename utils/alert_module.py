"""告警模块分类 —— 加载 config/alert_modules.yaml 并暴露判定函数。

跨端单一真实源：
  - 本模块：Python 运行时直接加载 yaml。
  - 前端：frontend/src/lib/alert-module.config.generated.ts
         由 frontend/scripts/gen-alert-module-config.mts 读同一份 yaml 生成。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "alert_modules.yaml"


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid alert_modules.yaml: {type(data)}")
    return data


def get_modules_in_order() -> list[str]:
    return list(_load().get("modules_in_order", []))


def get_grain_map() -> dict[str, str]:
    return dict(_load().get("grain_map", {}))


def get_grain_options() -> list[str]:
    return list(_load().get("grain_options", []))


def grain_label(target_level: str | None) -> str:
    """target_level → 中文粒度标签；未知值原样返回。"""
    text = (target_level or "").strip()
    return get_grain_map().get(text, text)


def infer_alert_module(target_key: str | None, rule_code: str | None) -> str:
    """从告警的 target_key / rule_code 推断所属模块。

    规则配置：config/alert_modules.yaml，按 rules 数组顺序匹配，命中即返回。
    """
    tk_raw = target_key or ""
    rc_raw = rule_code or ""
    tk_upper = tk_raw.upper()
    rc_upper = rc_raw.upper()

    cfg = _load()
    for rule in cfg.get("rules", []):
        match = rule.get("match") or {}
        # rule_code_upper_includes
        for sub in match.get("rule_code_upper_includes", []) or []:
            if sub and sub.upper() in rc_upper:
                return rule["module"]
        # target_key_upper_startswith
        for prefix in match.get("target_key_upper_startswith", []) or []:
            if prefix and tk_upper.startswith(prefix.upper()):
                return rule["module"]
        # target_key_upper_includes
        for sub in match.get("target_key_upper_includes", []) or []:
            if sub and sub.upper() in tk_upper:
                return rule["module"]
        # target_key_contains (大小写敏感原串)
        for sub in match.get("target_key_contains", []) or []:
            if sub and sub in tk_raw:
                return rule["module"]
        # target_key_equals
        for val in match.get("target_key_equals", []) or []:
            if tk_raw == val:
                return rule["module"]

    return cfg.get("default_module", "其他")
