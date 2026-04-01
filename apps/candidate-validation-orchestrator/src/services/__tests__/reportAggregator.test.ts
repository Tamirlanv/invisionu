import { describe, expect, it } from "vitest";

import { summarizeReport } from "../reportAggregator.js";

describe("summarizeReport", () => {
  it("appends check status explainability", () => {
    const out = summarizeReport({
      candidateId: "c",
      applicationId: "a",
      overallStatus: "processing",
      checks: {
        links: { status: "passed", result: null, updatedAt: "2026-01-01T00:00:00Z" },
        videoPresentation: null,
        certificates: { status: "manual_review_required", result: null, updatedAt: "2026-01-01T00:00:00Z" }
      },
      warnings: [],
      errors: [],
      explainability: [],
      updatedAt: "2026-01-01T00:00:00Z"
    });
    expect(out.explainability).toContain("links:passed");
    expect(out.explainability).toContain("certificates:manual_review_required");
  });
});
