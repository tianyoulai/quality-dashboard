import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { SmokeLastOk } from "@/components/smoke-last-ok";
import { SummaryCard } from "@/components/summary-card";
import { safeFetchApi } from "@/lib/api";

/**
 * /smoke —— 前端在线冒烟页。
 *
 * 定位：不依赖 jobs/smoke_checks.py 的 postdeploy 脚本，浏览器打开一次就能看到
 *  - 首页依赖的 /dashboard/overview 是否 200 + 有基础数据
 *  - 明细依赖的 /details/filters 是否 200 + 关键选项数组非空
 *  - 新人页依赖的 /newcomers/summary 是否 200 + batches 非空
 *  - 元数据 /meta/date-range 是否拿到有效日期
 *
 * 不做的事：不抓前端渲染后的 HTML（那是 jobs/smoke_checks.py 干的，双份价值不大），
 * 只做接口层最小闭环，保证 "前端页面能拿到数据" 这一层稳定。
 *
 * 每个检查项有一条明确的 status（ok / warn / error）+ 细节，方便截图给后端排障。
 * 同时附带本次接口耗时（latencyMs）和上一次 ok 的时间（localStorage 记），
 * 用来快速回答两个问题："现在慢不慢？" 和 "已经多久没通过了？"。
 */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "在线冒烟",
};

type CheckStatus = "ok" | "warn" | "error";

type CheckResult = {
  key: string;
  name: string;
  target: string;
  status: CheckStatus;
  message: string;
  hint?: string;
  latencyMs: number;
};

function toneOf(status: CheckStatus): "success" | "warning" | "danger" {
  if (status === "ok") return "success";
  if (status === "warn") return "warning";
  return "danger";
}

function labelOf(status: CheckStatus): string {
  if (status === "ok") return "✅ 正常";
  if (status === "warn") return "⚠️ 需关注";
  return "❌ 失败";
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function pickString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/** 统一测耗时的小包装，避免在每个 check 里都写一遍 Date.now()。 */
async function timed<T>(fn: () => Promise<T>): Promise<{ result: T; latencyMs: number }> {
  const t0 = Date.now();
  const result = await fn();
  return { result, latencyMs: Date.now() - t0 };
}

async function checkDateRange(): Promise<CheckResult> {
  const target = "/api/v1/meta/date-range";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "meta", name: "元数据 · 日期范围", target, status: "error", message: error, latencyMs };
  }
  const start = pickString(data?.min_date) || pickString(data?.start);
  const end = pickString(data?.max_date) || pickString(data?.end);
  if (!start || !end) {
    return {
      key: "meta",
      name: "元数据 · 日期范围",
      target,
      status: "warn",
      message: "接口返回成功，但 min_date/max_date 为空。",
      hint: "若数仓刚清库或还没导入任何 fact 数据，会返回空；否则要去看 mart_day_group 是否有行。",
      latencyMs,
    };
  }
  return {
    key: "meta",
    name: "元数据 · 日期范围",
    target,
    status: "ok",
    message: `日期范围 ${start} ~ ${end}`,
    latencyMs,
  };
}

async function checkDashboardOverview(): Promise<CheckResult> {
  const target = "/api/v1/dashboard/overview";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "home", name: "首页 · 经营驾驶舱", target, status: "error", message: error, latencyMs };
  }
  const groups = asArray((data as Record<string, unknown>)?.group_rows);
  if (groups.length === 0) {
    return {
      key: "home",
      name: "首页 · 经营驾驶舱",
      target,
      status: "warn",
      message: "接口成功，但 group_rows 为空。",
      hint: "检查 mart_day_group 是否有当天或最近一天的数据。",
      latencyMs,
    };
  }
  return {
    key: "home",
    name: "首页 · 经营驾驶舱",
    target,
    status: "ok",
    message: `group_rows 返回 ${groups.length} 行。`,
    latencyMs,
  };
}

