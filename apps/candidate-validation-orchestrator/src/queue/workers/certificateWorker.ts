import { Worker } from "bullmq";

import { env } from "../../config/env.js";
import { pgPool } from "../../db/pg.js";
import { recomputeOverallStatus, updateCheckStatus } from "../../repositories/validationOrchestratorRepository.js";
import { queueConnection } from "../queues.js";

export function startCertificateWorker(): Worker {
  return new Worker(
    "invision_orchestrator_certificate",
    async (job) => {
      const payload = job.data as { runId: string; applicationId: string; imagePath: string };
      await updateCheckStatus(pgPool, {
        runId: payload.runId,
        checkType: "certificates",
        status: "processing",
        incrementAttempts: true
      });
      try {
        const res = await fetch(env.CERTIFICATE_VALIDATION_URL, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            imagePath: payload.imagePath,
            applicationId: payload.applicationId
          })
        });
        const result = (await res.json()) as Record<string, unknown>;
        const authenticity = (result.authenticity ?? {}) as Record<string, unknown>;
        const status = authenticity.status === "likely_authentic" ? "passed" : "manual_review_required";
        await updateCheckStatus(pgPool, {
          runId: payload.runId,
          checkType: "certificates",
          status,
          resultPayload: result
        });
      } catch (error) {
        await updateCheckStatus(pgPool, {
          runId: payload.runId,
          checkType: "certificates",
          status: "failed",
          lastError: error instanceof Error ? error.message : "certificate check failed"
        });
      }
      await recomputeOverallStatus(pgPool, payload.runId);
    },
    { connection: queueConnection() }
  );
}
