// All text + vision calls go to OpenAI (Chat Completions). One key for everything.
const BASE = process.env.OPENAI_API_BASE || "https://api.openai.com/v1";
export const CHAT_MODEL = process.env.CHAT_MODEL || "gpt-4o";

export const llmReady = () => !!process.env.OPENAI_API_KEY;

const headers = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
});

async function call(body) {
  const res = await fetch(`${BASE}/chat/completions`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ model: CHAT_MODEL, ...body }),
  });
  if (!res.ok) throw new Error(`OpenAI error ${res.status}: ${await res.text()}`);
  return res;
}

export async function complete({ system, messages, maxTokens = 1200, json = false, deterministic = false }) {
  const res = await call({
    max_completion_tokens: maxTokens,
    ...(deterministic ? { temperature: 0, seed: 20260101 } : {}),
    ...(json ? { response_format: { type: "json_object" } } : {}),
    messages: [...(system ? [{ role: "system", content: system }] : []), ...messages],
  });
  return (await res.json()).choices[0].message.content;
}

// Calls onText(chunk) for each streamed piece.
export async function stream({ system, messages, maxTokens = 1200, onText }) {
  const res = await call({
    stream: true,
    max_completion_tokens: maxTokens,
    messages: [{ role: "system", content: system }, ...messages],
  });
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop();
    for (const l of lines) {
      if (!l.startsWith("data: ") || l.includes("[DONE]")) continue;
      const t = JSON.parse(l.slice(6)).choices?.[0]?.delta?.content;
      if (t) onText(t);
    }
  }
}
