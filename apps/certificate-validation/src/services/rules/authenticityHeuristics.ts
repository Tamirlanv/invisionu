import { AuthenticityStatus } from "../types.js";

export function evaluateAuthenticity(input: {
  templateScore: number;
  ocrConfidence: number | null;
  hasScore: boolean;
  missingAnchors: string[];
}): {
  status: AuthenticityStatus;
  fraudSignals: string[];
} {
  const fraudSignals: string[] = [];
  if (input.templateScore < 0.4) fraudSignals.push("weak_template_match");
  if ((input.ocrConfidence ?? 0) < 0.45) fraudSignals.push("low_ocr_confidence");
  if (!input.hasScore) fraudSignals.push("score_not_detected");
  if (input.missingAnchors.length > 1) fraudSignals.push("missing_key_anchors");

  if ((input.ocrConfidence ?? 0) < 0.2) return { status: "insufficient_quality", fraudSignals };
  if (fraudSignals.length === 0) return { status: "likely_authentic", fraudSignals };
  if (fraudSignals.includes("weak_template_match") && fraudSignals.includes("missing_key_anchors")) {
    return { status: "manual_review_required", fraudSignals };
  }
  return { status: "suspicious", fraudSignals };
}
