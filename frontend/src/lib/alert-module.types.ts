/** 告警模块配置类型 —— 与 config/alert_modules.yaml schema 对齐。 */

export interface AlertModuleRuleMatch {
  rule_code_upper_includes?: string[];
  target_key_upper_startswith?: string[];
  target_key_upper_includes?: string[];
  target_key_contains?: string[];
  target_key_equals?: string[];
}

export interface AlertModuleRule {
  name: string;
  module: string;
  match: AlertModuleRuleMatch;
}

export interface AlertModuleConfig {
  modules_in_order: readonly string[];
  default_module: string;
  grain_map: Readonly<Record<string, string>>;
  grain_options: readonly string[];
  rules: readonly AlertModuleRule[];
}
