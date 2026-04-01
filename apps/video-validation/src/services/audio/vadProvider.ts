import { VadResult } from "../types.js";

export interface VadProvider {
  analyzeSpeech(wavPath: string): Promise<VadResult>;
}
