import { env } from "../../config/env.js";
import { DocumentType } from "../types.js";

export function evaluateThresholds(documentType: DocumentType, score: number | null): {
  ieltsMinPassed?: boolean | null;
  entScoreDetected?: boolean | null;
  toeflMinPassed?: boolean | null;
} {
  if (documentType === "ielts") return { ieltsMinPassed: score === null ? null : score >= 6.0 };
  if (documentType === "toefl") return { toeflMinPassed: score === null ? null : score >= env.TOEFL_THRESHOLD };
  if (documentType === "ent_nish") return { entScoreDetected: score !== null };
  return {};
}
