import { describe, expect, it, vi } from "vitest";

import * as processUtil from "../../utils/process.js";
import { extractMetadata } from "../media/metadataExtractor.js";

describe("extractMetadata", () => {
  it("parses ffprobe json result", async () => {
    vi.spyOn(processUtil, "runProcess").mockResolvedValueOnce({
      stdout: JSON.stringify({
        format: { duration: "45.2" },
        streams: [
          { codec_type: "video", width: 1920, height: 1080, codec_name: "h264" },
          { codec_type: "audio", codec_name: "aac" }
        ]
      }),
      stderr: ""
    });

    const out = await extractMetadata("https://example.com/video.mp4");
    expect(out.durationSec).toBe(45.2);
    expect(out.hasAudioTrack).toBe(true);
    expect(out.hasVideoTrack).toBe(true);
  });
});
