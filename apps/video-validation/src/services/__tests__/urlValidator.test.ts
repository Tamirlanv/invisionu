import { describe, expect, it } from "vitest";

import { validateVideoUrl } from "../access/urlValidator.js";

describe("validateVideoUrl", () => {
  it("accepts and normalizes hostname without scheme", () => {
    const out = validateVideoUrl("example.com/video.mp4");
    expect(out.isValid).toBe(true);
    expect(out.normalizedUrl).toContain("https://example.com/video.mp4");
  });

  it("rejects javascript scheme", () => {
    const out = validateVideoUrl("javascript://alert(1)");
    expect(out.isValid).toBe(false);
  });
});
