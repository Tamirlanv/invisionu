import { describe, expect, it } from "vitest";
import { growthPathPageSchema } from "../validation";

describe("growthPathPageSchema", () => {
  it("accepts valid answers and consents", () => {
    const parsed = growthPathPageSchema.parse({
      answers: {
        q1: { text: "x".repeat(250) },
        q2: { text: "y".repeat(200) },
        q3: { text: "z".repeat(200) },
        q4: { text: "a".repeat(200) },
        q5: { text: "b".repeat(150) },
      },
      consent_privacy: true,
      consent_parent: true,
    });
    expect(parsed.answers.q1.text).toHaveLength(250);
  });

  it("rejects short q1", () => {
    expect(() =>
      growthPathPageSchema.parse({
        answers: {
          q1: { text: "x".repeat(100) },
          q2: { text: "y".repeat(200) },
          q3: { text: "z".repeat(200) },
          q4: { text: "a".repeat(200) },
          q5: { text: "b".repeat(150) },
        },
        consent_privacy: true,
        consent_parent: true,
      }),
    ).toThrow();
  });
});
