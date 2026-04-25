"""总览页：告警驱动 + 组别经营 + 队列概览整合版。

设计原则：
- 一页看全：核心指标、告警、队列分布、趋势，一个页面都能看到
- 视觉舒适：留白充分、卡片圆角、颜色温和
- 交互自然：下探路径清晰、筛选便捷

布局结构：
- Hero 区：标题 + 模式切换 + 日期
- 第一行：核心指标卡片（4-5个关键指标）
- 第二行：告警区域（异常总览 + 告警列表）
- 第三行：组别卡片（横向滚动或网格）
- 第四行：队列概览（饼图 + 排名表）+ 趋势图
- 第五行：下探区域（队列表格 + 审核人表格）
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.dashboard_service import DashboardService

# 从拆分后的模块导入数据加载函数和共享常量
from views.dashboard._data import (
    get_data_date_range,
    load_dashboard_lite,
    load_prev_group_df,
    load_group_overview,
    load_group_detail,
    load_queue_overview_data,
    load_alert_history,
    load_qa_label_distribution_cached,
    load_qa_owner_distribution_cached,
)
from views.dashboard._shared import (
    GRAIN_LABELS,
    ALERT_STATUS_OPTIONS,
    COLOR_P0, COLOR_P1, COLOR_P2,
    COLOR_SUCCESS, COLOR_GOOD, COLOR_BAD, COLOR_WARN,
    calc_change,
    build_export_file_name,
    to_csv_bytes,
)

# 设计系统 v3.0（替换旧的 styles.py）
from utils.design_system import ds, COLORS
ds.inject_theme()

service = DashboardService()

# 颜色常量和工具函数已移至 views/dashboard/_shared.py
# 数据加载函数已移至 views/dashboard/_data.py


def _jump_to_detail(group: str | None = None, queue: str | None = None, auditor: str | None = None):
    """跳转到明细查询页，同时传递筛选条件。"""
    if group and group != "(全部)":
        st.session_state["detail_group_preset"] = group
    if queue and queue != "(全部)":
        st.session_state["detail_queue_preset"] = queue
    if auditor and auditor != "(全部)":
        st.session_state["detail_reviewer_preset"] = auditor
    # 传递当前日期范围
    if "selected_date" in dir():
        st.session_state["detail_quick_start"] = selected_date
        st.session_state["detail_quick_end"] = selected_date
    st.switch_page("pages/03_明细查询.py")


# ==================== Hero 区 ====================
ds.hero(
    "📊", "质培运营看板",
    "实时监控 · 智能告警 · 数据驱动",
    badges=["日看异常", "周看复发", "月看治理", "组别→队列→审核人→样本"],
)

# 全局错误边界
from utils.error_boundary import safe_section

# 获取数据日期范围，设置默认日期为数据最新日期
try:
    _data_min_date, _data_max_date = get_data_date_range()
    _default_date = _data_max_date if _data_max_date <= date.today() else date.today()
except Exception as _init_err:
    st.error(f"🚨 数据库连接异常，请稍后刷新重试。\n\n**错误信息**：`{_init_err}`")
    with st.expander("🔍 查看详细错误信息", expanded=False):
        import traceback as _tb
        st.code(_tb.format_exc(), language="text")
    if st.button("🔄 重试", key="retry_overview"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# 数据更新时间标注
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
    <div style="font-size: 0.78rem; color: {COLORS.text_muted};">
        📅 数据范围 <strong>{_data_min_date}</strong> ~ <strong>{_data_max_date}</strong> &nbsp;·&nbsp; 🕐 页面加载于 <strong>{date.today().strftime('%Y-%m-%d')}</strong>
    </div>
</div>
""", unsafe_allow_html=True)

# 快捷入口按钮（增强版）
st.markdown("#### ⚡ 快捷入口")
quick_col1, quick_col2, quick_col3, quick_col4 = st.columns([1, 1, 1, 1])
with quick_col1:
    if st.button("🚨 今日异常", use_container_width=True, help="快速定位今日 P0/P1 告警"):
        st.session_state["quick_mode"] = "alert"
        st.rerun()
with quick_col2:
    if st.button("📉 最差队列", use_container_width=True, help="查看本周正确率最低的队列"):
        st.session_state["quick_mode"] = "worst_queue"
        st.rerun()
with quick_col3:
    if st.button("🔄 申诉异常", use_container_width=True, help="查看申诉改判率高的组别"):
        st.session_state["quick_mode"] = "appeal"
        st.rerun()
with quick_col4:
    if st.button("👶 新人追踪", use_container_width=True, help="查看新人质检成长情况"):
        st.switch_page("pages/04_新人追踪.py")

# 模式切换 + 日期选择（一行搞定）
mode_col1, mode_col2, mode_col3, mode_col4 = st.columns([1, 1, 1, 2])
with mode_col1:
    grain = st.radio(
        "看板模式",
        options=["day", "week", "month"],
        format_func=lambda x: GRAIN_LABELS[x],
        horizontal=True,
        label_visibility="collapsed",
    )
with mode_col2:
    selected_date = st.date_input("业务日期", value=_default_date, label_visibility="collapsed")
with mode_col3:
    date_start = st.date_input("起始日期", value=selected_date - timedelta(days=6), label_visibility="collapsed", key="start_d")
with mode_col4:
    date_end = st.date_input("截止日期", value=selected_date, label_visibility="collapsed", key="end_d")

st.markdown("---")

# 缓存刷新按钮已由设计系统侧边栏统一提供

# ==================== 加载数据 ====================
# 💡 首屏轻量加载：只查 group_df + alerts_df（2次DB查询，原来7次）
try:
    payload = load_dashboard_lite(grain, selected_date)
except Exception as e:
    st.error(f"⚠️ 数据加载失败：{e}")
    st.info("请检查数据库连接是否正常，或尝试刷新缓存。")
    st.stop()
    
