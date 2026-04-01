import { AsrResult, FaceDetectionResult, VadResult, VideoMetadata, VideoPresentationValidationResult } from "../types.js";

export function deriveValidationResult(input: {
  videoUrl: string;
  accessStatus: VideoPresentationValidationResult["accessStatus"];
  metadata: VideoMetadata;
  faces: FaceDetectionResult[];
  sampledTimestampsSec: number[];
  vad: VadResult;
  asr: AsrResult;
  warnings: string[];
  errors: string[];
}): VideoPresentationValidationResult {
  const faceDetectedFramesCount = input.faces.filter((x) => x.detected).length;
  const totalFramesAnalyzed = input.faces.length;
  const faceCoverageRatio = totalFramesAnalyzed > 0 ? Number((faceDetectedFramesCount / totalFramesAnalyzed).toFixed(3)) : 0;
  const confidences = input.faces.map((x) => x.confidence).filter((x) => x > 0);
  const averageFaceConfidence = confidences.length
    ? Number((confidences.reduce((a, b) => a + b, 0) / confidences.length).toFixed(3))
    : null;

  const likelyFaceVisible = faceCoverageRatio >= 0.3;
  const likelySpeechAudible = input.vad.hasSpeech && (input.vad.speechCoverageRatio ?? 0) >= 0.08;
  const likelyPresentationValid =
    input.accessStatus === "reachable" &&
    input.metadata.hasVideoTrack &&
    input.metadata.hasAudioTrack &&
    likelyFaceVisible &&
    likelySpeechAudible;
  const manualReviewRequired = !likelyPresentationValid || input.errors.length > 0;

  const explainability = [
    `Face detected in ${faceDetectedFramesCount}/${totalFramesAnalyzed} sampled frames`,
    `Speech coverage ratio: ${input.vad.speechCoverageRatio ?? 0}`,
    `Audio track present: ${input.metadata.hasAudioTrack}`,
    `Video track present: ${input.metadata.hasVideoTrack}`
  ];

  const mediaStatus: VideoPresentationValidationResult["mediaStatus"] = !input.metadata.hasVideoTrack
    ? "video_missing"
    : !input.metadata.hasAudioTrack
      ? "audio_missing"
      : input.metadata.hasVideoTrack
        ? "valid_video"
        : "invalid_media";

  let confidence = 0.2;
  if (input.accessStatus === "reachable") confidence += 0.2;
  if (input.metadata.hasVideoTrack) confidence += 0.2;
  if (input.metadata.hasAudioTrack) confidence += 0.15;
  if (likelyFaceVisible) confidence += 0.15;
  if (likelySpeechAudible) confidence += 0.1;
  confidence -= Math.min(0.3, input.errors.length * 0.05);

  return {
    videoUrl: input.videoUrl,
    accessStatus: input.accessStatus,
    mediaStatus,
    metadata: input.metadata,
    frameAnalysis: {
      totalFramesAnalyzed,
      faceDetectedFramesCount,
      faceCoverageRatio,
      averageFaceConfidence,
      sampledTimestampsSec: input.sampledTimestampsSec
    },
    audioAnalysis: {
      hasSpeech: input.vad.hasSpeech,
      speechSegmentCount: input.vad.speechSegmentCount,
      speechCoverageRatio: input.vad.speechCoverageRatio,
      transcriptPreview: input.asr.transcriptPreview,
      transcriptConfidence: input.asr.transcriptConfidence
    },
    derivedChecks: {
      likelyFaceVisible,
      likelySpeechAudible,
      likelyPresentationValid,
      manualReviewRequired
    },
    explainability,
    warnings: input.warnings,
    errors: input.errors,
    confidence: Number(Math.max(0, Math.min(1, confidence)).toFixed(3))
  };
}
