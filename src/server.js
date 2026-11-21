import "dotenv/config";
import express from "express";
import cors from "cors";
import multer from "multer";
import rateLimit from "express-rate-limit";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { style, SYSTEM_PROMPT, styleSummary } from "./knowledge.js";
import { complete, stream, llmReady, CHAT_MODEL } from "./llm.js";
import { editImage, imageReady, availableImageModels } from "./images.js";

const PORT = process.env.PORT || 3000;

const app = express();
app.set("trust proxy", 1); // behind the host's proxy: real client IP for rate limits
app.use(cors({ origin: process.env.CORS_ORIGIN?.split(",") || true }));
app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(path.dirname(fileURLToPath(import.meta.url)), "../public")));
app.use("/api/", rateLimit({ windowMs: 60_000, limit: 30 }));
// Image analysis / generation cost money: cap them per visitor (default 8 per hour).
const aiCap = rateLimit({
  windowMs: 3_600_000,
  limit: Number(process.env.AI_LIMIT_PER_HOUR) || 8,
  message: { error: "تجاوزت الحد المسموح لهذه الساعة، حاول لاحقاً." },
});
app.use(["/api/analyze-image", "/api/generate-image"], aiCap);

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (_req, file, cb) =>
    cb(null, ["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.mimetype)),
});

const needKey = (_req, res, next) =>
  llmReady() ? next() : res.status(503).json({ error: "OPENAI_API_KEY is not set" });

const wrap = (fn) => (req, res) =>
  fn(req, res).catch((e) => {
    console.error(e);
    if (!res.headersSent) res.status(500).json({ error: e.message });
    else res.end();
  });

// ---------- Content API ----------
app.get("/api/health", (_req, res) =>
  res.json({ ok: true, ai: llmReady(), imageGeneration: imageReady(), chatModel: CHAT_MODEL })
);
app.get("/api/image-models", needKey, wrap(async (_req, res) => res.json(await availableImageModels())));
app.get("/api/style", (_req, res) => res.json(style));
app.get("/api/elements", (_req, res) => res.json(style.elements));
app.get("/api/elements/:id", (req, res) => {
  const el = style.elements.find((e) => e.id === req.params.id);
  return el ? res.json(el) : res.status(404).json({ error: "not found" });
});
app.get("/api/documents", (_req, res) => res.json(style.documents));

// ---------- Chat assistant, optional SSE streaming ----------
// body: { messages: [{role:"user"|"assistant", content:"..."}], stream?: boolean }
app.post("/api/chat", needKey, wrap(async (req, res) => {
  const messages = (req.body.messages || [])
    .filter((m) => ["user", "assistant"].includes(m.role) && typeof m.content === "string")
    .slice(-20);
  if (!messages.length || messages.at(-1).role !== "user")
    return res.status(400).json({ error: "messages must end with a user message" });

  const system = SYSTEM_PROMPT + (req.body.context ? `\n\nCONTEXT ABOUT THE USER'S BUILDING (from image analysis):\n${String(req.body.context).slice(0, 4000)}` : "");
  if (!req.body.stream) {
    return res.json({ reply: await complete({ system: system, messages }) });
  }
  res.set({ "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" });
  await stream({
    system,
    messages,
    onText: (t) => res.write(`data: ${JSON.stringify({ text: t })}\n\n`),
  });
  res.write("data: [DONE]\n\n");
  res.end();
}));

