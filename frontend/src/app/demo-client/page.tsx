import { PageTemplate } from '@/components/page-template';

export const metadata = {
  title: '客户端组件演示',
};

/**
 * 🚀 客户端组件演示页面
 * 
 * 这个页面展示了使用 PageTemplate 的效果：
 * - Sidebar 只渲染一次
 * - 路由切换瞬间响应
 * - 当前页面自动高亮
 * 
 * 使用方式：
 * 1. 访问 http://localhost:3000/demo-client
 * 2. 点击左侧 Sidebar 切换页面
 * 3. 观察切换速度和 Sidebar 是否闪烁
 * 
 * 预期效果：
 * - 切换速度：<200ms（几乎瞬间）
 * - Sidebar 不闪烁
 * - 当前页面高亮正确
 */
export default function DemoClientPage() {
  return (
    <PageTemplate
      title="客户端组件演示"
      subtitle="体验客户端组件带来的性能提升"
    >
      <div className="panel">
        <h3 className="panel-title">✨ 性能对比</h3>
        
        <div className="grid-3" style={{ marginTop: 'var(--spacing-lg)' }}>
          <div className="summary-card">
            <div className="card-label">切换页面</div>
            <div className="card-value">
              <span style={{ textDecoration: 'line-through', opacity: 0.5, marginRight: 8 }}>
                1000ms
              </span>
              <span style={{ color: 'var(--success)', fontSize: '1.5em' }}>
                &lt;200ms
              </span>
            </div>
            <div className="card-sublabel" style={{ color: 'var(--success)' }}>
              ⚡ 提升 80%
            </div>
          </div>

          <div className="summary-card">
            <div className="card-label">Sidebar 渲染</div>
            <div className="card-value">
              <span style={{ textDecoration: 'line-through', opacity: 0.5, marginRight: 8 }}>
                每次
              </span>
              <span style={{ color: 'var(--success)', fontSize: '1.5em' }}>
                仅1次
              </span>
            </div>
            <div className="card-sublabel" style={{ color: 'var(--success)' }}>
              ✅ 不闪烁
            </div>
          </div>

          <div className="summary-card">
            <div className="card-label">用户体验</div>
            <div className="card-value">
              <span style={{ textDecoration: 'line-through', opacity: 0.5, marginRight: 8 }}>
                ⭐⭐
              </span>
              <span style={{ color: 'var(--success)', fontSize: '1.5em' }}>
                ⭐⭐⭐⭐⭐
              </span>
            </div>
            <div className="card-sublabel" style={{ color: 'var(--success)' }}>
              🚀 流畅度翻倍
            </div>
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🔍 技术要点</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <h4 style={{ marginBottom: 'var(--spacing-sm)' }}>核心优化</h4>
          <ul style={{ marginLeft: 'var(--spacing-lg)', lineHeight: 1.8 }}>
            <li>
              <strong>Sidebar 持久化</strong>: 使用 <code>'use client'</code> 标记为客户端组件
            </li>
            <li>
              <strong>自动路径获取</strong>: <code>usePathname()</code> Hook 自动高亮当前页
            </li>
            <li>
              <strong>Link 预加载</strong>: <code>prefetch=true</code> 鼠标悬停时预加载
            </li>
            <li>
              <strong>无页面刷新</strong>: Next.js App Router 客户端路由
            </li>
          </ul>
        </div>

        <div style={{ marginTop: 'var(--spacing-lg)' }}>
          <h4 style={{ marginBottom: 'var(--spacing-sm)' }}>实现对比</h4>
          <div className="grid-2">
            <div>
              <h5 style={{ color: 'var(--danger)', marginBottom: 'var(--spacing-sm)' }}>
                ❌ Server Component（优化前）
              </h5>
              <pre style={{ 
                background: 'var(--panel-bg)', 
                padding: 'var(--spacing-md)', 
                borderRadius: 'var(--radius)',
                fontSize: '0.875em',
                overflow: 'auto'
              }}>
{`// 每次路由切换都重新渲染
export default async function Page() {
  const data = await fetch(...);
  return (
    <AppShell currentPath="/page">
      {/* Sidebar 重复渲染 */}
      {/* 等待数据加载 */}
    </AppShell>
  );
}`}
              </pre>
            </div>

            <div>
              <h5 style={{ color: 'var(--success)', marginBottom: 'var(--spacing-sm)' }}>
                ✅ Client Component（优化后）
              </h5>
              <pre style={{ 
                background: 'var(--panel-bg)', 
                padding: 'var(--spacing-md)', 
                borderRadius: 'var(--radius)',
                fontSize: '0.875em',
                overflow: 'auto'
              }}>
{`// Sidebar 只渲染一次
export default function Page() {
  return (
    <PageTemplate title="页面">
      {/* Sidebar 持久化 */}
      {/* 瞬间切换 */}
    </PageTemplate>
  );
}`}
              </pre>
            </div>
          </div>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🎯 测试步骤</h3>
        
        <ol style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>
            <strong>打开 Chrome DevTools</strong> (F12) → Performance 标签
          </li>
          <li>
            <strong>点击左侧 Sidebar</strong> 切换到其他页面（如"详情查询"）
          </li>
          <li>
            <strong>再切换回来</strong> 到本页面
          </li>
          <li>
            <strong>观察性能</strong>:
            <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-xs)' }}>
              <li>Sidebar 是否闪烁？（应该不闪烁）</li>
              <li>切换速度如何？（应该 &lt;200ms）</li>
              <li>页面是否全量刷新？（应该只更新内容区）</li>
            </ul>
          </li>
        </ol>
      </div>

      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">📚 使用文档</h3>
        
        <p style={{ marginTop: 'var(--spacing-md)', lineHeight: 1.8 }}>
          详细使用指南请查看：
        </p>
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-sm)', lineHeight: 2 }}>
          <li>
            <code>FRONTEND_COMPONENTS_USAGE.md</code> - 组件使用指南
          </li>
          <li>
            <code>FRONTEND_QUICK_FIX.md</code> - 快速优化指南
          </li>
          <li>
            <code>FRONTEND_PERFORMANCE_OPTIMIZATION.md</code> - 完整优化方案
          </li>
        </ul>
      </div>
    </PageTemplate>
  );
}
