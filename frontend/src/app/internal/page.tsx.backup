import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { BarListCard } from "@/components/bar-list-card";
import { CollapsiblePanel } from "@/components/collapsible-panel";
import { DataTable } from "@/components/data-table";
import { LineChartCard } from "@/components/line-chart-card";
import { SummaryCard } from "@/components/summary-card";
import { safeFetchApi } from "@/lib/api";
import { buildTableRows } from "@/lib/table-rows";
import { pickText, toInteger, toNumber, toDateInputValue } from "@/lib/formatters";

export const metadata: Metadata = {
  title: "内检看板",
};

type SearchParams = Record<string, string | string[] | undefined>;

type PageProps = {
  searchParams?: Promise<SearchParams>;
};

function readParams(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function getRows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

/** 正确率数值 → tone 映射：>=目标绿，>=目标-5 黄，否则红 */
function accTone(rate: number, target = 98): "success" | "warning" | "danger" | "neutral" {
  if (!Number.isFinite(rate)) return "neutral";
  if (rate >= target) return "success";
  if (rate >= target - 5) return "warning";
  return "danger";
}

export default async function InternalPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};

  // ── 1. 取日期参数 & 元数据 ──
  const metaResult = await safeFetchApi<Record<string, unknown>>("/api/v1/meta/date-range");
  const maxDate = toDateInputValue(metaResult.data?.max_date as string | undefined);
  const selectedDate = readParams(params.selected_date) || maxDate;

  // 趋势区间：默认近 7 天
  const d = selectedDate ? new Date(`${selectedDate}T00:00:00`) : new Date();
  d.setDate(d.getDate() - 6);
  const trendStart = d.toISOString().slice(0, 10);
  const trendEnd = selectedDate || new Date().toISOString().slice(0, 10);

  // ── 2. 并发请求全部 6 个内检接口 ──
  const [
    summaryResult,
    queuesResult,
    trendResult,
    reviewersResult,
    errorTypesResult,
    qaOwnersResult,
  ] = await Promise.all([
    safeFetchApi<Record<string, unknown>>(`/api/v1/internal/summary?selected_date=${selectedDate}&with_prev=true`),
    safeFetchApi<Record<string, unknown>>(`/api/v1/internal/queues?selected_date=${selectedDate}`),
    safeFetchApi<Record<string, unknown>>(`/api/v1/internal/trend?start_date=${trendStart}&end_date=${trendEnd}`),
    safeFetchApi<Record<string, unknown>>(`/api/v1/internal/reviewers?selected_date=${selectedDate}&limit=50`),
    safeFetchApi<Record<string, unknown>>(`/api/v1/internal/error-types?selected_date=${selectedDate}&top_n=10`),
    safeFetchApi<Record<string, unknown>>(`/api/v1/internal/qa-owners?selected_date=${selectedDate}&limit=20`),
  ]);

  // ── 3. 解析 summary ──
  const summaryData = (summaryResult.data ?? {}) as Record<string, unknown>;
  const metrics = (summaryData.metrics as Record<string, number | null>) ?? null;
  const prevData = (summaryData.prev as Record<string, number | null> | undefined) ?? null;
  const targetRate = toNumber(summaryData.target_rate); // 目标正确率
  const hasData = metrics !== null;

  // ── 4. 解析 queues ──
  const queueItems = getRows((queuesResult.data as Record<string, unknown>)?.items);

  // ── 5. 解析 trend ──
  const trendSeries = getRows((trendResult.data as Record<string, unknown>)?.series);

  // ── 6. 解析 reviewers ──
  const reviewerItems = getRows((reviewersResult.data as Record<string, unknown>)?.items);

  // ── 7. 解析 error-types ──
  const errorTypeItems = getRows((errorTypesResult.data as Record<string, unknown>)?.items);
  const totalErrors = toNumber((errorTypesResult.data as Record<string, unknown>)?.total_errors);

  // ── 8. 解析 qa-owners ──
  const qaOwnerItems = getRows((qaOwnersResult.data as Record<string, unknown>)?.items);

  // ════════════════════════════════════════════════════════
  // RENDER
  // ════════════════════════════════════════════════════════

  /** 环比 delta 格式化 */
  function fmtDelta(val: number | null | undefined, isPct = false): string {
    if (val === null || val === undefined) return "";
    const prefix = val > 0 ? "+" : "";
    return `${prefix}${isPct ? val.toFixed(2) + "pp" : val.toLocaleString()}`;
  }

  /** 指标卡区域 */
  const summarySection: ReactNode = hasData ? (
    <div className="grid grid-4">
      <SummaryCard
        label="质检总量"
        value={toInteger(metrics.qa_cnt)}
        hint="当日 qc_module=internal 的质检记录总数"
        tone="neutral"
        delta={prevData ? fmtDelta(prevData.qa_delta) : undefined}
      />
      <SummaryCard
        label="原始正确率"
        value={`${toNumber(metrics.raw_accuracy_rate).toFixed(2)}%`}
        hint={`目标 ${targetRate}%`}
        tone={accTone(toNumber(metrics.raw_accuracy_rate), targetRate)}
        delta={prevData ? fmtDelta(prevData.acc_delta_pp, true) : undefined}
      />
      <SummaryCard
        label="最终正确率"
        value={`${toNumber(metrics.final_accuracy_rate).toFixed(2)}%`}
        hint="经申诉复核后的最终口径"
        tone={accTone(toNumber(metrics.final_accuracy_rate), targetRate)}
      />
      <SummaryCard
        label="错误量"
        value={toInteger(metrics.error_count)}
        hint={`含错判 ${toInteger(metrics.misjudge_count)} / 漏判 ${toInteger(metrics.missjudge_count)}`}
        tone={toNumber(metrics.error_count) > 0 ? "warning" : "success"}
      />
      <SummaryCard
        label="涉及队列"
        value={toInteger(metrics.queue_count)}
        hint="当日有质检记录的队列去重计数"
        tone="neutral"
      />
      <SummaryCard
        label="参与质检员"
        value={toInteger(metrics.owner_count)}
        hint="当日执行质检的去重人数"
        tone="neutral"
      />
    </div>
  ) : (
    <section className="panel">
      <div className="info-banner" style={{ background: "#fef3c7", color: "#92400e" }}>
        ⚠️ 日期 {selectedDate} 无内检数据（可能当天无 qc_module=internal 的 fact_qa_event 记录，或数仓尚未回灌）。
        请切换到其他日期或检查数据导入任务。
      </div>
    </section>
  );

  /** 趋势图区域 */
  const trendPoints = trendSeries.map((row) => ({
    label: String(row.anchor_date ?? "").slice(5), // MM-DD
    primary: toNumber(row.raw_accuracy_rate),
    secondary: toNumber(row.final_accuracy_rate),
  }));

  const trendSection = (
    <LineChartCard
      title="日级正确率趋势"
      subtitle={`${trendStart} ~ ${trendEnd}`}
      points={trendPoints}
      primaryLabel="原始正确率"
      secondaryLabel="最终正确率"
    />
  );

  /** 队列排名区域 —— 用 BarListCard 展示正确率排名 */
  const queueBars = queueItems.map((row) => ({
    label: pickText(row.queue_name),
    value: toNumber(row.raw_accuracy_rate),
    meta: `质检${toInteger(row.qa_cnt)} 错误${toInteger(row.error_cnt)}`,
    tone: accTone(toNumber(row.raw_accuracy_rate), targetRate),
  }));

  const queuesSection = (
    <BarListCard
      title="队列正确率排名"
      subtitle={`共 ${queueItems.length} 个队列 · 按原始正确率升序排列`}
      items={queueBars}
      suffix="%"
    />
  );

  /** 审核人明细表格 */
  const reviewerColumns = [
    { key: "reviewer_name", label: "审核人", sortable: true },
    { key: "qa_cnt", label: "质检量", sortable: true },
    { key: "error_cnt", label: "错误量", sortable: true },
    { key: "raw_accuracy_rate", label: "原始正确率", sortable: true },
    { key: "final_accuracy_rate", label: "最终正确率", sortable: true },
    { key: "misjudge_cnt", label: "错判", sortable: true },
    { key: "missjudge_cnt", label: "漏判", sortable: true },
  ];

  const reviewerRows = buildTableRows(reviewerItems, {
    reviewer_name: (r) => <strong>{pickText(r.reviewer_name)}</strong>,
    qa_cnt: (r) => toInteger(r.qa_cnt),
    error_cnt: (r) => (
      <span style={{ color: toNumber(r.error_cnt) > 0 ? "#dc2626" : "#16a34a" }}>
        {toInteger(r.error_cnt)}
      </span>
    ),
    raw_accuracy_rate: (r) => `${toNumber(r.raw_accuracy_rate).toFixed(2)}%`,
    final_accuracy_rate: (r) => `${toNumber(r.final_accuracy_rate).toFixed(2)}%`,
    misjudge_cnt: (r) => toInteger(r.misjudge_cnt),
    missjudge_cnt: (r) => toInteger(r.missjudge_cnt),
  });

  const reviewersSection = (
    <DataTable
      title="审核人明细"
      rows={reviewerRows}
      columns={reviewerColumns}
      emptyText="暂无审核人数据"
    />
  );

  /** 错误标签分布 */
  const errorBars = errorTypeItems.map((row) => ({
    label: pickText(row.label_name),
    value: toNumber(row.cnt),
    meta: `${toNumber(row.pct).toFixed(1)}%`,
    tone: "primary" as const,
  }));

  const errorTypesSection = (
    <BarListCard
      title="错误标签分布 TOP 10"
      subtitle={`总错误量 ${totalErrors.toLocaleString()}`}
      items={errorBars}
      suffix=""
    />
  );

  /** 质检员工作量表 */
  const ownerColumns = [
    { key: "qa_owner_name", label: "质检员", sortable: true },
    { key: "qa_cnt", label: "执行量", sortable: true },
    { key: "error_cnt", label: "检出错误", sortable: true },
    { key: "accuracy_rate", label: "检出准确率", sortable: true },
  ];

  const ownerRows = buildTableRows(qaOwnerItems, {
    qa_owner_name: (r) => <strong>{pickText(r.qa_owner_name)}</strong>,
    qa_cnt: (r) => toInteger(r.qa_cnt),
    error_cnt: (r) => toInteger(r.error_cnt),
    accuracy_rate: (r) => `${toNumber(r.accuracy_rate).toFixed(2)}%`,
  });

  const ownersSection = (
    <DataTable
      title="质检员工作量"
      rows={ownerRows}
      columns={ownerColumns}
      emptyText="暂无质检员数据"
    />
  );

  // ── 最终组装 ──
  return (
    <AppShell
      currentPath="/internal"
      title="内检看板"
      subtitle={`内部团队质检数据 · ${selectedDate}`}
    >
      {/* 日期选择 */}
      <form method="get" action="/internal" className="date-picker-form">
        <label className="date-picker-label" htmlFor="internal-date">
          选择日期
        </label>
        <input
          id="internal-date"
          name="selected_date"
          type="date"
          defaultValue={selectedDate}
          min={metaResult.data?.min_date as string | undefined}
          max={metaResult.data?.max_date as string | undefined}
        />
        <button type="submit" className="btn btn-primary btn-sm">
          切换
        </button>
      </form>

      {/* 核心指标 */}
      {summarySection}

      {/* 趋势 */}
      <CollapsiblePanel title="正确率趋势" subtitle={`${trendPoints.length} 个数据点`} defaultOpen={true}>
        {trendSection}
      </CollapsiblePanel>

      {/* 双栏布局：队列排名 + 错误标签 */}
      <div className="grid grid-2">
        <CollapsiblePanel title="队列正确率排名" subtitle={`${queueItems.length} 个队列`} defaultOpen={true}>
          {queuesSection}
        </CollapsiblePanel>
        <CollapsiblePanel title="错误标签分布" subtitle={`TOP ${errorTypeItems.length}`} defaultOpen={true}>
          {errorTypesSection}
        </CollapsiblePanel>
      </div>

      {/* 审核人分析 */}
      <CollapsiblePanel
        title="审核人分析"
        subtitle={`共 ${reviewerItems.length} 名审核人 · 含错判/漏判统计`}
        defaultOpen={false}
      >
        {reviewersSection}
      </CollapsiblePanel>

      {/* 质检员工作量 */}
      <CollapsiblePanel
        title="质检员工作量"
        subtitle={`共 ${qaOwnerItems.length} 名质检员`}
        defaultOpen={false}
      >
        {ownersSection}
      </CollapsiblePanel>
    </AppShell>
  );
}

