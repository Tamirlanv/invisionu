import { pgPool } from "../db/pg.js";
import { saveCertificateValidationResult } from "../repositories/certificateValidationRepository.js";
import { classifyDocumentType } from "./classification/documentClassifier.js";
import { extractFields } from "./extraction/fieldExtractor.js";
import { preprocessImage } from "./image/preprocessImage.js";
import { TesseractOcrProvider } from "./ocr/tesseractOcrProvider.js";
import { evaluateAuthenticity } from "./rules/authenticityHeuristics.js";
import { evaluateThresholds } from "./rules/thresholdEvaluator.js";
import { buildOptionalSummary } from "./summary/llmSummaryService.js";
import { matchTemplate } from "./template/templateMatcher.js";
import { CertificateValidationResult } from "./types.js";

export async function validateCertificateImage(input: {
  imagePath: string;
  applicationId?: string | null;
  includeSummary?: boolean;
}): Promise<CertificateValidationResult> {
  const warnings: string[] = [];
  const errors: string[] = [];

  try {
    const preprocessed = await preprocessImage(input.imagePath);
    const ocr = await new TesseractOcrProvider().extractText(preprocessed);
    if (!ocr.text) {
      return {
        documentType: "unknown",
        processingStatus: "ocr_failed",
        extractedFields: { rawDetectedText: null },
        thresholdChecks: {},
        authenticity: {
          status: "insufficient_quality",
          templateMatchScore: null,
          ocrConfidence: ocr.confidence,
          fraudSignals: ["ocr_empty_output"]
        },
        warnings,
        errors: ["OCR failed to detect text"],
        explainability: ["Tesseract returned empty text"],
        confidence: 0.1
      };
    }

    const documentType = classifyDocumentType(ocr.text);
    const template = matchTemplate(ocr.text, documentType);
    const extracted = extractFields(ocr.text, documentType);
    const thresholds = evaluateThresholds(documentType, extracted.totalScore ?? null);
    const auth = evaluateAuthenticity({
      templateScore: template.score,
      ocrConfidence: ocr.confidence,
      hasScore: extracted.totalScore !== null && extracted.totalScore !== undefined,
      missingAnchors: template.missingAnchors
    });

    const explainability = [
      `Document type classified as ${documentType}`,
      `Template score: ${template.score}`,
      `Detected score: ${extracted.totalScore ?? "none"}`
    ];
    if (template.missingAnchors.length) warnings.push(`Missing anchors: ${template.missingAnchors.join(", ")}`);
    if (documentType === "unknown") warnings.push("Document type is unknown");

    const confidence = Number(
      Math.max(
        0,
        Math.min(
          1,
          0.25 + template.score * 0.35 + (ocr.confidence ?? 0) * 0.2 + (extracted.totalScore != null ? 0.1 : 0) - errors.length * 0.05
        )
      ).toFixed(3)
    );

    const result: CertificateValidationResult = {
      documentType,
      processingStatus: documentType === "unknown" ? "unsupported" : "processed",
      extractedFields: { ...extracted, rawDetectedText: ocr.text.slice(0, 3000) },
      thresholdChecks: thresholds,
      authenticity: {
        status: auth.status,
        templateMatchScore: template.score,
        ocrConfidence: ocr.confidence,
        fraudSignals: auth.fraudSignals
      },
      warnings,
      errors,
      explainability,
      confidence
    };

    if (input.includeSummary) result.summaryText = await buildOptionalSummary(result);
    await saveCertificateValidationResult(pgPool, { applicationId: input.applicationId, result });
    return result;
  } catch (error) {
    return {
      documentType: "unknown",
      processingStatus: "processing_failed",
      extractedFields: { rawDetectedText: null },
      thresholdChecks: {},
      authenticity: {
        status: "manual_review_required",
        templateMatchScore: null,
        ocrConfidence: null,
        fraudSignals: ["processing_exception"]
      },
      warnings,
      errors: [error instanceof Error ? error.message : "Unknown processing error"],
      explainability: ["Pipeline failed before final assembly"],
      confidence: 0
    };
  }
}
