import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.dirname(fileURLToPath(import.meta.url));
export const style = JSON.parse(
  fs.readFileSync(path.join(dir, "../data/taif-style.json"), "utf8")
);

// Optional extra text (e.g. extracted from the official PDFs) dropped in data/extra/*.txt
const extraDir = path.join(dir, "../data/extra");
export function loadExtra() {
  if (!fs.existsSync(extraDir)) return "";
  return fs
    .readdirSync(extraDir)
    .filter((f) => f.endsWith(".txt"))
    .map((f) => fs.readFileSync(path.join(extraDir, f), "utf8"))
    .join("\n\n")
    .slice(0, 60000);
}

export function styleSummary() {
  const lines = style.elements.map(
    (e) => `- ${e.en} (${e.ar}): ${e.details_en} | ${e.details_ar}`
  );
  return `${style.overview.en}\n\nKey elements of Taif highlands architecture:\n${lines.join("\n")}`;
}

export const SYSTEM_PROMPT = `You are Mirwa (مِرْوَة), the assistant of "Mirat Emarat Al-Taif" (Taif Architecture Mirror), an interactive site that analyses a user's building photo against Taif highlands architecture and proposes a redesigned concept.
Your main job is to explain WHY each part of the analysis, recommendation and proposed concept was made the way it was, using the user's own analysis (given as context when available) and the reference below. Be concrete about their building, short, warm, and never invent facts about the photo that are not in the analysis.
Answer in the language the user writes in (Arabic by default). Ground every claim in the reference below; if something is not covered, say so instead of inventing details, and point to the official Saudi Architectural Character documents (architsaudi.dasc.gov.sa).

REFERENCE
${styleSummary()}

${loadExtra()}`;
