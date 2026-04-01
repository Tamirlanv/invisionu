import { Pool } from "pg";
import { randomUUID } from "node:crypto";

import { VideoPresentationValidationResult } from "../services/types.js";

export async function saveVideoValidationResult(
  pool: Pool,
  payload: {
    applicationId?: string | null;
    videoUrl: string;
    normalizedUrl?: string | null;
    result: VideoPresentationValidationResult;
  }
): Promise<void> {
  const r = payload.result;
  await pool.query(
    `
      INSERT INTO video_validation_results (
        id, application_id, video_url, normalized_url, access_status, media_status,
        duration_sec, width, height, has_video_track, has_audio_track,
        codec_video, codec_audio, total_frames_analyzed, face_detected_frames_count,
        face_coverage_ratio, average_face_confidence, sampled_timestamps_sec,
        has_speech, speech_segment_count, speech_coverage_ratio,
        transcript_preview, transcript_confidence,
        likely_face_visible, likely_speech_audible, likely_presentation_valid, manual_review_required,
        explainability, warnings, errors, confidence, summary_text
      ) VALUES (
        $1,$2,$3,$4,$5,$6,
        $7,$8,$9,$10,$11,
        $12,$13,$14,$15,
        $16,$17,$18,
        $19,$20,$21,
        $22,$23,
        $24,$25,$26,$27,
        $28::jsonb,$29::jsonb,$30::jsonb,$31,$32
      )
    `,
    [
      randomUUID(),
      payload.applicationId ?? null,
      payload.videoUrl,
      payload.normalizedUrl ?? null,
      r.accessStatus,
      r.mediaStatus,
      r.metadata.durationSec,
      r.metadata.width,
      r.metadata.height,
      r.metadata.hasVideoTrack,
      r.metadata.hasAudioTrack,
      r.metadata.codecVideo,
      r.metadata.codecAudio,
      r.frameAnalysis.totalFramesAnalyzed,
      r.frameAnalysis.faceDetectedFramesCount,
      r.frameAnalysis.faceCoverageRatio,
      r.frameAnalysis.averageFaceConfidence,
      r.frameAnalysis.sampledTimestampsSec,
      r.audioAnalysis.hasSpeech,
      r.audioAnalysis.speechSegmentCount,
      r.audioAnalysis.speechCoverageRatio,
      r.audioAnalysis.transcriptPreview,
      r.audioAnalysis.transcriptConfidence,
      r.derivedChecks.likelyFaceVisible,
      r.derivedChecks.likelySpeechAudible,
      r.derivedChecks.likelyPresentationValid,
      r.derivedChecks.manualReviewRequired,
      JSON.stringify(r.explainability),
      JSON.stringify(r.warnings),
      JSON.stringify(r.errors),
      r.confidence,
      r.summaryText ?? null
    ]
  );
}
