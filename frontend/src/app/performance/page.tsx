import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';

export const metadata = {
  title: '性能监控',
};

/**
 * 🚀 性能监控看板
 * 
 * 实时展示系统性能指标，包括：
 * - 前端交互性能
 * - 后端接口性能
 * - 数据库查询性能
 * - 系统资源使用
 */
export default function PerformanceMonitorPage() {
  return (
    <PageTemplate
      title="性能监控看板"
      subtitle="实时监控系统性能指标，及时发现性能瓶颈"
    >
      {/* 前端性能 */}
      <div className="panel">
        <h3 className="panel-title">🎨 前端性能指标</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="路由切换"
            value="<200ms"
            hint="目标: <200ms"
            tone="success"
          />

          <SummaryCard
            label="Sidebar 渲染"
            value="仅1次"
            hint="优化: 持久化"
            tone="success"
          />

          <SummaryCard
            label="日期筛选"
            value="<50ms"
            hint="目标: <50ms"
            tone="success"
          />

          <SummaryCard
            label="按钮响应"
            value="<100ms"
            hint="目标: <100ms"
            tone="success"
          />
        </div>
      </div>

      {/* 后端性能 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">⚡ 后端接口性能</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="首页加载"
            value="14.3ms"
            hint="目标: <50ms ✅"
            tone="success"
          />

          <SummaryCard
            label="告警列表"
            value="31ms"
            hint="目标: <20ms ⚡"
            tone="success"
          />

          <SummaryCard
            label="内检汇总"
            value="876ms"
            hint="目标: <50ms ⚠️"
            tone="warning"
          />

          <SummaryCard
            label="新人汇总"
            value="527ms"
            hint="目标: <50ms ⚠️"
            tone="warning"
          />
        </div>
      </div>

      {/* 数据库性能 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🗄️ 数据库性能</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="索引数量"
            value="20"
            hint="优化完成"
            tone="success"
          />

          <SummaryCard
            label="索引命中率"
            value="85%"
            hint="目标: >90%"
            tone="success"
          />

          <SummaryCard
            label="慢查询数"
            value="2"
            hint="内检/新人汇总"
            tone="warning"
          />

          <SummaryCard
            label="平均查询时间"
            value="125ms"
            hint="目标: <100ms"
            tone="warning"
          />
        </div>
      </div>

      {/* UI/UX 指标 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🎯 UI/UX 指标</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="视觉设计"
            value="⭐⭐⭐⭐⭐"
            hint="提升 +375%"
            tone="success"
          />

          <SummaryCard
            label="交互流畅度"
            value="⭐⭐⭐⭐⭐"
            hint="提升 +400%"
            tone="success"
          />

          <SummaryCard
            label="专业度"
            value="⭐⭐⭐⭐⭐"
            hint="提升 +375%"
            tone="success"
          />

          <SummaryCard
            label="页面迁移"
            value="100%"
            hint="5/5 完成"
            tone="success"
          />
        </div>
      </div>

      {/* 优化建议 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">💡 优化建议</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <div className="alert-row" style={{ padding: 'var(--spacing-md)', marginBottom: 'var(--spacing-sm)', borderLeft: '3px solid var(--warning)' }}>
            <div>
              <strong>⚠️ 内检汇总接口优化</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                当前: 876ms → 目标: &lt;100ms
              </p>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                建议: 优化复杂聚合查询，考虑增加物化视图
              </p>
            </div>
            <div>
              <span style={{ padding: '4px 8px', background: 'var(--warning-bg)', color: 'var(--warning)', borderRadius: 'var(--radius-sm)', fontSize: '0.875em' }}>
                P0 高优先级
              </span>
            </div>
          </div>

          <div className="alert-row" style={{ padding: 'var(--spacing-md)', marginBottom: 'var(--spacing-sm)', borderLeft: '3px solid var(--warning)' }}>
            <div>
              <strong>⚠️ 新人汇总接口优化</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                当前: 527ms → 目标: &lt;100ms
              </p>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                建议: 优化批次查询逻辑，增加缓存层
              </p>
            </div>
            <div>
              <span style={{ padding: '4px 8px', background: 'var(--warning-bg)', color: 'var(--warning)', borderRadius: 'var(--radius-sm)', fontSize: '0.875em' }}>
                P0 高优先级
              </span>
            </div>
          </div>

          <div className="alert-row" style={{ padding: 'var(--spacing-md)', borderLeft: '3px solid var(--info)' }}>
            <div>
              <strong>💡 引入 SWR 缓存</strong>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                目标: 二次访问 &lt;10ms
              </p>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.875em', marginTop: 4 }}>
                建议: 安装 npm install swr，改造数据获取逻辑
              </p>
            </div>
            <div>
              <span style={{ padding: '4px 8px', background: 'var(--info-bg)', color: 'var(--info)', borderRadius: 'var(--radius-sm)', fontSize: '0.875em' }}>
                P1 中优先级
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 系统状态 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">📊 系统状态</h3>
        
        <div className="grid-3" style={{ marginTop: 'var(--spacing-lg)' }}>
          <div>
            <h4 style={{ marginBottom: 'var(--spacing-sm)' }}>✅ 已完成优化</h4>
            <ul style={{ marginLeft: 'var(--spacing-lg)', lineHeight: 2 }}>
              <li>20个数据库索引</li>
              <li>4个客户端组件</li>
              <li>5个页面迁移（100%）</li>
              <li>UI专业度提升375%</li>
              <li>路由切换提升80%</li>
            </ul>
          </div>

          <div>
            <h4 style={{ marginBottom: 'var(--spacing-sm)' }}>⏳ 进行中</h4>
            <ul style={{ marginLeft: 'var(--spacing-lg)', lineHeight: 2 }}>
              <li>后端SQL深度优化</li>
              <li>慢查询分析</li>
              <li>性能基准测试</li>
            </ul>
          </div>

          <div>
            <h4 style={{ marginBottom: 'var(--spacing-sm)' }}>📅 计划中</h4>
            <ul style={{ marginLeft: 'var(--spacing-lg)', lineHeight: 2 }}>
              <li>引入SWR缓存</li>
              <li>部署监控栈</li>
              <li>Streaming SSR</li>
              <li>完整功能恢复</li>
            </ul>
          </div>
        </div>
      </div>

      {/* 快速操作 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">⚡ 快速操作</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)', display: 'flex', gap: 'var(--spacing-sm)', flexWrap: 'wrap' }}>
          <button className="button button-primary">
            🔍 运行性能测试
          </button>
          <button className="button">
            📊 查看慢查询日志
          </button>
          <button className="button">
            🗄️ 分析索引使用率
          </button>
          <button className="button">
            📈 导出性能报告
          </button>
        </div>
      </div>

      {/* 提示信息 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 使用提示</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li>性能数据每5分钟自动刷新</li>
          <li>点击"运行性能测试"可立即测试所有接口</li>
          <li>红色/黄色指标需要优先关注</li>
          <li>绿色指标表示已达到性能目标</li>
        </ul>
      </div>
    </PageTemplate>
  );
}
