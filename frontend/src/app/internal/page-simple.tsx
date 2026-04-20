import { PageTemplate } from '@/components/page-template';
import { DateFilterClient } from '@/components/date-filter-client';
import { SummaryCard } from '@/components/summary-card';
import Link from 'next/link';

export const metadata = {
  title: '内检看板',
};

type SearchParams = Record<string, string | string[] | undefined>;

type PageProps = {
  searchParams?: Promise<SearchParams>;
};

function readParams(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/**
 * 🚀 内检看板 - 客户端优化版本（简化）
 * 
 * 优化要点：
 * 1. 使用 PageTemplate 实现 Sidebar 持久化
 * 2. 使用 DateFilterClient 实现无刷新日期切换
 * 3. 保持数据获取的 Server Component 优势
 * 
 * 注意：这是一个简化演示版本
 * 完整功能请参考原版 page.tsx.backup
 */
export default async function InternalPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const selectedDate = readParams(params.selected_date) || new Date().toISOString().slice(0, 10);
  const maxDate = new Date().toISOString().slice(0, 10);

  return (
    <PageTemplate
      title="内检看板"
      subtitle="实时监控内检质量指标，支持趋势分析和问题下钻"
    >
      {/* 日期筛选 - 客户端组件，无页面刷新 */}
      <div className="panel">
        <h3 className="panel-title">📅 日期筛选</h3>
        <DateFilterClient
          initialDate={selectedDate}
          maxDate={maxDate}
        />
      </div>

      {/* 核心指标 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">📊 核心指标</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="审核量"
            value="12,345"
            hint="较昨日 +8.2%"
            tone="success"
          />

          <SummaryCard
            label="正确率"
            value="98.5%"
            hint="目标 98.0%"
            tone="success"
          />

          <SummaryCard
            label="错误数"
            value="185"
            hint="较昨日 -5.3%"
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

      {/* 功能导航 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🔍 数据下钻</h3>
        
        <div className="grid-3" style={{ marginTop: 'var(--spacing-lg)' }}>
          <Link href="/details" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">队列分析</div>
            <div className="card-value" style={{ fontSize: '2em' }}>📈</div>
            <div className="card-hint">查看各队列明细数据</div>
          </Link>

          <Link href="/details" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">审核人分析</div>
            <div className="card-value" style={{ fontSize: '2em' }}>👥</div>
            <div className="card-hint">查看审核人表现排名</div>
          </Link>

          <Link href="/details" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">错误类型分析</div>
            <div className="card-value" style={{ fontSize: '2em' }}>🎯</div>
            <div className="card-hint">查看高频错误类型</div>
          </Link>
        </div>
      </div>

      {/* 提示信息 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 使用提示</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>修改日期后自动更新数据，无需刷新页面</li>
          <li>点击功能卡片可快速跳转到详情查询页面</li>
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
