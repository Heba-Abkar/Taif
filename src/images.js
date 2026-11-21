// Image generation via OpenAI Images API (same OPENAI_API_KEY).
const BASE = process.env.OPENAI_API_BASE || "https://api.openai.com/v1";

// Pick an image model this key can actually use (IMAGE_MODEL overrides).
const PREFERRED = ["gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini", "dall-e-2"];
let cached;
export async function availableImageModels() {
  const res = await fetch(`${BASE}/models`, { headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` } });
  if (!res.ok) throw new Error(`Models error ${res.status}: ${await res.text()}`);
  return (await res.json()).data.map((m) => m.id).filter((id) => /image|dall/i.test(id)).sort();
}
export async function imageModel() {
  if (cached) return cached;
  const ids = await availableImageModels();
  const wanted = process.env.IMAGE_MODEL;
  if (wanted && ids.includes(wanted)) return (cached = wanted);
  if (wanted) console.warn(`IMAGE_MODEL=${wanted} is not available for this key; picking automatically.`);
  cached = PREFERRED.find((m) => ids.includes(m)) || ids[0];
  if (!cached) throw new Error("This API key has no image model available (no gpt-image-* / dall-e).");
  console.log("Using image model:", cached);
  return cached;
}

export const imageReady = () => !!process.env.OPENAI_API_KEY;

export async function generateImage(prompt, { size = "1536x1024" } = {}) {
  const res = await fetch(`${BASE}/images/generations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
    },
    body: JSON.stringify({ model: await imageModel(), prompt, size, n: 1 }),
  });
  if (!res.ok) throw new Error(`Image error ${res.status}: ${await res.text()}`);
  const item = (await res.json()).data?.[0];
  if (item?.b64_json) return { b64: item.b64_json, mime: "image/png" };
  if (item?.url) return { url: item.url };
  throw new Error("No image returned");
}

// Edit the user's own photo (keeps the same building, applies the requested changes).
export async function editImage(buffer, mime, prompt) {
  const fd = new FormData();
  fd.append("model", await imageModel());
  fd.append("prompt", prompt);
  fd.append("size", "auto");
  fd.append("n", "1");
  fd.append("image", new Blob([buffer], { type: mime }), `photo.${mime === "image/png" ? "png" : mime === "image/webp" ? "webp" : "jpg"}`);
  const res = await fetch(`${BASE}/images/edits`, {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
    body: fd,
  });
  if (!res.ok) throw new Error(`Image edit error ${res.status}: ${await res.text()}`);
  const item = (await res.json()).data?.[0];
  if (item?.b64_json) return { b64: item.b64_json, mime: "image/png" };
  if (item?.url) return { url: item.url };
  throw new Error("No image returned");
}
