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
import { apiClient } from '@/lib/api-enhanced';

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
  // 使用 useAsync Hook 自动管理异步数据加载
  const { data, loading, error, refetch } = useAsync(
    async () => {
      const response = await apiClient.get<{ data: DashboardData }>(
        `/api/v1/dashboard/overview`,
        {
          params: { grain, selected_date: selectedDate }
        }
      );
      return response.data;
    },
    // 依赖项：当 grain 或 selectedDate 变化时自动重新加载
    [grain, selectedDate]
  );

  // Loading 状态
  if (loading) {
    return (
      <div className="dashboard-stats-loading">
        <div className="skeleton-card" />
        <div className="skeleton-card" />
        <div className="skeleton-card" />
        <div className="skeleton-card" />
      </div>
    );
  }

  // Error 状态
  if (error) {
    return (
      <div className="dashboard-stats-error">
        <h3>⚠️ 数据加载失败</h3>
        <p>{error.message}</p>
        <button onClick={refetch} className="button-secondary">
          重试
        </button>
      </div>
    );
  }

  // Success 状态
  if (!data) {
    return (
      <div className="dashboard-stats-empty">
        <p>暂无数据</p>
      </div>
    );
  }

  return (
    <div className="dashboard-stats">
      <div className="stat-card">
        <div className="stat-label">总样本量</div>
        <div className="stat-value">{data.total_samples.toLocaleString()}</div>
      </div>
      
      <div className="stat-card">
        <div className="stat-label">错误率</div>
        <div className="stat-value">{(data.error_rate * 100).toFixed(2)}%</div>
      </div>
      
      <div className="stat-card">
        <div className="stat-label">平均处理时长</div>
        <div className="stat-value">{data.avg_processing_time.toFixed(1)}s</div>
      </div>
      
      <div className="stat-card">
        <div className="stat-label">告警数量</div>
        <div className="stat-value">{data.alert_count}</div>
      </div>

      <style jsx>{`
        .dashboard-stats {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }

        .stat-card {
          padding: 20px;
          background: white;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .stat-label {
          font-size: 14px;
          color: #6b7280;
          margin-bottom: 8px;
        }

        .stat-value {
          font-size: 28px;
          font-weight: 600;
          color: #1f2937;
        }

        .dashboard-stats-loading {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
        }

        .skeleton-card {
          height: 100px;
          background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
          background-size: 200% 100%;
          animation: loading 1.5s infinite;
          border-radius: 8px;
        }

        @keyframes loading {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }

        .dashboard-stats-error {
          padding: 20px;
          background: #fee;
          border: 1px solid #fcc;
          border-radius: 8px;
          text-align: center;
        }

        .dashboard-stats-error h3 {
          margin: 0 0 12px 0;
          color: #c00;
        }

        .dashboard-stats-error p {
          margin: 0 0 16px 0;
          color: #666;
        }

        .button-secondary {
          padding: 8px 16px;
          background: #6b7280;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }

        .button-secondary:hover {
          background: #4b5563;
        }

        .dashboard-stats-empty {
          padding: 40px;
          text-align: center;
          color: #9ca3af;
        }
      `}</style>
    </div>
  );
}
