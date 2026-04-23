'use client';

import { PageTemplate } from '@/components/page-template';
import { DateFilterClient } from '@/components/date-filter-client';
import { MultiFilter } from '@/components/multi-filter';
import { ExcelExporter } from '@/lib/excel-exporter';
import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Suspense } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area, PieChart, Pie, Cell,
} from 'recharts';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const QUEUE_THRESHOLD = 99;
const REVIEWER_THRESHOLD = 95;
const COLORS = ['#8B5CF6', '#6366F1', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#14B8A6'];

// ── Types ──

interface ExternalSummary {
  start: string; end: string; has_data: boolean;
  total_count: number; correct_count: number;
  misjudge_cnt: number; missjudge_cnt: number;
  correct_rate: number; misjudge_rate: number; missjudge_rate: number;
  appeal_reversed_cnt: number; appeal_reverse_rate: number;
  queue_count: number;
}

interface TrendItem {
  date: string; total_count: number; correct_rate: number;
  misjudge_cnt: number; missjudge_cnt: number;
  misjudge_rate: number; missjudge_rate: number;
}

interface QueueItem {
  group_name: string; queue_name: string;
  total_count: number; correct_rate: number;
  misjudge_cnt: number; missjudge_cnt: number;
  misjudge_rate: number; missjudge_rate: number;
  appeal_reverse_rate: number; reviewer_cnt: number;
  needs_attention: boolean;
}

interface ReviewerItem {
  reviewer_name: string; group_name: string; queue_name: string;
  review_count: number; correct_rate: number;
  misjudge_cnt: number; missjudge_cnt: number;
  needs_attention: boolean;
}

interface InternalSummary {
  metrics: {
    qa_cnt: number; raw_accuracy_rate: number;
    error_count: number; missjudge_count: number;
    misjudge_count: number; owner_count: number; queue_count: number;
  };
  target_rate: number;
}

// ── Utils ──

function fmt(n: number | undefined | null, digits = 2) {
  if (n == null) return '—';
  return n.toFixed(digits);
}
function fmtInt(n: number | undefined | null) {
  if (n == null) return '—';
  return n.toLocaleString('zh-CN');
}
function rateColor(rate: number): string {
  if (rate >= 99) return '#10b981';
  if (rate >= 98) return '#f59e0b';
  return '#ef4444';
}

// ── Sub-components ──

function MetricCard({
  label, value, sub, color = '#374151', alert = false, bg,
}: {
  label: string; value: string; sub?: string;
  color?: string; alert?: boolean; bg?: string;
}) {
  return (
    <div style={{
      background: bg || '#fff', borderRadius: 12, padding: '16px 18px 12px',
      border: `${alert ? 2 : 1}px solid ${alert ? '#fca5a5' : '#e5e7eb'}`,
      boxShadow: alert ? '0 2px 8px rgba(239,68,68,.1)' : '0 1px 4px rgba(0,0,0,.05)',
      display: 'flex', flexDirection: 'column', gap: 3,
    }}>
      <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: alert ? '#dc2626' : color, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: alert ? '#dc2626' : '#9ca3af' }}>{sub}</div>}
    </div>
  );
}

function MiniBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 8, background: '#f3f4f6', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 4 }} />
      </div>
      <span style={{ fontSize: 12, color: '#6b7280', minWidth: 28, textAlign: 'right' }}>{value}</span>
    </div>
  );
}

// ── Tab Definitions ──

type TabKey = 'external' | 'internal' | 'error';
const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'external', label: '外检', icon: '🌐' },
  { key: 'internal', label: '内检', icon: '🏠' },
  { key: 'error', label: '错误深钻', icon: '🎯' },
];

// ══════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════

const TODAY = new Date().toISOString().slice(0, 10);

// Suspense wrapper required for useSearchParams in Next.js App Router
export default function AnalysisPageWrapper() {
  return (
    <Suspense fallback={<div style={{ padding: 48, textAlign: 'center', color: '#9ca3af' }}>加载中...</div>}>
      <AnalysisPage />
    </Suspense>
  );
}

