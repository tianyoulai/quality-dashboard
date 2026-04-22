"use client";

import { useState, useEffect, useCallback } from "react";
import { PageTemplate } from "@/components/page-template";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8002";

interface BadCase {
  complaint_date: string | null;
  complainant: string | null;
  error_type: string | null;
  correct_answer: string | null;
  reviewer_name: string | null;
  queue_name: string | null;
  comment_text: string | null;
  review_reason: string | null;
  review_summary: string | null;
  review_thinking: string | null;
  review_todo: string | null;
  qa_analysis: string | null;
  follow_up_action: string | null;
  repeated_complaint_cnt: string | null;
  has_internal_check: string | null;
  check_data: string | null;
  error_analysis: string | null;
}

interface Filters {
  error_types: string[];
  queues: string[];
  reviewers: string[];
}

interface Stats {
  total: number;
  error_type_dist: { label: string; cnt: number }[];
  queue_dist: { label: string; cnt: number }[];
  date_range: { min: string; max: string };
}

const ERROR_TYPE_COLOR: Record<string, string> = {
  漏判: "bg-orange-100 text-orange-700 border-orange-200",
  错判: "bg-red-100 text-red-700 border-red-200",
  误判: "bg-yellow-100 text-yellow-700 border-yellow-200",
};

function Badge({ text, type }: { text: string; type?: string }) {
  const cls = type ? (ERROR_TYPE_COLOR[type] ?? "bg-gray-100 text-gray-600 border-gray-200") : "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium ${cls}`}>
      {text}
    </span>
  );
}

function ExpandableText({ text, maxLen = 80 }: { text: string; maxLen?: number }) {
  const [expanded, setExpanded] = useState(false);
  if (!text || text.length <= maxLen) return <span>{text || "—"}</span>;
  return (
    <span>
      {expanded ? text : text.slice(0, maxLen) + "…"}
      <button
        onClick={() => setExpanded(!expanded)}
        className="ml-1 text-blue-500 hover:underline text-xs"
      >
        {expanded ? "收起" : "展开"}
      </button>
    </span>
  );
}

