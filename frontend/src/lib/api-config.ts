/**
 * API配置文件
 * 
 * 配置后端API的基础URL和相关参数
 */

export const API_CONFIG = {
  // API基础URL
  BASE_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  
  // API前缀
  API_PREFIX: '/api/v1',
  
  // 超时时间（毫秒）
  TIMEOUT: 30000,
  
  // 重试次数
  RETRY_COUNT: 3,
  
  // 重试延迟（毫秒）
  RETRY_DELAY: 1000
};

/**
 * 构造完整的API URL
 * @param path API路径（如：/monitor/dashboard）
 * @returns 完整的API URL
 */
export function getApiUrl(path: string): string {
  // 移除path开头的斜杠（如果有）
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_CONFIG.BASE_URL}${API_CONFIG.API_PREFIX}${cleanPath}`;
}

/**
 * API错误类
 */
export class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public data?: any
  ) {
    super(message);
    this.name = 'APIError';
  }
}

/**
 * 通用API请求函数
 * @param path API路径
 * @param options 请求选项
 * @returns API响应数据
 */
export async function apiRequest<T = any>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = getApiUrl(path);
  
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers
      },
      signal: AbortSignal.timeout(API_CONFIG.TIMEOUT)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new APIError(
        errorData?.message || `请求失败: ${response.statusText}`,
        response.status,
        errorData
      );
    }
    
    return await response.json();
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    
    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        throw new APIError('请求超时，请稍后重试');
      }
      throw new APIError(error.message);
    }
    
    throw new APIError('未知错误');
  }
}

/**
 * 带重试的API请求
 * @param path API路径
 * @param options 请求选项
 * @param retries 剩余重试次数
 * @returns API响应数据
 */
export async function apiRequestWithRetry<T = any>(
  path: string,
  options?: RequestInit,
  retries: number = API_CONFIG.RETRY_COUNT
): Promise<T> {
  try {
    return await apiRequest<T>(path, options);
  } catch (error) {
    if (retries > 0 && error instanceof APIError && (!error.status || error.status >= 500)) {
      // 只对5xx错误或网络错误重试
      await new Promise(resolve => setTimeout(resolve, API_CONFIG.RETRY_DELAY));
      return apiRequestWithRetry<T>(path, options, retries - 1);
    }
    throw error;
  }
}
