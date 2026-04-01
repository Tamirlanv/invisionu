import { DocumentType, TemplateMatchResult } from "../types.js";

const REQUIRED_ANCHORS: Record<DocumentType, string[]> = {
  ielts: ["ielts", "test report form", "overall band"],
  toefl: ["toefl", "ets", "score"],
  ent_nish: ["ент", "ниш", "балл"],
  unknown: []
};

export function matchTemplate(text: string, type: DocumentType): TemplateMatchResult {
  const anchors = REQUIRED_ANCHORS[type] ?? [];
  if (!anchors.length) return { score: 0, anchorsFound: [], missingAnchors: [] };
  const lower = text.toLowerCase();
  const anchorsFound = anchors.filter((a) => lower.includes(a));
  const missingAnchors = anchors.filter((a) => !lower.includes(a));
  const score = Number((anchorsFound.length / anchors.length).toFixed(3));
  return { score, anchorsFound, missingAnchors };
}
