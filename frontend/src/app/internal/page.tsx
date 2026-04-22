'use client';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

import { PageTemplate } from '@/components/page-template';
import { DateFilterClient } from '@/components/date-filter-client';
import { MultiFilter } from '@/components/multi-filter';
import { ExcelExporter } from '@/lib/excel-exporter';
import { useState, useEffect } from 'react';

/**
 * 🚀 内检看板 - 完整下钻功能版本
 * 
 * 功能：
 * 1. 日期筛选 - 无刷新切换
 * 2. 核心指标展示
 * 3. 数据下钻 - 折叠展开式，支持：
 *    - 队列分析：查看各队列明细数据
 *    - 审核人分析：查看审核人表现排名
 *    - 错误类型分析：查看高频错误类型
 */
export default function InternalPage() {
  const [selectedDate, setSelectedDate] = useState<string>('2026-04-01');
  const maxDate = '2026-04-22';

  // 筛选器状态
  const [showFilter, setShowFilter] = useState(false);
  const [filters, setFilters] = useState<{
    queues: string[];
    reviewers: string[];
    errorTypes: string[];
  }>({
    queues: [],
    reviewers: [],
    errorTypes: []
  });

  // 核心指标数据
  const [summaryData, setSummaryData] = useState<any>(null);

  // 下钻模块展开状态
  const [expandedModule, setExpandedModule] = useState<string | null>(null);
  
  // 各模块数据
  const [queueData, setQueueData] = useState<any[]>([]);
  const [reviewerData, setReviewerData] = useState<any[]>([]);
  const [errorTypeData, setErrorTypeData] = useState<any[]>([]);
  
  // 加载状态
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  // 导出表格数据（使用Excel工具类）
  const exportTable = (tableName: string, data: any[]) => {
    if (data.length === 0) {
      alert('没有数据可导出');
      return;
    }

    // 构建筛选条件描述
    const filterDesc = [];
    if (filters.queues.length > 0) filterDesc.push(`队列: ${filters.queues.join(', ')}`);
    if (filters.reviewers.length > 0) filterDesc.push(`审核人: ${filters.reviewers.join(', ')}`);
    if (filters.errorTypes.length > 0) filterDesc.push(`错误类型: ${filters.errorTypes.join(', ')}`);
    const filterInfo = filterDesc.length > 0 ? filterDesc.join(' | ') : undefined;

    // 准备列定义和数据
    let columns: any[] = [];
    let exportData: any[] = [];

    switch (tableName) {
      case 'queue':
        columns = [
          { key: 'rank', label: '排名' },
          { key: 'queue_name', label: '队列名称', width: 20 },
          { key: 'qa_cnt', label: '审核量', width: 12 },
          { key: 'raw_accuracy_rate', label: '正确率（%）', width: 15 },
          { key: 'misjudge_rate', label: '误判率（%）', width: 15 }
        ];
        exportData = data.map((item, index) => ({
          rank: index + 1,
          queue_name: item.queue_name,
          qa_cnt: item.qa_cnt,
          raw_accuracy_rate: item.raw_accuracy_rate?.toFixed(2),
          misjudge_rate: (100 - (item.raw_accuracy_rate || 0)).toFixed(2)
        }));
        break;

      case 'reviewer':
        columns = [
          { key: 'rank', label: '排名' },
          { key: 'reviewer_name', label: '审核人', width: 15 },
          { key: 'qa_cnt', label: '审核量', width: 12 },
          { key: 'raw_accuracy_rate', label: '正确率（%）', width: 15 },
          { key: 'misjudge_cnt', label: '误判数', width: 12 }
        ];
        exportData = data.map((item, index) => ({
          rank: index + 1,
          reviewer_name: item.reviewer_name,
          qa_cnt: item.qa_cnt,
          raw_accuracy_rate: item.raw_accuracy_rate?.toFixed(2),
          misjudge_cnt: item.misjudge_cnt || 0
        }));
        break;

      case 'error':
        columns = [
          { key: 'rank', label: '排名' },
          { key: 'label_name', label: '错误类型', width: 20 },
          { key: 'cnt', label: '错误数', width: 12 },
          { key: 'pct', label: '占比（%）', width: 12 }
        ];
        exportData = data.map((item, index) => ({
          rank: index + 1,
          label_name: item.label_name,
          cnt: item.cnt,
          pct: item.pct?.toFixed(2)
        }));
        break;
    }

    // 导出
    ExcelExporter.exportSingleSheet(
      exportData,
      columns,
      tableName,
      `${tableName}_${selectedDate}.csv`,
      filterInfo
    );
  };

  // 页面加载时自动加载所有模块数据（用于问题汇总）
  useEffect(() => {
    loadAllModulesData();
  }, [selectedDate, filters]);

  // 构建查询参数
  const buildQueryParams = () => {
    const params = new URLSearchParams();
    params.set('selected_date', selectedDate);
    
    if (filters.queues.length > 0) {
      params.set('queues', filters.queues.join(','));
    }
    if (filters.reviewers.length > 0) {
      params.set('reviewers', filters.reviewers.join(','));
    }
    if (filters.errorTypes.length > 0) {
      params.set('error_types', filters.errorTypes.join(','));
    }
    
    return params.toString();
  };

  // 加载所有模块数据
  const loadAllModulesData = async () => {
    const baseUrl = `${API_BASE}/api/v1`;
    const queryParams = buildQueryParams();
    
    try {
      // 并发加载所有数据（包括 summary）
      const [summaryRes, queueRes, reviewerRes, errorRes] = await Promise.all([
        fetch(`${baseUrl}/internal/summary?${queryParams}`),
        fetch(`${baseUrl}/internal/queues?${queryParams}`),
        fetch(`${baseUrl}/internal/reviewers?${queryParams}&limit=20`),
        fetch(`${baseUrl}/internal/error-types?${queryParams}&top_n=10`)
      ]);

      const [summaryJson, queueJson, reviewerJson, errorJson] = await Promise.all([
        summaryRes.json(),
        queueRes.json(),
        reviewerRes.json(),
        errorRes.json()
      ]);

      setSummaryData(summaryJson.data);
      setQueueData(queueJson.data?.items || []);
      setReviewerData(reviewerJson.data?.items || []);
      setErrorTypeData(errorJson.data?.items || []);
    } catch (error) {
      console.error('加载数据失败:', error);
    }
  };

  // 切换展开/收起
  const toggleModule = async (moduleName: string) => {
    if (expandedModule === moduleName) {
      setExpandedModule(null);
    } else {
      setExpandedModule(moduleName);
      // 加载数据
      await loadModuleData(moduleName);
    }
  };

  // 加载模块数据
  const loadModuleData = async (moduleName: string) => {
    setLoading({ ...loading, [moduleName]: true });
    
    try {
      const baseUrl = `${API_BASE}/api/v1`;
      
      switch (moduleName) {
        case 'queue':
          // 获取所有队列数据
          const queueRes = await fetch(`${baseUrl}/internal/queues?selected_date=${selectedDate}`);
          const queueJson = await queueRes.json();
          setQueueData(queueJson.data?.items || []);
          break;
          
        case 'reviewer':
          // 获取审核人排名
          const reviewerRes = await fetch(`${baseUrl}/internal/reviewers?selected_date=${selectedDate}&limit=20`);
          const reviewerJson = await reviewerRes.json();
          setReviewerData(reviewerJson.data?.items || []);
          break;
          
        case 'error':
          // 获取错误类型分布
          const errorRes = await fetch(`${baseUrl}/internal/error-types?selected_date=${selectedDate}&top_n=10`);
          const errorJson = await errorRes.json();
          setErrorTypeData(errorJson.data?.items || []);
          break;
      }
    } catch (error) {
      console.error(`加载${moduleName}数据失败:`, error);
    } finally {
      setLoading({ ...loading, [moduleName]: false });
    }
  };

  return (
    <PageTemplate
      title="内检看板"
      subtitle="实时监控内检质量指标，支持趋势分析和问题下钻"
    >
      {/* 日期筛选 */}
      <div className="panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 className="panel-title">📅 筛选条件</h3>
          <button
            onClick={() => setShowFilter(!showFilter)}
            className="button button-sm"
            style={{ background: showFilter ? 'var(--primary)' : 'var(--bg-secondary)', color: showFilter ? 'white' : 'var(--text)' }}
          >
            {showFilter ? '收起筛选器' : '展开筛选器'} {showFilter ? '▲' : '▼'}
          </button>
        </div>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <DateFilterClient
            initialDate={selectedDate}
            maxDate={maxDate}
            onDateChange={setSelectedDate}
          />
        </div>

        {/* 多维度筛选器（可折叠） */}
        {showFilter && (
          <div style={{ marginTop: 'var(--spacing-md)' }}>
            <MultiFilter
              queues={[
                { value: '评论_A组', label: '评论_A组', checked: filters.queues.includes('评论_A组') },
                { value: '评论_B组', label: '评论_B组', checked: filters.queues.includes('评论_B组') },
                { value: '评论_C组', label: '评论_C组', checked: filters.queues.includes('评论_C组') },
                { value: '弹幕_A组', label: '弹幕_A组', checked: filters.queues.includes('弹幕_A组') },
                { value: '弹幕_B组', label: '弹幕_B组', checked: filters.queues.includes('弹幕_B组') },
                { value: '账号_A组', label: '账号_A组', checked: filters.queues.includes('账号_A组') },
              ]}
              reviewers={[
                ...reviewerData.map(r => ({
                  value: r.reviewer_name,
                  label: r.reviewer_name,
                  checked: filters.reviewers.includes(r.reviewer_name)
                }))
              ]}
              errorTypes={[
                ...errorTypeData.map(e => ({
                  value: e.label_name,
                  label: e.label_name,
                  checked: filters.errorTypes.includes(e.label_name)
                }))
              ]}
              onApply={(newFilters) => setFilters(newFilters)}
              onReset={() => setFilters({ queues: [], reviewers: [], errorTypes: [] })}
            />
          </div>
        )}

        {/* 当前筛选条件显示 */}
        {(filters.queues.length > 0 || filters.reviewers.length > 0 || filters.errorTypes.length > 0) && (
          <div style={{ marginTop: 'var(--spacing-md)', padding: 'var(--spacing-sm)', background: 'var(--info-bg)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--info)' }}>
            <strong style={{ fontSize: '0.875em' }}>🔍 当前筛选：</strong>
            <div style={{ marginTop: '4px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
              {filters.queues.map(q => (
                <span key={q} className="filter-tag">队列: {q}</span>
              ))}
              {filters.reviewers.map(r => (
                <span key={r} className="filter-tag">审核人: {r}</span>
              ))}
              {filters.errorTypes.map(e => (
                <span key={e} className="filter-tag">错误: {e}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 核心指标 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">📊 核心指标</h3>
        
        {summaryData ? (
          <div style={{ marginTop: 'var(--spacing-lg)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            {/* 审核量 */}
            <div style={{
              background: '#fff',
              borderRadius: '12px',
              padding: '18px 20px 14px',
              border: '1px solid #e5e7eb',
              boxShadow: '0 1px 4px rgba(0,0,0,.06)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div style={{ fontSize: '12px', color: '#9ca3af', fontWeight: '500' }}>审核量</div>
              <div style={{ fontSize: '30px', fontWeight: '700', color: '#6366f1', lineHeight: '1' }}>
                {summaryData.metrics?.qa_cnt?.toLocaleString() || '0'}
              </div>
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>日期: {selectedDate}</div>
            </div>

            {/* 正确率 */}
            <div style={{
              background: '#fff',
              borderRadius: '12px',
              padding: '18px 20px 14px',
              border: '1px solid #e5e7eb',
              boxShadow: '0 1px 4px rgba(0,0,0,.06)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div style={{ fontSize: '12px', color: '#9ca3af', fontWeight: '500' }}>正确率</div>
              <div style={{ fontSize: '30px', fontWeight: '700', color: '#10b981', lineHeight: '1' }}>
                {summaryData.metrics?.raw_accuracy_rate?.toFixed(2) || '0'}%
              </div>
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                目标 ≥{summaryData.target_rate || 99.5}%
              </div>
            </div>

            {/* 错误数 */}
            <div style={{
              background: '#fff',
              borderRadius: '12px',
              padding: '18px 20px 14px',
              border: '1px solid #e5e7eb',
              boxShadow: '0 1px 4px rgba(0,0,0,.06)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div style={{ fontSize: '12px', color: '#9ca3af', fontWeight: '500' }}>错误数</div>
              <div style={{ fontSize: '30px', fontWeight: '700', color: '#ef4444', lineHeight: '1' }}>
                {summaryData.metrics?.error_count?.toLocaleString() || '0'}
              </div>
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                漏判 {summaryData.metrics?.missjudge_count || 0} / 错判 {summaryData.metrics?.misjudge_count || 0}
              </div>
            </div>

            {/* 参与人数 */}
            <div style={{
              background: '#fff',
              borderRadius: '12px',
              padding: '18px 20px 14px',
              border: '1px solid #e5e7eb',
              boxShadow: '0 1px 4px rgba(0,0,0,.06)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <div style={{ fontSize: '12px', color: '#9ca3af', fontWeight: '500' }}>参与人数</div>
              <div style={{ fontSize: '30px', fontWeight: '700', color: '#8b5cf6', lineHeight: '1' }}>
                {summaryData.metrics?.owner_count?.toLocaleString() || '0'}
              </div>
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>
                队列数 {summaryData.metrics?.queue_count || 0}
              </div>
            </div>
          </div>
        ) : (
          <div style={{ marginTop: 'var(--spacing-lg)', textAlign: 'center', padding: '48px 0', color: '#9ca3af' }}>
            加载中...
          </div>
        )}
      </div>

      {/* 问题汇总 - 新增模块 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', borderColor: 'var(--danger)', borderWidth: '2px' }}>
        <h3 className="panel-title" style={{ color: 'var(--danger)' }}>📌 重点关注问题</h3>
        
        <div style={{ marginTop: 'var(--spacing-lg)' }}>
          {/* 问题队列 */}
          <div className="problem-section">
            <div className="problem-header">
              <span className="problem-icon">🔴</span>
              <span className="problem-title">问题队列（正确率 &lt; 90%）</span>
              <button 
                className="problem-jump"
                onClick={() => {
                  setExpandedModule('queue');
                  loadModuleData('queue');
                }}
              >
                查看详情 →
              </button>
            </div>
            <div className="problem-list">
              {queueData.length === 0 && (
                <div style={{ padding: 'var(--spacing-sm)', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  暂无数据，点击"查看详情"加载队列信息
                </div>
              )}
              {queueData.filter(q => q.raw_accuracy_rate < 90).length === 0 && queueData.length > 0 && (
                <div style={{ padding: 'var(--spacing-sm)', color: 'var(--success)' }}>
                  ✅ 太棒了！所有队列正确率都 ≥ 90%
                </div>
              )}
              {queueData.filter(q => q.raw_accuracy_rate < 90).map((queue, index) => (
                <div key={index} className="problem-item">
                  <span className="problem-name">{queue.queue_name}</span>
                  <span className="problem-value danger">{queue.raw_accuracy_rate?.toFixed(2)}%</span>
                  <span className="problem-meta">审核量: {queue.qa_cnt?.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 问题审核人 */}
          <div className="problem-section" style={{ marginTop: 'var(--spacing-md)' }}>
            <div className="problem-header">
              <span className="problem-icon">🟡</span>
              <span className="problem-title">问题审核人（正确率 &lt; 85%）</span>
              <button 
                className="problem-jump"
                onClick={() => {
                  setExpandedModule('reviewer');
                  loadModuleData('reviewer');
                }}
              >
                查看详情 →
              </button>
            </div>
            <div className="problem-list">
              {reviewerData.length === 0 && (
                <div style={{ padding: 'var(--spacing-sm)', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  暂无数据，点击"查看详情"加载审核人信息
                </div>
              )}
              {reviewerData.filter(r => r.raw_accuracy_rate < 85).length === 0 && reviewerData.length > 0 && (
                <div style={{ padding: 'var(--spacing-sm)', color: 'var(--success)' }}>
                  ✅ 太棒了！所有审核人正确率都 ≥ 85%
                </div>
              )}
              {reviewerData.filter(r => r.raw_accuracy_rate < 85).map((reviewer, index) => (
                <div key={index} className="problem-item">
                  <span className="problem-name">{reviewer.reviewer_name}</span>
                  <span className="problem-value warning">{reviewer.raw_accuracy_rate?.toFixed(2)}%</span>
                  <span className="problem-meta">审核量: {reviewer.qa_cnt?.toLocaleString()} | 误判: {reviewer.misjudge_cnt || 0}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 高频错误 */}
          <div className="problem-section" style={{ marginTop: 'var(--spacing-md)' }}>
            <div className="problem-header">
              <span className="problem-icon">🎯</span>
              <span className="problem-title">高频错误类型（Top 3）</span>
              <button 
                className="problem-jump"
                onClick={() => {
                  setExpandedModule('error');
                  loadModuleData('error');
                }}
              >
                查看详情 →
              </button>
            </div>
            <div className="problem-list">
              {errorTypeData.length === 0 && (
                <div style={{ padding: 'var(--spacing-sm)', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                  暂无数据，点击"查看详情"加载错误类型信息
                </div>
              )}
              {errorTypeData.slice(0, 3).map((error, index) => (
                <div key={index} className="problem-item">
                  <span className="problem-name">#{index + 1} {error.label_name}</span>
                  <span className="problem-value neutral">{error.cnt?.toLocaleString()} 次</span>
                  <span className="problem-meta">占比: {error.pct?.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 使用提示 */}
        <div style={{ marginTop: 'var(--spacing-lg)', padding: 'var(--spacing-sm)', background: 'var(--info-bg)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--info)' }}>
          <p style={{ margin: 0, fontSize: '0.875em', color: 'var(--text)' }}>
            💡 <strong>提示：</strong>点击"查看详情"按钮可跳转到对应下钻模块，查看完整明细数据
          </p>
        </div>
      </div>

      {/* 数据下钻 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🔍 数据下钻</h3>
        
        <div style={{ marginTop: 'var(--spacing-lg)' }}>
          {/* 队列分析 */}
          <div className="drill-module">
            <button
              className="drill-header"
              onClick={() => toggleModule('queue')}
            >
              <div className="drill-info">
                <div className="drill-icon">📈</div>
                <div>
                  <div className="drill-title">队列分析</div>
                  <div className="drill-subtitle">查看各队列明细数据</div>
                </div>
              </div>
              <div className="drill-toggle">
                {expandedModule === 'queue' ? '▼' : '▶'}
              </div>
            </button>
            
            {expandedModule === 'queue' && (
              <div className="drill-content">
                {/* 导出按钮 */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--spacing-sm)' }}>
                  <button
                    onClick={() => exportTable('queue', queueData)}
                    className="button button-sm"
                    disabled={queueData.length === 0}
                  >
                    导出队列数据 ⬇
                  </button>
                </div>

                {loading.queue ? (
                  <p style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>
                    加载中...
                  </p>
                ) : queueData.length > 0 ? (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: 'var(--bg-secondary)' }}>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>排名</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>队列名称</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>审核量</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>正确率</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>误判率</th>
                        </tr>
                      </thead>
                      <tbody>
                        {queueData.map((queue, index) => (
                          <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: 'var(--spacing-sm)' }}>{index + 1}</td>
                            <td style={{ padding: 'var(--spacing-sm)' }}>{queue.queue_name}</td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{queue.qa_cnt?.toLocaleString() || 0}</td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: queue.raw_accuracy_rate >= 90 ? 'var(--success)' : 'var(--danger)' }}>
                              {queue.raw_accuracy_rate?.toFixed(2)}%
                            </td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>
                              {((100 - (queue.raw_accuracy_rate || 0))).toFixed(2)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>
                    暂无数据
                  </p>
                )}
              </div>
            )}
          </div>

          {/* 审核人分析 */}
          <div className="drill-module" style={{ marginTop: 'var(--spacing-md)' }}>
            <button
              className="drill-header"
              onClick={() => toggleModule('reviewer')}
            >
              <div className="drill-info">
                <div className="drill-icon">👥</div>
                <div>
                  <div className="drill-title">审核人分析</div>
                  <div className="drill-subtitle">查看审核人表现排名</div>
                </div>
              </div>
              <div className="drill-toggle">
                {expandedModule === 'reviewer' ? '▼' : '▶'}
              </div>
            </button>
            
            {expandedModule === 'reviewer' && (
              <div className="drill-content">
                {/* 导出按钮 */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--spacing-sm)' }}>
                  <button
                    onClick={() => exportTable('reviewer', reviewerData)}
                    className="button button-sm"
                    disabled={reviewerData.length === 0}
                  >
                    导出审核人数据 ⬇
                  </button>
                </div>

                {loading.reviewer ? (
                  <p style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>
                    加载中...
                  </p>
                ) : reviewerData.length > 0 ? (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: 'var(--bg-secondary)' }}>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>排名</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>审核人</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>审核量</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>正确率</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>误判数</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reviewerData.map((reviewer, index) => (
                          <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: 'var(--spacing-sm)' }}>{index + 1}</td>
                            <td style={{ padding: 'var(--spacing-sm)' }}>{reviewer.reviewer_name}</td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{reviewer.qa_cnt?.toLocaleString() || 0}</td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: reviewer.raw_accuracy_rate >= 85 ? 'var(--success)' : 'var(--danger)' }}>
                              {reviewer.raw_accuracy_rate?.toFixed(2)}%
                            </td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>
                              {reviewer.misjudge_cnt || 0}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>
                    暂无数据
                  </p>
                )}
              </div>
            )}
          </div>

          {/* 错误类型分析 */}
          <div className="drill-module" style={{ marginTop: 'var(--spacing-md)' }}>
            <button
              className="drill-header"
              onClick={() => toggleModule('error')}
            >
              <div className="drill-info">
                <div className="drill-icon">🎯</div>
                <div>
                  <div className="drill-title">错误类型分析</div>
                  <div className="drill-subtitle">查看高频错误类型</div>
                </div>
              </div>
              <div className="drill-toggle">
                {expandedModule === 'error' ? '▼' : '▶'}
              </div>
            </button>
            
            {expandedModule === 'error' && (
              <div className="drill-content">
                {/* 导出按钮 */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--spacing-sm)' }}>
                  <button
                    onClick={() => exportTable('error', errorTypeData)}
                    className="button button-sm"
                    disabled={errorTypeData.length === 0}
                  >
                    导出错误类型数据 ⬇
                  </button>
                </div>

                {loading.error ? (
                  <p style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>
                    加载中...
                  </p>
                ) : errorTypeData.length > 0 ? (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: 'var(--bg-secondary)' }}>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>排名</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>错误类型</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>错误数</th>
                          <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>占比</th>
                        </tr>
                      </thead>
                      <tbody>
                        {errorTypeData.map((error, index) => (
                          <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td style={{ padding: 'var(--spacing-sm)' }}>{index + 1}</td>
                            <td style={{ padding: 'var(--spacing-sm)' }}>{error.label_name}</td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{error.cnt?.toLocaleString() || 0}</td>
                            <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{error.pct?.toFixed(2)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p style={{ textAlign: 'center', padding: 'var(--spacing-lg)', color: 'var(--text-muted)' }}>
                    暂无数据
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 使用提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 使用提示</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>点击"展开筛选器"可按队列/审核人/错误类型筛选数据</li>
          <li>点击下钻模块标题展开查看明细数据</li>
          <li>每个表格右上角有"导出"按钮，可下载CSV文件</li>
          <li>切换日期或筛选条件会自动重新加载数据</li>
          <li>正确率低于阈值会以红色标注（队列≥90%，审核人≥85%）</li>
        </ul>
      </div>

      <style jsx>{`
        /* 下钻模块样式 */
        .drill-module {
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
        }

        .drill-header {
          width: 100%;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--spacing-md);
          background: var(--bg-primary);
          border: none;
          cursor: pointer;
          transition: background 0.2s;
        }

        .drill-header:hover {
          background: var(--bg-secondary);
        }

        .drill-info {
          display: flex;
          align-items: center;
          gap: var(--spacing-md);
        }

        .drill-icon {
          font-size: 2em;
        }

        .drill-title {
          font-weight: 600;
          font-size: 1.1em;
          margin-bottom: 4px;
        }

        .drill-subtitle {
          font-size: 0.875em;
          color: var(--text-muted);
        }

        .drill-toggle {
          font-size: 1.2em;
          color: var(--text-muted);
        }

        .drill-content {
          padding: var(--spacing-md);
          background: var(--bg-primary);
          border-top: 1px solid var(--border);
          animation: slideDown 0.3s ease-out;
        }

        @keyframes slideDown {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        /* 问题汇总模块样式 */
        .problem-section {
          background: var(--bg-primary);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: var(--spacing-md);
        }

        .problem-header {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
          margin-bottom: var(--spacing-md);
          padding-bottom: var(--spacing-sm);
          border-bottom: 2px solid var(--border);
        }

        .problem-icon {
          font-size: 1.2em;
        }

        .problem-title {
          font-weight: 600;
          font-size: 1em;
          flex: 1;
        }

        .problem-jump {
          padding: 4px 12px;
          background: var(--primary);
          color: white;
          border: none;
          border-radius: var(--radius);
          font-size: 0.875em;
          cursor: pointer;
          transition: background 0.2s;
        }

        .problem-jump:hover {
          background: var(--primary-dark);
          transform: translateX(2px);
        }

        .problem-list {
          display: flex;
          flex-direction: column;
          gap: var(--spacing-sm);
        }

        .problem-item {
          display: flex;
          align-items: center;
          gap: var(--spacing-md);
          padding: var(--spacing-sm);
          background: var(--bg-secondary);
          border-radius: var(--radius);
          border-left: 3px solid var(--border);
        }

        .problem-name {
          font-weight: 500;
          flex: 1;
        }

        .problem-value {
          font-weight: 600;
          font-size: 1.1em;
          min-width: 80px;
          text-align: right;
        }

        .problem-value.danger {
          color: var(--danger);
        }

        .problem-value.warning {
          color: var(--warning);
        }

        .problem-value.neutral {
          color: var(--primary);
        }

        .problem-meta {
          font-size: 0.875em;
          color: var(--text-muted);
          min-width: 150px;
          text-align: right;
        }

        /* 筛选标签样式 */
        .filter-tag {
          display: inline-block;
          padding: 2px 8px;
          background: var(--primary);
          color: white;
          border-radius: 12px;
          font-size: 0.75em;
          font-weight: 500;
        }
      `}</style>
    </PageTemplate>
  );
}
