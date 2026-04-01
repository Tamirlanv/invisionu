import { AsrResult } from "../types.js";

export interface AsrProvider {
  transcribe(wavPath: string): Promise<AsrResult>;
}
