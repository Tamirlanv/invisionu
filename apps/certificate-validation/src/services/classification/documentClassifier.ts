import { DocumentType } from "../types.js";

export function classifyDocumentType(text: string): DocumentType {
  const t = text.toLowerCase();
  if (t.includes("ielts") && (t.includes("test report form") || t.includes("overall band"))) return "ielts";
  if (t.includes("toefl") || t.includes("ets")) return "toefl";
  if (t.includes("ент") || t.includes("ниш") || t.includes("nazarbayev intellectual schools")) return "ent_nish";
  return "unknown";
}
