import Link from "next/link";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { CollapsiblePanel } from "@/components/collapsible-panel";
import { DataTable } from "@/components/data-table";
import { ExportButton } from "@/components/export-button";
import { FilterActionsBar } from "@/components/filter-actions-bar";
import { SummaryCard } from "@/components/summary-card";
import { getApiBaseUrl, safeFetchApi } from "@/lib/api";
import { buildTableRows } from "@/lib/table-rows";
import {
  buildQueryString,
  pickText,
  toDateInputValue,
  toDisplayDate,
  toNumber,
} from "@/lib/formatters";

type SearchParams = Record<string, string | string[] | undefined>;

export const metadata: Metadata = {
  title: "明细查询",
};

type PageProps = {
  searchParams?: Promise<SearchParams>;
};

function readParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function getRows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function subtractDays(dateText: string, days: number): string {
  const target = new Date(`${dateText}T00:00:00`);
  target.setDate(target.getDate() - days);
  return target.toISOString().slice(0, 10);
}

/**
 * 纯前端级的日期合法性快检，用于在 UI 上提前告警。
 * 不替代后端校验——后端该怎么拒绝还是怎么拒绝；这里只是让用户不要等接口报错才知道参数不对。
 */
function evaluateDateWindow(
  start: string,
  end: string,
  minDate: string,
  maxDate: string,
): { tone: "warning" | "neutral"; message: string } | null {
  if (!start || !end) {
    return null;
  }
  if (start > end) {
    return {
      tone: "warning",
      message: `开始日期 ${start} 比结束日期 ${end} 晚，查询大概率没有命中。先把顺序调回来再查。`,
    };
  }
  if (minDate && end < minDate) {
    return {
      tone: "warning",
      message: `结束日期 ${end} 已经早于数仓当前最早保留日期 ${minDate}，数据已按 45 天策略裁剪，查出来是空。`,
    };
  }
  if (maxDate && start > maxDate) {
    return {
      tone: "warning",
      message: `开始日期 ${start} 已经晚于数仓当前最新日期 ${maxDate}，多半是导入还没跑到这天。`,
    };
  }
  const startTs = new Date(`${start}T00:00:00`).getTime();
  const endTs = new Date(`${end}T00:00:00`).getTime();
  if (Number.isFinite(startTs) && Number.isFinite(endTs)) {
    const spanDays = Math.round((endTs - startTs) / 86400000) + 1;
    if (spanDays > 30) {
      return {
        tone: "warning",
        message: `当前日期跨度 ${spanDays} 天，接近数仓 45 天保留上限；查询和导出都会偏慢，必要时缩到 7-14 天再细看。`,
      };
    }
  }
  return null;
}

function formatDateTime(value: unknown): string {
  const text = pickText(value, "—");
  if (!text || text === "—") {
    return "—";
  }
  return text.replace("T", " ");
}

function getAlertSampleScopeLabel(scope: string): string {
  if (scope === "scoped") {
    return "scoped 样本";
  }
  if (scope === "global") {
    return "global 样本";
  }
  return "当前告警样本";
}

