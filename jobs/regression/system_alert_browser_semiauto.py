#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests

TIMEOUT_SECONDS = 60
DEFAULT_FRONTEND_BASE = "http://127.0.0.1:3000"
DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_PREFERRED_RULE_CODES = ["JOIN_MATCH_LT_85_DAY", "MISSING_JOIN_KEY_GT_10_DAY"]
COMPARISON_LOOKBACK_DAYS = 30
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class LinkItem:
    href: str
    text: str


@dataclass
class FocusCandidateItem:
    class_name: str
    text: str


class AnchorTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[LinkItem] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_map = {key: value for key, value in attrs}
        self._current_href = attr_map.get("href")
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        text = " ".join(part.strip() for part in self._text_parts if part.strip())
        self.links.append(LinkItem(href=self._current_href, text=text))
        self._current_href = None
        self._text_parts = []


class FocusCandidateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[FocusCandidateItem] = []
        self._capture_depth = 0
        self._current_class_name: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value for key, value in attrs}
        class_name = attr_map.get("class") or ""
        class_tokens = class_name.split()
        if self._capture_depth == 0 and tag == "li" and "focus-candidate-item" in class_tokens:
            self._capture_depth = 1
            self._current_class_name = class_name
            self._text_parts = []
            return
        if self._capture_depth > 0:
            self._capture_depth += 1

    def handle_data(self, data: str) -> None:
        if self._capture_depth > 0:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture_depth == 0:
            return
        self._capture_depth -= 1
        if self._capture_depth == 0 and self._current_class_name is not None:
            text = " ".join(part.strip() for part in self._text_parts if part.strip())
            self.items.append(FocusCandidateItem(class_name=self._current_class_name, text=text))
            self._current_class_name = None
            self._text_parts = []


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "extra": self.extra or {},
        }


class CheckFailure(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="系统级告警链路半自动化浏览器回归首版。")
    parser.add_argument("--frontend-base", default=DEFAULT_FRONTEND_BASE, help="前端地址，默认 http://127.0.0.1:3000")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="API 地址，默认 http://127.0.0.1:8000")
    parser.add_argument("--grain", default="day", choices=["day", "week", "month"], help="首页粒度，默认 day")
    parser.add_argument("--selected-date", default=None, help="业务日期 YYYY-MM-DD；默认自动取 meta 返回的 default_selected_date")
    parser.add_argument(
        "--prefer-rule-codes",
        default=",".join(DEFAULT_PREFERRED_RULE_CODES),
        help="优先挑选的系统级规则代码，逗号分隔。",
    )
    parser.add_argument("--demo-fixture", default=None, help="dev-only fixture 名称，如 system_alert_same_group_queue_shift；启用后脚本会走固定样本而非真实数据扫描")
    parser.add_argument("--output", default=None, help="可选，把结果写到指定 JSON 文件")
    return parser.parse_args()


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def build_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    base = f"{normalize_base_url(base_url)}{path}"
    if not params:
        return base
    query = urlencode({key: value for key, value in params.items() if value not in (None, "")}, doseq=True)
    return f"{base}?{query}" if query else base


def fetch_json(session: requests.Session, url: str) -> dict[str, Any]:
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise CheckFailure(f"接口未返回 JSON 对象：{url}")
    return payload


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def parse_links(html: str) -> list[LinkItem]:
    parser = AnchorTextParser()
    parser.feed(html)
    return parser.links


def parse_focus_candidates(html: str) -> list[FocusCandidateItem]:
    parser = FocusCandidateParser()
    parser.feed(html)
    return parser.items


def find_focus_candidate(
    items: list[FocusCandidateItem],
    expected_tokens: list[str],
    description: str,
    *,
    require_active: bool = False,
) -> FocusCandidateItem:
    for item in items:
        class_tokens = item.class_name.split()
        if require_active and "active" not in class_tokens:
            continue
        if all(token in item.text for token in expected_tokens):
            return item
    raise CheckFailure(f"页面里没找到符合条件的候选卡片：{description}")


def find_link(links: list[LinkItem], text_keyword: str) -> LinkItem:
    for link in links:
        if text_keyword in link.text:
            return link
    raise CheckFailure(f"页面里没找到链接文案：{text_keyword}")


def find_link_by_predicate(
    links: list[LinkItem],
    predicate: Callable[[LinkItem], bool],
    description: str,
) -> LinkItem:
    for link in links:
        if predicate(link):
            return link
    raise CheckFailure(f"页面里没找到符合条件的链接：{description}")


def require_contains(html: str, keyword: str, hint: str) -> None:
    if keyword not in html:
        raise CheckFailure(f"页面缺少关键文案“{keyword}”：{hint}")


