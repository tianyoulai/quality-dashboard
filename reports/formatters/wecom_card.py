"""企微群推送格式化器 -- 卡片式精简版（≤4096 字）。

设计原则：
- 一屏可读，手机端友好
- 数据密度高，去掉套话
- 用 emoji + 粗体 引导扫读
- 严格控制在企微 4096 字限制内
"""
from __future__ import annotations

from reports.engine import ReportResult, ACC_TARGET


# ── 工具 ──────────────────────────────────────────────────────
def _arrow(val: float | None) -> str:
    if val is None:
        return ""
    if val > 0.1:
        return f" ↑{val:+.2f}pp"
    if val < -0.1:
        return f" ↓{val:.2f}pp"
    return " →持平"


def _vol_tag(pct: float | None) -> str:
    if pct is None:
        return ""
    if abs(pct) < 5:
        return ""
    return f"（量{'↑' if pct > 0 else '↓'}{abs(pct):.0f}%）"


def _status_emoji(acc: float) -> str:
    if acc >= ACC_TARGET:
        return "✅"
    if acc >= ACC_TARGET - 0.5:
        return "🟡"
    return "🔴"


# ═══════════════════════════════════════════════════════════════
#  日报卡片
# ═══════════════════════════════════════════════════════════════

def format_daily_wecom(r: ReportResult) -> str:
    """日报 → 企微 Markdown 卡片（≤4096 字）。"""
    if not r.has_data:
        return f"📊 质检日报 | {r.report_date}\n\n⚠️ 今日无质检数据，请检查数据链路。"

    lines: list[str] = []

    # ── 标题栏 ──
    lines.append(f"📊 **评论质检日报** | {r.report_date}")
    lines.append(f"目标 {r.target:.2f}% | 总量 **{r.total_qa:,}**{_vol_tag(r.volume_change_pct)}")
    lines.append("---")

    # ── 核心指标（一行看全局） ──
    status = _status_emoji(r.acc)
    pp_str = _arrow(r.acc_change_pp)
    lines.append(f"{status} 正确率 **{r.acc:.2f}%**{pp_str} | 出错 **{r.total_error}** | 告警 P0:{r.alerts.p0} P1:{r.alerts.p1}")
    lines.append("")

    # ── 分组表格 ──
    lines.append("**分组表现**")
    lines.append("> | 组 | 正确率 | 量 | 错 | |")
    lines.append("> |:--|:--:|--:|--:|:--:|")
    for g in r.groups:
        lines.append(f"> | {g.name} | **{g.acc:.2f}%** | {g.qa_cnt:,} | {g.error_cnt} | {g.flag} |")
        if len(g.subs) > 1:
            for s in g.subs:
                lines.append(f"> | ├ {s.name} | {s.acc:.2f}% | {s.qa_cnt:,} | {s.error_cnt} | {s.flag} |")
    if r.absent_groups:
        lines.append(f"> *{'、'.join(r.absent_groups)}当日无数据*")
    lines.append("")

    # ── 风险聚焦（只展示未达标/承压的核心信息） ──
    risks = []
    for g in r.groups:
        for s in g.subs:
            if not s.is_ok:
                queues = [q for q in r.top_error_queues if q.sub_biz == s.name]
                q_str = f"，集中在「{queues[0].queue}」" if queues else ""
                risks.append(f"🔴 **{s.name}** {s.acc:.2f}%（差 {s.gap:.2f}pp）{q_str}")
            elif s.acc < ACC_TARGET + 0.5 and s.qa_cnt > 500:
                risks.append(f"🟡 **{s.name}** {s.acc:.2f}% 处于承压区间")

    if risks:
        lines.append("**风险**")
        for risk in risks[:4]:
            lines.append(risk)
        lines.append("")

    # ── 出错 TOP3 队列 ──
    if r.top_error_queues:
        lines.append("**出错 TOP3**")
        for q in r.top_error_queues[:3]:
            cp_lp = ""
            if q.cuopan > 0 or q.loupan > 0:
                parts = []
                if q.cuopan > 0:
                    parts.append(f"错判{q.cuopan}")
                if q.loupan > 0:
                    parts.append(f"漏判{q.loupan}")
                cp_lp = f"（{'，'.join(parts)}）"
            lines.append(f"- {q.queue} **{q.err_cnt}条**{cp_lp}")
        lines.append("")

    # ── AI 洞察 ──
    if r.ai_insight:
        insight = r.ai_insight
        if len(insight) > 350:
            insight = insight[:347] + "..."
        lines.append("**🤖 AI 洞察**")
        lines.append(f"> {insight}")
        lines.append("")

    # ── 告警 & 申诉 ──
    extras = []
    if r.alerts.total > 0:
        extras.append(f"告警 P0:{r.alerts.p0} P1:{r.alerts.p1} P2:{r.alerts.p2}")
    if r.total_appealed > 0:
        extras.append(f"申诉{r.total_appealed}条 改判{r.total_appeal_reversed}条（{r.appeal_rev_rate:.0f}%）")
    if r.yesterday_alerts.total > 0 and r.alerts.total == 0:
        extras.append(f"昨日告警回顾 P0:{r.yesterday_alerts.p0} P1:{r.yesterday_alerts.p1}")
    if extras:
        lines.append("---")
        lines.append(" | ".join(extras))

    # ── 尾部 ──
    if r.dashboard_url:
        lines.append(f"\n🔗 [查看完整看板]({r.dashboard_url})")

    result = "\n".join(lines)
    # 硬截断保护
    if len(result) > 4000:
        result = result[:3997] + "..."
    return result


