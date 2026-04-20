/**
 * 首页 Dashboard 的辅助类型与函数。
 *
 * 从 app/page.tsx 拆出，让首页组件文件瘦身。
 * 所有类型和函数都是纯逻辑（无 React 依赖），可被任意页面或组件复用。
 */

import {
  buildQueryString,
  pickText,
  toDateInputValue,
  toDisplayDate,
  toInteger,
  toPercent,
} from "@/lib/formatters";

// ===== 类型 =====

export type AlertDetailHrefOptions = {
  groupName?: string;
  queueName?: string;
  errorType?: string;
  focusSource?: string;
  focusScope?: string;
  focusJoinKeyType?: string;
  focusAlertId?: string;
  focusAlertRuleName?: string;
  dashboardGrain?: string;
  dashboardSelectedDate?: string;
  dashboardAlertId?: string;
  dashboardGroupName?: string;
  dashboardFocusQueueName?: string;
  dashboardFocusJoinKeyType?: string;
  demoFixture?: string;
  dashboardDemoFixture?: string;
};

export type DashboardAlertHrefOptions = {
  grain: string;
  selectedDate: string;
  alertId?: string;
  groupName?: string;
  focusQueueName?: string;
  focusJoinKeyType?: string;
  demoFixture?: string;
};

export type GlobalAlertFocusItem = {
  key: string;
  label: string;
  count: number;
  groupName?: string;
  queueName?: string;
  joinKeyType?: string;
  groupCoverage: number;
  queueCoverage: number;
  sampleShare: number;
};

export type GlobalAlertFocusBucket = Omit<GlobalAlertFocusItem, "groupCoverage" | "queueCoverage" | "sampleShare"> & {
  groupKeys: Set<string>;
  queueKeys: Set<string>;
};

export type FocusComparisonCard = {
  key: string;
  title: string;
  summary: string;
  tone: "success" | "warning" | "danger";
};

// ===== 通用辅助 =====

export function readParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/** 读取多值参数；支持 `?k=a&k=b` 和 `?k=a,b` 两种形式。 */
export function readMultiParam(value: string | string[] | undefined): string[] {
  if (value === undefined) return [];
  const raw = Array.isArray(value) ? value : [value];
  const out: string[] = [];
  for (const item of raw) {
    for (const seg of item.split(",")) {
      const t = seg.trim();
      if (t) out.push(t);
    }
  }
  return out;
}

export function getRows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

export function formatDateTime(value: unknown): string {
  const text = pickText(value, "");
  if (!text) {
    return "—";
  }
  return text.replace("T", " ").slice(0, 19);
}

