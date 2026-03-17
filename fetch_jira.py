"""
Fetch Jira issues from TIF and AE projects related to AI Agents,
classify them into feature themes, and return structured data.
"""
from __future__ import annotations

import os

import requests
from requests.auth import HTTPBasicAuth

from config import FEATURE_THEMES

JIRA_BASE_URL = "https://uipath.atlassian.net"
JQL = 'project in (TIF, AE) ORDER BY updated DESC'
_PAGE_SIZE = 100


def fetch_jira_issues() -> list[dict]:
    """Return all matching Jira issues, each annotated with matched theme IDs."""
    auth = HTTPBasicAuth(os.environ["JIRA_EMAIL"], os.environ["JIRA_TOKEN"])
    issues: list[dict] = []
    next_page_token: str | None = None

    while True:
        payload: dict = {
            "jql": JQL,
            "maxResults": _PAGE_SIZE,
            "fields": [
                "summary", "status", "labels", "components",
                "created", "updated", "priority", "reporter", "assignee", "comment", "votes"
            ],
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token

        resp = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/search/jql",
            auth=auth,
            json=payload,
            timeout=30,
        )
        if not resp.ok:
            print(f"[jira] HTTP {resp.status_code}: {resp.text}")
        resp.raise_for_status()
        body = resp.json()

        batch = body.get("issues", [])
        for raw in batch:
            f = raw.get("fields", {})
            issues.append({
                "key": raw["key"],
                "summary": f.get("summary", ""),
                "status": (f.get("status") or {}).get("name", ""),
                "labels": f.get("labels", []),
                "components": [c["name"] for c in (f.get("components") or [])],
                "created": f.get("created", ""),
                "updated": f.get("updated", ""),
                "priority": (f.get("priority") or {}).get("name", ""),
                "reporter": (f.get("reporter") or {}).get("displayName", ""),
                "assignee": (f.get("assignee") or {}).get("displayName", ""),
                "comment_count": (f.get("comment") or {}).get("total", 0),
                "votes": (f.get("votes") or {}).get("votes", 0),
                "themes": _classify_issue(f),
            })

        next_page_token = body.get("nextPageToken")
        if not batch or not next_page_token:
            break

    return issues


def _classify_issue(fields: dict) -> list[str]:
    """Return list of FT-xxx IDs whose keywords match this issue's text."""
    text = " ".join([
        fields.get("summary", ""),
        " ".join(fields.get("labels", [])),
        " ".join(c["name"] for c in (fields.get("components") or [])),
    ]).lower()

    return [
        tid
        for tid, tdata in FEATURE_THEMES.items()
        if any(kw.lower() in text for kw in tdata["keywords"])
    ]