group_df: pd.DataFrame = payload["group_df"]
alerts_df: pd.DataFrame = payload["alerts_df"]
alert_summary: dict[str, int] = payload["alert_summary"]
alert_status_summary = service.summarize_alert_status(alerts_df)
alert_sla_summary = service.summarize_alert_sla(alerts_df)

# 预先获取选中的组别（用于队列数据过滤）
selected_group = st.session_state.get("selected_group")
if not selected_group and not group_df.empty:
    # 默认选中第一个组别
    selected_group = group_df.iloc[0]["group_name"]
    st.session_state["selected_group"] = selected_group

# 加载队列概览数据 → 延迟到第四行队列区域再加载（减少首屏阻塞）
# queue_data = load_queue_overview_data(...)  # moved below

# 加载前一天/上周/上月的数据用于环比对比
if grain == "day":
    prev_date = selected_date - timedelta(days=1)
elif grain == "week":
    prev_date = selected_date - timedelta(weeks=1)
else:
    prev_date = (selected_date.replace(day=1) - timedelta(days=1)).replace(day=1)

# 💡 环比数据：只查上期 group_df（1次DB查询，原来7次）
prev_group_df = load_prev_group_df(grain, prev_date)

if group_df.empty:
    st.warning("当前还没有 fact 数据。请先导入质检数据。")
    st.stop()

# calc_change 已从 views.dashboard._shared 导入

# ==================== 第一行：核心指标 ====================
ds.section("📈 核心指标概览")
total_qa = group_df["qa_cnt"].sum()
avg_raw_acc = (group_df["raw_accuracy_rate"] * group_df["qa_cnt"]).sum() / total_qa if total_qa > 0 else 0
avg_final_acc = (group_df["final_accuracy_rate"] * group_df["qa_cnt"]).sum() / total_qa if total_qa > 0 else 0
# 直接汇总错误量，避免计算精度损失
if "raw_error_cnt" in group_df.columns:
    total_raw_errors = int(group_df["raw_error_cnt"].sum())
else:
    total_raw_errors = int(total_qa * (100 - avg_raw_acc) / 100)
if "final_error_cnt" in group_df.columns:
    total_final_errors = int(group_df["final_error_cnt"].sum())
else:
    total_final_errors = int(total_qa * (100 - avg_final_acc) / 100)

# 核心指标卡片（设计系统 v3.0）
metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
with metric_col1:
    ds.metric_card("质检总量", f"{int(total_qa):,}", icon="📊", border_color=COLORS.primary)
with metric_col2:
    # 环比变化：原始正确率
    prev_total_qa = prev_group_df["qa_cnt"].sum() if not prev_group_df.empty else 0
    prev_avg_raw_acc = (prev_group_df["raw_accuracy_rate"] * prev_group_df["qa_cnt"]).sum() / prev_total_qa if prev_total_qa > 0 else None
    raw_acc_change_html = calc_change(avg_raw_acc, prev_avg_raw_acc)
    grain_label = "日" if grain == "day" else ("周" if grain == "week" else "月")
    ds.metric_card("原始正确率", f"{avg_raw_acc:.2f}%", delta=raw_acc_change_html, icon="✓",
                   color=COLORS.success if avg_raw_acc >= 99 else COLORS.danger,
                   border_color=COLORS.success if avg_raw_acc >= 99 else COLORS.danger)
with metric_col3:
    prev_avg_final_acc = (prev_group_df["final_accuracy_rate"] * prev_group_df["qa_cnt"]).sum() / prev_total_qa if prev_total_qa > 0 else None
    final_acc_change_html = calc_change(avg_final_acc, prev_avg_final_acc)
    ds.metric_card("最终正确率", f"{avg_final_acc:.2f}%", delta=final_acc_change_html, icon="✓✓",
                   color=COLORS.success if avg_final_acc >= 99 else COLORS.danger,
                   border_color=COLORS.success if avg_final_acc >= 99 else COLORS.danger)
with metric_col4:
    ds.metric_card("原始错误量", f"{total_raw_errors:,}", icon="✗",
                   color=COLORS.danger, border_color=COLORS.danger)
with metric_col5:
    ds.metric_card("终审错误量", f"{total_final_errors:,}", icon="✗✗",
                   color=COLORS.danger, border_color=COLORS.danger)

st.markdown("")  # 轻量间距

# ==================== 第二行：告警区域（设计系统 v3.0） ====================
ds.section("🚨 实时告警监控")
# 级别统计（横向紧凑展示）
alert_col1, alert_col2, alert_col3, alert_col4, alert_col5 = st.columns([1, 1, 1, 1, 2])
with alert_col1:
    ds.alert_badge("P0", alert_summary.get("P0", 0))
with alert_col2:
    ds.alert_badge("P1", alert_summary.get("P1", 0))
with alert_col3:
    ds.alert_badge("P2", alert_summary.get("P2", 0))
with alert_col4:
    ds.alert_badge("total", alert_summary.get("total", 0))
with alert_col5:
    ds.sla_status(
        alert_sla_summary.get("total_overdue", 0),
        alert_sla_summary.get("open_overdue", 0),
        alert_sla_summary.get("claimed_overdue", 0),
    )

