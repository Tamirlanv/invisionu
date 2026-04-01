import { Worker } from "bullmq";

import { env } from "../../config/env.js";
import { pgPool } from "../../db/pg.js";
import { recomputeOverallStatus, updateCheckStatus } from "../../repositories/validationOrchestratorRepository.js";
import { queueConnection } from "../queues.js";

export function startVideoWorker(): Worker {
  return new Worker(
    "invision_orchestrator_video",
    async (job) => {
      const payload = job.data as { runId: string; applicationId: string; videoUrl: string };
      await updateCheckStatus(pgPool, {
        runId: payload.runId,
        checkType: "videoPresentation",
        status: "processing",
        incrementAttempts: true
      });
      try {
        const res = await fetch(env.VIDEO_VALIDATION_URL, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            videoUrl: payload.videoUrl,
            applicationId: payload.applicationId
          })
        });
        const result = (await res.json()) as Record<string, unknown>;
        const checks = (result.derivedChecks ?? {}) as Record<string, unknown>;
        const status = checks.likelyPresentationValid === true ? "passed" : "manual_review_required";
        await updateCheckStatus(pgPool, {
          runId: payload.runId,
          checkType: "videoPresentation",
          status,
          resultPayload: result
        });
      } catch (error) {
        await updateCheckStatus(pgPool, {
          runId: payload.runId,
          checkType: "videoPresentation",
          status: "failed",
          lastError: error instanceof Error ? error.message : "video check failed"
        });
      }
      await recomputeOverallStatus(pgPool, payload.runId);
    },
    { connection: queueConnection() }
  );
}
