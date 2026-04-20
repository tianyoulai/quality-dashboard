/**
 * 使用 usePagination Hook 的示例组件
 * 
 * 场景：加载分页数据（如详情列表），自动管理页码、loading、分页元数据
 * 
 * 使用方式：
 * ```tsx
 * import { DetailsList } from '@/components/details-list';
 * 
 * <DetailsList filters={{ group_name: "组别A" }} />
 * ```
 */

'use client';

import { usePagination } from '@/hooks/useAsync';
import { apiClient } from '@/lib/api-enhanced';

type DetailsListProps = {
  filters?: Record<string, string>;
};

type DetailItem = {
  id: string;
  biz_date: string;
  group_name: string;
  reviewer_name: string;
  error_type: string;
  sample_id: string;
};

export function DetailsList({ filters = {} }: DetailsListProps) {
  // 使用 usePagination Hook 自动管理分页状态
  const {
    data,
    loading,
    error,
    page,
    totalPages,
    totalItems,
    setPage,
    refetch,
  } = usePagination<DetailItem>(
    async (currentPage, pageSize) => {
      const response = await apiClient.get<{
        data: {
          items: DetailItem[];
          total: number;
          page: number;
          page_size: number;
        };
      }>('/api/v1/details/query', {
        params: {
          ...filters,
          page: currentPage,
          page_size: pageSize,
        },
      });
      return {
        items: response.data.items,
        total: response.data.total,
      };
    },
    [JSON.stringify(filters)], // 依赖项：filters 变化时重置到第1页
    { pageSize: 20 } // 每页20条
  );

  // Loading 状态
  if (loading && !data) {
    return (
      <div className="details-list-loading">
        <p>加载中...</p>
      </div>
    );
  }

  // Error 状态
  if (error) {
    return (
      <div className="details-list-error">
        <h3>⚠️ 加载失败</h3>
        <p>{error.message}</p>
        <button onClick={refetch} className="button-secondary">
          重试
        </button>
      </div>
    );
  }

  // Empty 状态
  if (!data || data.length === 0) {
    return (
      <div className="details-list-empty">
        <p>暂无数据</p>
      </div>
    );
  }

  return (
    <div className="details-list">
      {/* 数据表格 */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>业务日期</th>
              <th>组别</th>
              <th>审核人</th>
              <th>错误类型</th>
              <th>样本ID</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr key={item.id}>
                <td>{item.biz_date}</td>
                <td>{item.group_name}</td>
                <td>{item.reviewer_name}</td>
                <td>{item.error_type}</td>
                <td>
                  <a href={`/samples/${item.sample_id}`} className="link">
                    {item.sample_id}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 分页控制 */}
      <div className="pagination">
        <div className="pagination-info">
          共 {totalItems} 条，第 {page} / {totalPages} 页
        </div>
        <div className="pagination-controls">
          <button
            onClick={() => setPage(1)}
            disabled={page === 1 || loading}
            className="pagination-button"
          >
            首页
          </button>
          <button
            onClick={() => setPage(page - 1)}
            disabled={page === 1 || loading}
            className="pagination-button"
          >
            上一页
          </button>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages || loading}
            className="pagination-button"
          >
            下一页
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={page >= totalPages || loading}
            className="pagination-button"
          >
            末页
          </button>
        </div>
      </div>

      {/* Loading 遮罩（翻页时显示） */}
      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />
        </div>
      )}

      <style jsx>{`
        .details-list {
          position: relative;
        }

        .table-container {
          overflow-x: auto;
          margin-bottom: 16px;
        }

        .data-table {
          width: 100%;
          border-collapse: collapse;
          background: white;
        }

        .data-table th {
          padding: 12px;
          text-align: left;
          background: #f3f4f6;
          border-bottom: 2px solid #e5e7eb;
          font-weight: 600;
        }

        .data-table td {
          padding: 12px;
          border-bottom: 1px solid #e5e7eb;
        }

        .data-table tbody tr:hover {
          background: #f9fafb;
        }

        .link {
          color: #3b82f6;
          text-decoration: none;
        }

        .link:hover {
          text-decoration: underline;
        }

        .pagination {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px;
          background: white;
          border-radius: 8px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .pagination-info {
          color: #6b7280;
          font-size: 14px;
        }

        .pagination-controls {
          display: flex;
          gap: 8px;
        }

        .pagination-button {
          padding: 8px 16px;
          background: white;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .pagination-button:hover:not(:disabled) {
          background: #f3f4f6;
          border-color: #9ca3af;
        }

        .pagination-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .loading-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(255, 255, 255, 0.8);
          display: flex;
          justify-content: center;
          align-items: center;
        }

        .spinner {
          width: 40px;
          height: 40px;
          border: 4px solid #e5e7eb;
          border-top-color: #3b82f6;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .details-list-loading,
        .details-list-error,
        .details-list-empty {
          padding: 40px;
          text-align: center;
          background: white;
          border-radius: 8px;
        }

        .details-list-error {
          background: #fee;
          border: 1px solid #fcc;
        }

        .details-list-error h3 {
          margin: 0 0 12px 0;
          color: #c00;
        }

        .details-list-error p {
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
      `}</style>
    </div>
  );
}
