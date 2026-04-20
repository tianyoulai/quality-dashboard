#!/usr/bin/env python3
"""alert_modules 配置 & 双端一致性冒烟。

做两层校验：
  1. Config sync：比对 config/alert_modules.yaml  vs
     frontend/src/lib/alert-module.config.generated.ts 内嵌的 JSON，
     保证 TS 生成文件是 yaml 的忠实镜像。
  2. Logic parity：用相同的一组 (target_key, rule_code) 输入，
     跑 Python 版 infer_alert_module 和 “TS 等价 matcher”（在本脚本内
     用 Python 重实现 TS 侧 matcher 的逐条 OR 匹配），确保两边规则顺序
     + 命中语义一致。

TS matcher 的“正确性”通过以下三道防线保证：
  a) 本脚本 shadow matcher 与生产 TS matcher 字段+顺序一致
  b) tsc --noEmit 类型校验
  c) 真机 SSR 冒烟命中 chip severity + alert_module 筛选
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO))

from utils.alert_module import infer_alert_module  # noqa: E402
import yaml  # noqa: E402


YAML_PATH = REPO / "config" / "alert_modules.yaml"
GEN_TS_PATH = REPO / "frontend" / "src" / "lib" / "alert-module.config.generated.ts"


def parse_generated_ts(text: str) -> dict[str, Any]:
    # 抓 `export const ALERT_MODULE_CONFIG: AlertModuleConfig = {...} as const;` 的 JSON 块
    m = re.search(r"ALERT_MODULE_CONFIG[^=]*=\s*(\{.*?\})\s*as const;", text, re.S)
    if not m:
        raise ValueError("无法在 generated.ts 中解析出 ALERT_MODULE_CONFIG")
    return json.loads(m.group(1))


def shadow_infer(config: dict[str, Any], tk_raw: str, rc_raw: str) -> str:
    """Python 复刻 TS 侧 matcher，字段顺序和 TS 严格一致。"""
    tk_upper = tk_raw.upper()
    rc_upper = rc_raw.upper()
    for rule in config.get("rules", []):
        match = rule.get("match") or {}
        for sub in match.get("rule_code_upper_includes", []) or []:
            if sub and sub.upper() in rc_upper:
                return rule["module"]
        for prefix in match.get("target_key_upper_startswith", []) or []:
            if prefix and tk_upper.startswith(prefix.upper()):
                return rule["module"]
        for sub in match.get("target_key_upper_includes", []) or []:
            if sub and sub.upper() in tk_upper:
                return rule["module"]
        for sub in match.get("target_key_contains", []) or []:
            if sub and sub in tk_raw:
                return rule["module"]
        for val in match.get("target_key_equals", []) or []:
            if tk_raw == val:
                return rule["module"]
    return config.get("default_module", "其他")


CASES: list[tuple[str, str]] = [
    ("A组-评论", "ACC_LOW"),
    ("B组-评论", "ACC_LOW"),
    ("C组-评论", "ACC_LOW"),
    ("导出-质检", "ACC_LOW"),
    ("内部团队·邓生位", "ACC_LOW"),
    ("10816-新人培训", "ACC_LOW"),
    ("18365-新人评论测试", "ACC_LOW"),
    ("全局", "SLA_P0_UNRESOLVED"),
    ("BADCASE-抖音", "ANY"),
    ("外部反馈·周报", "ANY"),
    ("A组", "BADCASE_HIT"),   # BadCase 优先于外检
    ("未知队列", "ANY"),
    ("", ""),
    ("badcase-lower", "ANY"),
    ("a组", "ANY"),           # 大小写敏感：不应命中外检
]


def main() -> int:
    # 1) config sync
    yaml_data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    ts_data = parse_generated_ts(GEN_TS_PATH.read_text(encoding="utf-8"))
    if yaml_data != ts_data:
        print("[FAIL] yaml 与 generated.ts 内容不一致，请跑 `pnpm gen:config`")
        print("--- yaml ---")
        print(json.dumps(yaml_data, ensure_ascii=False, indent=2))
        print("--- ts   ---")
        print(json.dumps(ts_data, ensure_ascii=False, indent=2))
        return 1
    print("[OK] config sync: yaml == generated.ts")

    # 2) logic parity
    fails = 0
    for tk, rc in CASES:
        py_prod = infer_alert_module(tk, rc)           # 生产 Python 实现
        py_shadow_yaml = shadow_infer(yaml_data, tk, rc)  # shadow over yaml
        py_shadow_ts = shadow_infer(ts_data, tk, rc)      # shadow over ts
        all_eq = py_prod == py_shadow_yaml == py_shadow_ts
        if not all_eq:
            fails += 1
        status = "OK" if all_eq else "FAIL"
        print(
            f"[{status}] tk={tk!r:32} rc={rc:20} "
            f"py={py_prod:8} shadow(yaml)={py_shadow_yaml:8} shadow(ts)={py_shadow_ts}"
        )

    print(f"\nTotal cases: {len(CASES)}, failed: {fails}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
