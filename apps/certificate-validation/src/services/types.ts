export type DocumentType = "ielts" | "toefl" | "ent_nish" | "unknown";
export type ProcessingStatus = "processed" | "unsupported" | "ocr_failed" | "low_quality" | "processing_failed";
export type AuthenticityStatus = "likely_authentic" | "suspicious" | "manual_review_required" | "insufficient_quality";

export type CertificateValidationResult = {
  documentType: DocumentType;
  processingStatus: ProcessingStatus;
  extractedFields: {
    candidateName?: string | null;
    certificateNumber?: string | null;
    examDate?: string | null;
    totalScore?: number | null;
    sectionScores?: Record<string, number | null> | null;
    rawDetectedText?: string | null;
  };
  thresholdChecks: {
    ieltsMinPassed?: boolean | null;
    entScoreDetected?: boolean | null;
    toeflMinPassed?: boolean | null;
  };
  authenticity: {
    status: AuthenticityStatus;
    templateMatchScore: number | null;
    ocrConfidence: number | null;
    fraudSignals: string[];
  };
  warnings: string[];
  errors: string[];
  explainability: string[];
  confidence: number;
  summaryText?: string | null;
};

export type FileValidationResult = {
  isValid: boolean;
  warnings: string[];
  errors: string[];
};

export type OcrResult = {
  text: string;
  confidence: number | null;
  words?: Array<{ text: string; confidence: number | null }>;
};

export type TemplateMatchResult = {
  score: number;
  anchorsFound: string[];
  missingAnchors: string[];
};
