import "dotenv/config";
import express from "express";
import cors from "cors";
import multer from "multer";
import rateLimit from "express-rate-limit";
import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
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

// ---------- Cache: the same photo is never analysed or generated twice ----------
const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const CACHE = path.join(ROOT, "cache");
fs.mkdirSync(CACHE, { recursive: true });
const hashOf = (buf) => crypto.createHash("sha256").update(buf).digest("hex").slice(0, 40);
const readCache = (name) => { try { return fs.readFileSync(path.join(CACHE, name)); } catch { return null; } };
const writeCache = (name, data) => { try { fs.writeFileSync(path.join(CACHE, name), data); } catch {} };

// ---------- Gallery: sample photos dropped in public/gallery ----------
app.get("/api/gallery", (_req, res) => {
  const dir = path.join(ROOT, "public", "gallery");
  let files = [];
  try { files = fs.readdirSync(dir).filter((f) => /\.(jpe?g|png|webp)$/i.test(f)).sort(); } catch {}
  res.json(files.map((f) => ({ name: f, label: f.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " "), url: `/gallery/${encodeURIComponent(f)}` })));
});

// ---------- Image analysis (vision) ----------
// multipart: image=<file>
const KEYS = ["composition", "colors", "materials", "openings", "shading"];
const RECS = ["openings", "materials", "entrance", "shading", "palette"];
const CONTEMPORARY_DIGEST = "central arched entrance set in a recessed surround; symmetrical facade with aligned vertical bays; upright arched or deep-recessed window openings with slender frames and abstracted timber screens or shutters; horizontal cornice bands and shadow gaps giving a clear base, middle and top; flat roofline with a simple parapet; white or off-white render with restrained timber accents (accent colours under 20% of the facade); no reflective or mirrored glass, no large glass walls";

app.post("/api/analyze-image", needKey, upload.single("image"), wrap(async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "image file required (jpeg/png/webp/gif, max 5MB)" });
  const key = hashOf(req.file.buffer);
  const cached = readCache(`${key}.analysis.json`);
  if (cached) return res.json({ ...JSON.parse(cached), cached: true });

  const dataUrl = `data:${req.file.mimetype};base64,${req.file.buffer.toString("base64")}`;
  const raw = await complete({
    system: SYSTEM_PROMPT,
    maxTokens: 3200,
    json: true,
    messages: [{
      role: "user",
      content: [
        { type: "image_url", image_url: { url: dataUrl, detail: "high" } },
        { type: "text", text:
`You are reviewing ONE real building photo against the official Taif Highlands guidelines in the reference, using the CONTEMPORARY style. The reader is an ordinary homeowner who knows nothing about architecture or AI: write simple, concrete Arabic, never generic praise like "good symmetry" without pointing at what you see.

STEP 1 - inventory what is really visible (be careful, do not guess): floors, windows (shape, position), main entrance, VEHICLE GATE / garage opening (a gate for cars is a gate, NOT a wall), PEDESTRIAN gate, boundary wall, roof/parapet, materials, colours, shading devices.
GUARD ROOM (غرفة الحارس): look carefully at the ground level beside the gates and along the boundary wall for a small enclosed room or booth with its own small door and/or small window or hatch. That is a GUARD ROOM, a real room used by the guard: it is NOT a window of the house, NOT a niche and NOT a decoration. If present, list it in "gates" with type "guard room" and describe it precisely (side, size, its door/window), and never count its small opening as a window of the main facade in the scores or recommendations.
STEP 2 - score each area 0-100 with this rubric: composition = central entrance, symmetry, aligned vertical bays, base-middle-top articulation, flat roofline; colors = white/off-white or natural tones, accents under 20%, no saturated/reflective finishes; materials = render/stucco/stone/timber, no fake or reflective materials, no big glass walls; openings = arched or recessed, upright proportion between 1:2 and 1:3, evenly spaced; shading = operable shutters, cornices and shadow gaps, pergolas/screens.
STEP 3 - recommendations must be SPECIFIC TO THIS PHOTO and different from any other building: say exactly WHERE on this facade (floor, side, which element), exactly WHAT to change, and the REAL reason (visual character AND practical benefit such as sun, privacy, depth, rain, maintenance, or the specific guideline rule). Never use "to comply with the standards" as the reason. Granite and timber are only traditional references: do not demand them; keep what the building already has when it is acceptable.
STEP 4 - "preserve" lists, in English, every gate, door, garage opening, guard room, boundary wall and other fixed element that the image editor must keep exactly as is and in the same place.

Respond with ONLY valid JSON (Arabic text unless marked English):
{
 "buildingType": "villa | lowrise | other",
 "summary": "3 short plain sentences: what the facade looks like; one concrete thing already close to Taif character (point at it); the main gap and why it matters",
 "verdict": "one sentence, plain",
 "scores": {"composition":0,"colors":0,"materials":0,"openings":0,"shading":0},
 "scoreNotes": {"composition":"max 12 words citing what you see","colors":"...","materials":"...","openings":"...","shading":"..."},
 "detected": {"windows":true,"entrance":true,"materials":true,"colors":true,"shading":true},
 "gates": [{"type":"vehicle gate | pedestrian gate | guard room | boundary wall | garage door","where":"short location"}],
 "strengths": ["short concrete strengths"],
 "recommendations": [
   {"id":"openings","element":"معالجة الفتحات","where":"exact place on this facade","change":"exact change","why":"real specific reason","gain":0-15}
   ... exactly five items with ids: openings, materials, entrance, shading, palette (titles: معالجة الفتحات, المواد والخامات, المدخل, التظليل, لوحة الألوان)
 ],
 "changes": ["subset of: المدخل, النوافذ, المواد, التظليل, الألوان"],
 "preserve": ["English list of fixed elements to keep"],
 "redesign": "English: precise, restrained edits for this exact facade (what to change where), keeping everything in preserve unchanged"
}
If the image is not a building, set all scores to 0 and say so in summary.` },
      ],
    }],
  });
  let a;
  try { a = JSON.parse(raw); } catch { return res.status(502).json({ error: "model returned invalid JSON", raw }); }
  a.scores = Object.fromEntries(KEYS.map((k) => [k, Math.max(0, Math.min(100, Math.round(Number(a.scores?.[k]) || 0)))]));
  a.matchScore = Math.round(KEYS.reduce((t, k) => t + a.scores[k], 0) / KEYS.length);
  const byId = Object.fromEntries((Array.isArray(a.recommendations) ? a.recommendations : []).map((r) => [r.id, r]));
  a.recommendations = RECS.map((id) => ({ id, element: "", where: "", change: "", why: "", gain: 0, ...(byId[id] || {}) }));
  writeCache(`${key}.analysis.json`, JSON.stringify(a));
  res.json(a);
}));

