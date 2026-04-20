const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

// 慢请求阈值（毫秒）。与后端 API_SLOW_THRESHOLD_MS 对齐，便于前后端一起排障。
const SLOW_MS = Number(
  (typeof process !== "undefined" ? process.env.NEXT_PUBLIC_API_SLOW_MS : undefined) ||
    (typeof process !== "undefined" ? process.env.API_SLOW_THRESHOLD_MS : undefined) ||
    800,
);

// 开发环境开启详细日志；生产环境只打 warn/error。
const DEV = typeof process !== "undefined" && process.env.NODE_ENV !== "production";

export type ApiEnvelope<T> = {
  ok: boolean;
  data: T;
  message?: string;
};

export type ApiRequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
};

/** 带有 API 上下文的错误，便于前端定位问题时附带 request_id 和路径。 */
export class ApiError extends Error {
  status: number;
  path: string;
  method: string;
  requestId: string | null;
  elapsedMs: number;

  constructor(init: {
    message: string;
    status: number;
    path: string;
    method: string;
    requestId: string | null;
    elapsedMs: number;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.path = init.path;
    this.method = init.method;
    this.requestId = init.requestId;
    this.elapsedMs = init.elapsedMs;
  }
}

export function getApiBaseUrl(): string {
  return (
    process.env.QC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    DEFAULT_API_BASE_URL
  );
}

// ===== 内部日志 =====

type LogLevel = "info" | "warn" | "error";

type LogRecord = {
  method: string;
  path: string;
  status: number | "FAILED";
  elapsedMs: number;
  requestId: string | null;
  env: "ssr" | "browser";
  bodyPreview?: string;
  error?: string;
};

/** 脱敏 + 截断写请求 body，只为日志显示用。 */
function previewBody(body: unknown): string | undefined {
  if (body === undefined || body === null) return undefined;
  try {
    const text = typeof body === "string" ? body : JSON.stringify(body);
    if (!text) return undefined;
    // 简单脱敏：明显的 password/token/secret 键的值打码
    const masked = text.replace(/(\"(?:password|token|secret|authorization)\"\s*:\s*)\"[^\"]*\"/gi, '$1"***"');
    return masked.length > 200 ? `${masked.slice(0, 200)}…(${masked.length}b)` : masked;
  } catch {
    return "[unserializable body]";
  }
}

function pickLevel(record: LogRecord): LogLevel {
  if (record.status === "FAILED") return "error";
  if (typeof record.status === "number" && record.status >= 500) return "error";
  if (typeof record.status === "number" && record.status >= 400) return "warn";
  if (record.elapsedMs >= SLOW_MS) return "warn";
  return "info";
}

/** 统一把一次请求的结果打到 console。浏览器端带颜色，SSR 端一行字符串（便于 server log 抓取）。*/
function logApiCall(record: LogRecord): void {
  const level = pickLevel(record);

  // 生产环境 info 一律不打，减少噪音。
  if (!DEV && level === "info") return;

  const tag = `[api] ${record.method} ${record.path}`;
  const status = record.status;
  const elapsed = `${record.elapsedMs.toFixed(0)}ms`;
  const rid = record.requestId ? `rid=${record.requestId}` : "rid=-";
  const base = `${tag} status=${status} in ${elapsed} ${rid} (${record.env})`;
  const extras: string[] = [];
  if (record.bodyPreview) extras.push(`body=${record.bodyPreview}`);
  if (record.error) extras.push(`err=${record.error}`);
  const line = extras.length ? `${base} ${extras.join(" ")}` : base;

  const fn = level === "error" ? console.error : level === "warn" ? console.warn : console.log;

  if (record.env === "browser") {
    // 浏览器端用 CSS 彩色输出，方便肉眼扫描。
    const color =
      level === "error" ? "#ef4444" : level === "warn" ? "#f59e0b" : "#10b981";
    fn(
      `%c${tag}%c status=${String(status)} in ${elapsed} %c${rid}%c${
        extras.length ? ` ${extras.join(" ")}` : ""
      } (${record.env})`,
      `color:${color};font-weight:600`,
      "color:inherit",
      "color:#64748b",
      "color:inherit",
    );
  } else {
    fn(line);
  }
}

// ===== 核心请求 =====

export async function requestApi<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers } = options;
  const env: "ssr" | "browser" = typeof window === "undefined" ? "ssr" : "browser";
  const start =
    typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now()
      : Date.now();
  const bodyPreview = method !== "GET" ? previewBody(body) : undefined;

  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      method,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (networkErr) {
    const elapsedMs =
      (typeof performance !== "undefined" && typeof performance.now === "function"
        ? performance.now()
        : Date.now()) - start;
    const errMsg = networkErr instanceof Error ? networkErr.message : String(networkErr);
    logApiCall({
      method,
      path,
      status: "FAILED",
      elapsedMs,
      requestId: null,
      env,
      bodyPreview,
      error: errMsg,
    });
    throw new ApiError({
      message: `API 网络错误：${errMsg}`,
      status: 0,
      path,
      method,
      requestId: null,
      elapsedMs,
    });
  }

  const elapsedMs =
    (typeof performance !== "undefined" && typeof performance.now === "function"
      ? performance.now()
      : Date.now()) - start;
  const requestId = response.headers.get("X-Request-Id");

  if (!response.ok) {
    // 尝试解析错误体（FastAPI 异常兜底会返回 {error, request_id, message}）
    let message = `${response.status} ${response.statusText}`;
    try {
      const errBody = await response.clone().json();
      if (errBody && typeof errBody === "object") {
        const detail =
          (errBody as Record<string, unknown>).message ??
          (errBody as Record<string, unknown>).detail ??
          (errBody as Record<string, unknown>).error;
        if (detail) message = `${response.status} ${String(detail)}`;
      }
    } catch {
      // ignore json parse error
    }
    logApiCall({
      method,
      path,
      status: response.status,
      elapsedMs,
      requestId,
      env,
      bodyPreview,
      error: message,
    });
    throw new ApiError({
      message: `API 请求失败：${message}`,
      status: response.status,
      path,
      method,
      requestId,
      elapsedMs,
    });
  }

  logApiCall({
    method,
    path,
    status: response.status,
    elapsedMs,
    requestId,
    env,
    bodyPreview,
  });

  const payload = (await response.json()) as ApiEnvelope<T> | T;
  if (typeof payload === "object" && payload !== null && "ok" in payload && "data" in payload) {
    return (payload as ApiEnvelope<T>).data;
  }
  return payload as T;
}

export async function fetchApi<T>(path: string): Promise<T> {
  return requestApi<T>(path);
}

export async function safeFetchApi<T>(path: string): Promise<{ data: T | null; error: string | null }> {
  try {
    const data = await fetchApi<T>(path);
    return { data, error: null };
  } catch (error) {
    const message = formatSafeError(error);
    return { data: null, error: message };
  }
}

export async function safeRequestApi<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<{ data: T | null; error: string | null }> {
  try {
    const data = await requestApi<T>(path, options);
    return { data, error: null };
  } catch (error) {
    const message = formatSafeError(error);
    return { data: null, error: message };
  }
}

/** 统一 safe* 错误文案，附带 rid 便于用户截图反馈时我们能溯源。 */
function formatSafeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.requestId
      ? `${error.message}（rid=${error.requestId}）`
      : error.message;
  }
  return error instanceof Error ? error.message : "未知错误";
}

