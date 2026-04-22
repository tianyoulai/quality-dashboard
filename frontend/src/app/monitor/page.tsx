'use client';

import { PageTemplate } from '@/components/page-template';
import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8002';

interface MetaData { groups: string[]; queues: string[]; }

interface SummaryData {
  date: string; has_data: boolean;
  total_count: number; correct_count: number;
  misjudge_cnt: number; missjudge_cnt: number;
  correct_rate: number; misjudge_rate: number; missjudge_rate: number;
  appeal_reversed_cnt: number; appeal_reverse_rate: number;
  queue_count: number;
}

interface QueueItem {
  group_name: string; queue_name: string; total_count: number;
  correct_rate: number; misjudge_rate: number; missjudge_rate: number;
  misjudge_cnt: number; missjudge_cnt: number;
  appeal_reverse_rate: number; reviewer_cnt: number; needs_attention: boolean;
}

interface ReviewerItem {
  reviewer_name: string; group_name: string; queue_name: string;
  review_count: number; correct_rate: number;
  misjudge_rate: number; missjudge_rate: number;
  misjudge_cnt: number; missjudge_cnt: number; needs_attention: boolean;
}

export default function MonitorPage() {
  const [date, setDate] = useState('2026-04-21');
  const [groupName, setGroupName] = useState('全部');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [metaData, setMetaData] = useState<MetaData | null>(null);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [queueData, setQueueData] = useState<QueueItem[]>([]);
  const [reviewerData, setReviewerData] = useState<ReviewerItem[]>([]);
  const [showAllReviewers, setShowAllReviewers] = useState(false);

  useEffect(() => { loadMeta(); }, [date]);

  async function loadMeta() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/monitor/meta?date=${date}`);
      setMetaData(res.ok ? await res.json() : { groups: [], queues: [] });
    } catch { setMetaData({ groups: [], queues: [] }); }
  }

  async function handleQuery() {
    setLoading(true); setError(null);
    const g = groupName === '全部' ? '' : encodeURIComponent(groupName);
    try {
      const [sRes, qRes, rRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/monitor/summary?date=${date}&group_name=${g}`),
        fetch(`${API_BASE}/api/v1/monitor/queue-ranking?date=${date}&group_name=${g}&limit=50`),
        fetch(`${API_BASE}/api/v1/monitor/reviewer-ranking?date=${date}&group_name=${g}&limit=200`),
      ]);
      if (!sRes.ok || !qRes.ok || !rRes.ok) throw new Error('API 请求失败');
      const [sJson, qJson, rJson] = await Promise.all([sRes.json(), qRes.json(), rRes.json()]);
      setSummary(sJson);
      setQueueData(Array.isArray(qJson) ? qJson : []);
      setReviewerData(Array.isArray(rJson) ? rJson : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally { setLoading(false); }
  }

  const displayedReviewers = showAllReviewers ? reviewerData : reviewerData.filter(r => r.needs_attention);
  const problemQueues = queueData.filter(q => q.needs_attention).slice(0, 10);

  return (
    <PageTemplate
      title="实时监控"
      subtitle="队列与人员正确率排名"
      actions={
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="date" value={date} onChange={e => setDate(e.target.value)} className="input" style={{ width: 160 }} />
          <select value={groupName} onChange={e => setGroupName(e.target.value)} className="input" style={{ width: 180 }}>
            <option value="全部">全部</option>
            {metaData?.groups.map(g => <option key={g} value={g}>{g}</option>)}
          </select>
          <button onClick={handleQuery} className="button" disabled={loading}>
            {loading ? '查询中...' : '查询'}
          </button>
        </div>
      }
    >
      {error && (
        <div className="panel" style={{ background: 'var(--danger-bg)', borderColor: 'var(--danger)', marginBottom: 24 }}>
          <p style={{ color: 'var(--danger)' }}>❌ {error}</p>
        </div>
      )}

      {/* ── 核心指标数字卡片 ── */}
      {summary?.has_data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(155px, 1fr))', gap: 14, marginBottom: 32 }}>
          <MetricCard label="抽检总量" value={summary.total_count.toLocaleString()} sub={`${summary.queue_count} 个队列 · ${date}`} color="#6366f1" />
          <MetricCard
            label="综合正确率"
            value={`${summary.correct_rate.toFixed(2)}%`}
            sub="目标 ≥ 99%"
            color={summary.correct_rate >= 99 ? '#10b981' : '#ef4444'}
            highlight={summary.correct_rate < 99}
          />
          <MetricCard label="错判数" value={summary.misjudge_cnt.toLocaleString()} sub={`错判率 ${summary.misjudge_rate.toFixed(2)}%`} color="#3b82f6" />
          <MetricCard label="漏判数" value={summary.missjudge_cnt.toLocaleString()} sub={`漏判率 ${summary.missjudge_rate.toFixed(2)}%`} color="#f97316" />
          <MetricCard label="申诉改判" value={summary.appeal_reversed_cnt.toLocaleString()} sub={`改判率 ${summary.appeal_reverse_rate.toFixed(2)}%`} color="#8b5cf6" />
          <MetricCard
            label="错漏合计"
            value={(summary.misjudge_cnt + summary.missjudge_cnt).toLocaleString()}
            sub={`占总量 ${((summary.misjudge_cnt + summary.missjudge_cnt) / summary.total_count * 100).toFixed(2)}%`}
            color="#64748b"
          />
        </div>
      )}

      {/* ── 队列排名 ── */}
      <div className="panel" style={{ marginBottom: 32 }}>
        <h3 className="panel-title">📋 队列正确率排名</h3>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '6px 0 16px' }}>正确率 &lt; 99% 红色预警</p>
        {queueData.length === 0 ? (
          <p style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
            {loading ? '加载中...' : '暂无数据，请选择日期后点击查询'}
          </p>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', minWidth: 780 }}>
                <thead>
                  <tr>
                    <th style={{ width: 48 }}>排名</th>
                    <th>组别</th>
                    <th>队列名称</th>
                    <th style={{ textAlign: 'right' }}>抽检量</th>
                    <th style={{ textAlign: 'right' }}>正确率</th>
                    <th style={{ textAlign: 'right' }}>错判率</th>
                    <th style={{ textAlign: 'right' }}>漏判率</th>
                    <th style={{ textAlign: 'right' }}>申诉改判率</th>
                    <th style={{ textAlign: 'right' }}>审核人数</th>
                  </tr>
                </thead>
                <tbody>
                  {queueData.map((item, i) => (
                    <tr key={i} style={{ backgroundColor: item.needs_attention ? 'var(--danger-bg)' : undefined }}>
                      <td style={{ textAlign: 'center' }}>{i + 1}</td>
                      <td>{item.group_name}</td>
                      <td>{item.queue_name}</td>
                      <td style={{ textAlign: 'right' }}>{item.total_count.toLocaleString()}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700, color: item.correct_rate < 99 ? 'var(--danger)' : 'var(--success)' }}>
                        {item.correct_rate.toFixed(2)}%
                      </td>
                      <td style={{ textAlign: 'right' }}>{item.misjudge_rate.toFixed(2)}%</td>
                      <td style={{ textAlign: 'right' }}>{item.missjudge_rate.toFixed(2)}%</td>
                      <td style={{ textAlign: 'right' }}>{item.appeal_reverse_rate.toFixed(2)}%</td>
                      <td style={{ textAlign: 'right' }}>{item.reviewer_cnt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {problemQueues.length > 0 && (
              <div style={{ marginTop: 24, padding: '18px 20px', background: 'var(--card-bg)', borderRadius: 8 }}>
                <h4 style={{ marginBottom: 16, fontSize: 14, fontWeight: 600 }}>⚠️ 问题队列：错判 vs 漏判</h4>
                <BarChart data={problemQueues} />
              </div>
            )}
          </>
        )}
      </div>

      {/* ── 审核人排名 ── */}
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <h3 className="panel-title">👤 审核人正确率</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>正确率 &lt; 95% 红色预警</p>
          </div>
          <button onClick={() => setShowAllReviewers(!showAllReviewers)} className="button" style={{ fontSize: 13, flexShrink: 0 }}>
            {showAllReviewers ? '只看问题人员' : `显示全部 (${reviewerData.length}人)`}
          </button>
        </div>
        {reviewerData.length === 0 ? (
          <p style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
            {loading ? '加载中...' : '暂无数据，请点击查询'}
          </p>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', minWidth: 680 }}>
                <thead>
                  <tr>
                    <th style={{ width: 48 }}>排名</th>
                    <th>姓名</th>
                    <th>组别</th>
                    <th>队列</th>
                    <th style={{ textAlign: 'right' }}>审核量</th>
                    <th style={{ textAlign: 'right' }}>正确率</th>
                    <th style={{ textAlign: 'right' }}>错判数</th>
                    <th style={{ textAlign: 'right' }}>漏判数</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedReviewers.map((item, i) => (
                    <tr key={i} style={{ backgroundColor: item.needs_attention ? 'var(--danger-bg)' : undefined }}>
                      <td style={{ textAlign: 'center' }}>{i + 1}</td>
                      <td>{item.reviewer_name}</td>
                      <td>{item.group_name}</td>
                      <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.queue_name}>{item.queue_name}</td>
                      <td style={{ textAlign: 'right' }}>{item.review_count.toLocaleString()}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700, color: item.correct_rate < 95 ? 'var(--danger)' : undefined }}>
                        {item.correct_rate.toFixed(2)}%
                      </td>
                      <td style={{ textAlign: 'right' }}>{item.misjudge_cnt}</td>
                      <td style={{ textAlign: 'right' }}>{item.missjudge_cnt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!showAllReviewers && displayedReviewers.length === 0 && (
              <p style={{ textAlign: 'center', padding: 32, color: 'var(--success)' }}>✅ 所有审核人正确率 ≥ 95%</p>
            )}
          </>
        )}
      </div>
    </PageTemplate>
  );
}

