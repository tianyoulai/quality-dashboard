import { PageTemplate } from '@/components/page-template';
import { SummaryCard } from '@/components/summary-card';
import { safeFetchApi } from '@/lib/api';
import { toDisplayDate } from '@/lib/formatters';

export const metadata = {
  title: '实时监控',
};

type SearchParams = Record<string, string | string[] | undefined>;

type PageProps = {
  searchParams?: Promise<SearchParams>;
};

/**
 * 🎯 实时数据监控页面
 * 
 * 核心目标：
 * 1. 快速发现数据异常（正确率突降、错误类型激增、队列异常）
 * 2. 实时监控关键指标（当日/昨日对比）
 * 3. 聚焦高风险问题（误判/漏判/申诉率）
 * 4. 支持快速下钻（点击跳转详情查询）
 */
export default async function RealTimeMonitorPage({ searchParams }: PageProps) {
  // 获取日期范围
  const metaResult = await safeFetchApi<Record<string, unknown>>('/api/v1/meta/date-range');
  const maxDate = metaResult.data?.max_date as string | undefined;
  const yesterdayDate = maxDate ? subtractDays(maxDate, 1) : '';

  // 获取当日汇总数据
  const todayResult = await safeFetchApi<Record<string, unknown>>(
    `/api/v1/dashboard?start_date=${maxDate}&end_date=${maxDate}`
  );
  const todayData = todayResult.data || {};

  // 获取昨日汇总数据（用于对比）
  const yesterdayResult = await safeFetchApi<Record<string, unknown>>(
    `/api/v1/dashboard?start_date=${yesterdayDate}&end_date=${yesterdayDate}`
  );
  const yesterdayData = yesterdayResult.data || {};

  // 计算关键指标
  const todayCorrectRate = Number(todayData.correct_rate || 0);
  const yesterdayCorrectRate = Number(yesterdayData.correct_rate || 0);
  const correctRateChange = todayCorrectRate - yesterdayCorrectRate;

  const todayTotalCount = Number(todayData.total_count || 0);
  const yesterdayTotalCount = Number(yesterdayData.total_count || 0);
  const countChange = todayTotalCount - yesterdayTotalCount;

  const todayMisjudgeRate = Number(todayData.misjudge_rate || 0);
  const yesterdayMisjudgeRate = Number(yesterdayData.misjudge_rate || 0);
  const misjudgeRateChange = todayMisjudgeRate - yesterdayMisjudgeRate;

  const todayAppealRate = Number(todayData.appeal_rate || 0);
  const yesterdayAppealRate = Number(yesterdayData.appeal_rate || 0);
  const appealRateChange = todayAppealRate - yesterdayAppealRate;

  // 判断异常状态
  const isCorrectRateAbnormal = correctRateChange < -5; // 正确率下降超过5%
  const isMisjudgeAbnormal = misjudgeRateChange > 2; // 误判率上升超过2%
  const isAppealAbnormal = appealRateChange > 3; // 申诉率上升超过3%

  return (
    <PageTemplate
      title="实时数据监控"
      subtitle={`${toDisplayDate(maxDate)} 实时数据 vs ${toDisplayDate(yesterdayDate)} 对比`}
    >
      {/* 异常告警（如果有） */}
      {(isCorrectRateAbnormal || isMisjudgeAbnormal || isAppealAbnormal) && (
        <div className="panel" style={{ background: 'var(--danger-bg)', borderColor: 'var(--danger)' }}>
          <h3 className="panel-title" style={{ color: 'var(--danger)' }}>🚨 异常告警</h3>
          
          <div style={{ marginTop: 'var(--spacing-md)' }}>
            {isCorrectRateAbnormal && (
              <div style={{ padding: 'var(--spacing-sm)', marginBottom: 'var(--spacing-xs)', background: 'white', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--danger)' }}>
                <strong style={{ color: 'var(--danger)' }}>⚠️ 正确率大幅下降</strong>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.875em', color: 'var(--text-muted)' }}>
                  当前正确率 {todayCorrectRate.toFixed(2)}%，较昨日下降 {Math.abs(correctRateChange).toFixed(2)}%
                </p>
              </div>
            )}
            
            {isMisjudgeAbnormal && (
              <div style={{ padding: 'var(--spacing-sm)', marginBottom: 'var(--spacing-xs)', background: 'white', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--danger)' }}>
                <strong style={{ color: 'var(--danger)' }}>⚠️ 误判率异常上升</strong>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.875em', color: 'var(--text-muted)' }}>
                  当前误判率 {todayMisjudgeRate.toFixed(2)}%，较昨日上升 {misjudgeRateChange.toFixed(2)}%
                </p>
              </div>
            )}
            
            {isAppealAbnormal && (
              <div style={{ padding: 'var(--spacing-sm)', background: 'white', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--danger)' }}>
                <strong style={{ color: 'var(--danger)' }}>⚠️ 申诉率异常上升</strong>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.875em', color: 'var(--text-muted)' }}>
                  当前申诉率 {todayAppealRate.toFixed(2)}%，较昨日上升 {appealRateChange.toFixed(2)}%
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 核心指标对比 */}
      <div className="panel" style={{ marginTop: isCorrectRateAbnormal || isMisjudgeAbnormal || isAppealAbnormal ? 'var(--spacing-lg)' : 0 }}>
        <h3 className="panel-title">📊 核心指标（当日 vs 昨日）</h3>
        
        <div className="grid-4" style={{ marginTop: 'var(--spacing-lg)' }}>
          <SummaryCard
            label="正确率"
            value={`${todayCorrectRate.toFixed(2)}%`}
            hint={`昨日: ${yesterdayCorrectRate.toFixed(2)}% ${correctRateChange >= 0 ? '↑' : '↓'} ${Math.abs(correctRateChange).toFixed(2)}%`}
            tone={isCorrectRateAbnormal ? 'danger' : (correctRateChange >= 0 ? 'success' : 'warning')}
          />

          <SummaryCard
            label="质检总量"
            value={todayTotalCount.toLocaleString()}
            hint={`昨日: ${yesterdayTotalCount.toLocaleString()} ${countChange >= 0 ? '↑' : '↓'} ${Math.abs(countChange).toLocaleString()}`}
            tone={Math.abs(countChange) > yesterdayTotalCount * 0.2 ? 'warning' : 'neutral'}
          />

          <SummaryCard
            label="误判率"
            value={`${todayMisjudgeRate.toFixed(2)}%`}
            hint={`昨日: ${yesterdayMisjudgeRate.toFixed(2)}% ${misjudgeRateChange >= 0 ? '↑' : '↓'} ${Math.abs(misjudgeRateChange).toFixed(2)}%`}
            tone={isMisjudgeAbnormal ? 'danger' : (misjudgeRateChange <= 0 ? 'success' : 'warning')}
          />

          <SummaryCard
            label="申诉率"
            value={`${todayAppealRate.toFixed(2)}%`}
            hint={`昨日: ${yesterdayAppealRate.toFixed(2)}% ${appealRateChange >= 0 ? '↑' : '↓'} ${Math.abs(appealRateChange).toFixed(2)}%`}
            tone={isAppealAbnormal ? 'danger' : (appealRateChange <= 0 ? 'success' : 'warning')}
          />
        </div>
      </div>

      {/* 队列质量排行（Top 10 最差队列） */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">⚠️ 重点关注队列（正确率 &lt;90%）</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            以下队列正确率低于 90%，需要重点关注和改进
          </p>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--card-bg)', borderBottom: '2px solid var(--border)' }}>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>排名</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>队列名称</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>正确率</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>质检量</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>误判率</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>漏判率</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>主要错误</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {/* 模拟数据，实际需要从 API 获取 */}
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)' }}>1</td>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>视频号评论队列A</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: 'var(--danger)', fontWeight: 600 }}>85.2%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>1,234</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>8.5%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>6.3%</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>引流判定</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                    <a href="/details?queue_name=视频号评论队列A" style={{ color: 'var(--primary)', textDecoration: 'none' }}>详情 →</a>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)' }}>2</td>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>视频号评论队列B</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: 'var(--danger)', fontWeight: 600 }}>87.8%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>982</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>7.2%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>5.0%</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>低质内容</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                    <a href="/details?queue_name=视频号评论队列B" style={{ color: 'var(--primary)', textDecoration: 'none' }}>详情 →</a>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)' }}>3</td>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>公众号评论队列</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: 'var(--warning)', fontWeight: 600 }}>89.1%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>756</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>6.5%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>4.4%</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>广告识别</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                    <a href="/details?queue_name=公众号评论队列" style={{ color: 'var(--primary)', textDecoration: 'none' }}>详情 →</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 错误类型分布（Top 5） */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">🎯 高频错误类型（Top 5）</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            聚焦高频错误，精准培训提升
          </p>
          
          <div className="grid-2" style={{ gap: 'var(--spacing-md)' }}>
            {/* 模拟数据 */}
            <div style={{ padding: 'var(--spacing-md)', background: 'var(--card-bg)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--danger)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <strong>评论引流判定</strong>
                <span style={{ color: 'var(--danger)', fontWeight: 700, fontSize: '1.25em' }}>342 次</span>
              </div>
              <div style={{ fontSize: '0.875em', color: 'var(--text-muted)', marginBottom: '8px' }}>
                占比: 28.5% | 误判率: 65% | 漏判率: 35%
              </div>
              <div style={{ fontSize: '0.875em' }}>
                主要队列: 视频号评论队列A、B
              </div>
              <div style={{ marginTop: '8px' }}>
                <a href="/details?error_type=评论引流判定" style={{ color: 'var(--primary)', fontSize: '0.875em', textDecoration: 'none' }}>查看明细 →</a>
              </div>
            </div>

            <div style={{ padding: 'var(--spacing-md)', background: 'var(--card-bg)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--warning)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <strong>低质内容判定</strong>
                <span style={{ color: 'var(--warning)', fontWeight: 700, fontSize: '1.25em' }}>218 次</span>
              </div>
              <div style={{ fontSize: '0.875em', color: 'var(--text-muted)', marginBottom: '8px' }}>
                占比: 18.2% | 误判率: 55% | 漏判率: 45%
              </div>
              <div style={{ fontSize: '0.875em' }}>
                主要队列: 视频号评论队列B、C
              </div>
              <div style={{ marginTop: '8px' }}>
                <a href="/details?error_type=低质内容判定" style={{ color: 'var(--primary)', fontSize: '0.875em', textDecoration: 'none' }}>查看明细 →</a>
              </div>
            </div>

            <div style={{ padding: 'var(--spacing-md)', background: 'var(--card-bg)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--warning)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <strong>广告识别</strong>
                <span style={{ color: 'var(--warning)', fontWeight: 700, fontSize: '1.25em' }}>156 次</span>
              </div>
              <div style={{ fontSize: '0.875em', color: 'var(--text-muted)', marginBottom: '8px' }}>
                占比: 13.0% | 误判率: 48% | 漏判率: 52%
              </div>
              <div style={{ fontSize: '0.875em' }}>
                主要队列: 公众号评论队列
              </div>
              <div style={{ marginTop: '8px' }}>
                <a href="/details?error_type=广告识别" style={{ color: 'var(--primary)', fontSize: '0.875em', textDecoration: 'none' }}>查看明细 →</a>
              </div>
            </div>

            <div style={{ padding: 'var(--spacing-md)', background: 'var(--card-bg)', borderRadius: 'var(--radius)', borderLeft: '3px solid var(--info)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <strong>违规内容</strong>
                <span style={{ color: 'var(--info)', fontWeight: 700, fontSize: '1.25em' }}>124 次</span>
              </div>
              <div style={{ fontSize: '0.875em', color: 'var(--text-muted)', marginBottom: '8px' }}>
                占比: 10.3% | 误判率: 42% | 漏判率: 58%
              </div>
              <div style={{ fontSize: '0.875em' }}>
                主要队列: 视频号评论队列C
              </div>
              <div style={{ marginTop: '8px' }}>
                <a href="/details?error_type=违规内容" style={{ color: 'var(--primary)', fontSize: '0.875em', textDecoration: 'none' }}>查看明细 →</a>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 审核人员表现（Top 10 最需关注） */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">👤 重点关注审核人（正确率 &lt;85%）</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875em', marginBottom: 'var(--spacing-md)' }}>
            以下审核人员正确率低于 85%，需要加强培训
          </p>
          
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--card-bg)', borderBottom: '2px solid var(--border)' }}>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>排名</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>审核人</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>正确率</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>审核量</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>误判率</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>漏判率</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>主要问题</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'left' }}>所属队列</th>
                  <th style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {/* 模拟数据 */}
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)' }}>1</td>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>张三</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: 'var(--danger)', fontWeight: 600 }}>78.5%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>456</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>12.8%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>8.7%</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>引流判定</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>视频号评论队列A</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                    <a href="/details?reviewer_name=张三" style={{ color: 'var(--primary)', textDecoration: 'none' }}>详情 →</a>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)' }}>2</td>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>李四</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: 'var(--danger)', fontWeight: 600 }}>81.2%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>389</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>10.5%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>8.3%</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>低质内容</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>视频号评论队列B</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                    <a href="/details?reviewer_name=李四" style={{ color: 'var(--primary)', textDecoration: 'none' }}>详情 →</a>
                  </td>
                </tr>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: 'var(--spacing-sm)' }}>3</td>
                  <td style={{ padding: 'var(--spacing-sm)', fontWeight: 600 }}>王五</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right', color: 'var(--warning)', fontWeight: 600 }}>83.7%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>312</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>9.2%</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'right' }}>7.1%</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>广告识别</td>
                  <td style={{ padding: 'var(--spacing-sm)' }}>公众号评论队列</td>
                  <td style={{ padding: 'var(--spacing-sm)', textAlign: 'center' }}>
                    <a href="/details?reviewer_name=王五" style={{ color: 'var(--primary)', textDecoration: 'none' }}>详情 →</a>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 快速操作 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)' }}>
        <h3 className="panel-title">⚡ 快速操作</h3>
        
        <div style={{ marginTop: 'var(--spacing-md)', display: 'flex', gap: 'var(--spacing-sm)', flexWrap: 'wrap' }}>
          <a href="/details" className="button button-primary" style={{ textDecoration: 'none' }}>
            📋 查看全部明细
          </a>
          <a href={`/details?start_date=${maxDate}&end_date=${maxDate}`} className="button" style={{ textDecoration: 'none' }}>
            📅 导出当日数据
          </a>
          <a href="/internal" className="button" style={{ textDecoration: 'none' }}>
            📊 内检看板
          </a>
          <a href="/newcomers" className="button" style={{ textDecoration: 'none' }}>
            👤 新人追踪
          </a>
        </div>
      </div>

      {/* 使用说明 */}
      <div className="panel" style={{ marginTop: 'var(--spacing-lg)', background: 'var(--info-bg)', borderColor: 'var(--info)' }}>
        <h3 className="panel-title" style={{ color: 'var(--info)' }}>💡 监控说明</h3>
        
        <ul style={{ marginLeft: 'var(--spacing-lg)', marginTop: 'var(--spacing-md)', lineHeight: 2 }}>
          <li><strong>异常告警</strong>：自动检测正确率/误判率/申诉率异常波动</li>
          <li><strong>队列排行</strong>：聚焦正确率 &lt;90% 的队列，优先改进</li>
          <li><strong>错误类型</strong>：统计高频错误，精准培训提升</li>
          <li><strong>人员表现</strong>：识别正确率 &lt;85% 的审核人，加强培训</li>
          <li><strong>快速下钻</strong>：点击「详情 →」跳转到明细查询页面</li>
        </ul>
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