export function truncateText(value: unknown, maxLength = 40): string {
  const text = pickText(value, "");
  if (!text) {
    return "—";
  }
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

// ===== 告警样本表 =====

export function buildAlertSampleColumns(rows: Array<Record<string, unknown>>): {
  columns: Array<{ key: string; label: string; sortable?: boolean }>;
  cellBuilders: Record<string, (row: Record<string, unknown>) => string>;
} {
  const hasGroupName = rows.some((row) => pickText(row.group_name, "") !== "");
  const hasJoinStatus = rows.some((row) => pickText(row.join_status, "") !== "");
  const hasJoinKeyType = rows.some((row) => pickText(row.join_key_type, "") !== "");
  const hasErrorType = rows.some((row) => pickText(row.error_type, "") !== "");

  const columns: Array<{ key: string; label: string; sortable?: boolean }> = [
    { key: "biz_date", label: "日期", sortable: true },
  ];
  const cellBuilders: Record<string, (row: Record<string, unknown>) => string> = {
    biz_date: (row) => toDisplayDate(row.biz_date as string | undefined),
  };

  if (hasGroupName) {
    columns.push({ key: "group_name", label: "组别", sortable: true });
  }

  columns.push(
    { key: "queue_name", label: "队列", sortable: true },
    { key: "reviewer_name", label: "审核人", sortable: true },
    {
      key: hasJoinStatus ? "join_status" : "final_review_result",
      label: hasJoinStatus ? "联表状态" : "最终结果",
      sortable: true,
    },
  );

  if (hasJoinKeyType) {
    columns.push({ key: "join_key_type", label: "主键类型", sortable: true });
  }

  if (hasErrorType) {
    columns.push({ key: "error_type", label: "错误类型", sortable: true });
  }

  columns.push(
    { key: "comment_text", label: "样本文本" },
    { key: "qa_note", label: "备注" },
    { key: "join_key", label: "关联主键" },
  );
  cellBuilders.comment_text = (row) => truncateText(row.comment_text, 42);
  cellBuilders.qa_note = (row) => truncateText(row.qa_note, 24);
  cellBuilders.join_key = (row) => truncateText(row.join_key, 18);

  return { columns, cellBuilders };
}

// ===== 状态/严重度 =====

export function getStatusTone(status: unknown): "success" | "warning" | "neutral" {
  const normalized = pickText(status, "").toLowerCase();
  if (normalized === "resolved") {
    return "success";
  }
  if (normalized === "open") {
    return "warning";
  }
  return "neutral";
}

export function getSeverityTone(severity: unknown): "danger" | "warning" | "neutral" {
  const normalized = pickText(severity, "").toUpperCase();
  if (normalized === "P0") {
    return "danger";
  }
  if (normalized === "P1") {
    return "warning";
  }
  return "neutral";
}

// ===== 日期 =====

export function addDays(dateText: string, days: number): string {
  const target = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(target.getTime())) {
    return dateText;
  }
  target.setDate(target.getDate() + days);
  return target.toISOString().slice(0, 10);
}

export function getMonthEnd(dateText: string): string {
  const target = new Date(`${dateText}T00:00:00`);
  if (Number.isNaN(target.getTime())) {
    return dateText;
  }
  return new Date(target.getFullYear(), target.getMonth() + 1, 0).toISOString().slice(0, 10);
}

// ===== 告警分类 =====

export function getAlertIssueFilter(ruleCode: unknown): string | undefined {
  const normalized = pickText(ruleCode, "").toUpperCase();
  switch (normalized) {
    case "RAW_ACC_LT_99_DAY":
    case "RAW_ACC_DROP_GT_1P5_WEEK":
      return "原始错误";
    case "FINAL_ACC_LT_99_QUEUE_DAY":
      return "最终错误";
    case "MISS_RATE_GT_035_DAY":
    case "MISS_RATE_SPIKE_GT_0P2_QUEUE_WEEK":
      return "漏判";
    case "APPEAL_REV_GT_18_DAY":
      return "申诉改判";
    case "TOP_ERROR_SHARE_GT_35_QUEUE_MONTH":
    case "ERROR_TYPE_SHARE_GT_15_QUEUE_WEEK":
      return "全部问题";
    default:
      return undefined;
  }
}

export function normalizeFocusValue(value: unknown): string | null {
  const text = pickText(value, "").trim();
  if (!text || text === "—") {
    return null;
  }
  return text;
}

export function getAlertSampleScopeLabel(scope: string): string {
  if (scope === "scoped") {
    return "scoped 样本";
  }
  if (scope === "global") {
    return "global 样本";
  }
  return "当前告警样本";
}

export function getRestoreLayerLabel({
  groupName,
  focusQueueName,
  focusJoinKeyType,
}: {
  groupName?: string;
  focusQueueName?: string;
  focusJoinKeyType?: string;
}): string {
  if (groupName && focusQueueName) {
    return `${groupName} / ${focusQueueName} scoped 视图`;
  }
  if (groupName) {
    return `${groupName} scoped 视图`;
  }
  if (focusJoinKeyType) {
    return `global 样本（主键类型：${focusJoinKeyType}）`;
  }
  return "当前告警详情";
}

export function getReturnModeLabel(mode: string, isLegacyFallback: boolean): string {
  if (isLegacyFallback || mode === "legacy_fallback") {
    return "旧链接降级恢复";
  }
  if (mode === "previous_layer") {
    return "回上一层聚焦";
  }
  if (mode === "clear_focus") {
    return "彻底清空聚焦";
  }
  return "返回首页当前告警";
}

