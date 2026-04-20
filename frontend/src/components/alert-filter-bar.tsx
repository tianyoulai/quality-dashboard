"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useTransition } from "react";

import {
  ALERT_GRAIN_OPTIONS,
  ALERT_MODULES_IN_ORDER,
  type AlertGrainLabel,
  type AlertModule,
} from "@/lib/alert-module";

type SeverityKey = "P0" | "P1" | "P2";
const SEVERITY_OPTIONS: readonly SeverityKey[] = ["P0", "P1", "P2"];

type StatusValue = "all" | "open" | "resolved";

export type AlertFilterBarProps = {
  /** 当前参数反显用。 */
  activeSeverities: SeverityKey[];
  activeModules: AlertModule[];
  activeGrains: AlertGrainLabel[];
  activeStatus: StatusValue;
  /** 仅列出数据中真实出现过的选项，避免干扰点击。 */
  availableModules: AlertModule[];
  availableGrains: AlertGrainLabel[];
  /** 过滤后剩余 / 总条数，直接反馈筛选效果。 */
  filteredCount: number;
  totalCount: number;
};

function toggleInList<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
}

export function AlertFilterBar({
  activeSeverities,
  activeModules,
  activeGrains,
  activeStatus,
  availableModules,
  availableGrains,
  filteredCount,
  totalCount,
}: AlertFilterBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = useTransition();

  function applyChange(updates: Record<string, string[] | string | null>) {
    const next = new URLSearchParams(searchParams?.toString() ?? "");
    for (const [key, value] of Object.entries(updates)) {
      next.delete(key);
      if (Array.isArray(value)) {
        for (const item of value) if (item) next.append(key, item);
      } else if (value != null && value !== "") {
        next.set(key, value);
      }
    }
    const query = next.toString();
    startTransition(() => {
      router.replace(query ? `${pathname}?${query}` : pathname);
    });
  }

  function onToggleSeverity(s: SeverityKey) {
    applyChange({ alert_sev: toggleInList(activeSeverities, s) });
  }
  function onToggleModule(m: AlertModule) {
    applyChange({ alert_module: toggleInList(activeModules, m) });
  }
  function onToggleGrain(g: AlertGrainLabel) {
    applyChange({ alert_grain: toggleInList(activeGrains, g) });
  }
  function onChangeStatus(s: StatusValue) {
    applyChange({ alert_status_filter: s === "all" ? null : s });
  }
  function onClearAll() {
    applyChange({
      alert_sev: [],
      alert_module: [],
      alert_grain: [],
      alert_status_filter: null,
    });
  }

  const hasAnyFilter =
    activeSeverities.length > 0 ||
    activeModules.length > 0 ||
    activeGrains.length > 0 ||
    activeStatus !== "all";

  return (
    <section className="panel subtle-panel alert-filter-bar">
      <div className="panel-header">
        <div>
          <h4 className="panel-title">告警筛选</h4>
          <p className="panel-subtitle">
            三排筛选 + 状态：和 Streamlit 侧口径一致；多选叠加，切换会实时更新下方批量流转表格。
          </p>
        </div>
        <div className="hero-actions">
          <span className="kpi-pill">
            {filteredCount === totalCount
              ? `全部 ${totalCount} 条`
              : `筛后 ${filteredCount} / ${totalCount}`}
          </span>
          {hasAnyFilter ? (
            <button
              type="button"
              className="link-button"
              onClick={onClearAll}
              disabled={pending}
            >
              清空筛选
            </button>
          ) : null}
        </div>
      </div>

      <div className="filter-row">
        <span className="filter-row-label">等级</span>
        <div className="chip-group">
          {SEVERITY_OPTIONS.map((sev) => {
            const active = activeSeverities.includes(sev);
            return (
              <button
                key={sev}
                type="button"
                className={`chip severity-${sev.toLowerCase()}${active ? " active" : ""}`}
                onClick={() => onToggleSeverity(sev)}
                disabled={pending}
              >
                {sev}
              </button>
            );
          })}
        </div>
      </div>

      <div className="filter-row">
        <span className="filter-row-label">模块</span>
        <div className="chip-group">
          {ALERT_MODULES_IN_ORDER.filter((m) => availableModules.includes(m)).map((m) => {
            const active = activeModules.includes(m);
            return (
              <button
                key={m}
                type="button"
                className={`chip${active ? " active" : ""}`}
                onClick={() => onToggleModule(m)}
                disabled={pending}
              >
                {m}
              </button>
            );
          })}
          {availableModules.length === 0 ? (
            <span className="muted">当前没有可筛的模块（名单为空）</span>
          ) : null}
        </div>
      </div>

      <div className="filter-row">
        <span className="filter-row-label">粒度</span>
        <div className="chip-group">
          {ALERT_GRAIN_OPTIONS.filter((g) => availableGrains.includes(g)).map((g) => {
            const active = activeGrains.includes(g);
            return (
              <button
                key={g}
                type="button"
                className={`chip${active ? " active" : ""}`}
                onClick={() => onToggleGrain(g)}
                disabled={pending}
              >
                {g}
              </button>
            );
          })}
          {availableGrains.length === 0 ? (
            <span className="muted">当前没有可筛的粒度</span>
          ) : null}
        </div>
      </div>

      <div className="filter-row">
        <span className="filter-row-label">状态</span>
        <div className="chip-group">
          {(
            [
              { value: "all" as const, label: "全部" },
              { value: "open" as const, label: "未解决" },
              { value: "resolved" as const, label: "已解决" },
            ]
          ).map((s) => (
            <button
              key={s.value}
              type="button"
              className={`chip${activeStatus === s.value ? " active" : ""}`}
              onClick={() => onChangeStatus(s.value)}
              disabled={pending}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
