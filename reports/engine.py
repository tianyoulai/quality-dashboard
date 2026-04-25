"""统一报告引擎 -- 数据采集 → AI 洞察 → 格式化 → 推送。

核心数据结构 ReportResult 是所有格式化器的统一输入。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import DashboardRepository

# ── 常量 ─────────────────────────────────────────────────────
ACC_TARGET = 99.00
KNOWN_GROUPS = ["A组", "B组"]


# ── 数据结构 ──────────────────────────────────────────────────
@dataclass
class BizGroup:
    name: str
    qa_cnt: int = 0
    correct_cnt: int = 0
    error_cnt: int = 0
    cuopan: int = 0
    loupan: int = 0
    appealed: int = 0
    appeal_reversed: int = 0
    acc: float = 0.0
    subs: list[BizGroup] = field(default_factory=list)

    @property
    def flag(self) -> str:
        if self.acc >= ACC_TARGET:
            return "✅"
        if self.acc >= ACC_TARGET - 0.5:
            return "🟡"
        return "🔴"

    @property
    def is_ok(self) -> bool:
        return self.acc >= ACC_TARGET

    @property
    def gap(self) -> float:
        return round(ACC_TARGET - self.acc, 2) if self.acc < ACC_TARGET else 0.0


@dataclass
class ErrorQueue:
    mother_biz: str
    sub_biz: str
    queue: str
    err_cnt: int
    cuopan: int = 0
    loupan: int = 0


@dataclass
class AlertSummary:
    p0: int = 0
    p1: int = 0
    p2: int = 0

    @property
    def total(self) -> int:
        return self.p0 + self.p1 + self.p2


@dataclass
class ReportResult:
    """所有格式化器的统一输入数据结构。"""
    report_type: str  # "daily" | "weekly" | "newcomer"
    report_date: date
    has_data: bool = True
    target: float = ACC_TARGET

    # 总览
    total_qa: int = 0
    total_correct: int = 0
    total_error: int = 0
    total_cuopan: int = 0
    total_loupan: int = 0
    total_appealed: int = 0
    total_appeal_reversed: int = 0
    acc: float = 0.0
    appeal_rev_rate: float = 0.0

    # 环比
    yesterday_acc: float | None = None
    yesterday_qa: int | None = None
    volume_change_pct: float | None = None
    acc_change_pp: float | None = None

    # 分组
    groups: list[BizGroup] = field(default_factory=list)
    absent_groups: list[str] = field(default_factory=list)

    # 错误队列 TOP N
    top_error_queues: list[ErrorQueue] = field(default_factory=list)
    top_error_types: list[dict] = field(default_factory=list)

    # 告警
    alerts: AlertSummary = field(default_factory=AlertSummary)
    yesterday_alerts: AlertSummary = field(default_factory=AlertSummary)

    # 周报专属
    week_start: date | None = None
    week_end: date | None = None
    daily_trend: list[dict] = field(default_factory=list)
    week_over_week_acc_pp: float | None = None
    last_week_acc: float | None = None

    # 新人专属
    newcomer_batches: list[dict] = field(default_factory=list)
    newcomer_alerts: list[dict] = field(default_factory=list)

    # AI 洞察（在 engine 中填充）
    ai_insight: str = ""

    # 看板链接
    dashboard_url: str = ""

    # 原始 payload（给 AI 用）
    raw_payload: dict = field(default_factory=dict)


# ── 工具函数 ──────────────────────────────────────────────────
def _si(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _sf(val, d: int = 2) -> float:
    try:
        return round(float(val), d) if val is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


from utils.helpers import safe_pct as _safe_pct


# _load_settings 统一使用 jobs/_report_common.py 中的版本
from jobs._report_common import load_settings as _load_settings


# ── DeepSeek 4.0 Pro 调用 ────────────────────────────────────
def _call_deepseek(report: ReportResult, custom_prompt: str = "") -> str:
    """调用 DeepSeek 4.0 Pro API 生成 AI 洞察。"""
    import requests

    settings = _load_settings()
    ds_cfg = settings.get("deepseek", {})

    api_key = os.environ.get("DEEPSEEK_API_KEY", "") or ds_cfg.get("api_key", "")
    api_url = os.environ.get("DEEPSEEK_API_URL", "") or ds_cfg.get("api_url", "https://api.deepseek.com/v1/chat/completions")
    model_name = ds_cfg.get("model", "deepseek-reasoner")

    if not api_key:
        return ""

    # 构造精简数据
    data_brief = {
        "type": report.report_type,
        "date": str(report.report_date),
        "target": report.target,
        "acc": report.acc,
        "total_qa": report.total_qa,
        "total_error": report.total_error,
        "cuopan": report.total_cuopan,
        "loupan": report.total_loupan,
        "groups": [
            {
                "name": g.name,
                "acc": g.acc,
                "qa_cnt": g.qa_cnt,
                "error_cnt": g.error_cnt,
                "subs": [{"name": s.name, "acc": s.acc, "qa_cnt": s.qa_cnt, "error_cnt": s.error_cnt} for s in g.subs],
            }
            for g in report.groups
        ],
        "top_error_queues": [
            {"queue": q.queue, "sub_biz": q.sub_biz, "err_cnt": q.err_cnt}
            for q in report.top_error_queues[:5]
        ],
        "top_error_types": report.top_error_types[:5],
        "alerts": {"P0": report.alerts.p0, "P1": report.alerts.p1, "P2": report.alerts.p2},
    }
    if report.yesterday_acc is not None:
        data_brief["yesterday_acc"] = report.yesterday_acc
    if report.volume_change_pct is not None:
        data_brief["volume_change_pct"] = report.volume_change_pct
    if report.report_type == "weekly":
        data_brief["week_range"] = f"{report.week_start} ~ {report.week_end}"
        if report.last_week_acc is not None:
            data_brief["last_week_acc"] = report.last_week_acc
        data_brief["daily_trend"] = report.daily_trend

    data_str = json.dumps(data_brief, ensure_ascii=False, indent=2)

    system_prompt = """你是评论业务质检数据分析师（质培 owner 视角）。根据给定的质检数据生成一段精炼的 AI 洞察分析。