export default function BadCasePage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [filters, setFilters] = useState<Filters>({ error_types: [], queues: [], reviewers: [] });
  const [items, setItems] = useState<BadCase[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  // 筛选状态
  const [page, setPage] = useState(1);
  const [errorType, setErrorType] = useState("");
  const [queueName, setQueueName] = useState("");
  const [reviewerName, setReviewerName] = useState("");
  const [keyword, setKeyword] = useState("");
  const [keywordInput, setKeywordInput] = useState("");

  // 加载统计 + 筛选项
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/badcase/stats`)
      .then((r) => r.json())
      .then((d) => setStats(d.data))
      .catch(() => {});
    fetch(`${API_BASE}/api/v1/badcase/filters`)
      .then((r) => r.json())
      .then((d) => setFilters(d.data))
      .catch(() => {});
  }, []);

  // 加载列表
  const loadList = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: "15" });
    if (errorType) params.set("error_type", errorType);
    if (queueName) params.set("queue_name", queueName);
    if (reviewerName) params.set("reviewer_name", reviewerName);
    if (keyword) params.set("keyword", keyword);

    fetch(`${API_BASE}/api/v1/badcase/list?${params}`)
      .then((r) => r.json())
      .then((d) => {
        setItems(d.data.items ?? []);
        setTotal(d.data.total ?? 0);
        setTotalPages(d.data.total_pages ?? 1);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, errorType, queueName, reviewerName, keyword]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const handleSearch = () => {
    setKeyword(keywordInput);
    setPage(1);
  };

  const handleReset = () => {
    setErrorType("");
    setQueueName("");
    setReviewerName("");
    setKeyword("");
    setKeywordInput("");
    setPage(1);
  };

  return (
    <PageTemplate title="Bad Case 库" subtitle="外部投诉反馈复盘案例">
      {/* 统计摘要 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <div className="bg-white rounded-lg border p-3 text-center">
            <div className="text-2xl font-bold text-gray-800">{stats.total}</div>
            <div className="text-xs text-gray-500 mt-0.5">案例总数</div>
          </div>
          {stats.error_type_dist.map((e) => (
            <div key={e.label} className="bg-white rounded-lg border p-3 text-center">
              <div className={`text-2xl font-bold ${e.label === "漏判" ? "text-orange-600" : "text-red-600"}`}>
                {e.cnt}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">{e.label}</div>
            </div>
          ))}
          {stats.date_range?.min && (
            <div className="bg-white rounded-lg border p-3 text-center">
              <div className="text-sm font-semibold text-gray-700">
                {stats.date_range.min?.slice(0, 7)}
              </div>
              <div className="text-xs text-gray-400">~</div>
              <div className="text-sm font-semibold text-gray-700">
                {stats.date_range.max?.slice(0, 7)}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">时间范围</div>
            </div>
          )}
        </div>
      )}

      {/* 筛选栏 */}
      <div className="bg-white rounded-lg border p-3 mb-4 flex flex-wrap gap-2 items-end">
        <div className="flex flex-col gap-1 min-w-[120px]">
          <label className="text-xs text-gray-500">错误类型</label>
          <select
            value={errorType}
            onChange={(e) => { setErrorType(e.target.value); setPage(1); }}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="">全部</option>
            {filters.error_types.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1 min-w-[160px]">
          <label className="text-xs text-gray-500">队列</label>
          <select
            value={queueName}
            onChange={(e) => { setQueueName(e.target.value); setPage(1); }}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="">全部</option>
            {filters.queues.map((q) => <option key={q} value={q}>{q}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1 min-w-[160px]">
          <label className="text-xs text-gray-500">审核员</label>
          <select
            value={reviewerName}
            onChange={(e) => { setReviewerName(e.target.value); setPage(1); }}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="">全部</option>
            {filters.reviewers.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
          <label className="text-xs text-gray-500">关键词（评论内容/复盘原因）</label>
          <div className="flex gap-1">
            <input
              value={keywordInput}
              onChange={(e) => setKeywordInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="搜索..."
              className="border rounded px-2 py-1 text-sm flex-1"
            />
            <button
              onClick={handleSearch}
              className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
            >
              搜索
            </button>
          </div>
        </div>
        <button
          onClick={handleReset}
          className="px-3 py-1 border rounded text-sm text-gray-600 hover:bg-gray-50 self-end"
        >
          重置
        </button>
      </div>

      {/* 列表 */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <div className="px-4 py-2 border-b bg-gray-50 flex justify-between items-center">
          <span className="text-sm text-gray-600">共 <span className="font-semibold text-gray-800">{total}</span> 条</span>
          {loading && <span className="text-xs text-gray-400">加载中…</span>}
        </div>

        {items.length === 0 && !loading ? (
          <div className="py-12 text-center text-gray-400 text-sm">暂无数据</div>
        ) : (
          <div className="divide-y">
            {items.map((item, idx) => (
              <div key={idx} className="p-4 hover:bg-gray-50 transition-colors">
                {/* 头部行 */}
                <div className="flex flex-wrap gap-2 items-center mb-2">
                  <span className="text-xs text-gray-400">{item.complaint_date ?? "—"}</span>
                  {item.error_type && <Badge text={item.error_type} type={item.error_type} />}
                  {item.correct_answer && (
                    <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded">
                      正确答案: {item.correct_answer}
                    </span>
                  )}
                  {item.reviewer_name && (
                    <span className="text-xs text-gray-600">👤 {item.reviewer_name}</span>
                  )}
                  {item.queue_name && (
                    <span className="text-xs text-gray-500">📋 {item.queue_name}</span>
                  )}
                  {item.repeated_complaint_cnt && Number(item.repeated_complaint_cnt) > 1 && (
                    <span className="text-xs bg-red-50 text-red-600 border border-red-200 px-2 py-0.5 rounded">
                      连续被投诉 {item.repeated_complaint_cnt} 次
                    </span>
                  )}
                </div>

                {/* 评论内容 */}
                {item.comment_text && (
                  <div className="text-sm text-gray-700 mb-2 bg-gray-50 rounded px-3 py-2 border-l-2 border-gray-300">
                    <ExpandableText text={item.comment_text} maxLen={100} />
                  </div>
                )}

                {/* 复盘原因 — 结构化展示 */}
                {(item.review_thinking || item.review_summary) && (
                  <div className="text-xs text-gray-600 mb-1 bg-amber-50 border border-amber-100 rounded px-3 py-2">
                    <span className="font-medium text-amber-800">💭 一审思路：</span>
                    <span className="text-gray-700">
                      <ExpandableText text={item.review_thinking || item.review_summary || ""} maxLen={100} />
                    </span>
                    {item.review_todo && (
                      <div className="mt-1">
                        <span className="font-medium text-amber-800">📌 待跟进：</span>
                        <ExpandableText text={item.review_todo} maxLen={80} />
                      </div>
                    )}
                  </div>
                )}

                {/* 展开详情按钮 */}
                {(item.qa_analysis || item.follow_up_action || item.check_data) && (
                  <button
                    onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}
                    className="mt-1 text-xs text-blue-500 hover:underline"
                  >
                    {expandedRow === idx ? "▲ 收起" : "▼ 展开质培分析 & 跟进动作"}
                  </button>
                )}

                {/* 展开区 */}
                {expandedRow === idx && (
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-gray-600">
                    {item.qa_analysis && (
                      <div className="bg-blue-50 rounded p-3">
                        <div className="font-medium text-blue-800 mb-1">📋 质培侧分析</div>
                        <div className="whitespace-pre-line">{item.qa_analysis}</div>
                      </div>
                    )}
                    {item.follow_up_action && (
                      <div className="bg-green-50 rounded p-3">
                        <div className="font-medium text-green-800 mb-1">✅ 跟进动作</div>
                        <div className="whitespace-pre-line">{item.follow_up_action}</div>
                      </div>
                    )}
                    {item.check_data && (
                      <div className="bg-yellow-50 rounded p-3">
                        <div className="font-medium text-yellow-800 mb-1">📊 抽检数据</div>
                        <div className="whitespace-pre-line">{item.check_data}</div>
                      </div>
                    )}
                    {item.error_analysis && (
                      <div className="bg-orange-50 rounded p-3">
                        <div className="font-medium text-orange-800 mb-1">🔍 出错分析</div>
                        <div className="whitespace-pre-line">{item.error_analysis}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* 分页 */}
        {totalPages > 1 && (
          <div className="px-4 py-3 border-t bg-gray-50 flex justify-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1 border rounded text-sm disabled:opacity-40 hover:bg-white"
            >
              上一页
            </button>
            <span className="px-3 py-1 text-sm text-gray-600">
              {page} / {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 border rounded text-sm disabled:opacity-40 hover:bg-white"
            >
              下一页
            </button>
          </div>
        )}
      </div>
    </PageTemplate>
  );
}
