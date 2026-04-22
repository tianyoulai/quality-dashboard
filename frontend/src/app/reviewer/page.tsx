'use client';

import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import { useState, useEffect } from 'react';

/**
 * 审核人个人视图
 * 
 * 功能：
 * 1. 搜索/选择审核人
 * 2. 个人核心指标展示
 * 3. 与团队对比
 * 4. 错误分布分析
 * 5. 趋势图（7天/14天/30天）
 * 6. 问题案例列表
 */
export default function ReviewerPage() {
  const [reviewerName, setReviewerName] = useState<string>('');
  const [reviewerData, setReviewerData] = useState<any>(null);
  const [compareData, setCompareData] = useState<any>(null);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [errorData, setErrorData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string>('2026-04-01');
  const [trendDays, setTrendDays] = useState<number>(7);

  // 搜索审核人
  const searchReviewer = async () => {
    if (!reviewerName.trim()) {
      alert('请输入审核人姓名');
      return;
    }

    setLoading(true);
    try {
      // TODO: 替换为真实API
      // const res = await fetch(`/api/v1/reviewer/profile?name=${reviewerName}&date=${selectedDate}`);
      // const data = await res.json();
      
      // 模拟数据
      const mockData = {
        name: reviewerName,
        queue: '评论_A组',
        stats: {
          auditCount: 1234,
          correctCount: 1180,
          accuracy: 95.6,
          misjudgeCount: 54,
          rank: 12,
          totalReviewers: 45
        },
        teamAvg: {
          auditCount: 980,
          accuracy: 93.2,
          misjudgeCount: 67
        },
        errors: [
          { type: '引流判定', count: 23, pct: 42.6 },
          { type: '重要消息', count: 15, pct: 27.8 },
          { type: '低质导流', count: 10, pct: 18.5 },
          { type: '其他', count: 6, pct: 11.1 }
        ],
        trend: [
          { date: '2026-03-26', accuracy: 94.2, auditCount: 1150 },
          { date: '2026-03-27', accuracy: 93.8, auditCount: 1180 },
          { date: '2026-03-28', accuracy: 95.1, auditCount: 1200 },
          { date: '2026-03-29', accuracy: 94.7, auditCount: 1190 },
          { date: '2026-03-30', accuracy: 95.3, auditCount: 1210 },
          { date: '2026-03-31', accuracy: 95.8, auditCount: 1220 },
          { date: '2026-04-01', accuracy: 95.6, auditCount: 1234 }
        ]
      };
      
      setReviewerData(mockData.stats);
      setCompareData(mockData.teamAvg);
      setErrorData(mockData.errors);
      setTrendData(mockData.trend);
    } catch (error) {
      console.error('加载审核人数据失败:', error);
      alert('加载失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 导出个人报告
  const exportReport = () => {
    if (!reviewerData) {
      alert('请先搜索审核人');
      return;
    }

    // TODO: 实现导出功能
    alert('导出功能开发中...');
  };

  return (
    <PageTemplate
      title="👤 审核人个人视图"
      subtitle="查看个人表现，对比团队平均，精准定位问题"
    >
      {/* 搜索区域 */}
      <div className="panel">
        <h3 className="panel-title">🔍 搜索审核人</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)', display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center' }}>
          <input
            type="text"
            className="input"
            placeholder="输入审核人姓名..."
            value={reviewerName}
            onChange={(e) => setReviewerName(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && searchReviewer()}
            style={{ flex: 1, maxWidth: '400px' }}
          />
          <button
            onClick={searchReviewer}
            className="button"
            disabled={loading}
            style={{ minWidth: '100px' }}
          >
            {loading ? '搜索中...' : '搜索'}
          </button>
          {reviewerData && (
            <button
              onClick={exportReport}
              className="button button-secondary"
            >
              导出报告 ⬇
            </button>
          )}
        </div>

        {/* 快捷搜索示例（可选） */}
        <div style={{ marginTop: 'var(--spacing-sm)', fontSize: '0.875em', color: 'var(--text-muted)' }}>
          提示: 输入姓名后按Enter或点击搜索按钮
        </div>
      </div>

      {/* 加载状态 */}
      {loading && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)', textAlign: 'center', padding: 'var(--spacing-xl)' }}>
          <div style={{ fontSize: '2em', marginBottom: 'var(--spacing-sm)' }}>🔄</div>
          <div>正在加载数据...</div>
        </div>
      )}

      {/* 未搜索状态 */}
      {!loading && !reviewerData && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)', textAlign: 'center', padding: 'var(--spacing-xl)' }}>
          <div style={{ fontSize: '4em', marginBottom: 'var(--spacing-md)' }}>🔍</div>
          <h3 style={{ marginBottom: 'var(--spacing-sm)' }}>开始搜索审核人</h3>
          <p style={{ color: 'var(--text-muted)' }}>
            输入审核人姓名，查看个人表现和分析报告
          </p>
        </div>
      )}

      {/* 个人数据展示 */}
      {!loading && reviewerData && (
        <>
          {/* 个人核心指标 */}
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <h3 className="panel-title">📊 个人核心指标（{selectedDate}）</h3>
            
            <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
              <SummaryCard
                label="审核量"
                value={reviewerData.auditCount?.toLocaleString() || '0'}
                hint={`团队平均: ${compareData?.auditCount?.toLocaleString() || 0}`}
                tone={reviewerData.auditCount > compareData.auditCount ? 'success' : 'neutral'}
              />

              <SummaryCard
                label="正确率"
                value={`${reviewerData.accuracy?.toFixed(1)}%`}
                hint={`团队平均: ${compareData?.accuracy?.toFixed(1)}%`}
                tone={reviewerData.accuracy >= 90 ? 'success' : reviewerData.accuracy >= 85 ? 'warning' : 'danger'}
              />

              <SummaryCard
                label="误判数"
                value={reviewerData.misjudgeCount?.toString() || '0'}
                hint={`团队平均: ${compareData?.misjudgeCount || 0}`}
                tone={reviewerData.misjudgeCount < compareData.misjudgeCount ? 'success' : 'warning'}
              />

              <SummaryCard
                label="团队排名"
                value={`${reviewerData.rank}/${reviewerData.totalReviewers}`}
                hint={`前 ${((reviewerData.rank / reviewerData.totalReviewers) * 100).toFixed(0)}%`}
                tone={reviewerData.rank <= reviewerData.totalReviewers / 3 ? 'success' : 'neutral'}
              />
            </div>
          </div>

          {/* 与团队对比 */}
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <h3 className="panel-title">📈 与团队对比</h3>
            
            <div style={{ marginTop: 'var(--spacing-lg)' }}>
              {/* 审核量对比 */}
              <div style={{ marginBottom: 'var(--spacing-lg)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-xs)' }}>
                  <span style={{ fontWeight: 500 }}>审核量</span>
                  <span style={{ color: reviewerData.auditCount > compareData.auditCount ? 'var(--success)' : 'var(--text-muted)' }}>
                    {reviewerData.auditCount > compareData.auditCount ? '↑' : '↓'} 
                    {Math.abs(reviewerData.auditCount - compareData.auditCount).toLocaleString()}
                    （{((reviewerData.auditCount / compareData.auditCount - 1) * 100).toFixed(1)}%）
                  </span>
                </div>
                <div style={{ background: 'var(--bg-secondary)', height: '20px', borderRadius: 'var(--radius)', overflow: 'hidden', position: 'relative' }}>
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${Math.min(100, (compareData.auditCount / Math.max(reviewerData.auditCount, compareData.auditCount)) * 100)}%`,
                    background: 'var(--text-muted)',
                    opacity: 0.3
                  }} />
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${Math.min(100, (reviewerData.auditCount / Math.max(reviewerData.auditCount, compareData.auditCount)) * 100)}%`,
                    background: 'var(--primary)'
                  }} />
                </div>
              </div>

              {/* 正确率对比 */}
              <div style={{ marginBottom: 'var(--spacing-lg)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-xs)' }}>
                  <span style={{ fontWeight: 500 }}>正确率</span>
                  <span style={{ color: reviewerData.accuracy > compareData.accuracy ? 'var(--success)' : 'var(--danger)' }}>
                    {reviewerData.accuracy > compareData.accuracy ? '↑' : '↓'} 
                    {Math.abs(reviewerData.accuracy - compareData.accuracy).toFixed(1)}%
                  </span>
                </div>
                <div style={{ background: 'var(--bg-secondary)', height: '20px', borderRadius: 'var(--radius)', overflow: 'hidden', position: 'relative' }}>
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${compareData.accuracy}%`,
                    background: 'var(--text-muted)',
                    opacity: 0.3
                  }} />
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${reviewerData.accuracy}%`,
                    background: reviewerData.accuracy >= 90 ? 'var(--success)' : 'var(--danger)'
                  }} />
                </div>
              </div>

              {/* 误判数对比 */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-xs)' }}>
                  <span style={{ fontWeight: 500 }}>误判数</span>
                  <span style={{ color: reviewerData.misjudgeCount < compareData.misjudgeCount ? 'var(--success)' : 'var(--warning)' }}>
                    {reviewerData.misjudgeCount < compareData.misjudgeCount ? '↓' : '↑'} 
                    {Math.abs(reviewerData.misjudgeCount - compareData.misjudgeCount)}
                  </span>
                </div>
                <div style={{ background: 'var(--bg-secondary)', height: '20px', borderRadius: 'var(--radius)', overflow: 'hidden', position: 'relative' }}>
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${Math.min(100, (compareData.misjudgeCount / Math.max(reviewerData.misjudgeCount, compareData.misjudgeCount)) * 100)}%`,
                    background: 'var(--text-muted)',
                    opacity: 0.3
                  }} />
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: `${Math.min(100, (reviewerData.misjudgeCount / Math.max(reviewerData.misjudgeCount, compareData.misjudgeCount)) * 100)}%`,
                    background: 'var(--warning)'
                  }} />
                </div>
              </div>
            </div>
          </div>

          {/* 错误分布 */}
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <h3 className="panel-title">🎯 错误类型分布</h3>
            
            <div style={{ marginTop: 'var(--spacing-lg)' }}>
              {errorData.map((error, index) => (
                <div key={index} style={{ marginBottom: 'var(--spacing-md)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--spacing-xs)' }}>
                    <span style={{ fontWeight: 500 }}>{error.type}</span>
                    <span>{error.count}次（{error.pct.toFixed(1)}%）</span>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', height: '12px', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${error.pct}%`,
                      background: index === 0 ? 'var(--danger)' : index === 1 ? 'var(--warning)' : 'var(--info)'
                    }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 趋势图 */}
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title">📉 正确率趋势</h3>
              <div style={{ display: 'flex', gap: 'var(--spacing-xs)' }}>
                <button
                  onClick={() => setTrendDays(7)}
                  className={`button button-sm ${trendDays === 7 ? 'button-primary' : ''}`}
                >
                  7天
                </button>
                <button
                  onClick={() => setTrendDays(14)}
                  className={`button button-sm ${trendDays === 14 ? 'button-primary' : ''}`}
                >
                  14天
                </button>
                <button
                  onClick={() => setTrendDays(30)}
                  className={`button button-sm ${trendDays === 30 ? 'button-primary' : ''}`}
                >
                  30天
                </button>
              </div>
            </div>
            
            <div style={{ marginTop: 'var(--spacing-lg)', overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-secondary)' }}>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>日期</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>审核量</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>正确率</th>
                    <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center', borderBottom: '2px solid var(--border)' }}>趋势</th>
                  </tr>
                </thead>
                <tbody>
                  {trendData.map((item, index) => (
                    <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: 'var(--spacing-sm)' }}>{item.date}</td>
                      <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>{item.auditCount.toLocaleString()}</td>
                      <td style={{ 
                        padding: 'var(--spacing-sm)', 
                        textAlign: 'right',
                        color: item.accuracy >= 90 ? 'var(--success)' : 'var(--warning)',
                        fontWeight: 600
                      }}>
                        {item.accuracy.toFixed(1)}%
                      </td>
                      <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', fontSize: '1.2em' }}>
                        {index > 0 && (
                          item.accuracy > trendData[index - 1].accuracy ? '📈' :
                          item.accuracy < trendData[index - 1].accuracy ? '📉' : '➡️'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 改进建议 */}
          <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
            <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 改进建议</h3>
            
            <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
              {reviewerData.accuracy < 90 && (
                <li><strong>正确率偏低</strong>：当前{reviewerData.accuracy.toFixed(1)}%，低于90%目标，建议加强培训</li>
              )}
              {errorData[0] && errorData[0].pct > 30 && (
                <li><strong>错误集中</strong>：{errorData[0].type}占比{errorData[0].pct.toFixed(1)}%，建议针对性学习</li>
              )}
              {reviewerData.auditCount < compareData.auditCount * 0.8 && (
                <li><strong>审核量偏少</strong>：低于团队平均{((1 - reviewerData.auditCount / compareData.auditCount) * 100).toFixed(0)}%，建议提升效率</li>
              )}
              {reviewerData.accuracy >= 90 && reviewerData.auditCount >= compareData.auditCount && (
                <li><strong>表现优秀</strong>：正确率和审核量均达标，继续保持！🌟</li>
              )}
            </ul>
          </div>
        </>
      )}

      {/* 使用提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--bg-secondary)' }}>
        <h3 className="panel-title">💡 使用提示</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>输入审核人姓名，查看个人完整表现</li>
          <li>绿色表示优于团队平均，红色表示低于团队平均</li>
          <li>错误分布帮助定位个人薄弱环节</li>
          <li>趋势图显示最近表现变化</li>
          <li>点击"导出报告"可下载个人分析报告（开发中）</li>
        </ul>
      </div>
    </PageTemplate>
  );
}
