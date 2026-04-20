'use client';

import { PageTemplate } from '@/components/page-template';
import {
  PerformanceTrendChart,
  ApiPerformanceBarChart,
  PerformanceImprovementAreaChart,
  PerformanceDistributionPieChart,
  DatabaseQueryBarChart,
} from '@/components/charts';

export default function DataVisualizationPage() {
  // 性能趋势数据
  const trendData = [
    { name: '第1天', 响应时间: 1000, 目标值: 200 },
    { name: '第2天', 响应时间: 950, 目标值: 200 },
    { name: '第3天', 响应时间: 800, 目标值: 200 },
    { name: '第4天', 响应时间: 600, 目标值: 200 },
    { name: '第5天', 响应时间: 400, 目标值: 200 },
    { name: '第6天', 响应时间: 250, 目标值: 200 },
    { name: '第7天', 响应时间: 180, 目标值: 200 },
  ];

  // 接口性能对比数据
  const apiPerformanceData = [
    { name: '首页加载', 优化前: 356, 优化后: 14, 目标值: 50 },
    { name: '告警列表', 优化前: 259, 优化后: 31, 目标值: 20 },
    { name: '内检汇总', 优化前: 787, 优化后: 876, 目标值: 50 },
    { name: '新人汇总', 优化前: 547, 优化后: 527, 目标值: 50 },
  ];

  // 性能提升幅度数据
  const improvementData = [
    { name: '路由切换', 提升幅度: 80 },
    { name: '首页加载', 提升幅度: 96 },
    { name: '告警接口', 提升幅度: 88 },
    { name: '日期筛选', 提升幅度: 92 },
    { name: '按钮响应', 提升幅度: 87 },
  ];

  // 性能分布数据
  const distributionData = [
    { name: '优秀 (<50ms)', value: 2 },
    { name: '良好 (50-100ms)', value: 3 },
    { name: '一般 (100-500ms)', value: 2 },
    { name: '较慢 (>500ms)', value: 2 },
  ];

  // 数据库查询性能
  const databaseQueryData = [
    { name: '首页查询', 查询时间: 14 },
    { name: '告警查询', 查询时间: 31 },
    { name: '队列统计', 查询时间: 45 },
    { name: '详情查询', 查询时间: 120 },
    { name: '内检汇总', 查询时间: 876 },
    { name: '新人汇总', 查询时间: 527 },
  ];

  return (
    <PageTemplate
      title="数据可视化"
      subtitle="通过图表直观展示系统性能指标和优化效果"
    >
      {/* 性能趋势 */}
      <div className="panel">
        <h3 className="panel-title">📈 路由切换性能趋势（7天）</h3>
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            通过客户端组件优化，路由切换时间从 1000ms 降至 180ms，达成目标
          </p>
          <PerformanceTrendChart data={trendData} />
        </div>
      </div>

      {/* 接口性能对比 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">⚡ 接口性能优化对比</h3>
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            首页和告警接口已达到优秀水平，内检和新人汇总仍需进一步优化
          </p>
          <ApiPerformanceBarChart data={apiPerformanceData} />
        </div>
      </div>

      {/* 性能提升幅度 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🚀 各项性能提升幅度</h3>
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            前端交互性能提升最明显，平均提升幅度超过 85%
          </p>
          <PerformanceImprovementAreaChart data={improvementData} />
        </div>
      </div>

      {/* 性能分布 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🎯 接口性能等级分布</h3>
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            目前有 22% 的接口达到优秀水平，55% 处于良好或一般水平
          </p>
          <PerformanceDistributionPieChart data={distributionData} />
        </div>
      </div>

      {/* 数据库查询性能 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🗄️ 数据库查询性能排行</h3>
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            内检汇总和新人汇总是当前的性能瓶颈，需要 SQL 深度优化
          </p>
          <DatabaseQueryBarChart data={databaseQueryData} />
        </div>
      </div>

      {/* 关键指标总览 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">📊 关键指标总览</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <div style={{ textAlign: 'center', padding: 'var(--spacing-md)', background: 'var(--success-bg)', borderRadius: 'var(--radius)' }}>
            <div style={{ fontSize: '2.5em', fontWeight: 700, color: 'var(--success)', marginBottom: '8px' }}>
              96%
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>最大性能提升</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.75em', marginTop: '4px' }}>首页加载</div>
          </div>

          <div style={{ textAlign: 'center', padding: 'var(--spacing-md)', background: 'var(--success-bg)', borderRadius: 'var(--radius)' }}>
            <div style={{ fontSize: '2.5em', fontWeight: 700, color: 'var(--success)', marginBottom: '8px' }}>
              88%
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>平均提升幅度</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.75em', marginTop: '4px' }}>前端交互</div>
          </div>

          <div style={{ textAlign: 'center', padding: 'var(--spacing-md)', background: 'var(--warning-bg)', borderRadius: 'var(--radius)' }}>
            <div style={{ fontSize: '2.5em', fontWeight: 700, color: 'var(--warning)', marginBottom: '8px' }}>
              2
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>待优化接口</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.75em', marginTop: '4px' }}>内检/新人汇总</div>
          </div>

          <div style={{ textAlign: 'center', padding: 'var(--spacing-md)', background: 'var(--info-bg)', borderRadius: 'var(--radius)' }}>
            <div style={{ fontSize: '2.5em', fontWeight: 700, color: 'var(--info)', marginBottom: '8px' }}>
              20
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875em' }}>数据库索引</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.75em', marginTop: '4px' }}>已优化</div>
          </div>
        </div>
      </div>

      {/* 使用提示 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 图表说明</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li><strong>折线图</strong>：展示性能趋势，蓝线为实际值，绿色虚线为目标值</li>
          <li><strong>柱状图</strong>：对比优化前后的性能数据，红色为优化前，绿色为优化后</li>
          <li><strong>面积图</strong>：展示性能提升幅度，紫色区域面积越大表示提升越明显</li>
          <li><strong>饼图</strong>：展示接口性能等级分布，便于了解整体状态</li>
          <li><strong>横向柱状图</strong>：排行榜形式，直观对比各接口查询时间</li>
        </ul>
      </div>
    </PageTemplate>
  );
}
