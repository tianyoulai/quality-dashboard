/**
 * API 客户端增强版 - 新增重试、错误码统一处理
 * 
 * 在现有 api.ts 基础上扩展：
 * 1. 请求重试（针对 5xx 和网络错误）
 * 2. 业务错误码统一解析（对接后端 BusinessException）
 * 3. 请求取消（避免组件卸载后仍然执行回调）
 */

import { requestApi, ApiRequestOptions, ApiError } from './api';

/**
 * 标准业务错误响应格式（对应后端 BusinessException）
 */
export type BusinessErrorResponse = {
  error: {
    code: string;        // 错误码，如 "DATA_NOT_FOUND"
    message: string;     // 错误描述
  };
  request_id?: string;
};

/**
 * 带有业务错误码的 API 异常
 */
export class BusinessError extends ApiError {
  code: string;

  constructor(init: {
    code: string;
    message: string;
    status: number;
    path: string;
    method: string;
    requestId: string | null;
    elapsedMs: number;
  }) {
    super(init);
    this.name = 'BusinessError';
    this.code = init.code;
  }
}

/**
 * 重试配置
 */
export type RetryConfig = {
  maxRetries?: number;      // 最大重试次数，默认 3
  retryDelay?: number;      // 重试延迟（毫秒），默认 1000
  retryOn?: (error: ApiError) => boolean;  // 自定义重试条件
};

/**
 * 默认重试条件：5xx 或网络错误
 */
function defaultShouldRetry(error: ApiError): boolean {
  // 网络错误（status = 0）
  if (error.status === 0) return true;
  // 服务端错误（5xx）
  if (error.status >= 500) return true;
  // 408 请求超时
  if (error.status === 408) return true;
  // 429 频率限制（可选：是否重试）
  // if (error.status === 429) return true;
  return false;
}

/**
 * 带重试的 API 请求
 */
export async function requestApiWithRetry<T>(
  path: string,
  options: ApiRequestOptions = {},
  retryConfig: RetryConfig = {}
): Promise<T> {
  const {
    maxRetries = 3,
    retryDelay = 1000,
    retryOn = defaultShouldRetry
  } = retryConfig;

  let lastError: ApiError | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await requestApi<T>(path, options);
    } catch (error) {
      if (error instanceof ApiError) {
        lastError = error;

        // 最后一次尝试失败，不再重试
        if (attempt === maxRetries) {
          throw error;
        }

        // 检查是否需要重试
        if (!retryOn(error)) {
          throw error;
        }

        // 指数退避：第 n 次重试延迟 = retryDelay * 2^(n-1)
        const delay = retryDelay * Math.pow(2, attempt);
        console.warn(
          `[api-retry] ${options.method || 'GET'} ${path} failed (attempt ${attempt + 1}/${maxRetries + 1}), retrying in ${delay}ms...`,
          error
        );
        await sleep(delay);
      } else {
        // 非 ApiError，直接抛出
        throw error;
      }
    }
  }

  throw lastError || new Error('请求失败');
}

/**
 * 解析后端业务错误（BusinessException）
 */
export function parseBusinessError(error: unknown): BusinessError | null {
  if (!(error instanceof ApiError)) return null;

  // 尝试从错误消息中提取业务错误码
  // 后端异常格式：{"error": {"code": "DATA_NOT_FOUND", "message": "..."}, "request_id": "..."}
  const match = error.message.match(/API 请求失败：(\d+) (.+)/);
  if (!match) return null;

  const [, , detailStr] = match;
  try {
    const detail = JSON.parse(detailStr);
    if (detail && typeof detail === 'object' && 'error' in detail) {
      const errorObj = detail.error as { code: string; message: string };
      return new BusinessError({
        code: errorObj.code,
        message: errorObj.message,
        status: error.status,
        path: error.path,
        method: error.method,
        requestId: error.requestId,
        elapsedMs: error.elapsedMs
      });
    }
  } catch {
    // JSON 解析失败，返回 null
  }

  return null;
}

/**
 * 根据业务错误码显示友好提示
 */
export function formatBusinessError(error: unknown): string {
  const businessError = parseBusinessError(error);
  if (!businessError) {
    return error instanceof Error ? error.message : '未知错误';
  }

  const errorMessages: Record<string, string> = {
    DATA_NOT_FOUND: '数据不存在，请刷新后重试',
    VALIDATION_ERROR: '参数格式错误，请检查输入',
    DATABASE_ERROR: '数据库操作失败，请稍后重试',
    PERMISSION_DENIED: '无权限执行此操作',
    RATE_LIMIT_EXCEEDED: '请求过于频繁，请稍后再试',
    EXTERNAL_SERVICE_ERROR: '外部服务暂时不可用',
    CONFLICT: '数据已被修改，请刷新后重试',
  };

  const friendlyMessage = errorMessages[businessError.code] || businessError.message;
  const rid = businessError.requestId ? `（rid=${businessError.requestId}）` : '';
  return `${friendlyMessage}${rid}`;
}

/**
 * 请求取消控制器（防止组件卸载后仍然执行回调）
 */
export class RequestCanceller {
  private cancelled = false;

  cancel(): void {
    this.cancelled = true;
  }

  throwIfCancelled(): void {
    if (this.cancelled) {
      throw new Error('Request cancelled');
    }
  }
}

/**
 * 带取消功能的 API 请求
 */
export async function requestApiWithCancel<T>(
  path: string,
  options: ApiRequestOptions = {},
  canceller: RequestCanceller
): Promise<T> {
  canceller.throwIfCancelled();
  const result = await requestApi<T>(path, options);
  canceller.throwIfCancelled();
  return result;
}

/**
 * Sleep 工具函数
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ===== React Hook 示例 =====

/**
 * 使用示例（React Hook）：
 * 
 * import { useEffect, useState } from 'react';
 * import { requestApiWithRetry, RequestCanceller, formatBusinessError } from './api-enhanced';
 * 
 * function useAlerts() {
 *   const [alerts, setAlerts] = useState([]);
 *   const [loading, setLoading] = useState(true);
 *   const [error, setError] = useState<string | null>(null);
 * 
 *   useEffect(() => {
 *     const canceller = new RequestCanceller();
 * 
 *     async function loadAlerts() {
 *       try {
 *         const data = await requestApiWithRetry(
 *           '/api/v1/alerts?page=1&page_size=20',
 *           {},
 *           { maxRetries: 3 }
 *         );
 *         canceller.throwIfCancelled();
 *         setAlerts(data);
 *       } catch (err) {
 *         if (err.message !== 'Request cancelled') {
 *           setError(formatBusinessError(err));
 *         }
 *       } finally {
 *         setLoading(false);
 *       }
 *     }
 * 
 *     loadAlerts();
 * 
 *     return () => {
 *       canceller.cancel();
 *     };
 *   }, []);
 * 
 *   return { alerts, loading, error };
 * }
 */
