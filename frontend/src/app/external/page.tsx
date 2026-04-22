'use client';
import { PageTemplate } from '@/components/page-template';
import { useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8002';

// ─────────────── 工具 ───────────────

function fmt(n: number | undefined | null, digits = 2) {
  if (n == null) return '—';
  return n.toFixed(digits);
}
function fmtInt(n: number | undefined | null) {
  if (n == null) return '—';
  return n.toLocaleString('zh-CN');
}

const QUEUE_THRESHOLD = 99;
const REVIEWER_THRESHOLD = 95;

// ─────────────── 类型 ───────────────

interface Summary {
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

// ─────────────── 子组件 ───────────────

function MetricCard({
  label, value, sub, color = '#374151', bg = '#fff', border = '#e5e7eb', alert = false,
}: {
  label: string; value: string; sub?: string;
  color?: string; bg?: string; border?: string; alert?: boolean;
}) {
  return (
    <div style={{
      background: bg, borderRadius: 12, padding: '16px 18px 12px',
      border: `${alert ? 2 : 1}px solid ${alert ? '#fca5a5' : border}`,
      boxShadow: alert ? '0 2px 8px rgba(239,68,68,.1)' : '0 1px 4px rgba(0,0,0,.05)',
      display: 'flex', flexDirection: 'column', gap: 3,
    }}>
      <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontSize: 30, fontWeight: 700, color: alert ? '#dc2626' : color, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: '#9ca3af' }}>{sub}</div>}
    </div>
  );
}

// 迷你柱状图
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

