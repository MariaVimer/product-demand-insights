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

Current dashboard data (${data.last_updated}):
${JSON.stringify(data.features.map(f => ({
  id: f.id, rank: f.rank, theme: f.theme, demand: f.demand,
  confidence: f.confidence, priority: f.priority,
  customers: f.customers, escalations: f.escalations, renewal: f.renewal,
  jira_count: f.jira.length, quote: f.quote
})), null, 2)}

Guidelines:
- Answer directly without preamble like "based on the data"
- Use markdown formatting: **bold**, bullet lists with -, numbered lists
- Reference specific feature IDs and scores when relevant
- Be concise but complete`;

  try {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 800,
        system: systemPrompt,
        messages,
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
