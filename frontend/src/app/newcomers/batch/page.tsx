'use client';

import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import { useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';
import Link from 'next/link';

/**
 * 批次详情页
 * 
 * 显示指定批次的详细信息：
 * 1. 批次概览
 * 2. 新人列表
 * 3. 质量趋势
 * 4. 问题新人关注
 */
export default function BatchDetailPage() {
  const searchParams = useSearchParams();
  const batchId = searchParams.get('id') || '2024Q1-01';
  
  const [batchData, setBatchData] = useState<any>(null);
  const [newcomersList, setNewcomersList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // 加载批次数据
  useEffect(() => {
    loadBatchData();
  }, [batchId]);

  const loadBatchData = async () => {
    setLoading(true);
    try {
      // 调用真实API
      const res = await fetch(`http://localhost:8000/api/v1/newcomers/batch/${batchId}`);
      const data = await res.json();
      
      if (data.ok && data.data) {
        setBatchData(data.data);
        setNewcomersList(data.data.newcomers || []);
      } else {
        throw new Error('数据格式错误');
      }
    } catch (error) {
      console.error('加载批次数据失败:', error);
      alert('加载失败，请检查网络连接');
    } finally {
      setLoading(false);
    }
  };

  // 导出新人列表
  const exportNewcomers = () => {
    // TODO: 实现导出功能
    alert('导出功能开发中...');
  };

  if (loading) {
    return (
      <PageTemplate title="批次详情" subtitle="加载中...">
        <div style={{ textAlign: 'center', padding: 'var(--spacing-xl)' }}>
          加载中...
        </div>
      </PageTemplate>
    );
  }

  return (
    <PageTemplate
      title={`📚 ${batchData?.name || '批次详情'}`}
      subtitle="查看批次新人表现和质量趋势"
    >
      {/* 返回按钮 */}
      <div style={{ marginBottom: 'var(--spacing-lg)' }}>
        <Link href="/newcomers" className="button button-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text)' }}>
          ← 返回批次列表
        </Link>
      </div>

      {/* 批次概览 */}
      <div className="panel">
        <h3 className="panel-title">📊 批次概览</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="总人数"
            value={batchData?.total_people?.toString() || '0'}
            hint={`已达标: ${batchData?.passed_count}人`}
            tone="neutral"
          />

          <SummaryCard
            label="平均正确率"
            value={`${batchData?.avg_accuracy?.toFixed(1)}%`}
            hint="目标 ≥90%"
            tone={batchData?.avg_accuracy >= 90 ? 'success' : 'danger'}
          />

          <SummaryCard
            label="培训进度"
            value={`${batchData?.current_day}/${batchData?.total_days}天`}
            hint={`完成度: ${((batchData?.current_day / batchData?.total_days) * 100).toFixed(0)}%`}
            tone="neutral"
          />

          <SummaryCard
            label="达标率"
            value={`${batchData?.pass_rate?.toFixed(1)}%`}
            hint={`${batchData?.passed_count}人达标`}
            tone={batchData?.pass_rate >= 85 ? 'success' : 'warning'}
          />
        </div>
      </div>

      {/* 问题新人重点关注 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', borderColor: 'var(--danger)', borderWidth: '2px' }}>
        <h3 className="panel-title" style={{ color: 'var(--danger)' }}>⚠️ 问题新人重点关注（正确率 &lt; 90%）</h3>
        
        <div style={{ marginTop: 'var(--spacing-lg)' }}>
          {newcomersList.filter(n => n.status === 'problem' || n.status === 'warning').length === 0 ? (
            <div style={{ padding: 'var(--spacing-md)', textAlign: 'center', color: 'var(--success)' }}>
              ✅ 太棒了！所有新人正确率都 ≥ 90%
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
              {newcomersList.filter(n => n.status === 'problem' || n.status === 'warning').map((newcomer, index) => (
                <div key={index} className="problem-item" style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--spacing-md)',
                  padding: 'var(--spacing-sm)',
                  background: 'var(--bg-secondary)',
                  borderRadius: 'var(--radius)',
                  borderLeft: `3px solid ${newcomer.status === 'problem' ? 'var(--danger)' : 'var(--warning)'}`
                }}>
                  <span style={{ fontWeight: 500, flex: 1 }}>{newcomer.name}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>{newcomer.queue}</span>
                  <span style={{ 
                    fontWeight: 600, 
                    fontSize: '1.1em',
                    color: newcomer.status === 'problem' ? 'var(--danger)' : 'var(--warning)'
                  }}>
                    {newcomer.accuracy.toFixed(1)}%
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>
                    审核量: {newcomer.audit_count.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 新人列表 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 className="panel-title">👥 新人列表</h3>
          <button onClick={exportNewcomers} className="button button-sm">
            导出列表 ⬇
          </button>
        </div>
        
        <div style={{ marginTop: 'var(--spacing-lg)', overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-secondary)' }}>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>排名</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>姓名</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', borderBottom: '2px solid var(--border)' }}>队列</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>审核量</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>正确率</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right', borderBottom: '2px solid var(--border)' }}>进度</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center', borderBottom: '2px solid var(--border)' }}>状态</th>
              </tr>
            </thead>
            <tbody>
              {newcomersList.map((newcomer, index) => (
                <tr key={index} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)' }}>{index + 1}</td>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 500 }}>{newcomer.name}</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>{newcomer.queue}</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>
                    {newcomer.audit_count.toLocaleString()}
                  </td>
                  <td style={{ 
                    padding: 'var(--spacing-sm)', 
                    textAlign: 'right',
                    color: newcomer.accuracy >= 95 ? 'var(--success)' : 
                           newcomer.accuracy >= 90 ? 'var(--warning)' : 'var(--danger)',
                    fontWeight: 600
                  }}>
                    {newcomer.accuracy.toFixed(1)}%
                  </td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>
                    {newcomer.days}天
                  </td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                    {newcomer.status === 'excellent' && '🌟 优秀'}
                    {newcomer.status === 'normal' && '✅ 正常'}
                    {newcomer.status === 'warning' && '⚠️ 关注'}
                    {newcomer.status === 'problem' && '❌ 问题'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 使用提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 使用提示</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>问题新人（正确率&lt;90%）会自动标注在上方重点关注区域</li>
          <li>点击"导出列表"可下载新人表现数据（开发中）</li>
          <li>正确率颜色编码：绿色≥95%，黄色90-95%，红色&lt;90%</li>
          <li>状态标签：🌟优秀(≥95%) ✅正常(90-95%) ⚠️关注(85-90%) ❌问题(&lt;85%)</li>
        </ul>
      </div>
    </PageTemplate>
  );
}
