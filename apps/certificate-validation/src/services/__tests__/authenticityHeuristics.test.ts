import { describe, expect, it } from "vitest";

import { evaluateAuthenticity } from "../rules/authenticityHeuristics.js";

describe("evaluateAuthenticity", () => {
  it("returns likely_authentic for strong signals", () => {
    const out = evaluateAuthenticity({
      templateScore: 0.9,
      ocrConfidence: 0.9,
      hasScore: true,
      missingAnchors: []
    });
    expect(out.status).toBe("likely_authentic");
  });

  it("returns manual_review_required for weak template + missing anchors", () => {
    const out = evaluateAuthenticity({
      templateScore: 0.2,
      ocrConfidence: 0.6,
      hasScore: false,
      missingAnchors: ["ielts", "overall band"]
    });
    expect(out.status).toBe("manual_review_required");
  });
});
