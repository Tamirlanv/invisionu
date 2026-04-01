import { Pool } from "pg";
import { randomUUID } from "node:crypto";

import { CertificateValidationResult } from "../services/types.js";

export async function saveCertificateValidationResult(
  pool: Pool,
  payload: { applicationId?: string | null; result: CertificateValidationResult }
): Promise<void> {
  const r = payload.result;
  await pool.query(
    `
      INSERT INTO certificate_validation_results (
        id, application_id, document_type, processing_status, extracted_fields,
        threshold_checks, authenticity_status, template_match_score, ocr_confidence,
        fraud_signals, warnings, errors, explainability, confidence, summary_text
      ) VALUES (
        $1,$2,$3,$4,$5::jsonb,
        $6::jsonb,$7,$8,$9,
        $10::jsonb,$11::jsonb,$12::jsonb,$13::jsonb,$14,$15
      )
    `,
    [
      randomUUID(),
      payload.applicationId ?? null,
      r.documentType,
      r.processingStatus,
      JSON.stringify(r.extractedFields),
      JSON.stringify(r.thresholdChecks),
      r.authenticity.status,
      r.authenticity.templateMatchScore,
      r.authenticity.ocrConfidence,
      JSON.stringify(r.authenticity.fraudSignals),
      JSON.stringify(r.warnings),
      JSON.stringify(r.errors),
      JSON.stringify(r.explainability),
      r.confidence,
      r.summaryText ?? null
    ]
  );
}
