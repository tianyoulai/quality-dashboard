import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { SmokeLastOk } from "@/components/smoke-last-ok";
import { SummaryCard } from "@/components/summary-card";
import { safeFetchApi } from "@/lib/api";

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

async function timed<T>(fn: () => Promise<T>): Promise<{ result: T; latencyMs: number }> {
  const t0 = Date.now();
  const result = await fn();
  return { result, latencyMs: Date.now() - t0 };
}

async function fetchEffectiveDate(): Promise<string> {
  const { result } = await timed(() => safeFetchApi<Record<string, unknown>>("/api/v1/meta/date-range"));
  const { data } = result;
  return pickString(data?.default_selected_date) || pickString(data?.max_date) || new Date().toISOString().slice(0, 10);
}

async function checkDateRange(): Promise<CheckResult> {
  const target = "/api/v1/meta/date-range";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "meta", name: "元数据 · 日期范围", target, status: "error", message: error, latencyMs };
  }
  const start = pickString(data?.min_date);
  const end = pickString(data?.max_date);
  const defaultDate = pickString(data?.default_selected_date);
  if (!start || !end) {
    return {
      key: "meta",
      name: "元数据 · 日期范围",
      target,
      status: "warn",
      message: "接口返回成功，但 min_date/max_date 为空。",
      hint: "通常说明基础事实表未导入完成，首页和趋势类页面会失去日期锚点。",
      latencyMs,
    };
  }
  return {
    key: "meta",
    name: "元数据 · 日期范围",
    target,
    status: "ok",
    message: `日期范围 ${start} ~ ${end}，默认日期 ${defaultDate || end}`,
    latencyMs,
  };
}

async function checkWarehouseFreshness(): Promise<CheckResult> {
  const target = "/api/v1/meta/date-range";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "freshness", name: "数仓 · 数据新鲜度", target, status: "error", message: error, latencyMs };
  }
  const end = pickString(data?.max_date);
  if (!end) {
    return {
      key: "freshness",
      name: "数仓 · 数据新鲜度",
      target,
      status: "warn",
      message: "max_date 为空，无法判断数据新鲜度。",
      latencyMs,
    };
  }
  const endDate = new Date(`${end}T00:00:00`);
  const today = new Date();
  const diffDays = Math.floor((today.getTime() - endDate.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays <= 1) {
    return {
      key: "freshness",
      name: "数仓 · 数据新鲜度",
      target,
      status: "ok",
      message: `最新数据日期 ${end}，距今 ${diffDays} 天。`,
      latencyMs,
    };
  }
  if (diffDays <= 3) {
    return {
      key: "freshness",
      name: "数仓 · 数据新鲜度",
      target,
      status: "warn",
      message: `最新数据日期 ${end}，距今 ${diffDays} 天。`,
      hint: "数据并未中断，但已有轻微滞后。",
      latencyMs,
    };
  }
  return {
    key: "freshness",
    name: "数仓 · 数据新鲜度",
    target,
    status: "error",
    message: `最新数据日期 ${end}，距今 ${diffDays} 天。`,
    hint: "需要优先检查 ETL / 定时任务是否异常。",
    latencyMs,
  };
}

