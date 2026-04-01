import { describe, expect, it, vi } from "vitest";

import * as repo from "../../repositories/validationOrchestratorRepository.js";
import * as producer from "../../queue/producer.js";
import { submitValidationRun } from "../orchestratorService.js";

describe("submitValidationRun", () => {
  it("creates run and enqueues selected checks", async () => {
    vi.spyOn(repo, "createRun").mockResolvedValueOnce({ runId: "run-1" });
    vi.spyOn(repo, "addAuditEvent").mockResolvedValueOnce();
    const enqueueSpy = vi.spyOn(producer, "enqueueCheck").mockResolvedValue();

    const out = await submitValidationRun({
      candidateId: "00000000-0000-0000-0000-000000000001",
      applicationId: "00000000-0000-0000-0000-000000000002",
      checks: {
        links: { url: "https://example.com" },
        videoPresentation: null,
        certificates: { imagePath: "/tmp/cert.png" }
      }
    });

    expect(out.runId).toBe("run-1");
    expect(enqueueSpy).toHaveBeenCalledTimes(2);
  });
});
