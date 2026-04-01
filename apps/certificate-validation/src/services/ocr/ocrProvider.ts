import { OcrResult } from "../types.js";

export interface OcrProvider {
  extractText(imagePath: string): Promise<OcrResult>;
}
