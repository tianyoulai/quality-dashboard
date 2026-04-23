'use client';

import { PageTemplate } from '@/components/page-template';
import { useState, useEffect } from 'react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// ── 阈值常量（全站统一） ──
const REVIEWER_THRESHOLD = 95;

// ── 类型 ──
interface NewcomerSummary {
  active_count: number;
  avg_accuracy: number;
  avg_training_days: number;
  graduated_count: number;
  estimated_days_to_standard: number;
}

interface BatchItem {
  batch_id: string;
  batch_name: string;
  status: string;
  join_date: string | null;
  total_people: number;
  active_people: number;
  avg_accuracy: number;
  passed_count: number;
  pass_rate: number;
  qa_cnt: number;
  current_day: number;
  last_date: string | null;
}

interface BatchDetail {
  id: string;
  name: string;
  total_people: number;
  active_people: number;
  avg_accuracy: number;
  passed_count: number;
  pass_rate: number;
  newcomers: {
    name: string;
    team: string;
    qa_cnt: number;
    accuracy: number;
    error_cnt: number;
    days: number;
    status: string;
  }[];
}

// ── 工具 ──
function fmt(n: number | undefined | null, digits = 1) {
  if (n == null) return '—';
  return n.toFixed(digits);
}
function rateColor(rate: number): string {
  if (rate >= 97) return '#10b981';
  if (rate >= REVIEWER_THRESHOLD) return '#f59e0b';
  if (rate >= 85) return '#f97316';
  return '#ef4444';
}
function statusLabel(s: string) {
  switch (s) {
    case 'excellent': return '🌟 优秀';
    case 'normal': return '✅ 达标';
    case 'warning': return '⚠️ 预警';
    case 'problem': return '🔴 不达标';
    case 'no_data': return '⬜ 无数据';
    default: return s;
  }
}

function batchRiskLabel(batch: BatchItem) {
  if (batch.qa_cnt === 0) return { text: '待接数', color: '#9a3412', bg: '#fff7ed' };
  if (batch.pass_rate < 60) return { text: '高风险', color: '#991b1b', bg: '#fef2f2' };
  if (batch.pass_rate < 90) return { text: '需关注', color: '#92400e', bg: '#fffbeb' };
  return { text: '稳定', color: '#065f46', bg: '#ecfdf5' };
}

/**
 * 🚀 新人追踪 v3.0
 *
 * 变更：
 * - v3: 对接 /api/v1/newcomers/overview + /batches + /batch/{id}
 * - 批次列表 + 批次详情 + 未达标新人高亮
 * - 点击批次展开成员列表
 */
