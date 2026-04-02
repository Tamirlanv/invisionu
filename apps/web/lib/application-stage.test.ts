import { describe, expect, it } from "vitest";

import { CANDIDATE_STAGE_PIPELINE, getCandidateStageIndex } from "./application-stage";

describe("candidate stage mapping", () => {
  it("maps initial_screening to second step", () => {
    expect(getCandidateStageIndex("initial_screening")).toBe(1);
    expect(CANDIDATE_STAGE_PIPELINE[1]?.label).toBe("Проверка данных");
  });

  it("falls back to first step for unknown stages", () => {
    expect(getCandidateStageIndex("unknown_stage")).toBe(0);
  });
});
