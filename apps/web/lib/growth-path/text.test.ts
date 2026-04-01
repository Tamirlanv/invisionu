import { describe, expect, it } from "vitest";
import { GROWTH_CHAR_LIMITS } from "./constants";
import { growthCharCount, normalizeGrowthText, trimToMaxForQuestion, validateGrowthAnswerLength } from "./text";

describe("growth-path/text", () => {
  it("normalizes whitespace like backend", () => {
    expect(normalizeGrowthText("  a \n b  ")).toBe("a b");
  });

  it("counts normalized length", () => {
    expect(growthCharCount("  hi  ")).toBe(2);
  });

  it("validates q1 boundaries", () => {
    const short = validateGrowthAnswerLength("q1", "x".repeat(100));
    expect(short.ok).toBe(false);
    const ok = validateGrowthAnswerLength("q1", "x".repeat(250));
    expect(ok.ok).toBe(true);
  });

  it("trimToMaxForQuestion caps length", () => {
    const max = GROWTH_CHAR_LIMITS.q5.max;
    const long = "w ".repeat(500);
    const trimmed = trimToMaxForQuestion("q5", long);
    expect(trimmed.length).toBeLessThanOrEqual(long.length);
    expect(validateGrowthAnswerLength("q5", trimmed).len).toBeLessThanOrEqual(max);
  });
});