输出要求（严格遵守）：
1. 总长度控制在 280 字以内，不要超
2. 第一句给出整体判断：✅达标 / 🟡承压 / 🔴风险，附一句核心结论
3. 用 2-3 句话做归因分析：错误集中在哪个组/队列、是错判还是漏判主导、与昨日/上周对比的变化趋势
4. 如果正确率下降，尝试定位根因：是人员问题(某审核人)、队列问题(某队列集中出错)、还是类型问题(某类错误激增)
5. 最后给 2 条可执行的行动建议，格式为「① ... ② ...」，每条建议指向具体对象和动作
6. 关键数值加粗（用**包裹），使用企微 Markdown 格式
7. 不要重复罗列原始数据，只做分析和判断
8. 语气直接专业，禁止"请注意""建议关注""值得注意"等套话
9. 如果所有组都达标且无异常，简洁总结后给出预防性建议即可"""

    if custom_prompt:
        system_prompt += f"\n\n补充要求：{custom_prompt}"

    try:
        resp = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"质检数据：\n{data_str}"},
                ],
                "max_tokens": 600,
                "temperature": 0.2,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        # 清理 markdown 代码块包裹
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )
        return content
    except Exception as e:
        print(f"[DeepSeek] API 调用失败: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════
#  日报生成
# ═══════════════════════════════════════════════════════════════

def _query_sub_biz(repo: DashboardRepository, d: str) -> list[dict]:
    sql = """
        SELECT
            mother_biz, sub_biz,
            COUNT(*) AS qa_cnt,
            SUM(CASE WHEN is_raw_correct = 1 THEN 1 ELSE 0 END) AS raw_correct,
            SUM(CASE WHEN is_raw_correct = 0 AND (
                COALESCE(raw_judgement,'') LIKE '%%错判%%' OR COALESCE(error_type,'') LIKE '%%错判%%'
            ) THEN 1 ELSE 0 END) AS cuopan,
            SUM(CASE WHEN is_raw_correct = 0 AND (
                COALESCE(raw_judgement,'') LIKE '%%漏判%%' OR COALESCE(error_type,'') LIKE '%%漏判%%'
            ) THEN 1 ELSE 0 END) AS loupan,
            SUM(CASE WHEN is_raw_correct = 0 THEN 1 ELSE 0 END) AS error_total,
            SUM(CASE WHEN is_appealed = 1 THEN 1 ELSE 0 END) AS appealed,
            SUM(CASE WHEN is_appeal_reversed = 1 THEN 1 ELSE 0 END) AS appeal_reversed
        FROM vw_qa_base
        WHERE biz_date = %s
          AND COALESCE(mother_biz, '') != ''
          AND COALESCE(sub_biz, '') != ''
          AND mother_biz != '未识别'
        GROUP BY 1, 2
        ORDER BY 1, 2
    """
    df = repo.fetch_df(sql, [d])
    rows = []
    for _, r in df.iterrows():
        cnt = _si(r["qa_cnt"])
        rows.append({
            "mother_biz": r["mother_biz"],
            "sub_biz": r["sub_biz"],
            "qa_cnt": cnt,
            "raw_correct": _si(r["raw_correct"]),
            "cuopan": _si(r["cuopan"]),
            "loupan": _si(r["loupan"]),
            "error_total": _si(r["error_total"]),
            "appealed": _si(r["appealed"]),
            "appeal_reversed": _si(r["appeal_reversed"]),
            "raw_acc": _safe_pct(r["raw_correct"], cnt),
        })
    return rows


def _query_top_error_queues(repo: DashboardRepository, d: str) -> list[ErrorQueue]:
    sql = """
        SELECT mother_biz, sub_biz, queue_name,
               COUNT(*) AS err_cnt,
               SUM(CASE WHEN COALESCE(error_type,'') LIKE '%%错判%%' THEN 1 ELSE 0 END) AS cuopan,
               SUM(CASE WHEN COALESCE(error_type,'') LIKE '%%漏判%%' THEN 1 ELSE 0 END) AS loupan
        FROM vw_qa_base
        WHERE biz_date = %s AND is_raw_correct = 0
          AND COALESCE(mother_biz, '') != ''
          AND mother_biz != '未识别'
        GROUP BY 1, 2, 3
        ORDER BY 4 DESC LIMIT 10
    """
    df = repo.fetch_df(sql, [d])
    return [
        ErrorQueue(
            mother_biz=r["mother_biz"], sub_biz=r["sub_biz"], queue=r["queue_name"],
            err_cnt=_si(r["err_cnt"]), cuopan=_si(r["cuopan"]), loupan=_si(r["loupan"]),
        )
        for _, r in df.iterrows()
    ]


def _query_top_error_types(repo: DashboardRepository, d: str) -> list[dict]:
    sql = """
        SELECT COALESCE(NULLIF(TRIM(error_type), ''), '未标注') AS err_type,
               COUNT(*) AS cnt
        FROM vw_qa_base
        WHERE biz_date = %s AND is_raw_correct = 0
        GROUP BY 1 ORDER BY 2 DESC LIMIT 5
    """
    df = repo.fetch_df(sql, [d])
    result = [{"error_type": r["err_type"], "cnt": _si(r["cnt"])} for _, r in df.iterrows()]

    # 如果结果全为"未标注"（说明 error_type 字段普遍缺失），
    # 则退化到从 raw_judgement / final_judgement / qa_result 推断
    if result and all(item["error_type"] == "未标注" for item in result):
        fallback_sql = """
            SELECT
                CASE
                    WHEN COALESCE(raw_judgement,'') LIKE '%%错判%%'
                      OR COALESCE(raw_judgement,'') LIKE '%%误判%%'
                      OR COALESCE(final_judgement,'') LIKE '%%错判%%'
                      OR COALESCE(qa_result,'') LIKE '%%错判%%'
                    THEN '错判'
                    WHEN COALESCE(raw_judgement,'') LIKE '%%漏判%%'
                      OR COALESCE(raw_judgement,'') LIKE '%%漏审%%'
                      OR COALESCE(final_judgement,'') LIKE '%%漏判%%'
                      OR COALESCE(qa_result,'') LIKE '%%漏判%%'
                    THEN '漏判'
                    WHEN TRIM(COALESCE(raw_judgement, '')) IN ('', '正常', '通过', 'pass')
                    THEN '漏判'
                    ELSE '错判'
                END AS err_type,
                COUNT(*) AS cnt
            FROM vw_qa_base
            WHERE biz_date = %s AND is_raw_correct = 0
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        """
        df2 = repo.fetch_df(fallback_sql, [d])
        if not df2.empty:
            result = [{"error_type": r["err_type"], "cnt": _si(r["cnt"])} for _, r in df2.iterrows()]

    return result


def _query_alerts(repo: DashboardRepository, d: str) -> AlertSummary:
    df = repo.fetch_df(
        "SELECT severity, COUNT(*) AS cnt FROM fact_alert_event WHERE alert_date = %s GROUP BY 1", [d]
    )
    s = AlertSummary()
    for _, r in df.iterrows():
        if r["severity"] == "P0":
            s.p0 = _si(r["cnt"])
        elif r["severity"] == "P1":
            s.p1 = _si(r["cnt"])
        elif r["severity"] == "P2":
            s.p2 = _si(r["cnt"])
    return s


def _query_yesterday(repo: DashboardRepository, d: str) -> tuple[float | None, int | None]:
    yesterday = str(date.fromisoformat(d) - timedelta(days=1))
    df = repo.fetch_df(
        "SELECT COUNT(*) AS cnt, ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS acc FROM vw_qa_base WHERE biz_date=%s",
        [yesterday],
    )
    if df.empty or _si(df.iloc[0]["cnt"]) == 0:
        return None, None
    return _sf(df.iloc[0]["acc"]), _si(df.iloc[0]["cnt"])


def generate_daily_report(report_date: date, skip_ai: bool = False) -> ReportResult:
    """生成日报数据结构。"""
    repo = DashboardRepository()
    d = str(report_date)
    settings = _load_settings()

    sub_list = _query_sub_biz(repo, d)
    if not sub_list:
        return ReportResult(
            report_type="daily",
            report_date=report_date,
            has_data=False,
            dashboard_url=settings.get("dashboard_url", ""),
        )

    # 聚合母业务
    from collections import OrderedDict
    mother_map: OrderedDict[str, BizGroup] = OrderedDict()
    for s in sub_list:
        mb = s["mother_biz"]
        if mb not in mother_map:
            mother_map[mb] = BizGroup(name=mb)
        g = mother_map[mb]
        g.qa_cnt += s["qa_cnt"]
        g.correct_cnt += s["raw_correct"]
        g.error_cnt += s["error_total"]
        g.cuopan += s["cuopan"]
        g.loupan += s["loupan"]
        g.appealed += s["appealed"]
        g.appeal_reversed += s["appeal_reversed"]
        g.subs.append(BizGroup(
            name=s["sub_biz"], qa_cnt=s["qa_cnt"], correct_cnt=s["raw_correct"],
            error_cnt=s["error_total"], cuopan=s["cuopan"], loupan=s["loupan"],
            appealed=s["appealed"], appeal_reversed=s["appeal_reversed"],
            acc=s["raw_acc"],
        ))

    groups = []
    for g in mother_map.values():
        g.acc = _safe_pct(g.correct_cnt, g.qa_cnt)
        groups.append(g)

    total_qa = sum(g.qa_cnt for g in groups)
    total_correct = sum(g.correct_cnt for g in groups)
    total_error = sum(g.error_cnt for g in groups)

    yesterday_acc, yesterday_qa = _query_yesterday(repo, d)
    vol_change = None
    if yesterday_qa and yesterday_qa > 0:
        vol_change = _sf((total_qa - yesterday_qa) / yesterday_qa * 100)
    acc_pp = None
    acc_val = _safe_pct(total_correct, total_qa)
    if yesterday_acc is not None:
        acc_pp = round(acc_val - yesterday_acc, 2)

    present = {g.name for g in groups}
    absent = [n for n in KNOWN_GROUPS if n not in present]

    result = ReportResult(
        report_type="daily",
        report_date=report_date,
        has_data=True,
        target=ACC_TARGET,
        total_qa=total_qa,
        total_correct=total_correct,
        total_error=total_error,
        total_cuopan=sum(g.cuopan for g in groups),
        total_loupan=sum(g.loupan for g in groups),
        total_appealed=sum(g.appealed for g in groups),
        total_appeal_reversed=sum(g.appeal_reversed for g in groups),
        acc=acc_val,
        appeal_rev_rate=_safe_pct(
            sum(g.appeal_reversed for g in groups),
            sum(g.appealed for g in groups),
        ),
        yesterday_acc=yesterday_acc,
        yesterday_qa=yesterday_qa,
        volume_change_pct=vol_change,
        acc_change_pp=acc_pp,
        groups=groups,
        absent_groups=absent,
        top_error_queues=_query_top_error_queues(repo, d),
        top_error_types=_query_top_error_types(repo, d),
        alerts=_query_alerts(repo, d),
        yesterday_alerts=_query_alerts(repo, str(report_date - timedelta(days=1))),
        dashboard_url=settings.get("dashboard_url", ""),
    )

    if not skip_ai:
        result.ai_insight = _call_deepseek(result)

    return result


# ═══════════════════════════════════════════════════════════════
#  周报生成
# ═══════════════════════════════════════════════════════════════

def generate_weekly_report(week_end_date: date, skip_ai: bool = False) -> ReportResult:
    """生成周报数据结构。week_end_date 为本周日（或周五），自动回溯到周一。"""
    repo = DashboardRepository()
    settings = _load_settings()

    # 计算本周范围：周一到 week_end_date
    weekday = week_end_date.weekday()
    week_start = week_end_date - timedelta(days=weekday)
    week_end = week_end_date

    d_start = str(week_start)
    d_end = str(week_end)

    # 本周聚合
    sql_sub = """
        SELECT mother_biz, sub_biz,
               COUNT(*) AS qa_cnt,
               SUM(CASE WHEN is_raw_correct = 1 THEN 1 ELSE 0 END) AS raw_correct,
               SUM(CASE WHEN is_raw_correct = 0 THEN 1 ELSE 0 END) AS error_total,
               SUM(CASE WHEN is_raw_correct = 0 AND COALESCE(error_type,'') LIKE '%%错判%%' THEN 1 ELSE 0 END) AS cuopan,
               SUM(CASE WHEN is_raw_correct = 0 AND COALESCE(error_type,'') LIKE '%%漏判%%' THEN 1 ELSE 0 END) AS loupan,
               SUM(CASE WHEN is_appealed = 1 THEN 1 ELSE 0 END) AS appealed,
               SUM(CASE WHEN is_appeal_reversed = 1 THEN 1 ELSE 0 END) AS appeal_reversed
        FROM vw_qa_base
        WHERE biz_date BETWEEN %s AND %s
          AND COALESCE(mother_biz, '') != ''
          AND mother_biz != '未识别'
        GROUP BY 1, 2 ORDER BY 1, 2
    """
    df_sub = repo.fetch_df(sql_sub, [d_start, d_end])

    if df_sub.empty:
        return ReportResult(
            report_type="weekly", report_date=week_end, has_data=False,
            week_start=week_start, week_end=week_end,
            dashboard_url=settings.get("dashboard_url", ""),
        )

    # 每日趋势
    sql_trend = """
        SELECT biz_date,
               COUNT(*) AS qa_cnt,
               ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS acc
        FROM vw_qa_base
        WHERE biz_date BETWEEN %s AND %s
        GROUP BY 1 ORDER BY 1
    """
    df_trend = repo.fetch_df(sql_trend, [d_start, d_end])
    daily_trend = [
        {"date": str(r["biz_date"]), "qa_cnt": _si(r["qa_cnt"]), "acc": _sf(r["acc"])}
        for _, r in df_trend.iterrows()
    ]

    # 上周数据
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)
    df_lw = repo.fetch_df(
        "SELECT COUNT(*) AS cnt, ROUND(SUM(CASE WHEN is_raw_correct=1 THEN 1 ELSE 0 END)*100.0/NULLIF(COUNT(*),0),2) AS acc FROM vw_qa_base WHERE biz_date BETWEEN %s AND %s",
        [str(last_week_start), str(last_week_end)],
    )
    last_week_acc = _sf(df_lw.iloc[0]["acc"]) if not df_lw.empty and _si(df_lw.iloc[0]["cnt"]) > 0 else None

    # 聚合
    from collections import OrderedDict
    mother_map: OrderedDict[str, BizGroup] = OrderedDict()
    for _, r in df_sub.iterrows():
        mb = r["mother_biz"]
        if mb not in mother_map:
            mother_map[mb] = BizGroup(name=mb)
        g = mother_map[mb]
        cnt = _si(r["qa_cnt"])
        correct = _si(r["raw_correct"])
        err = _si(r["error_total"])
        g.qa_cnt += cnt
        g.correct_cnt += correct
        g.error_cnt += err
        g.cuopan += _si(r["cuopan"])
        g.loupan += _si(r["loupan"])
        g.appealed += _si(r["appealed"])
        g.appeal_reversed += _si(r["appeal_reversed"])
        g.subs.append(BizGroup(
            name=r["sub_biz"], qa_cnt=cnt, correct_cnt=correct, error_cnt=err,
            cuopan=_si(r["cuopan"]), loupan=_si(r["loupan"]),
            acc=_safe_pct(correct, cnt),
        ))

    groups = []
    for g in mother_map.values():
        g.acc = _safe_pct(g.correct_cnt, g.qa_cnt)
        groups.append(g)

    total_qa = sum(g.qa_cnt for g in groups)
    total_correct = sum(g.correct_cnt for g in groups)
    acc_val = _safe_pct(total_correct, total_qa)
    wow_pp = round(acc_val - last_week_acc, 2) if last_week_acc is not None else None

    # 告警汇总
    sql_alerts = "SELECT severity, COUNT(*) AS cnt FROM fact_alert_event WHERE alert_date BETWEEN %s AND %s GROUP BY 1"
    df_alerts = repo.fetch_df(sql_alerts, [d_start, d_end])
    alerts = AlertSummary()
    for _, r in df_alerts.iterrows():
        if r["severity"] == "P0":
            alerts.p0 = _si(r["cnt"])
        elif r["severity"] == "P1":
            alerts.p1 = _si(r["cnt"])
        elif r["severity"] == "P2":
            alerts.p2 = _si(r["cnt"])

    present = {g.name for g in groups}
    absent = [n for n in KNOWN_GROUPS if n not in present]

    result = ReportResult(
        report_type="weekly",
        report_date=week_end,
        has_data=True,
        target=ACC_TARGET,
        total_qa=total_qa,
        total_correct=total_correct,
        total_error=sum(g.error_cnt for g in groups),
        total_cuopan=sum(g.cuopan for g in groups),
        total_loupan=sum(g.loupan for g in groups),
        total_appealed=sum(g.appealed for g in groups),
        total_appeal_reversed=sum(g.appeal_reversed for g in groups),
        acc=acc_val,
        groups=groups,
        absent_groups=absent,
        top_error_queues=_query_top_error_queues(repo, d_end),
        top_error_types=_query_top_error_types(repo, d_end),
        alerts=alerts,
        week_start=week_start,
        week_end=week_end,
        daily_trend=daily_trend,
        week_over_week_acc_pp=wow_pp,
        last_week_acc=last_week_acc,
        dashboard_url=settings.get("dashboard_url", ""),
    )

    if not skip_ai:
        result.ai_insight = _call_deepseek(
            result,
            custom_prompt="这是周报，侧重本周趋势变化、周度风险是否收敛、下周预判",
        )

    return result


# ═══════════════════════════════════════════════════════════════
#  新人日报
# ═══════════════════════════════════════════════════════════════

def generate_newcomer_report(report_date: date, skip_ai: bool = False) -> ReportResult:
    """生成新人培训日报数据。"""
    repo = DashboardRepository()
    settings = _load_settings()
    d = str(report_date)

    # 查询活跃批次
    sql_batches = """
        SELECT
            n.batch_name,
            n.team_name,
            COUNT(DISTINCT n.reviewer_alias) AS member_cnt,
            COUNT(q.id) AS qa_cnt,
            SUM(CASE WHEN q.is_correct = 1 THEN 1 ELSE 0 END) AS correct_cnt,
            SUM(CASE WHEN q.is_correct = 0 THEN 1 ELSE 0 END) AS error_cnt,
            ROUND(SUM(CASE WHEN q.is_correct = 1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(q.id), 0), 2) AS acc
        FROM dim_newcomer_batch n
        LEFT JOIN fact_newcomer_qa q
          ON q.reviewer_name = n.reviewer_alias AND q.biz_date = %s
        WHERE n.status = 'training'
        GROUP BY n.batch_name, n.team_name
        ORDER BY n.batch_name
    """
    df_batches = repo.fetch_df(sql_batches, [d])

    batches = []
    total_qa = 0
    total_correct = 0
    total_error = 0
    for _, r in df_batches.iterrows():
        qa = _si(r["qa_cnt"])
        correct = _si(r["correct_cnt"])
        err = _si(r["error_cnt"])
        total_qa += qa
        total_correct += correct
        total_error += err
        batches.append({
            "batch_name": r["batch_name"],
            "team_name": r.get("team_name", ""),
            "member_cnt": _si(r["member_cnt"]),
            "qa_cnt": qa,
            "correct_cnt": correct,
            "error_cnt": err,
            "acc": _sf(r["acc"]) if qa > 0 else 0.0,
        })

    # 异常新人
    sql_alerts = """
        SELECT
            n.batch_name, n.reviewer_alias, n.team_name,
            COUNT(q.id) AS qa_cnt,
            ROUND(SUM(CASE WHEN q.is_correct = 1 THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(q.id), 0), 2) AS acc
        FROM dim_newcomer_batch n
        JOIN fact_newcomer_qa q
          ON q.reviewer_name = n.reviewer_alias AND q.biz_date = %s
        WHERE n.status = 'training'
        GROUP BY n.batch_name, n.reviewer_alias, n.team_name
        HAVING acc < 97
        ORDER BY acc ASC
    """
    df_nc_alerts = repo.fetch_df(sql_alerts, [d])
    nc_alerts = [
        {
            "batch_name": r["batch_name"],
            "reviewer": r["reviewer_alias"],
            "team_name": r.get("team_name", ""),
            "qa_cnt": _si(r["qa_cnt"]),
            "acc": _sf(r["acc"]),
        }
        for _, r in df_nc_alerts.iterrows()
    ]

    result = ReportResult(
        report_type="newcomer",
        report_date=report_date,
        has_data=total_qa > 0 or len(batches) > 0,
        target=97.0,  # 新人目标
        total_qa=total_qa,
        total_correct=total_correct,
        total_error=total_error,
        acc=_safe_pct(total_correct, total_qa),
        newcomer_batches=batches,
        newcomer_alerts=nc_alerts,
        dashboard_url=settings.get("dashboard_url", ""),
    )

    if not skip_ai and total_qa > 0:
        result.ai_insight = _call_deepseek(
            result,
            custom_prompt="这是新人培训日报，侧重新人成长曲线、异常人员定位、培训建议",
        )

    return result
