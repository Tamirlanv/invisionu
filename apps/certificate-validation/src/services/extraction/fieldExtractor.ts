import { DocumentType } from "../types.js";
import { parseEntScore, parseIeltsOverall, parseToeflScore } from "./scoreParsers.js";

export function extractFields(text: string, documentType: DocumentType): {
  candidateName?: string | null;
  certificateNumber?: string | null;
  examDate?: string | null;
  totalScore?: number | null;
} {
  const certificateNumber = text.match(/\b(?:candidate\s*no|certificate\s*no|reg(?:istration)?\s*no)[:\s]*([A-Z0-9-]{5,})/i)?.[1] ?? null;
  const examDate = text.match(/\b(\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{2,4})\b/)?.[1] ?? null;
  let totalScore: number | null = null;
  if (documentType === "ielts") totalScore = parseIeltsOverall(text);
  if (documentType === "toefl") totalScore = parseToeflScore(text);
  if (documentType === "ent_nish") totalScore = parseEntScore(text);
  return { candidateName: null, certificateNumber, examDate, totalScore };
}