// ===== URL 构建 =====

export function buildDashboardAlertHref({
  grain,
  selectedDate,
  alertId,
  groupName,
  focusQueueName,
  focusJoinKeyType,
  demoFixture,
}: DashboardAlertHrefOptions): string {
  return (
    buildQueryString({
      grain,
      selected_date: selectedDate,
      alert_id: alertId,
      group_name: groupName,
      focus_queue_name: focusQueueName,
      focus_join_key_type: focusJoinKeyType,
      demo_fixture: demoFixture,
    }) || "/"
  );
}

export function buildAlertDetailsHref(detail: Record<string, unknown>, overrides: AlertDetailHrefOptions = {}): string {
  const grain = pickText(detail.grain, "day");
  const anchorDate = toDateInputValue(pickText(detail.anchor_date, ""));
  if (!anchorDate) {
    return "/details";
  }

  const dateRange =
    grain === "week"
      ? { date_start: anchorDate, date_end: addDays(anchorDate, 6) }
      : grain === "month"
        ? { date_start: anchorDate, date_end: getMonthEnd(anchorDate) }
        : { date_start: anchorDate, date_end: anchorDate };

  const issueFilter = getAlertIssueFilter(detail.rule_code);
  const focusSource = overrides.focusSource;
  return `/details${buildQueryString({
    ...dateRange,
    group_name: overrides.groupName ?? pickText(detail.group_name, ""),
    queue_name: overrides.queueName ?? pickText(detail.queue_name, ""),
    error_type: overrides.errorType ?? pickText(detail.error_type, ""),
    only_issues: issueFilter ? "true" : undefined,
    issue_filter: issueFilter,
    focus_source: focusSource,
    focus_scope: focusSource ? overrides.focusScope : undefined,
    focus_join_key_type: focusSource ? overrides.focusJoinKeyType : undefined,
    focus_alert_id: focusSource ? overrides.focusAlertId ?? pickText(detail.alert_id, "") : undefined,
    focus_alert_rule_name: focusSource ? overrides.focusAlertRuleName ?? pickText(detail.rule_name, "") : undefined,
    dashboard_grain: overrides.dashboardGrain,
    dashboard_selected_date: overrides.dashboardSelectedDate,
    dashboard_alert_id: overrides.dashboardAlertId,
    dashboard_group_name: overrides.dashboardGroupName,
    dashboard_focus_queue_name: overrides.dashboardFocusQueueName,
    dashboard_focus_join_key_type: overrides.dashboardFocusJoinKeyType,
    demo_fixture: overrides.demoFixture,
    dashboard_demo_fixture: overrides.dashboardDemoFixture ?? overrides.demoFixture,
  })}`;
}

// ===== 聚焦（Focus）聚合 =====

export function buildTopFocusItems(
  rows: Array<Record<string, unknown>>,
  projector: (row: Record<string, unknown>) => Omit<GlobalAlertFocusItem, "count" | "groupCoverage" | "queueCoverage" | "sampleShare"> | null,
): GlobalAlertFocusItem[] {
  const buckets = new Map<string, GlobalAlertFocusBucket>();
  const totalCount = rows.length;

  rows.forEach((row) => {
    const item = projector(row);
    if (!item) {
      return;
    }
    const normalizedGroupName = normalizeFocusValue(row.group_name);
    const normalizedQueueName = normalizeFocusValue(row.queue_name);
    const queueKey = normalizedGroupName && normalizedQueueName
      ? `${normalizedGroupName}::${normalizedQueueName}`
      : normalizedQueueName;
    const existing = buckets.get(item.key);

    if (existing) {
      existing.count += 1;
      if (normalizedGroupName) {
        existing.groupKeys.add(normalizedGroupName);
      }
      if (queueKey) {
        existing.queueKeys.add(queueKey);
      }
      return;
    }

    const bucket: GlobalAlertFocusBucket = {
      ...item,
      count: 1,
      groupKeys: new Set<string>(),
      queueKeys: new Set<string>(),
    };

    if (normalizedGroupName) {
      bucket.groupKeys.add(normalizedGroupName);
    }
    if (queueKey) {
      bucket.queueKeys.add(queueKey);
    }

    buckets.set(item.key, bucket);
  });

  return [...buckets.values()]
    .sort(
      (left, right) =>
        right.count - left.count ||
        right.queueKeys.size - left.queueKeys.size ||
        right.groupKeys.size - left.groupKeys.size ||
        left.label.localeCompare(right.label, "zh-CN"),
    )
    .map(({ groupKeys, queueKeys, ...item }) => ({
      ...item,
      groupCoverage: groupKeys.size,
      queueCoverage: queueKeys.size,
      sampleShare: totalCount > 0 ? item.count / totalCount : 0,
    }));
}

