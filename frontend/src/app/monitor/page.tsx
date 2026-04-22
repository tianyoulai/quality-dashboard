'use client';

import { PageTemplate } from '@/components/page-template';
import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8002';

interface MetaData {
  groups: string[];
  queues: string[];
}

interface QueueRanking {
  group_name: string;
  queue_name: string;
  total_count: number;
  correct_rate: number;
  misjudge_rate: number;
  missjudge_rate: number;
  misjudge_cnt: number;
  missjudge_cnt: number;
  appeal_reverse_rate: number;
  reviewer_cnt: number;
  needs_attention: boolean;
}

interface ReviewerRanking {
  reviewer_name: string;
  group_name: string;
  queue_name: string;
  review_count: number;
  correct_rate: number;
  misjudge_rate: number;
  missjudge_rate: number;
  misjudge_cnt: number;
  missjudge_cnt: number;
  needs_attention: boolean;
}

/**
 * 📊 实时监控页面
 * 
 * 功能：
 * 1. 队列正确率排名（阈值 99%）
 * 2. 审核人正确率排名（阈值 95%）
 * 3. 错判vs漏判柱状图
 */
export default function MonitorPage() {
  const [date, setDate] = useState('2026-04-21');
  const [groupName, setGroupName] = useState('全部');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [metaData, setMetaData] = useState<MetaData | null>(null);
  const [queueData, setQueueData] = useState<QueueRanking[]>([]);
  const [reviewerData, setReviewerData] = useState<ReviewerRanking[]>([]);
  const [showAllReviewers, setShowAllReviewers] = useState(false);

  // 加载组别元数据
  useEffect(() => {
    loadMetaData();
  }, [date]);

  async function loadMetaData() {
    try {
      const response = await fetch(`${API_BASE}/api/v1/monitor/meta?date=${date}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setMetaData(data);
    } catch (err) {
      console.error('加载元数据失败:', err);
      setMetaData({ groups: [], queues: [] });
    }
  }

  async function handleQuery() {
    setLoading(true);
    setError(null);
    
    try {
      const groupParam = groupName === '全部' ? '' : groupName;
      
      // 并行请求队列和人员排名
      const [queueRes, reviewerRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/monitor/queue-ranking?date=${date}&group_name=${groupParam}&limit=50`),
        fetch(`${API_BASE}/api/v1/monitor/reviewer-ranking?date=${date}&group_name=${groupParam}&limit=200`)
      ]);

      if (!queueRes.ok || !reviewerRes.ok) {
        throw new Error('API请求失败');
      }

      const queueJson = await queueRes.json();
      const reviewerJson = await reviewerRes.json();

      setQueueData(Array.isArray(queueJson) ? queueJson : []);
      setReviewerData(Array.isArray(reviewerJson) ? reviewerJson : []);
    } catch (err) {
      console.error('查询失败:', err);
      setError(err instanceof Error ? err.message : '未知错误');
      setQueueData([]);
      setReviewerData([]);
    } finally {
      setLoading(false);
    }
  }

  // 筛选需要展示的审核人
  const displayedReviewers = showAllReviewers
    ? reviewerData
    : reviewerData.filter(r => r.needs_attention);

  // 获取需要关注的队列（用于柱状图）
  const problemQueues = queueData
    .filter(q => q.needs_attention)
    .slice(0, 10);

  return (
    <PageTemplate
      title="实时监控"
      subtitle="队列与人员正确率排名"
      actions={
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="input"
            style={{ width: '160px' }}
          />
          <select
            value={groupName}
            onChange={(e) => setGroupName(e.target.value)}
            className="input"
            style={{ width: '180px' }}
          >
            <option value="全部">全部</option>
            {metaData?.groups.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          <button onClick={handleQuery} className="button" disabled={loading}>
            {loading ? '查询中...' : '查询'}
          </button>
        </div>
      }
    >
      {error && (
        <div className="panel" style={{ background: 'var(--danger-bg)', borderColor: 'var(--danger)', marginBottom: 24 }}>
          <p style={{ color: 'var(--danger)' }}>❌ {error}</p>
        </div>
      )}

      {/* 队列正确率排名 */}
      <div className="panel" style={{ marginBottom: 32 }}>
        <h3 className="panel-title">📋 队列正确率排名</h3>
        <p style={{ fontSize: 14, color: 'var(--text-muted)', marginTop: 8, marginBottom: 16 }}>
          阈值说明：正确率 &lt; 99% 标红预警
        </p>

        {queueData.length === 0 ? (
          <p style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
            {loading ? '加载中...' : '暂无数据，请点击查询'}
          </p>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', minWidth: 800 }}>
                <thead>
                  <tr>
                    <th style={{ width: 60 }}>排名</th>
                    <th>组别</th>
                    <th>队列名称</th>
                    <th style={{ textAlign: 'right' }}>抽检量</th>
                    <th style={{ textAlign: 'right' }}>正确率</th>
                    <th style={{ textAlign: 'right' }}>错判率</th>
                    <th style={{ textAlign: 'right' }}>漏判率</th>
                    <th style={{ textAlign: 'right' }}>申诉改判率</th>
                    <th style={{ textAlign: 'right' }}>审核人数</th>
                  </tr>
                </thead>
                <tbody>
                  {queueData.map((item, index) => (
                    <tr
                      key={index}
                      style={{
                        backgroundColor: item.needs_attention ? 'var(--danger-bg)' : undefined
                      }}
                    >
                      <td style={{ textAlign: 'center' }}>{index + 1}</td>
                      <td>{item.group_name}</td>
                      <td>{item.queue_name}</td>
                      <td style={{ textAlign: 'right' }}>{item.total_count.toLocaleString()}</td>
                      <td style={{
                        textAlign: 'right',
                        fontWeight: 'bold',
                        color: item.correct_rate < 99 ? 'var(--danger)' : 'var(--success)'
                      }}>
                        {item.correct_rate.toFixed(2)}%
                      </td>
                      <td style={{ textAlign: 'right' }}>{item.misjudge_rate.toFixed(2)}%</td>
                      <td style={{ textAlign: 'right' }}>{item.missjudge_rate.toFixed(2)}%</td>
                      <td style={{ textAlign: 'right' }}>{item.appeal_reverse_rate.toFixed(2)}%</td>
                      <td style={{ textAlign: 'right' }}>{item.reviewer_cnt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 错判vs漏判柱状图 */}
            {problemQueues.length > 0 && (
              <div style={{ marginTop: 32, padding: 24, background: 'var(--card-bg)', borderRadius: 8 }}>
                <h4 style={{ marginBottom: 16, fontSize: 16, fontWeight: 600 }}>
                  ⚠️ 问题队列：错判 vs 漏判对比
                </h4>
                <BarChart data={problemQueues} />
              </div>
            )}
          </>
        )}
      </div>

      {/* 审核人正确率 */}
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <h3 className="panel-title">👤 审核人正确率</h3>
            <p style={{ fontSize: 14, color: 'var(--text-muted)', marginTop: 8 }}>
              阈值说明：正确率 &lt; 95% 标红预警
            </p>
          </div>
          <button
            onClick={() => setShowAllReviewers(!showAllReviewers)}
            className="button"
            style={{ fontSize: 14, padding: '8px 16px' }}
          >
            {showAllReviewers ? '只看问题人员' : '显示全部'}
          </button>
        </div>

        {reviewerData.length === 0 ? (
          <p style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
            {loading ? '加载中...' : '暂无数据，请点击查询'}
          </p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', minWidth: 800 }}>
              <thead>
                <tr>
                  <th style={{ width: 60 }}>排名</th>
                  <th>姓名</th>
                  <th>组别</th>
                  <th>队列</th>
                  <th style={{ textAlign: 'right' }}>审核量</th>
                  <th style={{ textAlign: 'right' }}>正确率</th>
                  <th style={{ textAlign: 'right' }}>错判数</th>
                  <th style={{ textAlign: 'right' }}>漏判数</th>
                </tr>
              </thead>
              <tbody>
                {displayedReviewers.map((item, index) => (
                  <tr
                    key={index}
                    style={{
                      backgroundColor: item.needs_attention ? 'var(--danger-bg)' : undefined
                    }}
                  >
                    <td style={{ textAlign: 'center' }}>{index + 1}</td>
                    <td>{item.reviewer_name}</td>
                    <td>{item.group_name}</td>
                    <td>{item.queue_name}</td>
                    <td style={{ textAlign: 'right' }}>{item.review_count.toLocaleString()}</td>
                    <td style={{
                      textAlign: 'right',
                      fontWeight: 'bold',
                      color: item.correct_rate < 95 ? 'var(--danger)' : undefined
                    }}>
                      {item.correct_rate.toFixed(2)}%
                    </td>
                    <td style={{ textAlign: 'right' }}>{item.misjudge_cnt}</td>
                    <td style={{ textAlign: 'right' }}>{item.missjudge_cnt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!showAllReviewers && displayedReviewers.length === 0 && (
              <p style={{ textAlign: 'center', padding: 32, color: 'var(--success)' }}>
                ✅ 暂无问题人员（所有审核人正确率 ≥ 95%）
              </p>
            )}
          </div>
        )}
      </div>
    </PageTemplate>
  );
}

/**
 * 简单柱状图组件（纯 CSS 实现）
 */
function BarChart({ data }: { data: QueueRanking[] }) {
  if (data.length === 0) return null;

  const maxValue = Math.max(
    ...data.map(d => Math.max(d.misjudge_cnt, d.missjudge_cnt))
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {data.map((item, index) => {
        const misjudgeHeight = (item.misjudge_cnt / maxValue) * 100;
        const missjudgeHeight = (item.missjudge_cnt / maxValue) * 100;

        return (
          <div key={index} style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
            <div style={{ width: 150, fontSize: 13, color: 'var(--text-primary)', flexShrink: 0 }}>
              {item.queue_name}
            </div>
            <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: 8, height: 120 }}>
              {/* 错判柱 */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center' }}>
                <div style={{ fontSize: 12, marginBottom: 4, color: '#3b82f6' }}>
                  {item.misjudge_cnt}
                </div>
                <div
                  style={{
                    width: '100%',
                    height: `${misjudgeHeight}%`,
                    minHeight: 4,
                    backgroundColor: '#3b82f6',
                    borderRadius: '4px 4px 0 0',
                    transition: 'height 0.3s ease'
                  }}
                />
              </div>
              {/* 漏判柱 */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center' }}>
                <div style={{ fontSize: 12, marginBottom: 4, color: '#f97316' }}>
                  {item.missjudge_cnt}
                </div>
                <div
                  style={{
                    width: '100%',
                    height: `${missjudgeHeight}%`,
                    minHeight: 4,
                    backgroundColor: '#f97316',
                    borderRadius: '4px 4px 0 0',
                    transition: 'height 0.3s ease'
                  }}
                />
              </div>
            </div>
          </div>
        );
      })}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginTop: 16, fontSize: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 16, height: 16, backgroundColor: '#3b82f6', borderRadius: 2 }} />
          <span>错判数</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 16, height: 16, backgroundColor: '#f97316', borderRadius: 2 }} />
          <span>漏判数</span>
        </div>
      </div>
    </div>
  );
}