async function checkDetailsFilters(): Promise<CheckResult> {
  const target = "/api/v1/details/filters";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "details", name: "明细 · 筛选选项", target, status: "error", message: error, latencyMs };
  }
  const groupNames = asArray((data as Record<string, unknown>)?.group_names);
  const queueNames = asArray((data as Record<string, unknown>)?.queue_names);
  if (groupNames.length === 0 || queueNames.length === 0) {
    return {
      key: "details",
      name: "明细 · 筛选选项",
      target,
      status: "warn",
      message: `group_names=${groupNames.length}，queue_names=${queueNames.length}。`,
      hint: "任一为空都会让明细筛选变半残，先去看 fact_qa_event 是否有足够的 sub_biz/queue_name。",
      latencyMs,
    };
  }
  return {
    key: "details",
    name: "明细 · 筛选选项",
    target,
    status: "ok",
    message: `业务线 ${groupNames.length} 个 / 队列 ${queueNames.length} 个。`,
    latencyMs,
  };
}

async function checkNewcomersSummary(): Promise<CheckResult> {
  const target = "/api/v1/newcomers/summary";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "newcomers", name: "新人 · 批次摘要", target, status: "error", message: error, latencyMs };
  }
  const batches = asArray((data as Record<string, unknown>)?.batches);
  if (batches.length === 0) {
    return {
      key: "newcomers",
      name: "新人 · 批次摘要",
      target,
      status: "warn",
      message: "接口成功，但 batches 为空。",
      hint: "通常是新人批次表还没建或还没映射到 fact_newcomer_qa，看 dim_newcomer_member 是否有数据。",
      latencyMs,
    };
  }
  return {
    key: "newcomers",
    name: "新人 · 批次摘要",
    target,
    status: "ok",
    message: `当前共 ${batches.length} 个新人批次。`,
    latencyMs,
  };
}

async function checkNewcomersAggregates(): Promise<CheckResult> {
  const target = "/api/v1/newcomers/aggregates";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return {
      key: "newcomers-agg",
      name: "新人 · 聚合指标",
      target,
      status: "error",
      message: error,
      latencyMs,
    };
  }
  const rc = ((data as Record<string, unknown>)?.row_count ?? {}) as Record<string, unknown>;
  const members = Number(rc.members ?? 0);
  const batchCompare = Number(rc.batch_compare ?? 0);
  const combinedDaily = Number(rc.combined_daily ?? 0);
  // members>0 是详情页能不能出名单的下限；batch_compare>0 是新人对标卡能不能渲染
  if (members === 0 || batchCompare === 0) {
    return {
      key: "newcomers-agg",
      name: "新人 · 聚合指标",
      target,
      status: "warn",
      message: `members=${members}，batch_compare=${batchCompare}，combined_daily=${combinedDaily}。`,
      hint: "members=0 会让详情页空；batch_compare=0 说明没有能跟正式队列对比的基础数据。先查 fact_newcomer_qa/fact_qa_event 是否齐。",
      latencyMs,
    };
  }
  return {
    key: "newcomers-agg",
    name: "新人 · 聚合指标",
    target,
    status: "ok",
    message: `members=${members}，batch_compare=${batchCompare}，combined_daily=${combinedDaily}。`,
    latencyMs,
  };
}


// ==================== 新人页补充检查（Phase 4 收口新增） ====================

/** 拿到 summary 后用第一个 batch_name 查 members —— 决定页面能否渲染成员列表和筛选器 */
async function checkNewcomersMembers(): Promise<CheckResult> {
  // 先拿一个可用 batch_name
  const { result: sumResult } = await timed(() => safeFetchApi<Record<string, unknown>>("/api/v1/newcomers/summary"));
  const batches = asArray(sumResult.data?.batches);
  const firstBatch = batches.length > 0 ? pickString((batches[0] as Record<string, unknown>).batch_name) : "";
  if (!firstBatch) {
    return {
      key: "newcomers-members",
      name: "新人 · 成员列表",
      target: "/api/v1/newcomers/members?batch_names=[...]",
      status: "warn",
      message: "无可用批次，跳过 members 接口检查。",
      latencyMs: sumResult.latencyMs ?? 0,
    };
  }

  const target = `/api/v1/newcomers/members?batch_names=${encodeURIComponent(firstBatch)}`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "newcomers-members", name: "新人 · 成员列表", target, status: "error", message: error, latencyMs };
  }
  const items = asArray(data?.items);
  if (items.length === 0) {
    return {
      key: "newcomers-members",
      name: "新人 · 成员列表",
      target,
      status: "warn",
      message: `批次 ${firstBatch} 下无成员数据。`,
      hint: "dim_newcomer_batch 可能没建好或该批次已清空；新人页筛选器和趋势图会全空。",
      latencyMs,
    };
  }
  return {
    key: "newcomers-members",
    name: "新人 · 成员列表",
    target,
    status: "ok",
    message: `批次 ${firstBatch} 下 ${items.length} 名成员。`,
    latencyMs,
  };
}