# 告警详情折叠面板
if not alerts_df.empty:
    with st.expander("📋 查看告警详情", expanded=False):
        # 筛选
        filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 2])
        with filter_col1:
            severity_filters = st.multiselect("级别", options=["P0", "P1", "P2"], default=["P0", "P1"], label_visibility="collapsed", placeholder="级别", key="alert_severity")
        with filter_col2:
            status_filters = st.multiselect("状态", options=ALERT_STATUS_OPTIONS, default=["open"], format_func=service.get_alert_status_label, label_visibility="collapsed", placeholder="状态", key="alert_status")
        with filter_col3:
            keyword = st.text_input("关键词", placeholder="搜索...", label_visibility="collapsed", key="alert_keyword")
        
        filtered_alerts = service.filter_alerts(alerts_df, severity_filters, status_filters, ["system", "group", "queue"], keyword)
        
        if not filtered_alerts.empty:
            st.caption(f"共 {len(filtered_alerts)} 条告警")
            # 显示前 10 条
            display_alerts = filtered_alerts.head(10)
            alert_show = pd.DataFrame()
            alert_show["级别"] = display_alerts["severity"]
            alert_show["规则"] = display_alerts.apply(lambda r: r.get("rule_name") or r.get("rule_code", ""), axis=1)
            alert_show["对象"] = display_alerts["target_key"]
            alert_show["当前值"] = display_alerts.apply(lambda r: f"{r.get('metric_value', 0):.2f}%" if r.get('metric_value') else "—", axis=1)
            alert_show["阈值"] = display_alerts.apply(lambda r: f"{r.get('threshold_value', 0):.2f}%" if r.get('threshold_value') else "—", axis=1)
            alert_show["责任人"] = display_alerts["owner_name"]
            alert_show["状态"] = display_alerts["alert_status"].apply(service.get_alert_status_label)
            alert_show["时间"] = display_alerts["alert_date"]
            st.dataframe(alert_show, use_container_width=True, hide_index=True)
        else:
            st.info("当前筛选条件下无告警")
else:
    # 无告警时显示规则说明
    st.caption("💡 当前无活跃告警。告警规则：原始正确率 < 99% 触发 P1，< 98% 触发 P0。告警自动按日生成。")

st.markdown("")  # 轻量间距

# ==================== 第三行：组别卡片 ====================
ds.section("🏢 组别经营视图")
st.caption("💡 点击组别卡片可切换查看详细数据，卡片颜色代表达标状态")

# 计算 B 组整体
b_groups = group_df[group_df["group_name"].str.startswith("B组")]
if not b_groups.empty:
    b_total_qa = b_groups["qa_cnt"].sum()
    # 直接汇总正确量，避免用正确率反推
    b_total_raw_correct = b_groups["raw_correct_cnt"].sum() if "raw_correct_cnt" in b_groups.columns else (b_groups["raw_accuracy_rate"] * b_groups["qa_cnt"] / 100).sum()
    b_total_final_correct = b_groups["final_correct_cnt"].sum() if "final_correct_cnt" in b_groups.columns else (b_groups["final_accuracy_rate"] * b_groups["qa_cnt"] / 100).sum()
    # 计算错误量：优先用 raw_error_cnt，否则用 qa_cnt - raw_correct_cnt
    if "raw_error_cnt" in b_groups.columns:
        b_total_raw_error = b_groups["raw_error_cnt"].sum()
    else:
        b_total_raw_error = b_total_qa - b_total_raw_correct
    b_summary = pd.DataFrame([{
        "group_name": "B组",
        "raw_accuracy_rate": b_total_raw_correct / b_total_qa * 100 if b_total_qa > 0 else 0,
        "final_accuracy_rate": b_total_final_correct / b_total_qa * 100 if b_total_qa > 0 else 0,
        "qa_cnt": b_total_qa,
        "raw_error_cnt": int(b_total_raw_error),
        "misjudge_rate": (b_groups["misjudge_rate"] * b_groups["qa_cnt"] / 100).sum() / b_total_qa * 100 if b_total_qa > 0 else 0,
        "missjudge_rate": (b_groups["missjudge_rate"] * b_groups["qa_cnt"] / 100).sum() / b_total_qa * 100 if b_total_qa > 0 else 0,
    }])
    extended_df = pd.concat([group_df, b_summary], ignore_index=True)
else:
    extended_df = group_df

# 显示顺序
order_map = {"A组-评论": 1, "B组": 2, "B组-评论": 3, "B组-账号": 4}
extended_df["_order"] = extended_df["group_name"].map(order_map).fillna(99)
extended_df = extended_df.sort_values("_order").drop(columns="_order")

# 显示所有组别卡片（增加悬停效果和阴影）
display_groups = extended_df.head(4)
group_cols = st.columns(len(display_groups))

# 获取当前选中的组别（已在前面初始化）
selected_group = st.session_state.get("selected_group")

