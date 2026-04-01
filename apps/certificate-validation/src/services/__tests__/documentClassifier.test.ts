import { describe, expect, it } from "vitest";

import { classifyDocumentType } from "../classification/documentClassifier.js";

describe("classifyDocumentType", () => {
  it("detects IELTS", () => {
    expect(classifyDocumentType("IELTS Test Report Form Overall Band Score 6.5")).toBe("ielts");
  });

  it("detects TOEFL", () => {
    expect(classifyDocumentType("ETS TOEFL iBT total score 98")).toBe("toefl");
  });
});