/** 正式阶段趋势 —— 新人页"培训期 vs 正式上线"对比的核心数据源 */
async function checkNewcomersFormalDaily(): Promise<CheckResult> {
  // 先拿到一个 reviewer_alias（从 members）
  const { result: sumResult } = await timed(() => safeFetchApi<Record<string, unknown>>("/api/v1/newcomers/summary"));
  const batches = asArray(sumResult.data?.batches);
  const firstBatch = batches.length > 0 ? pickString((batches[0] as Record<string, unknown>).batch_name) : "";
  if (!firstBatch) {
    return {
      key: "newcomers-formal",
      name: "新人 · 正式阶段趋势",
      target: "/api/v1/newcomers/formal-daily?reviewer_aliases=[...]",
      status: "warn",
      message: "无可用批次，跳过正式阶段接口检查。",
      latencyMs: sumResult.latencyMs ?? 0,
    };
  }
  // 用第一个 batch 拿 members 再取 alias
  const { result: memResult } = await timed(() =>
    safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/members?batch_names=${encodeURIComponent(firstBatch)}`)
  );
  const members = asArray(memResult.data?.items);
  const firstAlias = members.length > 0 ? pickString((members[0] as Record<string, unknown>).reviewer_alias) : "";
  if (!firstAlias) {
    return {
      key: "newcomers-formal",
      name: "新人 · 正式阶段趋势",
      target: "/api/v1/newcomers/formal-daily",
      status: "warn",
      message: `批次 ${firstBatch} 无可用 reviewer_alias。`,
      hint: "可能 dim_newcomer_batch 的 reviewer_alias 字段为空。",
      latencyMs: memResult.latencyMs ?? 0,
    };
  }

  const target = `/api/v1/newcomers/formal-daily?reviewer_aliases=${encodeURIComponent(firstAlias)}`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "newcomers-formal", name: "新人 · 正式阶段趋势", target, status: "error", message: error, latencyMs };
  }
  const items = asArray(data?.items);
  if (items.length === 0) {
    return {
      key: "newcomers-formal",
      name: "新人 · 正式阶段趋势",
      target,
      status: "warn",
      message: `${firstAlias} 无正式阶段数据（可能尚未毕业或 mart_day_auditor 无记录）。`,
      hint: `新人对标卡的"正式上线"tab 会为空，这是正常的如果该人还在培训期。`,
      latencyMs,
    };
  }
  return {
    key: "newcomers-formal",
    name: "新人 · 正式阶段趋势",
    target,
    status: "ok",
    message: `${firstAlias} 正式阶段 ${items.length} 条日记录。`,
    latencyMs,
  };
}

/** 个人错误明细 —— 详情下钻面板的数据源 */
async function checkNewcomersPersonDetail(): Promise<CheckResult> {
  const { result: sumResult } = await timed(() => safeFetchApi<Record<string, unknown>>("/api/v1/newcomers/summary"));
  const batches = asArray(sumResult.data?.batches);
  const firstBatch = batches.length > 0 ? pickString((batches[0] as Record<string, unknown>).batch_name) : "";
  if (!firstBatch) {
    return {
      key: "newcomers-person",
      name: "新人 · 个人明细",
      target: "/api/v1/newcomers/person-detail?reviewer_alias=...",
      status: "warn",
      message: "无可用批次，跳过个人明细接口检查。",
      latencyMs: sumResult.latencyMs ?? 0,
    };
  }
  const { result: memResult } = await timed(() =>
    safeFetchApi<Record<string, unknown>>(`/api/v1/newcomers/members?batch_names=${encodeURIComponent(firstBatch)}`)
  );
  const members = asArray(memResult.data?.items);
  const firstAlias = members.length > 0 ? pickString((members[0] as Record<string, unknown>).reviewer_alias) : "";
  if (!firstAlias) {
    return {
      key: "newcomers-person",
      name: "新人 · 个人明细",
      target: "/api/v1/newcomers/person-detail",
      status: "warn",
      message: "无可用 reviewer_alias，跳过个人明细。",
      latencyMs: memResult.latencyMs ?? 0,
    };
  }

  const target = `/api/v1/newcomers/person-detail?reviewer_alias=${encodeURIComponent(firstAlias)}&limit=20`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "newcomers-person", name: "新人 · 个人明细", target, status: "error", message: error, latencyMs };
  }
  const items = asArray(data?.items);
  return {
    key: "newcomers-person",
    name: "新人 · 个人明细",
    target,
    status: items.length > 0 ? "ok" : "warn",
    message: `${firstAlias} 最近 ${items.length} 条质检记录。`,
    hint: items.length === 0 ? "此人可能全部正确(is_correct=1)，没有错误样本可展示。" : undefined,
    latencyMs,
  };
}

/** 数仓新鲜度：max_date 距今 <=1 天绿、<=3 天黄、超过红。 */
async function checkWarehouseFreshness(): Promise<CheckResult> {
  const target = "/api/v1/meta/date-range";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "freshness", name: "数仓 · 数据新鲜度", target, status: "error", message: error, latencyMs };
  }
  const end = pickString(data?.max_date) || pickString(data?.end);
  if (!end) {
    return {
      key: "freshness",
      name: "数仓 · 数据新鲜度",
      target,
      status: "warn",
      message: "max_date 为空，无法判断新鲜度。",
      hint: "通常是 mart_day_group 还没回灌；看 jobs/daily_sync 最近一次是否跑过。",
      latencyMs,
    };
  }
  const endDate = new Date(`${end}T00:00:00`);
  const today = new Date();
  const diffDays = Math.floor((today.getTime() - endDate.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) {
    return {
      key: "freshness",
      name: "数仓 · 数据新鲜度",
      target,
      status: "warn",
      message: `max_date=${end}，居然在未来？`,
      hint: "多半是服务器/导入源的时区错位，顺手看下 ingest 脚本。",
      latencyMs,
    };
  }
  if (diffDays > 3) {
    return {
      key: "freshness",
      name: "数仓 · 数据新鲜度",
      target,
      status: "error",
      message: `max_date=${end}，距今 ${diffDays} 天。数据已过期。`,
      hint: "日更任务挂了；先去看 launchd / jobs 日志。",
      latencyMs,
    };
  }
  if (diffDays > 1) {
    return {
      key: "freshness",
      name: "数仓 · 数据新鲜度",
      target,
      status: "warn",
      message: `max_date=${end}，距今 ${diffDays} 天。昨天的数据没到。`,
      hint: "一般是 00:00 跑批延迟或失败；明细页会看到断档。",
      latencyMs,
    };
  }
  return {
    key: "freshness",
    name: "数仓 · 数据新鲜度",
    target,
    status: "ok",
    message: `max_date=${end}，距今 ${diffDays} 天，数据新鲜。`,
    latencyMs,
  };
}

// ==================== 内检看板检查（Phase 5 新增） ====================

/** 拿到 meta/date-range 的 max_date 作为内检接口的默认日期 */
async function fetchEffectiveDate(): Promise<string> {
  const { result } = await timed(() => safeFetchApi<Record<string, unknown>>("/api/v1/meta/date-range"));
  const end = pickString(result.data?.max_date) || pickString(result.data?.end);
  if (end) return end;
  // fallback to today
  return new Date().toISOString().slice(0, 10);
}

/** /api/v1/internal/summary — 核心指标卡（5 卡 + 环比） */
async function checkInternalSummary(): Promise<CheckResult> {
  const sd = await fetchEffectiveDate();
  const target = `/api/v1/internal/summary?selected_date=${sd}&with_prev=true`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "internal-summary", name: "内检 · 核心指标", target, status: "error", message: error, latencyMs };
  }
  const metrics = (data as Record<string, unknown>)?.metrics as Record<string, unknown> | null;
  if (!metrics) {
    return {
      key: "internal-summary",
      name: "内检 · 核心指标",
      target,
      status: "warn",
      message: `日期 ${sd} 无内检数据（metrics=null）。`,
      hint: "可能当天无 qc_module='internal' 的 fact_qa_event 记录，或数仓尚未回灌。",
      latencyMs,
    };
  }
  const qaCnt = Number(metrics.qa_cnt ?? 0);
  const rawAcc = Number(metrics.raw_accuracy_rate ?? 0);
  const finalAcc = Number(metrics.final_accuracy_rate ?? 0);
  return {
    key: "internal-summary",
    name: "内检 · 核心指标",
    target,
    status: "ok",
    message: `质检量 ${qaCnt.toLocaleString()}，原始正确率 ${rawAcc.toFixed(2)}%，最终正确率 ${finalAcc.toFixed(2)}%。`,
    latencyMs,
  };
}

/** /api/v1/internal/queues — 队列正确率排名 */
async function checkInternalQueues(): Promise<CheckResult> {
  const sd = await fetchEffectiveDate();
  const target = `/api/v1/internal/queues?selected_date=${sd}`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "internal-queues", name: "内检 · 队列排名", target, status: "error", message: error, latencyMs };
  }
  const items = asArray(data?.items);
  return {
    key: "internal-queues",
    name: "内检 · 队列排名",
    target,
    status: items.length > 0 ? "ok" : "warn",
    message: `返回 ${items.length} 个队列。`,
    hint: items.length === 0 ? "队列表为空说明当天无内检数据；内检页队列排名会显示空状态。" : undefined,
    latencyMs,
  };
}

/** /api/v1/internal/trend — 日级正确率趋势 */
async function checkInternalTrend(): Promise<CheckResult> {
  const sd = await fetchEffectiveDate();
  const d = new Date(sd);
  d.setDate(d.getDate() - 6);
  const start = d.toISOString().slice(0, 10);
  const target = `/api/v1/internal/trend?start_date=${start}&end_date=${sd}`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "internal-trend", name: "内检 · 正确率趋势", target, status: "error", message: error, latencyMs };
  }
  const series = asArray(data?.series);
  return {
    key: "internal-trend",
    name: "内检 · 正确率趋势",
    target,
    status: series.length > 0 ? "ok" : "warn",
    message: `趋势区间 ${start} ~ ${sd}，${series.length} 个数据点。`,
    hint: series.length === 0 ? "趋势图为空，折线图无法渲染。" : undefined,
    latencyMs,
  };
}

/** /api/v1/internal/reviewers — 审核人明细（含错判/漏判） */
async function checkInternalReviewers(): Promise<CheckResult> {
  const sd = await fetchEffectiveDate();
  const target = `/api/v1/internal/reviewers?selected_date=${sd}&limit=30`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "internal-reviewers", name: "内检 · 审核人明细", target, status: "error", message: error, latencyMs };
  }
  const items = asArray(data?.items);
  return {
    key: "internal-reviewers",
    name: "内检 · 审核人明细",
    target,
    status: items.length > 0 ? "ok" : "warn",
    message: `返回 ${items.length} 名审核人。`,
    hint: items.length === 0 ? "审核人表为空，内检页审核人分析面板全空。" : undefined,
    latencyMs,
  };
}

/** /api/v1/internal/error-types — 错误标签分布 TOP10 */
async function checkInternalErrorTypes(): Promise<CheckResult> {
  const sd = await fetchEffectiveDate();
  const target = `/api/v1/internal/error-types?selected_date=${sd}&top_n=10`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "internal-error-types", name: "内检 · 错误标签 TOP", target, status: "error", message: error, latencyMs };
  }
  const items = asArray(data?.items);
  const totalErrors = Number((data as Record<string, unknown>)?.total_errors ?? 0);
  return {
    key: "internal-error-types",
    name: "内检 · 错误标签 TOP",
    target,
    status: items.length > 0 ? "ok" : "warn",
    message: `${items.length} 个标签，总错误量 ${totalErrors}。`,
    hint: items.length === 0 ? "错误标签为空，说明当日全部正确（error_type 无数据）或无内检记录。" : undefined,
    latencyMs,
  };
}

/** /api/v1/internal/qa-owners — 质检员工作量 */
async function checkInternalQaOwners(): Promise<CheckResult> {
  const sd = await fetchEffectiveDate();
  const target = `/api/v1/internal/qa-owners?selected_date=${sd}&limit=20`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "internal-qa-owners", name: "内检 · 质检员工作量", target, status: "error", message: error, latencyMs };
  }
  const items = asArray(data?.items);
  return {
    key: "internal-qa-owners",
    name: "内检 · 质检员工作量",
    target,
    status: items.length > 0 ? "ok" : "warn",
    message: `返回 ${items.length} 名质检员。`,
    hint: items.length === 0 ? "质检员为空，内检页质检员工作量表全空。" : undefined,
    latencyMs,
  };
}


/** 根据耗时粗略给个直观 tone：200ms 以内绿，800ms 内中性，超过则黄。 */
function latencyLabel(ms: number): string {
  if (ms < 200) return `⚡ ${ms} ms`;
  if (ms < 800) return `${ms} ms`;
  return `🐢 ${ms} ms`;
}

export default async function SmokePage() {
  const checks = await Promise.all([
    checkDateRange(),
    checkWarehouseFreshness(),
    checkDashboardOverview(),
    checkDetailsFilters(),
    checkNewcomersSummary(),
    checkNewcomersAggregates(),
    // Phase 4 收口新增 —— 新人页核心数据链路
    checkNewcomersMembers(),
    checkNewcomersFormalDaily(),
    checkNewcomersPersonDetail(),
    // Phase 5 新增 —— 内检看板（/internal）6 个接口全覆盖
    checkInternalSummary(),
    checkInternalQueues(),
    checkInternalTrend(),
    checkInternalReviewers(),
    checkInternalErrorTypes(),
    checkInternalQaOwners(),
  ]);

  const errorCount = checks.filter((item) => item.status === "error").length;
  const warnCount = checks.filter((item) => item.status === "warn").length;
  const okCount = checks.filter((item) => item.status === "ok").length;
  const overallTone: "success" | "warning" | "danger" =
    errorCount > 0 ? "danger" : warnCount > 0 ? "warning" : "success";
  const overallLabel =
    errorCount > 0 ? "有核心接口失败，前端页面大概率不可用。" : warnCount > 0 ? "接口都通，但有数据缺口，先排数仓。" : "全部通过，三页核心数据链路正常。";

  const totalLatency = checks.reduce((sum, item) => sum + item.latencyMs, 0);
  const maxLatency = checks.reduce((max, item) => (item.latencyMs > max ? item.latencyMs : max), 0);

  return (
    <AppShell
      currentPath="/smoke"
      title="在线冒烟"
      subtitle="一次性打 15 个关键接口，覆盖首页/明细/新人/内检四页核心数据链路 + 数仓新鲜度。"
    >
      <div className="grid grid-4">
        <SummaryCard label="总检查数" value={checks.length} hint="每项对应一个前端页面强依赖的接口。" />
        <SummaryCard label="通过" value={okCount} tone="success" hint="接口 200 且关键字段非空。" />
        <SummaryCard label="需关注" value={warnCount} tone={warnCount > 0 ? "warning" : "neutral"} hint="接口通但数据为空，多半是数仓侧问题。" />
        <SummaryCard label="失败" value={errorCount} tone={errorCount > 0 ? "danger" : "success"} hint="接口直接挂掉，先看 API 日志或服务是否在跑。" />
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">整体结论</h3>
            <p className="panel-subtitle">只是 live 快拍，不持久化；刷新页面即重新跑一次。</p>
          </div>
          <span className={`status-pill ${toneOf(errorCount > 0 ? "error" : warnCount > 0 ? "warn" : "ok")}`}>
            {overallTone === "success" ? "✅ 一切正常" : overallTone === "warning" ? "⚠️ 部分接口有数据缺口" : "❌ 有接口失败"}
          </span>
        </div>
        <div className="info-banner">{overallLabel}</div>
        <div className="kpi-row" style={{ marginTop: 8 }}>
          <span className="kpi-pill">总耗时 {totalLatency} ms</span>
          <span className="kpi-pill">最慢一项 {maxLatency} ms</span>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">明细结果</h3>
            <p className="panel-subtitle">按前端页面划分，逐项列出接口路径、状态、耗时与上次成功时间。</p>
          </div>
        </div>
        <div className="section-stack">
          {checks.map((item) => (
            <article key={item.key} className={`comparison-card ${toneOf(item.status)}`}>
              <div className="focus-candidate-title-row">
                <div className="comparison-card-title">{item.name}</div>
                <span className={`status-pill ${toneOf(item.status)}`}>{labelOf(item.status)}</span>
              </div>
              <div className="comparison-card-summary">{item.message}</div>
              <div className="kpi-row">
                <span className="kpi-pill">GET {item.target}</span>
                <span className="kpi-pill">{latencyLabel(item.latencyMs)}</span>
                <SmokeLastOk checkKey={item.key} status={item.status} latencyMs={item.latencyMs} />
              </div>
              {item.hint ? <div className="panel-subtitle" style={{ marginTop: 6 }}>💡 {item.hint}</div> : null}
            </article>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