async function checkDashboardOverview(): Promise<CheckResult> {
  const selectedDate = await fetchEffectiveDate();
  const target = `/api/v1/dashboard/overview?grain=day&selected_date=${selectedDate}`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "home", name: "首页 · 经营驾驶舱", target, status: "error", message: error, latencyMs };
  }
  const payload = (data?.data ?? data) as Record<string, unknown>;
  const groupRows = asArray(payload?.group_rows);
  if (groupRows.length === 0) {
    return {
      key: "home",
      name: "首页 · 经营驾驶舱",
      target,
      status: "warn",
      message: "接口成功，但 group_rows 为空。",
      hint: "首页可打开，但组别经营卡会没有内容。",
      latencyMs,
    };
  }
  return {
    key: "home",
    name: "首页 · 经营驾驶舱",
    target,
    status: "ok",
    message: `首页返回 ${groupRows.length} 个组别数据块。`,
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
  const payload = (data?.data ?? data) as Record<string, unknown>;
  const groups = asArray(payload?.groups ?? payload?.group_names);
  const queues = asArray(payload?.queues ?? payload?.queue_names);
  if (groups.length === 0 || queues.length === 0) {
    return {
      key: "details",
      name: "明细 · 筛选选项",
      target,
      status: "warn",
      message: `groups=${groups.length}，queues=${queues.length}。`,
      hint: "明细页能打开，但筛选器不完整，实际使用会受限。",
      latencyMs,
    };
  }
  return {
    key: "details",
    name: "明细 · 筛选选项",
    target,
    status: latencyMs > 5000 ? "warn" : "ok",
    message: `业务线 ${groups.length} 个，队列 ${queues.length} 个。`,
    hint: latencyMs > 5000 ? "接口可用，但耗时偏长，建议继续做缓存/查询优化。" : undefined,
    latencyMs,
  };
}

async function checkNewcomersOverview(): Promise<CheckResult> {
  const target = "/api/v1/newcomers/overview";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "newcomers-overview", name: "新人 · 总览指标", target, status: "error", message: error, latencyMs };
  }
  const payload = (data?.data ?? data) as Record<string, unknown>;
  const avgAccuracy = Number(payload?.avg_accuracy ?? 0);
  return {
    key: "newcomers-overview",
    name: "新人 · 总览指标",
    target,
    status: "ok",
    message: `综合正确率 ${avgAccuracy.toFixed(2)}%，已结业 ${Number(payload?.graduated_count ?? 0)} 人。`,
    latencyMs,
  };
}

async function checkNewcomersBatches(): Promise<CheckResult> {
  const target = "/api/v1/newcomers/batches?status=all";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "newcomers-batches", name: "新人 · 批次列表", target, status: "error", message: error, latencyMs };
  }
  const payload = (data?.data ?? data) as Record<string, unknown>;
  const batches = asArray(payload?.batches);
  const zeroQa = batches.filter((item) => Number((item as Record<string, unknown>)?.qa_cnt ?? 0) === 0).length;
  if (batches.length === 0) {
    return {
      key: "newcomers-batches",
      name: "新人 · 批次列表",
      target,
      status: "warn",
      message: "当前没有任何新人批次。",
      hint: "新人页可打开，但没有可分析对象。",
      latencyMs,
    };
  }
  return {
    key: "newcomers-batches",
    name: "新人 · 批次列表",
    target,
    status: zeroQa > 0 ? "warn" : "ok",
    message: `共 ${batches.length} 个批次，其中 ${zeroQa} 个批次尚未接通质检数据。`,
    hint: zeroQa > 0 ? "这不是前端故障，通常是 dim_newcomer_batch 与 fact_newcomer_qa 姓名未对齐。" : undefined,
    latencyMs,
  };
}

async function checkInternalSummary(): Promise<CheckResult> {
  const selectedDate = await fetchEffectiveDate();
  const target = `/api/v1/internal/summary?selected_date=${selectedDate}`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "internal", name: "内检 · 核心指标", target, status: "error", message: error, latencyMs };
  }
  const payload = (data?.data ?? data) as Record<string, unknown>;
  const metrics = (payload?.metrics ?? {}) as Record<string, unknown>;
  return {
    key: "internal",
    name: "内检 · 核心指标",
    target,
    status: Number(metrics.qa_cnt ?? 0) > 0 ? "ok" : "warn",
    message: `质检量 ${Number(metrics.qa_cnt ?? 0).toLocaleString()}，最终正确率 ${Number(metrics.final_accuracy_rate ?? 0).toFixed(2)}%。`,
    hint: Number(metrics.qa_cnt ?? 0) === 0 ? "内检页可打开，但当天无核心数据。" : undefined,
    latencyMs,
  };
}

