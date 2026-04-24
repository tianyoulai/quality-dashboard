"""Markdown 文件存档格式化器 -- 完整版（保存到 deliverables/）。

比企微卡片版更详细，包含完整的处理动作建议和队列明细。
"""
from __future__ import annotations

from reports.engine import ReportResult, ACC_TARGET


def format_daily_markdown(r: ReportResult) -> str:
    """日报 → 完整 Markdown 文件。"""
    if not r.has_data:
        return f"# 质检日报 | {r.report_date}\n\n无数据。"

    lines: list[str] = []
    lines.append(f"# 📊 评论业务质检日报 | {r.report_date}")
    lines.append(f"正确率目标：{r.target:.2f}%")
    lines.append("")

    # 一、今日结论
    lines.append("## 一、今日结论")
    unqual = [s for g in r.groups for s in g.subs if not s.is_ok]
    if not unqual:
        lines.append(f"✅ 今日整体正确率 **{r.acc:.2f}%**，达标。各业务线表现平稳。")
    else:
        names = [f"{s.name}（{s.acc:.2f}%）" for s in unqual]
        lines.append(f"🔴 今日整体正确率 **{r.acc:.2f}%**，{'、'.join(names)} 未达标。")
    if r.acc_change_pp is not None and abs(r.acc_change_pp) >= 0.1:
        lines.append(f"较昨日 {'上升' if r.acc_change_pp > 0 else '下降'} **{abs(r.acc_change_pp):.2f}pp**。")
    if r.volume_change_pct is not None and abs(r.volume_change_pct) >= 15:
        lines.append(f"质检量较昨日变化 **{r.volume_change_pct:+.0f}%**，请确认是否为业务正常波动。")
    lines.append("")

    # 二、分组表现
    lines.append("## 二、分组表现")
    lines.append("| 业务组 | 正确率 | 质检量 | 出错 | 错判 | 漏判 | 状态 |")
    lines.append("|:--:|:--:|--:|--:|--:|--:|:--:|")
    for g in r.groups:
        lines.append(f"| **{g.name}** | {g.acc:.2f}% | {g.qa_cnt:,} | {g.error_cnt} | {g.cuopan} | {g.loupan} | {g.flag} |")
        for s in g.subs:
            lines.append(f"| {s.name} | {s.acc:.2f}% | {s.qa_cnt:,} | {s.error_cnt} | {s.cuopan} | {s.loupan} | {s.flag} |")
    if r.absent_groups:
        lines.append(f"\n> {'、'.join(r.absent_groups)} 当日无质检数据。")
    lines.append("")

    # 三、出错队列 TOP10
    if r.top_error_queues:
        lines.append("## 三、出错队列 TOP10")
        lines.append("| 队列 | 所属 | 错误数 | 错判 | 漏判 |")
        lines.append("|:--|:--|--:|--:|--:|")
        for q in r.top_error_queues:
            lines.append(f"| {q.queue} | {q.sub_biz} | {q.err_cnt} | {q.cuopan} | {q.loupan} |")
        lines.append("")

    # 四、错误类型
    if r.top_error_types:
        lines.append("## 四、错误类型 TOP5")
        for t in r.top_error_types:
            lines.append(f"- {t['error_type']}：**{t['cnt']}** 条")
        lines.append("")

    # 五、AI 洞察
    if r.ai_insight:
        lines.append("## 五、AI 洞察")
        lines.append(r.ai_insight)
        lines.append("")

    # 六、告警
    lines.append("## 六、告警联动")
    if r.alerts.total > 0:
        lines.append(f"- 当日告警：P0 {r.alerts.p0} / P1 {r.alerts.p1} / P2 {r.alerts.p2}")
    else:
        lines.append("- 当日无告警。")
    if r.yesterday_alerts.total > 0 and r.alerts.total == 0:
        lines.append(f"- 昨日告警回顾：P0 {r.yesterday_alerts.p0} / P1 {r.yesterday_alerts.p1} / P2 {r.yesterday_alerts.p2}")
    lines.append("")

    # 申诉
    if r.total_appealed > 0:
        lines.append("## 七、申诉情况")
        lines.append(f"申诉 {r.total_appealed} 条，改判 {r.total_appeal_reversed} 条（改判率 {r.appeal_rev_rate:.0f}%）。")
        lines.append("")

    if r.dashboard_url:
        lines.append("---")
        lines.append(f"🔗 [查看完整看板]({r.dashboard_url})")

    return "\n".join(lines)