// 趋势折线（纯 SVG）
function TrendChart({ data }: { data: TrendItem[] }) {
  if (!data || data.length < 2) return (
    <div style={{ height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>
      数据不足，无法绘图
    </div>
  );
  const rates = data.map(d => d.correct_rate);
  const minR = Math.min(...rates);
  const maxR = Math.max(...rates);
  const range = maxR - minR || 0.1;
  const W = 600, H = 80, pad = 8;
  const points = data.map((d, i) => {
    const x = pad + (i / (data.length - 1)) * (W - pad * 2);
    const y = pad + ((maxR - d.correct_rate) / range) * (H - pad * 2);
    return `${x},${y}`;
  }).join(' ');
  return (
    <div style={{ overflowX: 'auto' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 80 }}>
        <polyline points={points} fill="none" stroke="#6366f1" strokeWidth={2} strokeLinejoin="round" />
        {data.map((d, i) => {
          const x = pad + (i / (data.length - 1)) * (W - pad * 2);
          const y = pad + ((maxR - d.correct_rate) / range) * (H - pad * 2);
          const alert = d.correct_rate < QUEUE_THRESHOLD;
          return (
            <g key={i}>
              <circle cx={x} cy={y} r={3} fill={alert ? '#ef4444' : '#6366f1'} />
              <title>{d.date}: {d.correct_rate.toFixed(2)}%</title>
            </g>
          );
        })}
      </svg>
      {/* x轴标签 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2 }}>
        <span style={{ fontSize: 11, color: '#9ca3af' }}>{data[0]?.date?.slice(5)}</span>
        <span style={{ fontSize: 11, color: '#9ca3af' }}>{data[data.length - 1]?.date?.slice(5)}</span>
      </div>
    </div>
  );
}

// ─────────────── 页面主体 ───────────────

const TODAY = new Date().toISOString().slice(0, 10);

export default function ExternalPage() {
  // 日期区间
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 6);
    return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(TODAY);
  const [groupName, setGroupName] = useState('');

  // 数据
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [queues, setQueues] = useState<QueueItem[]>([]);
  const [reviewers, setReviewers] = useState<ReviewerItem[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  // 审核人视图
  const [reviewerView, setReviewerView] = useState<'problem' | 'all'>('problem');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const base = `${API_BASE}/api/v1/external`;
      const gp = groupName ? `&group_name=${encodeURIComponent(groupName)}` : '';
      const dr = `start_date=${startDate}&end_date=${endDate}`;

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

      setSummary(sumD);
      setTrend(trendD || []);
      setQueues(queueD || []);
      setReviewers(reviewerD || []);
      setGroups(metaD?.groups || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, groupName]);

  useEffect(() => { load(); }, [load]);

  const alertQueues = queues.filter(q => q.needs_attention);
  const problemReviewers = reviewers.filter(r => r.needs_attention);
  const displayReviewers = reviewerView === 'problem' ? problemReviewers : reviewers;

  const maxErr = Math.max(...queues.map(q => q.misjudge_cnt + q.missjudge_cnt), 1);

  return (
    <PageTemplate title="外检看板" subtitle="外部质检数据监控 · 队列排名 · 审核人分析">

      {/* ── 筛选栏 ── */}
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '14px 16px', marginBottom: 20 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          🔍 筛选条件
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: '#6b7280' }}>开始日期</label>
            <input type="date" value={startDate} max={endDate}
              onChange={e => setStartDate(e.target.value)}
              style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13 }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: '#6b7280' }}>结束日期</label>
            <input type="date" value={endDate} min={startDate} max={TODAY}
              onChange={e => setEndDate(e.target.value)}
              style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13 }} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 12, color: '#6b7280' }}>组别</label>
            <select value={groupName} onChange={e => setGroupName(e.target.value)}
              style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '5px 8px', fontSize: 13, minWidth: 140 }}>
              <option value="">全部</option>
              {groups.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <button onClick={load} disabled={loading}
            style={{ padding: '6px 16px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer', alignSelf: 'flex-end' }}>
            {loading ? '加载中…' : '查询'}
          </button>
        </div>
      </div>

      {/* ── 核心指标卡片 ── */}
      {summary?.has_data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px,1fr))', gap: 16, marginBottom: 24 }}>
          <MetricCard label="抽检总量" value={fmtInt(summary.total_count)} sub={`${summary.start} ~ ${summary.end}`} color="#6366f1" />
          <MetricCard label="综合正确率" value={`${fmt(summary.correct_rate)}%`}
            sub="目标 ≥99%" color="#059669"
            bg={summary.correct_rate < QUEUE_THRESHOLD ? '#fff1f2' : '#f0fdf4'}
            alert={summary.correct_rate < QUEUE_THRESHOLD} />
          <MetricCard label="错判数" value={fmtInt(summary.misjudge_cnt)}
            sub={`错判率 ${fmt(summary.misjudge_rate)}%`} color="#2563eb" />
          <MetricCard label="漏判数" value={fmtInt(summary.missjudge_cnt)}
            sub={`漏判率 ${fmt(summary.missjudge_rate)}%`} color="#d97706" />
          <MetricCard label="申诉改判" value={fmtInt(summary.appeal_reversed_cnt)}
            sub={`改判率 ${fmt(summary.appeal_reverse_rate)}%`} color="#7c3aed" />
          <MetricCard label="队列数" value={String(summary.queue_count)} sub="参与队列" color="#374151" />
        </div>
      )}
      {summary && !summary.has_data && (
        <div style={{ padding: '32px 0', textAlign: 'center', color: '#9ca3af', fontSize: 14, marginBottom: 24 }}>
          所选日期范围暂无数据
        </div>
      )}

      {/* ── 正确率趋势 ── */}
      {trend.length > 0 && (
        <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '14px 16px', marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 12 }}>
            📈 正确率趋势（<span style={{ color: '#6366f1' }}>蓝点正常</span> / <span style={{ color: '#ef4444' }}>红点预警</span>）
          </div>
          <TrendChart data={trend} />
          <div style={{ marginTop: 8, display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {trend.map(d => (
              <div key={d.date} style={{ fontSize: 12, color: d.correct_rate < QUEUE_THRESHOLD ? '#dc2626' : '#6b7280' }}>
                {d.date.slice(5)} <strong>{d.correct_rate.toFixed(2)}%</strong>
              </div>
            ))}
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
              共 {queues.length} 条 · 按正确率升序（最需关注在最前）
            </span>
          </span>
        </div>
        {queues.length === 0 ? (
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
                {queues.map((q, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #f3f4f6', background: q.needs_attention ? '#fff7f7' : '#fff' }}>
                    <td style={{ padding: '8px 12px' }}>
                      <span style={{ fontSize: 11, background: q.needs_attention ? '#fee2e2' : '#f3f4f6', color: q.needs_attention ? '#dc2626' : '#6b7280', borderRadius: 4, padding: '2px 6px' }}>
                        {q.group_name}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.queue_name}</td>
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
              全部 ({reviewers.length})
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
                      {r.reviewer_name}
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

    </PageTemplate>
  );
}
