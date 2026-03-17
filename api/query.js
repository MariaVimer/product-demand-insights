// Fetch a Confluence page by URL and return plain text content + title.
// Returns null if URL is not a Confluence page or fetch fails.
async function fetchConfluencePage(url, email, token) {
  const match = url.match(/atlassian\.net\/wiki\/(?:spaces\/[^/]+\/pages\/(\d+)|x\/([A-Za-z0-9_-]+))/);
  if (!match) return null;

  const auth = Buffer.from(`${email}:${token}`).toString('base64');
  const headers = { Authorization: `Basic ${auth}`, Accept: 'application/json' };

  let pageId = match[1];

  // Short-link format (/wiki/x/XXXX) — resolve to page ID first
  if (!pageId && match[2]) {
    const tiny = await fetch(url, { method: 'HEAD', redirect: 'follow' });
    const resolved = tiny.url;
    const m2 = resolved.match(/pages\/(\d+)/);
    if (!m2) return null;
    pageId = m2[1];
  }

  const resp = await fetch(
    `https://uipath.atlassian.net/wiki/rest/api/content/${pageId}?expand=body.storage,title`,
    { headers }
  );
  if (!resp.ok) return null;

  const data = await resp.json();
  const title = data.title || 'Confluence page';
  // Strip Confluence storage XML/HTML to plain text
  const raw = (data.body?.storage?.value || '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  // Truncate to ~12 000 chars to stay within token budget
  const content = raw.length > 12000 ? raw.slice(0, 12000) + '\n… [truncated]' : raw;
  return { title, content };
}

// Replace any Confluence URLs in the last user message with fetched page content.
async function resolveConfluenceUrls(messages) {
  if (!process.env.JIRA_EMAIL || !process.env.JIRA_TOKEN) return messages;

  const out = [...messages];
  const last = out[out.length - 1];
  if (!last || last.role !== 'user') return out;

  const urlRe = /https:\/\/[^\s]+\.atlassian\.net\/wiki\/[^\s)">]*/g;
  const urls = last.content.match(urlRe);
  if (!urls) return out;

  let content = last.content;
  for (const url of urls) {
    try {
      const page = await fetchConfluencePage(url, process.env.JIRA_EMAIL, process.env.JIRA_TOKEN);
      if (page) {
        content = content.replace(url, `[Confluence page: "${page.title}"]\n\n${page.content}`);
      } else {
        content = content.replace(url, `[Failed to fetch Confluence page — null response. URL: ${url}]`);
      }
    } catch (e) {
      content = content.replace(url, `[Failed to fetch Confluence page — error: ${e.message}. URL: ${url}]`);
    }
  }
  out[out.length - 1] = { ...last, content };
  return out;
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { messages, data } = req.body;
  if (!messages || !messages.length || !data) {
    return res.status(400).json({ error: 'Missing messages or data' });
  }

  const systemPrompt = `You are a product analyst assistant for UiPath's AI Agents team.
You have access to a demand dashboard that ranks feature themes by customer demand, scored from Jira issues and Slack messages.
When making recommendations, factor in both customer demand signals AND the competitive landscape in enterprise AI agents.

Current dashboard data (${data.last_updated}):
${JSON.stringify(data.features.map(f => ({
  id: f.id, rank: f.rank, theme: f.theme, demand: f.demand,
  confidence: f.confidence, priority: f.priority,
  customers: f.customers, escalations: f.escalations, renewal: f.renewal,
  jira_count: f.jira.length, quote: f.quote
})), null, 2)}

Competitor context — enterprise AI agents space (use your knowledge, flag if uncertain):
- **Microsoft Copilot Studio**: strong on multi-agent orchestration, Teams/M365 integration, RBAC, and enterprise auth. Weak on on-prem/air-gap and async execution.
- **Salesforce Agentforce**: leading on CRM-native agent memory and state, customer-facing voice/IVR agents, and named-account validation. Limited cross-platform orchestration.
- **Google Agentspace / Vertex AI Agents**: strong on observability, logging, and LLM evals. Weak on enterprise licensing flexibility and no-code agent templates.
- **ServiceNow AI Agents**: strong on ITSM workflow templates and RBAC. Limited testing/simulation framework and async execution.
- **AWS Bedrock Agents**: strong on async/long-running execution and on-prem (Outposts). Weak on multi-agent orchestration UX and pre-built templates.
- **Glean**: strong on enterprise search across tools but not a full agent platform.

When a feature has both high customer demand AND a competitor gap, flag it as a **strategic priority**.
When a competitor leads on a feature UiPath customers are asking for, flag it as a **competitive risk**.

Pasted content analysis:
When the user pastes a wiki page, roadmap, PRD, or backlog (detected by length or structure), automatically:
1. Extract the feature/initiative names or themes from the pasted content
2. Cross-reference each against the demand dashboard data
3. Flag: **high-demand gap** (customers asking for it, not in their roadmap), **low-demand investment** (roadmap item with low demand score), **well-aligned** (roadmap matches top demand), and **competitive risk** (competitor leads + customer demand exists)
4. End with a prioritized recommendation on what to add, cut, or re-prioritize

Guidelines:
- Answer directly without preamble like "based on the data"
- Use markdown: **bold**, bullet lists with -, numbered lists
- Reference specific feature IDs and scores when relevant
- Call out competitive angles only when genuinely relevant to the question
- Be concise but complete`;

  try {
    const resolvedMessages = await resolveConfluenceUrls(messages);

    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 1200,
        system: systemPrompt,
        messages: resolvedMessages,
      }),
    });

    if (!response.ok) {
      const err = await response.text();
      return res.status(502).json({ error: `Claude API error: ${err}` });
    }

    const result = await response.json();
    return res.status(200).json({ answer: result.content[0].text });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}