/** 大数字指标卡片 */
function MetricCard({ label, value, sub, color, highlight }: {
  label: string; value: string; sub?: string; color?: string; highlight?: boolean;
}) {
  return (
    <div style={{
      background: '#fff',
      border: highlight ? '2px solid #ef4444' : '1px solid var(--border)',
      borderRadius: 12,
      padding: '18px 18px 14px',
      display: 'flex', flexDirection: 'column', gap: 5,
      boxShadow: highlight ? '0 0 0 3px rgba(239,68,68,.08)' : '0 1px 3px rgba(0,0,0,.06)',
    }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontSize: 30, fontWeight: 700, color: color ?? 'var(--text-primary)', lineHeight: 1.1, letterSpacing: '-0.02em' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{sub}</div>}
    </div>
  );
}

/** 错判 vs 漏判横向柱状图 */
function BarChart({ data }: { data: QueueItem[] }) {
  if (!data.length) return null;
  const maxVal = Math.max(...data.map(d => Math.max(d.misjudge_cnt || 0, d.missjudge_cnt || 0)), 1);
  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {data.map((item, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 150, fontSize: 12, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-primary)' }} title={item.queue_name}>
              {item.queue_name}
            </div>
            <div style={{ flex: 1, display: 'flex', gap: 6, alignItems: 'flex-end', height: 38 }}>
              {[
                { val: item.misjudge_cnt, color: '#3b82f6', label: '错' },
                { val: item.missjudge_cnt, color: '#f97316', label: '漏' },
              ].map(({ val, color, label }) => (
                <div key={label} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color, marginBottom: 2 }}>{val}</span>
                  <div style={{ width: '100%', height: `${Math.max((val / maxVal) * 30, 3)}px`, background: color, borderRadius: '2px 2px 0 0' }} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#3b82f6', borderRadius: 2, marginRight: 4 }} />错判</span>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#f97316', borderRadius: 2, marginRight: 4 }} />漏判</span>
      </div>
    </div>
  );
}
