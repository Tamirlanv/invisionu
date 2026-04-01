export type AccessStatus =
  | "reachable"
  | "private_access"
  | "forbidden"
  | "not_found"
  | "timeout"
  | "invalid";

export type MediaStatus =
  | "valid_video"
  | "invalid_media"
  | "video_missing"
  | "audio_missing"
  | "processing_failed";

export type VideoPresentationValidationResult = {
  videoUrl: string;
  accessStatus: AccessStatus;
  mediaStatus: MediaStatus;
  metadata: {
    durationSec: number | null;
    width: number | null;
    height: number | null;
    hasVideoTrack: boolean;
    hasAudioTrack: boolean;
    codecVideo: string | null;
    codecAudio: string | null;
  };
  frameAnalysis: {
    totalFramesAnalyzed: number;
    faceDetectedFramesCount: number;
    faceCoverageRatio: number;
    averageFaceConfidence: number | null;
    sampledTimestampsSec: number[];
  };
  audioAnalysis: {
    hasSpeech: boolean;
    speechSegmentCount: number;
    speechCoverageRatio: number | null;
    transcriptPreview: string | null;
    transcriptConfidence: number | null;
  };
  derivedChecks: {
    likelyFaceVisible: boolean;
    likelySpeechAudible: boolean;
    likelyPresentationValid: boolean;
    manualReviewRequired: boolean;
  };
  explainability: string[];
  warnings: string[];
  errors: string[];
  confidence: number;
  summaryText?: string | null;
};

export type UrlValidationResult = {
  isValid: boolean;
  normalizedUrl: string | null;
  errors: string[];
};

export type MediaProbeResult = {
  finalUrl: string | null;
  statusCode: number | null;
  contentType: string | null;
  contentLength: number | null;
  redirected: boolean;
  redirectCount: number;
  responseTimeMs: number | null;
  error: string | null;
};

export type VideoMetadata = {
  durationSec: number | null;
  width: number | null;
  height: number | null;
  hasVideoTrack: boolean;
  hasAudioTrack: boolean;
  codecVideo: string | null;
  codecAudio: string | null;
};

export type FaceDetectionResult = {
  timestampSec: number;
  detected: boolean;
  confidence: number;
};

export type VadResult = {
  hasSpeech: boolean;
  speechSegmentCount: number;
  speechCoverageRatio: number | null;
};

export type AsrResult = {
  transcriptPreview: string | null;
  transcriptConfidence: number | null;
};

