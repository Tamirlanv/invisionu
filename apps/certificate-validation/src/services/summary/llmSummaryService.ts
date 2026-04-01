import OpenAI from "openai";

import { env } from "../../config/env.js";
import { CertificateValidationResult } from "../types.js";

export async function buildOptionalSummary(result: CertificateValidationResult): Promise<string | null> {
  if (!env.OPENAI_API_KEY) return null;
  const client = new OpenAI({ apiKey: env.OPENAI_API_KEY });
  const compact = {
    documentType: result.documentType,
    processingStatus: result.processingStatus,
    extractedFields: result.extractedFields,
    thresholdChecks: result.thresholdChecks,
    authenticity: result.authenticity,
    warnings: result.warnings
  };
  const response = await client.responses.create({
    model: "gpt-4.1-mini",
    input: [
      { role: "system", content: "Summarize certificate validation signals in under 80 words." },
      { role: "user", content: JSON.stringify(compact) }
    ]
  });
  return response.output_text?.trim() || null;
}
