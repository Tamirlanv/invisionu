import { describe, expect, it } from "vitest";
import { mapApiCard, rangeFromQuery } from "./query";

describe("commission query", () => {
  it("maps snake_case api card", () => {
    const out = mapApiCard({
      application_id: "abc",
      candidate_full_name: "User Name",
      stage_column: "data_check",
      stage_status: "approved",
      submitted_at_iso: "2026-01-01T00:00:00Z",
      updated_at_iso: "2026-01-01T01:00:00Z",
      attention_flag_manual: false,
    });
    expect(out.applicationId).toBe("abc");
    expect(out.visualState).toBe("positive");
  });

  it("normalizes unsupported range to week", () => {
    expect(rangeFromQuery("bad")).toBe("week");
  });
});