// ---------- Image analysis (vision) ----------
// multipart: image=<file>, lang=ar|en
const CONTEMPORARY_DIGEST = "central double-recessed arched timber entrance with flanking elements; symmetrical facade with aligned vertical bays; deep recessed arched window openings with slender frames and abstracted timber screens or operable timber shutters; horizontal cornice bands and shadow gaps giving a clear base, middle and top; flat roofline with simple sharp parapet (circular or elliptical openings in rectangular recesses allowed) and optional pergola; white or off-white render with natural stone/timber, accents below 20% of the facade, geometric or abstracted floral patterns only on doors, screens and shutters; no reflective or mirrored glass, no large glass walls, no exposed rolling shutters, air-conditioning units or water tanks";
const KEYS = ["composition", "colors", "materials", "openings", "shading"];
app.post("/api/analyze-image", needKey, upload.single("image"), wrap(async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "image file required (jpeg/png/webp/gif, max 5MB)" });
  const dataUrl = `data:${req.file.mimetype};base64,${req.file.buffer.toString("base64")}`;
  const raw = await complete({
    system: SYSTEM_PROMPT,
    maxTokens: 2200,
    json: true,
    messages: [{
      role: "user",
      content: [
        { type: "image_url", image_url: { url: dataUrl } },
        { type: "text", text:
`Analyze this building facade against the official Taif Highlands guidelines in the reference (Architectural Design Guidelines + Residential Villas / Low-rise Buildings handbooks), applying the CONTEMPORARY style.
Scoring rubric (each 0-100): composition = central entrance, symmetry, vertical bays, base-middle-top articulation, flat roofline/parapet; colors = white/off-white or natural tones, accents under 20% of facade, no saturated/reflective finishes; materials = local stone/render/stucco/timber, no fake or reflective materials, no large glass walls; openings = arched or deep-recessed, upright 1:2-1:3 proportion, evenly spaced, timber/slender frames; shading = operable shutters, cornices and shadow gaps, pergolas/screens, housed shutters.
Cite specific guideline rules (by their content) in "rationale". Be specific to THIS building and judge only what is visible.
Write all Arabic fields in Arabic. Respond with ONLY valid JSON:
{
 "buildingType": "villa | lowrise | other",
 "summary": "2-3 Arabic sentences describing the facade and how close it is to Taif character",
 "scores": {"composition":0-100,"colors":0-100,"materials":0-100,"openings":0-100,"shading":0-100},
 "detected": {"windows":bool,"entrance":bool,"materials":bool,"colors":bool,"shading":bool},
 "strengths": ["short Arabic strength", "..."],
 "recommendations": {"openings":"Arabic, 1-2 sentences specific to this facade","materials":"...","entrance":"...","shading":"...","palette":"..."},
 "rationale": {"openings":"Arabic: WHY this recommendation fits Taif architecture","materials":"...","entrance":"...","shading":"...","palette":"..."},
 "changes": ["subset of: المدخل, النوافذ, المواد, التظليل, الألوان — the parts the redesign changes"],
 "redesign": "English instructions for an image editor: what to change on this exact facade (openings, entrance, materials, shading, palette) while keeping its massing and floors"
}
If the image is not a building, set all scores to 0 and explain in summary.` },
      ],
    }],
  });
  let a;
  try { a = JSON.parse(raw); } catch { return res.status(502).json({ error: "model returned invalid JSON", raw }); }
  const scores = Object.fromEntries(KEYS.map((k) => [k, Math.max(0, Math.min(100, Math.round(Number(a.scores?.[k]) || 0)))]));
  a.scores = scores;
  a.matchScore = Math.round(KEYS.reduce((t, k) => t + scores[k], 0) / KEYS.length);
  res.json(a);
}));

// ---------- Redesigned concept: edits the user's own photo ----------
// multipart: image=<file>, analysis=<JSON string from /api/analyze-image>
app.post("/api/generate-image", needKey, upload.single("image"), wrap(async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "image file required" });
  let a = {};
  try { a = JSON.parse(req.body.analysis || "{}"); } catch {}
  const prompt =
`Edit this photo of a building facade into a contemporary design that follows Taif highlands architecture.
KEEP exactly: the same building, camera angle, massing, number of floors, surroundings, sky and lighting.
CHANGE only the facade treatment, following the official Taif Highlands CONTEMPORARY style: ${CONTEMPORARY_DIGEST}.
Specific changes for this building: ${a.redesign || "apply the rules above to the existing openings, entrance, materials, shading and palette"}.
Taif reference: ${styleSummary()}
Photorealistic result. No text, logos or watermarks.`;
  res.json({ prompt, ...(await editImage(req.file.buffer, req.file.mimetype, prompt)) });
}));

app.use((_req, res) => res.status(404).json({ error: "not found" }));
app.listen(PORT, () => console.log(`Taif backend on :${PORT}`));
