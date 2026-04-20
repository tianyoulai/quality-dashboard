/**
 * 告警模块 / 粒度推断与中文化。
 *
 * 单一真实源：`config/alert_modules.yaml`。
 *   - Python 运行时加载（utils/alert_module.py）。
 *   - TS 由 scripts/gen_alert_module_config.py 生成 `alert-module.config.generated.ts`。
 *
 * 改规则只改 yaml；改完跑 `pnpm gen:config`。
 */

import { ALERT_MODULE_CONFIG } from "./alert-module.config.generated";
import type { AlertModuleRule } from "./alert-module.types";

export type AlertModule =
  | "外检"
  | "内检"
  | "新人外检"
  | "新人内检"
  | "BadCase"
  | "全局"
  | "其他";

export const ALERT_MODULES_IN_ORDER: AlertModule[] =
  ALERT_MODULE_CONFIG.modules_in_order.slice() as AlertModule[];

export const ALERT_GRAIN_OPTIONS = ALERT_MODULE_CONFIG.grain_options;
export type AlertGrainLabel = (typeof ALERT_GRAIN_OPTIONS)[number];

const DEFAULT_MODULE = ALERT_MODULE_CONFIG.default_module as AlertModule;

function matchRule(rule: AlertModuleRule, tkRaw: string, rcRaw: string): boolean {
  const tkUpper = tkRaw.toUpperCase();
  const rcUpper = rcRaw.toUpperCase();
  const m = rule.match;

  if (m.rule_code_upper_includes) {
    for (const sub of m.rule_code_upper_includes) {
      if (sub && rcUpper.includes(sub.toUpperCase())) return true;
    }
  }
  if (m.target_key_upper_startswith) {
    for (const prefix of m.target_key_upper_startswith) {
      if (prefix && tkUpper.startsWith(prefix.toUpperCase())) return true;
    }
  }
  if (m.target_key_upper_includes) {
    for (const sub of m.target_key_upper_includes) {
      if (sub && tkUpper.includes(sub.toUpperCase())) return true;
    }
  }
  if (m.target_key_contains) {
    for (const sub of m.target_key_contains) {
      if (sub && tkRaw.includes(sub)) return true;
    }
  }
  if (m.target_key_equals) {
    for (const val of m.target_key_equals) {
      if (tkRaw === val) return true;
    }
  }
  return false;
}

/** 从 target_key / rule_code 推断所属业务模块。规则源：config/alert_modules.yaml。 */
export function inferAlertModule(
  targetKey: string | null | undefined,
  ruleCode: string | null | undefined,
): AlertModule {
  const tk = (targetKey ?? "").toString();
  const rc = (ruleCode ?? "").toString();

  for (const rule of ALERT_MODULE_CONFIG.rules) {
    if (matchRule(rule, tk, rc)) {
      return rule.module as AlertModule;
    }
  }
  return DEFAULT_MODULE;
}

/** `target_level` → 中文粒度标签；未知值原样返回。 */
export function grainLabel(targetLevel: string | null | undefined): string {
  const text = (targetLevel ?? "").toString();
  return ALERT_MODULE_CONFIG.grain_map[text] ?? text;
}
