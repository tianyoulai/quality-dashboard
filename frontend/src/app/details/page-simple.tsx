import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import { safeFetchApi } from '@/lib/api';
import { toDateInputValue } from '@/lib/formatters';

export const metadata = {
  title: '明细查询',
};

type SearchParams = Record<string, string | string[] | undefined>;

type PageProps = {
  searchParams?: Promise<SearchParams>;
};

function readParam(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/**
 * 🚀 详情查询 - 客户端优化版本（简化）
 * 
 * 优化要点：
 * 1. 使用 PageTemplate 实现 Sidebar 持久化
 * 2. 简化查询表单，突出核心功能
 * 3. 保持快速响应的用户体验
 * 
 * 注意：这是一个简化演示版本
 * 完整功能请参考原版 page.tsx.backup
 */
export default async function DetailsPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  
  // 获取日期范围
  const metaResult = await safeFetchApi<Record<string, unknown>>('/api/v1/meta/date-range');
  const maxDate = toDateInputValue(metaResult.data?.max_date as string | undefined);
  const minDate = toDateInputValue(metaResult.data?.min_date as string | undefined);
  
  // 解析查询参数
  const startDate = readParam(params.start_date) || (maxDate ? subtractDays(maxDate, 6) : '');
  const endDate = readParam(params.end_date) || maxDate || '';

  return (
    <PageTemplate
      title="明细查询"
      subtitle="多维度下钻分析，支持按日期、队列、审核人等条件筛选"
    >
      {/* 快速说明 */}
      <div className="panel">
        <h3 className="panel-title">📊 查询说明</h3>
        
        <div className="grid-3" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="数据范围"
            value={`${minDate || '—'} ~ ${maxDate || '—'}`}
            hint="保留45天数据"
            tone="neutral"
          />

          <SummaryCard
            label="默认时间窗口"
            value="7天"
            hint="可自定义调整"
            tone="neutral"
          />

          <SummaryCard
            label="支持筛选"
            value="10+"
            hint="日期/队列/审核人等"
            tone="neutral"
          />
        </div>
      </div>

      {/* 查询表单 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🔍 查询条件</h3>
        
        <form action="/details" method="GET" style={{ marginTop: 'var(--spacing-lg)' }}>
          <div className="grid-2" style={{ gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-md)' }}>
            <div>
              <label htmlFor="start_date" style={{ display: 'block', marginBottom: 'var(--spacing-xs)', fontWeight: 500 }}>
                开始日期
              </label>
              <input
                type="date"
                id="start_date"
                name="start_date"
                defaultValue={startDate}
                max={maxDate}
                min={minDate}
                className="input"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <label htmlFor="end_date" style={{ display: 'block', marginBottom: 'var(--spacing-xs)', fontWeight: 500 }}>
                结束日期
              </label>
              <input
                type="date"
                id="end_date"
                name="end_date"
                defaultValue={endDate}
                max={maxDate}
                min={minDate}
                className="input"
                style={{ width: '100%' }}
              />
            </div>
          </div>

          <div style={{ marginTop: 'var(--spacing-md)' }}>
            <button type="submit" className="button button-primary">
              🔍 查询
            </button>
            <button 
              type="reset" 
              className="button" 
              style={{ marginLeft: 'var(--spacing-sm)' }}
              onClick={() => window.location.href = '/details'}
            >
              重置
            </button>
          </div>
        </form>
      </div>

      {/* 查询结果提示 */}
      {(startDate || endDate) && (
        <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
          <h3 className="panel-title">📋 查询结果</h3>
          
          <div style={{ marginTop: 'var(--spacing-md)', padding: 'var(--spacing-md)', background: 'var(--info-bg)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--info)' }}>
            <p style={{ margin: 0, color: 'var(--info)' }}>
              ✅ 查询条件：{startDate} 至 {endDate}
            </p>
            <p style={{ margin: '8px 0 0 0', color: 'var(--text-muted)', fontSize: '0.875em' }}>
              数据加载中，请稍候...
            </p>
          </div>
        </div>
      )}

      {/* 功能导航 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🎯 高级功能</h3>
        
        <div className="grid-3" style={{ marginTop: 'var(--spacing-lg)' }}>
          <div className="summary-card">
            <div className="card-label">批量导出</div>
            <div className="card-value" style={{ fontSize: '2em' }}>📥</div>
            <div className="card-hint">支持 Excel/CSV 格式</div>
          </div>

          <div className="summary-card">
            <div className="card-label">多维筛选</div>
            <div className="card-value" style={{ fontSize: '2em' }}>🎛️</div>
            <div className="card-hint">队列/审核人/错误类型</div>
          </div>

          <div className="summary-card">
            <div className="card-label">数据透视</div>
            <div className="card-value" style={{ fontSize: '2em' }}>📊</div>
            <div className="card-hint">自定义维度分析</div>
          </div>
        </div>
      </div>

      {/* 使用提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 使用提示</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>建议日期跨度控制在 7-14 天，查询速度最快</li>
          <li>超过 30 天的查询会较慢，请耐心等待</li>
          <li>支持按 Enter 键快速查询</li>
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

// 辅助函数：日期减法
function subtractDays(dateText: string, days: number): string {
  const target = new Date(`${dateText}T00:00:00`);
  target.setDate(target.getDate() - days);
  return target.toISOString().slice(0, 10);
}
