import { Worker } from "bullmq";

import { env } from "../../config/env.js";
import { pgPool } from "../../db/pg.js";
import {
  addAuditEvent,
  recomputeOverallStatus,
  updateCheckStatus
} from "../../repositories/validationOrchestratorRepository.js";
import { queueConnection } from "../queues.js";

export function startLinkWorker(): Worker {
  return new Worker(
    "invision_orchestrator_link",
    async (job) => {
      const payload = job.data as { runId: string; applicationId: string; url: string };
      await updateCheckStatus(pgPool, {
        runId: payload.runId,
        checkType: "links",
        status: "processing",
        incrementAttempts: true
      });
      await addAuditEvent(pgPool, {
        runId: payload.runId,
        checkType: "links",
        eventType: "check_processing_started",
        payload: { jobId: job.id as string }
      });
      try {
        const res = await fetch(env.LINK_VALIDATION_URL, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ url: payload.url, application_id: payload.applicationId })
        });
        const result = (await res.json()) as Record<string, unknown>;
        const status = result.availabilityStatus === "reachable" ? "passed" : "manual_review_required";
        await updateCheckStatus(pgPool, {
          runId: payload.runId,
          checkType: "links",
          status,
          resultPayload: result
        });
      } catch (error) {
        await updateCheckStatus(pgPool, {
          runId: payload.runId,
          checkType: "links",
          status: "failed",
          lastError: error instanceof Error ? error.message : "link check failed"
        });
      }
      await recomputeOverallStatus(pgPool, payload.runId);
    },
    { connection: queueConnection() }
  );
}
