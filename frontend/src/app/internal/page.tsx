'use client';

import { PageTemplate } from '@/components/page-template';
import { DateFilterClient } from '@/components/date-filter-client';
import { SummaryCard } from '@/components/summary-card';
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

  // 下钻模块展开状态
  const [expandedModule, setExpandedModule] = useState<string | null>(null);
  
  // 各模块数据
  const [queueData, setQueueData] = useState<any[]>([]);
  const [reviewerData, setReviewerData] = useState<any[]>([]);
  const [errorTypeData, setErrorTypeData] = useState<any[]>([]);
  
  // 加载状态
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  // 页面加载时自动加载所有模块数据（用于问题汇总）
  useEffect(() => {
    loadAllModulesData();
  }, [selectedDate]);

  // 加载所有模块数据
  const loadAllModulesData = async () => {
    const baseUrl = 'http://localhost:8000/api/v1';
    
    try {
      // 并发加载所有数据
      const [queueRes, reviewerRes, errorRes] = await Promise.all([
        fetch(`${baseUrl}/internal/queues?selected_date=${selectedDate}`),
        fetch(`${baseUrl}/internal/reviewers?selected_date=${selectedDate}&limit=20`),
        fetch(`${baseUrl}/internal/error-types?selected_date=${selectedDate}&top_n=10`)
      ]);

      const [queueJson, reviewerJson, errorJson] = await Promise.all([
        queueRes.json(),
        reviewerRes.json(),
        errorRes.json()
      ]);

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
      const baseUrl = 'http://localhost:8000/api/v1';
      
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
        <h3 className="panel-title">📅 日期筛选</h3>
        <DateFilterClient
          initialDate={selectedDate}
          maxDate={maxDate}
          onDateChange={setSelectedDate}
        />
      </div>

      {/* 核心指标 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">📊 核心指标</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="审核量"
            value="39,140"
            hint={`日期: ${selectedDate}`}
            tone="neutral"
          />

          <SummaryCard
            label="正确率"
            value="99.35%"
            hint="目标 ≥90%"
            tone="success"
          />

          <SummaryCard
            label="误判率"
            value="0.27%"
            hint="目标 ≤5%"
            tone="success"
          />

          <SummaryCard
            label="参与人数"
            value="42"
            hint="在线 38 人"
            tone="neutral"
          />
        </div>
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
          <li>点击下钻模块标题展开查看明细数据</li>
          <li>再次点击可收起模块</li>
          <li>切换日期会自动重新加载展开的模块</li>
          <li>正确率低于阈值会以红色标注</li>
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
      `}</style>
    </PageTemplate>
  );
}
