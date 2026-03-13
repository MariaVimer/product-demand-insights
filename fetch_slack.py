"""
Fetch Slack messages from monitored channels over the last 180 days,
classify messages into feature themes, and return structured data.

Required bot token scopes: channels:history, channels:read
The bot must be invited to each monitored channel.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import (
    ENTERPRISE_KEYWORDS,
    ESCALATION_KEYWORDS,
    FEATURE_THEMES,
    HIGH_CHANNELS,
    MEDIUM_CHANNELS,
    RENEWAL_KEYWORDS,
    TARGET_CHANNELS,
)

_LOOKBACK_DAYS = 180
_PAGE_SIZE = 200
_RATE_LIMIT_SLEEP = 0.5  # seconds between paginated requests

# Patterns to extract company/customer names from message text
_CUSTOMER_RE = re.compile(
    r'(?:customer|client|from|at|for)\s+([A-Z][A-Za-z0-9&]{1,}(?:\s+[A-Z][A-Za-z0-9&]{1,}){0,3})',
)
_ALLCAPS_RE = re.compile(r'\b([A-Z]{3,})\b')
_STOP_WORDS = {
    "AND", "OR", "BUT", "THE", "FOR", "WITH", "API", "SDK", "URL",
    "HTTP", "HTTPS", "FYI", "TBD", "ETA", "SLA", "QA", "POC", "AI",
    "ML", "UI", "UX", "PM", "PR", "PO", "CX", "CS", "OK", "NO",
}


def fetch_slack_messages() -> list[dict]:
    """Return all relevant Slack messages classified by feature theme."""
    client = WebClient(token=os.environ["SLACK_TOKEN"])
    channel_map = _resolve_channels(client)

    oldest = str(
        (datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)).timestamp()
    )

    messages: list[dict] = []
    for name, channel_id in channel_map.items():
        quality = "HIGH" if name in HIGH_CHANNELS else "MEDIUM"
        print(f"[fetch_slack] Fetching #{name} ({channel_id})...")
        raw_msgs = _fetch_channel_history(client, channel_id, oldest)
        print(f"[fetch_slack]   {len(raw_msgs)} messages")

        for msg in raw_msgs:
            text = msg.get("text", "")
            if not text.strip():
                continue
            themes = _classify_message(text)
            if not themes:
                continue  # skip messages unrelated to any feature theme

            messages.append({
                "text": text,
                "user": msg.get("user", ""),
                "ts": msg.get("ts", ""),
                "channel_id": channel_id,
                "channel_name": name,
                "channel_quality": quality,
                "reactions": msg.get("reactions", []),
                "reply_count": msg.get("reply_count", 0),
                "themes": themes,
                "has_escalation": _has_any(text, ESCALATION_KEYWORDS),
                "has_enterprise": _has_any(text, ENTERPRISE_KEYWORDS),
                "has_renewal": _has_any(text, RENEWAL_KEYWORDS),
                "customer_name": _extract_customer(text),
                "permalink": _make_permalink(channel_id, msg.get("ts", "")),
                "date_label": _ts_to_label(msg.get("ts", "")),
            })

    return messages


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_channels(client: WebClient) -> dict[str, str]:
    """Return {channel_name: channel_id} for all TARGET_CHANNELS found."""
    result: dict[str, str] = {}
    cursor: Optional[str] = None

    while len(result) < len(TARGET_CHANNELS):
        kwargs: dict = {
            "exclude_archived": True,
            "types": "public_channel",
            "limit": 200,
        }
        if cursor:
            kwargs["cursor"] = cursor
        try:
            resp = client.conversations_list(**kwargs)
        except SlackApiError as exc:
            print(f"[fetch_slack] conversations_list error: {exc}")
            break

        for ch in resp.get("channels", []):
            if ch["name"] in TARGET_CHANNELS:
                result[ch["name"]] = ch["id"]

        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break

    missing = TARGET_CHANNELS - set(result)
    if missing:
        print(f"[fetch_slack] WARNING: channels not found (bot may not be invited): {missing}")

    return result


def _fetch_channel_history(
    client: WebClient, channel_id: str, oldest: str
) -> list[dict]:
    messages: list[dict] = []
    cursor: Optional[str] = None

    while True:
        kwargs: dict = {"channel": channel_id, "oldest": oldest, "limit": _PAGE_SIZE}
        if cursor:
            kwargs["cursor"] = cursor
        try:
            resp = client.conversations_history(**kwargs)
        except SlackApiError as exc:
            print(f"[fetch_slack] conversations_history error ({channel_id}): {exc}")
            break

        messages.extend(resp.get("messages", []))

        if not resp.get("has_more"):
            break
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(_RATE_LIMIT_SLEEP)

    return messages


def _classify_message(text: str) -> list[str]:
    lower = text.lower()
    return [
        tid
        for tid, tdata in FEATURE_THEMES.items()
        if any(kw.lower() in lower for kw in tdata["keywords"])
    ]


def _has_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)


def _extract_customer(text: str) -> Optional[str]:
    """Best-effort extraction of a company/customer name from message text."""
    m = _CUSTOMER_RE.search(text)
    if m:
        name = m.group(1).strip()
        if name.upper() not in _STOP_WORDS and len(name) >= 3:
            return name

    # Fall back to ALL-CAPS abbreviations (e.g. "IBM", "KPMG")
    for m2 in _ALLCAPS_RE.finditer(text):
        candidate = m2.group(1)
        if candidate not in _STOP_WORDS:
            return candidate

    return None


def _make_permalink(channel_id: str, ts: str) -> str:
    ts_clean = ts.replace(".", "")
    return f"https://uipath.slack.com/archives/{channel_id}/p{ts_clean}"


def _ts_to_label(ts: str) -> str:
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        return dt.strftime("%b %d")
    except (ValueError, OSError):
        return ""