export function buildVisibleFocusItems(
  items: GlobalAlertFocusItem[],
  isActive: (item: GlobalAlertFocusItem) => boolean,
  limit = 3,
): GlobalAlertFocusItem[] {
  const visibleItems = items.slice(0, limit);
  const activeItem = items.find(isActive);
  if (!activeItem || visibleItems.some((item) => item.key === activeItem.key)) {
    return visibleItems;
  }
  return [...visibleItems, activeItem];
}

export function getFocusCandidateMetricsText(item: GlobalAlertFocusItem): string {
  return `命中 ${toInteger(item.count)} 条样本，占当前范围 ${toPercent(item.sampleShare)}，覆盖 ${toInteger(item.groupCoverage)} 个组别 / ${toInteger(item.queueCoverage)} 个队列`;
}

export function getFocusPanelSummary({
  dimensionLabel,
  topItem,
  activeItem,
  returnedFromDetails,
}: {
  dimensionLabel: string;
  topItem?: GlobalAlertFocusItem;
  activeItem?: GlobalAlertFocusItem | null;
  returnedFromDetails: boolean;
}): string {
  if (!topItem) {
    return "";
  }

  const topSummary = `${dimensionLabel}当前最新 Top1 是 ${topItem.label}，${getFocusCandidateMetricsText(topItem)}。排序先看样本数；样本数相同，再优先覆盖范围更广的候选。`;
  if (!activeItem) {
    return returnedFromDetails
      ? `${topSummary} 这次回看还没恢复到这一层，可以直接拿它当新的优先候选。`
      : `${topSummary} 当前还是首次排查，建议先从它开始缩小范围。`;
  }
  if (activeItem.key === topItem.key) {
    return `${topSummary} 当前高亮项就是最新 Top1，可以继续沿这条线深挖。`;
  }

  const sampleGap = topItem.count - activeItem.count;
  const queueGap = topItem.queueCoverage - activeItem.queueCoverage;
  return `${topSummary} 但当前高亮的是 ${activeItem.label}（${getFocusCandidateMetricsText(activeItem)}）。和最新 Top1 相比，样本少 ${toInteger(sampleGap)} 条${queueGap > 0 ? `，覆盖队列少 ${toInteger(queueGap)} 个` : ""}；如果你要追当前主战场，建议切到最新 Top1。`;
}

export function getFocusItemRank(items: GlobalAlertFocusItem[], target?: GlobalAlertFocusItem | null): number | null {
  if (!target) {
    return null;
  }
  const index = items.findIndex((item) => item.key === target.key);
  return index >= 0 ? index + 1 : null;
}

export function getFocusGapText(topItem: GlobalAlertFocusItem, activeItem: GlobalAlertFocusItem): string {
  const gaps: string[] = [];
  const sampleGap = topItem.count - activeItem.count;
  const groupGap = topItem.groupCoverage - activeItem.groupCoverage;
  const queueGap = topItem.queueCoverage - activeItem.queueCoverage;

  if (sampleGap > 0) {
    gaps.push(`少 ${toInteger(sampleGap)} 条样本`);
  }
  if (groupGap > 0) {
    gaps.push(`少覆盖 ${toInteger(groupGap)} 个组别`);
  }
  if (queueGap > 0) {
    gaps.push(`少覆盖 ${toInteger(queueGap)} 个队列`);
  }

  return gaps.length > 0 ? gaps.join("，") : "覆盖范围基本持平";
}
