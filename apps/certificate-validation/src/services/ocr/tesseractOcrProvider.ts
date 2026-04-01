import { env } from "../../config/env.js";
import { runProcess } from "../../utils/process.js";
import { OcrResult } from "../types.js";
import { OcrProvider } from "./ocrProvider.js";

export class TesseractOcrProvider implements OcrProvider {
  async extractText(imagePath: string): Promise<OcrResult> {
    const { stdout } = await runProcess("tesseract", [imagePath, "stdout", "-l", env.OCR_LANG]);
    const text = stdout.trim();
    return {
      text,
      confidence: text ? 0.7 : null
    };
  }
}
