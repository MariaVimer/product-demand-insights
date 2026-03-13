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
from datetime import datetime, timezone
from pathlib import Path


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

    # --- Score ---
    print("[build] Scoring feature themes...")
    from score import score_features
    features = score_features(jira_issues, slack_messages)
    print(f"[build] {len(features)} features scored and ranked")

    # --- Build DATA object ---
    data = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "features": features,
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