// ==================== 监控接口（Monitor） ====================

export type MonitorDashboardResponse = {
  date: string;
  yesterday_date: string;
  today: {
    total_count: number;
    correct_count: number;
    correct_rate: number;
    misjudge_rate: number;
    appeal_rate: number;
  };
  yesterday: {
    total_count: number;
    correct_count: number;
    correct_rate: number;
    misjudge_rate: number;
    appeal_rate: number;
  };
  changes: {
    total_count: number;
    total_count_rate: number;
    correct_rate: number;
    misjudge_rate: number;
    appeal_rate: number;
  };
  alerts: Array<{
    type: string;
    level: string;
    title: string;
    message: string;
    current_value: number;
    previous_value: number;
    change: number;
  }>;
};

export async function getMonitorDashboard(date?: string): Promise<MonitorDashboardResponse> {
  const path = date ? `/api/v1/monitor/dashboard?date=${date}` : '/api/v1/monitor/dashboard';
  return fetchApi<MonitorDashboardResponse>(path);
}

export type QueueRankingItem = {
  rank: number;
  queue_name: string;
  total_count: number;
  correct_count: number;
  correct_rate: number;
  misjudge_rate: number;
  missjudge_rate: number;
  main_errors: string;
};

export async function getQueueRanking(threshold: number = 90, limit: number = 10): Promise<QueueRankingItem[]> {
  return fetchApi<QueueRankingItem[]>(`/api/v1/monitor/queue-ranking?threshold=${threshold}&limit=${limit}`);
}

