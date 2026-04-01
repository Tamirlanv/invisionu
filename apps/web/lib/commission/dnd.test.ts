import { describe, expect, it } from "vitest";
import { canMoveCards, isNextStageOnly } from "./dnd";

describe("commission dnd", () => {
  it("allows move only for reviewer/admin", () => {
    expect(canMoveCards("viewer")).toBe(false);
    expect(canMoveCards("reviewer")).toBe(true);
    expect(canMoveCards("admin")).toBe(true);
  });

  it("allows only next stage moves", () => {
    expect(isNextStageOnly("data_check", "application_review")).toBe(true);
    expect(isNextStageOnly("data_check", "interview")).toBe(false);
    expect(isNextStageOnly("result", "committee_decision")).toBe(false);
  });
});

