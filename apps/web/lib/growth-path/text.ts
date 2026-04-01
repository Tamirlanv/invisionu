import { GROWTH_CHAR_LIMITS, type GrowthQuestionId } from "./constants";

/** Align with backend `normalize_growth_text`. */
export function normalizeGrowthText(raw: string): string {
  return raw.replace(/\s+/g, " ").trim();
}

export function growthCharCount(raw: string): number {
  return normalizeGrowthText(raw).length;
}

export function trimToMaxForQuestion(id: GrowthQuestionId, raw: string): string {
  const max = GROWTH_CHAR_LIMITS[id].max;
  let s = raw;
  while (normalizeGrowthText(s).length > max && s.length > 0) {
    s = s.slice(0, -1);
  }
  return s;
}

export function validateGrowthAnswerLength(
  id: GrowthQuestionId,
  raw: string,
): { ok: boolean; min: number; max: number; len: number } {
  const { min, max } = GROWTH_CHAR_LIMITS[id];
  const len = normalizeGrowthText(raw).length;
  return { ok: len >= min && len <= max, min, max, len };
}
