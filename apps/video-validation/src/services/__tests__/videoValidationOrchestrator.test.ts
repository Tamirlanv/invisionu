import { describe, expect, it, vi } from "vitest";

import * as repo from "../../repositories/videoValidationRepository.js";
import { validateVideoPresentation } from "../videoValidationOrchestrator.js";

vi.mock("../media/metadataExtractor.js", () => ({
  extractMetadata: vi.fn().mockResolvedValue({
    durationSec: 30,
    width: 1280,
    height: 720,
    hasVideoTrack: true,
    hasAudioTrack: true,
    codecVideo: "h264",
    codecAudio: "aac"
  })
}));
vi.mock("../access/mediaProbe.js", () => ({
  probeMediaUrl: vi.fn().mockResolvedValue({
    finalUrl: "https://example.com/video.mp4",
    statusCode: 200,
    contentType: "video/mp4",
    contentLength: 1024,
    redirected: false,
    redirectCount: 0,
    responseTimeMs: 110,
    error: null
  })
}));
vi.mock("../media/frameSampler.js", () => ({
  sampleFrames: vi.fn().mockResolvedValue({
    framePaths: ["a.jpg", "b.jpg"],
    sampledTimestampsSec: [10, 20]
  })
}));
vi.mock("../vision/opencvFaceDetector.js", () => ({
  OpenCvFaceDetector: class {
    detectFaces() {
      return Promise.resolve([
        { timestampSec: 10, detected: true, confidence: 0.8 },
        { timestampSec: 20, detected: false, confidence: 0.0 }
      ]);
    }
  }
}));
vi.mock("../media/audioExtractor.js", () => ({
  extractAudioWav: vi.fn().mockResolvedValue("/tmp/audio.wav")
}));
vi.mock("../audio/webrtcVadAnalyzer.js", () => ({
  EnergyVadAnalyzer: class {
    analyzeSpeech() {
      return Promise.resolve({ hasSpeech: true, speechSegmentCount: 2, speechCoverageRatio: 0.3 });
    }
  }
}));
vi.mock("../audio/managedAsrAdapter.js", () => ({
  ManagedAsrAdapter: class {
    transcribe() {
      return Promise.resolve({ transcriptPreview: "hello", transcriptConfidence: 0.7 });
    }
  }
}));

describe("validateVideoPresentation", () => {
  it("returns deterministic validation result", async () => {
    vi.spyOn(repo, "saveVideoValidationResult").mockResolvedValueOnce();
    const out = await validateVideoPresentation({ videoUrl: "https://example.com/video.mp4" });
    expect(out.metadata.hasVideoTrack).toBe(true);
    expect(out.derivedChecks.likelyPresentationValid).toBe(true);
  });
});
