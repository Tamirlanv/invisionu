import { describe, expect, it } from "vitest";

import { deriveValidationResult } from "../rules/decisionEngine.js";

describe("deriveValidationResult", () => {
  it("marks likely presentation valid on strong signals", () => {
    const out = deriveValidationResult({
      videoUrl: "https://example.com/video.mp4",
      accessStatus: "reachable",
      metadata: {
        durationSec: 80,
        width: 1280,
        height: 720,
        hasVideoTrack: true,
        hasAudioTrack: true,
        codecVideo: "h264",
        codecAudio: "aac"
      },
      faces: [
        { timestampSec: 10, detected: true, confidence: 0.9 },
        { timestampSec: 20, detected: true, confidence: 0.8 },
        { timestampSec: 30, detected: false, confidence: 0.0 }
      ],
      sampledTimestampsSec: [10, 20, 30],
      vad: { hasSpeech: true, speechSegmentCount: 4, speechCoverageRatio: 0.4 },
      asr: { transcriptPreview: "hello world", transcriptConfidence: 0.8 },
      warnings: [],
      errors: []
    });
    expect(out.derivedChecks.likelyPresentationValid).toBe(true);
    expect(out.confidence).toBeGreaterThan(0.5);
  });
});
