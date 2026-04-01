export type CheckType = "links" | "videoPresentation" | "certificates";
export type CheckStatus = "pending" | "processing" | "passed" | "failed" | "manual_review_required" | "skipped";
export type OverallStatus = "passed" | "failed" | "manual_review_required" | "partially_processed" | "processing";

export type ValidationCheckSummary = {
  status: CheckStatus;
  result: Record<string, unknown> | null;
  updatedAt: string;
};

export type CandidateValidationReport = {
  candidateId: string;
  applicationId: string;
  overallStatus: OverallStatus;
  checks: {
    links: ValidationCheckSummary | null;
    videoPresentation: ValidationCheckSummary | null;
    certificates: ValidationCheckSummary | null;
  };
  warnings: string[];
  errors: string[];
  explainability: string[];
  updatedAt: string;
};

export type SubmitValidationRunBody = {
  candidateId: string;
  applicationId: string;
  checks: {
    links?: { url: string } | null;
    videoPresentation?: { videoUrl: string } | null;
    certificates?: { imagePath: string } | null;
  };
};
