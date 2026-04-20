/**
 * useAsync Hook - 统一的异步数据加载 Hook
 * 
 * 功能：
 * 1. 自动管理 loading/data/error 状态
 * 2. 组件卸载时自动取消请求
 * 3. 支持依赖项变化时重新加载
 * 4. 集成错误码友好提示
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import { requestApiWithRetry, RequestCanceller, formatBusinessError } from './api-enhanced';
import type { ApiRequestOptions } from './api';

export type AsyncState<T> = {
  loading: boolean;
  data: T | null;
  error: string | null;
  reload: () => void;
};

/**
 * 异步数据加载 Hook
 * 
 * @param path - API 路径
 * @param options - 请求配置
 * @param dependencies - 依赖项数组，变化时重新加载
 * 
 * @example
 * ```tsx
 * function AlertsPage() {
 *   const { loading, data, error, reload } = useAsync<Alert[]>(
 *     '/api/v1/alerts?page=1',
 *     {},
 *     []
 *   );
 * 
 *   if (loading) return <div>加载中...</div>;
 *   if (error) return <div className="error">{error} <button onClick={reload}>重试</button></div>;
 *   if (!data) return null;
 * 
 *   return (
 *     <ul>
 *       {data.map(alert => <li key={alert.id}>{alert.message}</li>)}
 *     </ul>
 *   );
 * }
 * ```
 */
export function useAsync<T>(
  path: string,
  options: ApiRequestOptions = {},
  dependencies: any[] = []
): AsyncState<T> {
  const [state, setState] = useState<Omit<AsyncState<T>, 'reload'>>({
    loading: true,
    data: null,
    error: null,
  });

  const load = useCallback(() => {
    let cancelled = false;
    const canceller = new RequestCanceller();

    setState(prev => ({ ...prev, loading: true, error: null }));

    requestApiWithRetry<T>(path, options, { maxRetries: 2 })
      .then(data => {
        canceller.throwIfCancelled();
        if (!cancelled) {
          setState({ loading: false, data, error: null });
        }
      })
      .catch(err => {
        canceller.throwIfCancelled();
        if (!cancelled && err.message !== 'Request cancelled') {
          setState({ loading: false, data: null, error: formatBusinessError(err) });
        }
      });

    return () => {
      cancelled = true;
      canceller.cancel();
    };
  }, [path, JSON.stringify(options), ...dependencies]);

  useEffect(() => {
    return load();
  }, [load]);

  return {
    ...state,
    reload: load,
  };
}

/**
 * 延迟加载 Hook（手动触发加载）
 * 
 * @example
 * ```tsx
 * function AlertDetailModal({ alertId }: { alertId: string }) {
 *   const { loading, data, error, execute } = useLazyAsync<AlertDetail>();
 * 
 *   useEffect(() => {
 *     if (alertId) {
 *       execute(`/api/v1/alerts/${alertId}`);
 *     }
 *   }, [alertId]);
 * 
 *   if (loading) return <Spinner />;
 *   if (error) return <ErrorMessage error={error} />;
 *   if (!data) return null;
 * 
 *   return <div>{data.description}</div>;
 * }
 * ```
 */
export function useLazyAsync<T>(): AsyncState<T> & {
  execute: (path: string, options?: ApiRequestOptions) => Promise<void>;
} {
  const [state, setState] = useState<Omit<AsyncState<T>, 'reload'>>({
    loading: false,
    data: null,
    error: null,
  });

  const execute = useCallback(async (path: string, options: ApiRequestOptions = {}) => {
    const canceller = new RequestCanceller();

    setState({ loading: true, data: null, error: null });

    try {
      const data = await requestApiWithRetry<T>(path, options, { maxRetries: 2 });
      canceller.throwIfCancelled();
      setState({ loading: false, data, error: null });
    } catch (err) {
      canceller.throwIfCancelled();
      if ((err as Error).message !== 'Request cancelled') {
        setState({ loading: false, data: null, error: formatBusinessError(err) });
      }
    }
  }, []);

  return {
    ...state,
    reload: () => {},  // 延迟加载不支持 reload
    execute,
  };
}

/**
 * 分页数据加载 Hook
 * 
 * @example
 * ```tsx
 * function AlertsList() {
 *   const { loading, data, error, page, pageSize, total, nextPage, prevPage, setPageSize } = 
 *     usePagination<Alert>('/api/v1/alerts', { pageSize: 20 });
 * 
 *   return (
 *     <div>
 *       <AlertsTable data={data} />
 *       <Pagination
 *         current={page}
 *         total={total}
 *         pageSize={pageSize}
 *         onNext={nextPage}
 *         onPrev={prevPage}
 *         onPageSizeChange={setPageSize}
 *       />
 *     </div>
 *   );
 * }
 * ```
 */
export function usePagination<T>(
  basePath: string,
  options: {
    pageSize?: number;
    initialPage?: number;
  } = {}
) {
  const [page, setPage] = useState(options.initialPage || 1);
  const [pageSize, setPageSize] = useState(options.pageSize || 20);
  const [total, setTotal] = useState(0);

  const path = `${basePath}${basePath.includes('?') ? '&' : '?'}page=${page}&page_size=${pageSize}`;
  const { loading, data: rawData, error, reload } = useAsync<{
    items: T[];
    total: number;
    page: number;
    page_size: number;
    has_more: boolean;
  }>(path, {}, [page, pageSize]);

  useEffect(() => {
    if (rawData) {
      setTotal(rawData.total);
    }
  }, [rawData]);

  const nextPage = useCallback(() => {
    if (rawData?.has_more) {
      setPage(p => p + 1);
    }
  }, [rawData]);

  const prevPage = useCallback(() => {
    if (page > 1) {
      setPage(p => p - 1);
    }
  }, [page]);

  return {
    loading,
    data: rawData?.items || [],
    error,
    page,
    pageSize,
    total,
    hasMore: rawData?.has_more || false,
    nextPage,
    prevPage,
    setPage,
    setPageSize,
    reload,
  };
}
