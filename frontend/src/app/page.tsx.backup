import Link from "next/link";
import type { Metadata } from "next";

import { AlertBulkPanel } from "@/components/alert-bulk-panel";
import { AlertFilterBar } from "@/components/alert-filter-bar";
import { AlertQuickActions } from "@/components/alert-quick-actions";
import { AppShell } from "@/components/app-shell";
import { BarListCard } from "@/components/bar-list-card";
import { CollapsiblePanel } from "@/components/collapsible-panel";
import { DataTable } from "@/components/data-table";
import { FilterActionsBar } from "@/components/filter-actions-bar";
import { LineChartCard } from "@/components/line-chart-card";
import { StatusChip } from "@/components/status-chip";
import { SummaryCard } from "@/components/summary-card";
import {
  ALERT_GRAIN_OPTIONS,
  ALERT_MODULES_IN_ORDER,
  type AlertGrainLabel,
  type AlertModule,
  grainLabel,
  inferAlertModule,
} from "@/lib/alert-module";
import { safeFetchApi } from "@/lib/api";
import { buildTableRows } from "@/lib/table-rows";
import {
  buildQueryString,
  pickText,
  toDateInputValue,
  toDisplayDate,
  toInteger,
  toNumber,
  toPercent,
} from "@/lib/formatters";
import {
  type FocusComparisonCard,
  buildAlertDetailsHref,
  buildAlertSampleColumns,
  buildDashboardAlertHref,
  buildTopFocusItems,
  buildVisibleFocusItems,
  formatDateTime,
  getAlertSampleScopeLabel,
  getFocusCandidateMetricsText,
  getFocusGapText,
  getFocusItemRank,
  getFocusPanelSummary,
  getRestoreLayerLabel,
  getReturnModeLabel,
  getRows,
  getSeverityTone,
  getStatusTone,
  normalizeFocusValue,
  readMultiParam,
  readParam,
} from "@/lib/dashboard-helpers";

type SearchParams = Record<string, string | string[] | undefined>;

export const metadata: Metadata = {
  title: "首页总览",
};

type PageProps = {
  searchParams?: Promise<SearchParams>;
};

