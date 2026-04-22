/**
 * 实时监控API客户端
 * 
 * 提供实时监控相关的API调用函数
 */

import { apiRequestWithRetry } from './api-config';

// ============================================
// 类型定义
// ============================================

/**
 * Dashboard响应数据
 */
export interface DashboardResponse {
  date: string;
  today: {
    total_qa: number;
    correct_rate: number;
    misjudge_rate: number;
    miss_rate: number;
    appeal_rate: number;
  };
  yesterday: {
    total_qa: number;
    correct_rate: number;
    misjudge_rate: number;
    miss_rate: number;
    appeal_rate: number;
  };
  changes: {
    total_qa: number;
    correct_rate: number;
    misjudge_rate: number;
    miss_rate: number;
    appeal_rate: number;
  };
  alerts: Array<{
    level: 'critical' | 'error' | 'warning' | 'info';
    title: string;
    message: string;
  }>;
}

/**
 * 队列排行响应数据
 */
export interface QueueRankingResponse {
  date: string;
  threshold: number;
  queues: Array<{
    rank: number;
    queue_name: string;
    correct_rate: number;
    total_qa: number;
    misjudge_count: number;
    miss_count: number;
    top_errors: string[];
  }>;
  summary: {
    total_below_threshold: number;
    avg_correct_rate: number;
    message: string;
  };
}

/**
 * 错误排行响应数据
 */
export interface ErrorRankingResponse {
  date: string;
  error_types: Array<{
    rank: number;
    error_type: string;
    count: number;
    rate: number;
    misjudge_count: number;
    miss_count: number;
  }>;
  summary: {
    total_errors: number;
    total_error_types: number;
    top5_coverage: number;
  };
}

/**
 * 审核人排行响应数据
 */
export interface ReviewerRankingResponse {
  date: string;
  threshold: number;
  reviewers: Array<{
    rank: number;
    reviewer_id: string;
    reviewer_name: string;
    correct_rate: number;
    total_qa: number;
    queue_name: string;
    main_errors: string[];
    group_name?: string;
  }>;
  summary: {
    total_below_threshold: number;
    avg_correct_rate: number;
  };
}

// ============================================
// API调用函数
// ============================================

/**
 * 获取Dashboard数据
 * @param date 统计日期 (YYYY-MM-DD)
 * @returns Dashboard数据
 */
export async function getDashboard(date: string): Promise<DashboardResponse> {
  return apiRequestWithRetry<DashboardResponse>(
    `/monitor/dashboard?date=${date}`
  );
}

/**
 * 获取队列排行
 * @param date 统计日期
 * @param threshold 正确率阈值（默认90%）
 * @param limit 返回数量（默认10）
 * @returns 队列排行数据
 */
export async function getQueueRanking(
  date: string,
  threshold: number = 90,
  limit: number = 10
): Promise<QueueRankingResponse> {
  return apiRequestWithRetry<QueueRankingResponse>(
    `/monitor/queue-ranking?date=${date}&threshold=${threshold}&limit=${limit}`
  );
}

/**
 * 获取错误排行
 * @param date 统计日期
 * @param limit 返回数量（默认10）
 * @returns 错误排行数据
 */
export async function getErrorRanking(
  date: string,
  limit: number = 10
): Promise<ErrorRankingResponse> {
  return apiRequestWithRetry<ErrorRankingResponse>(
    `/monitor/error-ranking?date=${date}&limit=${limit}`
  );
}

/**
 * 获取审核人排行
 * @param date 统计日期
 * @param threshold 正确率阈值（默认85%）
 * @param limit 返回数量（默认10）
 * @param groupName 批次/组名称（可选）
 * @returns 审核人排行数据
 */
export async function getReviewerRanking(
  date: string,
  threshold: number = 85,
  limit: number = 10,
  groupName?: string
): Promise<ReviewerRankingResponse> {
  let url = `/monitor/reviewer-ranking?date=${date}&threshold=${threshold}&limit=${limit}`;
  if (groupName) {
    url += `&group_name=${encodeURIComponent(groupName)}`;
  }
  return apiRequestWithRetry<ReviewerRankingResponse>(url);
}