def format_weekly_markdown(r: ReportResult) -> str:
    """周报 → 完整 Markdown 文件。"""
    if not r.has_data:
        return f"# 质检周报 | {r.week_start} ~ {r.week_end}\n\n无数据。"

    lines: list[str] = []
    lines.append(f"# 📈 评论业务质检周报 | {r.week_start} ~ {r.week_end}")
    lines.append(f"正确率目标：{r.target:.2f}%")
    lines.append("")

    # 总览
    lines.append("## 一、周度总览")
    lines.append(f"- 正确率：**{r.acc:.2f}%**")
    if r.week_over_week_acc_pp is not None:
        lines.append(f"- 周环比：**{r.week_over_week_acc_pp:+.2f}pp**（上周 {r.last_week_acc:.2f}%）")
    lines.append(f"- 总质检量：**{r.total_qa:,}**")
    lines.append(f"- 总出错：**{r.total_error}**（错判 {r.total_cuopan}，漏判 {r.total_loupan}）")
    lines.append("")

    # 每日趋势
    if r.daily_trend:
        lines.append("## 二、每日趋势")
        lines.append("| 日期 | 正确率 | 质检量 |")
        lines.append("|:--:|:--:|--:|")
        for day in r.daily_trend:
            lines.append(f"| {day['date']} | {day['acc']:.2f}% | {day['qa_cnt']:,} |")
        lines.append("")

    # 分组
    lines.append("## 三、分组表现")
    lines.append("| 业务组 | 正确率 | 质检量 | 出错 | 状态 |")
    lines.append("|:--:|:--:|--:|--:|:--:|")
    for g in r.groups:
        lines.append(f"| **{g.name}** | {g.acc:.2f}% | {g.qa_cnt:,} | {g.error_cnt} | {g.flag} |")
        for s in g.subs:
            lines.append(f"| {s.name} | {s.acc:.2f}% | {s.qa_cnt:,} | {s.error_cnt} | {s.flag} |")
    lines.append("")

    # AI 洞察
    if r.ai_insight:
        lines.append("## 四、AI 周度洞察")
        lines.append(r.ai_insight)
        lines.append("")

    # 告警
    if r.alerts.total > 0:
        lines.append("## 五、周告警汇总")
        lines.append(f"P0 {r.alerts.p0} / P1 {r.alerts.p1} / P2 {r.alerts.p2}（共 {r.alerts.total} 条）")
        lines.append("")

    if r.dashboard_url:
        lines.append("---")
        lines.append(f"🔗 [查看完整看板]({r.dashboard_url})")

    return "\n".join(lines)


def format_newcomer_markdown(r: ReportResult) -> str:
    """新人日报 → 完整 Markdown。"""
    if not r.has_data:
        return f"# 新人培训日报 | {r.report_date}\n\n无数据。"

    lines: list[str] = []
    lines.append(f"# 👶 新人培训日报 | {r.report_date}")
    lines.append(f"目标正确率：{r.target:.0f}%")
    lines.append("")

    lines.append("## 批次汇总")
    if r.newcomer_batches:
        lines.append("| 批次 | 团队 | 人数 | 质检量 | 正确率 |")
        lines.append("|:--|:--|--:|--:|:--:|")
        for b in r.newcomer_batches:
            flag = "✅" if b["acc"] >= r.target else "🔴"
            lines.append(f"| {b['batch_name']} | {b['team_name']} | {b['member_cnt']} | {b['qa_cnt']} | {b['acc']:.2f}% {flag} |")
    lines.append("")

    if r.newcomer_alerts:
        lines.append(f"## 异常人员（正确率 < {r.target:.0f}%）")
        lines.append("| 姓名 | 批次 | 质检量 | 正确率 |")
        lines.append("|:--|:--|--:|:--:|")
        for a in r.newcomer_alerts:
            lines.append(f"| {a['reviewer']} | {a['batch_name']} | {a['qa_cnt']} | {a['acc']:.2f}% |")
        lines.append("")

    if r.ai_insight:
        lines.append("## AI 洞察")
        lines.append(r.ai_insight)
        lines.append("")

    if r.dashboard_url:
        lines.append("---")
        lines.append(f"🔗 [查看完整看板 · 新人追踪]({r.dashboard_url})")

    return "\n".join(lines)


def format_markdown(r: ReportResult) -> str:
    """根据 report_type 选择格式化器。"""
    formatters = {
        "daily": format_daily_markdown,
        "weekly": format_weekly_markdown,
        "newcomer": format_newcomer_markdown,
    }
    fn = formatters.get(r.report_type, format_daily_markdown)
    return fn(r)