function AnalysisPage() {
  const searchParams = useSearchParams();

  // ── Tab state (synced with URL) ──
  const initialTab = (searchParams.get('tab') as TabKey) || 'external';
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab);

  // ── IA-5: URL参数传递 — 从运营总览等页面跳入时自动初始化筛选 ──
  const initialQueue = searchParams.get('queue') || '';
  const initialReviewer = searchParams.get('reviewer') || '';
  const initialErrorType = searchParams.get('error_type') || '';

  const [effectiveMaxDate, setEffectiveMaxDate] = useState(TODAY);
  const [dateRangeReady, setDateRangeReady] = useState(false);

  // ── External state ──
  const [extStartDate, setExtStartDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 6);
    return d.toISOString().slice(0, 10);
  });
  const [extEndDate, setExtEndDate] = useState(TODAY);
  const [extGroupName, setExtGroupName] = useState('');
  const [extSummary, setExtSummary] = useState<ExternalSummary | null>(null);
  const [extTrend, setExtTrend] = useState<TrendItem[]>([]);
  const [extQueues, setExtQueues] = useState<QueueItem[]>([]);
  const [extReviewers, setExtReviewers] = useState<ReviewerItem[]>([]);
  const [extGroups, setExtGroups] = useState<string[]>([]);
  const [extLoading, setExtLoading] = useState(false);
  const [reviewerView, setReviewerView] = useState<'problem' | 'all'>('problem');

  // ── Internal state ──
  const [intDate, setIntDate] = useState(TODAY);
  const [intSummary, setIntSummary] = useState<InternalSummary | null>(null);
  const [intQueues, setIntQueues] = useState<any[]>([]);
  const [intQueueOptions, setIntQueueOptions] = useState<string[]>([]); // HC-1: 动态队列选项
  const [intReviewers, setIntReviewers] = useState<any[]>([]);
  const [intErrorTypes, setIntErrorTypes] = useState<any[]>([]);
  const [intLoading, setIntLoading] = useState(false);
  const [intExpanded, setIntExpanded] = useState<string | null>(null);
  const [intShowFilter, setIntShowFilter] = useState(false);
  const [intFilters, setIntFilters] = useState<{
    queues: string[]; reviewers: string[]; errorTypes: string[];
  }>({ queues: [], reviewers: [], errorTypes: [] });

  // ── Error Drill state ──
  const [errStartDate, setErrStartDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 6);
    return d.toISOString().slice(0, 10);
  });
  const [errEndDate, setErrEndDate] = useState(TODAY);
  const [errSource, setErrSource] = useState<'all' | 'external' | 'internal'>('all');
  const [errDistribution, setErrDistribution] = useState<any[]>([]);
  const [errTrend, setErrTrend] = useState<any[]>([]);
  const [errReviewers, setErrReviewers] = useState<any[]>([]);
  const [errHeatmap, setErrHeatmap] = useState<{ queues: string[]; error_types: string[]; data: any[] }>({ queues: [], error_types: [], data: [] });
  const [errSummary, setErrSummary] = useState<any>(null);
  const [errLoading, setErrLoading] = useState(false);

  // ── Appeal analysis state (shared across all tabs) ──
  const [appealData, setAppealData] = useState<{
    appeal_rate: number; reverse_success_rate: number; reversed_cnt: number;
    top_reasons: { reason: string; count: number }[];
  } | null>(null);

  // ══════════════════════════════════════════════════════════════
  // External data loading
  // ══════════════════════════════════════════════════════════════

  const loadExternal = useCallback(async () => {
    setExtLoading(true);
    try {
      const base = `${API_BASE}/api/v1/external`;
      const gp = extGroupName ? `&group_name=${encodeURIComponent(extGroupName)}` : '';
      const dr = `start_date=${extStartDate}&end_date=${extEndDate}`;

      const [sumRes, trendRes, queueRes, reviewerRes, metaRes] = await Promise.all([
        fetch(`${base}/summary?${dr}${gp}`),
        fetch(`${base}/trend?${dr}${gp}`),
        fetch(`${base}/queue-ranking?${dr}${gp}`),
        fetch(`${base}/reviewer-ranking?${dr}${gp}`),
        fetch(`${base}/meta?${dr}`),
      ]);

      const [sumD, trendD, queueD, reviewerD, metaD] = await Promise.all([
        sumRes.json(), trendRes.json(), queueRes.json(), reviewerRes.json(), metaRes.json(),
      ]);

      setExtSummary(sumD);
      setExtTrend(trendD || []);
      setExtQueues(queueD || []);
      setExtReviewers(reviewerD || []);
      setExtGroups(metaD?.groups || []);
    } catch (e) {
      console.error(e);
    } finally {
      setExtLoading(false);
    }
  }, [extStartDate, extEndDate, extGroupName]);

  // ══════════════════════════════════════════════════════════════
  // Internal data loading
  // ══════════════════════════════════════════════════════════════

  const loadInternal = useCallback(async () => {
    setIntLoading(true);
    try {
      const base = `${API_BASE}/api/v1`;
      const params = new URLSearchParams();
      params.set('selected_date', intDate);
      if (intFilters.queues.length > 0) params.set('queues', intFilters.queues.join(','));
      if (intFilters.reviewers.length > 0) params.set('reviewers', intFilters.reviewers.join(','));
      if (intFilters.errorTypes.length > 0) params.set('error_types', intFilters.errorTypes.join(','));

      const [summaryRes, queueRes, reviewerRes, errorRes] = await Promise.all([
        fetch(`${base}/internal/summary?${params.toString()}`),
        fetch(`${base}/internal/queues?${params.toString()}`),
        fetch(`${base}/internal/reviewers?${params.toString()}&limit=20`),
        fetch(`${base}/internal/error-types?${params.toString()}&top_n=10`),
      ]);

      const [summaryJson, queueJson, reviewerJson, errorJson] = await Promise.all([
        summaryRes.json(), queueRes.json(), reviewerRes.json(), errorRes.json(),
      ]);

      setIntSummary(summaryJson.data);
      setIntQueues(queueJson.data?.items || []);
      // HC-1: 从 API 动态获取队列选项，替代硬编码的 6 个队列
      const queueItems = queueJson.data?.items || queueJson.data?.queues || [];
      setIntQueueOptions(queueItems.map((q: any) => q.queue_name || q).filter(Boolean));
      setIntReviewers(reviewerJson.data?.items || []);
      setIntErrorTypes(errorJson.data?.items || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIntLoading(false);
    }
  }, [intDate, intFilters]);

  // ══════════════════════════════════════════════════════════════
  // Error drill data loading
  // ══════════════════════════════════════════════════════════════

  const loadErrorDrill = useCallback(async () => {
    setErrLoading(true);
    try {
      const base = `${API_BASE}/api/v1/analysis/error-drill`;
      const params = new URLSearchParams();
      params.set('start_date', errStartDate);
      params.set('end_date', errEndDate);
      params.set('source', errSource);
      const res = await fetch(`${base}?${params.toString()}`);
      const json = await res.json();
      const data = json.data || {};
      setErrSummary(data.summary || null);
      setErrDistribution(data.error_distribution || []);
      setErrTrend(data.daily_trend || []);
      setErrReviewers(data.top_reviewers || []);
      setErrHeatmap(data.heatmap || { queues: [], error_types: [], data: [] });
    } catch (e) {
      console.error(e);
    } finally {
      setErrLoading(false);
    }
  }, [errStartDate, errEndDate, errSource]);

  // ── 初始化有效日期范围 ──
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/meta/date-range`)
      .then((r) => r.json())
      .then((d) => {
        const data = d.data || d;
        const max = data.default_selected_date || data.max_date || TODAY;
        setEffectiveMaxDate(max);
        setExtEndDate(max);
        setExtStartDate(() => {
          const dt = new Date(`${max}T00:00:00`);
          dt.setDate(dt.getDate() - 6);
          return dt.toISOString().slice(0, 10);
        });
        setIntDate(max);
        setErrEndDate(max);
        setErrStartDate(() => {
          const dt = new Date(`${max}T00:00:00`);
          dt.setDate(dt.getDate() - 6);
          return dt.toISOString().slice(0, 10);
        });
      })
      .catch(() => {})
      .finally(() => setDateRangeReady(true));
  }, []);

  // ── Auto-load on tab/date change ──

  useEffect(() => {
    if (!dateRangeReady) return;
    if (activeTab === 'external') loadExternal();
    else if (activeTab === 'internal') loadInternal();
  }, [activeTab, loadExternal, loadInternal, dateRangeReady]);

  useEffect(() => {
    if (!dateRangeReady) return;
    if (activeTab === 'error') loadErrorDrill();
  }, [activeTab, loadErrorDrill, dateRangeReady]);

  // ── Load appeal data (shared, load once on mount) ──
  useEffect(() => {
    const base = activeTab === 'internal' ? 'internal' : 'external';
    fetch(`${API_BASE}/api/v1/${base}/appeal-summary`)
      .then(r => { if (!r.ok) throw new Error('no api'); return r.json(); })
      .then(d => setAppealData(d.data || d))
      .catch(() => setAppealData(null));
  }, [activeTab]);

  // ── Derived data ──

  const alertQueues = extQueues.filter(q => q.needs_attention);
  const problemReviewers = extReviewers.filter(r => r.needs_attention);
  const displayReviewers = reviewerView === 'problem' ? problemReviewers : extReviewers;
  const maxErr = Math.max(...extQueues.map(q => q.misjudge_cnt + q.missjudge_cnt), 1);

  // ══════════════════════════════════════════════════════════════
  // Internal export helper
  // ══════════════════════════════════════════════════════════════

  const exportTable = (tableName: string, data: any[]) => {
    if (data.length === 0) { alert('没有数据可导出'); return; }
    let columns: any[] = [];
    let exportData: any[] = [];
    switch (tableName) {
      case 'queue':
        columns = [
          { key: 'rank', label: '排名' },
          { key: 'queue_name', label: '队列名称', width: 20 },
          { key: 'qa_cnt', label: '审核量', width: 12 },
          { key: 'raw_accuracy_rate', label: '正确率（%）', width: 15 },
          { key: 'misjudge_rate', label: '误判率（%）', width: 15 },
        ];
        exportData = data.map((item, index) => ({
          rank: index + 1, queue_name: item.queue_name, qa_cnt: item.qa_cnt,
          raw_accuracy_rate: item.raw_accuracy_rate?.toFixed(2),
          misjudge_rate: (100 - (item.raw_accuracy_rate || 0)).toFixed(2),
        }));
        break;
      case 'reviewer':
        columns = [
          { key: 'rank', label: '排名' },
          { key: 'reviewer_name', label: '审核人', width: 15 },
          { key: 'qa_cnt', label: '审核量', width: 12 },
          { key: 'raw_accuracy_rate', label: '正确率（%）', width: 15 },
          { key: 'misjudge_cnt', label: '误判数', width: 12 },
        ];
        exportData = data.map((item, index) => ({
          rank: index + 1, reviewer_name: item.reviewer_name, qa_cnt: item.qa_cnt,
          raw_accuracy_rate: item.raw_accuracy_rate?.toFixed(2),
          misjudge_cnt: item.misjudge_cnt || 0,
        }));
        break;
      case 'error':
        columns = [
          { key: 'rank', label: '排名' },
          { key: 'label_name', label: '错误类型', width: 20 },
          { key: 'cnt', label: '错误数', width: 12 },
          { key: 'pct', label: '占比（%）', width: 12 },
        ];
        exportData = data.map((item, index) => ({
          rank: index + 1, label_name: item.label_name, cnt: item.cnt,
          pct: item.pct?.toFixed(2),
        }));
        break;
    }
    ExcelExporter.exportSingleSheet(exportData, columns, tableName, `${tableName}_${activeTab === 'internal' ? intDate : `${errStartDate}_${errEndDate}`}.csv`);
  };

  // ══════════════════════════════════════════════════════════════
  // Render
  // ══════════════════════════════════════════════════════════════

  return (
    <PageTemplate title="质检分析" subtitle="外检 / 内检 / 错误深钻">

      {/* ── Tab Switcher ── */}
      <div style={{
        display: 'flex', gap: 4, background: '#f3f4f6', borderRadius: 10,
        padding: 4, marginBottom: 24, width: 'fit-content',
      }}>
        {TABS.map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '8px 20px', borderRadius: 8, fontSize: 14, fontWeight: 500,
              border: 'none', cursor: 'pointer',
              background: activeTab === tab.key ? '#fff' : 'transparent',
              color: activeTab === tab.key ? '#374151' : '#9ca3af',
              boxShadow: activeTab === tab.key ? '0 1px 3px rgba(0,0,0,.1)' : 'none',
              transition: 'all 0.15s',
            }}>
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════════ */}
      {/* EXTERNAL TAB                                              */}
      {/* ════════════════════════════════════════════════════════ */}

      {activeTab === 'external' && (
        <>
          {/* ── 筛选栏 ── */}
          <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '14px 16px', marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              🔍 筛选条件
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: '#6b7280' }}>开始日期</label>
                <input type="date" value={extStartDate} max={extEndDate}
                  onChange={e => setExtStartDate(e.target.value)}
                  style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: '#6b7280' }}>结束日期</label>
                <input type="date" value={extEndDate} min={extStartDate} max={TODAY}
                  onChange={e => setExtEndDate(e.target.value)}
                  style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: '#6b7280' }}>组别</label>
                <select value={extGroupName} onChange={e => setExtGroupName(e.target.value)}
                  style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13, minWidth: 140 }}>
                  <option value="">全部</option>
                  {extGroups.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              {/* 查询按钮已移除 — 筛选条件变更自动刷新（文档 5.5 交互模式统一） */}
            </div>
          </div>

          {/* ── 核心指标卡片 ── */}
          {extSummary?.has_data && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px,1fr))', gap: 16, marginBottom: 24 }}>
              <MetricCard label="抽检总量" value={fmtInt(extSummary.total_count)} sub={`${extSummary.start} ~ ${extSummary.end}`} color="#6366f1" />
              <MetricCard label="综合正确率" value={`${fmt(extSummary.correct_rate)}%`}
                sub="目标 ≥99%" color="#059669"
                bg={extSummary.correct_rate < QUEUE_THRESHOLD ? '#fff1f2' : '#f0fdf4'}
                alert={extSummary.correct_rate < QUEUE_THRESHOLD} />
              <MetricCard label="错判数" value={fmtInt(extSummary.misjudge_cnt)}
                sub={`错判率 ${fmt(extSummary.misjudge_rate)}%`} color="#2563eb" />
              <MetricCard label="漏判数" value={fmtInt(extSummary.missjudge_cnt)}
                sub={`漏判率 ${fmt(extSummary.missjudge_rate)}%`} color="#d97706" />
              <MetricCard label="申诉改判" value={fmtInt(extSummary.appeal_reversed_cnt)}
                sub={`改判率 ${fmt(extSummary.appeal_reverse_rate)}%`} color="#7c3aed" />
              <MetricCard label="队列数" value={String(extSummary.queue_count)} sub="参与队列" color="#374151" />
            </div>
          )}
          {extSummary && !extSummary.has_data && (
            <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 14, marginBottom: 24 }}>
              所选日期范围暂无数据
            </div>
          )}

          {/* ── 正确率趋势 ── */}
          {extTrend.length >= 2 && (
            <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '14px 16px', marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 12 }}>
                📈 正确率趋势（<span style={{ color: '#6366f1' }}>蓝点正常</span> / <span style={{ color: '#ef4444' }}>红点预警</span>）
              </div>
              <div style={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={extTrend} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                    <defs>
                      <linearGradient id="extGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} tickFormatter={(v: string) => v.slice(5)} />
                    <YAxis domain={[97, 100]} tick={{ fontSize: 12 }} tickFormatter={(v: number) => `${v}%`} />
                    <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}%`, '正确率']} labelFormatter={(l: any) => `日期: ${l}`} />
                    <Area type="monotone" dataKey="correct_rate" stroke="#6366f1" fill="url(#extGrad)" strokeWidth={2} dot={{ r: 3 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* ── 需关注队列 ── */}
          {alertQueues.length > 0 && (
            <div style={{ background: '#fff1f2', border: '2px solid #fca5a5', borderRadius: 10, padding: '14px 16px', marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#dc2626', marginBottom: 10 }}>
                🔴 需关注队列（正确率 &lt;{QUEUE_THRESHOLD}%，共 {alertQueues.length} 条）
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {alertQueues.map((q, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: '#fff', borderRadius: 8, border: '1px solid #fecaca' }}>
                    <span style={{ fontSize: 11, background: '#fee2e2', color: '#dc2626', borderRadius: 4, padding: '2px 6px', fontWeight: 600, whiteSpace: 'nowrap' }}>
                      {q.group_name}
                    </span>
                    <span style={{ fontSize: 13, fontWeight: 500, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.queue_name}</span>
                    <span style={{ fontSize: 14, fontWeight: 700, color: '#dc2626', whiteSpace: 'nowrap' }}>{q.correct_rate.toFixed(2)}%</span>
                    <span style={{ fontSize: 12, color: '#9ca3af', whiteSpace: 'nowrap' }}>错{q.misjudge_cnt}+漏{q.missjudge_cnt}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── 全部队列排名 ── */}
          <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', overflow: 'hidden', marginBottom: 20 }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #f3f4f6', background: '#f9fafb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
                📋 队列排名
                <span style={{ fontSize: 12, fontWeight: 400, color: '#9ca3af', marginLeft: 8 }}>
                  共 {extQueues.length} 条 · 按正确率升序
                </span>
              </span>
            </div>
            {extQueues.length === 0 ? (
              <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>暂无数据</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: '#6b7280', fontWeight: 500 }}>组别</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: '#6b7280', fontWeight: 500 }}>队列</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280', fontWeight: 500 }}>抽检量</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280', fontWeight: 500 }}>正确率</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: '#6b7280', fontWeight: 500, minWidth: 160 }}>错漏判分布</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280', fontWeight: 500 }}>审核人数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {extQueues.map((q, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6', background: q.needs_attention ? '#fff7f7' : '#fff' }}>
                        <td style={{ padding: '8px 12px' }}>
                          <span style={{ fontSize: 11, background: q.needs_attention ? '#fee2e2' : '#f3f4f6', color: q.needs_attention ? '#dc2626' : '#6b7280', borderRadius: 4, padding: '2px 6px' }}>
                            {q.group_name}
                          </span>
                        </td>
                        <td style={{ padding: '8px 12px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <Link href={`/details?queue=${encodeURIComponent(q.queue_name)}`} style={{ color: q.needs_attention ? '#dc2626' : '#374151', textDecoration: 'none', fontWeight: q.needs_attention ? 600 : 400 }}>
                            {q.queue_name}
                          </Link>
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280' }}>{fmtInt(q.total_count)}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 700, color: q.needs_attention ? '#dc2626' : '#059669' }}>
                          {q.correct_rate.toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                            <MiniBar value={q.misjudge_cnt} max={maxErr} color="#3b82f6" />
                            <MiniBar value={q.missjudge_cnt} max={maxErr} color="#f97316" />
                          </div>
                          <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
                            <span style={{ fontSize: 10, color: '#3b82f6' }}>错{q.misjudge_rate.toFixed(2)}%</span>
                            <span style={{ fontSize: 10, color: '#f97316' }}>漏{q.missjudge_rate.toFixed(2)}%</span>
                          </div>
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280' }}>{q.reviewer_cnt}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* ── 审核人排名 ── */}
          <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #f3f4f6', background: '#f9fafb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
                👤 审核人排名
                {problemReviewers.length > 0 && (
                  <span style={{ marginLeft: 8, fontSize: 12, background: '#fee2e2', color: '#dc2626', borderRadius: 4, padding: '2px 6px' }}>
                    {problemReviewers.length} 人需关注
                  </span>
                )}
              </span>
              <div style={{ display: 'flex', gap: 4 }}>
                <button onClick={() => setReviewerView('problem')}
                  style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: '1px solid #e5e7eb', cursor: 'pointer', background: reviewerView === 'problem' ? '#6366f1' : '#fff', color: reviewerView === 'problem' ? '#fff' : '#374151' }}>
                  只看问题 ({problemReviewers.length})
                </button>
                <button onClick={() => setReviewerView('all')}
                  style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: '1px solid #e5e7eb', cursor: 'pointer', background: reviewerView === 'all' ? '#6366f1' : '#fff', color: reviewerView === 'all' ? '#fff' : '#374151' }}>
                  全部 ({extReviewers.length})
                </button>
              </div>
            </div>
            {displayReviewers.length === 0 ? (
              <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
                {reviewerView === 'problem' ? '✅ 当前所有审核人正确率达标' : '暂无数据'}
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: '#6b7280', fontWeight: 500 }}>审核员</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: '#6b7280', fontWeight: 500 }}>组别 / 队列</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280', fontWeight: 500 }}>抽检量</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280', fontWeight: 500 }}>正确率</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280', fontWeight: 500 }}>错判</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280', fontWeight: 500 }}>漏判</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayReviewers.map((r, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6', background: r.needs_attention ? '#fff7f7' : '#fff' }}>
                        <td style={{ padding: '8px 12px', fontWeight: r.needs_attention ? 600 : 400, color: r.needs_attention ? '#dc2626' : '#374151' }}>
                          <Link href={`/details?reviewer=${encodeURIComponent(r.reviewer_name)}&queue=${encodeURIComponent(r.queue_name || '')}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                            {r.reviewer_name}
                          </Link>
                        </td>
                        <td style={{ padding: '8px 12px', color: '#6b7280', fontSize: 12 }}>
                          <div>{r.group_name}</div>
                          <div style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.queue_name}</div>
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280' }}>{fmtInt(r.review_count)}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 700, color: r.needs_attention ? '#dc2626' : '#059669' }}>
                          {r.correct_rate.toFixed(2)}%
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: '#3b82f6' }}>{r.misjudge_cnt}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: '#f97316' }}>{r.missjudge_cnt}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* ════════════════════════════════════════════════════════ */}
      {/* INTERNAL TAB                                              */}
      {/* ════════════════════════════════════════════════════════ */}

      {activeTab === 'internal' && (
        <>
          {/* ── 筛选栏 ── */}
          <div className="panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title">📅 筛选条件</h3>
              <button onClick={() => setIntShowFilter(!intShowFilter)}
                className="button button-sm"
                style={{ background: intShowFilter ? 'var(--primary)' : 'var(--bg-secondary)', color: intShowFilter ? 'white' : 'var(--text)' }}>
                {intShowFilter ? '收起筛选器' : '展开筛选器'} {intShowFilter ? '▲' : '▼'}
              </button>
            </div>
            <div style={{ marginTop: 'var(--spacing-md)' }}>
              <DateFilterClient initialDate={intDate} maxDate={TODAY} onDateChange={setIntDate} />
            </div>
            {intShowFilter && (
              <div style={{ marginTop: 'var(--spacing-md)' }}>
                <MultiFilter
                  queues={intQueueOptions.map(q => ({
                    value: q, label: q, checked: intFilters.queues.includes(q),
                  }))}
                  reviewers={intReviewers.map(r => ({
                    value: r.reviewer_name, label: r.reviewer_name,
                    checked: intFilters.reviewers.includes(r.reviewer_name),
                  }))}
                  errorTypes={intErrorTypes.map(e => ({
                    value: e.label_name, label: e.label_name,
                    checked: intFilters.errorTypes.includes(e.label_name),
                  }))}
                  onApply={setIntFilters}
                  onReset={() => setIntFilters({ queues: [], reviewers: [], errorTypes: [] })}
                />
              </div>
            )}
          </div>

          {/* ── 核心指标 ── */}
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <h3 className="panel-title">📊 核心指标</h3>
            {intSummary ? (
              <div style={{ marginTop: 'var(--spacing-lg)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
                <div style={{ background: '#fff', borderRadius: 12, padding: '18px 20px 14px', border: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,.06)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', fontWeight: 500 }}>审核量</div>
                  <div style={{ fontSize: 30, fontWeight: 700, color: '#6366f1', lineHeight: 1 }}>{intSummary.metrics?.qa_cnt?.toLocaleString() || '0'}</div>
                  <div style={{ fontSize: 12, color: '#9ca3af' }}>日期: {intDate}</div>
                </div>
                <div style={{ background: '#fff', borderRadius: 12, padding: '18px 20px 14px', border: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,.06)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', fontWeight: 500 }}>正确率</div>
                  <div style={{ fontSize: 30, fontWeight: 700, color: '#10b981', lineHeight: 1 }}>{intSummary.metrics?.raw_accuracy_rate?.toFixed(2) || '0'}%</div>
                  <div style={{ fontSize: 12, color: '#9ca3af' }}>目标 ≥{intSummary.target_rate || 99.5}%</div>
                </div>
                <div style={{ background: '#fff', borderRadius: 12, padding: '18px 20px 14px', border: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,.06)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', fontWeight: 500 }}>错误数</div>
                  <div style={{ fontSize: 30, fontWeight: 700, color: '#ef4444', lineHeight: 1 }}>{intSummary.metrics?.error_count?.toLocaleString() || '0'}</div>
                  <div style={{ fontSize: 12, color: '#9ca3af' }}>漏判 {intSummary.metrics?.missjudge_count || 0} / 错判 {intSummary.metrics?.misjudge_count || 0}</div>
                </div>
                <div style={{ background: '#fff', borderRadius: 12, padding: '18px 20px 14px', border: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,.06)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <div style={{ fontSize: 12, color: '#9ca3af', fontWeight: 500 }}>参与人数</div>
                  <div style={{ fontSize: 30, fontWeight: 700, color: '#8b5cf6', lineHeight: 1 }}>{intSummary.metrics?.owner_count?.toLocaleString() || '0'}</div>
                  <div style={{ fontSize: 12, color: '#9ca3af' }}>队列数 {intSummary.metrics?.queue_count || 0}</div>
                </div>
              </div>
            ) : (
              <div style={{ marginTop: 'var(--spacing-lg)', textAlign: 'center', padding: '48px 0', color: '#9ca3af' }}>加载中...</div>
            )}
          </div>

          {/* ── 问题汇总 ── */}
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)', borderColor: 'var(--danger)', borderWidth: 2 }}>
            <h3 className="panel-title" style={{ color: 'var(--danger)' }}>📌 重点关注问题</h3>
            <div style={{ marginTop: 'var(--spacing-lg)' }}>
              {/* 问题队列 */}
              <div className="problem-section">
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-md)', paddingBottom: 'var(--spacing-sm)', borderBottom: '2px solid var(--border)' }}>
                  <span>🔴</span><span style={{ fontWeight: 600 }}>问题队列（正确率 &lt; {QUEUE_THRESHOLD}%）</span>
                  <button onClick={() => setIntExpanded(intExpanded === 'queue' ? null : 'queue')} style={{ marginLeft: 'auto', padding: '4px 12px', background: 'var(--primary)', color: 'white', border: 'none', borderRadius: 'var(--radius)', fontSize: '0.875em', cursor: 'pointer' }}>查看详情 →</button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                  {intQueues.filter(q => (q.raw_accuracy_rate ?? 100) < QUEUE_THRESHOLD).length === 0 && intQueues.length > 0 && (
                    <div style={{ padding: 'var(--spacing-sm)', color: 'var(--success)' }}>✅ 所有队列正确率 ≥ {QUEUE_THRESHOLD}%</div>
                  )}
                  {intQueues.filter(q => (q.raw_accuracy_rate ?? 100) < QUEUE_THRESHOLD).map((q, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)', padding: 'var(--spacing-sm)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--border)' }}>
                      <Link href={`/details?queue=${encodeURIComponent(q.queue_name || '')}`} style={{ fontWeight: 500, flex: 1, color: 'inherit', textDecoration: 'none' }}>{q.queue_name}</Link>
                      <span style={{ fontWeight: 600, color: 'var(--danger)' }}>{q.raw_accuracy_rate?.toFixed(2)}%</span>
                      <span style={{ fontSize: '0.875em', color: 'var(--text-muted)' }}>审核量: {q.qa_cnt?.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 高频错误 */}
              <div style={{ marginTop: 'var(--spacing-md)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)', marginBottom: 'var(--spacing-md)', paddingBottom: 'var(--spacing-sm)', borderBottom: '2px solid var(--border)' }}>
                  <span>🎯</span><span style={{ fontWeight: 600 }}>高频错误类型（Top 3）</span>
                  <button onClick={() => setIntExpanded(intExpanded === 'error' ? null : 'error')} style={{ marginLeft: 'auto', padding: '4px 12px', background: 'var(--primary)', color: 'white', border: 'none', borderRadius: 'var(--radius)', fontSize: '0.875em', cursor: 'pointer' }}>查看详情 →</button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                  {intErrorTypes.slice(0, 3).map((e, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)', padding: 'var(--spacing-sm)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--border)' }}>
                      <span style={{ fontWeight: 500 }}>#{i + 1} {e.label_name}</span>
                      <span style={{ fontWeight: 600, color: 'var(--primary)' }}>{e.cnt?.toLocaleString()} 次</span>
                      <span style={{ fontSize: '0.875em', color: 'var(--text-muted)' }}>占比: {e.pct?.toFixed(1)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ── 错误类型分布饼图 ── */}
          {intErrorTypes.length > 0 && (
            <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
              <h3 className="panel-title">📊 错误类型分布</h3>
              <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginTop: 'var(--spacing-md)' }}>
                <div style={{ width: 180, height: 180 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={intErrorTypes.map(e => ({ name: e.label_name, value: e.cnt }))}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={70}
                        label={({ name, percent }: any) => `${name?.length > 4 ? name.substring(0, 4) + '..' : name} ${(percent * 100).toFixed(0)}%`}
                        labelLine={false}
                      >
                        {intErrorTypes.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                      </Pie>
                      <Tooltip formatter={(v: any, name: any) => [v, name]} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div style={{ flex: 1 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                        <th style={{ textAlign: 'left', padding: '6px 8px', color: '#6b7280' }}>错误类型</th>
                        <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>数量</th>
                        <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>占比</th>
                      </tr>
                    </thead>
                    <tbody>
                      {intErrorTypes.map((e: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                          <td style={{ padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ width: 10, height: 10, borderRadius: 2, background: COLORS[i % COLORS.length] }} />
                            {e.label_name}
                          </td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600 }}>{e.cnt?.toLocaleString() || 0}</td>
                          <td style={{ padding: '6px 8px', textAlign: 'right', color: '#6b7280' }}>{e.pct?.toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ── 数据下钻 ── */}
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <h3 className="panel-title">🔍 数据下钻</h3>
            <div style={{ marginTop: 'var(--spacing-lg)' }}>
              {/* Queue drill */}
              <DrillSection title="队列分析" subtitle="查看各队列明细数据" icon="📈" expanded={intExpanded === 'queue'} onToggle={() => setIntExpanded(intExpanded === 'queue' ? null : 'queue')}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--spacing-sm)' }}>
                  <button onClick={() => exportTable('queue', intQueues)} className="button button-sm" disabled={intQueues.length === 0}>导出队列数据 ⬇</button>
                </div>
                {intQueues.length > 0 ? (
                  <>
                    <div style={{ height: 200, marginBottom: 'var(--spacing-md)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius)', padding: 'var(--spacing-sm)' }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={intQueues.map(q => ({ name: q.queue_name.length > 10 ? q.queue_name.substring(0, 8) + '..' : q.queue_name, 正确率: q.raw_accuracy_rate || 0 }))} margin={{ top: 5, right: 10, left: -20, bottom: 30 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                          <XAxis dataKey="name" stroke="var(--text-muted)" tick={{ fontSize: 9, angle: -35, textAnchor: 'end' }} interval={0} />
                          <YAxis domain={[98, 101]} stroke="var(--text-muted)" tick={{ fontSize: 11 }} unit="%" />
                          <Tooltip formatter={(val) => [`${Number(val).toFixed(2)}%`, '正确率']} contentStyle={{ fontSize: 12 }} />
                          <Bar dataKey="正确率" radius={[4, 4, 0, 0]} fill="#8b5cf6" maxBarSize={24} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: 'var(--bg-secondary)' }}>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>排名</th>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>队列名称</th>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>审核量</th>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>正确率</th>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>误判率</th>
                          </tr>
                        </thead>
                        <tbody>
                          {intQueues.map((q, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={{ padding: 'var(--spacing-sm)' }}>{i + 1}</td>
                              <td style={{ padding: 'var(--spacing-sm)' }}>
                                <Link href={`/details?queue=${encodeURIComponent(q.queue_name || '')}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                                  {q.queue_name}
                                </Link>
                              </td>
                              <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{q.qa_cnt?.toLocaleString() || 0}</td>
                              <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: q.raw_accuracy_rate >= QUEUE_THRESHOLD ? 'var(--success)' : 'var(--danger)' }}>{q.raw_accuracy_rate?.toFixed(2)}%</td>
                              <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{(100 - (q.raw_accuracy_rate || 0)).toFixed(2)}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : <div style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>暂无数据</div>}
              </DrillSection>

              {/* Reviewer drill */}
              <DrillSection title="审核人分析" subtitle="查看审核人表现排名" icon="👥" expanded={intExpanded === 'reviewer'} onToggle={() => setIntExpanded(intExpanded === 'reviewer' ? null : 'reviewer')}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--spacing-sm)' }}>
                  <button onClick={() => exportTable('reviewer', intReviewers)} className="button button-sm" disabled={intReviewers.length === 0}>导出审核人数据 ⬇</button>
                </div>
                {intReviewers.length > 0 ? (
                  <>
                    <div style={{ height: Math.min(intReviewers.length * 28 + 60, 280), marginBottom: 'var(--spacing-md)', background: 'var(--bg-secondary)', borderRadius: 'var(--radius)', padding: 'var(--spacing-sm)' }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={intReviewers.map((r, i) => ({ name: `${i + 1}.${r.reviewer_name}`, 正确率: r.raw_accuracy_rate || 0 }))} layout="vertical" margin={{ left: 70, right: 20, top: 5, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                          <XAxis type="number" domain={[95, 101]} stroke="var(--text-muted)" tick={{ fontSize: 10 }} unit="%" />
                          <YAxis type="category" dataKey="name" stroke="var(--text-muted)" tick={{ fontSize: 9 }} width={65} />
                          <Tooltip formatter={(val) => [`${Number(val).toFixed(2)}%`, '正确率']} contentStyle={{ fontSize: 11 }} />
                          <Bar dataKey="正确率" radius={[0, 4, 4, 0]} fill="#8b5cf6" maxBarSize={16} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: 'var(--bg-secondary)' }}>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>排名</th>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>审核人</th>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>审核量</th>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>正确率</th>
                            <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>误判数</th>
                          </tr>
                        </thead>
                        <tbody>
                          {intReviewers.map((r, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                              <td style={{ padding: 'var(--spacing-sm)' }}>{i + 1}</td>
                              <td style={{ padding: 'var(--spacing-sm)' }}>
                                <Link href={`/details?reviewer=${encodeURIComponent(r.reviewer_name || '')}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                                  {r.reviewer_name}
                                </Link>
                              </td>
                              <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{r.qa_cnt?.toLocaleString() || 0}</td>
                              <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: (r.raw_accuracy_rate || 0) >= REVIEWER_THRESHOLD ? 'var(--success)' : 'var(--danger)' }}>{r.raw_accuracy_rate?.toFixed(2)}%</td>
                              <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{r.misjudge_cnt || 0}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : <div style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>暂无数据</div>}
              </DrillSection>

              {/* Error drill */}
              <DrillSection title="错误类型分析" subtitle="查看高频错误类型" icon="🎯" expanded={intExpanded === 'error'} onToggle={() => setIntExpanded(intExpanded === 'error' ? null : 'error')}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--spacing-sm)' }}>
                  <button onClick={() => exportTable('error', intErrorTypes)} className="button button-sm" disabled={intErrorTypes.length === 0}>导出错误类型数据 ⬇</button>
                </div>
                {intErrorTypes.length > 0 ? (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: 'var(--bg-secondary)' }}>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>排名</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>错误类型</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>错误数</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>占比</th>
                        </tr>
                      </thead>
                      <tbody>
                        {intErrorTypes.map((e, i) => (
                          <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: 'var(--spacing-sm)' }}>{i + 1}</td>
                            <td style={{ padding: 'var(--spacing-sm)' }}>{e.label_name}</td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{e.cnt?.toLocaleString() || 0}</td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{e.pct?.toFixed(2)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : <div style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>暂无数据</div>}
              </DrillSection>
            </div>
          </div>
        </>
      )}

      {/* ════════════════════════════════════════════════════════ */}
      {/* ERROR DRILL TAB                                           */}
      {/* ════════════════════════════════════════════════════════ */}

      {activeTab === 'error' && (
        <>
          {/* ── 筛选栏 ── */}
          <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '14px 16px', marginBottom: 20 }}>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: '#6b7280' }}>开始日期</label>
                <input type="date" value={errStartDate} max={TODAY} onChange={e => setErrStartDate(e.target.value)}
                  style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: '#6b7280' }}>结束日期</label>
                <input type="date" value={errEndDate} max={TODAY} onChange={e => setErrEndDate(e.target.value)}
                  style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13 }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 12, color: '#6b7280' }}>数据来源</label>
                <select value={errSource} onChange={e => setErrSource(e.target.value as any)}
                  style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13, background: '#fff' }}>
                  <option value="all">全部</option>
                  <option value="external">外检</option>
                  <option value="internal">内检</option>
                </select>
              </div>
            </div>
            {/* ── 汇总指标 ── */}
            {errSummary && (
              <div style={{ display: 'flex', gap: 16, marginTop: 14, flexWrap: 'wrap' }}>
                <MetricCard label="错误总量" value={fmtInt(errSummary.total_errors)}
                  sub={`${errSummary.date_range?.days || 0}天汇总 · 来源: ${errSummary.source === 'all' ? '全部' : errSummary.source === 'external' ? '外检' : '内检'}`} />
                <MetricCard label="错误类型数" value={String(errSummary.total_error_types || 0)} />
                <MetricCard label="涉及队列" value={String(errSummary.heatmap_queue_count || 0)} />
              </div>
            )}
          </div>

          {/* ── 错误趋势面积图 ── */}
          <div className="panel" style={{ marginBottom: 20 }}>
            <h3 className="panel-title">📈 错误趋势（按来源分色）</h3>
            {errTrend.length > 0 ? (
              <div style={{ height: 280, marginTop: 12 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={errTrend} margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    {errSource === 'all' ? (
                      <>
                        <Area type="monotone" dataKey="external" stackId="1" stroke="#6366f1" fill="#6366f1" fillOpacity={0.4} name="外检" />
                        <Area type="monotone" dataKey="internal" stackId="1" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.4} name="内检" />
                      </>
                    ) : (
                      <Area type="monotone" dataKey={errSource} stroke={errSource === 'external' ? '#6366f1' : '#f59e0b'} fill={errSource === 'external' ? '#6366f1' : '#f59e0b'} fillOpacity={0.4} name={errSource === 'external' ? '外检' : '内检'} />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
                {errLoading ? '加载中...' : '暂无数据'}
              </div>
            )}
          </div>

          {/* ── 错误类型分布图 ── */}
          <div className="panel" style={{ marginBottom: 20 }}>
            <h3 className="panel-title">📊 错误类型分布（Top 20）</h3>
            {errDistribution.length > 0 ? (
              <div style={{ height: 320, marginTop: 12 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={errDistribution.map(e => ({
                    name: (e.error_type || '—').length > 12 ? (e.error_type || '—').substring(0, 10) + '..' : (e.error_type || '—'),
                    数量: e.count || 0,
                    占比: e.percentage || 0,
                  }))} layout="vertical" margin={{ left: 80, right: 20, top: 5, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={75} />
                    <Tooltip formatter={(v: any, name: any) => [name === '占比' ? `${v}%` : v, name]} />
                    <Bar dataKey="数量" fill="#8B5CF6" radius={[0, 4, 4, 0]} maxBarSize={20} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
                {errLoading ? '加载中...' : '暂无数据'}
              </div>
            )}
          </div>

          {/* ── 队列×错误类型 热力矩阵 ── */}
          <div className="panel" style={{ marginBottom: 20 }}>
            <h3 className="panel-title">🔥 队列 × 错误类型热力矩阵</h3>
            {errHeatmap.queues.length > 0 && errHeatmap.error_types.length > 0 ? (
              <div style={{ overflowX: 'auto', marginTop: 12 }}>
                <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr>
                      <th style={{ padding: '6px 10px', borderBottom: '2px solid #e5e7eb', color: '#6b7280', position: 'sticky', left: 0, background: '#fff', zIndex: 1, minWidth: 80 }}>队列</th>
                      {errHeatmap.error_types.map(et => (
                        <th key={et} style={{ padding: '6px 8px', borderBottom: '2px solid #e5e7eb', color: '#6b7280', writingMode: 'vertical-rl', textOrientation: 'mixed', maxWidth: 30, fontSize: 10 }}>{et.length > 6 ? et.substring(0, 5) + '..' : et}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {errHeatmap.queues.map(q => {
                      const maxCnt = Math.max(...errHeatmap.data.filter(d => d.queue_name === q).map(d => d.count), 1);
                      return (
                        <tr key={q}>
                          <td style={{ padding: '6px 10px', borderBottom: '1px solid #f3f4f6', fontWeight: 500, position: 'sticky', left: 0, background: '#fff', zIndex: 1, fontSize: 11 }}>{q.length > 10 ? q.substring(0, 8) + '..' : q}</td>
                          {errHeatmap.error_types.map(et => {
                            const cell = errHeatmap.data.find(d => d.queue_name === q && d.error_type === et);
                            const cnt = cell?.count || 0;
                            const intensity = maxCnt > 0 ? cnt / maxCnt : 0;
                            const bgColor = cnt === 0 ? '#f9fafb' : `rgba(239, 68, 68, ${0.15 + intensity * 0.7})`;
                            return (
                              <td key={et} title={`${q} × ${et}: ${cnt}`}
                                style={{ padding: '4px 6px', borderBottom: '1px solid #f3f4f6', textAlign: 'center', background: bgColor, color: intensity > 0.5 ? '#fff' : '#374151', fontWeight: intensity > 0.3 ? 600 : 400, fontSize: 11, minWidth: 30 }}>
                                {cnt > 0 ? cnt : ''}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
                {errLoading ? '加载中...' : '暂无数据'}
              </div>
            )}
          </div>

          {/* ── 受影响审核人 Top10 ── */}
          <div className="panel">
            <h3 className="panel-title">👤 受影响审核人（Top 10）</h3>
            {errReviewers.length > 0 ? (
              <div style={{ overflowX: 'auto', marginTop: 12 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: '#6b7280' }}>排名</th>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: '#6b7280' }}>审核人</th>
                      <th style={{ padding: '8px 12px', textAlign: 'center', color: '#6b7280' }}>来源</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280' }}>错误数</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: '#6b7280' }}>涉及队列</th>
                    </tr>
                  </thead>
                  <tbody>
                    {errReviewers.map((e, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ padding: '8px 12px' }}>{i + 1}</td>
                        <td style={{ padding: '8px 12px', fontWeight: i < 3 ? 600 : 400 }}>
                          <Link href={`/details?reviewer=${encodeURIComponent(e.reviewer_name || '')}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                            {e.reviewer_name || '—'}
                          </Link>
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 10, background: e.source === 'external' ? '#ede9fe' : '#fef3c7', color: e.source === 'external' ? '#6366f1' : '#d97706' }}>
                            {e.source === 'external' ? '外检' : '内检'}
                          </span>
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: e.error_count > 5 ? '#dc2626' : '#374151', fontWeight: 600 }}>{e.error_count}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>{e.affected_queues}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
                {errLoading ? '加载中...' : '暂无数据'}
              </div>
            )}
          </div>
        </>
      )}

      {/* ════════════════════════════════════════════════════════ */}
      {/* APPEAL ANALYSIS (shared across all tabs)                  */}
      {/* ════════════════════════════════════════════════════════ */}
      <div className="panel" style={{ marginTop: 24 }}>
        <h3 className="panel-title">💬 申诉分析</h3>
        {appealData ? (
          <div style={{ marginTop: 'var(--spacing-md)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 16 }}>
              <div style={{ background: '#f8fafc', borderRadius: 10, padding: '14px 16px', border: '1px solid #e5e7eb' }}>
                <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500 }}>申诉率</div>
                <div style={{ fontSize: 26, fontWeight: 700, color: '#6366f1', lineHeight: 1.1 }}>
                  {(appealData.appeal_rate ?? 0).toFixed(2)}%
                </div>
              </div>
              <div style={{ background: '#f0fdf4', borderRadius: 10, padding: '14px 16px', border: '1px solid #bbf7d0' }}>
                <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500 }}>申诉改判成功率</div>
                <div style={{ fontSize: 26, fontWeight: 700, color: '#10b981', lineHeight: 1.1 }}>
                  {(appealData.reverse_success_rate ?? 0).toFixed(2)}%
                </div>
              </div>
              <div style={{ background: '#fff7ed', borderRadius: 10, padding: '14px 16px', border: '1px solid #fed7aa' }}>
                <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500 }}>申诉改判数</div>
                <div style={{ fontSize: 26, fontWeight: 700, color: '#ea580c', lineHeight: 1.1 }}>
                  {appealData.reversed_cnt ?? 0}
                </div>
              </div>
            </div>
            {appealData.top_reasons && appealData.top_reasons.length > 0 && (
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 8 }}>Top 申诉理由</div>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                      <th style={{ textAlign: 'left', padding: '6px 8px', color: '#6b7280' }}>理由</th>
                      <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>次数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {appealData.top_reasons.map((r, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        <td style={{ padding: '6px 8px' }}>{r.reason}</td>
                        <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600 }}>{r.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: '16px 0', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
            待对接（需 /api/v1/external/appeal-summary 或 /api/v1/internal/appeal-summary API）
          </div>
        )}
      </div>

      {/* ── Shared drill section style ── */}
      <style jsx>{`
        .problem-section {
          background: var(--bg-primary);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: var(--spacing-md);
        }
      `}</style>
    </PageTemplate>
  );
}

// ── DrillSection Component ──

function DrillSection({ title, subtitle, icon, expanded, onToggle, children }: {
  title: string; subtitle: string; icon: string;
  expanded: boolean; onToggle: () => void; children: React.ReactNode;
}) {
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden', marginTop: 'var(--spacing-md)' }}>
      <button onClick={onToggle} style={{
        width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: 'var(--spacing-md)', background: 'var(--bg-primary)', border: 'none', cursor: 'pointer',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
          <span style={{ fontSize: '2em' }}>{icon}</span>
          <div>
            <div style={{ fontWeight: 600, fontSize: '1.1em', marginBottom: 4 }}>{title}</div>
            <div style={{ fontSize: '0.875em', color: 'var(--text-muted)' }}>{subtitle}</div>
          </div>
        </div>
        <span style={{ fontSize: '1.2em', color: 'var(--text-muted)' }}>{expanded ? '▼' : '▶'}</span>
      </button>
      {expanded && (
        <div style={{ padding: 'var(--spacing-md)', background: 'var(--bg-primary)', borderTop: '1px solid var(--border)' }}>
          {children}
        </div>
      )}
    </div>
  );
}
