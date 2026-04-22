'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import { ExcelExporter } from '@/lib/excel-exporter';
import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';

/**
 * 明细查询 - 合并审核人分析
 *
 * 三种查询模式：
 * 1. 明细记录 - 按日期/队列/审核人查询具体记录
 * 2. 审核人分析 - 搜索某个审核人，查看个人表现
 * 3. 队列分析 - 选择队列，查看队列详细数据
 */

type QueryMode = 'detail' | 'reviewer' | 'queue';

function DetailsPageInner() {
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<QueryMode>('detail');

  // ---- 明细记录模式状态 ----
  const maxDate = '2026-04-20';
  const minDate = '2026-03-06';
  const [startDate, setStartDate] = useState(searchParams.get('start_date') || subtractDays(maxDate, 6));
  const [endDate, setEndDate] = useState(searchParams.get('end_date') || maxDate);
  const [filterQueue, setFilterQueue] = useState('');
  const [filterReviewer, setFilterReviewer] = useState('');
  const [filterError, setFilterError] = useState('');
  const [detailResults, setDetailResults] = useState<any[]>([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [queues, setQueues] = useState<string[]>([]);
  const [reviewers, setReviewers] = useState<string[]>([]);
  const [errorTypes, setErrorTypes] = useState<string[]>([]);

  // ---- 审核人分析模式状态 ----
  const [reviewerName, setReviewerName] = useState('');
  const [reviewerData, setReviewerData] = useState<any>(null);
  const [compareData, setCompareData] = useState<any>(null);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [errorDist, setErrorDist] = useState<any[]>([]);
  const [reviewerLoading, setReviewerLoading] = useState(false);
  const [trendDays, setTrendDays] = useState(7);

  // ---- 队列分析模式状态 ----
  const [selectedQueue, setSelectedQueue] = useState('');
  const [queueData, setQueueData] = useState<any>(null);
  const [queueLoading, setQueueLoading] = useState(false);
  const [queueDate, setQueueDate] = useState('2026-04-01');

  // 加载筛选选项
  useEffect(() => {
    fetch('${API_BASE}/api/v1/internal/queues?selected_date=2026-04-01')
      .then(r => r.json())
      .then(d => setQueues((d.data?.queues || []).map((q: any) => q.queue_name || q)))
      .catch(() => {});

    fetch('${API_BASE}/api/v1/internal/reviewers?selected_date=2026-04-01&limit=200')
      .then(r => r.json())
      .then(d => setReviewers((d.data?.reviewers || []).map((r: any) => r.reviewer_name || r)))
      .catch(() => {});

    fetch('${API_BASE}/api/v1/internal/error-types?selected_date=2026-04-01')
      .then(r => r.json())
      .then(d => setErrorTypes((d.data?.error_types || []).map((e: any) => e.label_name || e)))
      .catch(() => {});
  }, []);

  // ==================== 明细记录查询 ====================
  const queryDetail = async () => {
    setDetailLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
        ...(filterQueue && { queue_name: filterQueue }),
        ...(filterReviewer && { reviewer_name: filterReviewer }),
        ...(filterError && { error_type: filterError }),
        limit: '100',
      });
      const res = await fetch(`${API_BASE}/api/v1/details/records?${params}`);
      const data = await res.json();
      setDetailResults(data.data?.records || data.data || []);
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

  // ==================== 审核人分析 ====================
  const searchReviewer = async () => {
    if (!reviewerName.trim()) return alert('请输入审核人姓名');
    setReviewerLoading(true);
    try {
      // TODO: 对接真实API
      // const res = await fetch(`/api/v1/reviewer/profile?name=${reviewerName}`);
      const mockStats = {
        auditCount: 1234, accuracy: 95.6, misjudgeCount: 54, rank: 12, totalReviewers: 45,
      };
      const mockTeam = { auditCount: 980, accuracy: 93.2, misjudgeCount: 67 };
      const mockErrors = [
        { type: '引流判定', count: 23, pct: 42.6 },
        { type: '重要消息', count: 15, pct: 27.8 },
        { type: '低质导流', count: 10, pct: 18.5 },
        { type: '其他', count: 6, pct: 11.1 },
      ];
      const mockTrend = [
        { date: '2026-03-26', accuracy: 94.2, auditCount: 1150 },
        { date: '2026-03-27', accuracy: 93.8, auditCount: 1180 },
        { date: '2026-03-31', accuracy: 95.8, auditCount: 1220 },
        { date: '2026-04-01', accuracy: 95.6, auditCount: 1234 },
      ];
      setReviewerData(mockStats);
      setCompareData(mockTeam);
      setErrorDist(mockErrors);
      setTrendData(mockTrend);
    } finally {
      setReviewerLoading(false);
    }
  };

  const exportReviewer = () => {
    if (!reviewerData) return alert('请先搜索审核人');
    ExcelExporter.exportSingleSheet(
      trendData,
      [
        { key: 'date', label: '日期' },
        { key: 'auditCount', label: '审核量' },
        { key: 'accuracy', label: '正确率(%)' },
      ],
      '审核人趋势',
      `审核人分析_${reviewerName}.csv`,
      `审核人: ${reviewerName}`
    );
  };

  // ==================== 队列分析 ====================
  const queryQueue = async () => {
    if (!selectedQueue) return alert('请选择队列');
    setQueueLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/internal/reviewers?selected_date=${queueDate}&queue_name=${encodeURIComponent(selectedQueue)}&limit=50`
      );
      const data = await res.json();
      const reviewerList = data.data?.reviewers || [];
      setQueueData({
        queueName: selectedQueue,
        date: queueDate,
        reviewers: reviewerList,
        avgAccuracy: reviewerList.length
          ? reviewerList.reduce((s: number, r: any) => s + (r.raw_accuracy_rate || 0), 0) / reviewerList.length
          : 0,
      });
    } catch {
      setQueueData(null);
    } finally {
      setQueueLoading(false);
    }
  };

  const exportQueue = () => {
    if (!queueData?.reviewers?.length) return alert('没有数据可导出');
    ExcelExporter.exportSingleSheet(
      queueData.reviewers,
      [
        { key: 'reviewer_name', label: '审核人' },
        { key: 'qa_cnt', label: '审核量' },
        { key: 'raw_accuracy_rate', label: '正确率(%)' },
      ],
      '队列成员',
      `队列分析_${selectedQueue}_${queueDate}.csv`,
      `队列: ${selectedQueue} | 日期: ${queueDate}`
    );
  };

  // ==================== 渲染 ====================
  const modeConfig: { key: QueryMode; label: string; icon: string }[] = [
    { key: 'detail', label: '明细记录', icon: '📋' },
    { key: 'reviewer', label: '审核人分析', icon: '👤' },
    { key: 'queue', label: '队列分析', icon: '📊' },
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
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 'var(--spacing-md)', marginTop: 'var(--spacing-md)' }}>
              <div>
                <label style={labelStyle}>开始日期</label>
                <input type="date" className="input" style={inputStyle} value={startDate} min={minDate} max={endDate}
                  onChange={e => setStartDate(e.target.value)} />
              </div>
              <div>
                <label style={labelStyle}>结束日期</label>
                <input type="date" className="input" style={inputStyle} value={endDate} min={startDate} max={maxDate}
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
                setStartDate(subtractDays(maxDate, 6)); setEndDate(maxDate);
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
                      {['审核人', '队列', '错误类型', '审核时间', '内容摘要'].map(h => (
                        <th key={h} style={thStyle}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {detailResults.map((row, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={tdStyle}>{row.reviewer_name || '—'}</td>
                        <td style={tdStyle}>{row.queue_name || '—'}</td>
                        <td style={tdStyle}>{row.error_type || '—'}</td>
                        <td style={tdStyle}>{row.audit_time || '—'}</td>
                        <td style={{ ...tdStyle, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {row.content || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* ===== 审核人分析模式 ===== */}
      {mode === 'reviewer' && (
        <>
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <h3 className="panel-title">👤 搜索审核人</h3>
            <div style={{ marginTop: 'var(--spacing-md)', display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center' }}>
              <select
                className="input"
                value={reviewerName}
                onChange={e => setReviewerName(e.target.value)}
                style={{ flex: 1, maxWidth: 320 }}
              >
                <option value="">请选择或搜索审核人...</option>
                {reviewers.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
              <input
                type="text"
                className="input"
                placeholder="或直接输入姓名"
                value={reviewerName}
                onChange={e => setReviewerName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && searchReviewer()}
                style={{ flex: 1, maxWidth: 240 }}
              />
              <button className="button" onClick={searchReviewer} disabled={reviewerLoading}
                style={{ background: 'var(--primary)', color: '#fff', minWidth: 80 }}>
                {reviewerLoading ? '...' : '查询'}
              </button>
              {reviewerData && (
                <button className="button" onClick={exportReviewer} style={{ marginLeft: 4 }}>
                  ⬇ 导出
                </button>
              )}
            </div>
            <p style={{ marginTop: 8, fontSize: '0.8em', color: 'var(--text-muted)' }}>
              下拉选择或直接输入姓名，按 Enter 查询
            </p>
          </div>

          {!reviewerData && !reviewerLoading && (
            <div className="panel" style={{ marginTop: 'var(--spacing-lg)', ...emptyStyle }}>
              <div style={{ fontSize: '3em', marginBottom: 8 }}>👤</div>
              <div>选择审核人，查看个人表现分析</div>
            </div>
          )}

          {reviewerLoading && (
            <div className="panel" style={{ marginTop: 'var(--spacing-lg)', ...emptyStyle }}>
              🔄 加载中...
            </div>
          )}

          {reviewerData && !reviewerLoading && (
            <>
              {/* 核心指标 */}
              <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
                <h3 className="panel-title">📊 {reviewerName} · 个人指标</h3>
                <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
                  <SummaryCard label="审核量" value={reviewerData.auditCount.toLocaleString()}
                    hint={`团队均: ${compareData.auditCount.toLocaleString()}`}
                    tone={reviewerData.auditCount >= compareData.auditCount ? 'success' : 'neutral'} />
                  <SummaryCard label="正确率" value={`${reviewerData.accuracy.toFixed(1)}%`}
                    hint={`团队均: ${compareData.accuracy.toFixed(1)}%`}
                    tone={reviewerData.accuracy >= 90 ? 'success' : reviewerData.accuracy >= 85 ? 'warning' : 'danger'} />
                  <SummaryCard label="误判数" value={reviewerData.misjudgeCount.toString()}
                    hint={`团队均: ${compareData.misjudgeCount}`}
                    tone={reviewerData.misjudgeCount <= compareData.misjudgeCount ? 'success' : 'warning'} />
                  <SummaryCard label="团队排名"
                    value={`${reviewerData.rank}/${reviewerData.totalReviewers}`}
                    hint={`前 ${((reviewerData.rank / reviewerData.totalReviewers) * 100).toFixed(0)}%`}
                    tone={reviewerData.rank <= reviewerData.totalReviewers / 3 ? 'success' : 'neutral'} />
                </div>
              </div>

              {/* 错误分布 + 趋势 并排 */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--spacing-lg)', marginTop: 'var(--spacing-lg)' }}>
                {/* 错误分布 */}
                <div className="panel">
                  <h3 className="panel-title">🎯 错误类型分布</h3>
                  <div style={{ marginTop: 'var(--spacing-md)' }}>
                    {errorDist.map((err, i) => (
                      <div key={i} style={{ marginBottom: 'var(--spacing-md)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: '0.875em' }}>
                          <span>{err.type}</span>
                          <span style={{ color: 'var(--text-muted)' }}>{err.count}次 ({err.pct.toFixed(1)}%)</span>
                        </div>
                        <div style={{ background: 'var(--bg-secondary)', height: 10, borderRadius: 5, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', width: `${err.pct}%`,
                            background: i === 0 ? 'var(--danger)' : i === 1 ? 'var(--warning)' : 'var(--info)'
                          }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 趋势 */}
                <div className="panel">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 className="panel-title">📉 正确率趋势</h3>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {[7, 14, 30].map(d => (
                        <button key={d} onClick={() => setTrendDays(d)}
                          style={{
                            padding: '2px 10px', fontSize: '0.8em', borderRadius: 4, cursor: 'pointer',
                            border: trendDays === d ? '1px solid var(--primary)' : '1px solid var(--border)',
                            background: trendDays === d ? 'var(--primary)' : 'var(--bg)',
                            color: trendDays === d ? '#fff' : 'var(--text)',
                          }}>
                          {d}天
                        </button>
                      ))}
                    </div>
                  </div>
                  <table style={{ ...tableStyle, marginTop: 'var(--spacing-md)' }}>
                    <thead>
                      <tr style={{ background: 'var(--bg-secondary)' }}>
                        <th style={thStyle}>日期</th>
                        <th style={{ ...thStyle, textAlign: 'right' }}>审核量</th>
                        <th style={{ ...thStyle, textAlign: 'right' }}>正确率</th>
                        <th style={{ ...thStyle, textAlign: 'center' }}>走势</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trendData.map((row, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={tdStyle}>{row.date}</td>
                          <td style={{ ...tdStyle, textAlign: 'right' }}>{row.auditCount.toLocaleString()}</td>
                          <td style={{
                            ...tdStyle, textAlign: 'right', fontWeight: 600,
                            color: row.accuracy >= 90 ? 'var(--success)' : 'var(--warning)'
                          }}>{row.accuracy.toFixed(1)}%</td>
                          <td style={{ ...tdStyle, textAlign: 'center' }}>
                            {i > 0 ? (row.accuracy > trendData[i-1].accuracy ? '📈' : row.accuracy < trendData[i-1].accuracy ? '📉' : '➡️') : ''}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* 改进建议 */}
              {(reviewerData.accuracy < 90 || errorDist[0]?.pct > 30) && (
                <div className="panel" style={{ marginTop: 'var(--spacing-lg)', borderLeft: '3px solid var(--info)' }}>
                  <h3 className="panel-title">💡 改进建议</h3>
                  <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-sm)', lineHeight: 2 }}>
                    {reviewerData.accuracy < 90 && (
                      <li>正确率 {reviewerData.accuracy.toFixed(1)}% 低于90%目标，建议加强相关培训</li>
                    )}
                    {errorDist[0]?.pct > 30 && (
                      <li>「{errorDist[0].type}」占比 {errorDist[0].pct.toFixed(1)}%，建议针对性学习</li>
                    )}
                    {reviewerData.auditCount < compareData.auditCount * 0.8 && (
                      <li>审核量低于团队平均 {((1 - reviewerData.auditCount/compareData.auditCount)*100).toFixed(0)}%，建议提升效率</li>
                    )}
                  </ul>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ===== 队列分析模式 ===== */}
      {mode === 'queue' && (
        <>
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <h3 className="panel-title">📊 选择队列</h3>
            <div style={{ marginTop: 'var(--spacing-md)', display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center', flexWrap: 'wrap' }}>
              <select className="input" value={selectedQueue} onChange={e => setSelectedQueue(e.target.value)}
                style={{ flex: 1, maxWidth: 280 }}>
                <option value="">请选择队列</option>
                {queues.map(q => <option key={q} value={q}>{q}</option>)}
              </select>
              <div>
                <input type="date" className="input" value={queueDate} min={minDate} max={maxDate}
                  onChange={e => setQueueDate(e.target.value)} />
              </div>
              <button className="button" onClick={queryQueue} disabled={queueLoading}
                style={{ background: 'var(--primary)', color: '#fff', minWidth: 80 }}>
                {queueLoading ? '...' : '查询'}
              </button>
              {queueData?.reviewers?.length > 0 && (
                <button className="button" onClick={exportQueue}>⬇ 导出</button>
              )}
            </div>
          </div>

          {!queueData && !queueLoading && (
            <div className="panel" style={{ marginTop: 'var(--spacing-lg)', ...emptyStyle }}>
              <div style={{ fontSize: '3em', marginBottom: 8 }}>📊</div>
              <div>选择队列和日期，查看队列成员表现</div>
            </div>
          )}

          {queueLoading && (
            <div className="panel" style={{ marginTop: 'var(--spacing-lg)', ...emptyStyle }}>🔄 加载中...</div>
          )}

          {queueData && !queueLoading && (
            <>
              <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 className="panel-title">👥 {queueData.queueName} · 成员列表（{queueData.date}）</h3>
                  <span style={{ fontSize: '0.875em', color: 'var(--text-muted)' }}>
                    均正确率：
                    <strong style={{ color: queueData.avgAccuracy >= 90 ? 'var(--success)' : 'var(--danger)' }}>
                      {queueData.avgAccuracy.toFixed(1)}%
                    </strong>
                  </span>
                </div>

                {queueData.reviewers.length === 0 ? (
                  <div style={{ ...emptyStyle, marginTop: 'var(--spacing-md)' }}>该队列当日无数据</div>
                ) : (
                  <div style={{ overflowX: 'auto', marginTop: 'var(--spacing-md)' }}>
                    <table style={tableStyle}>
                      <thead>
                        <tr style={{ background: 'var(--bg-secondary)' }}>
                          <th style={thStyle}>排名</th>
                          <th style={thStyle}>审核人</th>
                          <th style={{ ...thStyle, textAlign: 'right' }}>审核量</th>
                          <th style={{ ...thStyle, textAlign: 'right' }}>正确率</th>
                          <th style={{ ...thStyle, textAlign: 'center' }}>状态</th>
                        </tr>
                      </thead>
                      <tbody>
                        {queueData.reviewers.map((r: any, i: number) => (
                          <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={tdStyle}>{i + 1}</td>
                            <td style={{ ...tdStyle, fontWeight: 500 }}>{r.reviewer_name}</td>
                            <td style={{ ...tdStyle, textAlign: 'right' }}>{(r.qa_cnt || 0).toLocaleString()}</td>
                            <td style={{
                              ...tdStyle, textAlign: 'right', fontWeight: 600,
                              color: (r.raw_accuracy_rate || 0) >= 90 ? 'var(--success)'
                                : (r.raw_accuracy_rate || 0) >= 85 ? 'var(--warning)' : 'var(--danger)'
                            }}>
                              {(r.raw_accuracy_rate || 0).toFixed(1)}%
                            </td>
                            <td style={{ ...tdStyle, textAlign: 'center' }}>
                              {(r.raw_accuracy_rate || 0) >= 90 ? '✅' : (r.raw_accuracy_rate || 0) >= 85 ? '⚠️' : '❌'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </>
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
