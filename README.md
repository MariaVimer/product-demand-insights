# Product Demand Insights

A tool to help P&E teams work on features users actually want. It contains a dashboard that shows which AI Agents features customers are asking for the most — ranked by feedback logged in Jira and Slack. You can also prompt it to see if your roadmap covers the features in demand and what's missing.

## What it does

Every Monday morning it pulls data from:
- **Jira** (projects TIF and AE) — issues tagged with `ai-agents` or the `AI Agents` component
- **Slack** — messages from customer-facing channels (see full list below)

It classifies everything into 10 feature themes (things like "Multi-Agent Orchestration", "Enterprise Auth", "On-Prem Deployment"), scores each one based on how much activity is coming in, and updates the dashboard with a ranked list.

## The scoring

Each feature gets a demand score based on:
- How many Jira issues mention it
- How many Slack messages mention it
- Whether the activity comes from enterprise customers, escalations, or renewal risk conversations (those count more)

## How it's built

- `fetch_jira.py` — pulls Jira issues via the Atlassian REST API
- `fetch_slack.py` — pulls Slack messages via the Slack SDK
- `score.py` — applies the demand scoring formula
- `build.py` — orchestrates everything and injects the results into `index.html`
- `.github/workflows/refresh.yml` — runs the whole pipeline every Monday at 8am UTC (4am EST / 3am EDT)

The dashboard is a single `index.html` file hosted on GitHub Pages. The workflow commits updated data directly to the repo, so there's no separate backend.

## Running locally

```bash
cp .env.example .env
# fill in JIRA_EMAIL, JIRA_TOKEN, SLACK_TOKEN
pip install -r requirements.txt
python build.py
```

## Slack channels monitored

| Channel | Priority |
|---------|----------|
| `#help-tif-voc` | High |
| `#product-support-escalations` | High |
| `#platform-customer-engagement` | High |
| `#help-agent-builder` | Medium |
| `#help-orchestrator` | Medium |
