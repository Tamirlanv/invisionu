import { describe, expect, it } from "vitest";
import { sortColumnApplications } from "./sort";
import type { CommissionBoardApplicationCard } from "./types";

function card(overrides: Partial<CommissionBoardApplicationCard>): CommissionBoardApplicationCard {
  return {
    applicationId: "1",
    candidateId: "1",
    candidateFullName: "A",
    program: "X",
    city: null,
    phone: null,
    age: null,
    submittedAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-01T00:00:00.000Z",
    currentStage: "data_check",
    currentStageStatus: "new",
    finalDecision: null,
    manualAttentionFlag: false,
    commentCount: 0,
    aiRecommendation: null,
    aiConfidence: null,
    visualState: "neutral",
    ...overrides,
  };
}

describe("commission sort", () => {
  it("puts needs_attention first", () => {
    const rows = sortColumnApplications([
      card({ applicationId: "2", currentStageStatus: "new" }),
      card({ applicationId: "1", currentStageStatus: "needs_attention" }),
    ]);
    expect(rows[0].applicationId).toBe("1");
  });
});