def require_contains_any(html: str, keywords: list[str], hint: str) -> None:
    if any(keyword in html for keyword in keywords):
        return
    raise CheckFailure(f"页面缺少任一关键文案 {keywords}：{hint}")


def get_query_values(href: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(href).query, keep_blank_values=False)


def get_single_query_value(href: str, key: str) -> str:
    return (get_query_values(href).get(key) or [""])[0]


def update_query_values(href: str, updates: dict[str, str | None]) -> str:
    parsed = urlparse(href)
    query = parse_qs(parsed.query, keep_blank_values=False)
    for key, value in updates.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = [value]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def normalize_rule_codes(raw_value: str) -> list[str]:
    return [item.strip().upper() for item in raw_value.split(",") if item.strip()]


def pick_selected_date(session: requests.Session, api_base: str, preferred_date: str | None) -> str:
    if preferred_date:
        return preferred_date
    meta_payload = fetch_json(session, build_url(api_base, "/api/v1/meta/date-range"))
    meta_data = meta_payload.get("data", {}) if isinstance(meta_payload, dict) else {}
    selected_date = str(meta_data.get("default_selected_date") or meta_data.get("max_date") or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", selected_date):
        raise CheckFailure("无法从 /api/v1/meta/date-range 拿到有效 selected_date")
    return selected_date


DEMO_FIXTURE_NAME = "system_alert_same_group_queue_shift"


def list_system_alerts(
    session: requests.Session,
    api_base: str,
    grain: str,
    selected_date: str,
    demo_fixture: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"grain": grain, "selected_date": selected_date}
    if demo_fixture:
        params["demo_fixture"] = demo_fixture
    alerts_payload = fetch_json(
        session,
        build_url(
            api_base,
            "/api/v1/dashboard/alerts",
            params,
        ),
    )
    items = alerts_payload.get("data", {}).get("items", []) if isinstance(alerts_payload, dict) else []
    if not isinstance(items, list):
        raise CheckFailure("告警列表接口返回格式不对，items 不是数组")
    return [
        item
        for item in items
        if isinstance(item, dict) and str(item.get("target_level", "")).strip().lower() == "system" and str(item.get("alert_id", "")).strip()
    ]


def pick_system_alert(
    session: requests.Session,
    api_base: str,
    grain: str,
    selected_date: str,
    preferred_rule_codes: list[str],
) -> dict[str, Any]:
    system_alerts = list_system_alerts(session, api_base, grain, selected_date)
    if not system_alerts:
        raise CheckFailure(f"{selected_date} 这天没有可用的系统级告警，没法做这轮半自动化链路回归")

    preferred = [
        item
        for item in system_alerts
        if str(item.get("rule_code", "")).strip().upper() in preferred_rule_codes
    ]
    return preferred[0] if preferred else system_alerts[0]


def fetch_alert_detail_rows(
    session: requests.Session,
    api_base: str,
    grain: str,
    selected_date: str,
    alert_id: str,
    demo_fixture: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"grain": grain, "selected_date": selected_date}
    if demo_fixture:
        params["demo_fixture"] = demo_fixture
    detail_payload = fetch_json(
        session,
        build_url(
            api_base,
            f"/api/v1/dashboard/alerts/{alert_id}",
            params,
        ),
    )
    detail_data = detail_payload.get("data") if isinstance(detail_payload, dict) else None
    rows = detail_data.get("alert_sample_df", []) if isinstance(detail_data, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def find_same_group_queue_shift_candidate(
    session: requests.Session,
    api_base: str,
    grain: str,
    selected_date: str,
    preferred_rule_codes: list[str],
    lookback_days: int = COMPARISON_LOOKBACK_DAYS,
    demo_fixture: str | None = None,
) -> dict[str, Any] | None:
    # ── fixture 短路：直接从 API 拉一条 fixture 告警的样本，构造候选项 ──
    if demo_fixture:
        fixture_alerts = list_system_alerts(session, api_base, grain, selected_date, demo_fixture=demo_fixture)
        if not fixture_alerts:
            return None
        fixture_item = fixture_alerts[0]
        fixture_alert_id = str(fixture_item.get("alert_id", "")).strip()
        rows = fetch_alert_detail_rows(session, api_base, grain, selected_date, fixture_alert_id, demo_fixture=demo_fixture)
        group_queue_counts: dict[str, dict[str, int]] = {}
        for row in rows:
            group_name = str(row.get("group_name") or "").strip()
            queue_name = str(row.get("queue_name") or "").strip()
            if not group_name or not queue_name:
                continue
            group_queue_counts.setdefault(group_name, {})
            group_queue_counts[group_name][queue_name] = group_queue_counts[group_name].get(queue_name, 0) + 1
        for group_name, queue_counter in group_queue_counts.items():
            if len(queue_counter) < 2:
                continue
            sorted_queues = sorted(queue_counter.items(), key=lambda pair: (-pair[1], pair[0]))
            top_queue_name, top_queue_count = sorted_queues[0]
            narrowed_queue_name, narrowed_queue_count = sorted_queues[1]
            if top_queue_name == narrowed_queue_name:
                continue
            return {
                "selected_date": selected_date,
                "alert_id": fixture_alert_id,
                "rule_code": str(fixture_item.get("rule_code", "")).strip(),
                "group_name": group_name,
                "top_queue_name": top_queue_name,
                "top_queue_count": top_queue_count,
                "narrowed_queue_name": narrowed_queue_name,
                "narrowed_queue_count": narrowed_queue_count,
                "lookback_days": 0,
                "demo_fixture": demo_fixture,
            }
        return None

    # ── 真实模式：遍历近 N 天 ──
    try:
        anchor_date = date.fromisoformat(selected_date)
    except ValueError:
        return None

    for offset in range(lookback_days + 1):
        scan_date = (anchor_date - timedelta(days=offset)).isoformat()
        system_alerts = list_system_alerts(session, api_base, grain, scan_date)
        if not system_alerts:
            continue
        ordered_alerts = sorted(
            system_alerts,
            key=lambda item: (
                str(item.get("rule_code", "")).strip().upper() not in preferred_rule_codes,
                str(item.get("alert_id", "")).strip(),
            ),
        )
        for item in ordered_alerts:
            alert_id = str(item.get("alert_id", "")).strip()
            rows = fetch_alert_detail_rows(session, api_base, grain, scan_date, alert_id)
            group_queue_counts: dict[str, dict[str, int]] = {}
            for row in rows:
                group_name = str(row.get("group_name") or "").strip()
                queue_name = str(row.get("queue_name") or "").strip()
                if not group_name or not queue_name:
                    continue
                group_queue_counts.setdefault(group_name, {})
                group_queue_counts[group_name][queue_name] = group_queue_counts[group_name].get(queue_name, 0) + 1
            for group_name, queue_counter in group_queue_counts.items():
                if len(queue_counter) < 2:
                    continue
                sorted_queues = sorted(queue_counter.items(), key=lambda pair: (-pair[1], pair[0]))
                top_queue_name, top_queue_count = sorted_queues[0]
                narrowed_queue_name, narrowed_queue_count = sorted_queues[1]
                if top_queue_name == narrowed_queue_name:
                    continue
                return {
                    "selected_date": scan_date,
                    "alert_id": alert_id,
                    "rule_code": str(item.get("rule_code", "")).strip(),
                    "group_name": group_name,
                    "top_queue_name": top_queue_name,
                    "top_queue_count": top_queue_count,
                    "narrowed_queue_name": narrowed_queue_name,
                    "narrowed_queue_count": narrowed_queue_count,
                    "lookback_days": lookback_days,
                }
    return None


def absolutize(frontend_base: str, href: str) -> str:
    return urljoin(f"{normalize_base_url(frontend_base)}/", href)


def remove_dashboard_context(href: str) -> str:
    parsed = urlparse(href)
    query = parse_qs(parsed.query, keep_blank_values=False)
    for key in list(query.keys()):
        if key.startswith("dashboard_"):
            query.pop(key, None)
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def main() -> int:
    args = parse_args()
    frontend_base = normalize_base_url(args.frontend_base)
    api_base = normalize_base_url(args.api_base)
    preferred_rule_codes = normalize_rule_codes(args.prefer_rule_codes)
    demo_fixture = args.demo_fixture  # None 或 fixture 名称
    session = requests.Session()

    results: list[CheckResult] = []

    try:
        selected_date = pick_selected_date(session, api_base, args.selected_date)
        results.append(
            CheckResult(
                name="selected_date",
                status="passed",
                detail="已确定回归业务日期。",
                extra={"selected_date": selected_date, "grain": args.grain},
            )
        )

        if demo_fixture:
            fixture_alerts = list_system_alerts(session, api_base, args.grain, selected_date, demo_fixture=demo_fixture)
            if not fixture_alerts:
                raise CheckFailure(f"fixture 模式：{demo_fixture} 没有返回告警列表，请确认 QC_ENABLE_DEMO_FIXTURES=1 已设置且 fixture 文件存在")
            system_alert = fixture_alerts[0]
        else:
            system_alert = pick_system_alert(session, api_base, args.grain, selected_date, preferred_rule_codes)
        alert_id = str(system_alert.get("alert_id", "")).strip()
        rule_code = str(system_alert.get("rule_code", "")).strip()
        results.append(
            CheckResult(
                name="pick_system_alert",
                status="passed",
                detail="已选中本轮系统级告警。",
                extra={
                    "alert_id": alert_id,
                    "rule_code": rule_code,
                    "target_level": system_alert.get("target_level"),
                },
            )
        )

        home_url = build_url(
            frontend_base,
            "/",
            {"grain": args.grain, "selected_date": selected_date, "alert_id": alert_id, "demo_fixture": demo_fixture},
        )
        home_html = fetch_html(session, home_url)
        require_contains(home_html, "告警详情闭环", "首页系统级告警详情应该已经展开")
        require_contains(home_html, "当前聚焦说明", "系统级告警详情态需要说明 global/scoped 层级")
        require_contains(home_html, "样本文本", "首页系统级告警详情态应该展示告警关联样本表的核心字段")
        require_contains(home_html, "关联主键", "首页系统级告警详情态应该展示关联主键列")
        require_contains_any(home_html, ["联表状态", "最终结果"], "首页系统级告警详情态应该展示样本结果列")
        results.append(
            CheckResult(
                name="home_alert_samples_table",
                status="passed",
                detail="首页系统级告警详情态已承接告警关联样本表，核心列与样本结果列可见。",
                extra={"home_url": home_url},
            )
        )
        home_links = parse_links(home_html)
        details_link = find_link(home_links, "打开关联明细（保留返回链路）")
        details_href = absolutize(frontend_base, details_link.href)
        results.append(
            CheckResult(
                name="home_to_details_link",
                status="passed",
                detail="首页系统级告警详情态已产出带返回链路的明细链接。",
                extra={"home_url": home_url, "details_href": details_link.href},
            )
        )

        group_focus_link = find_link_by_predicate(
            home_links,
            lambda link: "聚焦首页" in link.text
            and bool(get_single_query_value(link.href, "group_name"))
            and not get_single_query_value(link.href, "focus_queue_name"),
            "问题最多组别的“聚焦首页”",
        )
        group_focus_group_name = get_single_query_value(group_focus_link.href, "group_name")
        group_focus_href = absolutize(frontend_base, group_focus_link.href)
        group_focus_html = fetch_html(session, group_focus_href)
        require_contains(group_focus_html, f"组别：{group_focus_group_name}", "组别聚焦后首页应明确展示当前组别")
        require_contains(group_focus_html, "已经从全局样本收窄到", "组别聚焦后首页应明确说明已从全局样本收窄")
        results.append(
            CheckResult(
                name="group_focus_link",
                status="passed",
                detail="问题最多组别里的“聚焦首页”链接可用，且首页会进入组别聚焦态。",
                extra={
                    "group_name": group_focus_group_name,
                    "group_focus_href": group_focus_link.href,
                },
            )
        )

        group_details_link = find_link_by_predicate(
            home_links,
            lambda link: "明细查询" in link.text
            and bool(get_single_query_value(link.href, "dashboard_group_name"))
            and not get_single_query_value(link.href, "dashboard_focus_queue_name"),
            "问题最多组别的“明细查询”",
        )
        group_details_href = absolutize(frontend_base, group_details_link.href)
        group_details_html = fetch_html(session, group_details_href)
        group_detail_links = parse_links(group_details_html)
        group_return_link = find_link(group_detail_links, "返回首页当前告警")
        if not group_return_link.href.startswith("/?"):
            raise CheckFailure(f"组别返回首页当前告警的 href 不是根路由：{group_return_link.href}")
        returned_group_home_href = absolutize(frontend_base, group_return_link.href)
        returned_group_home_html = fetch_html(session, returned_group_home_href)
        require_contains(returned_group_home_html, "系统级样本快速聚焦", "组别恢复后首页必须继续显示快速聚焦区")
        group_focus_candidates = parse_focus_candidates(returned_group_home_html)
        matched_group_candidate = find_focus_candidate(
            group_focus_candidates,
            [group_focus_group_name, "本次恢复命中"],
            "组别恢复后的高亮候选",
            require_active=True,
        )
        results.append(
            CheckResult(
                name="group_return_highlight",
                status="passed",
                detail="问题最多组别 -> 明细 -> 返回首页后，首页会继续显示快速聚焦区，并把当前组别高亮成“本次恢复命中”。",
                extra={
                    "group_details_href": group_details_link.href,
                    "group_return_href": group_return_link.href,
                    "matched_candidate": matched_group_candidate.text,
                },
            )
        )

        queue_focus_link = find_link_by_predicate(
            home_links,
            lambda link: "聚焦首页" in link.text and bool(get_single_query_value(link.href, "focus_queue_name")),
            "问题最多队列的“聚焦首页”",
        )
        queue_focus_group_name = get_single_query_value(queue_focus_link.href, "group_name")
        queue_focus_name = get_single_query_value(queue_focus_link.href, "focus_queue_name")
        queue_focus_href = absolutize(frontend_base, queue_focus_link.href)
        queue_focus_html = fetch_html(session, queue_focus_href)
        require_contains(queue_focus_html, f"组别：{queue_focus_group_name}", "队列聚焦后首页应继续展示所属组别")
        require_contains(queue_focus_html, f"队列：{queue_focus_name}", "队列聚焦后首页应明确展示当前队列")
        results.append(
            CheckResult(
                name="queue_focus_link",
                status="passed",
                detail="问题最多队列里的“聚焦首页”链接可用，且首页会进入队列聚焦态。",
                extra={
                    "group_name": queue_focus_group_name,
                    "queue_name": queue_focus_name,
                    "queue_focus_href": queue_focus_link.href,
                },
            )
        )
        require_contains(queue_focus_html, "当前已经从全局告警样本收窄到", "队列聚焦后首页样本区应显式说明当前展示的是 scoped 样本")
        require_contains(queue_focus_html, "样本文本", "队列聚焦后首页应继续展示告警关联样本的核心列")
        require_contains(queue_focus_html, "关联主键", "队列聚焦后首页应继续展示关联主键列")
        results.append(
            CheckResult(
                name="queue_focus_alert_samples",
                status="passed",
                detail="问题最多队列聚焦后，首页会继续承接 scoped 告警关联样本，并明确说明当前样本来源。",
                extra={
                    "queue_focus_href": queue_focus_link.href,
                    "group_name": queue_focus_group_name,
                    "queue_name": queue_focus_name,
                },
            )
        )

        join_key_focus_link = find_link_by_predicate(
            home_links,
            lambda link: "展开该类型" in link.text and bool(get_single_query_value(link.href, "focus_join_key_type")),
            "按主键类型展开的“展开该类型”",
        )
        join_key_type = get_single_query_value(join_key_focus_link.href, "focus_join_key_type")
        join_key_focus_href = absolutize(frontend_base, join_key_focus_link.href)
        join_key_focus_html = fetch_html(session, join_key_focus_href)
        require_contains(join_key_focus_html, f"主键类型：{join_key_type}", "按主键类型展开后首页应显式展示当前主键类型")
        require_contains(join_key_focus_html, "清空类型", "主键类型展开后首页应提供清空类型动作")
        results.append(
            CheckResult(
                name="join_key_type_focus_link",
                status="passed",
                detail="按主键类型展开入口可用，且首页会进入主键类型展开态。",
                extra={
                    "join_key_type": join_key_type,
                    "join_key_focus_href": join_key_focus_link.href,
                },
            )
        )

        missing_join_key_type = "__wb_missing_join_key_type__"
        missing_join_key_href = absolutize(
            frontend_base,
            update_query_values(join_key_focus_link.href, {"focus_join_key_type": missing_join_key_type}),
        )
        missing_join_key_html = fetch_html(session, missing_join_key_href)
        require_contains(
            missing_join_key_html,
            f"当前主键类型“{missing_join_key_type}”在这条系统级告警的全局样本里已经没有命中记录",
            "主键类型没有命中样本时，首页必须显式展示空状态说明",
        )
        require_contains(missing_join_key_html, "清空类型", "主键类型空状态时首页仍应保留清空类型动作")
        results.append(
            CheckResult(
                name="join_key_type_empty_state",
                status="passed",
                detail="构造失效主键类型后，首页会显式展示样本空状态说明，并保留清空类型动作。",
                extra={
                    "missing_join_key_type": missing_join_key_type,
                    "missing_join_key_href": missing_join_key_href,
                },
            )
        )

        join_key_focus_links = parse_links(join_key_focus_html)
        join_key_details_link = find_link_by_predicate(
            join_key_focus_links,
            lambda link: "打开关联明细（保留返回链路）" in link.text
            and get_single_query_value(link.href, "dashboard_focus_join_key_type") == join_key_type,
            "主键类型展开态里的“打开关联明细（保留返回链路）”",
        )
        join_key_details_href = absolutize(frontend_base, join_key_details_link.href)
        join_key_details_html = fetch_html(session, join_key_details_href)
        require_contains(join_key_details_html, "返回首页与状态恢复", "主键类型展开态进入明细页后，必须仍能返回首页恢复状态")
        join_key_detail_links = parse_links(join_key_details_html)
        join_key_return_link = find_link(join_key_detail_links, "返回首页当前告警")
        if not join_key_return_link.href.startswith("/?"):
            raise CheckFailure(f"主键类型返回首页当前告警的 href 不是根路由：{join_key_return_link.href}")
        returned_join_key_home_html = fetch_html(session, absolutize(frontend_base, join_key_return_link.href))
        require_contains(returned_join_key_home_html, "从明细页返回的恢复感知", "主键类型返回首页后必须显式展示恢复感知")
        require_contains(returned_join_key_home_html, "系统级样本快速聚焦", "主键类型返回首页后必须继续显示快速聚焦区")
        returned_join_key_focus_candidates = parse_focus_candidates(returned_join_key_home_html)
        matched_join_key_candidate = find_focus_candidate(
            returned_join_key_focus_candidates,
            [join_key_type, "本次恢复命中"],
            "主键类型恢复后的高亮候选",
            require_active=True,
        )
        results.append(
            CheckResult(
                name="join_key_type_return_highlight",
                status="passed",
                detail="按主键类型展开 -> 明细 -> 返回首页后，首页会继续显示快速聚焦区，并把当前主键类型高亮成“本次恢复命中”。",
                extra={
                    "join_key_details_href": join_key_details_link.href,
                    "join_key_return_href": join_key_return_link.href,
                    "matched_candidate": matched_join_key_candidate.text,
                },
            )
        )

        queue_details_link = find_link_by_predicate(
            home_links,
            lambda link: "明细查询" in link.text
            and bool(get_single_query_value(link.href, "queue_name"))
            and bool(get_single_query_value(link.href, "dashboard_focus_queue_name")),
            "问题最多队列的“明细查询”",
        )
        queue_details_href = absolutize(frontend_base, queue_details_link.href)
        details_html = fetch_html(session, queue_details_href)
        require_contains(details_html, "返回首页与状态恢复", "明细页需要展示返回首页动作")
        require_contains(details_html, "来自系统级告警的联动说明", "明细页需要承接首页联动语义")
        detail_links = parse_links(details_html)
        return_link = find_link(detail_links, "返回首页当前告警")
        if not return_link.href.startswith("/?"):
            raise CheckFailure(f"返回首页当前告警的 href 不是根路由：{return_link.href}")
        results.append(
            CheckResult(
                name="queue_details_return_href",
                status="passed",
                detail="问题最多队列链路进入明细页后，返回首页当前告警的链接仍固定到首页根路由。",
                extra={
                    "queue_details_href": queue_details_link.href,
                    "return_href": return_link.href,
                },
            )
        )

        returned_home_href = absolutize(frontend_base, return_link.href)
        returned_home_html = fetch_html(session, returned_home_href)
        require_contains(returned_home_html, "从明细页返回的恢复感知", "返回首页后必须显式展示恢复感知")
        require_contains(returned_home_html, "系统级样本快速聚焦", "带队列恢复态返回首页后必须继续显示快速聚焦区")
        require_contains(returned_home_html, "二次回看变化对比", "带队列恢复态返回首页后必须展示二次回看变化对比")
        require_contains(returned_home_html, "重新定位当前告警", "恢复后首页必须继续保留重新定位入口")
        require_contains(returned_home_html, "变化判断：", "带队列恢复态返回首页后，变化对比面板必须显式展示变化判断字段")
        require_contains(returned_home_html, "当前队列仍是主战场", "当前命中的就是最新 Top1 队列时，变化判断不应该再停留在泛化提示")
        require_contains(returned_home_html, "当前队列仍是最新 Top1", "当前命中的就是最新 Top1 队列时，变化卡片标题应明确说明它仍是最新 Top1")
        returned_focus_candidates = parse_focus_candidates(returned_home_html)
        matched_group_candidate = find_focus_candidate(
            returned_focus_candidates,
            [queue_focus_group_name, "当前组别（队列已继续收窄）"],
            "队列恢复后的组别高亮候选",
            require_active=True,
        )
        matched_queue_candidate = find_focus_candidate(
            returned_focus_candidates,
            [f"{queue_focus_group_name} / {queue_focus_name}", "本次恢复命中"],
            "队列恢复后的命中队列候选",
            require_active=True,
        )
        results.append(
            CheckResult(
                name="queue_focus_return_comparison",
                status="passed",
                detail="问题最多队列 -> 明细 -> 返回首页的链路可用，且首页会展示恢复感知与二次回看变化对比。",
                extra={"returned_home_href": return_link.href},
            )
        )
        results.append(
            CheckResult(
                name="queue_focus_return_stable_branch",
                status="passed",
                detail="当前命中的就是最新 Top1 队列时，二次回看变化对比会明确落到“当前队列仍是主战场 / 当前队列仍是最新 Top1”分支。",
                extra={
                    "queue_return_href": return_link.href,
                    "expected_decision": "当前队列仍是主战场",
                    "expected_card_title": "当前队列仍是最新 Top1",
                },
            )
        )
        results.append(
            CheckResult(
                name="queue_return_highlight",
                status="passed",
                detail="问题最多队列 -> 明细 -> 返回首页后，首页会保留快速聚焦区，并同时高亮当前组别和命中队列。",
                extra={
                    "queue_return_href": return_link.href,
                    "matched_group_candidate": matched_group_candidate.text,
                    "matched_queue_candidate": matched_queue_candidate.text,
                },
            )
        )

        alert_only_return_href = build_url(
            frontend_base,
            "/",
            {
                "grain": args.grain,
                "selected_date": selected_date,
                "alert_id": alert_id,
                "return_source": "details",
                "demo_fixture": demo_fixture,
            },
        )
        alert_only_return_html = fetch_html(session, alert_only_return_href)
        require_contains(alert_only_return_html, "变化判断：", "只带 alert_id 返回首页时，变化对比面板必须显式展示变化判断字段")
        require_contains(alert_only_return_html, "还没恢复到具体候选", "只带 alert_id 返回首页时，变化判断应明确说明还没恢复到具体候选")
        require_contains(alert_only_return_html, "当前还停在告警详情层", "只带 alert_id 返回首页时，变化卡片标题应明确说明当前还停在告警详情层")
        results.append(
            CheckResult(
                name="alert_only_return_comparison",
                status="passed",
                detail="只恢复到 alert 详情层时，首页会把变化判断明确落到“还没恢复到具体候选 / 当前还停在告警详情层”。",
                extra={"alert_only_return_href": alert_only_return_href},
            )
        )

        missing_join_key_drift_href = build_url(
            frontend_base,
            "/",
            {
                "grain": args.grain,
                "selected_date": selected_date,
                "alert_id": alert_id,
                "focus_join_key_type": missing_join_key_type,
                "return_source": "details",
                "demo_fixture": demo_fixture,
            },
        )
        missing_join_key_drift_html = fetch_html(session, missing_join_key_drift_href)
        require_contains(missing_join_key_drift_html, "变化判断：", "主键类型漂移时，变化对比面板必须显式展示变化判断字段")
        require_contains(missing_join_key_drift_html, "主键类型已漂移", "返回首页时如果主键类型已经没有命中样本，变化判断必须明确说明当前类型已漂移")
        require_contains(missing_join_key_drift_html, "主键类型已经漂移", "返回首页时如果主键类型已经没有命中样本，变化卡片标题必须明确说明主键类型已经漂移")
        require_contains_any(
            missing_join_key_drift_html,
            ["切到最新类型：", "重新定位当前告警"],
            "主键类型漂移后，首页必须给出切到最新类型或重新定位当前告警的动作",
        )
        results.append(
            CheckResult(
                name="join_key_type_drift_comparison",
                status="passed",
                detail="构造失效主键类型并标记为明细返回时，首页会把二次回看变化对比落到“主键类型已漂移”分支。",
                extra={
                    "missing_join_key_drift_href": missing_join_key_drift_href,
                    "missing_join_key_type": missing_join_key_type,
                },
            )
        )

        same_group_queue_shift_candidate = find_same_group_queue_shift_candidate(
            session,
            api_base,
            args.grain,
            selected_date,
            preferred_rule_codes,
            demo_fixture=demo_fixture,
        )
        if same_group_queue_shift_candidate:
            queue_shift_return_href = build_url(
                frontend_base,
                "/",
                {
                    "grain": args.grain,
                    "selected_date": same_group_queue_shift_candidate["selected_date"],
                    "alert_id": same_group_queue_shift_candidate["alert_id"],
                    "group_name": same_group_queue_shift_candidate["group_name"],
                    "focus_queue_name": same_group_queue_shift_candidate["narrowed_queue_name"],
                    "return_source": "details",
                    "demo_fixture": same_group_queue_shift_candidate.get("demo_fixture") or demo_fixture,
                },
            )
            queue_shift_return_html = fetch_html(session, queue_shift_return_href)
            require_contains(queue_shift_return_html, "变化判断：", "命中同组别双队列样本后，变化对比面板必须显式展示变化判断字段")
            require_contains(queue_shift_return_html, "组别没变，但队列更收敛", "同组别里最新 Top1 队列和当前恢复队列不一致时，变化判断应明确说明队列已经收敛")
            require_contains(
                queue_shift_return_html,
                f"切到最新队列：{same_group_queue_shift_candidate['top_queue_name']}",
                "同组别里最新 Top1 队列更集中时，首页必须给出切到最新队列的明确动作",
            )
            queue_shift_focus_candidates = parse_focus_candidates(queue_shift_return_html)
            matched_queue_shift_group_candidate = find_focus_candidate(
                queue_shift_focus_candidates,
                [same_group_queue_shift_candidate["group_name"], "当前组别（队列已继续收窄）"],
                "同组别队列收敛分支的组别高亮候选",
                require_active=True,
            )
            matched_queue_shift_queue_candidate = find_focus_candidate(
                queue_shift_focus_candidates,
                [
                    f"{same_group_queue_shift_candidate['group_name']} / {same_group_queue_shift_candidate['narrowed_queue_name']}",
                    "本次恢复命中",
                ],
                "同组别队列收敛分支的命中队列候选",
                require_active=True,
            )
            results.append(
                CheckResult(
                    name="queue_return_same_group_shift_branch",
                    status="passed",
                    detail="当当前恢复队列和最新 Top1 队列仍在同一组别时，首页会把二次回看变化对比明确落到“组别没变，但队列更收敛”分支。",
                    extra={
                        "queue_shift_return_href": queue_shift_return_href,
                        "selected_date": same_group_queue_shift_candidate["selected_date"],
                        "alert_id": same_group_queue_shift_candidate["alert_id"],
                        "group_name": same_group_queue_shift_candidate["group_name"],
                        "top_queue_name": same_group_queue_shift_candidate["top_queue_name"],
                        "narrowed_queue_name": same_group_queue_shift_candidate["narrowed_queue_name"],
                        "matched_group_candidate": matched_queue_shift_group_candidate.text,
                        "matched_queue_candidate": matched_queue_shift_queue_candidate.text,
                    },
                )
            )
        else:
            results.append(
                CheckResult(
                    name="queue_return_same_group_shift_branch",
                    status="skipped",
                    detail=f"最近 {COMPARISON_LOOKBACK_DAYS} 天内没有找到“同组别至少两个队列同时命中”的系统级告警样本，暂时无法稳定复验“组别没变，但队列更收敛”分支。",
                    extra={"lookback_days": COMPARISON_LOOKBACK_DAYS, "selected_date": selected_date},
                )
            )

        missing_alert_id = "__wb_missing_alert__"
        invalid_return_href = update_query_values(
            return_link.href,
            {"alert_id": missing_alert_id, "return_alert_id": missing_alert_id},
        )
        invalid_return_html = fetch_html(session, absolutize(frontend_base, invalid_return_href))
        require_contains_any(
            invalid_return_html,
            [
                f"明细页想帮你恢复的 alert_id={missing_alert_id}",
                f"明细页刚尝试帮你恢复的 alert_id={missing_alert_id}",
            ],
            "恢复失败时首页必须明确告诉用户当前 alert_id 已失效",
        )
        require_contains(invalid_return_html, "重新定位当前告警", "恢复失败时首页必须保留重新定位入口")
        require_contains(invalid_return_html, "回到告警列表", "恢复失败时首页必须保留回到告警列表入口")
        results.append(
            CheckResult(
                name="invalid_return_relocalize",
                status="passed",
                detail="构造失效 alert_id 后，首页会显式提示恢复失败并保留重新定位与回列表入口。",
                extra={"invalid_return_href": invalid_return_href, "missing_alert_id": missing_alert_id},
            )
        )

        legacy_details_href = absolutize(frontend_base, remove_dashboard_context(queue_details_link.href))
        legacy_details_html = fetch_html(session, legacy_details_href)
        require_contains(legacy_details_html, "返回首页（旧链接降级恢复）", "缺少 dashboard_* 时应进入旧链接降级面板")
        legacy_links = parse_links(legacy_details_html)
        legacy_return_link = find_link(legacy_links, "按当前范围返回首页")
        if not legacy_return_link.href.startswith("/?"):
            raise CheckFailure(f"旧链接降级恢复返回首页的 href 不是根路由：{legacy_return_link.href}")
        results.append(
            CheckResult(
                name="legacy_fallback_panel",
                status="passed",
                detail="旧链接降级恢复面板存在，且返回首页链接仍然落到根路由。",
                extra={
                    "legacy_details_href": legacy_details_href,
                    "legacy_return_href": legacy_return_link.href,
                },
            )
        )

        passed_count = len([item for item in results if item.status == "passed"])
        skipped_count = len([item for item in results if item.status == "skipped"])
        report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
            "summary": {
                "passed": passed_count,
                "failed": 0,
                "skipped": skipped_count,
                "success": True,
            },
            "context": {
                "frontend_base": frontend_base,
                "api_base": api_base,
                "grain": args.grain,
                "selected_date": selected_date,
                "alert_id": alert_id,
                "rule_code": rule_code,
                "preferred_rule_codes": preferred_rule_codes,
                "demo_fixture": demo_fixture,
            },
            "results": [item.to_dict() for item in results],
        }
    except Exception as exc:
        passed_count = len([item for item in results if item.status == "passed"])
        skipped_count = len([item for item in results if item.status == "skipped"])
        failed_report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
            "summary": {
                "passed": passed_count,
                "failed": 1,
                "skipped": skipped_count,
                "success": False,
            },
            "results": [item.to_dict() for item in results]
            + [
                CheckResult(
                    name="system_alert_browser_semiauto",
                    status="failed",
                    detail=str(exc),
                ).to_dict()
            ],
        }
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(failed_report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(failed_report, ensure_ascii=False, indent=2))
        return 1

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