for idx, (_, row) in enumerate(display_groups.iterrows()):
    group_name = row["group_name"]
    raw_rate = row["raw_accuracy_rate"]
    final_rate = row["final_accuracy_rate"]
    qa_cnt = int(row["qa_cnt"])
    # 直接从 mart 表读取错误量，避免计算精度损失
    raw_error_cnt_val = row.get("raw_error_cnt")
    if pd.isna(raw_error_cnt_val):
        # 如果没有 raw_error_cnt，用 qa_cnt - raw_correct_cnt 计算
        raw_correct = row.get("raw_correct_cnt", qa_cnt)
        raw_error_cnt = int(qa_cnt - raw_correct)
    else:
        raw_error_cnt = int(raw_error_cnt_val)
    
    # 获取前一天的环比数据
    prev_row = prev_group_df[prev_group_df["group_name"] == group_name]
    prev_raw_rate = prev_row.iloc[0]["raw_accuracy_rate"] if not prev_row.empty else None
    prev_final_rate = prev_row.iloc[0]["final_accuracy_rate"] if not prev_row.empty else None
    
    # 计算环比变化
    raw_change = calc_change(raw_rate, prev_raw_rate)
    final_change = calc_change(final_rate, prev_final_rate)
    
    # 使用设计系统的卡片样式方案
    is_selected = (group_name == selected_group)
    style = ds.group_card_style(raw_rate, is_selected)
    display_name = "B组（整体）" if group_name == "B组" else group_name
    
    with group_cols[idx]:
        st.markdown(
            f"""
            <div class="ds-card" style="background: {style['bg']}; border: {style['border']}; box-shadow: {style['shadow']}; min-height: 180px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                    <div style="font-weight: 700; font-size: 1.1rem; color: {COLORS.text_primary};">{display_name}</div>
                    {ds.status_chip(f"{style['icon']} {style['text']}", "success" if raw_rate >= 99 else ("warning" if raw_rate >= 98 else "danger"))}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.5rem;">
                    <div style="background: white; padding: 0.75rem; border-radius: 0.5rem; text-align: center; border: 1px solid {COLORS.border};">
                        <div style="font-size: 0.7rem; color: {COLORS.text_secondary}; margin-bottom: 0.25rem;">原始正确率</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: {COLORS.success if raw_rate >= 99 else COLORS.danger};">{raw_rate:.2f}%</div>
                        <div style="font-size: 0.65rem; margin-top: 0.25rem; height: 0.9rem;">{raw_change}</div>
                    </div>
                    <div style="background: white; padding: 0.75rem; border-radius: 0.5rem; text-align: center; border: 1px solid {COLORS.border};">
                        <div style="font-size: 0.7rem; color: {COLORS.text_secondary}; margin-bottom: 0.25rem;">最终正确率</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: {COLORS.success if final_rate >= 99 else COLORS.danger};">{final_rate:.2f}%</div>
                        <div style="font-size: 0.65rem; margin-top: 0.25rem; height: 0.9rem;">{final_change}</div>
                    </div>
                    <div style="background: white; padding: 0.75rem; border-radius: 0.5rem; text-align: center; border: 1px solid {COLORS.border};">
                        <div style="font-size: 0.7rem; color: {COLORS.text_secondary}; margin-bottom: 0.25rem;">质检量</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: {COLORS.text_primary};">{qa_cnt:,}</div>
                    </div>
                    <div style="background: white; padding: 0.75rem; border-radius: 0.5rem; text-align: center; border: 1px solid {COLORS.border};">
                        <div style="font-size: 0.7rem; color: {COLORS.text_secondary}; margin-bottom: 0.25rem;">原始错误量</div>
                        <div style="font-size: 1.1rem; font-weight: 700; color: {COLORS.danger};">{raw_error_cnt:,}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(f"🔍 查看详情", key=f"btn_{group_name}", use_container_width=True):
            st.session_state["selected_group"] = group_name
            st.rerun()

st.markdown("---")

# ==================== 第四行：队列概览 + 趋势 ====================
# 💡 延迟加载队列数据（首屏只需 group_df + alerts_df + prev_group_df）
queue_data = load_queue_overview_data(grain, date_start, date_end, selected_group)
queue_df = queue_data["queue_df"]
trend_df = queue_data["trend_df"]

queue_col, trend_col = st.columns([1, 1.2])

with queue_col:
    st.markdown("#### 🥧 队列抽检分布")
    if not queue_df.empty:
        # 饼图：取前 8 队列
        top_n = 8
        if len(queue_df) > top_n:
            top_queues = queue_df.head(top_n).copy()
            other_total = queue_df.iloc[top_n:]["total_qa_cnt"].sum()
            other_row = pd.DataFrame([{"queue_name": "其他", "total_qa_cnt": other_total}])
            pie_df = pd.concat([top_queues, other_row], ignore_index=True)
        else:
            pie_df = queue_df
        
        fig_pie = px.pie(pie_df, values="total_qa_cnt", names="queue_name", hole=0.4)
        
        # 计算总量用于占比计算
        total_qa = pie_df["total_qa_cnt"].sum()
        
        # 自定义 hover 显示：名称、占比、量级
        fig_pie.update_traces(
            textposition="inside", 
            textinfo="percent+label", 
            textfont_size=11,
            hovertemplate="<b>%{label}</b><br>占比: %{percent}<br>量级: %{value:,} 条<extra></extra>"
        )
        fig_pie.update_layout(**ds.chart_layout(height=300), showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # 添加说明
        st.caption(f"💡 共 {len(queue_df)} 个队列，展示前 {top_n} 个")
    else:
        st.info("暂无队列数据")

with trend_col:
    st.markdown("#### 📈 正确率趋势")
    # 快捷时间范围切换
    _trend_range_labels = {"7天": 7, "14天": 14, "30天": 30, "全部": None}
    _trend_cols = st.columns(len(_trend_range_labels))
    if "trend_range" not in st.session_state:
        st.session_state["trend_range"] = "全部"
    for i, (label, days) in enumerate(_trend_range_labels.items()):
        with _trend_cols[i]:
            is_sel = st.session_state["trend_range"] == label
            if st.button(label, key=f"trend_range_{label}", use_container_width=True, type="primary" if is_sel else "secondary"):
                st.session_state["trend_range"] = label
                st.rerun()
    
    if not trend_df.empty:
        trend_df["anchor_date"] = pd.to_datetime(trend_df["anchor_date"])
        # 根据选择的范围过滤数据
        _selected_days = _trend_range_labels[st.session_state["trend_range"]]
        if _selected_days is not None:
            _cutoff = trend_df["anchor_date"].max() - pd.Timedelta(days=_selected_days)
            trend_plot_df = trend_df[trend_df["anchor_date"] >= _cutoff].copy()
        else:
            trend_plot_df = trend_df.copy()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_plot_df["anchor_date"], y=trend_plot_df["final_accuracy_rate"],
            mode="lines+markers", name="最终正确率",
            line=dict(color=COLOR_SUCCESS, width=3), marker=dict(size=8),
            text=[f"{v:.2f}%" for v in trend_plot_df["final_accuracy_rate"]],
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>最终正确率: %{text}<extra></extra>"
        ))
        fig.add_trace(go.Scatter(
            x=trend_plot_df["anchor_date"], y=trend_plot_df["raw_accuracy_rate"],
            mode="lines+markers", name="原始正确率",
            line=dict(color=COLORS.text_muted, width=2, dash="dot"), marker=dict(size=6),
            text=[f"{v:.2f}%" for v in trend_plot_df["raw_accuracy_rate"]],
            hovertemplate="<b>%{x|%Y-%m-%d}</b><br>原始正确率: %{text}<extra></extra>"
        ))
        fig.add_hline(y=99.0, line_dash="dash", line_color=COLOR_WARN, annotation_text="目标 99%", annotation_position="right")
        _layout_trend = ds.chart_layout(height=300)
        _layout_trend["yaxis"] = {**_layout_trend.get("yaxis", {}), "range": [95, 100.5], "title": "正确率 (%)"}
        _layout_trend["xaxis"] = {**_layout_trend.get("xaxis", {}), "tickformat": "%Y-%m-%d", "tickangle": -45}
        fig.update_layout(**_layout_trend)
        # 支持点击交互
        clicked = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="trend_chart")
        
        # 处理点击事件
        if clicked and clicked.get("selection"):
            selection = clicked["selection"]
            if selection.get("point_indices"):
                clicked_idx = selection["point_indices"][0]
                if clicked_idx < len(trend_plot_df):
                    clicked_date = trend_plot_df.iloc[clicked_idx]["anchor_date"]
                    _click_col1, _click_col2 = st.columns([2, 1])
                    with _click_col1:
                        st.info(f"💡 选中了 **{clicked_date.strftime('%Y-%m-%d')}**")
                    with _click_col2:
                        if st.button("🔍 查看该日明细", key="trend_goto_detail", use_container_width=True):
                            st.session_state["detail_group_preset"] = selected_group
                            st.session_state["detail_quick_start"] = clicked_date.date() if hasattr(clicked_date, 'date') else clicked_date
                            st.session_state["detail_quick_end"] = clicked_date.date() if hasattr(clicked_date, 'date') else clicked_date
                            st.switch_page("pages/03_明细查询.py")

        # 趋势概要统计
        if len(trend_plot_df) >= 2:
            latest = trend_plot_df.iloc[-1]
            earliest = trend_plot_df.iloc[0]
            avg_final = trend_plot_df["final_accuracy_rate"].mean()
            min_final = trend_plot_df["final_accuracy_rate"].min()
            min_date = trend_plot_df.loc[trend_plot_df["final_accuracy_rate"].idxmin(), "anchor_date"]
            _ts1, _ts2, _ts3 = st.columns(3)
            _ts1.metric("区间均值", f"{avg_final:.2f}%")
            _ts2.metric("区间最低", f"{min_final:.2f}%", help=f"出现于 {min_date.strftime('%Y-%m-%d')}")
            delta_val = latest["final_accuracy_rate"] - earliest["final_accuracy_rate"]
            _ts3.metric("区间变化", f"{delta_val:+.2f}%")
    else:
        st.info("暂无趋势数据")

st.markdown("")  # 轻量间距

# ==================== 第五行：队列排名 + 下探 ====================
ds.section("🔍 数据下探分析")
st.caption("💡 通过选择队列和审核人，逐层下探到具体问题样本")

# 💡 性能优化：下探数据按需加载（点击"加载详情"后才查DB）
# 原来这里直接调 load_group_detail 触发 8 次 DB 查询
# 现在改为先用 queue_df（已加载）做队列选择，审核人等下探数据点击后加载
_detail_loaded = st.session_state.get("_detail_loaded", False)

# 队列和审核人选择器（优化布局）
select_col1, select_col2, select_col3 = st.columns([1.5, 1.5, 2])
with select_col1:
    # 用已有的 queue_df 构建队列选项，避免额外 DB 查询
    if not queue_df.empty:
        _sorted_queues = queue_df.sort_values("total_qa_cnt", ascending=False)["queue_name"].tolist()
        queue_options = ["(全部)"] + _sorted_queues
    else:
        queue_options = ["(全部)"]
    selected_queue = st.selectbox("🎯 选择队列（按质检量排序）", options=queue_options, key="queue_selector", label_visibility="visible")
with select_col2:
    # 审核人需要 DB 查询，延迟到用户点击加载
    if _detail_loaded:
        detail_payload = load_group_detail(grain, selected_date, selected_group, 
                                           selected_queue if selected_queue != "(全部)" else None, 
                                           None, None, None)
        detail_auditor_df = detail_payload["auditor_df"]
        detail_queue_df = detail_payload["queue_df"]
        auditor_options = ["(全部)"] + detail_auditor_df["reviewer_name"].tolist() if not detail_auditor_df.empty else ["(全部)"]
    else:
        detail_auditor_df = pd.DataFrame()
        detail_queue_df = pd.DataFrame()
        auditor_options = ["(全部)"]
    selected_auditor = st.selectbox("👤 选择审核人", options=auditor_options, key="auditor_selector", label_visibility="visible")
with select_col3:
    # 面包屑导航（设计系统 v3.0）
    breadcrumb_items = [(selected_group, COLORS.primary)]
    if selected_queue != "(全部)":
        breadcrumb_items.append((selected_queue, COLORS.success))
    if selected_auditor != "(全部)":
        breadcrumb_items.append((selected_auditor, COLORS.warning))
    ds.breadcrumb(breadcrumb_items)

# 加载下探数据按钮
if not _detail_loaded:
    if st.button("🔍 加载下探数据（队列排名 + 审核人 + 样本）", use_container_width=True, type="primary"):
        st.session_state["_detail_loaded"] = True
        st.rerun()
    st.caption("💡 点击上方按钮加载详细数据，首屏仅展示核心指标和趋势，加载更快")
else:
    # 快捷筛选按钮（带选中状态高亮）
    st.markdown("##### ⚡ 快捷筛选")
    _current_filter = st.session_state.get("quick_filter")
    quick_filter_col1, quick_filter_col2, quick_filter_col3, quick_filter_col4, _ = st.columns([1.2, 1.2, 1.2, 1.2, 0.8])
    with quick_filter_col1:
        if st.button("🔴 错误量TOP5", use_container_width=True, help="筛选错误量最多的5个队列", type="primary" if _current_filter == "error_top5" else "secondary"):
            st.session_state["quick_filter"] = "error_top5"
            st.rerun()
    with quick_filter_col2:
        if st.button("📉 正确率<99%", use_container_width=True, help="筛选正确率低于99%的队列", type="primary" if _current_filter == "low_rate" else "secondary"):
            st.session_state["quick_filter"] = "low_rate"
            st.rerun()
    with quick_filter_col3:
        if st.button("⚠️ 有错判/漏判", use_container_width=True, help="筛选有错判或漏判的队列", type="primary" if _current_filter == "has_judge_error" else "secondary"):
            st.session_state["quick_filter"] = "has_judge_error"
            st.rerun()
    with quick_filter_col4:
        if st.button("🔄 重置筛选", use_container_width=True, help="清除所有筛选条件"):
            st.session_state["quick_filter"] = None
            st.session_state["queue_selector"] = "(全部)"
            st.session_state["auditor_selector"] = "(全部)"
            st.rerun()

    # 快捷筛选当前状态提示
    if _current_filter:
        filter_labels = {"error_top5": "错误量TOP5", "low_rate": "正确率<99%", "has_judge_error": "有错判/漏判"}
        st.caption(f"🔸 当前筛选：**{filter_labels.get(_current_filter, _current_filter)}**")

    # 根据选择重新加载数据
    if selected_queue != "(全部)" or selected_auditor != "(全部)":
        final_payload = load_group_detail(
            grain, selected_date, selected_group,
            selected_queue if selected_queue != "(全部)" else None,
            selected_auditor if selected_auditor != "(全部)" else None,
            None, None
        )
        final_auditor_df = final_payload["auditor_df"]
    else:
        final_auditor_df = detail_auditor_df

    rank_col, auditor_col = st.columns([1.2, 1])

    with rank_col:
        st.markdown("#### 🏆 队列正确率排名")
        if not detail_queue_df.empty:
            # 添加提示信息
            st.caption(f"共 {len(detail_queue_df)} 个队列，按最终正确率升序排列（问题队列优先展示）")
            
            queue_show = pd.DataFrame()
            queue_show["队列"] = detail_queue_df["queue_name"]
            queue_show["质检量"] = detail_queue_df["qa_cnt"]
            queue_show["出错量"] = detail_queue_df["final_error_cnt"]
            queue_show["原始正确率"] = detail_queue_df["raw_accuracy_rate"]
            queue_show["最终正确率"] = detail_queue_df["final_accuracy_rate"]
            queue_show["错判率"] = detail_queue_df["misjudge_rate"]
            queue_show["漏判率"] = detail_queue_df["missjudge_rate"]

            st.dataframe(
                queue_show,
                use_container_width=True,
                hide_index=True,
                height=320,
                column_config={
                    "队列": st.column_config.TextColumn("队列", width="medium"),
                    "质检量": st.column_config.NumberColumn("质检量", width="small", format="d"),
                    "出错量": st.column_config.NumberColumn("出错量", width="small", format="d"),
                    "原始正确率": st.column_config.NumberColumn("原始正确率", width="small", format="%.2f%%"),
                    "最终正确率": st.column_config.NumberColumn("最终正确率", width="small", format="%.2f%%"),
                    "错判率": st.column_config.NumberColumn("错判率", width="small", format="%.2f%%"),
                    "漏判率": st.column_config.NumberColumn("漏判率", width="small", format="%.2f%%"),
                }
            )
        else:
            st.info("暂无队列数据")

    with auditor_col:
        st.markdown("#### 👥 审核人视图")
        if not final_auditor_df.empty:
            total_auditors = len(final_auditor_df)
            default_show = 20
            
            # 控制展示数量
            show_all = st.session_state.get("show_all_auditors", False)
            display_df = final_auditor_df if show_all else final_auditor_df.head(default_show)
            
            showing_count = len(display_df)
            st.caption(f"共 {total_auditors} 位审核人，当前展示 {showing_count} 位，按最终正确率升序排列（需关注的审核人优先展示）")
            
            auditor_show = pd.DataFrame()
            auditor_show["审核人"] = display_df["reviewer_name"]
            auditor_show["质检量"] = display_df["qa_cnt"]
            auditor_show["原始正确率"] = display_df["raw_accuracy_rate"]
            auditor_show["最终正确率"] = display_df["final_accuracy_rate"]
            auditor_show["错判量"] = display_df["misjudge_cnt"]
            auditor_show["漏判量"] = display_df["missjudge_cnt"]

            st.dataframe(
                auditor_show,
                use_container_width=True,
                hide_index=True,
                height=320,
                column_config={
                    "审核人": st.column_config.TextColumn("审核人", width="medium"),
                    "质检量": st.column_config.NumberColumn("质检量", width="small", format="d"),
                    "原始正确率": st.column_config.NumberColumn("原始正确率", width="small", format="%.2f%%"),
                    "最终正确率": st.column_config.NumberColumn("最终正确率", width="small", format="%.2f%%"),
                    "错判量": st.column_config.NumberColumn("错判量", width="small", format="d"),
                    "漏判量": st.column_config.NumberColumn("漏判量", width="small", format="d"),
                }
            )
            # 加载更多 / 收起
            if total_auditors > default_show:
                _btn_col1, _btn_col2 = st.columns(2)
                with _btn_col1:
                    if not show_all:
                        if st.button(f"📋 显示全部 {total_auditors} 位审核人", key="show_all_auditors_btn", use_container_width=True):
                            st.session_state["show_all_auditors"] = True
                            st.rerun()
                    else:
                        if st.button("🔼 收起，只显示前20位", key="collapse_auditors_btn", use_container_width=True):
                            st.session_state["show_all_auditors"] = False
                            st.rerun()
                with _btn_col2:
                    if st.button("📋 在明细查询中查看样本", key="goto_detail", use_container_width=True, help="跳转到明细查询页，自动带入当前筛选条件"):
                        _jump_to_detail(selected_group, selected_queue, selected_auditor)
            else:
                # 审核人不超过20位时只显示跳转按钮
                if st.button("📋 在明细查询中查看样本", key="goto_detail", use_container_width=True, help="跳转到明细查询页，自动带入当前筛选条件"):
                    _jump_to_detail(selected_group, selected_queue, selected_auditor)
        else:
            st.info("暂无审核人数据")

    # ==================== 第五点五行：问题样本预览（下探闭环） ====================
    st.markdown("---")
    st.markdown("#### 🔬 问题样本预览")
    st.caption("💡 选择队列和审核人后，自动展示对应的错误样本，完成下探闭环")

    # 构建样本查询参数
    _sample_group = selected_group
    _sample_queue = selected_queue if selected_queue != "(全部)" else None
    _sample_auditor = selected_auditor if selected_auditor != "(全部)" else None

    # 只在选择了具体队列或审核人时展示样本
    if _sample_queue or _sample_auditor:
        _sample_payload = load_group_detail(
            grain, selected_date, _sample_group,
            _sample_queue, _sample_auditor, None, None
        )
        _sample_df = _sample_payload.get("sample_df", pd.DataFrame())
        _error_df = _sample_payload.get("error_df", pd.DataFrame())

        if not _sample_df.empty:
            _sc1, _sc2, _sc3 = st.columns(3)
            _sc1.metric("样本总量", f"{len(_sample_df):,}")
            _raw_err_cnt = (_sample_df["is_raw_correct"] == 0).sum() if "is_raw_correct" in _sample_df.columns else 0
            _sc2.metric("原始错误", f"{_raw_err_cnt:,}")
            _appeal_rev = (_sample_df["is_appeal_reversed"] == 1).sum() if "is_appeal_reversed" in _sample_df.columns else 0
            _sc3.metric("申诉改判", f"{_appeal_rev:,}")

            # 错误类型 TOP5
            if not _error_df.empty:
                with st.expander("📊 错误类型分布", expanded=False):
                    _err_show = pd.DataFrame()
                    _err_show["错误类型"] = _error_df["error_type"]
                    _err_show["数量"] = _error_df["issue_cnt"]
                    st.dataframe(_err_show.head(10), use_container_width=True, hide_index=True)

            # 样本明细表
            with st.expander(f"📋 样本明细（共 {len(_sample_df)} 条）", expanded=True):
                _cols_map = {
                    "biz_date": "日期", "queue_name": "队列", "reviewer_name": "审核人",
                    "raw_judgement": "审核人判定", "final_review_result": "质检判定",
                    "error_type": "错误类型", "error_reason": "错误归因",
                    "comment_text": "评论文本",
                }
                _avail_cols = [c for c in _cols_map if c in _sample_df.columns]
                _show_df = _sample_df[_avail_cols].rename(columns=_cols_map).head(50)
                st.dataframe(_show_df, use_container_width=True, hide_index=True, height=350)

                if len(_sample_df) > 50:
                    st.caption(f"💡 仅展示前 50 条，完整数据请前往「明细查询」页面")

                # 跳转到明细查询的按钮
                if st.button("🔍 在明细查询中查看完整数据", key="goto_detail_from_sample", use_container_width=True):
                        _jump_to_detail(selected_group, _sample_queue, _sample_auditor)
        else:
            st.info("当前筛选条件下无样本数据")
    else:
        st.info("👆 请在上方选择具体的队列或审核人，查看问题样本")

st.markdown("")  # 轻量间距

# ==================== 第六行：质检标签分布 + 质检员工作量 ====================
st.markdown("---")
ds.section("📊 质检维度分析")

# 💡 性能优化：维度分析放在折叠面板中按需加载
with st.expander("📊 查看质检标签分布 + 质检员工作量（点击展开加载）", expanded=False):
    st.caption("💡 了解质检标签分布和质检员工作量分布，帮助识别问题高发区域")

    label_col, owner_col = st.columns([1, 1])

    with label_col:
        st.markdown("#### 🏷️ 质检结果分布")
        label_df = load_qa_label_distribution_cached(grain, selected_date, selected_group, top_n=10)
        if not label_df.empty:
            # 添加统计信息
            total_labels = label_df["cnt"].sum()
            st.caption(f"前10个标签（按质检量降序），共 {total_labels:,} 条质检记录")
            
            # 使用水平条形图展示
            fig_label = px.bar(
                label_df.sort_values("cnt", ascending=True),
                x="cnt", y="label_name",
                orientation="h",
                text=label_df.sort_values("cnt", ascending=True)["pct"].apply(lambda x: f"{x:.1f}%"),
                color="cnt",
                color_continuous_scale="Blues"
            )
            fig_label.update_traces(textposition="outside", textfont_size=11)
            fig_label.update_layout(**ds.chart_layout(height=320), xaxis_title="质检量", yaxis_title="", showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig_label, use_container_width=True)
            
            # 补充：仅错误样本分布
            with st.expander("🔴 仅错误样本分布", expanded=False):
                error_label_df = load_qa_label_distribution_cached(grain, selected_date, selected_group, top_n=10)
                # 从整体标签中过滤出错误相关项（如果有err_cnt字段）
                if "err_cnt" in label_df.columns:
                    err_only = label_df[label_df["err_cnt"] > 0].sort_values("err_cnt", ascending=False)
                    if not err_only.empty:
                        fig_err = px.bar(
                            err_only, x="err_cnt", y="label_name", orientation="h",
                            text="err_cnt", color_discrete_sequence=[COLORS.danger]
                        )
                        fig_err.update_traces(textposition="outside")
                        fig_err.update_layout(**ds.chart_layout(height=250), xaxis_title="错误量", yaxis_title="")
                        st.plotly_chart(fig_err, use_container_width=True)
                    else:
                        st.success("🎉 所有标签均无错误记录")
                else:
                    st.caption("💡 暂无错误维度数据，可通过数据管理页导入更完整的数据")
        else:
            st.info("暂无标签数据")

    with owner_col:
        st.markdown("#### 👨‍💼 质检员工作量")
        owner_df = load_qa_owner_distribution_cached(grain, selected_date, selected_group, top_n=10)
        if not owner_df.empty:
            # 工作量概览指标
            total_qa_owners = owner_df["qa_cnt"].sum()
            owner_count = len(owner_df)
            avg_qa = total_qa_owners / owner_count if owner_count > 0 else 0
            max_qa = owner_df["qa_cnt"].max()
            min_qa = owner_df["qa_cnt"].min()
            # 均衡度 = 1 - (标准差/均值)，越接近1说明越均衡
            std_qa = owner_df["qa_cnt"].std()
            balance_score = max(0, 1 - std_qa / avg_qa) * 100 if avg_qa > 0 else 0
            balance_color = COLORS.success if balance_score >= 70 else (COLORS.warning if balance_score >= 40 else COLORS.danger)
            
            _ow_col1, _ow_col2, _ow_col3 = st.columns(3)
            with _ow_col1:
                st.metric("人均质检量", f"{avg_qa:,.0f}")
            with _ow_col2:
                st.metric("最大/最小", f"{max_qa:,.0f} / {min_qa:,.0f}")
            with _ow_col3:
                st.markdown(f"""
                <div style="text-align:center;">
                    <div style="font-size:0.75rem; color:{COLORS.text_secondary};">均衡度</div>
                    <div style="font-size:1.5rem; font-weight:700; color:{balance_color};">{balance_score:.0f}%</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.caption(f"前{owner_count}名质检员（按质检量降序）")
            
            # 表格展示
            owner_show = pd.DataFrame()
            owner_show["质检员"] = owner_df["owner_name"].apply(lambda x: x.split("-")[-1] if "-" in x else x)
            owner_show["质检量"] = owner_df["qa_cnt"].apply(lambda x: f"{int(x):,}")
            owner_show["正确率"] = owner_df["accuracy_rate"].apply(lambda x: f"{x:.2f}%")
            owner_show["出错量"] = owner_df["error_cnt"].apply(lambda x: f"{int(x):,}")
            
            st.dataframe(
                owner_show, 
                use_container_width=True, 
                hide_index=True, 
                height=280,
                column_config={
                    "质检员": st.column_config.TextColumn("质检员", width="medium"),
                    "质检量": st.column_config.TextColumn("质检量", width="small"),
                    "正确率": st.column_config.TextColumn("正确率", width="small"),
                    "出错量": st.column_config.TextColumn("出错量", width="small"),
                }
            )
        else:
            st.info("暂无质检员数据")

# ==================== 底部说明 ====================
st.markdown("---")

# 导出中心
with st.expander("📥 导出中心", expanded=False):
    st.caption("一键导出当前看板数据为 Excel 文件")
    _exp_col1, _exp_col2 = st.columns(2)
    with _exp_col1:
        if st.button("📊 导出当日报表 (Excel)", key="export_daily", use_container_width=True):
            try:
                from utils.export_center import export_daily_excel
                _export_data = load_group_overview(grain, selected_date)
                _xlsx_bytes = export_daily_excel(_export_data, selected_date)
                st.download_button(
                    "⬇️ 下载日报 Excel",
                    data=_xlsx_bytes,
                    file_name=f"quality_daily_{selected_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_daily_xlsx",
                )
            except Exception as e:
                st.error(f"导出失败: {e}")
    with _exp_col2:
        if st.button("📈 导出本周报表 (Excel)", key="export_weekly", use_container_width=True):
            try:
                from utils.export_center import export_weekly_excel
                _week_start = selected_date - timedelta(days=selected_date.weekday())
                _daily_list = []
                for i in range(7):
                    _d = _week_start + timedelta(days=i)
                    if _d <= selected_date:
                        _daily_list.append(load_group_overview("day", _d))
                _xlsx_bytes = export_weekly_excel(_daily_list, _week_start, selected_date)
                st.download_button(
                    "⬇️ 下载周报 Excel",
                    data=_xlsx_bytes,
                    file_name=f"quality_weekly_{_week_start}_{selected_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_weekly_xlsx",
                )
            except Exception as e:
                st.error(f"导出失败: {e}")

ds.footer([
    "<strong>💡 看板设计原则：</strong>异常先暴露 → 支持下探 → 沉淀培训动作",
    "<strong>🚨 告警规则：</strong>原始正确率 &lt; 99% 触发 P1 重要 · &lt; 98% 触发 P0 紧急 · 告警按日自动生成",
    "<strong>📊 数据口径：</strong>原始正确率 = 一审正确数/质检总量 · 最终正确率 = 终审正确数/质检总量",
    f"<span style='color: {COLORS.text_muted}; font-size: 0.78rem;'>数据每日自动更新 · 告警自动推送 · 支持 CSV 导出 · 环比对比基准为同粒度前一期</span>",
])