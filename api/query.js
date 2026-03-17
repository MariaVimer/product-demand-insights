export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { question, data } = req.body;
  if (!question || !data) {
    return res.status(400).json({ error: 'Missing question or data' });
  }

  const systemPrompt = `You are a product analyst assistant for UiPath's AI Agents team.
You have access to a demand dashboard that ranks feature themes by customer demand,
scored from Jira issues and Slack messages.

The current dashboard data is:
${JSON.stringify(data, null, 2)}

Answer questions about the data concisely and directly.
- Reference specific feature IDs, demand scores, and confidence levels when relevant
- If asked about the roadmap or gaps, use the jira array to assess coverage
- Keep responses under 200 words
- Use HTML for formatting (<strong>, <br>, bullet points as &#8226;)
- Do not say "based on the data provided" — just answer directly`;

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
        max_tokens: 400,
        system: systemPrompt,
        messages: [{ role: 'user', content: question }],
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
