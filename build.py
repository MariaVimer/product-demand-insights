"""
Build script: fetches live Jira + Slack data, scores features, and
regenerates index.html by replacing the `const DATA = {...};` block.

Usage:
    python build.py

Secrets are read from environment variables.
Locally, place a .env file next to this script (python-dotenv will load it).
In GitHub Actions, set them as repository secrets.

Required env vars:
    JIRA_EMAIL   — Atlassian account email
    JIRA_TOKEN   — Jira API token
    SLACK_TOKEN  — Slack bot token (xoxb-...)
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PERIODS = [30, 60, 90, 180, 365]


def _filter_by_days(
    jira_issues: list[dict],
    slack_messages: list[dict],
    days: int,
    now: datetime,
) -> tuple[list[dict], list[dict]]:
    cutoff_str = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    cutoff_ts = (now - timedelta(days=days)).timestamp()
    return (
        [i for i in jira_issues if i.get("created", "")[:10] >= cutoff_str],
        [m for m in slack_messages if float(m.get("ts", 0)) >= cutoff_ts],
    )


def _load_dotenv() -> None:
    """Load .env if python-dotenv is available (local development only)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # GitHub Actions provides env vars directly


def _check_env() -> None:
    required = ("JIRA_EMAIL", "JIRA_TOKEN", "SLACK_TOKEN")
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"[build] ERROR — missing environment variables: {missing}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    _load_dotenv()
    _check_env()

    # --- Fetch ---
    print("[build] Fetching Jira issues...")
    from fetch_jira import fetch_jira_issues
    jira_issues = fetch_jira_issues()
    print(f"[build] {len(jira_issues)} Jira issues fetched")

    print("[build] Fetching Slack messages...")
    from fetch_slack import fetch_slack_messages
    slack_messages = fetch_slack_messages()
    print(f"[build] {len(slack_messages)} Slack messages fetched (theme-matched)")

    # --- Score per time window ---
    print("[build] Scoring feature themes...")
    from score import score_features
    now = datetime.now(timezone.utc)
    periods: dict[str, list] = {}
    for days in PERIODS:
        fj, fs = _filter_by_days(jira_issues, slack_messages, days, now)
        periods[str(days)] = score_features(fj, fs)
        print(f"[build]   {days}d window: {len(fj)} Jira, {len(fs)} Slack")
    print(f"[build] {len(periods['180'])} features scored and ranked")

    # --- Build DATA object ---
    data = {
        "last_updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "features": periods["180"],
        "periods": periods,
    }

    # --- Inject into index.html ---
    index_path = Path(__file__).parent / "index.html"
    if not index_path.exists():
        print(f"[build] ERROR — {index_path} not found", file=sys.stderr)
        sys.exit(1)

    html = index_path.read_text(encoding="utf-8")
    replacement = "const DATA = " + json.dumps(data, indent=2, ensure_ascii=False) + ";"

    new_html, n = re.subn(
        r"const DATA = \{.*?\};",
        replacement,
        html,
        flags=re.DOTALL,
    )

    if n == 0:
        print(
            "[build] ERROR — could not find `const DATA = {...};` in index.html.\n"
            "        Ensure the block uses exactly: const DATA = {  ...  };",
            file=sys.stderr,
        )
        sys.exit(1)

    index_path.write_text(new_html, encoding="utf-8")
    print(f"[build] index.html updated — last_updated={data['last_updated']}")


if __name__ == "__main__":
    main()
