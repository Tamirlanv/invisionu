import { describe, expect, it, vi } from "vitest";

import * as processUtil from "../../utils/process.js";
import { sampleFrames } from "../media/frameSampler.js";

describe("sampleFrames", () => {
  it("returns sampled timestamps and frame paths", async () => {
    vi.spyOn(processUtil, "runProcess").mockResolvedValueOnce({ stdout: "", stderr: "" });

    const out = await sampleFrames("https://example.com/video.mp4", 40);
    expect(out.sampledTimestampsSec.length).toBeGreaterThanOrEqual(5);
    expect(Array.isArray(out.framePaths)).toBe(true);
  });
});
