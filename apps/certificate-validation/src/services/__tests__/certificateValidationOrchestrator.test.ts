import { describe, expect, it, vi } from "vitest";

import * as repo from "../../repositories/certificateValidationRepository.js";
import { validateCertificateImage } from "../certificateValidationOrchestrator.js";

vi.mock("../image/preprocessImage.js", () => ({
  preprocessImage: vi.fn().mockResolvedValue("/tmp/preprocessed.png")
}));
vi.mock("../ocr/tesseractOcrProvider.js", () => ({
  TesseractOcrProvider: class {
    extractText() {
      return Promise.resolve({
        text: "IELTS Test Report Form Overall Band Score 6.5",
        confidence: 0.82
      });
    }
  }
}));

describe("validateCertificateImage", () => {
  it("returns processed ielts result", async () => {
    vi.spyOn(repo, "saveCertificateValidationResult").mockResolvedValueOnce();
    const out = await validateCertificateImage({ imagePath: "/tmp/cert.png" });
    expect(out.documentType).toBe("ielts");
    expect(out.processingStatus).toBe("processed");
    expect(out.thresholdChecks.ieltsMinPassed).toBe(true);
  });
});
