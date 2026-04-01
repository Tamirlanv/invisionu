import { CandidateValidationReport } from "./types.js";

export function summarizeReport(report: CandidateValidationReport): CandidateValidationReport {
  const explainability = [...report.explainability];
  if (report.checks.links) explainability.push(`links:${report.checks.links.status}`);
  if (report.checks.videoPresentation) explainability.push(`video:${report.checks.videoPresentation.status}`);
  if (report.checks.certificates) explainability.push(`certificates:${report.checks.certificates.status}`);
  return { ...report, explainability };
}
