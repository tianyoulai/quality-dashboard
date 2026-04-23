'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

import { PageTemplate } from '@/components/page-template';
import { ExcelExporter } from '@/lib/excel-exporter';
import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';

/**
 * 明细查询 - 精简版（v2）
 *
 * 变更：
 * - DS-4: 删除审核人分析模式（100% mock，等真实API后恢复）
 * - 队列分析模式改为跳转 /analysis?tab=internal
 * - 明细表补充字段（原始标注/正确标注/质检员）
 * - 支持 URL 参数接收筛选（?reviewer=xxx&queue=xxx）
 */

type QueryMode = 'detail' | 'queue';

function DetailsPageInner() {
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<QueryMode>('detail');

  // ---- 明细记录模式状态 ----
  const [maxDate, setMaxDate] = useState('');
  const [minDate, setMinDate] = useState('');
  const [startDate, setStartDate] = useState(searchParams.get('start_date') || '');
  const [endDate, setEndDate] = useState(searchParams.get('end_date') || '');
  const [filterQueue, setFilterQueue] = useState(searchParams.get('queue') || '');
  const [filterReviewer, setFilterReviewer] = useState(searchParams.get('reviewer') || '');
  const [filterError, setFilterError] = useState(searchParams.get('error_type') || '');
  const [detailResults, setDetailResults] = useState<any[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [queues, setQueues] = useState<string[]>([]);
  const [reviewers, setReviewers] = useState<string[]>([]);
  const [errorTypes, setErrorTypes] = useState<string[]>([]);

  // 加载筛选选项 — 从 /api/v1/details/filters 动态获取
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/details/filters`)
      .then(r => r.json())
      .then(d => {
        const data = d.data || {};
        setQueues(data.queues?.map((q: any) => q.queue_name || q).filter(Boolean) || []);
        setReviewers(data.reviewers || []);
        setErrorTypes(data.error_types || []);

        const apiMinDate = data.min_date || '';
        const apiMaxDate = data.max_date || '';
        setMinDate(apiMinDate);
        setMaxDate(apiMaxDate);

        if (!searchParams.get('end_date') && apiMaxDate) {
          setEndDate(apiMaxDate);
        }
        if (!searchParams.get('start_date') && apiMaxDate) {
          setStartDate(subtractDays(apiMaxDate, 6));
        }
      })
      .catch(() => {});
  }, []);

  // ==================== 明细记录查询 ====================
  const queryDetail = async () => {
    setDetailLoading(true);
    try {
      const params = new URLSearchParams({
        date_start: startDate,
        date_end: endDate,
        ...(filterQueue && { queue_name: filterQueue }),
        ...(filterReviewer && { reviewer_name: filterReviewer }),
        ...(filterError && { error_type: filterError }),
        limit: '200',
      });
      const res = await fetch(`${API_BASE}/api/v1/details/query?${params}`);
      const data = await res.json();
      // Backend returns rows in data.data.rows (with Chinese column keys)
      const rows = data.data?.rows || data.data?.records || data.data || [];
      setDetailResults(rows);
    } catch {
      // 无API时展示空结果
      setDetailResults([]);
    } finally {
      setDetailLoading(false);
    }
  };

  const exportDetail = () => {
    if (!detailResults.length) return alert('没有数据可导出');
    const filterParts = [];
    if (filterQueue) filterParts.push(`队列: ${filterQueue}`);
    if (filterReviewer) filterParts.push(`审核人: ${filterReviewer}`);
    if (filterError) filterParts.push(`错误类型: ${filterError}`);
    ExcelExporter.exportSingleSheet(
      detailResults,
      [
        { key: 'reviewer_name', label: '审核人' },
        { key: 'queue_name', label: '队列' },
        { key: 'error_type', label: '错误类型' },
        { key: 'audit_time', label: '审核时间' },
        { key: 'content', label: '内容摘要' },
      ],
      '明细记录',
      `明细记录_${startDate}_${endDate}.csv`,
      filterParts.join(' | ') || undefined
    );
  };

  // IA-5: URL 参数传入时自动触发查询
  const hasUrlFilter = filterQueue || filterReviewer || filterError || searchParams.get('start_date') || searchParams.get('end_date');
  useEffect(() => {
    if (hasUrlFilter && startDate && endDate) {
      queryDetail();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startDate, endDate]);

  // ==================== 渲染 ====================
  const modeConfig: { key: QueryMode; label: string; icon: string }[] = [
    { key: 'detail', label: '明细记录', icon: '📋' },
    { key: 'queue', label: '队列分析 → /analysis', icon: '📊' },
  ];

  return (
    <PageTemplate
      title="🔍 明细查询"
      subtitle="明细记录、审核人分析、队列分析，三种模式一站查询"
    >
      {/* ===== 模式切换 ===== */}
      <div className="panel">
        <div style={{ display: 'flex', gap: 'var(--spacing-sm)', flexWrap: 'wrap' }}>
          {modeConfig.map(m => (
            <button
              key={m.key}
              onClick={() => setMode(m.key)}
              style={{
                padding: '10px 24px',
                borderRadius: 'var(--radius)',
                border: mode === m.key ? '2px solid var(--primary)' : '2px solid var(--border)',
                background: mode === m.key ? 'var(--primary)' : 'var(--bg)',
                color: mode === m.key ? '#fff' : 'var(--text)',
                fontWeight: mode === m.key ? 700 : 400,
                cursor: 'pointer',
                fontSize: '0.95em',
                transition: 'all 0.15s',
              }}
            >
              {m.icon} {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* ===== 明细记录模式 ===== */}
      {mode === 'detail' && (
        <>
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <h3 className="panel-title">🔍 查询条件</h3>
            {maxDate && minDate && (
              <div style={{ marginTop: 8, fontSize: '0.85em', color: 'var(--text-muted)' }}>
                当前可查日期范围：{minDate} ~ {maxDate}
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-md)' }}>
              <div>
                <label style={labelStyle}>开始日期</label>
                <input type="date" className="input" style={inputStyle} value={startDate} min={minDate || undefined} max={endDate || undefined}
                  onChange={e => setStartDate(e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>结束日期</label>
                <input type="date" className="input" style={inputStyle} value={endDate} min={startDate || undefined} max={maxDate || undefined}
                  onChange={e => setEndDate(e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>队列</label>
                <select className="input" style={inputStyle} value={filterQueue} onChange={e => setFilterQueue(e.target.value)}>
                  <option value="">全部队列</option>
                  {queues.map(q => <option key={q} value={q}>{q}</option>)}
                </select>
              </div>
              <div>
                <label style={labelStyle}>审核人</label>
                <select className="input" style={inputStyle} value={filterReviewer} onChange={e => setFilterReviewer(e.target.value)}>
                  <option value="">全部审核人</option>
                  {reviewers.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label style={labelStyle}>错误类型</label>
                <select className="input" style={inputStyle} value={filterError} onChange={e => setFilterError(e.target.value)}>
                  <option value="">全部类型</option>
                  {errorTypes.map(e => <option key={e} value={e}>{e}</option>)}
                </select>
              </div>
            </div>
            <div style={{ marginTop: 'var(--spacing-md)', display: 'flex', gap: 'var(--spacing-sm)' }}>
              <button className="button" onClick={queryDetail} disabled={detailLoading}
                style={{ background: 'var(--primary)', color: '#fff', minWidth: 100 }}>
                {detailLoading ? '查询中...' : '🔍 查询'}
              </button>
              <button className="button" onClick={() => {
                setFilterQueue(''); setFilterReviewer(''); setFilterError('');
                if (maxDate) {
                  setStartDate(subtractDays(maxDate, 6));
                  setEndDate(maxDate);
                }
                setDetailResults([]);
              }}>重置</button>
              {detailResults.length > 0 && (
                <button className="button" onClick={exportDetail} style={{ marginLeft: 'auto' }}>
                  ⬇ 导出 CSV
                </button>
              )}
            </div>
          </div>

          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title">📋 查询结果</h3>
              {detailResults.length > 0 && (
                <span style={{ fontSize: '0.875em', color: 'var(--text-muted)' }}>
                  共 {detailResults.length} 条
                </span>
              )}
            </div>

            {detailLoading ? (
              <div style={emptyStyle}>🔄 查询中，请稍候...</div>
            ) : detailResults.length === 0 ? (
              <div style={emptyStyle}>
                <div style={{ fontSize: '3em', marginBottom: 8 }}>📋</div>
                <div>设置查询条件后点击「查询」</div>
                <div style={{ fontSize: '0.8em', color: 'var(--text-muted)', marginTop: 4 }}>
                  支持按日期范围、队列、审核人、错误类型筛选
                </div>
              </div>
            ) : (
              <div style={{ overflowX: 'auto', marginTop: 'var(--spacing-md)' }}>
                <table style={tableStyle}>
                  <thead>
                    <tr style={{ background: 'var(--bg-secondary)' }}>
                      {['审核人', '队列', '错误类型', '原始判断', '最终判断', '质检时间', '错判', '漏判'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {detailResults.map((row: any, i: number) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={tdStyle}>{row['审核人'] || '—'}</td>
                        <td style={tdStyle}>{row['队列'] || '—'}</td>
                        <td style={tdStyle}>{row['错误类型'] || '—'}</td>
                        <td style={tdStyle}>{row['原始判断'] || '—'}</td>
                        <td style={tdStyle}>{row['最终判断'] || '—'}</td>
                        <td style={tdStyle}>{row['质检时间'] || '—'}</td>
                        <td style={tdStyle}>{row['错判'] || '—'}</td>
                        <td style={tdStyle}>{row['漏判'] || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* ===== 审核人分析已迁移 ===== */}
      {/* DS-4: 审核人分析模式原为 100% mock 数据，已删除。等 /api/v1/reviewer/profile API 开发后恢复 */}

      {/* ===== 队列分析模式 → 跳转 /analysis ===== */}
      {mode === 'queue' && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)', ...emptyStyle }}>
          <div style={{ fontSize: '3em', marginBottom: 8 }}>📊</div>
          <div>队列分析已迁移到「质检分析」页面</div>
          <div style={{ marginTop: 12 }}>
            <Link href="/analysis?tab=internal" style={{
              padding: '10px 24px', background: 'var(--primary)', color: '#fff',
              borderRadius: 'var(--radius)', textDecoration: 'none', fontWeight: 600,
            }}>
              前往质检分析 →
            </Link>
          </div>
        </div>
      )}
    </PageTemplate>
  );
}

// ====== 样式常量 ======
const labelStyle: React.CSSProperties = {
  display: 'block', marginBottom: 4, fontWeight: 500, fontSize: '0.875em'
};
const inputStyle: React.CSSProperties = { width: '100%' };
const tableStyle: React.CSSProperties = { width: '100%', borderCollapse: 'collapse' };
const thStyle: React.CSSProperties = {
  padding: '8px 12px', textAlign: 'left',
  borderBottom: '2px solid var(--border)', fontSize: '0.875em', fontWeight: 600
};
const tdStyle: React.CSSProperties = { padding: '8px 12px', fontSize: '0.875em' };
const emptyStyle: React.CSSProperties = {
  textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)'
};

function subtractDays(dateText: string, days: number): string {
  const d = new Date(`${dateText}T00:00:00`);
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function DetailsPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center' }}>加载中...</div>}>
      <DetailsPageInner />
    </Suspense>
  );
}