// ---------- Redesigned concept: edits the user's own photo ----------
// multipart: image=<file>, analysis=<JSON string from /api/analyze-image>
app.post("/api/generate-image", needKey, upload.single("image"), wrap(async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "image file required" });
  const key = hashOf(req.file.buffer);
  const cached = readCache(`${key}.after.png`);
  if (cached) return res.json({ mime: "image/png", b64: cached.toString("base64"), cached: true });

  let a = {};
  try { a = JSON.parse(req.body.analysis || "{}"); } catch {}
  const preserve = Array.isArray(a.preserve) && a.preserve.length ? a.preserve.join("; ") : "all gates, doors, garage openings, guard rooms and boundary walls";
  const prompt =
`Edit this photo of a real residential building into a refined contemporary version that follows the Taif Highlands contemporary style.
This must still look like THE SAME house on the same street: keep the camera angle, framing, massing, number of floors, roof shape, surroundings, sky, lighting and overall colour tone.
KEEP EXACTLY AS THEY ARE (same position, same function, do not turn them into windows or walls): ${preserve}. A vehicle gate stays a vehicle gate, a pedestrian gate stays a gate, and the guard room (غرفة الحارس, a small room beside the gate with its own door and/or small window) stays exactly a guard room of the same size and position: never turn it into a window, niche or wall, and do not restyle it as part of the main facade.
Make only restrained, believable changes: ${a.redesign || CONTEMPORARY_DIGEST}.
Style target: ${CONTEMPORARY_DIGEST}.
Do NOT make it look like a palace or mansion: no columns, domes, heavy ornament or stone cladding unless already present. Materials and colours stay close to what the house already has, using off-white render with modest timber accents.
Photorealistic. No text, logos or watermarks.`;
  const out = await editImage(req.file.buffer, req.file.mimetype, prompt);
  if (out.b64) writeCache(`${key}.after.png`, Buffer.from(out.b64, "base64"));
  res.json({ prompt, ...out });
}));

app.use((_req, res) => res.status(404).json({ error: "not found" }));
app.listen(PORT, () => console.log(`Taif backend on :${PORT}`));