export default function NewcomersPage() {
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<NewcomerSummary | null>(null);
  const [hasApi, setHasApi] = useState(true);

  // 批次列表
  const [batches, setBatches] = useState<BatchItem[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<string | null>(null);
  const [batchDetail, setBatchDetail] = useState<BatchDetail | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [memberFilter, setMemberFilter] = useState<'all' | 'problem' | 'no_data'>('all');

  const selectedBatchMeta = batches.find(b => b.batch_id === selectedBatch) || null;
  const problemCount = batchDetail ? batchDetail.newcomers.filter(n => n.accuracy < REVIEWER_THRESHOLD).length : 0;
  const noDataBatchCount = batches.filter(b => b.total_people > 0 && b.qa_cnt === 0).length;
  const totalTrackedPeople = batches.reduce((sum, b) => sum + (b.total_people || 0), 0);
  const totalActivePeople = batches.reduce((sum, b) => sum + (b.active_people || 0), 0);
  const matchedPeople = totalActivePeople;
  const pendingMappedPeople = Math.max(totalTrackedPeople - totalActivePeople, 0);
  const readinessLabel = pendingMappedPeople === 0 ? '已接通' : matchedPeople > 0 ? '部分接通' : '待接通';

  const displayedMembers = batchDetail
    ? batchDetail.newcomers.filter((n) => {
        if (memberFilter === 'problem') return n.accuracy < REVIEWER_THRESHOLD;
        if (memberFilter === 'no_data') return n.qa_cnt === 0;
        return true;
      })
    : [];

  // 加载总览 + 批次列表
  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/v1/newcomers/overview`)
        .then(r => { if (!r.ok) throw new Error('no api'); return r.json(); })
        .then(d => { setSummary(d.data || d); setHasApi(true); })
        .catch(() => { setHasApi(false); setSummary(null); }),
      fetch(`${API_BASE}/api/v1/newcomers/batches?status=all`)
        .then(r => r.json())
        .then(d => {
          const list = (d.data?.batches || d.batches || []) as BatchItem[];
          const sorted = [...list].sort((a, b) => {
            const score = (x: BatchItem) => {
              if (x.qa_cnt === 0) return 0;
              if (x.pass_rate < 60) return 3;
              if (x.pass_rate < 90) return 2;
              return 1;
            };
            const diff = score(b) - score(a);
            if (diff !== 0) return diff;
            return String(b.last_date || '').localeCompare(String(a.last_date || ''));
          });
          setBatches(sorted);
          if (!selectedBatch && sorted.length > 0) {
            const preferred = sorted.find((b) => (b.qa_cnt || 0) > 0) || sorted[0];
            setSelectedBatch(preferred.batch_id);
          }
        })
        .catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  // 加载批次详情
  useEffect(() => {
    if (!selectedBatch) { setBatchDetail(null); return; }
    setBatchLoading(true);
    fetch(`${API_BASE}/api/v1/newcomers/batch/${encodeURIComponent(selectedBatch)}`)
      .then(r => r.json())
      .then(d => { setBatchDetail(d.data || d); })
      .catch(() => setBatchDetail(null))
      .finally(() => setBatchLoading(false));
  }, [selectedBatch]);

  return (
    <PageTemplate
      title="新人追踪"
      subtitle="追踪新人成长轨迹，分析培训效果和质量趋势"
    >
      {/* ═══ 指标卡 ═══ */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginBottom: 24,
      }}>
        <NewcomerCard label="在训人数" value={summary?.active_count ?? '—'}
          sub={hasApi ? (summary && summary.active_count > 0 ? `${summary.active_count}人未达标` : undefined) : '待对接'} />
        <NewcomerCard label="综合正确率" value={summary ? `${fmt(summary.avg_accuracy)}%` : '—'}
          sub={hasApi ? undefined : '待对接'}
          color={summary ? rateColor(summary.avg_accuracy) : '#374151'} />
        <NewcomerCard label="平均培训天数" value={summary?.avg_training_days ?? '—'}
          sub={hasApi ? undefined : '待对接'} />
        <NewcomerCard label="已结业人数" value={summary?.graduated_count ?? '—'}
          sub={hasApi ? (summary && summary.graduated_count > 0 ? '✅' : undefined) : '待对接'}
          color={summary && summary.graduated_count > 0 ? '#10b981' : '#374151'} />
        <NewcomerCard label="距达标天数预估"
          value={summary?.estimated_days_to_standard === -1 ? '↗ 需干预' : (summary?.estimated_days_to_standard ?? '—')}
          sub={hasApi ? (summary?.estimated_days_to_standard === -1 ? '正确率下降趋势' : summary?.estimated_days_to_standard ? '天' : undefined) : '计算字段'}
          color={summary ? (summary.estimated_days_to_standard === -1 ? '#ef4444' : summary.estimated_days_to_standard > 14 ? '#f59e0b' : '#10b981') : '#374151'} />
      </div>

      {!hasApi && (
        <div style={{
          background: '#fef3c7', border: '2px solid #f59e0b', borderRadius: 10,
          padding: '20px 24px', marginBottom: 24, textAlign: 'center',
        }}>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#92400e', marginBottom: 8 }}>
            ⚠️ 新人追踪 API 不可用
          </div>
          <div style={{ fontSize: 13, color: '#78350f' }}>
            当前页面依赖 <code style={{ background: '#fef9c3', padding: '2px 6px', borderRadius: 4 }}>/api/v1/newcomers/overview</code> 等接口。
          </div>
        </div>
      )}

      {/* ═══ 数据健康提示 ═══ */}
      {hasApi && noDataBatchCount > 0 && (
        <div style={{
          background: '#fff7ed', border: '1px solid #fdba74', borderRadius: 10,
          padding: '14px 16px', marginBottom: 20,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#9a3412', marginBottom: 6 }}>
            ⚠️ 数据健康提示
          </div>
          <div style={{ fontSize: 12, color: '#7c2d12', lineHeight: 1.7 }}>
            当前共有 <strong>{noDataBatchCount}</strong> 个批次存在“名单已建但质检数据未匹配”的情况。
            这会导致该批次在新人追踪页面显示为 <strong>0 质检量 / 0 正确率</strong>，不代表页面故障，通常是
            <strong> dim_newcomer_batch 与 fact_newcomer_qa 的姓名还未对齐</strong>。
          </div>
        </div>
      )}

      {/* ═══ 页面级综合评估 ═══ */}
      <div style={{
        background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb',
        padding: '16px 18px', marginBottom: 20,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>页面级综合评估</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#111827' }}>新人追踪数据状态：{readinessLabel}</div>
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6, lineHeight: 1.7 }}>
              已接通 <strong>{matchedPeople}</strong> 人，待补映射 <strong>{pendingMappedPeople}</strong> 人。
              当前页面适合做 <strong>功能展示 / 已接通批次分析</strong>，暂不适合做 <strong>完整批次经营判断</strong>。
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ padding: '6px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600, color: '#1d4ed8', background: '#eff6ff' }}>
              接口稳定
            </span>
            <span style={{ padding: '6px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600, color: pendingMappedPeople > 0 ? '#9a3412' : '#065f46', background: pendingMappedPeople > 0 ? '#fff7ed' : '#ecfdf5' }}>
              {pendingMappedPeople > 0 ? '数据待补齐' : '数据完整'}
            </span>
          </div>
        </div>
      </div>

      {/* ═══ 当前批次摘要 ═══ */}
      {selectedBatchMeta && (
        <div style={{
          background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb',
          padding: '16px 18px', marginBottom: 20,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 6 }}>当前批次概览</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#111827' }}>{selectedBatchMeta.batch_name}</div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
                共 {selectedBatchMeta.total_people} 人｜活跃 {selectedBatchMeta.active_people} 人｜质检量 {selectedBatchMeta.qa_cnt}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{
                padding: '6px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600,
                color: batchRiskLabel(selectedBatchMeta).color, background: batchRiskLabel(selectedBatchMeta).bg,
              }}>
                {batchRiskLabel(selectedBatchMeta).text}
              </span>
              {selectedBatchMeta.last_date && (
                <span style={{ fontSize: 12, color: '#6b7280' }}>最近数据日期：{selectedBatchMeta.last_date}</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ 批次列表 ═══ */}
      <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', marginBottom: 24 }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #f3f4f6', background: '#f9fafb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#374151' }}>📦 批次列表</span>
          <span style={{ fontSize: 12, color: '#9ca3af' }}>共 {batches.length} 个批次</span>
        </div>
        {batches.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af', fontSize: 13 }}>
            {loading ? '加载中...' : '暂无批次数据'}
          </div>
        ) : (
          <div style={{ padding: '12px 16px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                  <th style={{ textAlign: 'left', padding: '8px 10px', color: '#6b7280' }}>批次</th>
                  <th style={{ textAlign: 'center', padding: '8px 10px', color: '#6b7280' }}>状态</th>
                  <th style={{ textAlign: 'right', padding: '8px 10px', color: '#6b7280' }}>人数</th>
                  <th style={{ textAlign: 'right', padding: '8px 10px', color: '#6b7280' }}>在训天数</th>
                  <th style={{ textAlign: 'right', padding: '8px 10px', color: '#6b7280' }}>正确率</th>
                  <th style={{ textAlign: 'right', padding: '8px 10px', color: '#6b7280' }}>达标率</th>
                  <th style={{ textAlign: 'center', padding: '8px 10px', color: '#6b7280' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b, i) => (
                  <tr key={b.batch_id} style={{
                    borderBottom: '1px solid #f3f4f6',
                    background: selectedBatch === b.batch_id ? '#f0f9ff' : 'transparent',
                  }}>
                    <td style={{ padding: '8px 10px', fontWeight: 500 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span>{b.batch_name}</span>
                        <span style={{
                          padding: '2px 8px', borderRadius: 999, fontSize: 11, fontWeight: 600,
                          color: batchRiskLabel(b).color, background: batchRiskLabel(b).bg,
                        }}>
                          {batchRiskLabel(b).text}
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: 10, fontSize: 12,
                        background: b.status === 'training' ? '#fef3c7' : '#d1fae5',
                        color: b.status === 'training' ? '#92400e' : '#065f46',
                      }}>
                        {b.status === 'training' ? '培训中' : '已结业'}
                      </span>
                    </td>
                    <td style={{ padding: '8px 10px', textAlign: 'right' }}>{b.total_people}</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right' }}>{b.current_day}天</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: rateColor(b.avg_accuracy) }}>
                      {fmt(b.avg_accuracy)}%
                    </td>
                    <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                      {fmt(b.pass_rate)}%
                      <span style={{ fontSize: 11, color: '#9ca3af' }}> ({b.passed_count}/{b.total_people})</span>
                    </td>
                    <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                      <button onClick={() => setSelectedBatch(selectedBatch === b.batch_id ? null : b.batch_id)}
                        style={{
                          padding: '4px 12px', borderRadius: 6, fontSize: 12,
                          background: selectedBatch === b.batch_id ? '#8B5CF6' : '#f3f4f6',
                          color: selectedBatch === b.batch_id ? '#fff' : '#374151',
                          border: 'none', cursor: 'pointer', fontWeight: 500,
                        }}>
                        {selectedBatch === b.batch_id ? '收起' : '查看'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ═══ 批次详情 ═══ */}
      {selectedBatch && (
        <div style={{ background: '#fff', borderRadius: 10, border: '2px solid #8B5CF6', marginBottom: 24 }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #e5e7eb', background: '#faf5ff', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: '#6d28d9' }}>
              👥 {batchDetail?.name || '加载中...'}
            </span>
            <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#6b7280' }}>
              {batchDetail && (
                <>
                  <span>总人数: <strong>{batchDetail.total_people}</strong></span>
                  <span>平均正确率: <strong style={{ color: rateColor(batchDetail.avg_accuracy) }}>{fmt(batchDetail.avg_accuracy)}%</strong></span>
                  <span>达标率: <strong>{fmt(batchDetail.pass_rate)}%</strong></span>
                </>
              )}
            </div>
          </div>
          {batchLoading ? (
            <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>加载中...</div>
          ) : batchDetail && batchDetail.newcomers.length > 0 ? (
            <div style={{ padding: '12px 16px', overflowX: 'auto' }}>
              {selectedBatchMeta?.qa_cnt === 0 && (
                <div style={{
                  marginBottom: 12, padding: '10px 12px', borderRadius: 8,
                  background: '#faf5ff', border: '1px solid #ddd6fe',
                  fontSize: 12, color: '#6d28d9',
                }}>
                  当前批次成员名单已存在，但暂未匹配到对应质检记录。成员会先展示为“无数据”，待后续姓名映射补齐后即可恢复真实表现。
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
                <div style={{ fontSize: 12, color: '#6b7280' }}>
                  当前展示 <strong>{displayedMembers.length}</strong> / {batchDetail.newcomers.length} 人
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {[
                    { key: 'all', label: '全部成员' },
                    { key: 'problem', label: '仅未达标' },
                    { key: 'no_data', label: '仅无数据' },
                  ].map((item) => (
                    <button
                      key={item.key}
                      onClick={() => setMemberFilter(item.key as 'all' | 'problem' | 'no_data')}
                      style={{
                        padding: '6px 10px', borderRadius: 999, fontSize: 12, fontWeight: 600,
                        border: '1px solid ' + (memberFilter === item.key ? '#8B5CF6' : '#e5e7eb'),
                        background: memberFilter === item.key ? '#f5f3ff' : '#fff',
                        color: memberFilter === item.key ? '#6d28d9' : '#6b7280',
                        cursor: 'pointer',
                      }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                    <th style={{ textAlign: 'left', padding: '8px 10px', color: '#6b7280' }}>姓名</th>
                    <th style={{ textAlign: 'left', padding: '8px 10px', color: '#6b7280' }}>状态</th>
                    <th style={{ textAlign: 'right', padding: '8px 10px', color: '#6b7280' }}>质检量</th>
                    <th style={{ textAlign: 'right', padding: '8px 10px', color: '#6b7280' }}>正确率</th>
                    <th style={{ textAlign: 'right', padding: '8px 10px', color: '#6b7280' }}>错误数</th>
                    <th style={{ textAlign: 'right', padding: '8px 10px', color: '#6b7280' }}>在训天数</th>
                    <th style={{ width: 100, padding: '8px 10px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {displayedMembers.map((n, i) => (
                    <tr key={i} style={{
                      borderBottom: '1px solid #f3f4f6',
                      background: n.status === 'problem' ? '#fef2f2' : n.status === 'warning' ? '#fffbeb' : 'transparent',
                    }}>
                      <td style={{ padding: '8px 10px', fontWeight: 500 }}>
                        <Link href={`/details?reviewer=${encodeURIComponent(n.name)}`} style={{ color: '#374151', textDecoration: 'none' }}>
                          {n.name}
                        </Link>
                      </td>
                      <td style={{ padding: '8px 10px' }}>{statusLabel(n.status)}</td>
                      <td style={{ padding: '8px 10px', textAlign: 'right' }}>{n.qa_cnt}</td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', fontWeight: 600, color: rateColor(n.accuracy) }}>
                        {fmt(n.accuracy)}%
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'right', color: n.error_cnt > 0 ? '#ef4444' : '#9ca3af' }}>
                        {n.error_cnt}
                      </td>
                      <td style={{ padding: '8px 10px', textAlign: 'right' }}>{n.days}天</td>
                      <td style={{ padding: '8px 10px' }}>
                        <div style={{ height: 6, background: '#f3f4f6', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: `${Math.max(n.accuracy, 0)}%`, height: '100%', background: rateColor(n.accuracy), borderRadius: 3 }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>暂无成员数据</div>
          )}
        </div>
      )}

      {/* ═══ 快速功能区（真实数据） ═══ */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '18px 16px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 8 }}>👥 当前选中批次</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#374151', lineHeight: 1.2 }}>
            {selectedBatchMeta ? selectedBatchMeta.batch_name : '未选择'}
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
            {selectedBatchMeta ? `${selectedBatchMeta.total_people}人｜在训${selectedBatchMeta.current_day}天` : '先从上方批次列表选择一个批次'}
          </div>
        </div>

        <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '18px 16px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 8 }}>🔴 未达标人数</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: problemCount > 0 ? '#ef4444' : '#10b981', lineHeight: 1.1 }}>
            {selectedBatchMeta ? problemCount : '—'}
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
            {selectedBatchMeta ? `正确率 < ${REVIEWER_THRESHOLD}%` : '选择批次后自动统计'}
          </div>
        </div>

        <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '18px 16px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 8 }}>📦 已追踪总人数</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#6366f1', lineHeight: 1.1 }}>
            {totalTrackedPeople}
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
            活跃有数据 {totalActivePeople} 人
          </div>
        </div>

        <div style={{ background: '#fff', borderRadius: 10, border: '1px solid #e5e7eb', padding: '18px 16px' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', marginBottom: 8 }}>📊 进一步分析</div>
          <div style={{ marginTop: 4 }}>
            <Link href="/analysis?tab=dimension" style={{ color: '#8B5CF6', textDecoration: 'none', fontSize: 14, fontWeight: 600 }}>
              前往维度交叉分析 →
            </Link>
          </div>
          <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 6 }}>
            查看新人 × 队列 × 错误类型
          </div>
        </div>
      </div>
    </PageTemplate>
  );
}

// ── 子组件 ──

function NewcomerCard({
  label, value, sub, color = '#374151',
}: {
  label: string; value: string | number; sub?: string; color?: string;
}) {
  return (
    <div style={{
      background: '#fff', borderRadius: 12, padding: '16px 18px 12px',
      border: `1px solid #e5e7eb`, boxShadow: '0 1px 4px rgba(0,0,0,.05)',
      display: 'flex', flexDirection: 'column', gap: 3,
    }}>
      <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 12, color: '#f59e0b' }}>{sub}</div>}
    </div>
  );
}
