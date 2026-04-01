import { describe, expect, it } from "vitest";
import { getApplicationCardVisualState } from "./visual-state";

describe("commission visual-state", () => {
  it("prioritizes attention", () => {
    expect(
      getApplicationCardVisualState({
        currentStageStatus: "approved",
        finalDecision: "enrolled",
        manualAttentionFlag: true,
      }),
    ).toBe("attention");
  });

  it("uses final decision if present", () => {
    expect(
      getApplicationCardVisualState({
        currentStageStatus: "rejected",
        finalDecision: "move_forward",
        manualAttentionFlag: false,
      }),
    ).toBe("positive");
  });
});

