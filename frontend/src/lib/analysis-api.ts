/**
 * 错误分析API客户端
 * 
 * 提供错误分析相关的API调用函数
 */

import { apiRequestWithRetry } from './api-config';

// ============================================
// 类型定义
// ============================================

/**
 * 错误总览响应数据
 */
export interface ErrorOverviewResponse {
  date_range: {
    start_date: string;
    end_date: string;
    days: number;
  };
  total_errors: number;
  total_reviews: number;
  error_rate: number;
  daily_trend: Array<{
    date: string;
    error_count: number;
    review_count: number;
    error_rate: number;
  }>;
  error_distribution: Array<{
    error_type: string;
    count: number;
    rate: number;
  }>;
  top_queues: Array<{
    queue_name: string;
    error_count: number;
    review_count: number;
    error_rate: number;
  }>;
  misjudge_stats: {
    total_misjudge: number;
    total_miss: number;
    misjudge_rate: number;
    miss_rate: number;
  };
}

/**
 * 错误热力图响应数据
 */
export interface ErrorHeatmapResponse {
  error_types: string[];
  queues: string[];
  matrix: Array<{
    error_type: string;
    queue: string;
    count: number;
    rate: number;
  }>;
  summary: {
    total_cells: number;
    non_zero_cells: number;
    max_count: number;
    avg_count: number;
  };
}

/**
 * 根因分析响应数据
 */
export interface RootCauseResponse {
  date_range: {
    start_date: string;
    end_date: string;
  };
  categories: Array<{
    category: string;
    count: number;
    rate: number;
    examples: string[];
  }>;
  top_root_causes: Array<{
    root_cause: string;
    category: string;
    count: number;
    error_types: string[];
    queues: string[];
  }>;
  summary: {
    total_analyzed: number;
    has_root_cause: number;
    coverage_rate: number;
  };
}

// ============================================
// API调用函数
// ============================================

/**
 * 获取错误总览
 * @param days 查询天数（默认7天）
 * @returns 错误总览数据
 */
export async function getErrorOverview(
  days: number = 7
): Promise<ErrorOverviewResponse> {
  return apiRequestWithRetry<ErrorOverviewResponse>(
    `/analysis/error-overview?days=${days}`
  );
}

/**
 * 获取错误热力图
 * @param days 查询天数（默认7天）
 * @returns 热力图数据
 */
export async function getErrorHeatmap(
  days: number = 7
): Promise<ErrorHeatmapResponse> {
  return apiRequestWithRetry<ErrorHeatmapResponse>(
    `/analysis/error-heatmap?days=${days}`
  );
}

/**
 * 获取根因分析
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @returns 根因分析数据
 */
export async function getRootCause(
  startDate: string,
  endDate: string
): Promise<RootCauseResponse> {
  return apiRequestWithRetry<RootCauseResponse>(
    `/analysis/root-cause?start_date=${startDate}&end_date=${endDate}`
  );
}
