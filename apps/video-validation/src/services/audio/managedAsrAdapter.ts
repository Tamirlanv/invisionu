import { createReadStream } from "node:fs";

import OpenAI from "openai";

import { env } from "../../config/env.js";
import { AsrResult } from "../types.js";
import { AsrProvider } from "./asrProvider.js";

export class ManagedAsrAdapter implements AsrProvider {
  private readonly client: OpenAI | null;

  constructor() {
    this.client = env.OPENAI_API_KEY ? new OpenAI({ apiKey: env.OPENAI_API_KEY }) : null;
  }

  async transcribe(wavPath: string): Promise<AsrResult> {
    if (!this.client) {
      return { transcriptPreview: null, transcriptConfidence: null };
    }

    const res = await this.client.audio.transcriptions.create({
      model: "gpt-4o-mini-transcribe",
      file: createReadStream(wavPath)
    });
    const transcript = (res.text || "").trim();
    return {
      transcriptPreview: transcript ? transcript.slice(0, 300) : null,
      transcriptConfidence: transcript ? 0.75 : null
    };
  }
}
