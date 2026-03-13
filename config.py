"""Shared configuration: feature themes, keyword lists, channel sets."""

FEATURE_THEMES: dict[str, dict] = {
    "FT-001": {
        "theme": "On-Premises / Air-Gap Deployment",
        "keywords": [
            "on-prem", "on_prem", "on prem", "air-gap", "airgap", "air gap",
            "offline", "local deploy", "private cloud", "disconnected",
            "isolated environment", "self-hosted", "self hosted",
        ],
    },
    "FT-002": {
        "theme": "Observability, Logging & Safety Controls",
        "keywords": [
            "observability", "logging", "audit log", "audit trail", "trace",
            "tracing", "safety", "guardrail", "monitor", "visibility",
            "explainability", "log export", "activity log",
        ],
    },
    "FT-003": {
        "theme": "Licensing & Metering Flexibility",
        "keywords": [
            "licens", "meter", "metering", "quota", "usage limit", "billing",
            "entitlement", "tier", "consumption", "pay-per-use", "overage",
            "license model", "credit",
        ],
    },
    "FT-004": {
        "theme": "Multi-Agent Orchestration & Context Passing",
        "keywords": [
            "multi-agent", "multi agent", "orchestrat", "context pass",
            "handoff", "hand-off", "sub-agent", "subagent", "agent chain",
            "agent routing", "agent collaboration", "nested agent",
        ],
    },
    "FT-005": {
        "theme": "Long-Running / Async Agent Execution",
        "keywords": [
            "long-running", "long running", "async", "asynchronous",
            "background", "queue", "timeout", "persistent execution",
            "batch agent", "durable", "deferred",
        ],
    },
    "FT-006": {
        "theme": "IVR & Voice Channel Integration",
        "keywords": [
            "ivr", "voice", "telephony", "call center", "phone", "speech",
            "voicebot", "voice channel", "contact center", "sip", "twilio",
            "genesys", "amazon connect",
        ],
    },
    "FT-007": {
        "theme": "Enhanced Agent Memory & State Management",
        "keywords": [
            "memory", "state", "persist", "recall", "history",
            "conversation history", "context window", "long-term memory",
            "agent memory", "session state", "stateful",
        ],
    },
    "FT-008": {
        "theme": "Common Agent Templates & Accelerators",
        "keywords": [
            "template", "accelerator", "starter", "blueprint", "prebuilt",
            "pre-built", "sample agent", "agent template", "quick start",
            "out of the box", "ootb",
        ],
    },
    "FT-009": {
        "theme": "Advanced Testing & Simulation Framework",
        "keywords": [
            "test", "simulation", "simulat", "mock", "replay", "debug",
            "unit test", "testing framework", "agent testing", "test harness",
            "eval", "evaluation framework",
        ],
    },
    "FT-010": {
        "theme": "Enterprise Auth & RBAC for Agents",
        "keywords": [
            "rbac", "role-based", "role based", "permission", "sso", "saml",
            "oauth", "access control", "enterprise auth", "authorization",
            "authentication", "identity", "ad integration",
        ],
    },
}

# Demand scoring keyword lists
ENTERPRISE_KEYWORDS = [
    "enterprise", "global", "fortune", "bank", "insurance",
    "healthcare", "pharma", "telco",
]

ESCALATION_KEYWORDS = [
    "escalat", "blocker", "production issue", "critical", "urgent", "p1",
]

RENEWAL_KEYWORDS = [
    "renewal", "churn", "cancel", "at risk", "competitive",
]

# Slack channel classification
HIGH_CHANNELS = {
    "help-tif-voc",
    "product-support-escalations",
    "platform-customer-engagement",
}
MEDIUM_CHANNELS = {
    "help-agent-builder",
    "help-orchestrator",
}
TARGET_CHANNELS = HIGH_CHANNELS | MEDIUM_CHANNELS
