'use client';

import { PageTemplate } from '@/components/page-template';
import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// ── 阈值常量（全站统一） ──
const QUEUE_THRESHOLD = 99;
const REVIEWER_THRESHOLD = 95;

// ── 颜色 ──
const COLORS = ['#8B5CF6', '#6366F1', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#EC4899', '#14B8A6'];

// ── 类型 ──
interface Summary {
  date: string; has_data: boolean;
  total_count: number; correct_count: number;
  misjudge_cnt: number; missjudge_cnt: number;
  correct_rate: number; misjudge_rate: number; missjudge_rate: number;
  appeal_reversed_cnt: number; appeal_reverse_rate: number;
  queue_count: number;
}

interface TrendItem {
  date: string; total_count: number; correct_rate: number;
  misjudge_cnt: number; missjudge_cnt: number;
}

interface QueueItem {
  queue_name: string; group_name: string;
  total_count: number; correct_rate: number;
  misjudge_cnt: number; missjudge_cnt: number;
  needs_attention: boolean;
}

interface ReviewerItem {
  reviewer_name: string; group_name: string; queue_name: string;
  review_count: number; correct_rate: number;
  misjudge_cnt: number; missjudge_cnt: number;
  needs_attention: boolean;
}

interface ErrorTypeItem {
  error_type: string; count: number; rate: number;
}

interface LabelAccItem {
  label: string; accuracy: number; count: number;
}

interface ContentTypeItem {
  content_type: string; count: number; correct_rate: number; pct: number;
}

interface HourlyItem {
  hour: number; misjudge_cnt: number; missjudge_cnt: number; correct_rate: number; total: number;
}

// ── 工具函数 ──
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

// ── 数据来源类型（DS-1 解决方案） ──
type DataSource = 'all' | 'external' | 'internal';
const SOURCE_LABELS: Record<DataSource, string> = {
  all: '全局',
  external: '外检',
  internal: '内检',
};

/**
 * 🚀 运营总览 v8.0 — 全站仪表盘
 *
 * 核心原则：一眼看全局 → 一秒找问题 → 一步到明细
 * 布局：6指标卡 + 7日趋势 + 预警区 + 高频错误/标签/热力图/内容类型 + 快速入口
 * v8: 修复 DS-1(来源标注) + DS-3(内容类型真实API) + FN-1(字段名统一)
 */
export default function HomePage() {
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [dateRangeLoaded, setDateRangeLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 数据来源切换（全局/外检/内检）— 解决 DS-1
  const [source, setSource] = useState<DataSource>('all');

  // 数据状态
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [alertQueues, setAlertQueues] = useState<QueueItem[]>([]);
  const [alertReviewers, setAlertReviewers] = useState<ReviewerItem[]>([]);
  const [errorTypes, setErrorTypes] = useState<ErrorTypeItem[]>([]);
  const [labelAcc, setLabelAcc] = useState<LabelAccItem[]>([]);
  const [contentTypes, setContentTypes] = useState<ContentTypeItem[]>([]);
  const [hourlyData, setHourlyData] = useState<HourlyItem[]>([]);

  // 日期范围切换（日/周/月）
  const [grain, setGrain] = useState<'day' | 'week' | 'month'>('day');

  const loadData = useCallback(async () => {
    if (!dateRangeLoaded) return;
    setLoading(true);
    setError(null);
    try {
      const d = date;
      // ── 根据 source 选择 API 前缀（解决 DS-1） ──
      const summaryBase = source === 'internal'
        ? `${API_BASE}/api/v1/internal/summary`
        : `${API_BASE}/api/v1/monitor/summary`;
      const trendBase = source === 'internal'
        ? `${API_BASE}/api/v1/internal/trend`
        : `${API_BASE}/api/v1/external/trend`;
      const queueBase = source === 'internal'
        ? `${API_BASE}/api/v1/internal/queues`
        : `${API_BASE}/api/v1/monitor/queue-ranking`;
      const reviewerBase = source === 'internal'
        ? `${API_BASE}/api/v1/internal/reviewers`
        : `${API_BASE}/api/v1/monitor/reviewer-ranking`;

      const qcModuleParam = source !== 'all' ? `&qc_module=${source}` : '';
      const summaryDateParam = source === 'internal' ? `selected_date=${d}` : `date=${d}`;
      // grain 参数（日/周/月）传给支持它的 API
      const grainParam = `&grain=${grain}`;

      // 并行请求所有数据
      const [
        summaryRes, trendRes, queueRes, reviewerRes,
        errorTypeRes, labelRes, contentRes, hourlyRes,
      ] = await Promise.allSettled([
        fetch(`${summaryBase}?${summaryDateParam}${grainParam}`),
        fetch(`${trendBase}?end=${d}&days=7${qcModuleParam}${grainParam}`),
        fetch(`${queueBase}?date=${d}&limit=50${qcModuleParam}`),
        fetch(`${reviewerBase}?date=${d}&limit=200${qcModuleParam}`),
        fetch(`${API_BASE}/api/v1/analysis/error-overview?days=7${qcModuleParam}`),
        fetch(`${API_BASE}/api/v1/analysis/label-accuracy?date=${d}&limit=10${qcModuleParam}`),
        // DS-3: 内容类型分布对接真实 API（替代硬编码 *0.65/0.22/0.10/0.03）
        fetch(`${API_BASE}/api/v1/analysis/content-type-distribution?date=${d}${qcModuleParam}`),
        // 时段热力图对接真实 API
        fetch(`${API_BASE}/api/v1/analysis/hourly-quality?date=${d}${qcModuleParam}`),
      ]);

      // 1. Summary — FN-1: 使用统一字段名，不再做 || 兜底
      if (summaryRes.status === 'fulfilled' && summaryRes.value.ok) {
        const raw = await summaryRes.value.json();
        const s = raw.data || raw;
        setSummary({
          date: s.date || d,
          has_data: s.has_data ?? true,
          total_count: s.total_count ?? 0,
          correct_count: s.correct_count ?? 0,
          misjudge_cnt: s.misjudge_cnt ?? 0,
          missjudge_cnt: s.missjudge_cnt ?? 0,
          correct_rate: s.correct_rate ?? 0,
          misjudge_rate: s.misjudge_rate ?? 0,
          missjudge_rate: s.missjudge_rate ?? 0,
          appeal_reversed_cnt: s.appeal_reversed_cnt ?? 0,
          appeal_reverse_rate: s.appeal_reverse_rate ?? 0,
          queue_count: s.queue_count ?? 0,
        });
      }

      // 2. Trend (7天)
      if (trendRes.status === 'fulfilled' && trendRes.value.ok) {
        const t = await trendRes.value.json();
        const items = Array.isArray(t) ? t : (t.data || t.trend || []);
        setTrend(items.map((it: any) => ({
          date: it.date || it.biz_date || '',
          total_count: it.total_count ?? 0,
          correct_rate: it.correct_rate ?? 0,
          misjudge_cnt: it.misjudge_cnt ?? 0,
          missjudge_cnt: it.missjudge_cnt ?? 0,
        })));
      }

      // 3. Alert Queues (< 99%)
      if (queueRes.status === 'fulfilled' && queueRes.value.ok) {
        const q = await queueRes.value.json();
        const queues = (Array.isArray(q) ? q : (q.data?.items || q.data || q.queues || [])).map((it: any) => ({
          queue_name: it.queue_name || '',
          group_name: it.group_name || '',
          total_count: it.total_count ?? 0,
          correct_rate: it.correct_rate ?? 0,
          misjudge_cnt: it.misjudge_cnt ?? 0,
          missjudge_cnt: it.missjudge_cnt ?? 0,
          needs_attention: it.needs_attention ?? (it.correct_rate ?? 100) < QUEUE_THRESHOLD,
        }));
        setAlertQueues(queues.filter((item: QueueItem) => item.correct_rate < QUEUE_THRESHOLD).slice(0, 5));
      }

      // 4. Alert Reviewers (< 95%)
      if (reviewerRes.status === 'fulfilled' && reviewerRes.value.ok) {
        const r = await reviewerRes.value.json();
        const reviewers = (Array.isArray(r) ? r : (r.data?.items || r.data || r.reviewers || [])).map((it: any) => ({
          reviewer_name: it.reviewer_name || '',
          group_name: it.group_name || '',
          queue_name: it.queue_name || '',
          review_count: it.review_count ?? 0,
          correct_rate: it.correct_rate ?? 0,
          misjudge_cnt: it.misjudge_cnt ?? 0,
          missjudge_cnt: it.missjudge_cnt ?? 0,
          needs_attention: it.needs_attention ?? (it.correct_rate ?? 100) < REVIEWER_THRESHOLD,
        }));
        setAlertReviewers(reviewers.filter((item: ReviewerItem) => item.needs_attention || item.correct_rate < REVIEWER_THRESHOLD).slice(0, 5));
      }

      // 5. Error Types Top5 — FN-1: 统一字段名
      if (errorTypeRes.status === 'fulfilled' && errorTypeRes.value.ok) {
        const e = await errorTypeRes.value.json();
        const dist = e.error_distribution || e.data || [];
        setErrorTypes((Array.isArray(dist) ? dist : []).slice(0, 5).map((it: any) => ({
          error_type: it.error_type || '',
          count: it.count ?? 0,
          rate: it.rate ?? it.percentage ?? 0,
        })));
      }

      // 6. Label Accuracy Top5 — FN-1: 统一字段名
      if (labelRes.status === 'fulfilled' && labelRes.value.ok) {
        const l = await labelRes.value.json();
        const items = l.data || l.error_types || l.labels || [];
        if (Array.isArray(items)) {
          setLabelAcc(items.slice(0, 5).map((it: any) => ({
            label: it.label || it.error_type || '',
            accuracy: it.accuracy_rate ?? 0,
            count: it.count ?? 0,
          })));
        }
      } else {
        // 降级：从 error-overview 推算
        setLabelAcc([]);
      }

      // 7. Content Type — DS-3: 对接真实 API
      if (contentRes.status === 'fulfilled' && contentRes.value.ok) {
        const c = await contentRes.value.json();
        const items = c.data || c.content_types || [];
        if (Array.isArray(items) && items.length > 0) {
          const totalCt = items.reduce((s: number, it: any) => s + (it.count || 0), 0);
          setContentTypes(items.map((it: any) => ({
            content_type: it.content_type || '未知',
            count: it.count || 0,
            correct_rate: it.accuracy_rate ?? 0,
            pct: totalCt > 0 ? Math.round(it.count / totalCt * 100) : 0,
          })));
        } else {
          setContentTypes([]);
        }
      } else {
        // API 不存在时展示空态，不再用硬编码假数据
        setContentTypes([]);
      }

      // 8. Hourly heatmap — 对接真实 API
      if (hourlyRes.status === 'fulfilled' && hourlyRes.value.ok) {
        const h = await hourlyRes.value.json();
        const items = h.data || h.hourly || [];
        if (Array.isArray(items) && items.length > 0) {
          setHourlyData(items.map((it: any) => ({
            hour: it.hour ?? 0,
            misjudge_cnt: it.misjudge_cnt ?? 0,
            missjudge_cnt: it.missjudge_cnt ?? 0,
            correct_rate: it.accuracy_rate ?? 0,
            total: it.count ?? 0,
          })));
        } else {
          setHourlyData([]);
        }
      } else {
        setHourlyData([]);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [date, source, grain]);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/meta/date-range`)
      .then((r) => r.json())
      .then((d) => {
        const data = d.data || d;
        const max = data.default_selected_date || data.max_date;
        if (max) setDate(max);
      })
      .catch(() => {})
      .finally(() => setDateRangeLoaded(true));
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // 计算衍生指标
  const errorTotal = (summary?.misjudge_cnt || 0) + (summary?.missjudge_cnt || 0);
  const errorTotalRate = summary?.total_count ? (errorTotal / summary.total_count * 100) : 0;

  return (
    <PageTemplate
      title="运营总览"
      subtitle="全局质量指标、趋势与预警"
      actions={
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="date" value={date} onChange={e => setDate(e.target.value)} className="input" style={{ width: 150 }} />
          {/* 日期粒度 */}
          <div style={{ display: 'flex', gap: 4, background: '#f3f4f6', borderRadius: 8, padding: 3 }}>
            {(['day', 'week', 'month'] as const).map(g => (
              <button key={g} onClick={() => setGrain(g)}
                className={grain === g ? 'button' : ''}
                style={{
                  padding: '4px 12px', borderRadius: 6, fontSize: 13,
                  background: grain === g ? '#8B5CF6' : 'transparent',
                  color: grain === g ? '#fff' : '#6b7280',
                  border: 'none', cursor: 'pointer', fontWeight: 500,
                }}>
                {{ day: '日', week: '周', month: '月' }[g]}
              </button>
            ))}
          </div>
          {/* 数据来源切换 — DS-1 */}
          <div style={{ display: 'flex', gap: 4, background: '#f3f4f6', borderRadius: 8, padding: 3 }}>
            {(['all', 'external', 'internal'] as DataSource[]).map(s => (
              <button key={s} onClick={() => setSource(s)}
                style={{
                  padding: '4px 12px', borderRadius: 6, fontSize: 13,
                  background: source === s ? '#6366f1' : 'transparent',
                  color: source === s ? '#fff' : '#6b7280',
                  border: 'none', cursor: 'pointer', fontWeight: 500,
                }}>
                {SOURCE_LABELS[s]}
              </button>
            ))}
          </div>
        </div>
      }
    >
      {error && (
        <div className="panel" style={{ background: 'var(--danger-soft)', borderColor: 'var(--danger)', marginBottom: 24 }}>
          <p style={{ color: 'var(--danger)' }}>❌ {error}</p>
        </div>
      )}

      {/* ═══ 1. 六指标卡 ═══ */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 14, marginBottom: 24,
      }}>
        <MetricCard label="抽检总量" value={fmtInt(summary?.total_count)} sub={summary?.queue_count ? `${summary.queue_count}个队列` : undefined} />
        <MetricCard label="综合正确率" value={summary ? `${fmt(summary.correct_rate)}%` : '—'}
          color={summary ? rateColor(summary.correct_rate) : '#374151'}
          alert={summary ? summary.correct_rate < QUEUE_THRESHOLD : false}
          sub={summary?.correct_rate !== undefined && summary.correct_rate < QUEUE_THRESHOLD ? `⚠️ <${QUEUE_THRESHOLD}%` : undefined} />
        <MetricCard label="错判数" value={fmtInt(summary?.misjudge_cnt)} color={summary?.misjudge_cnt ? '#ef4444' : '#374151'} alert={(summary?.misjudge_cnt || 0) > 0} />
        <MetricCard label="漏判数" value={fmtInt(summary?.missjudge_cnt)} color={summary?.missjudge_cnt ? '#f97316' : '#374151'} alert={(summary?.missjudge_cnt || 0) > 0} />
        <MetricCard label="申诉改判" value={fmtInt(summary?.appeal_reversed_cnt)} />
        <MetricCard label="错漏合计" value={fmtInt(errorTotal)} sub={errorTotalRate > 1 ? `占${fmt(errorTotalRate)}%` : undefined} alert={errorTotalRate > 1} />
      </div>
      {/* 来源标注 — DS-1 */}
      <div style={{ fontSize: 11, color: '#9ca3af', marginBottom: 16, textAlign: 'right' }}>
        数据来源：{SOURCE_LABELS[source]}{source !== 'all' && ' · 仅展示该模块数据'}
      </div>

      {/* ═══ 2. 7日正确率趋势 ═══ */}
      {trend.length >= 2 && (
        <div className="panel" style={{ marginBottom: 24 }}>
          <h3 className="panel-title">📈 7日正确率趋势</h3>
          <div style={{ height: 200, marginTop: 12 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <defs>
                  <linearGradient id="rateGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis domain={[97, 100]} tick={{ fontSize: 12 }} tickFormatter={(v: number) => `${v}%`} />
                <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}%`, '正确率']} labelFormatter={(l: any) => `日期: ${l}`} />
                <Area type="monotone" dataKey="correct_rate" stroke="#8B5CF6" fill="url(#rateGrad)" strokeWidth={2} dot={{ r: 3 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ═══ 3. 预警区 ═══ */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        {/* 预警队列 */}
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 className="panel-title" style={{ margin: 0 }}>🔴 预警队列 ({alertQueues.length}个)</h3>
            <Link href="/analysis?tab=external" style={{ fontSize: 12, color: '#8B5CF6', textDecoration: 'none' }}>
              查看全部 →
            </Link>
          </div>
          {alertQueues.length === 0 ? (
            <div style={{ color: '#9ca3af', fontSize: 13, padding: 16, textAlign: 'center' }}>
              {loading ? <LoadingSkeleton /> : '✅ 所有队列正确率 ≥ 99%'}
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: '#6b7280' }}>队列</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>正确率</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>错判/漏判</th>
                </tr>
              </thead>
              <tbody>
                {alertQueues.map((q, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '6px 8px' }}>
                      <Link href={`/analysis?tab=external&queue=${encodeURIComponent(q.queue_name)}`} style={{ color: '#374151', textDecoration: 'none' }}>
                        {q.queue_name}
                      </Link>
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600, color: rateColor(q.correct_rate) }}>
                      {fmt(q.correct_rate)}%
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', color: '#6b7280' }}>
                      <span style={{ color: '#ef4444' }}>{q.misjudge_cnt}</span> / <span style={{ color: '#f97316' }}>{q.missjudge_cnt}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* 预警审核人 */}
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 className="panel-title" style={{ margin: 0 }}>🔴 预警审核人 ({alertReviewers.length}个)</h3>
            <Link href="/details?mode=reviewer" style={{ fontSize: 12, color: '#8B5CF6', textDecoration: 'none' }}>
              查看全部 →
            </Link>
          </div>
          {alertReviewers.length === 0 ? (
            <div style={{ color: '#9ca3af', fontSize: 13, padding: 16, textAlign: 'center' }}>
              {loading ? <LoadingSkeleton /> : '✅ 所有审核人正确率 ≥ 95%'}
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: '#6b7280' }}>审核人</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: '#6b7280' }}>队列</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>正确率</th>
                </tr>
              </thead>
              <tbody>
                {alertReviewers.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '6px 8px' }}>
                      <Link href={`/details?reviewer=${encodeURIComponent(r.reviewer_name)}`} style={{ color: '#374151', textDecoration: 'none' }}>
                        {r.reviewer_name}
                      </Link>
                    </td>
                    <td style={{ padding: '6px 8px', color: '#6b7280', fontSize: 12 }}>{r.queue_name}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600, color: rateColor(r.correct_rate) }}>
                      {fmt(r.correct_rate)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ═══ 4. 高频错误 Top5 + 标签准确率 Top5 ═══ */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        {/* 高频错误 */}
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 className="panel-title" style={{ margin: 0 }}>🔥 高频错误 Top5</h3>
            <Link href="/analysis?tab=error" style={{ fontSize: 12, color: '#8B5CF6', textDecoration: 'none' }}>
              深钻分析 →
            </Link>
          </div>
          {errorTypes.length === 0 ? (
            <>
              <EmptyState message={loading ? undefined : '暂无错误数据'} icon="🔥" />
              {loading && <LoadingSkeleton />}
            </>
          ) : (
            <div style={{ height: 180 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={errorTypes} layout="vertical" margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 12 }} />
                  <YAxis dataKey="error_type" type="category" tick={{ fontSize: 12 }} width={80} />
                  <Tooltip formatter={(v: any, name: any) => [v, name === 'count' ? '数量' : name]} />
                  <Bar dataKey="count" fill="#8B5CF6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* 标签准确率 */}
        <div className="panel">
          <h3 className="panel-title">🏷️ 标签准确率排行 Top5</h3>
          {labelAcc.length === 0 ? (
            <>
              <EmptyState message={loading ? undefined : '暂无标签数据'} icon="🏷️" />
              {loading && <LoadingSkeleton />}
            </>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px', color: '#6b7280' }}>标签</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>正确率</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>样本量</th>
                  <th style={{ width: 80, padding: '6px 8px' }}></th>
                </tr>
              </thead>
              <tbody>
                {labelAcc.map((l, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '6px 8px' }}>{l.label}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600, color: rateColor(l.accuracy) }}>
                      {fmt(l.accuracy)}%
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', color: '#6b7280' }}>
                      {fmtInt(l.count)}
                    </td>
                    <td style={{ padding: '6px 8px' }}>
                      <div style={{ height: 6, background: '#f3f4f6', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${Math.max(l.accuracy, 0)}%`, height: '100%', background: rateColor(l.accuracy), borderRadius: 3 }} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ═══ 5. 时段质量热力图 + 内容类型分布 ═══ */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        {/* 时段热力图 */}
        <div className="panel">
          <h3 className="panel-title">📅 时段质量热力图</h3>
          {hourlyData.length === 0 ? (
            <EmptyState message="待对接（需 /api/v1/analysis/hourly-quality API）" icon="📅" />
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                  <th style={{ padding: '6px 8px', color: '#6b7280' }}>时段</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>错判</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>漏判</th>
                  <th style={{ textAlign: 'right', padding: '6px 8px', color: '#6b7280' }}>正确率</th>
                </tr>
              </thead>
              <tbody>
                {hourlyData.map((h, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '6px 8px' }}>{h.hour}时</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{h.misjudge_cnt}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{h.missjudge_cnt}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 600, color: rateColor(h.correct_rate) }}>
                      {fmt(h.correct_rate)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* 内容类型分布 */}
        <div className="panel">
          <h3 className="panel-title">📂 内容类型分布</h3>
          {contentTypes.length === 0 ? (
            <EmptyState message="待对接（需 /api/v1/analysis/content-type-distribution API）" icon="📂" />
          ) : (
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div style={{ width: 140, height: 140 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={contentTypes} dataKey="pct" nameKey="content_type" cx="50%" cy="50%" outerRadius={60}>
                      {contentTypes.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v: any) => [`${v}%`, '占比']} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div style={{ flex: 1 }}>
                {contentTypes.map((c, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', fontSize: 13 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 10, height: 10, borderRadius: 2, background: COLORS[i % COLORS.length] }} />
                      <span>{c.content_type}</span>
                      <span style={{ color: '#9ca3af' }}>{c.pct}%</span>
                    </div>
                    <span style={{ fontWeight: 500, color: rateColor(c.correct_rate) }}>{fmt(c.correct_rate)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ═══ 6. 快速入口（紧凑横条） ═══ */}
      <div className="panel" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>🚀 快速入口</span>
          {[
            { label: '质检分析', href: '/analysis' },
            { label: '新人追踪', href: '/newcomers' },
            { label: 'BadCase库', href: '/badcase' },
            { label: '明细查询', href: '/details' },
          ].map(item => (
            <Link key={item.href} href={item.href}
              style={{
                padding: '6px 16px', borderRadius: 8, fontSize: 13, fontWeight: 500,
                background: '#f3f4f6', color: '#374151', textDecoration: 'none',
                transition: 'all 0.15s',
              }}>
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </PageTemplate>
  );
}

// ── 共享子组件 ──

function EmptyState({ message = '暂无数据', icon = '📋' }: { message?: string; icon?: string }) {
  return (
    <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
      <div style={{ fontSize: '2em', marginBottom: 8 }}>{icon}</div>
      <div>{message}</div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ display: 'flex', gap: 8, padding: '16px 0', justifyContent: 'center' }}>
      {[1, 2, 3].map(i => (
        <div key={i} style={{
          width: 80, height: 14, background: '#e5e7eb', borderRadius: 4,
          animation: 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        }} />
      ))}
    </div>
  );
}

function MetricCard({
  label, value, sub, color = '#374151', alert = false,
}: {
  label: string; value: string; sub?: string; color?: string; alert?: boolean;
}) {
  return (
    <div style={{
      background: '#fff', borderRadius: 12, padding: '16px 18px 12px',
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
