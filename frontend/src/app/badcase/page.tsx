"use client";

import { useState, useEffect, useCallback } from "react";
import { PageTemplate } from "@/components/page-template";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

interface BadCase {
  complaint_date: string | null;
  complainant: string | null;
  error_type: string | null;
  correct_answer: string | null;
  reviewer_name: string | null;
  queue_name: string | null;
  comment_text: string | null;
  review_reason: string | null;
  // 结构化字段
  reviewer_time: string | null;
  reviewer_choice: string | null;
  correct_choice: string | null;
  review_thinking: string | null;
  correct_thinking: string | null;
  review_action: string | null;
  // 质培侧
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

      {/* ── 统计数字卡片 ── */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {/* 总量 */}
          <div style={{
            background: '#fff', borderRadius: 12, padding: '18px 20px 14px',
            border: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,.06)',
            display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>案例总数</div>
            <div style={{ fontSize: 32, fontWeight: 700, color: '#6366f1', lineHeight: 1.1 }}>{stats.total}</div>
            <div style={{ fontSize: 12, color: '#9ca3af' }}>外部投诉反馈</div>
          </div>

          {/* 漏判 */}
          <div style={{
            background: '#fff7ed', borderRadius: 12, padding: '18px 20px 14px',
            border: '2px solid #fed7aa', boxShadow: '0 1px 4px rgba(249,115,22,.08)',
            display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>漏判</div>
            <div style={{ fontSize: 32, fontWeight: 700, color: '#ea580c', lineHeight: 1.1 }}>
              {stats.error_type_dist.find(e => e.label === '漏判')?.cnt ?? 0}
            </div>
            <div style={{ fontSize: 12, color: '#f97316' }}>
              {stats.total > 0
                ? `占比 ${((stats.error_type_dist.find(e => e.label === '漏判')?.cnt ?? 0) / stats.total * 100).toFixed(0)}%`
                : '—'}
            </div>
          </div>

          {/* 错判 */}
          <div style={{
            background: '#fff1f2', borderRadius: 12, padding: '18px 20px 14px',
            border: '2px solid #fecdd3', boxShadow: '0 1px 4px rgba(239,68,68,.08)',
            display: 'flex', flexDirection: 'column', gap: 4,
          }}>
            <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>错判</div>
            <div style={{ fontSize: 32, fontWeight: 700, color: '#dc2626', lineHeight: 1.1 }}>
              {stats.error_type_dist.find(e => e.label === '错判')?.cnt ?? 0}
            </div>
            <div style={{ fontSize: 12, color: '#ef4444' }}>
              {stats.total > 0
                ? `占比 ${((stats.error_type_dist.find(e => e.label === '错判')?.cnt ?? 0) / stats.total * 100).toFixed(0)}%`
                : '—'}
            </div>
          </div>

          {/* 时间范围 */}
          {stats.date_range?.min && (
            <div style={{
              background: '#f8fafc', borderRadius: 12, padding: '18px 20px 14px',
              border: '1px solid #e5e7eb', boxShadow: '0 1px 4px rgba(0,0,0,.04)',
              display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>时间范围</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#374151', lineHeight: 1.2 }}>
                {stats.date_range.min?.slice(0, 7)}
              </div>
              <div style={{ fontSize: 12, color: '#9ca3af' }}>
                ～ {stats.date_range.max?.slice(0, 7)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── 筛选栏 ── */}
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '14px 16px', marginBottom: 20 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          🔍 筛选条件
        </div>
        <div className="flex flex-wrap gap-3 items-end">
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
      </div>

      {/* ── 案例列表 ── */}
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        <div style={{ padding: '10px 16px', borderBottom: '1px solid #f3f4f6', background: '#f9fafb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>
            📋 案例列表
            <span style={{ fontSize: 12, fontWeight: 400, color: '#9ca3af', marginLeft: 8 }}>共 {total} 条</span>
          </span>
          {loading && <span style={{ fontSize: 12, color: '#9ca3af' }}>加载中…</span>}
        </div>

        {items.length === 0 && !loading ? (
          <div style={{ padding: '48px 0', textAlign: 'center', color: '#9ca3af', fontSize: 14 }}>暂无数据</div>
        ) : (
          <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {items.map((item, idx) => (
              <div key={idx} style={{
                border: '1px solid #e5e7eb',
                borderLeft: `4px solid ${item.error_type === '漏判' ? '#f97316' : '#ef4444'}`,
                borderRadius: 8,
                padding: '14px 16px',
                background: '#fafafa',
                transition: 'box-shadow 0.15s',
              }}
                onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,.08)')}
                onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
              >
                {/* ── 头部：日期 + 标签行 ── */}
                <div className="flex flex-wrap gap-2 items-center mb-3">
                  <span className="text-xs text-gray-400">{item.complaint_date ?? "—"}</span>
                  {item.error_type && <Badge text={item.error_type} type={item.error_type} />}
                  {/* 一审选项 → 正确答案 */}
                  {(item.reviewer_choice || item.correct_choice || item.correct_answer) && (
                    <span className="text-xs flex items-center gap-1">
                      {item.reviewer_choice && (
                        <span className="bg-orange-50 text-orange-700 border border-orange-200 px-2 py-0.5 rounded">
                          一审：{item.reviewer_choice}
                        </span>
                      )}
                      <span className="text-gray-400">→</span>
                      <span className="bg-green-50 text-green-700 border border-green-200 px-2 py-0.5 rounded">
                        正确：{item.correct_choice || item.correct_answer}
                      </span>
                    </span>
                  )}
                  {item.reviewer_name && (
                    <span className="text-xs font-bold text-gray-600">👤 {item.reviewer_name}</span>
                  )}
                  {item.queue_name && (
                    <span 
                      className="text-xs text-gray-400"
                      style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={item.queue_name}
                    >
                      📋 {item.queue_name}
                    </span>
                  )}
                  {item.repeated_complaint_cnt && Number(item.repeated_complaint_cnt) > 1 && (
                    <span className="text-xs bg-red-50 text-red-600 border border-red-200 px-2 py-0.5 rounded">
                      ⚠️ 连续被投诉 {item.repeated_complaint_cnt} 次
                    </span>
                  )}
                </div>

                {/* ── 评论内容 ── */}
                {item.comment_text && (
                  <div 
                    style={{
                      background: '#f8fafc',
                      borderLeft: '3px solid #e2e8f0',
                      borderRadius: '6px',
                      padding: '10px 12px',
                      fontSize: '14px',
                      lineHeight: '1.6',
                      color: '#374151',
                      marginBottom: '12px'
                    }}
                  >
                    <ExpandableText text={item.comment_text} maxLen={120} />
                  </div>
                )}

                {/* ── 复盘区：一审思路 + 正确思路（垂直排列）── */}
                {(item.review_thinking || item.correct_thinking) && (
                  <div className="flex flex-col gap-2 mb-2 text-xs">
                    {item.review_thinking && (
                      <div className="bg-orange-50 border border-orange-100 rounded px-3 py-2">
                        <div className="font-semibold text-orange-700 mb-1">💭 一审思路</div>
                        <div className="text-gray-700 leading-relaxed">
                          <ExpandableText text={item.review_thinking} maxLen={120} />
                        </div>
                      </div>
                    )}
                    {item.correct_thinking && (
                      <div className="bg-green-50 border border-green-100 rounded px-3 py-2">
                        <div className="font-semibold text-green-700 mb-1">✅ 正确思路</div>
                        <div className="text-gray-700 leading-relaxed">
                          <ExpandableText text={item.correct_thinking} maxLen={120} />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* ── 展开：后续措施 + 质培分析 ── */}
                {(item.review_action || item.qa_analysis || item.follow_up_action || item.check_data) && (
                  <>
                    <button
                      onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}
                      style={{
                        border: '1px solid #e5e7eb',
                        borderRadius: '6px',
                        padding: '3px 10px',
                        fontSize: '12px',
                        color: '#3b82f6',
                        background: '#fff',
                        marginTop: '4px',
                        cursor: 'pointer'
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f0f9ff')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = '#fff')}
                    >
                      {expandedRow === idx ? "▲ 收起" : "▼ 展开后续措施 & 质培分析"}
                    </button>

                    {expandedRow === idx && (
                      <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                        {item.review_action && (
                          <div className="bg-amber-50 border border-amber-100 rounded px-3 py-2 col-span-full">
                            <div className="font-semibold text-amber-800 mb-1">📌 后续措施</div>
                            <div className="text-gray-700 whitespace-pre-line leading-relaxed">{item.review_action}</div>
                          </div>
                        )}
                        {item.qa_analysis && (
                          <div className="bg-blue-50 border border-blue-100 rounded px-3 py-2">
                            <div className="font-semibold text-blue-800 mb-1">📋 质培侧分析</div>
                            <div className="text-gray-700 whitespace-pre-line">{item.qa_analysis}</div>
                          </div>
                        )}
                        {item.follow_up_action && (
                          <div className="bg-purple-50 border border-purple-100 rounded px-3 py-2">
                            <div className="font-semibold text-purple-800 mb-1">🎯 跟进动作</div>
                            <div className="text-gray-700 whitespace-pre-line">{item.follow_up_action}</div>
                          </div>
                        )}
                        {item.check_data && (
                          <div className="bg-yellow-50 border border-yellow-100 rounded px-3 py-2">
                            <div className="font-semibold text-yellow-800 mb-1">📊 抽检数据</div>
                            <div className="text-gray-700 whitespace-pre-line">{item.check_data}</div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
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