async function checkExternalSummary(): Promise<CheckResult> {
  const selectedDate = await fetchEffectiveDate();
  const target = `/api/v1/external/summary?date=${selectedDate}`;
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "external", name: "外检 · 核心指标", target, status: "error", message: error, latencyMs };
  }
  const payload = (data?.data ?? data) as Record<string, unknown>;
  const hasData = Boolean(payload?.has_data);
  return {
    key: "external",
    name: "外检 · 核心指标",
    target,
    status: hasData ? "ok" : "warn",
    message: `抽检量 ${Number(payload?.total_count ?? 0).toLocaleString()}，正确率 ${Number(payload?.correct_rate ?? 0).toFixed(2)}%。`,
    hint: hasData ? undefined : "外检页可打开，但所选日期没有数据。",
    latencyMs,
  };
}

async function checkBadCaseStats(): Promise<CheckResult> {
  const target = "/api/v1/badcase/stats";
  const { result, latencyMs } = await timed(() => safeFetchApi<Record<string, unknown>>(target));
  const { data, error } = result;
  if (error) {
    return { key: "badcase", name: "Bad Case · 统计摘要", target, status: "error", message: error, latencyMs };
  }
  const payload = (data?.data ?? data) as Record<string, unknown>;
  const total = Number(payload?.total ?? 0);
  return {
    key: "badcase",
    name: "Bad Case · 统计摘要",
    target,
    status: total > 0 ? "ok" : "warn",
    message: `案例总数 ${total}，错误类型分布 ${asArray(payload?.error_type_dist).length} 项。`,
    hint: total === 0 ? "Bad Case 页面会空白，需检查 Excel 缓存源文件。" : undefined,
    latencyMs,
  };
}

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
    checkNewcomersOverview(),
    checkNewcomersBatches(),
    checkInternalSummary(),
    checkExternalSummary(),
    checkBadCaseStats(),
  ]);

  const errorCount = checks.filter((item) => item.status === "error").length;
  const warnCount = checks.filter((item) => item.status === "warn").length;
  const okCount = checks.filter((item) => item.status === "ok").length;
  const overallTone: "success" | "warning" | "danger" =
    errorCount > 0 ? "danger" : warnCount > 0 ? "warning" : "success";
  const overallLabel =
    errorCount > 0 ? "仍有核心接口失败，页面链路不完整。" : warnCount > 0 ? "接口整体可用，但存在数据缺口或性能问题。" : "全部通过，主页面核心链路正常。";

  const totalLatency = checks.reduce((sum, item) => sum + item.latencyMs, 0);
  const maxLatency = checks.reduce((max, item) => (item.latencyMs > max ? item.latencyMs : max), 0);

  return (
    <AppShell
      currentPath="/smoke"
      title="在线冒烟"
      subtitle="用当前真实页面依赖的接口做轻量体检，优先发现接口失败、数据缺口和性能慢点。"
    >
      <div className="grid grid-4">
        <SummaryCard label="总检查数" value={checks.length} hint="每项对应当前页面真实依赖的一条核心接口。" />
        <SummaryCard label="通过" value={okCount} tone="success" hint="接口 200 且关键字段非空。" />
        <SummaryCard label="需关注" value={warnCount} tone={warnCount > 0 ? "warning" : "neutral"} hint="接口通但存在慢查询、空数据或部分未接通。" />
        <SummaryCard label="失败" value={errorCount} tone={errorCount > 0 ? "danger" : "success"} hint="接口直接失败，优先修。" />
      </div>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h3 className="panel-title">整体结论</h3>
            <p className="panel-subtitle">基于当前实际在用的首页 / 明细 / 新人 / 内检 / 外检 / Bad Case 主链路。</p>
          </div>
          <span className={`status-pill ${toneOf(errorCount > 0 ? "error" : warnCount > 0 ? "warn" : "ok")}`}>
            {overallTone === "success" ? "✅ 一切正常" : overallTone === "warning" ? "⚠️ 有待关注项" : "❌ 有接口失败"}
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
            <p className="panel-subtitle">逐项展示接口状态、路径、耗时与上次成功时间。</p>
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
