import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { SummaryCard } from "@/components/summary-card";
import { LineChartCard } from "@/components/line-chart-card";
import { DataTable } from "@/components/data-table";

import { safeFetchApi } from "@/lib/api";
import { toDateInputValue, toInteger, toNumber, toPercent } from "@/lib/formatters";

export const metadata: Metadata = {
  title: "内检看板",
};

type Row = Record<string, unknown>;
type LinePoint = { label: string; primary: number; secondary?: number };

// ─── 类型定义 ───

interface InternalMetrics {
  qa_cnt: number;
  raw_accuracy_rate: number;
  final_accuracy_rate: number;
  error_count: number;
  queue_count: number;
  owner_count: number;
  misjudge_count: number;
  missjudge_count: number;
}

interface InternalSummary {
  module: string;
  selected_date: string;
  target_rate: number;
  color: string;
  metrics: InternalMetrics | null;
  prev?: { qa_cnt: number; raw_accuracy_rate: number; qa_delta: number | null; acc_delta_pp: number | null };
}

interface InternalPageData {
  summary: InternalSummary | null;
  queues: Row[];
  trend: { series: Row[]; target_rate: number };
  reviewers: Row[];
  errorTypes: Row[];
  qaOwners: Row[];
}

// ─── 数据加载 ───

async function fetchInternalData(selectedDate: string): Promise<InternalPageData> {
  const sd = selectedDate;

  // 并行请求所有接口
  const [summaryResult, queueResult, trendResult, reviewerResult, errorTypeResult, qaOwnerResult] = await Promise.all([
    safeFetchApi<InternalSummary>(`/api/v1/internal/summary?selected_date=${sd}&with_prev=true`),
    safeFetchApi<{ items: Row[]; total: number }>(`/api/v1/internal/queues?selected_date=${sd}`),
    safeFetchApi<{ series: Row[]; target_rate: number }>(
      `/api/v1/internal/trend?start_date=${sd.replace(/(\d{4})-(\d{2})-(\d{2})/, "$1-$2-" + String(Math.max(1, parseInt("$3") - 6)).padStart(2, '0"))}&end_date=${sd}`
    ),
    safeFetchApi<{ items: Row[]; total: number }>(`/api/v1/internal/reviewers?selected_date=${sd}&limit=30`),
    safeFetchApi<{ items: Row[]; total_errors: number }>(`/api/v1/internal/error-types?selected_date=${sd}&top_n=10`),
    safeFetchApi<{ items: Row[]; total: number }>(`/api/v1/internal/qa-owners?selected_date=${sd}&limit=20`),
  ]);

  return {
    summary: summaryResult.data,
    queues: queueResult.data?.items ?? [],
    trend: trendResult.data ?? { series: [], target_rate: 99.5 },
    reviewers: reviewerResult.data?.items ?? [],
    errorTypes: errorTypeResult.data ?? { items: [], total_errors: 0 },
    qaOwners: qaOwnerResult.data?.items ?? [],
  };
}

function accTone(acc: number): "success" | "warning" | "danger" | "neutral" {
  if (acc >= 99.5) return "success";
  if (acc >= 99) return "warning";
  return "danger";
}

// ─── 页面组件 ───

