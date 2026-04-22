'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import { useState, useEffect } from 'react';

/**
 * 📊 实时监控页面（简化版）
 * 
 * 显示当日 vs 昨日核心指标对比
 */
export default function MonitorPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [date, setDate] = useState('2026-04-01');
  const [dashboardData, setDashboardData] = useState<any>(null);

  useEffect(() => {
    loadData();
  }, [date]);

  async function loadData() {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/v1/monitor/dashboard?date=${date}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setDashboardData(data);
    } catch (err) {
      console.error('加载数据失败:', err);
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <PageTemplate title="实时监控" subtitle="加载中...">
        <div className="panel">
          <p style={{ textAlign: 'center', padding: 'var(--spacing-xl)', color: 'var(--text-muted)' }}>
            正在加载数据...
          </p>
        </div>
      </PageTemplate>
    );
  }

  if (error || !dashboardData) {
    return (
      <PageTemplate title="实时监控" subtitle="加载失败">
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

  const { today, yesterday, changes, alerts } = dashboardData;

  return (
    <PageTemplate
      title="实时监控"
      subtitle={`${date} vs ${dashboardData.yesterday_date} 核心指标对比`}
      actions={
        <div style={{ display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center' }}>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="input"
            style={{ width: '160px' }}
          />
          <button onClick={loadData} className="button">
            刷新数据
          </button>
        </div>
      }
    >
      {/* 核心指标卡片 */}
      <div className="panel">
        <h3 className="panel-title">📊 核心指标</h3>
        
        <div className="cards-grid" style={{ marginTop: 'var(--spacing-md)' }}>
          <SummaryCard
            label="正确率"
            value={`${today.correct_rate.toFixed(2)}%`}
            hint={`昨日: ${yesterday.correct_rate.toFixed(2)}% ${changes.correct_rate >= 0 ? '↑' : '↓'} ${Math.abs(changes.correct_rate).toFixed(2)}%`}
            tone={changes.correct_rate >= 0 ? 'success' : 'danger'}
          />

          <SummaryCard
            label="质检总量"
            value={today.total_count.toLocaleString()}
            hint={`昨日: ${yesterday.total_count.toLocaleString()} ${changes.total_count >= 0 ? '↑' : '↓'} ${Math.abs(changes.total_count).toLocaleString()}`}
            tone="neutral"
          />

          <SummaryCard
            label="误判率"
            value={`${today.misjudge_rate.toFixed(2)}%`}
            hint={`昨日: ${yesterday.misjudge_rate.toFixed(2)}% ${changes.misjudge_rate >= 0 ? '↑' : '↓'} ${Math.abs(changes.misjudge_rate).toFixed(2)}%`}
            tone={changes.misjudge_rate <= 0 ? 'success' : 'warning'}
          />

          <SummaryCard
            label="申诉率"
            value={`${today.appeal_rate.toFixed(2)}%`}
            hint={`昨日: ${yesterday.appeal_rate.toFixed(2)}% ${changes.appeal_rate >= 0 ? '↑' : '↓'} ${Math.abs(changes.appeal_rate).toFixed(2)}%`}
            tone={changes.appeal_rate <= 0 ? 'success' : 'warning'}
          />
        </div>
      </div>

      {/* 异常告警 */}
      {alerts && alerts.length > 0 && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--warning-bg)', borderColor: 'var(--warning)' }}>
          <h3 className="panel-title">⚠️ 异常告警</h3>
          <ul style={{ marginTop: 'var(--spacing-md)', paddingLeft: '20px' }}>
            {alerts.map((alert: any, index: number) => (
              <li key={index} style={{ marginBottom: 'var(--spacing-sm)', color: 'var(--warning)' }}>
                {alert.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 使用提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--card-bg)' }}>
        <h3 className="panel-title">💡 使用提示</h3>
        <ul style={{ marginTop: 'var(--spacing-md)', paddingLeft: '20px', color: 'var(--text-muted)', lineHeight: 1.8 }}>
          <li>选择日期后点击"刷新数据"获取最新数据</li>
          <li>推荐测试日期：2026-04-01（有39,140条真实数据）</li>
          <li>正确率：当日正确数/质检总量</li>
          <li>误判率：误判数/质检总量</li>
          <li>申诉率：申诉数/质检总量</li>
        </ul>
      </div>

      {/* JSON数据查看器（调试用） */}
      <details style={{ marginTop: 'var(--spacing-lg)' }}>
        <summary style={{ cursor: 'pointer', color: 'var(--primary)', fontWeight: 'bold' }}>
          📋 查看完整API响应数据
        </summary>
        <pre style={{ 
          marginTop: 'var(--spacing-md)', 
          padding: 'var(--spacing-md)', 
          background: '#1e1e1e', 
          color: '#d4d4d4',
          borderRadius: '8px',
          overflow: 'auto',
          fontSize: '12px'
        }}>
          {JSON.stringify(dashboardData, null, 2)}
        </pre>
      </details>
    </PageTemplate>
  );
}
