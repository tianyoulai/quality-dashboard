from __future__ import annotations

from typing import Any

import requests

from storage.tidb_manager import _get_secret

WECOM_MAX_LEN = 4096


def resolve_wecom_webhook_url(
    webhook_url: str | None = None,
    webhook_key: str | None = None,
) -> str:
    explicit_url = str(webhook_url or "").strip()
    if explicit_url:
        return explicit_url

    explicit_key = str(webhook_key or "").strip()
    if explicit_key:
        return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={explicit_key}"

    configured_url = (
        _get_secret("wecom.webhook_url")
        or _get_secret("wecom_webhook_url")
        or _get_secret("wecom.webhook")
    )
    if configured_url:
        return str(configured_url).strip()

    configured_key = (
        _get_secret("wecom.webhook_key")
        or _get_secret("wecom_webhook_key")
        or _get_secret("wework_webhook_key")
    )
    if configured_key:
        return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={str(configured_key).strip()}"

    raise ValueError("未配置企业微信群 webhook，请先在 secrets / settings.json 中配置 wecom_webhook_url 或 wecom_webhook_key")


def split_markdown_for_wecom(content: str, max_len: int = WECOM_MAX_LEN) -> list[str]:
    if len(content) <= max_len:
        return [content]

    lines = content.split("\n")
    parts: list[str] = []
    current: list[str] = []
    current_len = 0

    for raw_line in lines:
        line = raw_line
        if len(line) > max_len - 50:
            line = line[: max_len - 80] + "...（内容过长已截断）"

        projected = current_len + len(line) + 1
        if projected > max_len and current:
            parts.append("\n".join(current))
            current = [line]
            current_len = len(line) + 1
        else:
            current.append(line)
            current_len = projected

    if current:
        parts.append("\n".join(current))
    return parts


def send_wecom_webhook(
    content: str,
    mentioned_list: list[str] | None = None,
    webhook_url: str | None = None,
    webhook_key: str | None = None,
) -> dict[str, Any]:
    resolved_url = resolve_wecom_webhook_url(webhook_url=webhook_url, webhook_key=webhook_key)
    payload: dict[str, Any] = {
        "msgtype": "markdown",
        "markdown": {"content": content},
    }
    if mentioned_list:
        payload["markdown"]["mentioned_list"] = mentioned_list

    response = requests.post(resolved_url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def send_wecom_webhook_with_split(
    content: str,
    mentioned_list: list[str] | None = None,
    webhook_url: str | None = None,
    webhook_key: str | None = None,
    title: str | None = None,
    detail_url: str | None = None,
    footer: str | None = None,
) -> tuple[bool, str]:
    parts = split_markdown_for_wecom(content)
    errors: list[str] = []
    clean_title = str(title or "").strip()
    clean_footer = str(footer or "").strip()
    clean_detail_url = str(detail_url or "").strip()

    for idx, part in enumerate(parts):
        message = part
        if len(parts) > 1 and clean_title:
            message = f"{clean_title} ({idx + 1}/{len(parts)})\n---\n{message}"

        if idx == len(parts) - 1:
            extra_lines: list[str] = []
            if clean_detail_url:
                extra_lines.append(f"> 详情链接：{clean_detail_url}")
            if clean_footer:
                extra_lines.append(clean_footer)
            if extra_lines:
                message = f"{message}\n\n" + "\n".join(extra_lines)

        try:
            result = send_wecom_webhook(
                message,
                mentioned_list=mentioned_list,
                webhook_url=webhook_url,
                webhook_key=webhook_key,
            )
            if result.get("errcode") != 0:
                errors.append(f"第{idx + 1}段推送失败: {result}")
        except Exception as exc:
            errors.append(f"第{idx + 1}段异常: {exc}")

    if errors:
        return False, "; ".join(errors)
    return True, f"共 {len(parts)} 条消息已推送"