export default async function InternalInspectionPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams ?? {};
  const dateParam = typeof params.date === "string" ? params.date : undefined;

  // 默认用今天，或从 URL 参数取
  const today = new Date().toISOString().slice(0, 10);
  const selectedDate = dateParam || today;
  const data = await fetchInternalData(selectedDate);

  const m = data.summary?.metrics;
  const prev = data.summary?.prev;

  // 趋势起始日期（往前推6天）
  const d = new Date(selectedDate);
  d.setDate(d.getDate() - 6);
  const trendStart = d.toISOString().slice(0, 10);

  return (
    <AppShell>
      <div className="internal-page">
        {/* Hero */}
        <div className="hero" style={{ borderLeftColor: "#8B5CF6" }}>
          <h1 className="hero-title">🔬 内检看板</h1>
          <p className="hero-subtitle">内部质检 · 按队列展示 · 出错下探 · 审核人分析</p>
        </div>

        {/* 日期选择 */}
        <div className="date-bar">
          <label htmlFor="int-date">业务日期</label>
          <input id="int-date" type="date" defaultValue={toDateInputValue(selectedDate)} />
          <span style={{ color: "#6b7280", fontSize: "0.85rem", marginLeft: "0.75rem" }}>
            趋势区间：{trendStart} ~ {selectedDate}
          </span>
        </div>

        {/* 空状态 */}
        {!m ? (
          <div className="empty-state">
            当前日期（{selectedDate}）暂无内检数据。
          </div>
        ) : (
          <>
            {/* 核心指标卡 — 5列网格 */}
            <section className="cards-row">
              <SummaryCard label="📊 质检总量" value={m.qa_cnt.toLocaleString()}
                delta={
                  prev && prev.qa_delta !== null
                    ? (prev.qa_delta > 0 ? `+${prev.qa_delta.toLocaleString()}` : `${prev.qa_delta.toLocaleString()}`)
                    : undefined
                }
                tone="neutral"
              />
              <SummaryCard label="✓ 原始正确率" value={`${m.raw_accuracy_rate.toFixed(2)}%`}
                delta={
                  prev && prev.acc_delta_pp !== null
                    ? `${prev.acc_delta_pp > 0 ? "+" : ""}${prev.acc_delta_pp.toFixed(2)}pp`
                    : undefined
                }
                tone={accTone(m.raw_accuracy_rate)}
                hint={`目标 ≥ ${data.summary?.target_rate}%`}
              />
              <SummaryCard label="🎯 最终正确率" value={`${m.final_accuracy_rate.toFixed(2)}%`} tone={accTone(m.final_accuracy_rate)} />
              <SummaryCard label="✗ 错误量" value={m.error_count.toLocaleString()} tone={m.error_count > 0 ? "danger" : "success"} />
              <SummaryCard label="🏢 队列 / 质检员" value={`${m.queue_count} / ${m.owner_count}`} tone="neutral" />
            </section>

            {/* 错判 / 漏判 结构 */}
            {m.misjudge_count + m.missjudge_count > 0 && (
              <section className="panel misjudge-panel">
                <h3 className="panel-title">⚖️ 错判 / 漏判 结构</h3>
                <div className="misjudge-stats">
                  <span className="mis-label mis-red">
                    错判 {m.misjudge_count}
                  </span>
                  <span className="mis-label mis-yellow">
                    漏判 {m.missjudge_count}
                  </span>
                  <span className="mis-diag">
                    {(m.misjudge_count > m.missjudge_count * 1.5) ? "⚠️ 错判偏多，审核偏松"
                      : (m.missjudge_count > m.misjudge_count * 1.5) ? "⚠️ 漏判偏多，审核偏严"
                      : "✓ 分布均衡"}
                  </span>
                </div>
              </section>
            )}

            {/* 队列排名 + 趋势 */}
            <div className="two-col">
              <section className="panel">
                <h3 className="panel-title">🏆 队列正确率排名</h3>
                {data.queues.length === 0 ? (
                  <div className="empty-state">暂无队列数据</div>
                ) : (
                  <DataTable
                    headers={["队列", "质检量", "错误量", "原始正确率", "最终正确率"]}
                    rows={data.queues.map((q) => [
                      String(q.queue_name).slice(0, 24),
                      toInteger(q.qa_cnt),
                      toInteger(q.error_cnt),
                      toPercent(q.raw_accuracy_rate),
                      toPercent(q.final_accuracy_rate),
                    ])}
                    highlight={(rowIdx) => {
                      const val = toNumber(data.queues[rowIdx]?.raw_accuracy_rate);
                      return val < 99 ? "danger" : val < 99.5 ? "warning" : "";
                    }}
                  />
                )}
              </section>

              <section className="panel chart-panel">
                <h3 className="panel-title">📈 正确率趋势</h3>
                <LineChartCard
                  title=""
                  subtitle={`目标 ${data.trend.target_rate}%`}
                  points={(data.trend.series || []).map((s: Row) => ({
                    label: String(s.anchor_date).slice(5), // MM-DD
                    primary: Number(s.final_accuracy_rate) || 0,
                    secondary: Number(s.raw_accuracy_rate) || 0,
                  }))}
                  primaryLabel="最终正确率"
                  secondaryLabel="原始正确率"
                />
              </section>
            </div>

            {/* 审核人明细 */}
            <section className="panel">
              <h3 className="panel-title">👥 审核人分析</h3>
              {data.reviewers.length === 0 ? (
                <div className="empty-state">暂无审核人数据</div>
              ) : (
                <DataTable
                  headers={["审核人", "质检量", "错误量", "原始正确率", "最终正确率", "错判量", "漏判量"]}
                  rows={data.reviewers.map((r) => {
                    const name = String(r.reviewer_name || "").split("-").pop() || r.reviewer_name;
                    return [
                      name.slice(0, 16),
                      toInteger(r.qa_cnt),
                      toInteger(r.error_cnt),
                      toPercent(r.raw_accuracy_rate),
                      toPercent(r.final_accuracy_rate),
                      toInteger(r.misjudge_cnt),
                      toInteger(r.missjudge_cnt),
                    ];
                  })}
                  highlight={(rowIdx) => {
                    const val = toNumber(data.reviewers[rowIdx]?.raw_accuracy_rate);
                    return val < 99 ? "danger" : val < 99.5 ? "warning" : "";
                  }}
                />
              )}
            </section>

            {/* 出错类型分布 */}
            <div className="two-col">
              <section className="panel">
                <h3 className="panel-title">🏷️ 错误标签 TOP</h3>
                {Array.isArray(data.errorTypes.items) && data.errorTypes.items.length > 0 ? (
                  <DataTable
                    headers={["错误标签", "数量", "占比"]}
                    rows={data.errorTypes.items.map((e) => [
                      String(e.label_name || "").slice(0, 24),
                      toInteger(e.cnt),
                      toPercent(e.pct),
                    ])}
                  />
                ) : (
                  <div className="empty-state">暂无出错类型</div>
                )}
              </section>

              <section className="panel">
                <h3 className="panel-title">👨‍💼 质检员工作量</h3>
                {data.qaOwners.length === 0 ? (
                  <div className="empty-state">暂无质检员数据</div>
                ) : (
                  <DataTable
                    headers={["质检员", "质检量", "错误量", "正确率"]}
                    rows={data.qaOwners.map((o) => {
                      const name = String(o.qa_owner_name || "").split("-").pop() || o.qa_owner_name;
                      return [
                        name.slice(0, 16),
                        toInteger(o.qa_cnt),
                        toInteger(o.error_cnt),
                        toPercent(o.accuracy_rate),
                      ];
                    })}
                  />
                )}
              </section>
            </div>
          </>
        )}
      </div>

      {/* 内联样式 —— 后续可抽到 globals.css 或 module.css */}
      <style jsx>{`
        .internal-page {
          max-width: 1280px;
          margin: 0 auto;
          padding: 1rem 1.5rem 3rem;
        }
        .hero {
          padding: 1.25rem 1.5rem;
          background: #fff;
          border-radius: 1rem;
          border-left: 4px solid #8B5CF6;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
          margin-bottom: 1rem;
        }
        .hero-title {
          margin: 0;
          font-size: 1.75rem;
          font-weight: 700;
          color: #1a1a1a;
        }
        .hero-subtitle {
          margin: 0.35rem 0 0;
          font-size: 0.88rem;
          color: #4b5563;
        }
        .date-bar {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-bottom: 1.25rem;
          padding: 0.5rem 0;
        }
        .date-bar label {
          font-size: 0.85rem;
          font-weight: 600;
          color: #374151;
        }
        .date-bar input[type="date"] {
          padding: 0.35rem 0.65rem;
          border: 1px solid #d1d5db;
          border-radius: 0.4rem;
          font-size: 0.9rem;
          background: #fff;
        }
        .cards-row {
          display: grid;
          grid-template-columns: repeat(5, 1fr);
          gap: 0.75rem;
          margin-bottom: 1.25rem;
        }
        @media (max-width: 900px) {
          .cards-row { grid-template-columns: repeat(3, 1fr); }
        }
        @media (max-width: 600px) {
          .cards-row { grid-template-columns: repeat(2, 1fr); }
        }
        .two-col {
          display: grid;
          grid-template-columns: 1fr 1.2fr;
          gap: 1rem;
          margin-bottom: 1.25rem;
        }
        @media (max-width: 800px) {
          .two-col { grid-template-columns: 1fr; }
        }
        .panel {
          background: #fff;
          border-radius: 0.75rem;
          border: 1px solid #e5e7eb;
          padding: 1rem 1.15rem;
          margin-bottom: 0;
        }
        .panel-title {
          margin: 0 0 0.75rem;
          font-size: 1rem;
          font-weight: 600;
          color: #1f2937;
        }
        .chart-panel { overflow: hidden; }
        .misjudge-panel {
          background: linear-gradient(135deg, #F5F3FF, #EDE9FE);
          border-left: 4px solid #8B5CF6;
          margin-bottom: 1.25rem;
        }
        .misjudge-stats {
          display: flex;
          align-items: center;
          gap: 1.25rem;
          flex-wrap: wrap;
        }
        .mis-label {
          font-size: 0.92rem;
          font-weight: 600;
          padding: 0.25rem 0.7rem;
          border-radius: 0.35rem;
        }
        .mis-red { color: #DC2626; background: #FEF2F2; }
        .mis-yellow { color: #D97706; background: #FFFBEB; }
        .mis-diag { font-size: 0.84rem; font-weight: 500; }
        .empty-state {
          text-align: center;
          padding: 2rem 1rem;
          color: #9ca3af;
          font-size: 0.92rem;
        }
      `}</style>
    </AppShell>
  );
}
