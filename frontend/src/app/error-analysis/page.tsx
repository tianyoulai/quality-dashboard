'use client';

import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import { useState, useEffect } from 'react';

/**
 * 🔍 错误分析页面
 * 
 * 显示错误总览、热力图、根因分析等
 */
export default function ErrorAnalysisPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);
  
  // API数据
  const [overviewData, setOverviewData] = useState<any>(null);
  const [heatmapData, setHeatmapData] = useState<any>(null);
  const [rootCauseData, setRootCauseData] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, [days]);

  async function loadData() {
    setLoading(true);
    setError(null);
    
    try {
      // 计算日期范围
      const endDate = new Date('2026-04-01'); // 固定使用有数据的日期
      const startDate = new Date(endDate);
      startDate.setDate(startDate.getDate() - days + 1);
      
      const startDateStr = startDate.toISOString().split('T')[0];
      const endDateStr = endDate.toISOString().split('T')[0];
      
      const baseUrl = 'http://localhost:8000/api/v1/analysis';
      
      // 并行请求
      const [overview, heatmap, rootCause] = await Promise.all([
        fetch(`${baseUrl}/error-overview?start_date=${startDateStr}&end_date=${endDateStr}`).then(r => r.json()),
        fetch(`${baseUrl}/error-heatmap?start_date=${startDateStr}&end_date=${endDateStr}`).then(r => r.json()),
        fetch(`${baseUrl}/root-cause?start_date=${startDateStr}&end_date=${endDateStr}`).then(r => r.json())
      ]);
      
      setOverviewData(overview);
      setHeatmapData(heatmap);
      setRootCauseData(rootCause);
    } catch (err) {
      console.error('加载数据失败:', err);
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <PageTemplate title="错误分析" subtitle="加载中...">
        <div className="panel">
          <p style={{ textAlign: 'center', padding: 'var(--spacing-xl)', color: 'var(--text-muted)' }}>
            正在加载数据...
          </p>
        </div>
      </PageTemplate>
    );
  }

  if (error || !overviewData) {
    return (
      <PageTemplate title="错误分析" subtitle="加载失败">
        <div className="panel" style={{ background: 'var(--danger-bg)', borderColor: 'var(--danger)' }}>
          <p style={{ color: 'var(--danger)' }}>加载数据失败: {error || '数据为空'}</p>
          <button 
            onClick={loadData} 
            className="button"
            style={{ marginTop: 'var(--spacing-md)' }}
          >
            重试
          </button>
        </div>
      </PageTemplate>
    );
  }

  return (
    <PageTemplate
      title="错误分析"
      subtitle={`${overviewData.date_range?.start_date || ''} 至 ${overviewData.date_range?.end_date || ''} (${days}天)`}
      actions={
        <div style={{ display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center' }}>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="input"
            style={{ width: '120px' }}
          >
            <option value={7}>最近7天</option>
            <option value={14}>最近14天</option>
            <option value={30}>最近30天</option>
          </select>
          <button onClick={loadData} className="button">
            刷新数据
          </button>
        </div>
      }
    >
      {/* 错误总览 */}
      <div className="panel">
        <h3 className="panel-title">📊 错误总览</h3>
        
        <div className="cards-grid" style={{ marginTop: 'var(--spacing-md)' }}>
          <SummaryCard
            label="总错误数"
            value={overviewData.total_errors?.toLocaleString() || '0'}
            hint={`总审核量: ${overviewData.total_reviews?.toLocaleString() || '0'}`}
            tone="neutral"
          />

          <SummaryCard
            label="错误率"
            value={`${(overviewData.error_rate || 0).toFixed(2)}%`}
            hint={`误判率: ${(overviewData.misjudge_stats?.rate || 0).toFixed(2)}%`}
            tone={(overviewData.error_rate || 0) > 5 ? 'danger' : 'success'}
          />

          <SummaryCard
            label="误判数"
            value={overviewData.misjudge_stats?.count?.toLocaleString() || '0'}
            hint={`占总错误: ${((overviewData.misjudge_stats?.count || 0) / (overviewData.total_errors || 1) * 100).toFixed(1)}%`}
            tone="warning"
          />

          <SummaryCard
            label="错误类型"
            value={overviewData.error_distribution?.length?.toString() || '0'}
            hint="不同错误分类数量"
            tone="neutral"
          />
        </div>
      </div>

      {/* 错误分布 */}
      {overviewData.error_distribution && overviewData.error_distribution.length > 0 && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="panel-title">🎯 错误类型分布 Top 10</h3>
          
          <div style={{ overflowX: 'auto', marginTop: 'var(--spacing-md)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--card-bg)', borderBottom: '2px solid var(--border)' }}>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>排名</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>错误类型</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>数量</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>占比</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>趋势</th>
                </tr>
              </thead>
              <tbody>
                {overviewData.error_distribution.slice(0, 10).map((item: any, index: number) => (
                  <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: 'var(--spacing-sm)' }}>{index + 1}</td>
                    <td style={{ padding: 'var(--spacing-sm)', fontWeight: 'bold' }}>{item.error_type || '-'}</td>
                    <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{(item.count || 0).toLocaleString()}</td>
                    <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{((item.percentage || 0)).toFixed(2)}%</td>
                    <td style={{ padding: 'var(--spacing-sm)' }}>
                      <span style={{ 
                        padding: '2px 8px', 
                        borderRadius: '4px',
                        fontSize: '0.875em',
                        background: item.trend === 'up' ? 'var(--danger-bg)' : item.trend === 'down' ? 'var(--success-bg)' : 'var(--card-bg)',
                        color: item.trend === 'up' ? 'var(--danger)' : item.trend === 'down' ? 'var(--success)' : 'var(--text-muted)'
                      }}>
                        {item.trend === 'up' ? '↑ 上升' : item.trend === 'down' ? '↓ 下降' : '→ 稳定'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 错误热力图 */}
      {heatmapData?.matrix && heatmapData.matrix.length > 0 && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="panel-title">🔥 错误热力图（队列×错误类型）</h3>
          
          <div style={{ marginTop: 'var(--spacing-md)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
              {heatmapData.summary?.message || `共${heatmapData.queues?.length || 0}个队列，${heatmapData.error_types?.length || 0}种错误类型`}
            </p>
            
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875em' }}>
                <thead>
                  <tr style={{ background: 'var(--card-bg)' }}>
                    <th style={{ padding: 'var(--spacing-xs)', textAlign: 'left', position: 'sticky', left: 0, background: 'var(--card-bg)', zIndex: 1 }}>队列</th>
                    {heatmapData.error_types?.slice(0, 8).map((type: string, i: number) => (
                      <th key={i} style={{ padding: 'var(--spacing-xs)', textAlign: 'center', minWidth: '80px' }}>
                        {type.length > 8 ? type.substring(0, 8) + '...' : type}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {heatmapData.matrix?.slice(0, 10).map((row: any, i: number) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: 'var(--spacing-xs)', fontWeight: 'bold', position: 'sticky', left: 0, background: 'var(--bg)', zIndex: 1 }}>
                        {row.queue_name?.length > 15 ? row.queue_name.substring(0, 15) + '...' : row.queue_name}
                      </td>
                      {row.error_counts?.slice(0, 8).map((count: number, j: number) => (
                        <td key={j} style={{ 
                          padding: 'var(--spacing-xs)', 
                          textAlign: 'center',
                          background: count > 0 ? `rgba(239, 68, 68, ${Math.min(count / 100, 0.8)})` : 'transparent',
                          color: count > 20 ? 'white' : 'inherit'
                        }}>
                          {count > 0 ? count : '-'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 根因分析 */}
      {rootCauseData?.related_errors && rootCauseData.related_errors.length > 0 && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="panel-title">🔍 根因分析</h3>
          
          <div style={{ marginTop: 'var(--spacing-md)' }}>
            <h4 style={{ color: 'var(--primary)', marginBottom: 'var(--spacing-sm)' }}>相关错误</h4>
            <ul style={{ paddingLeft: '20px', lineHeight: 1.8 }}>
              {rootCauseData.related_errors.slice(0, 5).map((item: any, index: number) => (
                <li key={index}>
                  <strong>{item.error_type}</strong>: {item.count}次 ({item.percentage?.toFixed(1)}%)
                </li>
              ))}
            </ul>
          </div>

          {rootCauseData.top_reviewers && rootCauseData.top_reviewers.length > 0 && (
            <div style={{ marginTop: 'var(--spacing-md)' }}>
              <h4 style={{ color: 'var(--primary)', marginBottom: 'var(--spacing-sm)' }}>重点关注审核人</h4>
              <ul style={{ paddingLeft: '20px', lineHeight: 1.8 }}>
                {rootCauseData.top_reviewers.slice(0, 5).map((item: any, index: number) => (
                  <li key={index}>
                    {item.reviewer_name || item.reviewer_id}: {item.error_count}次错误
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* 使用提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--card-bg)' }}>
        <h3 className="panel-title">💡 使用提示</h3>
        <ul style={{ marginTop: 'var(--spacing-md)', paddingLeft: '20px', color: 'var(--text-muted)', lineHeight: 1.8 }}>
          <li>错误热力图颜色越深表示该队列该错误类型越多</li>
          <li>趋势分析基于时间序列数据，显示上升/下降/稳定状态</li>
          <li>根因分析帮助定位系统性问题</li>
          <li>当前数据基于2026-04-01的测试数据</li>
        </ul>
      </div>

      {/* JSON数据查看器 */}
      <details style={{ marginTop: 'var(--spacing-lg)' }}>
        <summary style={{ cursor: 'pointer', color: 'var(--primary)', fontWeight: 'bold' }}>
          📋 查看完整API响应数据
        </summary>
        <div style={{ marginTop: 'var(--spacing-md)', display: 'grid', gap: 'var(--spacing-md)' }}>
          <details>
            <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>Error Overview</summary>
            <pre style={{ 
              marginTop: 'var(--spacing-sm)', 
              padding: 'var(--spacing-md)', 
              background: '#1e1e1e', 
              color: '#d4d4d4',
              borderRadius: '8px',
              overflow: 'auto',
              fontSize: '12px'
            }}>
              {JSON.stringify(overviewData, null, 2)}
            </pre>
          </details>
          
          <details>
            <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>Heatmap Data</summary>
            <pre style={{ 
              marginTop: 'var(--spacing-sm)', 
              padding: 'var(--spacing-md)', 
              background: '#1e1e1e', 
              color: '#d4d4d4',
              borderRadius: '8px',
              overflow: 'auto',
              fontSize: '12px'
            }}>
              {JSON.stringify(heatmapData, null, 2)}
            </pre>
          </details>
          
          <details>
            <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>Root Cause Data</summary>
            <pre style={{ 
              marginTop: 'var(--spacing-sm)', 
              padding: 'var(--spacing-md)', 
              background: '#1e1e1e', 
              color: '#d4d4d4',
              borderRadius: '8px',
              overflow: 'auto',
              fontSize: '12px'
            }}>
              {JSON.stringify(rootCauseData, null, 2)}
            </pre>
          </details>
        </div>
      </details>
    </PageTemplate>
  );
}
