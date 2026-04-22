/**
 * 数据可视化API客户端
 * 
 * 提供数据可视化相关的API调用函数
 */

import { apiRequestWithRetry } from './api-config';

// ============================================
// 类型定义
// ============================================

/**
 * 性能趋势响应数据
 */
export interface PerformanceTrendResponse {
  dates: string[];
  correct_rates: number[];
  misjudge_rates: number[];
  miss_rates: number[];
  appeal_rates: number[];
  review_counts: number[];
  summary: {
    avg_correct_rate: number;
    trend_direction: 'up' | 'down' | 'stable';
    best_date: string;
    worst_date: string;
  };
}

/**
 * API性能响应数据
 */
export interface ApiPerformanceResponse {
  endpoints: Array<{
    endpoint: string;
    avg_response_time: number;
    p50_response_time: number;
    p95_response_time: number;
    p99_response_time: number;
    total_requests: number;
    error_rate: number;
    status: 'excellent' | 'good' | 'normal' | 'slow';
  }>;
  summary: {
    total_endpoints: number;
    avg_response_time: number;
    slow_endpoints: number;
  };
}

/**
 * 队列分布响应数据
 */
export interface QueueDistributionResponse {
  queues: Array<{
    queue_name: string;
    review_count: number;
    correct_rate: number;
    percentage: number;
  }>;
  summary: {
    total_queues: number;
    total_reviews: number;
    avg_correct_rate: number;
  };
}

/**
 * 错误趋势响应数据
 */
export interface ErrorTrendResponse {
  dates: string[];
  error_types: Array<{
    error_type: string;
    daily_counts: number[];
    total_count: number;
    avg_daily: number;
    trend: 'increasing' | 'decreasing' | 'stable';
  }>;
  summary: {
    total_errors: number;
    avg_daily_errors: number;
    peak_date: string;
    peak_count: number;
  };
}

// ============================================
// API调用函数
// ============================================

/**
 * 获取性能趋势
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @returns 性能趋势数据
 */
export async function getPerformanceTrend(
  startDate: string,
  endDate: string
): Promise<PerformanceTrendResponse> {
  return apiRequestWithRetry<PerformanceTrendResponse>(
    `/visualization/performance-trend?start_date=${startDate}&end_date=${endDate}`
  );
}

/**
 * 获取API性能
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @returns API性能数据
 */
export async function getApiPerformance(
  startDate: string,
  endDate: string
): Promise<ApiPerformanceResponse> {
  return apiRequestWithRetry<ApiPerformanceResponse>(
    `/visualization/api-performance?start_date=${startDate}&end_date=${endDate}`
  );
}

/**
 * 获取队列分布
 * @param date 统计日期
 * @returns 队列分布数据
 */
export async function getQueueDistribution(
  date: string
): Promise<QueueDistributionResponse> {
  return apiRequestWithRetry<QueueDistributionResponse>(
    `/visualization/queue-distribution?date=${date}`
  );
}

/**
 * 获取错误趋势
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @param limit Top N错误类型（默认5）
 * @returns 错误趋势数据
 */
export async function getErrorTrend(
  startDate: string,
  endDate: string,
  limit: number = 5
): Promise<ErrorTrendResponse> {
  return apiRequestWithRetry<ErrorTrendResponse>(
    `/visualization/error-trend?start_date=${startDate}&end_date=${endDate}&limit=${limit}`
  );
}