export default async function DashboardPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const metaResult = await safeFetchApi<Record<string, unknown>>("/api/v1/meta/date-range");
  const defaultSelectedDate = toDateInputValue(
    (metaResult.data?.default_selected_date as string | undefined) ||
      (metaResult.data?.max_date as string | undefined),
  );
  const selectedDate = readParam(params.selected_date) || defaultSelectedDate;
  const grain = readParam(params.grain) || (metaResult.data?.default_grain as string | undefined) || "day";
  const groupName = readParam(params.group_name);
  const alertId = readParam(params.alert_id);
  const focusQueueName = readParam(params.focus_queue_name);
  const focusJoinKeyType = readParam(params.focus_join_key_type);
  const demoFixture = readParam(params.demo_fixture) || "";
  const returnSource = readParam(params.return_source) || "";
  const returnMode = readParam(params.return_mode) || "";
  const returnStatus = readParam(params.return_status) || "";
  const returnReason = readParam(params.return_reason) || "";
  const returnAlertId = readParam(params.return_alert_id) || alertId || "";
  const returnGroupName = readParam(params.return_group_name) || groupName || "";
  const returnFocusQueueName = readParam(params.return_focus_queue_name) || focusQueueName || "";
  const returnFocusJoinKeyType = readParam(params.return_focus_join_key_type) || focusJoinKeyType || "";
  const returnedFromDetails = returnSource === "details";

  const overviewApiPath = `/api/v1/dashboard/overview${buildQueryString({
    grain,
    selected_date: selectedDate,
    demo_fixture: demoFixture || undefined,
  })}`;
  const alertsApiPath = `/api/v1/dashboard/alerts${buildQueryString({
    grain,
    selected_date: selectedDate,
    demo_fixture: demoFixture || undefined,
  })}`;
  const alertDetailApiPath = alertId
    ? `/api/v1/dashboard/alerts/${encodeURIComponent(alertId)}${buildQueryString({
        grain,
        selected_date: selectedDate,
        demo_fixture: demoFixture || undefined,
      })}`
    : null;

  const [overviewResult, alertsResult, alertDetailResult, healthResult] = await Promise.all([
    safeFetchApi<Record<string, unknown>>(overviewApiPath),
    safeFetchApi<Record<string, unknown>>(alertsApiPath),
    alertDetailApiPath
      ? safeFetchApi<Record<string, unknown>>(alertDetailApiPath)
      : Promise.resolve({ data: null, error: null }),
    // 首页健康度胶囊：看后端 router 加载状态 + 数仓新鲜度
    safeFetchApi<Record<string, unknown>>("/api/health"),
  ]);

  // ===== 数仓健康度 & 新人路由状态（首页右上角一眼能看到）=====
  const warehouseMaxDate =
    pickText(metaResult.data?.max_date) || pickText(metaResult.data?.end);
  // 用首页锚点日期作为"今天"的代表，避免在 render 里调 Date.now()（对齐 react-hooks/purity）。
  // 场景上也合适：首页关注的就是这个锚点日期对应的数据链路是否齐。
  const warehouseDiffDays = (() => {
    if (!warehouseMaxDate || !selectedDate) return null;
    const max = new Date(`${warehouseMaxDate}T00:00:00`).getTime();
    const anchor = new Date(`${selectedDate}T00:00:00`).getTime();
    if (!Number.isFinite(max) || !Number.isFinite(anchor)) return null;
    return Math.floor((anchor - max) / (1000 * 60 * 60 * 24));
  })();
  const warehouseFreshnessTone: "success" | "warning" | "danger" | "neutral" =
    warehouseDiffDays === null
      ? "neutral"
      : warehouseDiffDays <= 1
        ? "success"
        : warehouseDiffDays <= 3
          ? "warning"
          : "danger";
  const warehouseFreshnessLabel =
    warehouseDiffDays === null
      ? "未知"
      : warehouseDiffDays <= 0
        ? "今日已到"
        : warehouseDiffDays === 1
          ? "滞后 1 天"
          : `滞后 ${warehouseDiffDays} 天`;
  const healthRouters = (healthResult.data?.routers as Record<string, unknown> | undefined) || {};
  const newcomersReady = healthRouters.newcomers === true;
  const newcomersLoadError = pickText(healthResult.data?.newcomers_load_error, "");
  const newcomersRouterTone: "success" | "danger" = newcomersReady ? "success" : "danger";
  const newcomersRouterLabel = newcomersReady ? "已挂载" : "未挂载";

  const groupRows = getRows(overviewResult.data?.group_df);
  const groupDisplayRows = getRows(overviewResult.data?.group_display_df).length > 0
    ? getRows(overviewResult.data?.group_display_df)
    : groupRows;
  const alertsPayload = alertsResult.data || {};
  const alertSummary = ((demoFixture ? alertsPayload.summary : overviewResult.data?.alert_summary) as Record<string, unknown> | undefined)
    || (alertsPayload.summary as Record<string, unknown> | undefined)
    || {};
  const alertActions = Array.isArray(demoFixture ? alertsPayload.actions : overviewResult.data?.alert_actions)
    ? ((demoFixture ? alertsPayload.actions : overviewResult.data?.alert_actions) as string[])
    : Array.isArray(alertsPayload.actions)
      ? (alertsPayload.actions as string[])
      : [];
  const cockpit = (overviewResult.data?.cockpit as Record<string, unknown> | undefined) || {};
  const alertItems = getRows(alertsPayload.items);
  const statusSummary = (alertsPayload.status_summary as Record<string, unknown> | undefined) || {};
  const slaSummary = (alertsPayload.sla_summary as Record<string, unknown> | undefined) || {};

  // ===== 告警筛选器（等级 / 模块 / 粒度 / 状态），和 Streamlit 口径一致 =====
  const SEVERITY_KEYS = ["P0", "P1", "P2"] as const;
  type SeverityKey = (typeof SEVERITY_KEYS)[number];
  const activeSeverities = readMultiParam(params.alert_sev).filter((s): s is SeverityKey =>
    (SEVERITY_KEYS as readonly string[]).includes(s),
  );
  const activeModules = readMultiParam(params.alert_module).filter((m): m is AlertModule =>
    ALERT_MODULES_IN_ORDER.includes(m as AlertModule),
  );
  const activeGrains = readMultiParam(params.alert_grain).filter((g): g is AlertGrainLabel =>
    (ALERT_GRAIN_OPTIONS as readonly string[]).includes(g),
  );
  const rawStatusFilter = readParam(params.alert_status_filter);
  const activeStatusFilter: "all" | "open" | "resolved" =
    rawStatusFilter === "open" || rawStatusFilter === "resolved" ? rawStatusFilter : "all";

  // 给每条告警派生 module / grain 两个派生字段
  const enrichedAlertItems: Array<Record<string, unknown> & { module: AlertModule; grain_cn: string }> =
    alertItems.map((row) => {
      const moduleLabel = inferAlertModule(pickText(row.target_key, ""), pickText(row.rule_code, ""));
      const grainCn = grainLabel(pickText(row.target_level, ""));
      return { ...row, module: moduleLabel, grain_cn: grainCn };
    });

  // 可筛项只展示数据里真实出现过的（和 Streamlit 行为一致）
  const availableModules = Array.from(
    new Set(enrichedAlertItems.map((row) => row.module as AlertModule)),
  ).filter((m): m is AlertModule => ALERT_MODULES_IN_ORDER.includes(m));
  const availableGrains = Array.from(
    new Set(enrichedAlertItems.map((row) => row.grain_cn as string)),
  ).filter((g): g is AlertGrainLabel =>
    (ALERT_GRAIN_OPTIONS as readonly string[]).includes(g),
  );

  const filteredAlertItems = enrichedAlertItems.filter((row) => {
    if (activeSeverities.length > 0) {
      const sev = pickText(row.severity, "") as SeverityKey;
      if (!activeSeverities.includes(sev)) return false;
    }
    if (activeModules.length > 0 && !activeModules.includes(row.module as AlertModule)) {
      return false;
    }
    if (activeGrains.length > 0 && !activeGrains.includes(row.grain_cn as AlertGrainLabel)) {
      return false;
    }
    if (activeStatusFilter === "open") {
      // alert_status 不是 "resolved" 就视为未解决；旧数据只有 is_resolved 时兼容。
      const status = pickText(row.alert_status, "").toLowerCase();
      const resolved = status === "resolved" || Boolean(toNumber(row.is_resolved));
      if (resolved) return false;
    } else if (activeStatusFilter === "resolved") {
      const status = pickText(row.alert_status, "").toLowerCase();
      const resolved = status === "resolved" || Boolean(toNumber(row.is_resolved));
      if (!resolved) return false;
    }
    return true;
  });

  const totalQa = groupRows.reduce((sum, row) => sum + toNumber(row.qa_cnt), 0);
  const avgFinalAccuracy =
    groupRows.length > 0
      ? groupRows.reduce((sum, row) => sum + toNumber(row.final_accuracy_rate), 0) / groupRows.length
      : 0;

  const selectedAlertDetail = alertDetailResult.data || null;
  const selectedAlertHistory = getRows(selectedAlertDetail?.history);
  const alertTargetLevel = pickText(selectedAlertDetail?.target_level, "").toLowerCase();
  const isSystemAlert = alertTargetLevel === "system";
  const relatedGroupName = pickText(selectedAlertDetail?.group_name, "");
  const effectiveGroupName = groupName || relatedGroupName;
  const focusedQueueName = focusQueueName || pickText(selectedAlertDetail?.queue_name, "");
  const focusedRuleCode = pickText(selectedAlertDetail?.rule_code, "");
  const focusedErrorType = pickText(selectedAlertDetail?.error_type, "");
  const closeAlertHref = buildQueryString({
    grain,
    selected_date: selectedDate,
    group_name: effectiveGroupName || undefined,
    demo_fixture: demoFixture || undefined,
  }) || "/";
  const relatedGroupHref = relatedGroupName
    ? buildDashboardAlertHref({
        grain,
        selectedDate,
        alertId: pickText(selectedAlertDetail?.alert_id, ""),
        groupName: relatedGroupName,
        focusQueueName: focusedQueueName || undefined,
        focusJoinKeyType: focusJoinKeyType || undefined,
        demoFixture: demoFixture || undefined,
      })
    : null;
  const groupDetailHref = effectiveGroupName
    ? `/api/v1/dashboard/group-detail${buildQueryString({
        grain,
        selected_date: selectedDate,
        group_name: effectiveGroupName,
        queue_name: alertId ? focusedQueueName || undefined : undefined,
        focus_rule_code: alertId ? focusedRuleCode || undefined : undefined,
        focus_error_type: alertId ? focusedErrorType || undefined : undefined,
        demo_fixture: demoFixture || undefined,
      })}`
    : null;
  const groupDetailResult = groupDetailHref
    ? await safeFetchApi<Record<string, unknown>>(groupDetailHref)
    : { data: null, error: null };

  const groupAlertSampleRows = getRows(groupDetailResult.data?.alert_sample_df);
  const detailAlertSampleRows = getRows(selectedAlertDetail?.alert_sample_df);
  const detailRows = {
    queues: getRows(groupDetailResult.data?.queue_df),
    auditors: getRows(groupDetailResult.data?.auditor_df),
    samples: getRows(groupDetailResult.data?.sample_df).slice(0, 12),
  };
  const hasScopedAlertSamples = groupAlertSampleRows.length > 0;
  const alertPreviewSourceRows = hasScopedAlertSamples ? groupAlertSampleRows : detailAlertSampleRows;
  const alertSampleScope = hasScopedAlertSamples
    ? "scoped"
    : pickText(selectedAlertDetail?.alert_sample_scope, detailAlertSampleRows.length > 0 ? "global" : "");
  const alertScopeLabel = getAlertSampleScopeLabel(alertSampleScope);
  const activeJoinKeyType = normalizeFocusValue(focusJoinKeyType);
  const filteredAlertPreviewSourceRows = activeJoinKeyType
    ? alertPreviewSourceRows.filter((row) => normalizeFocusValue(row.join_key_type) === activeJoinKeyType)
    : alertPreviewSourceRows;
  const alertPreviewRows = filteredAlertPreviewSourceRows.slice(0, 8);
  const alertSampleTitle = hasScopedAlertSamples
    ? pickText(groupDetailResult.data?.alert_sample_title, "告警关联样本")
    : pickText(selectedAlertDetail?.alert_sample_title, "告警关联样本");
  const alertSampleSubtitle = hasScopedAlertSamples
    ? focusedQueueName
      ? `当前已经从全局告警样本收窄到 ${effectiveGroupName || '目标组别'} / ${focusedQueueName}，这 8 条就是最值得先看的关联样本。`
      : "这块直接复用 group-detail 返回的 alert_sample_df，先把最关键的 8 条样本放回首页详情面板。"
    : activeJoinKeyType
      ? `当前全局样本已按主键类型"${activeJoinKeyType}"展开，先看该类型下最关键的 8 条异常样本。`
      : pickText(
          selectedAlertDetail?.alert_sample_hint,
          "系统级告警没有组别上下文时，这里会直接回全局范围抓样本，先看问题集中在哪些组别 / 队列。",
        );
  const alertSampleColumns = buildAlertSampleColumns(alertPreviewRows);
  const systemAlertFocusSummary = !selectedAlertDetail || !isSystemAlert
    ? ""
    : hasScopedAlertSamples
      ? focusedQueueName
        ? `这条系统级告警已经从全局样本收窄到 ${effectiveGroupName || "目标组别"} / ${focusedQueueName}。首页现在展示的是 scoped 样本，适合先判断问题是不是仍集中在这个队列。`
        : `这条系统级告警已经从全局样本收窄到 ${effectiveGroupName || "目标组别"}。首页现在展示的是 scoped 样本，适合先判断这个组别是否值得继续深挖。`
      : activeJoinKeyType
        ? `这条系统级告警当前仍停留在 global 样本，但已经按主键类型"${activeJoinKeyType}"展开。先判断是不是某一种关联主键路由的结构性问题，再决定要不要收窄到组别 / 队列。`
        : "这条系统级告警当前仍停留在 global 样本。先看问题集中在哪些组别 / 队列，再决定是否收窄到 scoped 样本或直接跳去明细查询。";
  const restoreStageLabel = returnedFromDetails ? "二次回看" : "首次排查";
  const systemAlertFocusPills = [
    `来源告警：${pickText(selectedAlertDetail?.rule_name, "系统级告警")}`,
    `当前视图：${alertScopeLabel}`,
    `排查阶段：${restoreStageLabel}`,
    effectiveGroupName ? `组别：${effectiveGroupName}` : null,
    focusedQueueName ? `队列：${focusedQueueName}` : null,
    activeJoinKeyType ? `主键类型：${activeJoinKeyType}` : null,
  ].filter((item): item is string => Boolean(item));
  const selectedAlertDetailHref = selectedAlertDetail
    ? buildAlertDetailsHref(selectedAlertDetail, {
        groupName: effectiveGroupName || undefined,
        queueName: focusedQueueName || undefined,
        focusSource: isSystemAlert ? "system_alert" : undefined,
        focusScope: isSystemAlert ? (hasScopedAlertSamples ? "scoped" : alertSampleScope || undefined) : undefined,
        focusJoinKeyType: isSystemAlert ? activeJoinKeyType || undefined : undefined,
        focusAlertId: isSystemAlert ? pickText(selectedAlertDetail.alert_id, "") : undefined,
        focusAlertRuleName: isSystemAlert ? pickText(selectedAlertDetail.rule_name, "") : undefined,
        dashboardGrain: grain,
        dashboardSelectedDate: selectedDate,
        dashboardAlertId: pickText(selectedAlertDetail.alert_id, ""),
        dashboardGroupName: effectiveGroupName || undefined,
        dashboardFocusQueueName: focusedQueueName || undefined,
        dashboardFocusJoinKeyType: activeJoinKeyType || undefined,
        demoFixture: demoFixture || undefined,
        dashboardDemoFixture: demoFixture || undefined,
      })
    : "/details";
  const returnedLayerLabel = getRestoreLayerLabel({
    groupName: returnGroupName || effectiveGroupName || undefined,
    focusQueueName: returnFocusQueueName || focusedQueueName || undefined,
    focusJoinKeyType: returnFocusJoinKeyType || activeJoinKeyType || undefined,
  });
  const relocalizeAlertId = returnAlertId || pickText(selectedAlertDetail?.alert_id, "") || alertId || "";
  const relocalizeCurrentAlertHref = relocalizeAlertId
    ? buildDashboardAlertHref({
        grain,
        selectedDate,
        alertId: relocalizeAlertId,
        demoFixture: demoFixture || undefined,
      })
    : buildQueryString({ grain, selected_date: selectedDate, demo_fixture: demoFixture || undefined }) || "/";
  const currentAlertLinkId = pickText(selectedAlertDetail?.alert_id, "") || relocalizeAlertId || alertId || "";
  const clearQuickFocusHref = buildDashboardAlertHref({
    grain,
    selectedDate,
    alertId: currentAlertLinkId || undefined,
    demoFixture: demoFixture || undefined,
  });
  const alertListHref = buildQueryString({ grain, selected_date: selectedDate, demo_fixture: demoFixture || undefined }) || "/";
  const returnModeLabel = getReturnModeLabel(returnMode, returnStatus === "legacy_fallback");
  const returnedFromDetailsSummary = !returnedFromDetails
    ? ""
    : returnStatus === "legacy_fallback"
      ? `这次是从明细页旧链接降级回来的。首页已经尽量恢复到 ${returnedLayerLabel}，但原始返回态不完整，粒度/日期可能已经按当前明细范围回退。`
      : returnMode === "previous_layer"
        ? `你刚从明细页回退了一层，首页当前恢复的是 ${returnedLayerLabel}。如果还想继续放大，直接沿着下面的快速聚焦入口往下走就行。`
        : returnMode === "clear_focus"
          ? "你刚从明细页清空了系统级快速聚焦。首页现在只保留当前告警详情，便于重新判断问题集中点。"
          : `你刚从明细页返回，首页已经恢复到 ${returnedLayerLabel}。当前告警、组别 / 队列和主键类型会按刚才的返回动作高亮说明。`;
  const returnedFromDetailsPills = !returnedFromDetails
    ? []
    : [
        `返回方式：${returnModeLabel}`,
        `恢复层级：${returnedLayerLabel}`,
        `当前阶段：${restoreStageLabel}`,
        returnAlertId ? `恢复 alert_id：${returnAlertId}` : null,
        returnGroupName ? `恢复组别：${returnGroupName}` : null,
        returnFocusQueueName ? `恢复队列：${returnFocusQueueName}` : null,
        returnFocusJoinKeyType ? `恢复主键类型：${returnFocusJoinKeyType}` : null,
      ].filter((item): item is string => Boolean(item));
  const returnedFromDetailsWarning = !returnedFromDetails
    ? null
    : alertId && alertDetailResult.error
      ? returnStatus === "legacy_fallback"
        ? `这是旧链接的降级恢复结果：首页已经按当前可用参数尽量回到这条系统级告警，但 alert_id=${returnAlertId || alertId} 在当前粒度/日期下没有命中详情。建议先关闭详情，再重新从上方告警列表进入。`
        : `明细页想帮你恢复的 alert_id=${returnAlertId || alertId} 在当前粒度/日期下没有命中详情，通常是日期切换或历史链接失效。可以先关闭详情，或直接从上方告警列表重新进入。`
      : returnReason === "missing_dashboard_context"
        ? "这次恢复来自旧链接降级链路；如果你看到的层级不够精确，优先重新从首页告警详情跳一次明细，后续就能走完整返回态。"
        : null;
  const showQuickFocusSection = Boolean(selectedAlertDetail && isSystemAlert && detailAlertSampleRows.length > 0);
  const quickFocusPanelSubtitle = hasScopedAlertSamples
    ? "即使首页已经收窄到当前 scoped 样本，这块也继续保留全局候选视角，方便核对这次恢复到底命中了哪个组别 / 队列 / 主键类型。"
    : "这块把全局样本继续往下推一层：先看问题最多的组别 / 队列，再按主键类型展开，然后一键带筛选跳去首页或明细查询。";
  const quickFocusRestoreSummary = !showQuickFocusSection
    ? ""
    : returnedFromDetails
      ? focusedQueueName
        ? `当前属于二次回看，首页已经在"问题最多队列"里恢复并高亮 ${effectiveGroupName || "目标组别"} / ${focusedQueueName}。如果这层太细，直接回上一层组别，或重新定位当前告警重新看 global 分布。`
        : effectiveGroupName
          ? `当前属于二次回看，首页已经在"问题最多组别"里恢复并高亮 ${effectiveGroupName}。如果确认这个组别仍是主战场，可以直接继续跳明细；如果不准，就重新定位当前告警再看全局候选。`
          : activeJoinKeyType
            ? `当前属于二次回看，首页已经在"按主键类型展开"里恢复并高亮 "${activeJoinKeyType}"。如果这层已经过时，清空类型或重新定位当前告警即可。`
            : "当前属于二次回看，但这次只恢复到了告警详情层，还没重新收窄范围。下面仍保留 Top 组别 / 队列 / 主键类型候选，方便你重新定位。"
      : hasScopedAlertSamples
        ? "当前还是首次排查。虽然首页已经收窄到 scoped 样本，这里仍保留全局候选，方便你判断当前下钻是不是还在主战场上。"
        : "当前还是首次排查。先用 Top 组别 / 队列 / 主键类型判断问题集中点，再决定是留在首页继续缩小范围，还是跳明细拉全量。";
  const groupDetailErrorMessage = groupDetailResult.error && alertPreviewRows.length === 0
    ? isSystemAlert && (effectiveGroupName || focusedQueueName)
      ? `当前已经从系统级告警收窄到 ${focusedQueueName ? `${effectiveGroupName || "目标组别"} / ${focusedQueueName}` : effectiveGroupName || "目标组别"}，但 scoped 样本拉取失败：${groupDetailResult.error}。可以先跳去明细查询拉全量，或清空快速聚焦回到 global 样本。`
      : `关联样本拉取失败：${groupDetailResult.error}。通常是当前告警缺少可下钻组别，或该日期下没有命中可预览样本；可以先跳到明细查询继续排查。`
    : null;
  const alertPreviewEmptyMessage = isSystemAlert && activeJoinKeyType && detailAlertSampleRows.length > 0 && filteredAlertPreviewSourceRows.length === 0
    ? `当前主键类型"${activeJoinKeyType}"在这条系统级告警的全局样本里已经没有命中记录，通常是旧链接或当天样本已刷新；建议先清空类型后再看全局分布。`
    : isSystemAlert && (effectiveGroupName || focusedQueueName) && detailAlertSampleRows.length > 0 && !hasScopedAlertSamples
      ? focusedQueueName
        ? `当前已经从系统级告警收窄到 ${effectiveGroupName || "目标组别"} / ${focusedQueueName}，但这一层没有命中可预览 scoped 样本。通常说明首页样本量不足；可以直接跳明细查询，或先清空快速聚焦回到 global 样本。`
        : `当前已经从系统级告警收窄到 ${effectiveGroupName || "目标组别"}，但这一层没有命中可预览 scoped 样本。可以先跳明细查询拉全量，或回到 global 样本重新判断问题集中点。`
      : "当前这条告警暂时没有返回可预览样本。组别 / 队列告警会优先走当前下钻范围，系统级联表告警则会回退到全局样本；如果这里仍为空，通常说明当天暂无命中记录。";
  const globalFocusBaseRows = activeJoinKeyType
    ? detailAlertSampleRows.filter((row) => normalizeFocusValue(row.join_key_type) === activeJoinKeyType)
    : detailAlertSampleRows;
  const globalGroupFocusItems = buildTopFocusItems(globalFocusBaseRows, (row) => {
    const normalizedGroupName = normalizeFocusValue(row.group_name);
    if (!normalizedGroupName) {
      return null;
    }
    return {
      key: `group:${normalizedGroupName}`,
      label: normalizedGroupName,
      groupName: normalizedGroupName,
    };
  });
  const activeGlobalGroupFocusItem = globalGroupFocusItems.find((item) => item.groupName === effectiveGroupName) || null;
  const visibleGlobalGroupFocusItems = buildVisibleFocusItems(
    globalGroupFocusItems,
    (item) => item.groupName === effectiveGroupName,
  );
  const globalGroupFocusSummary = getFocusPanelSummary({
    dimensionLabel: "组别候选",
    topItem: globalGroupFocusItems[0],
    activeItem: activeGlobalGroupFocusItem,
    returnedFromDetails,
  });
  const globalQueueFocusItems = buildTopFocusItems(globalFocusBaseRows, (row) => {
    const normalizedGroupName = normalizeFocusValue(row.group_name);
    const normalizedQueueName = normalizeFocusValue(row.queue_name);
    if (!normalizedGroupName || !normalizedQueueName) {
      return null;
    }
    return {
      key: `queue:${normalizedGroupName}:${normalizedQueueName}`,
      label: `${normalizedGroupName} / ${normalizedQueueName}`,
      groupName: normalizedGroupName,
      queueName: normalizedQueueName,
    };
  });
  const activeGlobalQueueFocusItem =
    globalQueueFocusItems.find((item) => item.groupName === effectiveGroupName && item.queueName === focusedQueueName) || null;
  const visibleGlobalQueueFocusItems = buildVisibleFocusItems(
    globalQueueFocusItems,
    (item) => item.groupName === effectiveGroupName && item.queueName === focusedQueueName,
  );
  const globalQueueFocusSummary = getFocusPanelSummary({
    dimensionLabel: "队列候选",
    topItem: globalQueueFocusItems[0],
    activeItem: activeGlobalQueueFocusItem,
    returnedFromDetails,
  });
  const globalJoinKeyTypeItems = buildTopFocusItems(detailAlertSampleRows, (row) => {
    const normalizedJoinKeyType = normalizeFocusValue(row.join_key_type);
    if (!normalizedJoinKeyType) {
      return null;
    }
    return {
      key: `join-key-type:${normalizedJoinKeyType}`,
      label: normalizedJoinKeyType,
      joinKeyType: normalizedJoinKeyType,
    };
  });
  const activeGlobalJoinKeyTypeItem =
    globalJoinKeyTypeItems.find((item) => item.joinKeyType === activeJoinKeyType) || null;
  const visibleGlobalJoinKeyTypeItems = buildVisibleFocusItems(
    globalJoinKeyTypeItems,
    (item) => item.joinKeyType === activeJoinKeyType,
  );
  const globalJoinKeyTypeFocusSummary = getFocusPanelSummary({
    dimensionLabel: "主键类型候选",
    topItem: globalJoinKeyTypeItems[0],
    activeItem: activeGlobalJoinKeyTypeItem,
    returnedFromDetails,
  });
  const globalFocusedSampleCount = globalFocusBaseRows.length;
  const globalFocusedGroupCount = new Set(
    globalFocusBaseRows
      .map((row) => normalizeFocusValue(row.group_name))
      .filter((value): value is string => Boolean(value)),
  ).size;
  const globalFocusedQueueCount = new Set(
    globalFocusBaseRows
      .map((row) => {
        const normalizedGroupName = normalizeFocusValue(row.group_name);
        const normalizedQueueName = normalizeFocusValue(row.queue_name);
        return normalizedGroupName && normalizedQueueName ? `${normalizedGroupName}::${normalizedQueueName}` : null;
      })
      .filter((value): value is string => Boolean(value)),
  ).size;
  const topGroupFocusItem = globalGroupFocusItems[0];
  const topQueueFocusItem = globalQueueFocusItems[0];
  const topJoinKeyTypeFocusItem = globalJoinKeyTypeItems[0];
  const topQueueWithinActiveGroup = effectiveGroupName
    ? globalQueueFocusItems.find((item) => item.groupName === effectiveGroupName) || null
    : null;
  const topQueueWithinActiveGroupShare =
    topQueueWithinActiveGroup && activeGlobalGroupFocusItem && activeGlobalGroupFocusItem.count > 0
      ? topQueueWithinActiveGroup.count / activeGlobalGroupFocusItem.count
      : 0;
  const activeGroupRank = getFocusItemRank(globalGroupFocusItems, activeGlobalGroupFocusItem);
  const activeQueueRank = getFocusItemRank(globalQueueFocusItems, activeGlobalQueueFocusItem);
  const activeJoinKeyTypeRank = getFocusItemRank(globalJoinKeyTypeItems, activeGlobalJoinKeyTypeItem);
  const switchToTopGroupHref = topGroupFocusItem
    ? buildDashboardAlertHref({
        grain,
        selectedDate,
        alertId: currentAlertLinkId || undefined,
        groupName: topGroupFocusItem.groupName,
        focusJoinKeyType: activeJoinKeyType || undefined,
        demoFixture: demoFixture || undefined,
      })
    : relocalizeCurrentAlertHref;
  const switchToTopQueueHref = topQueueFocusItem
    ? buildDashboardAlertHref({
        grain,
        selectedDate,
        alertId: currentAlertLinkId || undefined,
        groupName: topQueueFocusItem.groupName,
        focusQueueName: topQueueFocusItem.queueName,
        focusJoinKeyType: activeJoinKeyType || undefined,
        demoFixture: demoFixture || undefined,
      })
    : relocalizeCurrentAlertHref;
  const switchToTopJoinKeyTypeHref = topJoinKeyTypeFocusItem
    ? buildDashboardAlertHref({
        grain,
        selectedDate,
        alertId: currentAlertLinkId || undefined,
        focusJoinKeyType: topJoinKeyTypeFocusItem.joinKeyType,
        demoFixture: demoFixture || undefined,
      })
    : clearQuickFocusHref;
  const previousLayerHref = focusedQueueName
    ? buildDashboardAlertHref({
        grain,
        selectedDate,
        alertId: currentAlertLinkId || undefined,
        groupName: effectiveGroupName || undefined,
        focusJoinKeyType: activeJoinKeyType || undefined,
        demoFixture: demoFixture || undefined,
      })
    : effectiveGroupName
      ? buildDashboardAlertHref({
          grain,
          selectedDate,
          alertId: currentAlertLinkId || undefined,
          focusJoinKeyType: activeJoinKeyType || undefined,
          demoFixture: demoFixture || undefined,
        })
      : activeJoinKeyType
        ? clearQuickFocusHref
        : relocalizeCurrentAlertHref;
  const hasPreviousLayerAction = Boolean(focusedQueueName || effectiveGroupName || activeJoinKeyType);
  const previousLayerLabel = focusedQueueName
    ? "回上一层组别"
    : effectiveGroupName
      ? "回到 global 候选"
      : activeJoinKeyType
        ? "清空主键类型"
        : "重新定位当前告警";
  const focusComparisonCards: FocusComparisonCard[] = [];
  let focusComparisonSummary = "";
  let focusComparisonPrimaryLabel = "继续当前层查明细";
  let focusComparisonPrimaryHref = selectedAlertDetailHref;
  const focusComparisonPrimaryTone: "primary" | "default" = "primary";
  let focusComparisonDecisionLabel = "继续当前层";

  if (returnedFromDetails && selectedAlertDetail && isSystemAlert && detailAlertSampleRows.length > 0) {
    if (activeJoinKeyType && !activeGlobalJoinKeyTypeItem) {
      focusComparisonDecisionLabel = "主键类型已漂移";
      focusComparisonSummary = topJoinKeyTypeFocusItem
        ? `这次二次回看时，原主键类型"${activeJoinKeyType}"已经没有命中样本；当前更像是样本刷新后主战场切到了"${topJoinKeyTypeFocusItem.label}"。先别死追旧类型，优先切回最新类型或重新定位当前告警。`
        : `这次二次回看时，原主键类型"${activeJoinKeyType}"已经没有命中样本。当前这层更像是旧链路残留，优先清空类型或重新定位当前告警。`;
      focusComparisonPrimaryLabel = topJoinKeyTypeFocusItem ? `切到最新类型：${topJoinKeyTypeFocusItem.label}` : "重新定位当前告警";
      focusComparisonPrimaryHref = topJoinKeyTypeFocusItem ? switchToTopJoinKeyTypeHref : relocalizeCurrentAlertHref;
      focusComparisonCards.push({
        key: "join-key-type-drift",
        tone: "danger",
        title: "主键类型已经漂移",
        summary: topJoinKeyTypeFocusItem
          ? `当前恢复项"${activeJoinKeyType}"已不在候选列表里；最新 Top1 是 "${topJoinKeyTypeFocusItem.label}"（${getFocusCandidateMetricsText(topJoinKeyTypeFocusItem)}）。`
          : `当前恢复项"${activeJoinKeyType}"已不在候选列表里，首页这次只能告诉你这条线已经过时。`,
      });
    } else if (focusedQueueName) {
      if (!activeGlobalQueueFocusItem) {
        focusComparisonDecisionLabel = "原队列已掉出候选";
        focusComparisonSummary = topQueueFocusItem
          ? `这次恢复到了 ${effectiveGroupName || "目标组别"} / ${focusedQueueName}，但它已经不在当前候选里了；最新主战场更偏向 ${topQueueFocusItem.label}。如果你只想保住原路径，可以先回上一层组别；如果要追最新主战场，直接切到新的 Top1。`
          : `这次恢复到了 ${effectiveGroupName || "目标组别"} / ${focusedQueueName}，但它已经不在当前候选里了。优先回上一层组别，或重新定位当前告警重新看全局分布。`;
        focusComparisonPrimaryLabel = topQueueFocusItem ? `切到最新队列：${topQueueFocusItem.label}` : previousLayerLabel;
        focusComparisonPrimaryHref = topQueueFocusItem ? switchToTopQueueHref : previousLayerHref;
        focusComparisonCards.push({
          key: "queue-missing",
          tone: "danger",
          title: "原命中队列已掉出候选",
          summary: `首页保住了返回层级，但 ${effectiveGroupName || "目标组别"} / ${focusedQueueName} 当前已不在最新队列候选里；这更像是主战场已经换掉了。`,
        });
      } else if (topQueueFocusItem && activeGlobalQueueFocusItem.key !== topQueueFocusItem.key) {
        const battlegroundLabel = topQueueFocusItem.groupName === activeGlobalQueueFocusItem.groupName ? "组别没变，但队列更收敛" : "主战场已切换";
        focusComparisonDecisionLabel = battlegroundLabel;
        focusComparisonSummary = topQueueFocusItem.groupName === activeGlobalQueueFocusItem.groupName
          ? `这次恢复的队列还是 ${activeGlobalQueueFocusItem.label}，但同组别里最新 Top1 已经收敛到 ${topQueueFocusItem.label}。和它相比，当前队列${getFocusGapText(topQueueFocusItem, activeGlobalQueueFocusItem)}；如果要跟当前最热的 owner 继续追，建议直接切到新的 Top1。`
          : `这次恢复的队列还是 ${activeGlobalQueueFocusItem.label}，但最新 Top1 已经换成 ${topQueueFocusItem.label}。和新的主战场相比，当前队列${getFocusGapText(topQueueFocusItem, activeGlobalQueueFocusItem)}；如果你只是想确认旧路径，先回上一层组别更稳。`;
        focusComparisonPrimaryLabel = `切到最新队列：${topQueueFocusItem.label}`;
        focusComparisonPrimaryHref = switchToTopQueueHref;
        focusComparisonCards.push({
          key: "queue-shift",
          tone: topQueueFocusItem.groupName === activeGlobalQueueFocusItem.groupName ? "warning" : "danger",
          title: battlegroundLabel,
          summary: `当前恢复项排第 ${toInteger(activeQueueRank || 0)}，最新 Top1 是 ${topQueueFocusItem.label}；${getFocusCandidateMetricsText(topQueueFocusItem)}。`,
        });
      } else if (activeGlobalQueueFocusItem) {
        focusComparisonDecisionLabel = "当前队列仍是主战场";
        focusComparisonSummary = `这次恢复命中的 ${activeGlobalQueueFocusItem.label} 仍然是当前最新 Top1，说明这条回看路径还准。先沿当前队列继续查明细；如果想放大判断它是不是孤点，再回上一层组别也行。`;
        focusComparisonCards.push({
          key: "queue-stable",
          tone: "success",
          title: "当前队列仍是最新 Top1",
          summary: `${activeGlobalQueueFocusItem.label} 继续排在第一位，${getFocusCandidateMetricsText(activeGlobalQueueFocusItem)}。这次回看不是错位，而是命中了当前主战场。`,
        });
      }
    } else if (effectiveGroupName) {
      if (activeGlobalGroupFocusItem && topGroupFocusItem && activeGlobalGroupFocusItem.key !== topGroupFocusItem.key) {
        focusComparisonDecisionLabel = "原组别已不是 Top1";
        focusComparisonSummary = `这次恢复到了组别 ${activeGlobalGroupFocusItem.label}，但最新 Top1 已经换成 ${topGroupFocusItem.label}。和最新主战场相比，当前组别${getFocusGapText(topGroupFocusItem, activeGlobalGroupFocusItem)}；如果只是做复核，可以留在当前组别，否则建议切到新的 Top1。`;
        focusComparisonPrimaryLabel = `切到最新组别：${topGroupFocusItem.label}`;
        focusComparisonPrimaryHref = switchToTopGroupHref;
        focusComparisonCards.push({
          key: "group-shift",
          tone: "warning",
          title: "原命中组别已不是最新 Top1",
          summary: `当前恢复组别排第 ${toInteger(activeGroupRank || 0)}，最新 Top1 是 ${topGroupFocusItem.label}；${getFocusCandidateMetricsText(topGroupFocusItem)}。`,
        });
      } else if (topQueueWithinActiveGroup && activeGlobalGroupFocusItem && topQueueWithinActiveGroupShare >= 0.45) {
        focusComparisonDecisionLabel = "组别没变，但队列已收敛";
        focusComparisonSummary = `这次恢复的组别仍然是 ${effectiveGroupName}，但其中 ${topQueueWithinActiveGroup.queueName} 已占该组别 ${toPercent(topQueueWithinActiveGroupShare)} 的样本。与其继续停在组别层，不如直接收窄到队列，看是不是已经能直接打到对应 owner。`;
        focusComparisonPrimaryLabel = `继续收窄到队列：${topQueueWithinActiveGroup.queueName}`;
        focusComparisonPrimaryHref = buildDashboardAlertHref({
          grain,
          selectedDate,
          alertId: currentAlertLinkId || undefined,
          groupName: effectiveGroupName || undefined,
          focusQueueName: topQueueWithinActiveGroup.queueName,
          focusJoinKeyType: activeJoinKeyType || undefined,
          demoFixture: demoFixture || undefined,
        });
        focusComparisonCards.push({
          key: "group-to-queue",
          tone: "success",
          title: "组别没变，但队列已明显收敛",
          summary: `${effectiveGroupName} 仍是值得继续看的组别，但当前最集中的队列已经收敛到 ${topQueueWithinActiveGroup.queueName}。直接下钻会比继续停在组别层更快。`,
        });
      } else if (activeGlobalGroupFocusItem) {
        focusComparisonDecisionLabel = "当前组别仍值得继续看";
        focusComparisonSummary = `这次恢复的组别 ${activeGlobalGroupFocusItem.label} 仍然保持在前列。先留在这一层看 scoped 样本；如果还想继续缩小，再看下面的队列候选即可。`;
        focusComparisonCards.push({
          key: "group-stable",
          tone: "success",
          title: "当前组别仍是高优先候选",
          summary: activeGlobalGroupFocusItem.key === topGroupFocusItem?.key
            ? `${activeGlobalGroupFocusItem.label} 仍是最新 Top1，可以继续沿这条线深挖。`
            : `${activeGlobalGroupFocusItem.label} 目前排第 ${toInteger(activeGroupRank || 0)}，虽然不再是 Top1，但还在前列，适合先完成这轮复核。`,
        });
      }
    } else if (activeJoinKeyType && activeGlobalJoinKeyTypeItem && topJoinKeyTypeFocusItem && activeGlobalJoinKeyTypeItem.key !== topJoinKeyTypeFocusItem.key) {
      focusComparisonDecisionLabel = "当前类型已不是 Top1";
      focusComparisonSummary = `这次恢复的主键类型还是 "${activeGlobalJoinKeyTypeItem.label}"，但最新 Top1 已换成 "${topJoinKeyTypeFocusItem.label}"。如果你想先判断有没有换路由，直接切到新的 Top1 更快；如果只是验证旧类型，当前层也还能继续看。`;
      focusComparisonPrimaryLabel = `切到最新类型：${topJoinKeyTypeFocusItem.label}`;
      focusComparisonPrimaryHref = switchToTopJoinKeyTypeHref;
      focusComparisonCards.push({
        key: "join-key-type-shift",
        tone: "warning",
        title: "主键类型主战场已变化",
        summary: `当前恢复项排第 ${toInteger(activeJoinKeyTypeRank || 0)}，最新 Top1 是 "${topJoinKeyTypeFocusItem.label}"；${getFocusCandidateMetricsText(topJoinKeyTypeFocusItem)}。`,
      });
    } else if (activeJoinKeyType && activeGlobalJoinKeyTypeItem) {
      focusComparisonDecisionLabel = "当前类型仍值得继续看";
      focusComparisonSummary = `这次恢复的主键类型"${activeGlobalJoinKeyTypeItem.label}"仍然保持在前列。可以先沿这条类型继续看 global 分布，再决定要不要收窄到组别 / 队列。`;
      focusComparisonCards.push({
        key: "join-key-type-stable",
        tone: "success",
        title: "主键类型仍是高优先候选",
        summary: activeGlobalJoinKeyTypeItem.key === topJoinKeyTypeFocusItem?.key
          ? `当前类型仍是最新 Top1，说明这次回看没有跑偏。`
          : `当前类型目前排第 ${toInteger(activeJoinKeyTypeRank || 0)}，虽然不是 Top1，但还在候选前列。`,
      });
    } else {
      focusComparisonDecisionLabel = "还没恢复到具体候选";
      focusComparisonSummary = topQueueFocusItem
        ? `这次二次回看只恢复到了告警详情层，还没恢复到具体候选。当前最新队列 Top1 是 ${topQueueFocusItem.label}，组别 Top1 是 ${topGroupFocusItem?.label || "—"}；你不用自己扫表，直接从最新 Top1 重新聚焦就行。`
        : topGroupFocusItem
          ? `这次二次回看只恢复到了告警详情层，还没恢复到具体候选。当前最新组别 Top1 是 ${topGroupFocusItem.label}，建议直接从这里重新收窄范围。`
          : "这次二次回看只恢复到了告警详情层，当前候选还不够稳定。优先重新定位当前告警，再从首页重新判断集中点。";
      focusComparisonPrimaryLabel = topQueueFocusItem
        ? `切到最新队列：${topQueueFocusItem.label}`
        : topGroupFocusItem
          ? `切到最新组别：${topGroupFocusItem.label}`
          : "重新定位当前告警";
      focusComparisonPrimaryHref = topQueueFocusItem
        ? switchToTopQueueHref
        : topGroupFocusItem
          ? switchToTopGroupHref
          : relocalizeCurrentAlertHref;
      focusComparisonCards.push({
        key: "restore-to-alert-only",
        tone: "warning",
        title: "当前还停在告警详情层",
        summary: "这次回看没有直接恢复到组别 / 队列 / 主键类型层。首页已经把最新候选排出来了，后续动作应该是重新收窄，而不是盲目继续追旧路径。",
      });
    }

    if (topGroupFocusItem) {
      focusComparisonCards.push({
        key: "latest-group-top1",
        tone: focusComparisonCards.length > 0 && focusComparisonCards[0]?.tone === "danger" ? "warning" : "success",
        title: `最新组别 Top1：${topGroupFocusItem.label}`,
        summary: `${getFocusCandidateMetricsText(topGroupFocusItem)}。${effectiveGroupName && topQueueWithinActiveGroup
          ? `如果你还想留在当前组别 ${effectiveGroupName}，它里面最集中的队列是 ${topQueueWithinActiveGroup.queueName}。`
          : "这就是当前全局样本里最值得先看的组别入口。"}`,
      });
    }
  }
  const detailActions = Array.isArray(groupDetailResult.data?.actions)
    ? (groupDetailResult.data?.actions as string[])
    : [];
  const trendRows = getRows(groupDetailResult.data?.trend_df);
  const trendPoints = trendRows.map((row) => ({
    label: toDisplayDate(row.anchor_date as string | undefined),
    primary: toNumber(row.final_accuracy_rate),
    secondary: toNumber(row.raw_accuracy_rate),
  }));
  const trainingRecoveryRows = getRows(groupDetailResult.data?.training_recovery_df).slice(0, 10);
  const trainingRecoverySummary =
    (groupDetailResult.data?.training_recovery_summary as Record<string, unknown> | undefined) || {};

  const groupQualityItems = [...groupDisplayRows]
    .sort((left, right) => toNumber(right.qa_cnt) - toNumber(left.qa_cnt))
    .slice(0, 8)
    .map((row) => {
      const accuracy = toNumber(row.final_accuracy_rate);
      return {
        label: pickText(row.group_name),
        value: accuracy,
        meta: `质检量 ${toInteger(row.qa_cnt)}`,
        tone: accuracy >= 99 ? "success" : accuracy >= 98 ? "warning" : "danger",
      } as const;
    });

  const alertStatusItems = [
    { label: "待处理", value: toNumber(statusSummary.open), tone: "warning" as const, meta: "需要继续跟进" },
    { label: "已认领", value: toNumber(statusSummary.claimed), tone: "primary" as const, meta: "已有 owner 在处理" },
    { label: "已忽略", value: toNumber(statusSummary.ignored), tone: "neutral" as const, meta: "已确认暂不处理" },
    { label: "已解决", value: toNumber(statusSummary.resolved), tone: "success" as const, meta: "已完成闭环" },
  ];

  const queueQualityItems = detailRows.queues.slice(0, 8).map((row) => {
    const accuracy = toNumber(row.final_accuracy_rate);
    return {
      label: pickText(row.queue_name),
      value: accuracy,
      meta: `质检量 ${toInteger(row.qa_cnt)}`,
      tone: accuracy >= 99 ? "success" : accuracy >= 98 ? "warning" : "danger",
    } as const;
  });

  const errorMessages = [
    metaResult.error,
    overviewResult.error,
    alertsResult.error,
    groupDetailResult.error,
    alertId && alertDetailResult.error ? `告警详情：${alertDetailResult.error}` : null,
  ].filter(Boolean);

  return (
    <AppShell
      currentPath="/"
      title="首页总览"
      subtitle="质检经营数据总览、告警闭环与组别下钻"
      lastRefresh={selectedDate}
      actions={
        <>
          <Link className="link-button" href="/details">
            打开明细查询
          </Link>
          <Link className="link-button primary" href="/newcomers">
            打开新人追踪
          </Link>
        </>
      }
    >
      {errorMessages.length > 0 ? (
        <div className="error-banner">
          当前接口有异常：{errorMessages.join("；")}。请先确认 `bash start_api.sh` 已正常启动。
        </div>
      ) : null}

      <CollapsiblePanel
        title="查看条件"
        subtitle="调整时间粒度、锚点日期和下钻组别；展开修改。"
        defaultOpen={false}
        summary={
          <span>
            {grain === "day" ? "日监控" : grain === "week" ? "周复盘" : "月管理"}
            {" · "}{selectedDate}
            {effectiveGroupName ? ` · 下钻: ${effectiveGroupName}` : ""}
          </span>
        }
      >
        <form className="section-stack">
          {demoFixture ? <input type="hidden" name="demo_fixture" value={demoFixture} /> : null}
          <div className="form-grid">
            <div className="form-field">
              <label htmlFor="grain">粒度</label>
              <select id="grain" name="grain" className="select" defaultValue={grain}>
                <option value="day">日监控</option>
                <option value="week">周复盘</option>
                <option value="month">月管理</option>
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="selected_date">锚点日期</label>
              <input
                id="selected_date"
                name="selected_date"
                type="date"
                className="input"
                defaultValue={selectedDate}
                min={toDateInputValue(metaResult.data?.min_date as string | undefined)}
                max={toDateInputValue(metaResult.data?.max_date as string | undefined)}
              />
            </div>
            <div className="form-field">
              <label htmlFor="group_name">当前下钻组别</label>
              <input id="group_name" name="group_name" className="input" defaultValue={effectiveGroupName || ""} placeholder="可留空" />
            </div>
          </div>
          <div className="form-actions">
            <FilterActionsBar
              basePath="/"
              submitLabel="刷新首页"
              submitLoadingLabel="刷新中…"
              resetLabel="恢复默认条件"
              resetLoadingLabel="恢复中…"
              resetQueryString={
                demoFixture
                  ? buildQueryString({ demo_fixture: demoFixture }).slice(1)
                  : ""
              }
              defaultDateStart={toDateInputValue(
                (metaResult.data?.default_selected_date as string | undefined) ||
                  (metaResult.data?.max_date as string | undefined),
              )}
              resettableFieldNames={["group_name"]}
              extras={
                <Link
                  className="link-button"
                  href={
                    buildQueryString({
                      grain,
                      selected_date: selectedDate,
                      demo_fixture: demoFixture || undefined,
                    }) || "/"
                  }
                >
                  只清空下钻
                </Link>
              }
            />
          </div>
        </form>
      </CollapsiblePanel>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">经营驾驶舱</h3>
            <p className="panel-subtitle">直接复用后端 service 生成的结论层，前后端首页看到的是同一套{'\u201c'}今天先干什么{'\u201d'}。</p>
          </div>
        </div>
        <div className="section-stack">
          <div className="kpi-pill">{pickText(cockpit.headline, "先看关键风险，再决定是否继续下钻")}</div>
          {pickText(cockpit.summary) ? <div>{pickText(cockpit.summary)}</div> : null}
          <div className="grid grid-3">
            <div>
              <h4 className="panel-title">重点风险</h4>
              <ul className="bullet-list">
                {(Array.isArray(cockpit.risk_items) ? (cockpit.risk_items as string[]) : []).slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="panel-title">今日动作</h4>
              <ul className="bullet-list">
                {(Array.isArray(cockpit.action_items) ? (cockpit.action_items as string[]) : []).slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="panel-title">继续观察</h4>
              <ul className="bullet-list">
                {(Array.isArray(cockpit.watch_items) ? (cockpit.watch_items as string[]) : []).slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="panel subtle-panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">数仓健康度</h3>
            <p className="panel-subtitle">一眼看数据到没到、新人模块挂没挂；异常时建议先跳 /smoke 排接口，再回来看业务指标。</p>
          </div>
          <div className="hero-actions">
            <Link className="link-button" href="/smoke">打开在线冒烟</Link>
          </div>
        </div>
        <div className="kpi-row">
          <span className={`status-pill ${warehouseFreshnessTone}`}>
            数据新鲜度：{warehouseFreshnessLabel}
            {warehouseMaxDate ? `（max_date=${warehouseMaxDate}）` : ""}
          </span>
          <span className={`status-pill ${newcomersRouterTone}`}>
            新人路由：{newcomersRouterLabel}
          </span>
          {healthResult.error ? (
            <span className="status-pill danger">
              /api/health 异常：{healthResult.error}
            </span>
          ) : null}
        </div>
        {!newcomersReady && newcomersLoadError ? (
          <div className="error-banner" style={{ marginTop: 8 }}>
            新人路由加载失败：{newcomersLoadError}。明细/新人追踪页会走降级；先跳 /smoke 看是哪条接口挂了。
          </div>
        ) : null}
        {warehouseDiffDays !== null && warehouseDiffDays > 3 ? (
          <div className="error-banner" style={{ marginTop: 8 }}>
            数仓已滞后 {warehouseDiffDays} 天，日更任务大概率挂了。优先看 launchd / jobs 日志，或去 /smoke 单独确认 meta 接口。
          </div>
        ) : null}
      </section>

      <div className="grid grid-4">
        <SummaryCard label="当前组别数" value={toInteger(groupRows.length)} hint="首页首屏直接展示组别经营概览。" />
        <SummaryCard label="当前质检量" value={toInteger(totalQa)} hint="按当前粒度与锚点日期聚合。" />
        <SummaryCard label="组别平均最终正确率" value={toPercent(avgFinalAccuracy)} hint="先看整体水位，再决定是否继续下钻。" tone="success" />
        <SummaryCard label="触发告警总数" value={toInteger(alertSummary.total)} hint="P0 / P1 / P2 已统一从告警接口读取。" tone="warning" />
      </div>

      <div className="grid grid-3">
        <SummaryCard label="P0 告警" value={toInteger(alertSummary.P0)} hint="需要当天优先处理。" tone="danger" />
        <SummaryCard label="待处理告警" value={toInteger(statusSummary.open)} hint="状态流转后这块会直接变化。" tone="warning" />
        <SummaryCard label="SLA 超时" value={toInteger(slaSummary.total_overdue)} hint="接口已经给出超时摘要，前端不用再算。" tone="danger" />
      </div>

      <div className="grid grid-2">
        <BarListCard
          title="组别最终正确率分布"
          subtitle="按当前质检量排序展示最值得盯的组别，帮助首页第一眼先看经营水位。"
          items={groupQualityItems}
          suffix="%"
        />
        <BarListCard
          title="告警状态分布"
          subtitle="把待处理、已认领、已忽略、已解决拆开看，方便判断今天是不是在消化库存。"
          items={alertStatusItems}
        />
      </div>

      {alertActions.length > 0 ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">首页建议动作</h3>
              <p className="panel-subtitle">直接复用 service 层生成的动作建议，不再把文案逻辑写回前端。</p>
            </div>
          </div>
          <ul className="bullet-list">
            {alertActions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <DataTable
        title="组别经营概览"
        subtitle="这块对应原 Streamlit 首页第一屏。现在先迁出只读经营视图，点击组别继续看下钻。"
        rows={buildTableRows(groupDisplayRows, {
          group_name: (row) => (
            <Link
              className="table-link"
              href={buildQueryString({
                grain,
                selected_date: selectedDate,
                group_name: pickText(row.group_name, ""),
                demo_fixture: demoFixture || undefined,
              }) || "/"}
            >
              {pickText(row.group_name)}
            </Link>
          ),
          qa_cnt: (row) => toInteger(row.qa_cnt),
          raw_accuracy_rate: (row) => toPercent(row.raw_accuracy_rate),
          final_accuracy_rate: (row) => toPercent(row.final_accuracy_rate),
          misjudge_rate: (row) => toPercent(row.misjudge_rate),
          missjudge_rate: (row) => toPercent(row.missjudge_rate),
        })}
        columns={[
          { key: "group_name", label: "组别", sortable: true },
          { key: "qa_cnt", label: "质检量", sortable: true },
          { key: "raw_accuracy_rate", label: "原始正确率", sortable: true },
          { key: "final_accuracy_rate", label: "最终正确率", sortable: true },
          { key: "misjudge_rate", label: "错判率", sortable: true },
          { key: "missjudge_rate", label: "漏判率", sortable: true },
        ]}
        emptyText="当前条件下没有组别概览数据。"
        searchable
      />

      <AlertFilterBar
        activeSeverities={activeSeverities}
        activeModules={activeModules}
        activeGrains={activeGrains}
        activeStatus={activeStatusFilter}
        availableModules={availableModules}
        availableGrains={availableGrains}
        filteredCount={filteredAlertItems.length}
        totalCount={enrichedAlertItems.length}
      />

      <AlertBulkPanel
        alerts={filteredAlertItems.slice(0, 20)}
        grain={grain}
        selectedDate={selectedDate}
        groupName={effectiveGroupName || undefined}
        selectedAlertId={alertId}
        demoFixture={demoFixture || undefined}
      />

      {returnedFromDetails ? (
        <section className="panel subtle-panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">从明细页返回的恢复感知</h3>
              <p className="panel-subtitle">这块不再让首页悄悄恢复状态，而是把这次到底恢复到了哪一层、是精确恢复还是旧链接降级恢复直接讲清楚。</p>
            </div>
            <div className="hero-actions">
              <Link className="link-button primary" href={relocalizeCurrentAlertHref}>
                重新定位当前告警
              </Link>
              <Link className="link-button" href={alertListHref}>
                回到告警列表
              </Link>
            </div>
          </div>
          <div className="section-stack">
            <div>{returnedFromDetailsSummary}</div>
            <div className="kpi-row">
              {returnedFromDetailsPills.map((item) => (
                <span key={item} className="kpi-pill">{item}</span>
              ))}
            </div>
            {returnedFromDetailsWarning ? (
              <div className="error-banner">{returnedFromDetailsWarning}</div>
            ) : (
              <div className="inline-note">
                如果现在看到的层级不对，直接用{'\u201c'}重新定位当前告警{'\u201d'}先清掉回看标记，或者继续用下面高亮的组别 / 队列 / 主键类型候选往下查，不需要自己手改 query string。
              </div>
            )}
          </div>
        </section>
      ) : null}

      {alertId ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h3 className="panel-title">告警详情闭环</h3>
              <p className="panel-subtitle">首页现在可以直接从告警列表进入单条详情，看到状态、SLA、关联样本和处理历史；如果再跳去明细查询，也会保留这条告警当前的返回链路和聚焦状态。</p>
            </div>
            <div className="hero-actions">
              {selectedAlertDetail ? (
                <Link className="link-button primary" href={selectedAlertDetailHref}>
                  打开关联明细（保留返回链路）
                </Link>
              ) : null}
              <Link className="link-button" href={closeAlertHref}>
                关闭详情
              </Link>
            </div>
          </div>

          {alertDetailResult.error ? (
            <div className="section-stack">
              <div className="error-banner">
                {returnedFromDetails
                  ? `明细页刚尝试帮你恢复的 alert_id=${returnAlertId || alertId || "当前告警"} 在这个粒度/日期下没有命中详情。通常是日期切换、旧链接失效，或降级恢复后的锚点日期已经变化。先关闭详情，再重新从上方告警列表进入。`
                  : "当前 alert_id 在这个粒度/日期下没有命中详情，通常是切换日期或粒度后旧链接失效。先关闭详情，再重新从上方告警列表进入。"}
              </div>
              <div className="form-actions">
                <Link className="link-button primary" href={relocalizeCurrentAlertHref}>
                  重新定位当前告警
                </Link>
                <Link className="link-button" href={alertListHref}>
                  回到告警列表
                </Link>
              </div>
            </div>
          ) : selectedAlertDetail ? (
            <div className="section-stack">
              <div className="grid grid-4">
                <SummaryCard
                  label="告警级别"
                  value={<StatusChip value={selectedAlertDetail.severity} tone={getSeverityTone(selectedAlertDetail.severity)} />}
                  hint={pickText(selectedAlertDetail.rule_name, "当前规则")}
                  tone={getSeverityTone(selectedAlertDetail.severity)}
                />
                <SummaryCard
                  label="当前状态"
                  value={<StatusChip value={selectedAlertDetail.alert_status_label} tone={getStatusTone(selectedAlertDetail.alert_status)} />}
                  hint={pickText(selectedAlertDetail.owner_name, "待分配")}
                  tone={getStatusTone(selectedAlertDetail.alert_status)}
                />
                <SummaryCard
                  label="对象层级"
                  value={pickText(selectedAlertDetail.target_level_label)}
                  hint={pickText(selectedAlertDetail.target_key, "—")}
                />
                <SummaryCard
                  label="当前 SLA"
                  value={pickText(selectedAlertDetail.sla_label)}
                  hint={pickText(selectedAlertDetail.sla_policy_text, "—")}
                  tone={selectedAlertDetail.sla_is_overdue ? "danger" : "warning"}
                />
              </div>

              <div className="kpi-row">
                {pickText(selectedAlertDetail.group_name, "") ? (
                  <span className="kpi-pill">相关组别：{pickText(selectedAlertDetail.group_name)}</span>
                ) : null}
                {pickText(selectedAlertDetail.queue_name, "") ? (
                  <span className="kpi-pill">相关队列：{pickText(selectedAlertDetail.queue_name)}</span>
                ) : null}
                {pickText(selectedAlertDetail.error_type, "") ? (
                  <span className="kpi-pill">错误类型：{pickText(selectedAlertDetail.error_type)}</span>
                ) : null}
                <span className="kpi-pill">当前值：{pickText(selectedAlertDetail.metric_value_display)}</span>
                <span className="kpi-pill">阈值：{pickText(selectedAlertDetail.threshold_display)}</span>
              </div>

              <div className="grid grid-2">
                <div className="panel subtle-panel">
                  <div className="panel-header">
                    <div>
                      <h4 className="panel-title">核心信息</h4>
                      <p className="panel-subtitle">把首页需要快速看清的文案、备注和时间点一起收拢，避免再跳回旧版页面补信息。</p>
                    </div>
                  </div>
                  <div className="section-stack">
                    <div><strong>告警对象：</strong>{pickText(selectedAlertDetail.target_key)}</div>
                    <div><strong>告警文案：</strong>{pickText(selectedAlertDetail.alert_message)}</div>
                    <div><strong>当前备注：</strong>{pickText(selectedAlertDetail.handle_note)}</div>
                    <div><strong>创建时间：</strong>{formatDateTime(selectedAlertDetail.alert_created_at)}</div>
                    <div><strong>最近状态更新时间：</strong>{formatDateTime(selectedAlertDetail.status_updated_at)}</div>
                    <div><strong>SLA 起点：</strong>{formatDateTime(selectedAlertDetail.sla_stage_started_at)}</div>
                    <div><strong>SLA 截止：</strong>{formatDateTime(selectedAlertDetail.sla_deadline_at)}</div>
                  </div>
                </div>

                <div className="panel subtle-panel">
                  <div className="panel-header">
                    <div>
                      <h4 className="panel-title">快捷处置与建议</h4>
                      <p className="panel-subtitle">这条告警现在可以直接在首页认领 / 解决 / 忽略 / 重新打开；如果要继续跳去明细查询，也会保留回到当前告警的链路。</p>
                    </div>
                  </div>
                  <div className="section-stack">
                    <AlertQuickActions
                      alertId={pickText(selectedAlertDetail.alert_id, "")}
                      currentStatus={pickText(selectedAlertDetail.alert_status, "")}
                      currentStatusLabel={pickText(selectedAlertDetail.alert_status_label, "")}
                      initialOwnerName={pickText(selectedAlertDetail.owner_name, "")}
                      initialHandleNote={pickText(selectedAlertDetail.handle_note, "")}
                    />
                    <div>{pickText(selectedAlertDetail.suggestion, "当前暂无补充建议。")}</div>
                    <div>{pickText(selectedAlertDetail.sla_policy_text, "—")}</div>
                    <div className="inline-note">
                      现在从这里跳去明细查询，会一并带上当前 alert_id、组别 / 队列以及主键类型聚焦上下文；明细页里的动作名称会和首页保持一致：返回首页当前告警{hasPreviousLayerAction ? ` / ${previousLayerLabel} / 彻底清空聚焦` : ""}。
                    </div>
                    <div className="form-actions">
                      {relatedGroupHref ? (
                        <Link className="link-button" href={relatedGroupHref}>
                          聚焦相关组别
                        </Link>
                      ) : null}
                      <Link className="link-button primary" href={selectedAlertDetailHref}>
                        跳转到明细查询（保留返回链路）
                      </Link>
                    </div>
                  </div>
                </div>
              </div>

              {isSystemAlert ? (
                <section className="panel subtle-panel">
                  <div className="panel-header">
                    <div>
                      <h4 className="panel-title">当前聚焦说明</h4>
                      <p className="panel-subtitle">把这次系统级告警是怎么从 global 样本一路收窄过来的讲清楚，避免 owner 误以为首页和明细看到的是两套数据。</p>
                    </div>
                  </div>
                  <div className="section-stack">
                    <div>{systemAlertFocusSummary}</div>
                    <div className="kpi-row">
                      {systemAlertFocusPills.map((item) => (
                        <span key={item} className="kpi-pill">{item}</span>
                      ))}
                    </div>
                    {activeJoinKeyType ? (
                      <div className="inline-note">
                        当前主键类型只用于首页样本快速聚焦；如果现在跳去明细查询，这个类型会作为联动说明带过去，但不会直接变成明细接口过滤条件。
                      </div>
                    ) : null}
                    {returnedFromDetails ? (
                      <div className="inline-note">
                        这次是从明细页回来的，首页当前恢复层级就是{'\u201c'}{returnedLayerLabel}{'\u201d'}。如果你只是想先回看刚才确认过的范围，这里已经对齐；如果想重新放大或回到 global，直接继续用下面的快速聚焦入口即可。
                      </div>
                    ) : null}
                  </div>
                </section>
              ) : null}

              {focusComparisonSummary ? (
                <section className="panel subtle-panel">
                  <div className="panel-header">
                    <div>
                      <h4 className="panel-title">二次回看变化对比</h4>
                      <p className="panel-subtitle">把{'\u201c'}这次回来后到底是更集中、变分散，还是已经换主战场了{'\u201d'}直接讲清楚，不再逼你自己肉眼对比候选列表。</p>
                    </div>
                    <div className="hero-actions">
                      <Link className={`link-button${focusComparisonPrimaryTone === "primary" ? " primary" : ""}`} href={focusComparisonPrimaryHref}>
                        {focusComparisonPrimaryLabel}
                      </Link>
                      {hasPreviousLayerAction ? (
                        <Link className="link-button" href={previousLayerHref}>
                          {previousLayerLabel}
                        </Link>
                      ) : null}
                      <Link className="link-button" href={relocalizeCurrentAlertHref}>
                        重新定位当前告警
                      </Link>
                    </div>
                  </div>
                  <div className="section-stack">
                    <div>{focusComparisonSummary}</div>
                    <div className="kpi-row">
                      <span className="kpi-pill">变化判断：{focusComparisonDecisionLabel}</span>
                      {topGroupFocusItem ? <span className="kpi-pill">最新组别 Top1：{topGroupFocusItem.label}</span> : null}
                      {topQueueFocusItem ? <span className="kpi-pill">最新队列 Top1：{topQueueFocusItem.label}</span> : null}
                      {topJoinKeyTypeFocusItem ? <span className="kpi-pill">最新主键类型 Top1：{topJoinKeyTypeFocusItem.label}</span> : null}
                    </div>
                    {focusComparisonCards.length > 0 ? (
                      <div className="comparison-card-list">
                        {focusComparisonCards.map((card) => (
                          <div key={card.key} className={`comparison-card ${card.tone}`}>
                            <div className="comparison-card-title">{card.title}</div>
                            <div className="comparison-card-summary">{card.summary}</div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                    <div className="inline-note">
                      这块只负责帮你判断{'\u201c'}当前路径还准不准、下一步该往哪边点{'\u201d'}；真正继续放大时，还是直接用上面的建议动作或下面的快速聚焦入口，不用自己手改参数。
                    </div>
                  </div>
                </section>
              ) : null}

              {groupDetailErrorMessage ? (
                <div className="error-banner">{groupDetailErrorMessage}</div>
              ) : alertPreviewRows.length > 0 ? (
                <DataTable
                  title={alertSampleTitle}
                  subtitle={alertSampleSubtitle}
                  rows={buildTableRows(alertPreviewRows, alertSampleColumns.cellBuilders)}
                  columns={alertSampleColumns.columns}
                  emptyText="当前告警没有命中可预览样本。"
                />
              ) : selectedAlertDetail ? (
                <div className="info-banner">{alertPreviewEmptyMessage}</div>
              ) : null}

              {showQuickFocusSection ? (
                <section className="panel subtle-panel">
                  <div className="panel-header">
                    <div>
                      <h4 className="panel-title">系统级样本快速聚焦</h4>
                      <p className="panel-subtitle">{quickFocusPanelSubtitle}</p>
                    </div>
                    {(effectiveGroupName || focusedQueueName || activeJoinKeyType) ? (
                      <div className="hero-actions">
                        <Link
                          className="link-button"
                          href={clearQuickFocusHref}
                        >
                          清空快速聚焦
                        </Link>
                      </div>
                    ) : null}
                  </div>

                  <div className="section-stack">
                    <div className="kpi-row">
                      <span className="kpi-pill">排查阶段：{restoreStageLabel}</span>
                      {effectiveGroupName ? <span className="kpi-pill">当前组别：{effectiveGroupName}</span> : null}
                      {focusedQueueName ? <span className="kpi-pill">当前队列：{focusedQueueName}</span> : null}
                      {activeJoinKeyType ? <span className="kpi-pill">主键类型：{activeJoinKeyType}</span> : null}
                    </div>

                    {quickFocusRestoreSummary ? <div className="inline-note">{quickFocusRestoreSummary}</div> : null}

                    <div className="grid grid-3">
                      <SummaryCard label="全局样本数" value={toInteger(globalFocusedSampleCount)} hint="基于当前主键类型展开范围统计；这里是可继续聚焦的候选样本量。" />
                      <SummaryCard label="覆盖组别" value={toInteger(globalFocusedGroupCount)} hint="先看问题是否集中在少数组别，避免一上来就全量排查。" />
                      <SummaryCard label="覆盖队列" value={toInteger(globalFocusedQueueCount)} hint="如果队列集中度很高，优先直接打到队列 owner。" />
                    </div>

                    <div className="grid grid-3">
                      <div className="panel subtle-panel">
                        <div className="panel-header">
                          <div>
                            <h5 className="panel-title">问题最多组别</h5>
                            <p className="panel-subtitle">从全局样本先聚焦最值得先看的组别，再回到 scoped 样本视角。</p>
                          </div>
                        </div>
                        {visibleGlobalGroupFocusItems.length > 0 ? (
                          <div className="section-stack">
                            {globalGroupFocusSummary ? <div className="inline-note">{globalGroupFocusSummary}</div> : null}
                            <ul className="focus-candidate-list">
                              {visibleGlobalGroupFocusItems.map((item) => {
                                const isActive = item.groupName === effectiveGroupName;
                                const rank = globalGroupFocusItems.findIndex((candidate) => candidate.key === item.key) + 1;
                                const rankLabel = rank > 0 && rank <= 3 ? `Top${rank}` : rank > 0 ? `当前第 ${rank}` : null;
                                const activeLabel = !isActive
                                  ? null
                                  : focusedQueueName
                                    ? "当前组别（队列已继续收窄）"
                                    : returnedFromDetails
                                      ? "本次恢复命中"
                                      : "当前已聚焦";
                                return (
                                  <li key={item.key} className={`focus-candidate-item${isActive ? " active" : ""}`}>
                                    <div className="focus-candidate-content">
                                      <div className="focus-candidate-title-row">
                                        <strong>{item.label}</strong>
                                        {rankLabel ? <span className="kpi-pill">{rankLabel}</span> : null}
                                        <span className="kpi-pill">样本 {toInteger(item.count)}</span>
                                        {rank === 1 ? <span className="focus-candidate-badge">最新 Top1</span> : null}
                                        {activeLabel ? <span className="focus-candidate-badge">{activeLabel}</span> : null}
                                      </div>
                                      <div className="focus-candidate-subtitle">
                                        排序依据：{getFocusCandidateMetricsText(item)}。{returnedFromDetails && isActive
                                          ? "这次回看已经恢复到这个组别；如果它已经不是最新 Top1，优先看上面的对比说明再决定要不要切走。"
                                          : "先把首页样本收窄到这个组别，再判断是否值得继续下钻到队列。"}
                                      </div>
                                    </div>
                                    <div className="form-actions">
                                      <Link
                                        className={`link-button${isActive ? " primary" : ""}`}
                                        href={buildDashboardAlertHref({
                                          grain,
                                          selectedDate,
                                          alertId: pickText(selectedAlertDetail.alert_id, ""),
                                          groupName: item.groupName,
                                          focusJoinKeyType: activeJoinKeyType || undefined,
                                          demoFixture: demoFixture || undefined,
                                        })}
                                      >
                                        {isActive ? "当前已高亮" : "聚焦首页"}
                                      </Link>
                                      <Link
                                        className={`link-button${isActive ? "" : " primary"}`}
                                        href={buildAlertDetailsHref(selectedAlertDetail, {
                                          groupName: item.groupName,
                                          focusSource: "system_alert",
                                          focusScope: "scoped",
                                          focusJoinKeyType: activeJoinKeyType || undefined,
                                          focusAlertId: pickText(selectedAlertDetail.alert_id, ""),
                                          focusAlertRuleName: pickText(selectedAlertDetail.rule_name, ""),
                                          dashboardGrain: grain,
                                          dashboardSelectedDate: selectedDate,
                                          dashboardAlertId: pickText(selectedAlertDetail.alert_id, ""),
                                          dashboardGroupName: item.groupName,
                                          dashboardFocusJoinKeyType: activeJoinKeyType || undefined,
                                          demoFixture: demoFixture || undefined,
                                          dashboardDemoFixture: demoFixture || undefined,
                                        })}
                                      >
                                        明细查询
                                      </Link>
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        ) : (
                          <div className="empty-state">当前全局样本里还没有可聚焦的组别。</div>
                        )}
                      </div>

                      <div className="panel subtle-panel">
                        <div className="panel-header">
                          <div>
                            <h5 className="panel-title">问题最多队列</h5>
                            <p className="panel-subtitle">直接把系统级样本收窄到具体队列，首页就能立刻切到更精准的关联样本。</p>
                          </div>
                        </div>
                        {visibleGlobalQueueFocusItems.length > 0 ? (
                          <div className="section-stack">
                            {globalQueueFocusSummary ? <div className="inline-note">{globalQueueFocusSummary}</div> : null}
                            <ul className="focus-candidate-list">
                              {visibleGlobalQueueFocusItems.map((item) => {
                                const isActive = item.groupName === effectiveGroupName && item.queueName === focusedQueueName;
                                const rank = globalQueueFocusItems.findIndex((candidate) => candidate.key === item.key) + 1;
                                const rankLabel = rank > 0 && rank <= 3 ? `Top${rank}` : rank > 0 ? `当前第 ${rank}` : null;
                                const activeLabel = !isActive
                                  ? null
                                  : returnedFromDetails
                                    ? "本次恢复命中"
                                    : "当前已聚焦";
                                return (
                                  <li key={item.key} className={`focus-candidate-item${isActive ? " active" : ""}`}>
                                    <div className="focus-candidate-content">
                                      <div className="focus-candidate-title-row">
                                        <strong>{item.label}</strong>
                                        {rankLabel ? <span className="kpi-pill">{rankLabel}</span> : null}
                                        <span className="kpi-pill">样本 {toInteger(item.count)}</span>
                                        {rank === 1 ? <span className="focus-candidate-badge">最新 Top1</span> : null}
                                        {activeLabel ? <span className="focus-candidate-badge">{activeLabel}</span> : null}
                                      </div>
                                      <div className="focus-candidate-subtitle">
                                        排序依据：{getFocusCandidateMetricsText(item)}。{returnedFromDetails && isActive
                                          ? "这次回看已经恢复到这个队列；如果它已经不是最新 Top1，优先看上面的队列对比再决定要不要切走。"
                                          : "直接把系统级全局样本收窄到这个队列，适合快速确认是否已经定位到具体 owner。"}
                                      </div>
                                    </div>
                                    <div className="form-actions">
                                      <Link
                                        className={`link-button${isActive ? " primary" : ""}`}
                                        href={buildDashboardAlertHref({
                                          grain,
                                          selectedDate,
                                          alertId: pickText(selectedAlertDetail.alert_id, ""),
                                          groupName: item.groupName,
                                          focusQueueName: item.queueName,
                                          focusJoinKeyType: activeJoinKeyType || undefined,
                                          demoFixture: demoFixture || undefined,
                                        })}
                                      >
                                        {isActive ? "当前已高亮" : "聚焦首页"}
                                      </Link>
                                      <Link
                                        className={`link-button${isActive ? "" : " primary"}`}
                                        href={buildAlertDetailsHref(selectedAlertDetail, {
                                          groupName: item.groupName,
                                          queueName: item.queueName,
                                          focusSource: "system_alert",
                                          focusScope: "scoped",
                                          focusJoinKeyType: activeJoinKeyType || undefined,
                                          focusAlertId: pickText(selectedAlertDetail.alert_id, ""),
                                          focusAlertRuleName: pickText(selectedAlertDetail.rule_name, ""),
                                          dashboardGrain: grain,
                                          dashboardSelectedDate: selectedDate,
                                          dashboardAlertId: pickText(selectedAlertDetail.alert_id, ""),
                                          dashboardGroupName: item.groupName,
                                          dashboardFocusQueueName: item.queueName,
                                          dashboardFocusJoinKeyType: activeJoinKeyType || undefined,
                                          demoFixture: demoFixture || undefined,
                                          dashboardDemoFixture: demoFixture || undefined,
                                        })}
                                      >
                                        明细查询
                                      </Link>
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        ) : (
                          <div className="empty-state">当前全局样本里还没有可聚焦的队列。</div>
                        )}
                      </div>

                      <div className="panel subtle-panel">
                        <div className="panel-header">
                          <div>
                            <h5 className="panel-title">按主键类型展开</h5>
                            <p className="panel-subtitle">先按主键类型切开，再看问题是不是集中在某一种关联键路由。</p>
                          </div>
                        </div>
                        {visibleGlobalJoinKeyTypeItems.length > 0 ? (
                          <div className="section-stack">
                            {globalJoinKeyTypeFocusSummary ? <div className="inline-note">{globalJoinKeyTypeFocusSummary}</div> : null}
                            <ul className="focus-candidate-list">
                              {visibleGlobalJoinKeyTypeItems.map((item) => {
                                const isActive = item.joinKeyType === activeJoinKeyType;
                                const rank = globalJoinKeyTypeItems.findIndex((candidate) => candidate.key === item.key) + 1;
                                const rankLabel = rank > 0 && rank <= 3 ? `Top${rank}` : rank > 0 ? `当前第 ${rank}` : null;
                                const activeLabel = !isActive
                                  ? null
                                  : returnedFromDetails
                                    ? "本次恢复命中"
                                    : "当前已展开";
                                return (
                                  <li key={item.key} className={`focus-candidate-item${isActive ? " active" : ""}`}>
                                    <div className="focus-candidate-content">
                                      <div className="focus-candidate-title-row">
                                        <strong>{item.label}</strong>
                                        {rankLabel ? <span className="kpi-pill">{rankLabel}</span> : null}
                                        <span className="kpi-pill">样本 {toInteger(item.count)}</span>
                                        {rank === 1 ? <span className="focus-candidate-badge">最新 Top1</span> : null}
                                        {activeLabel ? <span className="focus-candidate-badge">{activeLabel}</span> : null}
                                      </div>
                                      <div className="focus-candidate-subtitle">
                                        排序依据：{getFocusCandidateMetricsText(item)}。{returnedFromDetails && isActive
                                          ? "这次回看已经恢复到这个主键类型；如果它已经不是最新 Top1，优先看上面的类型对比再决定要不要继续沿这条线排查。"
                                          : "先按这个主键类型切开，再决定要不要继续收窄到组别 / 队列。"}
                                      </div>
                                    </div>
                                    <div className="form-actions">
                                      <Link
                                        className={`link-button${isActive ? " primary" : ""}`}
                                        href={buildDashboardAlertHref({
                                          grain,
                                          selectedDate,
                                          alertId: pickText(selectedAlertDetail.alert_id, ""),
                                          groupName: effectiveGroupName || undefined,
                                          focusQueueName: focusedQueueName || undefined,
                                          focusJoinKeyType: item.joinKeyType,
                                          demoFixture: demoFixture || undefined,
                                        })}
                                      >
                                        {isActive ? "当前已高亮" : "展开该类型"}
                                      </Link>
                                      {isActive ? (
                                        <Link
                                          className="link-button"
                                          href={buildDashboardAlertHref({
                                            grain,
                                            selectedDate,
                                            alertId: pickText(selectedAlertDetail.alert_id, ""),
                                            groupName: effectiveGroupName || undefined,
                                            focusQueueName: focusedQueueName || undefined,
                                            demoFixture: demoFixture || undefined,
                                          })}
                                        >
                                          清空类型
                                        </Link>
                                      ) : null}
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        ) : (
                          <div className="empty-state">当前全局样本里还没有识别到主键类型。</div>
                        )}
                      </div>
                    </div>
                  </div>
                </section>
              ) : null}

              <DataTable
                title="处理历史"
                subtitle="单条告警的历史状态流转直接在首页可见，便于判断是新问题、库存问题，还是已经有人接手。"
                rows={buildTableRows(selectedAlertHistory, {
                  alert_status_label: (row) => (
                    <StatusChip value={row.alert_status_label} tone={getStatusTone(row.alert_status)} />
                  ),
                  updated_at: (row) => formatDateTime(row.updated_at),
                })}
                columns={[
                  { key: "alert_status_label", label: "状态" },
                  { key: "updated_at", label: "更新时间", sortable: true },
                  { key: "owner_name", label: "处理人", sortable: true },
                  { key: "handle_note", label: "处理备注" },
                ]}
                emptyText="这条告警当前还没有处理历史，说明它要么刚触发，要么还没人开始跟。"
              />
            </div>
          ) : null}
        </section>
      ) : null}

      {effectiveGroupName ? (
        <div className="section-stack">
          <section className="panel">
            <div className="panel-header">
              <div>
                <h3 className="panel-title">当前下钻：{effectiveGroupName}</h3>
                <p className="panel-subtitle">这一层已经开始消费 `/api/v1/dashboard/group-detail`；如果是从告警详情进来，会自动带上队列和规则上下文。</p>
              </div>
            </div>
            {detailActions.length > 0 ? (
              <ul className="bullet-list">
                {detailActions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">当前组别暂无额外建议动作。</div>
            )}
          </section>

          <div className="grid grid-2">
            <LineChartCard
              title="组别正确率趋势"
              subtitle="直接消费 group-detail 返回的 trend_df，对齐旧版首页那条最关键的趋势线。"
              points={trendPoints}
              primaryLabel="最终正确率"
              secondaryLabel="原始正确率"
            />
            <BarListCard
              title="队列最终正确率分布"
              subtitle="用当前下钻组别下的队列分布，快速判断问题是在单点爆发还是整体下滑。"
              items={queueQualityItems}
              suffix="%"
            />
          </div>

          {toNumber(trainingRecoverySummary.total) > 0 ? (
            <div className="grid grid-4">
              <SummaryCard label="跟踪动作数" value={toInteger(trainingRecoverySummary.total)} hint="当前组别下已进入回收跟踪的动作数量。" />
              <SummaryCard label="1周已回收" value={toInteger(trainingRecoverySummary.week1_recovered)} hint="动作后一周内已明显回收的问题。" tone="success" />
              <SummaryCard label="2周已回收" value={toInteger(trainingRecoverySummary.week2_recovered)} hint="两周内完成回收闭环的问题。" tone="success" />
              <SummaryCard label="2周未回收" value={toInteger(trainingRecoverySummary.week2_unrecovered)} hint="说明动作后仍未收敛，需要继续追责或换方案。" tone="warning" />
            </div>
          ) : null}

          {trainingRecoveryRows.length > 0 ? (
            <DataTable
              title="培训 / 整改动作回收跟踪"
              subtitle="把动作后的 1 周 / 2 周回收结果一起迁出来，这块对质培管理最关键。"
              rows={buildTableRows(trainingRecoveryRows, {
                action_date: (row) => toDisplayDate(row.action_date as string | undefined),
                baseline_issue_share: (row) => toPercent(row.baseline_issue_share),
                week1_issue_share: (row) => toPercent(row.week1_issue_share),
                week2_issue_share: (row) => toPercent(row.week2_issue_share),
              })}
              columns={[
                { key: "action_date", label: "动作日期", sortable: true },
                { key: "queue_name", label: "队列", sortable: true },
                { key: "error_type", label: "错误类型", sortable: true },
                { key: "owner_name", label: "Owner", sortable: true },
                { key: "baseline_issue_share", label: "动作当周占比", sortable: true },
                { key: "week1_issue_share", label: "1周后占比", sortable: true },
                { key: "week2_issue_share", label: "2周后占比", sortable: true },
                { key: "recovery_status", label: "回收状态", sortable: true },
              ]}
              emptyText="当前组别暂无培训 / 整改动作回收记录。"
            />
          ) : null}

          <div className="grid grid-2">
            <DataTable
              title="队列下钻"
              rows={buildTableRows(detailRows.queues.slice(0, 12), {
                qa_cnt: (row) => toInteger(row.qa_cnt),
                final_accuracy_rate: (row) => toPercent(row.final_accuracy_rate),
                missjudge_rate: (row) => toPercent(row.missjudge_rate),
              })}
              columns={[
                { key: "queue_name", label: "队列", sortable: true },
                { key: "qa_cnt", label: "质检量", sortable: true },
                { key: "final_accuracy_rate", label: "最终正确率", sortable: true },
                { key: "missjudge_rate", label: "漏判率", sortable: true },
              ]}
              emptyText="当前组别下暂无队列数据。"
            />
            <DataTable
              title="审核人下钻"
              rows={buildTableRows(detailRows.auditors.slice(0, 12), {
                qa_cnt: (row) => toInteger(row.qa_cnt),
                final_accuracy_rate: (row) => toPercent(row.final_accuracy_rate),
                missjudge_rate: (row) => toPercent(row.missjudge_rate),
              })}
              columns={[
                { key: "reviewer_name", label: "审核人", sortable: true },
                { key: "qa_cnt", label: "质检量", sortable: true },
                { key: "final_accuracy_rate", label: "最终正确率", sortable: true },
                { key: "missjudge_rate", label: "漏判率", sortable: true },
              ]}
              emptyText="当前组别下暂无审核人数据。"
            />
          </div>

          <DataTable
            title="问题样本（节选）"
            subtitle={'这里继续保留组别层的常规问题样本，和上面的告警关联样本形成\u201c专项样本 + 常规样本\u201d双视角。'}
            rows={buildTableRows(detailRows.samples, {
              biz_date: (row) => toDisplayDate(row.biz_date as string | undefined),
            })}
            columns={[
              { key: "biz_date", label: "日期", sortable: true },
              { key: "queue_name", label: "队列", sortable: true },
              { key: "reviewer_name", label: "审核人", sortable: true },
              { key: "judge_result", label: "最终判断" },
              { key: "error_type", label: "错误类型", sortable: true },
              { key: "qa_note", label: "备注" },
            ]}
            emptyText="当前组别下暂无问题样本。"
            searchable
          />
        </div>
      ) : null}
    </AppShell>
  );
}
