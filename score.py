"""
Score feature themes using demand and confidence formulas.
Returns a ranked list of features matching the DATA.features schema expected
by index.html.

Demand  = (unique_customers × 5) + (total_mentions × 1)
        + (enterprise_signals × 5) + (escalation_signals × 5)
        + (renewal_risk_signals × 10)

Confidence (max 100, additive):
  signal_type_base        : CUSTOMER_VALIDATED=40 | FIELD_OBSERVATION=25
                            | AUTOMATED_SIGNAL=15 | INTERNAL_DISCUSSION=10
  source_diversity        : 3+ sources=15 | 2=10 | 1=5
  channel_quality         : HIGH=15 | MEDIUM=10 | none=5
  named_customer_validation: 3+ named=10 | 1-2=7 | 0=0
  escalation_confirmation : any=10 | none=0
  backlog_alignment       : IN_BACKLOG=10 | IN_PLANNING=5 | NO_TICKET=0
"""
from __future__ import annotations

from config import FEATURE_THEMES, HIGH_CHANNELS

# (min_score, label) — first match wins (descending)
_PRIORITY_TIERS = [(80, "critical"), (50, "high"), (25, "moderate"), (0, "low")]
_CONF_TIERS = [(70, "HIGH"), (40, "MODERATE"), (0, "LOW")]


def score_features(
    jira_issues: list[dict],
    slack_messages: list[dict],
) -> list[dict]:
    """Return list of feature dicts sorted by demand score (highest first)."""
    features = []

    for theme_id, theme_data in FEATURE_THEMES.items():
        issues = [i for i in jira_issues if theme_id in i.get("themes", [])]
        msgs = [m for m in slack_messages if theme_id in m.get("themes", [])]

        demand, demand_components = _demand_score(issues, msgs)
        confidence, conf_rationale = _confidence_score(issues, msgs, demand_components)

        unique_customers = demand_components["unique_customers"]
        escalations = demand_components["escalation_signals"]
        renewal = demand_components["renewal_risk_signals"]

        features.append({
            "id": theme_id,
            "rank": 0,  # set after sort
            "theme": theme_data["theme"],
            "priority": _tier(_PRIORITY_TIERS, demand),
            "demand": demand,
            "confidence": confidence,
            "confLevel": _tier(_CONF_TIERS, confidence),
            "customers": unique_customers,
            "escalations": escalations,
            "renewal": renewal,
            "quote": _best_quote(msgs, issues),
            "confRationale": conf_rationale,
            "jira": [i["key"] for i in issues[:10]],
            "slack": _slack_refs(msgs),
            "_sort_key": demand,
        })

    features.sort(key=lambda x: x["_sort_key"], reverse=True)
    for i, feat in enumerate(features, 1):
        feat["rank"] = i
        del feat["_sort_key"]

    return features


# ---------------------------------------------------------------------------
# Demand scoring
# ---------------------------------------------------------------------------

def _demand_score(issues: list[dict], msgs: list[dict]) -> tuple[int, dict]:
    named = {m["customer_name"] for m in msgs if m.get("customer_name")}
    unique_customers = len(named)
    jira_mentions = len(issues)
    slack_mentions = len(msgs)
    enterprise_signals = sum(1 for m in msgs if m.get("has_enterprise"))
    escalation_signals = (
        sum(1 for m in msgs if m.get("has_escalation"))
        + sum(1 for i in issues if (i.get("priority") or "").lower() in ("critical", "blocker", "highest"))
    )
    renewal_risk_signals = sum(1 for m in msgs if m.get("has_renewal"))

    score = (
        unique_customers * 5
        + jira_mentions * 1
        + slack_mentions * 2
        + enterprise_signals * 5
        + escalation_signals * 5
        + renewal_risk_signals * 10
    )
    components = {
        "unique_customers": unique_customers,
        "jira_mentions": jira_mentions,
        "slack_mentions": slack_mentions,
        "enterprise_signals": enterprise_signals,
        "escalation_signals": escalation_signals,
        "renewal_risk_signals": renewal_risk_signals,
        "named_customers": named,
    }
    return score, components


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _confidence_score(
    issues: list[dict],
    msgs: list[dict],
    demand_components: dict,
) -> tuple[int, str]:
    rationale: list[str] = []
    named_count = demand_components["unique_customers"]
    high_msgs = [m for m in msgs if m.get("channel_quality") == "HIGH"]

    # signal_type_base
    if named_count > 0:
        base = 40
        rationale.append(f"customer-validated ({named_count} named customers)")
    elif high_msgs:
        base = 25
        rationale.append("field observation via customer-facing channels")
    elif msgs:
        base = 15
        rationale.append("automated signal from product channels")
    else:
        base = 10
        rationale.append("internal discussion only")

    # source_diversity
    sources: set[str] = set()
    if issues:
        sources.add("jira")
    if any(m.get("channel_quality") == "HIGH" for m in msgs):
        sources.add("high_channels")
    if any(m.get("channel_quality") == "MEDIUM" for m in msgs):
        sources.add("medium_channels")
    n = len(sources)
    src_score = 15 if n >= 3 else (10 if n == 2 else 5)
    rationale.append(f"{n} signal source(s)")

    # channel_quality (best present)
    if any(m.get("channel_quality") == "HIGH" for m in msgs):
        ch_score = 15
        rationale.append("signals from HIGH-quality channels")
    elif msgs:
        ch_score = 10
        rationale.append("signals from MEDIUM-quality channels")
    else:
        ch_score = 5

    # named_customer_validation
    nc_score = 10 if named_count >= 3 else (7 if named_count >= 1 else 0)

    # escalation_confirmation
    esc_score = 10 if demand_components["escalation_signals"] > 0 else 0
    if esc_score:
        rationale.append("escalation confirmed")

    # backlog_alignment
    if issues:
        backlog_score = 10
        rationale.append(f"{len(issues)} Jira issue(s) in backlog")
    else:
        backlog_score = 0

    total = min(100, base + src_score + ch_score + nc_score + esc_score + backlog_score)
    return total, "; ".join(rationale)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tier(thresholds: list[tuple], value: int) -> str:
    for minimum, label in thresholds:
        if value >= minimum:
            return label
    return thresholds[-1][1]


def _best_quote(msgs: list[dict], issues: list[dict]) -> str:
    # Prefer messages that have an escalation signal and enough text
    for m in msgs:
        if m.get("has_escalation") and len(m.get("text", "")) > 40:
            return m["text"][:250].strip()
    # Any substantial Slack message
    for m in msgs:
        if len(m.get("text", "")) > 40:
            return m["text"][:250].strip()
    # Fall back to a Jira summary
    for i in issues:
        if i.get("summary"):
            return i["summary"]
    return ""


def _slack_refs(msgs: list[dict]) -> list[dict]:
    """Up to 5 representative refs (one per channel, most recent first)."""
    seen: set[str] = set()
    refs: list[dict] = []
    for m in sorted(msgs, key=lambda x: float(x.get("ts") or 0), reverse=True):
        ch = m.get("channel_name", "")
        if ch not in seen:
            refs.append({
                "label": f"#{ch} ({m.get('date_label', '')})",
                "url": m.get("permalink", ""),
            })
            seen.add(ch)
        if len(refs) >= 5:
            break
    return refs
