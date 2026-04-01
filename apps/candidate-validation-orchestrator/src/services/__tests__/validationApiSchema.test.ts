import { describe, expect, it } from "vitest";
import { z } from "zod";

const Body = z.object({
  candidateId: z.string().uuid(),
  applicationId: z.string().uuid(),
  checks: z.object({
    links: z.object({ url: z.string().min(1) }).nullable().optional(),
    videoPresentation: z.object({ videoUrl: z.string().min(1) }).nullable().optional(),
    certificates: z.object({ imagePath: z.string().min(1) }).nullable().optional()
  })
});

describe("validation request schema", () => {
  it("accepts minimal valid payload", () => {
    const out = Body.parse({
      candidateId: "00000000-0000-0000-0000-000000000001",
      applicationId: "00000000-0000-0000-0000-000000000002",
      checks: { links: { url: "https://example.com" } }
    });
    expect(out.checks.links?.url).toContain("https://");
  });
});
