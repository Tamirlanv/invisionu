import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api-client", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "../api-client";
import { createCommissionComment, getCommissionApplicationPersonalInfo, mapApiCard, rangeFromQuery } from "./query";

const apiFetchMock = vi.mocked(apiFetch);

describe("commission query", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
  });

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

  it("requests personal-info view endpoint", async () => {
    apiFetchMock.mockResolvedValue({ applicationId: "abc" } as never);
    await getCommissionApplicationPersonalInfo("abc");
    expect(apiFetchMock).toHaveBeenCalledWith("/commission/applications/abc/personal-info");
  });

  it("posts internal commission comment", async () => {
    apiFetchMock.mockResolvedValue(undefined as never);
    await createCommissionComment("abc", "note");
    expect(apiFetchMock).toHaveBeenCalledWith("/commission/applications/abc/comments", {
      method: "POST",
      json: { body: "note" },
    });
  });
});

