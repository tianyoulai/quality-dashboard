/**
 * Auto-generated from config/alert_modules.yaml.
 * DO NOT EDIT BY HAND. Run `pnpm gen:config` to regenerate.
 */

import type { AlertModuleConfig } from "./alert-module.types";

export const ALERT_MODULE_CONFIG: AlertModuleConfig = {
  "modules_in_order": [
    "外检",
    "内检",
    "新人外检",
    "新人内检",
    "BadCase",
    "全局",
    "其他"
  ],
  "default_module": "其他",
  "grain_map": {
    "system": "全局",
    "queue": "队列",
    "group": "组",
    "reviewer": "审核员"
  },
  "grain_options": [
    "队列",
    "组",
    "全局",
    "审核员"
  ],
  "rules": [
    {
      "name": "badcase",
      "module": "BadCase",
      "match": {
        "rule_code_upper_includes": [
          "BADCASE"
        ],
        "target_key_upper_startswith": [
          "BADCASE"
        ],
        "target_key_contains": [
          "外部反馈"
        ]
      }
    },
    {
      "name": "newcomer_internal",
      "module": "新人内检",
      "match": {
        "target_key_upper_includes": [
          "18365"
        ]
      }
    },
    {
      "name": "newcomer_external",
      "module": "新人外检",
      "match": {
        "target_key_upper_includes": [
          "10816"
        ]
      }
    },
    {
      "name": "internal",
      "module": "内检",
      "match": {
        "target_key_contains": [
          "导出",
          "内部团队"
        ]
      }
    },
    {
      "name": "external",
      "module": "外检",
      "match": {
        "target_key_contains": [
          "A组",
          "B组",
          "C组"
        ]
      }
    },
    {
      "name": "system",
      "module": "全局",
      "match": {
        "target_key_equals": [
          "全局"
        ]
      }
    }
  ]
} as const;
