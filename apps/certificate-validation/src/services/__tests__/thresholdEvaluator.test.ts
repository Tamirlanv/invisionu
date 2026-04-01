import { describe, expect, it } from "vitest";

import { evaluateThresholds } from "../rules/thresholdEvaluator.js";

describe("evaluateThresholds", () => {
  it("checks IELTS >= 6.0", () => {
    expect(evaluateThresholds("ielts", 6.5).ieltsMinPassed).toBe(true);
    expect(evaluateThresholds("ielts", 5.5).ieltsMinPassed).toBe(false);
  });

  it("flags ENT score detected", () => {
    expect(evaluateThresholds("ent_nish", 110).entScoreDetected).toBe(true);
    expect(evaluateThresholds("ent_nish", null).entScoreDetected).toBe(false);
  });
});