export type ErrorRankingItem = {
  rank: number;
  error_type: string;
  error_count: number;
  error_percentage: number;
  misjudge_count: number;
  missjudge_count: number;
  misjudge_rate: number;
  missjudge_rate: number;
  main_queues: string;
};

export async function getErrorRanking(limit: number = 5): Promise<ErrorRankingItem[]> {
  return fetchApi<ErrorRankingItem[]>(`/api/v1/monitor/error-ranking?limit=${limit}`);
}

export type ReviewerRankingItem = {
  rank: number;
  reviewer_name: string;
  queue_name: string;
  review_count: number;
  correct_count: number;
  correct_rate: number;
  misjudge_rate: number;
  missjudge_rate: number;
  main_errors: string;
};

export async function getReviewerRanking(threshold: number = 85, limit: number = 10): Promise<ReviewerRankingItem[]> {
  return fetchApi<ReviewerRankingItem[]>(`/api/v1/monitor/reviewer-ranking?threshold=${threshold}&limit=${limit}`);
}

// ==================== 分析接口（Analysis） ====================

export type ErrorOverviewResponse = {
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
    review_count: number;
    error_count: number;
    error_rate: number;
  }>;
  error_distribution: Array<{
    error_type: string;
    count: number;
    percentage: number;
  }>;
  top_queues: Array<{
    queue_name: string;
    total_count: number;
    error_count: number;
    error_rate: number;
  }>;
  misjudge_stats: {
    misjudge_count: number;
    missjudge_count: number;
    misjudge_rate: number;
    missjudge_rate: number;
  };
};

export async function getErrorOverview(days: number = 7): Promise<ErrorOverviewResponse> {
  return fetchApi<ErrorOverviewResponse>(`/api/v1/analysis/error-overview?days=${days}`);
}

export type ErrorHeatmapResponse = {
  date_range: {
    start_date: string;
    end_date: string;
    days: number;
  };
  error_types: string[];
  queues: string[];
  matrix: Array<{
    error_type: string;
    queue: string;
    count: number;
    rate: number;
  }>;
  summary: {
    total_error_types: number;
    total_queues: number;
    total_combinations: number;
    total_errors: number;
  };
};

export async function getErrorHeatmap(days: number = 7): Promise<ErrorHeatmapResponse> {
  return fetchApi<ErrorHeatmapResponse>(`/api/v1/analysis/error-heatmap?days=${days}`);
}


// ==================== 可视化接口（Visualization） ====================

export type PerformanceTrendResponse = {
  metric: string;
  date_range: {
    start_date: string;
    end_date: string;
    days: number;
  };
  data: {
    dates: string[];
    values: number[];
  };
  statistics: {
    average: number;
    max: number;
    min: number;
    latest: number;
  };
  trend: {
    status: string;
    direction: string;
    change: number;
    change_rate: number;
    first_half_avg: number;
    second_half_avg: number;
  };
};

export async function getPerformanceTrend(
  days: number = 7,
  metric: 'correct_rate' | 'misjudge_rate' | 'appeal_rate' = 'correct_rate'
): Promise<PerformanceTrendResponse> {
  return fetchApi<PerformanceTrendResponse>(`/api/v1/visualization/performance-trend?days=${days}&metric=${metric}`);
}

export type ApiPerformanceResponse = {
  date: string;
  note: string;
  apis: Array<{
    endpoint: string;
    avg_response_time: number;
    p95_response_time: number;
    p99_response_time: number;
    qps: number;
    error_rate: number;
    status: string;
  }>;
  summary: {
    total_apis: number;
    healthy_count: number;
    warning_count: number;
    critical_count: number;
    avg_response_time: number;
    total_qps: number;
  };
};

export async function getApiPerformance(date?: string): Promise<ApiPerformanceResponse> {
  const path = date ? `/api/v1/visualization/api-performance?date=${date}` : '/api/v1/visualization/api-performance';
  return fetchApi<ApiPerformanceResponse>(path);
}

