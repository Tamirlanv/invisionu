import { probeMediaUrl } from "./access/mediaProbe.js";
import { validateVideoUrl } from "./access/urlValidator.js";
import { ManagedAsrAdapter } from "./audio/managedAsrAdapter.js";
import { EnergyVadAnalyzer } from "./audio/webrtcVadAnalyzer.js";
import { extractAudioWav } from "./media/audioExtractor.js";
import { sampleFrames } from "./media/frameSampler.js";
import { extractMetadata } from "./media/metadataExtractor.js";
import { saveVideoValidationResult } from "../repositories/videoValidationRepository.js";
import { pgPool } from "../db/pg.js";
import { deriveValidationResult } from "./rules/decisionEngine.js";
import { buildOptionalSummary } from "./summary/llmSummaryService.js";
import { AsrResult, FaceDetectionResult, VadResult, VideoPresentationValidationResult } from "./types.js";
import { OpenCvFaceDetector } from "./vision/opencvFaceDetector.js";

export async function validateVideoPresentation(input: {
  videoUrl: string;
  applicationId?: string | null;
  includeSummary?: boolean;
}): Promise<VideoPresentationValidationResult> {
  const warnings: string[] = [];
  const errors: string[] = [];

  const url = validateVideoUrl(input.videoUrl);
  if (!url.isValid || !url.normalizedUrl) {
    const invalidResult: VideoPresentationValidationResult = {
      videoUrl: input.videoUrl,
      accessStatus: "invalid",
      mediaStatus: "processing_failed",
      metadata: {
        durationSec: null,
        width: null,
        height: null,
        hasVideoTrack: false,
        hasAudioTrack: false,
        codecVideo: null,
        codecAudio: null
      },
      frameAnalysis: {
        totalFramesAnalyzed: 0,
        faceDetectedFramesCount: 0,
        faceCoverageRatio: 0,
        averageFaceConfidence: null,
        sampledTimestampsSec: []
      },
      audioAnalysis: {
        hasSpeech: false,
        speechSegmentCount: 0,
        speechCoverageRatio: null,
        transcriptPreview: null,
        transcriptConfidence: null
      },
      derivedChecks: {
        likelyFaceVisible: false,
        likelySpeechAudible: false,
        likelyPresentationValid: false,
        manualReviewRequired: true
      },
      explainability: ["URL failed deterministic validation"],
      warnings: [],
      errors: url.errors,
      confidence: 0
    };
    try {
      await saveVideoValidationResult(pgPool, {
        applicationId: input.applicationId,
        videoUrl: input.videoUrl,
        normalizedUrl: null,
        result: invalidResult
      });
    } catch {
      invalidResult.warnings.push("Could not persist validation result to database");
    }
    return invalidResult;
  }

  const probe = await probeMediaUrl(url.normalizedUrl);
  let accessStatus: VideoPresentationValidationResult["accessStatus"] = "reachable";
  if (!probe.statusCode) accessStatus = probe.error?.toLowerCase().includes("abort") ? "timeout" : "invalid";
  else if (probe.statusCode === 401) accessStatus = "private_access";
  else if (probe.statusCode === 403) accessStatus = "forbidden";
  else if (probe.statusCode === 404) accessStatus = "not_found";
  else if (probe.statusCode >= 400) accessStatus = "invalid";

  if (accessStatus !== "reachable") {
    errors.push(`Video access status is ${accessStatus}`);
  }

  let metadata;
  let sampledTimestampsSec: number[] = [];
  let faces: FaceDetectionResult[] = [];
  let vad: VadResult = { hasSpeech: false, speechSegmentCount: 0, speechCoverageRatio: 0 };
  let asr: AsrResult = { transcriptPreview: null, transcriptConfidence: null };

  try {
    metadata = await extractMetadata(url.normalizedUrl);
    const sampled = await sampleFrames(url.normalizedUrl, metadata.durationSec);
    sampledTimestampsSec = sampled.sampledTimestampsSec;
    faces = await new OpenCvFaceDetector().detectFaces(sampled.framePaths, sampled.sampledTimestampsSec);
    if (metadata.hasAudioTrack) {
      const wavPath = await extractAudioWav(url.normalizedUrl);
      vad = await new EnergyVadAnalyzer().analyzeSpeech(wavPath);
      asr = await new ManagedAsrAdapter().transcribe(wavPath);
    } else {
      warnings.push("Audio track is missing in media");
    }
  } catch (error) {
    errors.push(error instanceof Error ? error.message : "Processing pipeline failed");
    metadata = {
      durationSec: null,
      width: null,
      height: null,
      hasVideoTrack: false,
      hasAudioTrack: false,
      codecVideo: null,
      codecAudio: null
    };
  }

  const result = deriveValidationResult({
    videoUrl: input.videoUrl,
    accessStatus,
    metadata,
    faces,
    sampledTimestampsSec,
    vad,
    asr,
    warnings,
    errors
  });

  if (input.includeSummary) {
    result.summaryText = await buildOptionalSummary(result);
  }

  try {
    await saveVideoValidationResult(pgPool, {
      applicationId: input.applicationId,
      videoUrl: input.videoUrl,
      normalizedUrl: url.normalizedUrl,
      result
    });
  } catch {
    result.warnings.push("Could not persist validation result to database");
  }
  return result;
}