# ═══════════════════════════════════════════════════════════════
#  周报卡片
# ═══════════════════════════════════════════════════════════════

def format_weekly_wecom(r: ReportResult) -> str:
    """周报 → 企微 Markdown 卡片。"""
    if not r.has_data:
        return f"📈 质检周报 | {r.week_start} ~ {r.week_end}\n\n⚠️ 本周无质检数据。"

    lines: list[str] = []

    # ── 标题 ──
    lines.append(f"📈 **评论质检周报** | {r.week_start} ~ {r.week_end}")
    lines.append(f"目标 {r.target:.2f}% | 周总量 **{r.total_qa:,}**")
    lines.append("---")

    # ── 核心指标 ──
    status = _status_emoji(r.acc)
    wow_str = ""
    if r.week_over_week_acc_pp is not None:
        wow_str = _arrow(r.week_over_week_acc_pp)
        if r.last_week_acc is not None:
            wow_str += f"（上周 {r.last_week_acc:.2f}%）"
    lines.append(f"{status} 周正确率 **{r.acc:.2f}%**{wow_str}")
    lines.append(f"出错 **{r.total_error}** | 错判 {r.total_cuopan} 漏判 {r.total_loupan}")
    lines.append("")

    # ── 每日趋势（ASCII mini 图） ──
    if r.daily_trend:
        lines.append("**每日走势**")
        for day in r.daily_trend:
            d_str = day["date"][5:]  # MM-DD
            bar_len = max(1, int((day["acc"] - 95) * 3))
            bar = "█" * min(bar_len, 15)
            lines.append(f"> {d_str} {bar} **{day['acc']:.2f}%** ({day['qa_cnt']:,})")
        lines.append("")

    # ── 分组 ──
    lines.append("**分组表现**")
    for g in r.groups:
        lines.append(f"- **{g.name}** {g.acc:.2f}% {g.flag}（量{g.qa_cnt:,} 错{g.error_cnt}）")
        if len(g.subs) > 1:
            for s in g.subs:
                lines.append(f"  - {s.name} {s.acc:.2f}% {s.flag}")
    lines.append("")

    # ── 告警汇总 ──
    if r.alerts.total > 0:
        lines.append(f"**周告警** P0:{r.alerts.p0} P1:{r.alerts.p1} P2:{r.alerts.p2}（共{r.alerts.total}条）")
        lines.append("")

    # ── AI 洞察 ──
    if r.ai_insight:
        insight = r.ai_insight
        if len(insight) > 400:
            insight = insight[:397] + "..."
        lines.append("**🤖 AI 周度洞察**")
        lines.append(f"> {insight}")
        lines.append("")

    if r.dashboard_url:
        lines.append(f"🔗 [查看完整看板]({r.dashboard_url})")

    result = "\n".join(lines)
    if len(result) > 4000:
        result = result[:3997] + "..."
    return result


# ═══════════════════════════════════════════════════════════════
#  新人日报卡片
# ═══════════════════════════════════════════════════════════════

def format_newcomer_wecom(r: ReportResult) -> str:
    """新人日报 → 企微 Markdown 卡片。"""
    if not r.has_data:
        return f"👶 新人培训日报 | {r.report_date}\n\n⚠️ 今日无新人质检数据。"

    lines: list[str] = []

    lines.append(f"👶 **新人培训日报** | {r.report_date}")
    lines.append(f"目标 {r.target:.0f}% | 总量 **{r.total_qa:,}**")
    lines.append("---")

    # ── 总览 ──
    status = "✅" if r.acc >= r.target else ("🟡" if r.acc >= r.target - 2 else "🔴")
    lines.append(f"{status} 正确率 **{r.acc:.2f}%** | 出错 **{r.total_error}**")
    lines.append("")

    # ── 批次明细 ──
    if r.newcomer_batches:
        lines.append("**批次表现**")
        for b in r.newcomer_batches:
            flag = "✅" if b["acc"] >= r.target else "🔴"
            lines.append(f"- {b['batch_name']} | {flag} {b['acc']:.2f}% | {b['member_cnt']}人 | 质检{b['qa_cnt']}条")
        lines.append("")

    # ── 异常人员 ──
    if r.newcomer_alerts:
        lines.append(f"**⚠️ 异常人员（<{r.target:.0f}%）**")
        for a in r.newcomer_alerts[:8]:
            lines.append(f"- {a['reviewer']}（{a['batch_name']}）**{a['acc']:.2f}%** 质检{a['qa_cnt']}条")
        if len(r.newcomer_alerts) > 8:
            lines.append(f"  ... 共{len(r.newcomer_alerts)}人")
        lines.append("")

    # ── AI 洞察 ──
    if r.ai_insight:
        insight = r.ai_insight
        if len(insight) > 300:
            insight = insight[:297] + "..."
        lines.append("**🤖 AI 洞察**")
        lines.append(f"> {insight}")
        lines.append("")

    if r.dashboard_url:
        lines.append(f"🔗 [查看完整看板 · 新人追踪]({r.dashboard_url})")

    result = "\n".join(lines)
    if len(result) > 4000:
        result = result[:3997] + "..."
    return result


# ═══════════════════════════════════════════════════════════════
#  统一入口
# ═══════════════════════════════════════════════════════════════

def format_wecom(r: ReportResult) -> str:
    """根据 report_type 自动选择格式化器。"""
    formatters = {
        "daily": format_daily_wecom,
        "weekly": format_weekly_wecom,
        "newcomer": format_newcomer_wecom,
    }
    fn = formatters.get(r.report_type, format_daily_wecom)
    return fn(r)
