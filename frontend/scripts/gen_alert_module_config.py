#!/usr/bin/env python3
"""读 config/alert_modules.yaml，生成 frontend/src/lib/alert-module.config.generated.ts。

前端不依赖 js-yaml，保持 Node 子依赖最小；统一由 Python 生成 TS 常量。

使用：
    cd frontend && pnpm gen:config
或：
    python3 scripts/gen_alert_module_config.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 让脚本既能在 repo 根部运行，也能在 frontend/ 子目录里被 pnpm run 调起
HERE = Path(__file__).resolve()
# 尝试两种布局：
#   1) repo_root/frontend/scripts/gen_alert_module_config.py → repo_root/config/alert_modules.yaml
#   2) repo_root/scripts/gen_alert_module_config.py          → repo_root/config/alert_modules.yaml
_candidates = [
    HERE.parent.parent.parent / "config" / "alert_modules.yaml",
    HERE.parent.parent / "config" / "alert_modules.yaml",
]
CONFIG_PATH = next((p for p in _candidates if p.exists()), None)
if CONFIG_PATH is None:
    sys.stderr.write(f"[ERROR] 找不到 alert_modules.yaml，尝试过: {[str(p) for p in _candidates]}\n")
    sys.exit(1)

OUT_PATH = HERE.parent.parent / "src" / "lib" / "alert-module.config.generated.ts"

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    sys.stderr.write("[ERROR] 需要 PyYAML，请 pip install pyyaml\n")
    sys.exit(1)

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

# 走 JSON 序列化保证 TS 侧类型干净
payload = json.dumps(data, ensure_ascii=False, indent=2)

header = f"""/**
 * Auto-generated from {CONFIG_PATH.relative_to(HERE.parent.parent.parent).as_posix()}.
 * DO NOT EDIT BY HAND. Run `pnpm gen:config` to regenerate.
 */

import type {{ AlertModuleConfig }} from "./alert-module.types";

export const ALERT_MODULE_CONFIG: AlertModuleConfig = {payload} as const;
"""

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(header, encoding="utf-8")
print(f"[OK] wrote {OUT_PATH.relative_to(HERE.parent.parent.parent).as_posix()}")
