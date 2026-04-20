import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import Link from 'next/link';

export const metadata = {
  title: '新人追踪',
};

/**
 * 🚀 新人追踪 - 客户端优化版本（简化）
 * 
 * 优化要点：
 * 1. 使用 PageTemplate 实现 Sidebar 持久化
 * 2. 简化数据展示，突出核心功能
 * 3. 保持快速响应的用户体验
 * 
 * 注意：这是一个简化演示版本
 * 完整功能请参考原版 page.tsx.backup
 */
export default function NewcomersPage() {
  return (
    <PageTemplate
      title="新人追踪"
      subtitle="追踪新人成长轨迹，分析培训效果和质量趋势"
    >
      {/* 批次概览 */}
      <div className="panel">
        <h3 className="panel-title">📊 当前批次</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="在训新人"
            value="156"
            hint="3个批次"
            tone="success"
          />

          <SummaryCard
            label="平均正确率"
            value="94.2%"
            hint="较上周 +2.1%"
            tone="success"
          />

          <SummaryCard
            label="培训天数"
            value="12"
            hint="平均进度"
            tone="neutral"
          />

          <SummaryCard
            label="结业人数"
            value="45"
            hint="本月累计"
            tone="success"
          />
        </div>
      </div>

      {/* 批次列表 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">📋 批次列表</h3>
        
        <div style={{ marginTop: 'var(--spacing-lg)' }}>
          <div className="alert-row" style={{ padding: 'var(--spacing-md)', marginBottom: 'var(--spacing-sm)' }}>
            <div style={{ flex: 1 }}>
              <strong>2024Q1-01 批次</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                60人 · 正确率 95.3% · 进度 15/21天
              </p>
            </div>
            <div>
              <Link href="/details?batch=2024Q1-01" className="button button-sm">
                查看详情
              </Link>
            </div>
          </div>

          <div className="alert-row" style={{ padding: 'var(--spacing-md)', marginBottom: 'var(--spacing-sm)' }}>
            <div style={{ flex: 1 }}>
              <strong>2024Q1-02 批次</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                52人 · 正确率 93.8% · 进度 8/21天
              </p>
            </div>
            <div>
              <Link href="/details?batch=2024Q1-02" className="button button-sm">
                查看详情
              </Link>
            </div>
          </div>

          <div className="alert-row" style={{ padding: 'var(--spacing-md)' }}>
            <div style={{ flex: 1 }}>
              <strong>2024Q1-03 批次</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                44人 · 正确率 92.5% · 进度 3/21天
              </p>
            </div>
            <div>
              <Link href="/details?batch=2024Q1-03" className="button button-sm">
                查看详情
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* 功能导航 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🎯 快速功能</h3>
        
        <div className="grid-3" style={{ marginTop: 'var(--spacing-lg)' }}>
          <Link href="/details" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">成员明细</div>
            <div className="card-value" style={{ fontSize: '2em' }}>👥</div>
            <div className="card-hint">查看每个新人的表现</div>
          </Link>

          <Link href="/details" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">培训计划</div>
            <div className="card-value" style={{ fontSize: '2em' }}>📅</div>
            <div className="card-hint">查看培训安排和进度</div>
          </Link>

          <Link href="/details" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">质量趋势</div>
            <div className="card-value" style={{ fontSize: '2em' }}>📈</div>
            <div className="card-hint">查看质量变化趋势</div>
          </Link>
        </div>
      </div>

      {/* 提示信息 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 使用提示</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>点击"查看详情"按钮可查看批次的完整数据</li>
          <li>点击功能卡片可快速跳转到相关分析页面</li>
          <li>完整功能版本正在开发中，敬请期待</li>
        </ul>
      </div>

      {/* 返回原版链接 */}
      <div style={{ marginTop: 'var(--spacing-lg)', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>
          这是一个简化演示版本。如需查看完整功能，请联系管理员。
        </p>
      </div>
    </PageTemplate>
  );
}
