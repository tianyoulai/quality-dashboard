'use client';

import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import { useState, useEffect } from 'react';

/**
 * 📊 数据可视化页面
 * 
 * 显示性能趋势、队列分布等
 */
export default function VisualizationPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);
  
  // API数据
  const [performanceData, setPerformanceData] = useState<any>(null);
  const [queueData, setQueueData] = useState<any>(null);
  const [errorTrendData, setErrorTrendData] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, [days]);

  async function loadData() {
    setLoading(true);
    setError(null);
    
    try {
      const endDate = new Date('2026-04-01');
      const startDate = new Date(endDate);
      startDate.setDate(startDate.getDate() - days + 1);
      
      const startDateStr = startDate.toISOString().split('T')[0];
      const endDateStr = endDate.toISOString().split('T')[0];
      
      const baseUrl = 'http://localhost:8000/api/v1/visualization';
      
      // 暂时只加载performance-trend，其他2个端点待后端实现
      const performance = await fetch(`${baseUrl}/performance-trend?days=${days}`).then(r => r.json());
      
      setPerformanceData(performance);
      // setQueueData(queue); // TODO: 等待后端实现 queue-distribution API
      // setErrorTrendData(errorTrend); // TODO: 等待后端实现 error-trend API
    } catch (err) {
      console.error('加载数据失败:', err);
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <PageTemplate title="数据可视化" subtitle="加载中...">
        <div className="panel">
          <p style={{ textAlign: 'center', padding: 'var(--spacing-xl)', color: 'var(--text-muted)' }}>
            正在加载数据...
          </p>
        </div>
      </PageTemplate>
    );
  }

  if (error || !performanceData) {
    return (
      <PageTemplate title="数据可视化" subtitle="加载失败">
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
      title="数据可视化"
      subtitle={`${performanceData.date_range?.start_date || ''} 至 ${performanceData.date_range?.end_date || ''}`}
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
      {/* 性能趋势总览 */}
      <div className="panel">
        <h3 className="panel-title">📈 性能趋势总览</h3>
        
        <div className="cards-grid" style={{ marginTop: 'var(--spacing-md)' }}>
          <SummaryCard
            label="平均正确率"
            value={`${(performanceData.statistics?.average || 0).toFixed(2)}%`}
            hint={`最高: ${(performanceData.statistics?.max || 0).toFixed(2)}% / 最低: ${(performanceData.statistics?.min || 0).toFixed(2)}%`}
            tone="success"
          />

          <SummaryCard
            label="最新正确率"
            value={`${(performanceData.statistics?.latest || 0).toFixed(2)}%`}
            hint={`变化: ${performanceData.trend?.change >= 0 ? '+' : ''}${(performanceData.trend?.change || 0).toFixed(2)}%`}
            tone={performanceData.trend?.direction === 'up' ? 'success' : performanceData.trend?.direction === 'down' ? 'warning' : 'neutral'}
          />

          <SummaryCard
            label="趋势状态"
            value={performanceData.trend?.direction === 'up' ? '↑ 上升' : performanceData.trend?.direction === 'down' ? '↓ 下降' : '→ 稳定'}
            hint={`${performanceData.trend?.status === 'normal' ? '正常' : '异常'}`}
            tone={performanceData.trend?.direction === 'up' ? 'success' : performanceData.trend?.direction === 'down' ? 'danger' : 'neutral'}
          />

          <SummaryCard
            label="数据天数"
            value={performanceData.date_range?.days?.toString() || '0'}
            hint={`${performanceData.data?.dates?.length || 0}天有效数据`}
            tone="neutral"
          />
        </div>
      </div>

      {/* 正确率趋势图 */}
      {performanceData.data?.dates && performanceData.data.dates.length > 0 && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="panel-title">📊 正确率趋势图</h3>
          
          <div style={{ marginTop: 'var(--spacing-md)' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--card-bg)', borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>日期</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>正确率</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>可视化</th>
                  </tr>
                </thead>
                <tbody>
                  {performanceData.data.dates.map((date: string, index: number) => {
                    const value = performanceData.data.values[index];
                    const percentage = ((value - 90) / 10) * 100; // 90-100%映射到0-100%
                    return (
                      <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: 'var(--spacing-sm)' }}>{date}</td>
                        <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', fontWeight: 'bold' }}>
                          {value.toFixed(2)}%
                        </td>
                        <td style={{ padding: 'var(--spacing-sm)' }}>
                          <div style={{ 
                            height: '20px', 
                            background: 'var(--border)', 
                            borderRadius: '4px',
                            overflow: 'hidden',
                            position: 'relative'
                          }}>
                            <div style={{ 
                              width: `${Math.max(0, Math.min(100, percentage))}%`,
                              height: '100%',
                              background: value >= 99 ? 'var(--success)' : value >= 95 ? 'var(--warning)' : 'var(--danger)',
                              transition: 'width 0.3s ease'
                            }} />
                            <span style={{
                              position: 'absolute',
                              left: '50%',
                              top: '50%',
                              transform: 'translate(-50%, -50%)',
                              fontSize: '0.75em',
                              fontWeight: 'bold',
                              color: percentage > 50 ? 'white' : 'inherit'
                            }}>
                              {value.toFixed(1)}%
                            </span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 队列工作量分布 */}
      {queueData?.queues && queueData.queues.length > 0 && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="panel-title">🎯 队列工作量分布</h3>
          
          <div style={{ marginTop: 'var(--spacing-md)' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
              总队列数: {queueData.total_queues || 0} / 总工作量: {(queueData.total_work_count || 0).toLocaleString()}
            </p>
            
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--card-bg)', borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>队列名称</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>工作量</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>占比</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>可视化</th>
                  </tr>
                </thead>
                <tbody>
                  {queueData.queues.slice(0, 10).map((queue: any, index: number) => (
                    <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: 'var(--spacing-sm)', fontWeight: 'bold' }}>
                        {queue.queue_name}
                      </td>
                      <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>
                        {(queue.work_count || 0).toLocaleString()}
                      </td>
                      <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>
                        {(queue.percentage || 0).toFixed(1)}%
                      </td>
                      <td style={{ padding: 'var(--spacing-sm)' }}>
                        <div style={{ 
                          height: '20px', 
                          background: 'var(--border)', 
                          borderRadius: '4px',
                          overflow: 'hidden'
                        }}>
                          <div style={{ 
                            width: `${Math.min(100, queue.percentage || 0)}%`,
                            height: '100%',
                            background: 'var(--primary)',
                            transition: 'width 0.3s ease'
                          }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 错误趋势 */}
      {errorTrendData?.error_types && errorTrendData.error_types.length > 0 && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="panel-title">🔴 高频错误趋势 Top 5</h3>
          
          <div style={{ marginTop: 'var(--spacing-md)' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--card-bg)', borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>错误类型</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>总数</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>日均</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>趋势</th>
                  </tr>
                </thead>
                <tbody>
                  {errorTrendData.error_types.map((error: any, index: number) => (
                    <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: 'var(--spacing-sm)', fontWeight: 'bold' }}>
                        {error.error_type}
                      </td>
                      <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>
                        {(error.total_count || 0).toLocaleString()}
                      </td>
                      <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>
                        {(error.avg_daily || 0).toFixed(1)}
                      </td>
                      <td style={{ padding: 'var(--spacing-sm)' }}>
                        <span style={{ 
                          padding: '2px 8px', 
                          borderRadius: '4px',
                          fontSize: '0.875em',
                          background: error.trend === 'increasing' ? 'var(--danger-bg)' : error.trend === 'decreasing' ? 'var(--success-bg)' : 'var(--card-bg)',
                          color: error.trend === 'increasing' ? 'var(--danger)' : error.trend === 'decreasing' ? 'var(--success)' : 'var(--text-muted)'
                        }}>
                          {error.trend === 'increasing' ? '↑ 增加' : error.trend === 'decreasing' ? '↓ 减少' : '→ 稳定'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* 使用提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--card-bg)' }}>
        <h3 className="panel-title">💡 使用提示</h3>
        <ul style={{ marginTop: 'var(--spacing-md)', paddingLeft: '20px', color: 'var(--text-muted)', lineHeight: 1.8 }}>
          <li>趋势图使用CSS柱状图展示，可快速识别异常波动</li>
          <li>队列分布可识别工作量不均衡问题</li>
          <li>错误趋势帮助预测未来问题</li>
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
            <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>Performance Data</summary>
            <pre style={{ 
              marginTop: 'var(--spacing-sm)', 
              padding: 'var(--spacing-md)', 
              background: '#1e1e1e', 
              color: '#d4d4d4',
              borderRadius: '8px',
              overflow: 'auto',
              fontSize: '12px'
            }}>
              {JSON.stringify(performanceData, null, 2)}
            </pre>
          </details>
          
          <details>
            <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>Queue Data</summary>
            <pre style={{ 
              marginTop: 'var(--spacing-sm)', 
              padding: 'var(--spacing-md)', 
              background: '#1e1e1e', 
              color: '#d4d4d4',
              borderRadius: '8px',
              overflow: 'auto',
              fontSize: '12px'
            }}>
              {JSON.stringify(queueData, null, 2)}
            </pre>
          </details>
          
          <details>
            <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>Error Trend Data</summary>
            <pre style={{ 
              marginTop: 'var(--spacing-sm)', 
              padding: 'var(--spacing-md)', 
              background: '#1e1e1e', 
              color: '#d4d4d4',
              borderRadius: '8px',
              overflow: 'auto',
              fontSize: '12px'
            }}>
              {JSON.stringify(errorTrendData, null, 2)}
            </pre>
          </details>
        </div>
      </details>
    </PageTemplate>
  );
}