function getRestoreLayerLabel({
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

function getPreviousLayerActionLabel({
  groupName,
  focusQueueName,
  focusJoinKeyType,
}: {
  groupName?: string;
  focusQueueName?: string;
  focusJoinKeyType?: string;
}): string {
  if (focusQueueName) {
    return "回上一层组别";
  }
  if (groupName) {
    return "回到 global 候选";
  }
  if (focusJoinKeyType) {
    return "清空主键类型";
  }
  return "重新定位当前告警";
}

function getEntryModeLabel(hasFocusedContext: boolean): string {
  return hasFocusedContext ? "延续回看进入" : "重新定位进入";
}

type DashboardReturnOptions = {
  grain?: string;
  selectedDate?: string;
  alertId?: string;
  groupName?: string;
  focusQueueName?: string;
  focusJoinKeyType?: string;
  returnMode?: string;
  returnStatus?: string;
  returnReason?: string;
};

function buildDashboardReturnHref({
  grain,
  selectedDate,
  alertId,
  groupName,
  focusQueueName,
  focusJoinKeyType,
  returnMode,
  returnStatus,
  returnReason,
}: DashboardReturnOptions): string {
  const queryString = buildQueryString({
    grain,
    selected_date: selectedDate,
    alert_id: alertId,
    group_name: groupName,
    focus_queue_name: focusQueueName,
    focus_join_key_type: focusJoinKeyType,
    return_source: "details",
    return_mode: returnMode,
    return_status: returnStatus,
    return_reason: returnReason,
    return_alert_id: alertId,
    return_group_name: groupName,
    return_focus_queue_name: focusQueueName,
    return_focus_join_key_type: focusJoinKeyType,
  });
  return queryString ? `/${queryString}` : "/";
}

export default async function DetailsPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const metaResult = await safeFetchApi<Record<string, unknown>>("/api/v1/meta/date-range");
  const filtersResult = await safeFetchApi<Record<string, unknown>>("/api/v1/details/filters");
  const schemaResult = await safeFetchApi<Record<string, unknown>>("/api/v1/details/schema");

  const maxDate =
    toDateInputValue((filtersResult.data?.max_date as string | undefined) || (metaResult.data?.max_date as string | undefined)) ||
    toDateInputValue(metaResult.data?.default_selected_date as string | undefined);
  const minDate = toDateInputValue((filtersResult.data?.min_date as string | undefined) || (metaResult.data?.min_date as string | undefined));

  const dateStart = readParam(params.date_start) || subtractDays(maxDate, 6);
  const dateEnd = readParam(params.date_end) || maxDate;
  const dateWindowIssue = evaluateDateWindow(dateStart, dateEnd, minDate, maxDate);
  const groupName = readParam(params.group_name) || "";
  const queueName = readParam(params.queue_name) || "";
  const reviewerName = readParam(params.reviewer_name) || "";
  const errorType = readParam(params.error_type) || "";
  const issueFilter = readParam(params.issue_filter) || "全部问题";
  const onlyIssues = readParam(params.only_issues) === "true";
  const limit = readParam(params.limit) || "2000";
  const focusSource = readParam(params.focus_source) || "";
  const focusScope = readParam(params.focus_scope) || "";
  const focusJoinKeyType = readParam(params.focus_join_key_type) || "";
  const focusAlertId = readParam(params.focus_alert_id) || "";
  const focusAlertRuleName = readParam(params.focus_alert_rule_name) || "";
  const dashboardGrain = readParam(params.dashboard_grain) || "day";
  const dashboardSelectedDate = readParam(params.dashboard_selected_date) || "";
  const dashboardAlertId = readParam(params.dashboard_alert_id) || "";
  const dashboardGroupName = readParam(params.dashboard_group_name) || "";
  const dashboardFocusQueueName = readParam(params.dashboard_focus_queue_name) || "";
  const dashboardFocusJoinKeyType = readParam(params.dashboard_focus_join_key_type) || "";
  const hasFocusContext = focusSource === "system_alert";
  const hasDashboardReturnContext = Boolean(dashboardSelectedDate && dashboardAlertId);
  const dashboardHasScopedFocus = Boolean(dashboardGroupName || dashboardFocusQueueName);
  const dashboardHasAnyFocus = Boolean(dashboardHasScopedFocus || dashboardFocusJoinKeyType);
  const dashboardReturnHref = hasDashboardReturnContext
    ? buildDashboardReturnHref({
        grain: dashboardGrain,
        selectedDate: dashboardSelectedDate,
        alertId: dashboardAlertId,
        groupName: dashboardGroupName || undefined,
        focusQueueName: dashboardFocusQueueName || undefined,
        focusJoinKeyType: dashboardFocusJoinKeyType || undefined,
        returnMode: "current_alert",
        returnStatus: "exact",
      })
    : "/";
  const dashboardPreviousLayerHref = !hasDashboardReturnContext
    ? null
    : dashboardFocusQueueName
      ? buildDashboardReturnHref({
          grain: dashboardGrain,
          selectedDate: dashboardSelectedDate,
          alertId: dashboardAlertId,
          groupName: dashboardGroupName || undefined,
          focusJoinKeyType: dashboardFocusJoinKeyType || undefined,
          returnMode: "previous_layer",
          returnStatus: "exact",
        })
      : dashboardGroupName
        ? buildDashboardReturnHref({
            grain: dashboardGrain,
            selectedDate: dashboardSelectedDate,
            alertId: dashboardAlertId,
            focusJoinKeyType: dashboardFocusJoinKeyType || undefined,
            returnMode: "previous_layer",
            returnStatus: "exact",
          })
        : dashboardFocusJoinKeyType
          ? buildDashboardReturnHref({
              grain: dashboardGrain,
              selectedDate: dashboardSelectedDate,
              alertId: dashboardAlertId,
              returnMode: "previous_layer",
              returnStatus: "exact",
            })
          : null;
  const dashboardClearFocusHref = hasDashboardReturnContext && dashboardHasAnyFocus
    ? buildDashboardReturnHref({
        grain: dashboardGrain,
        selectedDate: dashboardSelectedDate,
        alertId: dashboardAlertId,
        returnMode: "clear_focus",
        returnStatus: "exact",
      })
    : null;
  const legacyDashboardReturnHref = !hasDashboardReturnContext && hasFocusContext && focusAlertId && dateEnd
    ? buildDashboardReturnHref({
        grain: "day",
        selectedDate: dateEnd,
        alertId: focusAlertId,
        groupName: groupName || undefined,
        focusQueueName: queueName || undefined,
        focusJoinKeyType: focusJoinKeyType || undefined,
        returnMode: "legacy_fallback",
        returnStatus: "legacy_fallback",
        returnReason: "missing_dashboard_context",
      })
    : null;
  const dashboardLayerLabel = getRestoreLayerLabel({
    groupName: dashboardGroupName || undefined,
    focusQueueName: dashboardFocusQueueName || undefined,
    focusJoinKeyType: dashboardFocusJoinKeyType || undefined,
  });
  const currentLayerLabel = getRestoreLayerLabel({
    groupName: groupName || undefined,
    focusQueueName: queueName || undefined,
    focusJoinKeyType: focusJoinKeyType || undefined,
  });
  const previousLayerActionLabel = getPreviousLayerActionLabel({
    groupName: dashboardGroupName || groupName || undefined,
    focusQueueName: dashboardFocusQueueName || queueName || undefined,
    focusJoinKeyType: dashboardFocusJoinKeyType || focusJoinKeyType || undefined,
  });
  const detailEntryModeLabel = getEntryModeLabel(Boolean(groupName || queueName || focusJoinKeyType));
  const dashboardEntryModeLabel = getEntryModeLabel(dashboardHasAnyFocus);
  const dashboardReturnSummary = !hasDashboardReturnContext
    ? ""
    : dashboardHasAnyFocus
      ? `返回首页时会恢复到 ${dashboardLayerLabel}。这次进入属于${dashboardEntryModeLabel}；如果这层太细，直接点“${previousLayerActionLabel}”，或者点“彻底清空聚焦”只保留当前告警详情。`
      : `返回首页时会恢复到 ${dashboardLayerLabel}。这次进入属于${dashboardEntryModeLabel}，也就是只保留当前告警详情，不会额外锁定组别 / 队列 / 主键类型。`;
  const legacyDashboardReturnSummary = !legacyDashboardReturnHref
    ? ""
    : queueName
      ? `这是一条旧的系统级告警明细链接，缺少首页返回态参数。首页会按当前明细范围尽量恢复到 ${groupName || "目标组别"} / ${queueName}，但粒度会降级为日监控，锚点日期改用当前结束日期 ${dateEnd}。`
      : groupName
        ? `这是一条旧的系统级告警明细链接，缺少首页返回态参数。首页会按当前明细范围尽量恢复到 ${groupName} 的 scoped 视图，但粒度会降级为日监控，锚点日期改用当前结束日期 ${dateEnd}。`
        : focusJoinKeyType
          ? `这是一条旧的系统级告警明细链接，缺少首页返回态参数。首页会尽量恢复到按主键类型“${focusJoinKeyType}”展开后的 global 视图，但粒度会降级为日监控，锚点日期改用当前结束日期 ${dateEnd}。`
          : `这是一条旧的系统级告警明细链接，缺少首页返回态参数。首页只能按当前结束日期 ${dateEnd} 尽量恢复这条告警，不会再静默回到默认首页。`;
  const dashboardReturnPills = hasDashboardReturnContext
    ? [
        `返回粒度：${dashboardGrain}`,
        `返回日期：${dashboardSelectedDate}`,
        `返回 alert_id：${dashboardAlertId}`,
        `进入方式：${dashboardEntryModeLabel}`,
        `首页层级：${dashboardLayerLabel}`,
        dashboardPreviousLayerHref ? `回退动作：${previousLayerActionLabel}` : null,
      ].filter((item): item is string => Boolean(item))
    : [];
  const focusScopeLabel = getAlertSampleScopeLabel(focusScope);
  const focusSemanticCards = hasFocusContext
    ? [
        {
          key: "layer",
          title: "首页当前层级",
          body: currentLayerLabel,
        },
        {
          key: "entry",
          title: "本次进入方式",
          body: detailEntryModeLabel,
        },
        {
          key: "filter-contract",
          title: "明细过滤口径",
          body: focusJoinKeyType
            ? `主键类型“${focusJoinKeyType}”只保留为联动说明；当前明细结果仍以表单里的组别 / 队列 / 错误类型筛选为准。`
            : "当前明细结果以表单里的组别 / 队列 / 错误类型筛选为准；首页联动说明不会偷偷改成后端硬过滤。",
        },
      ]
    : [];
  const focusContextSummary = hasFocusContext
    ? queueName
      ? `这次属于${detailEntryModeLabel}：你是从首页系统级告警先聚焦到 ${groupName || "目标组别"} / ${queueName}，再带着 scoped 条件跳进明细页的。`
      : groupName
        ? `这次属于${detailEntryModeLabel}：你是从首页系统级告警先聚焦到 ${groupName}，再带着 scoped 条件跳进明细页的。`
        : `这次属于${detailEntryModeLabel}：你是从首页系统级告警的 ${focusScopeLabel} 直接跳进明细页的，当前还没有继续锁定到组别 / 队列。`
    : "";
  const focusContextPills = hasFocusContext
    ? [
        `来源：${focusAlertRuleName || focusAlertId || "系统级告警"}`,
        `首页视图：${focusScopeLabel}`,
        `进入方式：${detailEntryModeLabel}`,
        `首页层级：${currentLayerLabel}`,
        groupName ? `组别：${groupName}` : null,
        queueName ? `队列：${queueName}` : null,
        focusJoinKeyType ? `主键类型：${focusJoinKeyType}` : null,
      ].filter((item): item is string => Boolean(item))
    : [];

  const detailPath = `/api/v1/details/query?date_start=${encodeURIComponent(dateStart)}&date_end=${encodeURIComponent(dateEnd)}&group_name=${encodeURIComponent(groupName)}&queue_name=${encodeURIComponent(queueName)}&reviewer_name=${encodeURIComponent(reviewerName)}&error_type=${encodeURIComponent(errorType)}&issue_filter=${encodeURIComponent(issueFilter)}&only_issues=${onlyIssues ? "true" : "false"}&limit=${encodeURIComponent(limit)}`;
  const queryResult = await safeFetchApi<Record<string, unknown>>(detailPath);

  const queueRows = getRows(filtersResult.data?.queues);
  const reviewerRows = getRows(filtersResult.data?.reviewer_by_group);
  const filteredQueues = groupName ? queueRows.filter((row) => row.group_name === groupName) : queueRows;
  const filteredReviewers = groupName ? reviewerRows.filter((row) => row.group_name === groupName) : reviewerRows;
  const rows = getRows(queryResult.data?.rows);
  const returnedCount = toNumber(queryResult.data?.returned_count ?? queryResult.data?.row_count);
  const totalCount = toNumber(queryResult.data?.total_count ?? queryResult.data?.row_count);
  const previewRowCap = Math.max(toNumber(queryResult.data?.preview_row_cap) || 50, 1);
  const exportRowCap = Math.max(toNumber(queryResult.data?.export_row_cap) || 50000, 1);
  const exportExpectedCount = Math.max(toNumber(queryResult.data?.export_expected_count) || Math.min(totalCount, exportRowCap), 0);
  const queryIsTruncated = Boolean(queryResult.data?.is_truncated);
  const exportWillTruncate = Boolean(queryResult.data?.export_will_truncate);
  const exportPath = `/api/v1/details/export?date_start=${encodeURIComponent(dateStart)}&date_end=${encodeURIComponent(dateEnd)}&group_name=${encodeURIComponent(groupName)}&queue_name=${encodeURIComponent(queueName)}&reviewer_name=${encodeURIComponent(reviewerName)}&error_type=${encodeURIComponent(errorType)}&issue_filter=${encodeURIComponent(issueFilter)}&only_issues=${onlyIssues ? "true" : "false"}&export_limit=${encodeURIComponent(String(exportRowCap))}`;
  const schemaRows = getRows(schemaResult.data?.columns);
  const defaultVisibleKeys = Array.isArray(schemaResult.data?.default_visible_keys)
    ? (schemaResult.data?.default_visible_keys as string[])
    : ["业务日期", "组别", "队列", "审核人", "内容类型", "原始判断", "最终判断", "错判", "漏判", "申诉改判", "错误类型", "备注", "质检时间"];
  const schemaMap = new Map(schemaRows.map((row) => [pickText(row.key, ""), row]));
  const resultColumns = defaultVisibleKeys.map((key) => ({
    key,
    label: pickText(schemaMap.get(key)?.label, key),
    sortable: ["业务日期", "质检时间", "审核人", "内容类型", "错误类型"].includes(key),
  }));
  const resultCellBuilders: Record<string, (row: Record<string, unknown>) => ReactNode> = {};
  for (const key of defaultVisibleKeys) {
    if (key === "业务日期") {
      resultCellBuilders[key] = (row) => toDisplayDate(row[key] as string | undefined);
    } else if (key === "质检时间") {
      resultCellBuilders[key] = (row) => formatDateTime(row[key]);
    }
  }
  const exportHref = `${getApiBaseUrl()}${exportPath}`;
  const previewRows = rows.slice(0, previewRowCap);
  const exportButtonLabel = exportWillTruncate ? `导出当前筛选结果 CSV（最多 ${exportRowCap.toLocaleString("zh-CN")} 行）` : `导出当前筛选结果 CSV（预计 ${exportExpectedCount.toLocaleString("zh-CN")} 行）`;
  const detailTableSubtitle = queryIsTruncated
    ? `当前命中 ${totalCount.toLocaleString("zh-CN")} 行，接口先按“返回上限”返回 ${returnedCount.toLocaleString("zh-CN")} 行；页面只预览前 ${previewRowCap} 行，导出单独按最多 ${exportRowCap.toLocaleString("zh-CN")} 行处理。`
    : `当前命中 ${totalCount.toLocaleString("zh-CN")} 行；页面只预览前 ${previewRowCap} 行，导出单独按最多 ${exportRowCap.toLocaleString("zh-CN")} 行处理。`;
  const detailEmptyText = hasFocusContext
    ? queueName
      ? `这次是从系统级告警聚焦到 ${groupName || "目标组别"} / ${queueName} 后带着筛选进来的，但当前日期范围下没有命中明细。可以放宽日期、清空队列，或回首页重新看全局样本分布。`
      : groupName
        ? `这次是从系统级告警聚焦到 ${groupName} 后带着筛选进来的，但当前日期范围下没有命中明细。可以放宽日期范围，或回首页清空快速聚焦重新判断集中点。`
        : "这次是从系统级告警的 global 样本直接跳过来的，但当前筛选条件下没有命中明细。可以先补组别 / 队列筛选，再继续放大。"
    : "当前筛选条件下暂无明细。";
  const errors = [metaResult.error, filtersResult.error, schemaResult.error, queryResult.error].filter(Boolean);

  return (
    <AppShell
      currentPath="/details"
      title="明细查询"
      subtitle="按日期、组别、队列、审核人筛选质检明细，支持导出和字段说明"
    >
      {errors.length > 0 ? <div className="error-banner">接口异常：{errors.join("；")}</div> : null}

      {hasDashboardReturnContext ? (
        <section className="panel subtle-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">返回首页与状态恢复</h3>
              <p className="panel-subtitle">这次从首页跳进来的告警链路已经被完整记住；动作名称现在和首页保持同一套说法：返回首页当前告警 / {previousLayerActionLabel}{dashboardClearFocusHref ? " / 彻底清空聚焦" : ""}。</p>
            </div>
            <div className="hero-actions">
              <Link className="link-button primary" href={dashboardReturnHref}>
                返回首页当前告警
              </Link>
              {dashboardPreviousLayerHref ? (
                <Link className="link-button" href={dashboardPreviousLayerHref}>
                  {previousLayerActionLabel}
                </Link>
              ) : null}
              {dashboardClearFocusHref ? (
                <Link className="link-button" href={dashboardClearFocusHref}>
                  彻底清空聚焦
                </Link>
              ) : null}
            </div>
          </div>
          <div className="section-stack">
            <div>{dashboardReturnSummary}</div>
            <div className="kpi-row">
              {dashboardReturnPills.map((item) => (
                <span key={item} className="kpi-pill">{item}</span>
              ))}
            </div>
            {dashboardHasScopedFocus ? (
              <div className="inline-note">
                “{previousLayerActionLabel}”只会退掉最内层的 scoped 条件；“彻底清空聚焦”则会一次性清掉组别 / 队列 / 主键类型，只保留当前告警详情。
              </div>
            ) : dashboardHasAnyFocus ? (
              <div className="inline-note">
                当前只带了主键类型聚焦；“{previousLayerActionLabel}”和“彻底清空聚焦”都会回到不带类型展开的原始告警详情。
              </div>
            ) : null}
          </div>
        </section>
      ) : legacyDashboardReturnHref ? (
        <section className="panel subtle-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">返回首页（旧链接降级恢复）</h3>
              <p className="panel-subtitle">这条明细链接缺少 v10 之后新增的首页返回态参数，所以这里不再静默把你送回默认首页，而是先把可恢复的部分讲清楚。</p>
            </div>
            <div className="hero-actions">
              <Link className="link-button primary" href={legacyDashboardReturnHref}>
                按当前范围返回首页
              </Link>
            </div>
          </div>
          <div className="section-stack">
            <div>{legacyDashboardReturnSummary}</div>
            <div className="kpi-row">
              <span className="kpi-pill">恢复方式：旧链接降级恢复</span>
              <span className="kpi-pill">恢复 alert_id：{focusAlertId}</span>
              {groupName ? <span className="kpi-pill">当前组别：{groupName}</span> : null}
              {queueName ? <span className="kpi-pill">当前队列：{queueName}</span> : null}
              {focusJoinKeyType ? <span className="kpi-pill">当前主键类型：{focusJoinKeyType}</span> : null}
            </div>
            <div className="inline-note">
              这不是精确恢复，只是避免旧链接直接把你丢回默认首页；如果回去后这条告警已经不在当前日期里，再从首页告警列表重新进入即可。
            </div>
          </div>
        </section>
      ) : null}

      {hasFocusContext ? (
        <section className="panel subtle-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">来自系统级告警的联动说明</h3>
              <p className="panel-subtitle">这块开始和首页彻底对齐：同样讲清楚当前层级、进入方式，以及哪些只是联动语义、哪些才会真的变成明细过滤。</p>
            </div>
          </div>
          <div className="section-stack">
            <div>{focusContextSummary}</div>
            <div className="kpi-row">
              {focusContextPills.map((item) => (
                <span key={item} className="kpi-pill">{item}</span>
              ))}
            </div>
            {focusSemanticCards.length > 0 ? (
              <div className="semantic-card-list">
                {focusSemanticCards.map((card) => (
                  <div key={card.key} className="semantic-card">
                    <div className="semantic-card-title">{card.title}</div>
                    <div className="semantic-card-body">{card.body}</div>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="inline-note">
              首页的“二次回看变化对比”负责判断当前路径还准不准；明细页这块只负责把语义收口清楚，并继续沿用同一套动作名称：返回首页当前告警 / {previousLayerActionLabel}{hasDashboardReturnContext && dashboardClearFocusHref ? " / 彻底清空聚焦" : ""}。
            </div>
            {hasDashboardReturnContext ? (
              <div className="inline-note">
                如果这次在明细里只是为了确认问题规模，不想丢掉首页当前视角，直接用上面的“返回首页当前告警”或“{previousLayerActionLabel}”就行，不需要重新手动拼参数。
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <CollapsiblePanel
        title="查询条件"
        subtitle="按日期、组别、队列、审核人筛选质检明细；展开调整筛选。"
        defaultOpen={false}
        summary={
          <span>
            {dateStart} ~ {dateEnd}
            {groupName ? ` · 组别: ${groupName}` : ""}
            {queueName ? ` · 队列: ${queueName}` : ""}
            {reviewerName ? ` · 审核人: ${reviewerName}` : ""}
            {errorType ? ` · 错误: ${errorType}` : ""}
            {onlyIssues ? " · 仅问题样本" : ""}
          </span>
        }
      >
        {dateWindowIssue ? (
          <div
            className="info-banner"
            role="status"
            style={{ background: "#fef3c7", color: "#92400e" }}
          >
            ⚠️ {dateWindowIssue.message}
          </div>
        ) : null}
        <form className="section-stack">
          {hasFocusContext ? <input type="hidden" name="focus_source" value={focusSource} /> : null}
          {hasFocusContext ? <input type="hidden" name="focus_scope" value={focusScope} /> : null}
          {hasFocusContext ? <input type="hidden" name="focus_alert_id" value={focusAlertId} /> : null}
          {hasFocusContext ? <input type="hidden" name="focus_alert_rule_name" value={focusAlertRuleName} /> : null}
          {hasFocusContext && focusJoinKeyType ? <input type="hidden" name="focus_join_key_type" value={focusJoinKeyType} /> : null}
          {hasDashboardReturnContext ? <input type="hidden" name="dashboard_grain" value={dashboardGrain} /> : null}
          {hasDashboardReturnContext ? <input type="hidden" name="dashboard_selected_date" value={dashboardSelectedDate} /> : null}
          {hasDashboardReturnContext ? <input type="hidden" name="dashboard_alert_id" value={dashboardAlertId} /> : null}
          {hasDashboardReturnContext && dashboardGroupName ? <input type="hidden" name="dashboard_group_name" value={dashboardGroupName} /> : null}
          {hasDashboardReturnContext && dashboardFocusQueueName ? <input type="hidden" name="dashboard_focus_queue_name" value={dashboardFocusQueueName} /> : null}
          {hasDashboardReturnContext && dashboardFocusJoinKeyType ? <input type="hidden" name="dashboard_focus_join_key_type" value={dashboardFocusJoinKeyType} /> : null}
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="date_start">开始日期</label>
              <input id="date_start" name="date_start" type="date" className="input" defaultValue={dateStart} min={minDate} max={maxDate} />
            </div>
            <div className="form-field">
              <label htmlFor="date_end">结束日期</label>
              <input id="date_end" name="date_end" type="date" className="input" defaultValue={dateEnd} min={minDate} max={maxDate} />
            </div>
            <div className="form-field">
              <label htmlFor="group_name">组别</label>
              <select id="group_name" name="group_name" className="select" defaultValue={groupName}>
                <option value="">全部组别</option>
                {(Array.isArray(filtersResult.data?.groups) ? (filtersResult.data?.groups as string[]) : []).map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="queue_name">队列</label>
              <select id="queue_name" name="queue_name" className="select" defaultValue={queueName}>
                <option value="">全部队列</option>
                {filteredQueues.map((item, index) => {
                  const value = pickText(item.queue_name, "");
                  return value ? <option key={`${value}-${index}`} value={value}>{value}</option> : null;
                })}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="reviewer_name">审核人</label>
              <select id="reviewer_name" name="reviewer_name" className="select" defaultValue={reviewerName}>
                <option value="">全部审核人</option>
                {filteredReviewers.map((item, index) => {
                  const value = pickText(item.reviewer_name, "");
                  return value ? <option key={`${value}-${index}`} value={value}>{value}</option> : null;
                })}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="error_type">错误类型</label>
              <select id="error_type" name="error_type" className="select" defaultValue={errorType}>
                <option value="">全部错误类型</option>
                {(Array.isArray(filtersResult.data?.error_types) ? (filtersResult.data?.error_types as string[]) : []).map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="issue_filter">问题类型</label>
              <select id="issue_filter" name="issue_filter" className="select" defaultValue={issueFilter}>
                {(Array.isArray(filtersResult.data?.issue_filter_options)
                  ? (filtersResult.data?.issue_filter_options as string[])
                  : ["全部问题", "原始错误", "最终错误", "错判", "漏判", "申诉改判"]).map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="limit">返回上限</label>
              <select id="limit" name="limit" className="select" defaultValue={limit}>
                {(Array.isArray(filtersResult.data?.limit_options)
                  ? (filtersResult.data?.limit_options as number[])
                  : [2000, 5000, 10000, 20000]).map((item) => (
                  <option key={item} value={String(item)}>{item}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-actions">
            <label className="kpi-pill">
              <input type="checkbox" name="only_issues" value="true" defaultChecked={onlyIssues} style={{ marginRight: 8 }} />
              只看问题样本
            </label>
            <FilterActionsBar
              submitLabel="查询明细"
              basePath="/details"
              resetQueryString={`date_start=${encodeURIComponent(dateStart)}&date_end=${encodeURIComponent(dateEnd)}`}
              defaultDateStart={dateStart}
              defaultDateEnd={dateEnd}
              resettableFieldNames={[
                "group_name",
                "queue_name",
                "reviewer_name",
                "error_type",
                "issue_filter",
                "limit",
                "only_issues",
              ]}
              extras={(
                <>
                  <ExportButton href={exportHref} label={exportButtonLabel} dataRole="details-export" />
                  <a className="button" href="#detail-field-schema">查看字段说明</a>
                </>
              )}
            />
          </div>
        </form>
      </CollapsiblePanel>

      <div className="grid grid-4">
        <SummaryCard label="当前命中总数" value={totalCount} hint="按当前筛选条件命中的真实总行数。" tone={queryIsTruncated ? "warning" : "success"} />
        <SummaryCard label="接口返回行数" value={returnedCount} hint={queryIsTruncated ? `当前被“返回上限 ${limit}”截断，页面只拿到了前 ${returnedCount} 行。` : "当前筛选结果已全部返回给页面。"} />
        <SummaryCard label="页面预览行数" value={previewRows.length} hint={`页面固定先看前 ${previewRowCap} 行，避免长表首屏过重。`} />
        <SummaryCard label="CSV 导出范围" value={exportExpectedCount} hint={exportWillTruncate ? `当前命中超过导出安全上限，CSV 最多导出 ${exportRowCap.toLocaleString("zh-CN")} 行。` : "当前筛选结果可完整进入本次 CSV 导出。"} tone={exportWillTruncate ? "warning" : "success"} />
      </div>

      <DataTable
        title="明细结果"
        subtitle={detailTableSubtitle}
        rows={buildTableRows(previewRows, resultCellBuilders)}
        columns={resultColumns}
        emptyText={detailEmptyText}
        searchable
      />

      <DataTable
        title="字段说明"
        subtitle="这里把导出列的口径直接公开出来，避免前端展示、接口返回和线下导出三套口径漂移。"
        rows={buildTableRows(schemaRows, {
          default_visible: (row) => (row.default_visible ? "是" : "否（仅导出/补充排查）"),
        })}
        columns={[
          { key: "label", label: "字段名", sortable: true },
          { key: "key", label: "结果列名", sortable: true },
          { key: "source", label: "来源字段" },
          { key: "description", label: "说明" },
          { key: "default_visible", label: "默认展示" },
        ]}
        emptyText="暂无字段说明。"
        paginated={false}
      />

      <section id="detail-field-schema" />
    </AppShell>
  );
}
