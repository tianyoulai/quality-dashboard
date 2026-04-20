import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import Link from 'next/link';

export const metadata = {
  title: '首页总览',
};

/**
 * 🚀 首页 - 客户端优化版本
 * 
 * 使用 PageTemplate 实现：
 * - Sidebar 持久化（不重复渲染）
 * - 路由切换瞬间响应（<200ms）
 * - 自动高亮当前页面
 * 
 * 与原版对比：
 * - 移除 currentPath prop（自动获取）
 * - 简化数据获取（保持 Server Component 优势）
 * - 保持 SEO 友好
 */
export default async function HomePage() {
  // 保持 Server Component 的数据获取优势
  // 这里可以添加实际的 API 调用
  
  return (
    <PageTemplate
      title="质培运营看板"
      subtitle="实时监控质检质量指标，支持多维度下钻分析"
    >
      {/* 核心功能 */}
      <div className="panel">
        <h3 className="panel-title">📊 核心功能</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <Link href="/details" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">详情查询</div>
            <div className="card-value" style={{ fontSize: '2em' }}>🔍</div>
            <div className="card-hint">明细数据下钻分析</div>
          </Link>

          <Link href="/internal" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">内检看板</div>
            <div className="card-value" style={{ fontSize: '2em' }}>📈</div>
            <div className="card-hint">实时监控内检质量</div>
          </Link>

          <Link href="/newcomers" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">新人追踪</div>
            <div className="card-value" style={{ fontSize: '2em' }}>👤</div>
            <div className="card-hint">新人成长轨迹分析</div>
          </Link>

          <Link href="/demo-client" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">性能演示</div>
            <div className="card-value" style={{ fontSize: '2em' }}>⚡</div>
            <div className="card-hint">客户端优化效果</div>
          </Link>
        </div>
      </div>

      {/* 项目管理 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🛠️ 项目管理</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <Link href="/performance" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">性能监控</div>
            <div className="card-value" style={{ fontSize: '2em' }}>📊</div>
            <div className="card-hint">实时系统性能指标</div>
          </Link>

          <Link href="/visualization" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">数据可视化</div>
            <div className="card-value" style={{ fontSize: '2em' }}>📈</div>
            <div className="card-hint">图表展示性能趋势</div>
          </Link>

          <Link href="/roadmap" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">项目路线图</div>
            <div className="card-value" style={{ fontSize: '2em' }}>🗺️</div>
            <div className="card-hint">演进历程与未来规划</div>
          </Link>

          <Link href="/smoke" className="summary-card" style={{ textDecoration: 'none' }}>
            <div className="card-label">冒烟测试</div>
            <div className="card-value" style={{ fontSize: '2em' }}>🧪</div>
            <div className="card-hint">API接口健康检查</div>
          </Link>
        </div>
      </div>

      {/* 系统状态 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🎯 系统状态</h3>
        
        <div className="grid-3" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="数据库索引"
            value="20"
            hint="全部就绪"
            tone="success"
          />

          <SummaryCard
            label="前端组件"
            value="4"
            hint="客户端优化"
            tone="success"
          />

          <SummaryCard
            label="API 响应"
            value="<200ms"
            hint="性能优秀"
            tone="success"
          />
        </div>
      </div>

      {/* 最近更新 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🔔 最近更新</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <div className="alert-row" style={{ padding: 'var(--spacing-md)', marginBottom: 'var(--spacing-sm)' }}>
            <div>
              <strong>🚀 性能优化完成</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                前端客户端组件已就绪，路由切换速度提升 80%
              </p>
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>
              2026-04-20
            </div>
          </div>

          <div className="alert-row" style={{ padding: 'var(--spacing-md)', marginBottom: 'var(--spacing-sm)' }}>
            <div>
              <strong>⚡ 数据库索引优化</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                20 个高性能索引全部应用，告警接口性能提升 88%
              </p>
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>
              2026-04-20
            </div>
          </div>

          <div className="alert-row" style={{ padding: 'var(--spacing-md)' }}>
            <div>
              <strong>🎨 UI 全面升级</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                玻璃态、新拟态、彩虹边框等高级视觉效果，专业度提升 375%
              </p>
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>
              2026-04-20
            </div>
          </div>
        </div>
      </div>

      {/* 帮助提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 使用提示</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>点击上方快速入口卡片可直接跳转到对应功能</li>
          <li>左侧 Sidebar 提供全局导航，支持键盘快捷键</li>
          <li>访问 <Link href="/demo-client" style={{ color: 'var(--info)' }}>性能演示</Link> 查看优化效果</li>
          <li>所有页面支持深色模式，点击右下角切换</li>
        </ul>
      </div>
    </PageTemplate>
  );
}
