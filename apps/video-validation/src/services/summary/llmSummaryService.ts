import OpenAI from "openai";

import { env } from "../../config/env.js";
import { VideoPresentationValidationResult } from "../types.js";

export async function buildOptionalSummary(result: VideoPresentationValidationResult): Promise<string | null> {
  if (!env.OPENAI_API_KEY) return null;
  const client = new OpenAI({ apiKey: env.OPENAI_API_KEY });

  const compact = {
    metadata: result.metadata,
    frameAnalysis: result.frameAnalysis,
    audioAnalysis: result.audioAnalysis,
    derivedChecks: result.derivedChecks,
    warnings: result.warnings
  };

  const response = await client.responses.create({
    model: "gpt-4.1-mini",
    input: [
      {
        role: "system",
        content:
          "You summarize algorithmic video-validation findings. Do not invent facts. Keep under 80 words."
      },
      {
        role: "user",
        content: `Create brief summary for committee review:\n${JSON.stringify(compact)}`
      }
    ]
  });

  return response.output_text?.trim() || null;
}
