import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';

export const metadata = {
  title: '错误分析',
};

/**
 * 🔍 深度错误分析页面
 * 
 * 核心目标：
 * 1. 多维度分析错误（错误类型×队列×审核人×时间）
 * 2. 识别问题根因（培训问题 vs 标准问题 vs 系统问题）
 * 3. 提供改进建议（培训重点/标准优化/流程改进）
 */
export default function ErrorAnalysisPage() {
  return (
    <PageTemplate
      title="深度错误分析"
      subtitle="多维度分析错误根因，精准制定改进方案"
    >
      {/* 错误总览 */}
      <div className="panel">
        <h3 className="panel-title">📊 错误总览（最近7天）</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="总错误数"
            value="1,245"
            hint="较上周 ↑ 8.5%"
            tone="warning"
          />

          <SummaryCard
            label="误判数"
            value="723"
            hint="占比 58.1%"
            tone="danger"
          />

          <SummaryCard
            label="漏判数"
            value="522"
            hint="占比 41.9%"
            tone="warning"
          />

          <SummaryCard
            label="申诉翻案率"
            value="32.5%"
            hint="较上周 ↑ 5.2%"
            tone="danger"
          />
        </div>
      </div>

      {/* 错误类型 × 队列热力矩阵 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🔥 错误热力矩阵（错误类型 × 队列）</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            颜色越深表示错误越集中，重点关注深红色区域
          </p>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875em' }}>
              <thead>
                <tr style={{ background: 'var(--card-bg)' }}>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', position: 'sticky', left: 0, background: 'var(--card-bg)', zIndex: 1 }}>错误类型</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>队列A</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>队列B</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>队列C</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>公众号</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>合计</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600, position: 'sticky', left: 0, background: 'white', zIndex: 1 }}>评论引流判定</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fee2e2', fontWeight: 600 }}>186</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fecaca', fontWeight: 600 }}>98</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>42</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>16</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', fontWeight: 700 }}>342</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600, position: 'sticky', left: 0, background: 'white', zIndex: 1 }}>低质内容判定</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>45</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fecaca', fontWeight: 600 }}>112</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fecaca' }}>61</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>0</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', fontWeight: 700 }}>218</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600, position: 'sticky', left: 0, background: 'white', zIndex: 1 }}>广告识别</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>8</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>23</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>19</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fecaca', fontWeight: 600 }}>106</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', fontWeight: 700 }}>156</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600, position: 'sticky', left: 0, background: 'white', zIndex: 1 }}>违规内容</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>34</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>28</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fecaca', fontWeight: 600 }}>52</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>10</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', fontWeight: 700 }}>124</td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600, position: 'sticky', left: 0, background: 'white', zIndex: 1 }}>其他</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>67</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>89</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>95</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', background: '#fef2f2' }}>154</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', fontWeight: 700 }}>405</td>
                </tr>
                <tr style={{ background: 'var(--card-bg)', fontWeight: 700 }}>
                  <td style={{ padding: 'var(--spacing-sm)', position: 'sticky', left: 0, background: 'var(--card-bg)', zIndex: 1 }}>合计</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>340</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>350</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>269</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>286</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center', color: 'var(--danger)' }}>1,245</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 问题根因分析 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🔍 问题根因分析</h3>
        
        <div className="grid-3" style={{ marginTop: 'var(--spacing-lg)', gap: 'var(--spacing-md)' }}>
          {/* 培训问题 */}
          <div style={{ padding: 'var(--spacing-md)', background: 'var(--danger-bg)', borderRadius: 'var(--radius)', borderLeft: '4px solid var(--danger)' }}>
            <h4 style={{ color: 'var(--danger)', marginBottom: 'var(--spacing-sm)' }}>🎓 培训问题（42%）</h4>
            <div style={{ fontSize: '0.875em', lineHeight: 1.8 }}>
              <p style={{ margin: '8px 0' }}><strong>表现：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>特定审核人反复出错</li>
                <li>新人错误率高</li>
                <li>同类问题持续发生</li>
              </ul>
              <p style={{ margin: '8px 0' }}><strong>典型案例：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>引流判定标准不清晰</li>
                <li>低质内容边界模糊</li>
              </ul>
              <p style={{ margin: '8px 0' }}><strong>改进建议：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>针对性培训（引流/低质）</li>
                <li>案例库补充</li>
                <li>定期复训考核</li>
              </ul>
            </div>
          </div>

          {/* 标准问题 */}
          <div style={{ padding: 'var(--spacing-md)', background: 'var(--warning-bg)', borderRadius: 'var(--radius)', borderLeft: '4px solid var(--warning)' }}>
            <h4 style={{ color: 'var(--warning)', marginBottom: 'var(--spacing-sm)' }}>📋 标准问题（35%）</h4>
            <div style={{ fontSize: '0.875em', lineHeight: 1.8 }}>
              <p style={{ margin: '8px 0' }}><strong>表现：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>不同审核人判定不一致</li>
                <li>申诉翻案率高</li>
                <li>标准文档模糊</li>
              </ul>
              <p style={{ margin: '8px 0' }}><strong>典型案例：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>引流vs导流边界不清</li>
                <li>广告vs正常推广</li>
              </ul>
              <p style={{ margin: '8px 0' }}><strong>改进建议：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>优化审核标准文档</li>
                <li>增加边界case</li>
                <li>统一判定口径</li>
              </ul>
            </div>
          </div>

          {/* 系统问题 */}
          <div style={{ padding: 'var(--spacing-md)', background: 'var(--info-bg)', borderRadius: 'var(--radius)', borderLeft: '4px solid var(--info)' }}>
            <h4 style={{ color: 'var(--info)', marginBottom: 'var(--spacing-sm)' }}>⚙️ 系统问题（23%）</h4>
            <div style={{ fontSize: '0.875em', lineHeight: 1.8 }}>
              <p style={{ margin: '8px 0' }}><strong>表现：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>数据展示不全</li>
                <li>上下文信息缺失</li>
                <li>标注工具限制</li>
              </ul>
              <p style={{ margin: '8px 0' }}><strong>典型案例：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>评论内容截断</li>
                <li>引用信息不完整</li>
              </ul>
              <p style={{ margin: '8px 0' }}><strong>改进建议：</strong></p>
              <ul style={{ marginLeft: 'var(--spacing-lg)' }}>
                <li>优化数据展示</li>
                <li>补充上下文</li>
                <li>改进工具功能</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* 重点改进行动计划 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">📋 重点改进行动计划</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--card-bg)', borderBottom: '2px solid var(--border)' }}>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', width: '5%' }}>优先级</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', width: '20%' }}>问题</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', width: '25%' }}>改进措施</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', width: '15%' }}>责任人</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', width: '10%' }}>完成时间</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left', width: '15%' }}>预期效果</th>
                <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center', width: '10%' }}>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: 'var(--spacing-sm)' }}>
                  <span style={{ padding: '2px 8px', background: 'var(--danger)', color: 'white', borderRadius: 'var(--radius-sm)', fontSize: '0.75em', fontWeight: 600 }}>P0</span>
                </td>
                <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>队列A引流判定错误率高（186次）</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>
                  1. 组织专项培训（引流标准）<br/>
                  2. 补充典型案例20个<br/>
                  3. 每日复盘机制
                </td>
                <td style={{ padding: 'var(--spacing-sm)' }}>培训负责人A</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>2026-04-25</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>错误降至 &lt;50次/周</td>
                <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                  <span style={{ padding: '4px 8px', background: 'var(--warning-bg)', color: 'var(--warning)', borderRadius: 'var(--radius-sm)', fontSize: '0.75em' }}>进行中</span>
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: 'var(--spacing-sm)' }}>
                  <span style={{ padding: '2px 8px', background: 'var(--danger)', color: 'white', borderRadius: 'var(--radius-sm)', fontSize: '0.75em', fontWeight: 600 }}>P0</span>
                </td>
                <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>队列B低质内容判定不一致（112次）</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>
                  1. 优化低质判定标准<br/>
                  2. 统一判定口径<br/>
                  3. 增加边界case
                </td>
                <td style={{ padding: 'var(--spacing-sm)' }}>标准负责人B</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>2026-04-28</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>判定一致性 &gt;90%</td>
                <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                  <span style={{ padding: '4px 8px', background: 'var(--info-bg)', color: 'var(--info)', borderRadius: 'var(--radius-sm)', fontSize: '0.75em' }}>计划中</span>
                </td>
              </tr>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: 'var(--spacing-sm)' }}>
                  <span style={{ padding: '2px 8px', background: 'var(--warning)', color: 'white', borderRadius: 'var(--radius-sm)', fontSize: '0.75em', fontWeight: 600 }}>P1</span>
                </td>
                <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>公众号广告识别错误（106次）</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>
                  1. 补充广告识别培训<br/>
                  2. 优化数据展示<br/>
                  3. 增加辅助判断工具
                </td>
                <td style={{ padding: 'var(--spacing-sm)' }}>产品负责人C</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>2026-05-05</td>
                <td style={{ padding: 'var(--spacing-sm)' }}>错误降至 &lt;30次/周</td>
                <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                  <span style={{ padding: '4px 8px', background: 'var(--info-bg)', color: 'var(--info)', borderRadius: 'var(--radius-sm)', fontSize: '0.75em' }}>计划中</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 快速操作 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">⚡ 快速操作</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)', display: 'flex', gap: 'var(--spacing-sm)', flexWrap: 'wrap' }}>
          <a href="/details?error_type=评论引流判定" className="button button-primary" style={{ textDecoration: 'none' }}>
            查看引流错误明细
          </a>
          <a href="/details?error_type=低质内容判定" className="button" style={{ textDecoration: 'none' }}>
            查看低质错误明细
          </a>
          <a href="/details?queue_name=视频号评论队列A" className="button" style={{ textDecoration: 'none' }}>
            查看队列A明细
          </a>
          <a href="/monitor" className="button" style={{ textDecoration: 'none' }}>
            返回实时监控
          </a>
        </div>
      </div>
    </PageTemplate>
  );
}
