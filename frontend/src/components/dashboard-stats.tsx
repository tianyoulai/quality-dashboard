/**
 * 使用 useAsync Hook 的示例组件
 * 
 * 场景：从 API 获取数据并展示，自动管理 loading/error 状态
 * 
 * 使用方式：
 * ```tsx
 * import { DashboardStats } from '@/components/dashboard-stats';
 * 
 * <DashboardStats grain="day" selectedDate="2026-04-16" />
 * ```
 */

'use client';

import { useMemo } from 'react';
import { useAsync } from '@/hooks/useAsync';

type DashboardStatsProps = {
  grain: 'day' | 'week' | 'month';
  selectedDate: string;
};

type DashboardData = {
  total_samples: number;
  error_rate: number;
  avg_processing_time: number;
  alert_count: number;
};

export function DashboardStats({ grain, selectedDate }: DashboardStatsProps) {
  // 动态构建 API 路径
  const apiPath = useMemo(
    () => `/api/v1/dashboard/overview?grain=${grain}&selected_date=${selectedDate}`,
    [grain, selectedDate]
  );

  // 使用 useAsync Hook 自动管理异步数据加载
  const { data, loading, error, reload } = useAsync<{ data: DashboardData }>(
    apiPath,
    {},
    [grain, selectedDate]  // 依赖项变化时重新加载
  );

  // Loading 状态
  if (loading) {
    return (
      <div className="stats-container">
        <div className="stats-loading">
          <div className="spinner"></div>
          <p>加载数据中...</p>
        </div>
        
        <style jsx>{`
          .stats-container {
            padding: 2rem;
          }
          
          .stats-loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1rem;
            padding: 3rem;
          }
          
          .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #e5e7eb;
            border-top-color: #8B5CF6;
            border-radius: 50%;
            animation: spin 1s linear infinite;
          }
          
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  // Error 状态
  if (error) {
    return (
      <div className="stats-container">
        <div className="stats-error">
          <div className="error-icon">⚠️</div>
          <h3>加载失败</h3>
          <p className="error-message">{error}</p>
          <button onClick={reload} className="button-retry">
            重试
          </button>
        </div>
        
        <style jsx>{`
          .stats-error {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1rem;
            padding: 3rem;
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 8px;
          }
          
          .error-icon {
            font-size: 3rem;
          }
          
          .error-message {
            color: #dc2626;
            text-align: center;
          }
          
          .button-retry {
            padding: 0.5rem 1.5rem;
            background: #8B5CF6;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.875rem;
            font-weight: 500;
          }
          
          .button-retry:hover {
            background: #7C3AED;
          }
        `}</style>
      </div>
    );
  }

  // 无数据
  if (!data || !data.data) {
    return (
      <div className="stats-container">
        <div className="stats-empty">
          <p>暂无数据</p>
        </div>
        
        <style jsx>{`
          .stats-empty {
            padding: 3rem;
            text-align: center;
            color: #6b7280;
          }
        `}</style>
      </div>
    );
  }

  // 展示数据
  const stats = data.data;
  
  return (
    <div className="stats-container">
      <div className="stats-header">
        <h2>数据概览</h2>
        <button onClick={reload} className="button-refresh">
          🔄 刷新
        </button>
      </div>
      
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">总样本数</div>
          <div className="stat-value">{stats.total_samples.toLocaleString()}</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">错误率</div>
          <div className="stat-value">{(stats.error_rate * 100).toFixed(2)}%</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">平均处理时间</div>
          <div className="stat-value">{stats.avg_processing_time.toFixed(1)}s</div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">告警数量</div>
          <div className="stat-value alert-count">{stats.alert_count}</div>
        </div>
      </div>
      
      <style jsx>{`
        .stats-container {
          padding: 1.5rem;
        }
        
        .stats-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
        }
        
        .stats-header h2 {
          margin: 0;
          font-size: 1.5rem;
          font-weight: 700;
          color: #1a1a1a;
        }
        
        .button-refresh {
          padding: 0.5rem 1rem;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 4px;
          cursor: pointer;
          font-size: 0.875rem;
          transition: all 0.2s;
        }
        
        .button-refresh:hover {
          background: #f9fafb;
          border-color: #8B5CF6;
        }
        
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1.5rem;
        }
        
        .stat-card {
          padding: 1.5rem;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        
        .stat-label {
          font-size: 0.875rem;
          color: #6b7280;
          margin-bottom: 0.5rem;
        }
        
        .stat-value {
          font-size: 2rem;
          font-weight: 700;
          color: #1a1a1a;
        }
        
        .alert-count {
          color: #dc2626;
        }
      `}</style>
    </div>
  );
}
